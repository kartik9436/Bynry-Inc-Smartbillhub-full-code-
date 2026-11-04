# ── Trace ──────────────────────────────────────────────
# Change:   CR-180-BRC10 — Fix a bill, revamped: B1–B10, the server half
#           (12-governance/change-requests/CR-180-BRC10-fix-a-bill-revamp.md,
#           "The contract between server and screen")
#           Screens: S30 (Fix a bill tab — Bills · Fix · Check · Send)
# Rules:    BR-BIL-004 · BR-BIL-011 · BR-BIL-014 (no money-bearing write before
#           approval: the preview writes NOTHING) · BR-BIL-018 (back-bill
#           window, theft exempt) · BR-BIL-041/042 (R > C > D, derived across the
#           rows) · BR-BIL-043 · BR-BIL-044 (approval binds the figures; moved
#           figures refuse) · BR-BIL-045 (posting period named before confirm) ·
#           BR-BIL-047 (one bill, one transaction; no batch rollback) ·
#           BR-BIL-048 (one open case per bill) · BR-PAY-010/031 · BR-TEN-038 ·
#           BR-TEN-043 · CLAUDE.md rules 1–8
# Journey:  08-qa/01-e2e/journeys/J-FIX-TWENTY-the-fix-a-bill-scenario-suite.md
# Tests:    06-backend/tests/test_cr180_fix_a_bill_revamp.py
# Impacts:  apps/billing/corrections_api.py (the four routes) ·
#           apps/billing/bulk_corrections.py (the case loop hands an item case
#           here) · apps/billing/corrections.py (execute_restatement's
#           `rebill_data` / `goodwill_amount`) · apps/billing/metering_seam.py
#           (the corrected reading, saved)
# ───────────────────────────────────────────────────────
"""Fix a bill from a TABLE of corrections — re-price, preview, send, issue.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 rating math (the re-price from a plan,
a schedule version, a tax rate, an added charge, a deposit, corrected dates and
an assessed usage), money rounding, and the hand-off to the ledger and to
payments all meet in this module. AI-authored 2026-10-12 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md. **It implements signed law and
invents none**: every figure is the rating engine's, through the ONE pricing
path (`runs.price_account`), and every posting is the existing mechanism's.

════════════════════════════════════════════════════════════════════════════
WHAT CHANGED, IN THE PO'S WORDS (decision log 2026-10-12, *FIX A BILL REVAMP*)
════════════════════════════════════════════════════════════════════════════
* *"one customer and bulk - two options"* — scopes `account` (one account, one
  or many of its bills, ONE case) and `run` / `price_mistake`.
* *"Instead of that if we do Table array … then user can add one otr mulitple
  correctiosn … and then say apply this to 1 or more bill"* — a case is N
  ROWS (`correction_case_items`), each naming WHAT was wrong, WHICH item, the
  value it should have been, and which bills it applies to.
* *"you ahve to allow user to select the plan and plan version"* — a plan row
  pins the plan AND the version; a rate row pins the schedule AND the version.
* *"in reprint case also - we hsould provide inputs field"* — a reprint row
  carries the field and its new value, served as field · was · becomes.
* The class is DERIVED across the rows, R > C > D (BR-BIL-041/042, signed) —
  per bill from the rows that apply to it, and for the case the strongest.

════════════════════════════════════════════════════════════════════════════
THE PREVIEW WRITES NOTHING, AND THE CASE IS OPENED AT SEND
════════════════════════════════════════════════════════════════════════════
`preview` gathers and prices and returns — no case, no row, no reading saved
(BR-BIL-014; the test counts fourteen tables before and after). `open_at_send`
re-runs the same computation inside one transaction, compares its content hash
with the one the clerk's screen was drawn from, and REFUSES if the figures
moved (BR-BIL-044, J-FIX-TWENTY S19 *"Figures changed. Check again."*). A clerk
who previews and walks away leaves nothing behind (S20) — the defect the
decision log measured on the demo tenant (a case opened at step 1 blocked the
bill under BR-BIL-048).

════════════════════════════════════════════════════════════════════════════
THE REBILL IS PRICED FROM THE SAME DATA THE PREVIEW WAS
════════════════════════════════════════════════════════════════════════════
`prepare_bill` builds the account's billing data — the corrected period, the
pinned plan version, the readings (the TYPED reading in the preview; the SAVED
one at issue), the mid-period split — and `_apply_rows` lays the rows over it.
The preview prices that with `runs.price_account`; approve-and-issue hands the
SAME data to `corrections.execute_restatement(rebill_data=…)`, whose rebill is
`runs.calculate_account` over it — `price_account` plus the one write. The
preview total and the issued total are therefore one computation, and a drift
between them is refused per bill before anything is written.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from django.apps import apps as django_apps
from django.db import IntegrityError, transaction

from apps.billing import (
    bulk_corrections,
    correction_reasons,
    corrections,
    delivery_seam,
    gather,
    metering_seam,
    models,
    posting_seam,
    rating_seam,
    runs,
    single,
    single_correction,
)
from apps.billing.correction_models import (
    BILL_ABANDONED,
    BILL_DONE,
    BILL_QUEUED,
    CASE_PENDING_APPROVAL,
    CLASS_CREDIT_ONLY,
    CLASS_DOCUMENT,
    CLASS_RESTATEMENT,
    SCOPE_ACCOUNT,
    SCOPE_PRICE_MISTAKE,
    SCOPE_SINGLE,
    CorrectionCase,
    CorrectionCaseBill,
    CorrectionCaseItem,
    InvoiceDocumentInstance,
)
from apps.billing.exceptions import BillingRuleError
from core import audit, money
from core import tenancy as core_tenancy

ZERO = Decimal("0")

# ── message keys — the refusals a clerk reads (eleven catalogues) ───────────
KEY_ITEMS_REQUIRED = "billing.correction.itemsRequired"
KEY_ITEM_INVALID = "billing.correction.itemInvalid"
KEY_REASON_NOT_FOR_SCOPE = "billing.correction.reasonNotForScope"
KEY_NOT_ON_THIS_BILL = "billing.correction.notOnThisBill"
KEY_FIGURES_MOVED = "billing.correction.figuresMoved"
KEY_NO_BILLS = "billing.correction.noBills"
KEY_IN_OPEN_CASE = "billing.correction.inOpenCase"

#: What the preview's answer says it wrote. A FACT, served so a screen can show
#: that nothing exists yet without inferring it from an absent case id.
WRITES_NOTHING = "nothing"

#: The REPRINT reasons and the page fields each may change — the payload keys
#: `document_correction.CORRECTABLE_PAYLOAD_KEYS` accepts, grouped by the
#: reason a clerk picks. The first is the default when a row names no field.
REPRINT_FIELDS: dict[str, tuple[str, ...]] = {
    "customer_name": ("customer_name",),
    "service_or_mailing_address": ("service_address", "mailing_address"),
    "premises_or_unit_label": ("premises_label", "unit_label"),
    "meter_number_or_read_dates": ("meter_number", "read_dates"),
    "template_or_language": ("message", "language"),
}

#: Which reasons each scope takes. **One customer** takes every reason. A bulk
#: run takes the re-price reasons and the template/language reprint; a price
#: mistake is re-price only — decision log 2026-10-12, item 2's matrix, which
#: the later instructions kept (they changed the option NAMES, not the matrix).
_REPRICE_ROWS = frozenset(
    {
        "wrong_rate",
        "wrong_plan",
        "wrong_rate_plan",
        "wrong_tax",
        "missed_charge",
        "charge_billed_in_error",
    }
)
_RUN_ROWS = _REPRICE_ROWS | {"wrong_discount", "template_or_language"}


def reasons_for_scope(kind: str) -> frozenset[str] | None:
    """The reasons a scope accepts — `None` means every seeded reason."""
    if kind in (SCOPE_ACCOUNT, SCOPE_SINGLE):
        return None
    if kind == SCOPE_PRICE_MISTAKE:
        return _REPRICE_ROWS
    return _RUN_ROWS


# ═══════════════════════════════════════════════════════════════════════════
# ROWS — the "What was wrong" table, validated
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Item:
    """One correction row, exactly as the contract's ITEM states it."""

    position: int
    reason: str
    correction_class: str
    item: str | None = None
    act: str | None = None
    value: str | None = None
    value2: str | None = None
    bill_ids: tuple[str, ...] | None = None

    def applies_to(self, invoice_id: Any) -> bool:
        return self.bill_ids is None or str(invoice_id) in self.bill_ids

    def as_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "reason": self.reason,
            "correction_class": self.correction_class,
            "item": self.item,
            "act": self.act,
            "value": self.value,
            "value2": self.value2,
            "bill_ids": None if self.bill_ids is None else list(self.bill_ids),
        }


def _refuse(key: str, detail: str, *, row: int | None = None, br_ref: str = "BR-BIL-014"):
    params: dict[str, Any] = {"detail": detail}
    if row is not None:
        params["row"] = row
    return BillingRuleError(detail, br_ref=br_ref, message_key=key, params=params)


def _text(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, float):
        # Rule 2 — a JSON number is an IEEE double by the time it arrives; a
        # value that may be money is refused as a float, never coerced.
        raise _refuse(KEY_ITEM_INVALID, "send numbers as strings, never as JSON numbers")
    text = str(raw).strip()
    return text or None


def _decimal(text: str | None, *, row: int, what: str) -> Decimal:
    try:
        value = Decimal(str(text))
    except (InvalidOperation, TypeError, ValueError) as bad:
        raise _refuse(KEY_ITEM_INVALID, f"row {row}: {what} is not a number", row=row) from bad
    if not value.is_finite():
        raise _refuse(KEY_ITEM_INVALID, f"row {row}: {what} is not a number", row=row)
    return value


def _uuid(text: str | None, *, row: int, what: str) -> str:
    try:
        return str(UUID(str(text)))
    except (ValueError, AttributeError, TypeError) as bad:
        raise _refuse(
            KEY_ITEM_INVALID, f"row {row}: {what} is not one this utility has", row=row
        ) from bad


def _date(text: str | None, *, row: int, what: str) -> date:
    try:
        return date.fromisoformat(str(text))
    except (ValueError, TypeError) as bad:
        raise _refuse(KEY_ITEM_INVALID, f"row {row}: {what} is not a date", row=row) from bad


def parse_items(
    raw_items: Any, *, scope_kind: str, bill_ids_in_scope: tuple[str, ...]
) -> tuple[Item, ...]:
    """The rows, validated — or a refusal naming the row. Writes nothing.

    Validates the SHAPE of every row (the right fields for its reason, numbers
    as strings, a known field for a reprint, bills inside the scope). Whether
    the row's ITEM is on a given bill — a meter, a schedule, a tax — is asked
    per bill when it is priced, because only the bill can answer it.
    """
    if not isinstance(raw_items, list) or not raw_items:
        raise _refuse(KEY_ITEMS_REQUIRED, "add at least one correction")
    allowed = reasons_for_scope(scope_kind)
    in_scope = set(bill_ids_in_scope)
    out: list[Item] = []
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            raise _refuse(KEY_ITEM_INVALID, f"row {index} is not a correction", row=index)
        reason = _text(raw.get("reason")) or ""
        if reason in correction_reasons.ROUTED_ELSEWHERE or (
            reason not in correction_reasons.SEEDED_REASON_CLASSES
        ):
            raise _refuse(KEY_ITEM_INVALID, f"row {index}: {reason!r} is not a reason", row=index)
        if allowed is not None and reason not in allowed:
            raise _refuse(
                KEY_REASON_NOT_FOR_SCOPE,
                f"row {index}: {reason} is not corrected from this option",
                row=index,
                br_ref="BR-BIL-042",
            )
        item = _text(raw.get("item"))
        act = _text(raw.get("act"))
        value = _text(raw.get("value"))
        value2 = _text(raw.get("value2"))
        raw_bills = raw.get("bill_ids")
        bills: tuple[str, ...] | None
        if raw_bills is None:
            bills = None
        elif isinstance(raw_bills, list) and raw_bills:
            bills = tuple(str(one) for one in raw_bills)
            stray = [one for one in bills if one not in in_scope]
            if stray:
                raise _refuse(
                    KEY_ITEM_INVALID, f"row {index} applies to a bill outside this list", row=index
                )
        else:
            raise _refuse(KEY_ITEM_INVALID, f"row {index} applies to no bill", row=index)

        # ── the fields each reason needs ────────────────────────────────────
        if reason in ("wrong_read", "theft_restated"):
            _uuid(item, row=index, what="the meter")
            quantity = _decimal(value, row=index, what="the value")
            if quantity < ZERO:
                raise _refuse(KEY_ITEM_INVALID, f"row {index}: a negative value", row=index)
        elif reason == "wrong_plan":
            _uuid(item, row=index, what="the plan")
            if value is not None:
                _uuid(value, row=index, what="the plan version")
        elif reason == "wrong_rate":
            _uuid(item, row=index, what="the rate schedule")
            if value is not None:
                _uuid(value, row=index, what="the schedule version")
        elif reason == "wrong_tax":
            if not item:
                raise _refuse(KEY_ITEM_INVALID, f"row {index}: name the tax", row=index)
            if value is not None:
                pct = _decimal(value, row=index, what="the rate")
                if pct < ZERO or pct > Decimal("100"):
                    raise _refuse(KEY_ITEM_INVALID, f"row {index}: a rate is 0–100%", row=index)
        elif reason == "missed_charge":
            if not item:
                raise _refuse(KEY_ITEM_INVALID, f"row {index}: name the charge code", row=index)
            if _decimal(value or "1", row=index, what="the quantity") <= ZERO:
                raise _refuse(KEY_ITEM_INVALID, f"row {index}: a quantity above zero", row=index)
        elif reason == "charge_billed_in_error":
            if not item:
                raise _refuse(KEY_ITEM_INVALID, f"row {index}: name the charge", row=index)
        elif reason == "wrong_discount":
            _uuid(item, row=index, what="the discount")
            if act not in ("add", "remove"):
                raise _refuse(KEY_ITEM_INVALID, f"row {index}: add or remove", row=index)
        elif reason == "wrong_deposit":
            if _decimal(value, row=index, what="the deposit") < ZERO:
                raise _refuse(KEY_ITEM_INVALID, f"row {index}: a negative deposit", row=index)
            item = item or "DEP"
        elif reason == "wrong_period_or_service":
            if (item or "dates") == "dates":
                item = "dates"
                start = _date(value, row=index, what="the start")
                end = _date(value2, row=index, what="the end")
                if end < start:
                    raise _refuse(
                        KEY_ITEM_INVALID, f"row {index}: the end is before the start", row=index
                    )
            # otherwise `item` is a service code the bill should not carry
        elif reason == "goodwill":
            if _decimal(value, row=index, what="the amount") <= ZERO:
                raise _refuse(KEY_ITEM_INVALID, f"row {index}: an amount above zero", row=index)
            item = item or "credit"
        elif reason in REPRINT_FIELDS:
            fields_ = REPRINT_FIELDS[reason]
            item = item or fields_[0]
            if item not in fields_:
                raise _refuse(
                    KEY_ITEM_INVALID, f"row {index}: {item} is not this reason's field", row=index
                )
            if value is None:
                raise _refuse(KEY_ITEM_INVALID, f"row {index}: type the new value", row=index)
        out.append(
            Item(
                position=index,
                reason=reason,
                correction_class=correction_reasons.SEEDED_REASON_CLASSES[reason],
                item=item,
                act=act,
                value=value,
                value2=value2,
                bill_ids=bills,
            )
        )
    return tuple(out)


def case_class(items: tuple[Item, ...]) -> str:
    """BR-BIL-041/042 — the strongest class across the rows (R > C > D)."""
    return correction_reasons.class_for([one.reason for one in items])


# ═══════════════════════════════════════════════════════════════════════════
# PINS — what the rows that apply to ONE bill ask the re-price to change
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class Pins:
    plan_id: str | None = None
    plan_version_id: str | None = None
    binding_day: date | None = None
    schedules: dict[str, str | None] = field(default_factory=dict)
    tax_rates: dict[str, Decimal | None] = field(default_factory=dict)
    charges_add: list[tuple[str, Decimal, int]] = field(default_factory=list)
    lines_remove: list[tuple[str, int]] = field(default_factory=list)
    discounts_remove: list[tuple[str, int]] = field(default_factory=list)
    discounts_add: list[tuple[str, int]] = field(default_factory=list)
    deposit: Decimal | None = None
    period: tuple[date, date] | None = None
    services_off: set[str] = field(default_factory=set)
    readings: dict[str, str] = field(default_factory=dict)
    assessed: dict[str, tuple[Decimal, int]] = field(default_factory=dict)
    goodwill: Decimal = ZERO
    page: dict[str, str] = field(default_factory=dict)
    theft: bool = False
    #: Set by `prepare_bill`: the services whose usage was shared by days
    #: (PO 2026-10-13 — a shortened period with no reading on its new end).
    shared_by_days: tuple[str, ...] = ()

    def keyed_reads(self) -> tuple[dict[str, Any], ...] | None:
        """The typed readings in metering's overlay shape — the one-time bill's
        option (`runs.KEYED_WINS_OVER_COMMITTED`, DEF-BIL-10067): the typed
        value replaces the committed reading in the period, counted from the
        dial the period opens at. Writes nothing."""
        if not self.readings:
            return None
        return tuple(
            {"asset_id": asset_id, "value": value, runs.KEYED_WINS_OVER_COMMITTED: True}
            for asset_id, value in self.readings.items()
        )


def _rating_model(name: str) -> Any:
    return django_apps.get_model("rating", name)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def pins_for(invoice: models.Invoice, items: tuple[Item, ...]) -> Pins:
    """The rows that apply to THIS bill, turned into what the re-price changes.

    Reads rating's rows THROUGH THE APP REGISTRY (identity only — which plan a
    version belongs to, which schedule a version belongs to, a programme's
    code) the way `single_correction._actor` reads identity: billing imports
    no other module's models (B1, G6). Refuses a row whose item is not this
    utility's, naming the row.
    """
    pins = Pins()
    tenant_id = invoice.tenant_id
    for one in items:
        if not one.applies_to(invoice.pk):
            continue
        reason, row = one.reason, one.position
        if reason == "wrong_read":
            if metering_seam.read_on_bill_for_meter(invoice, one.item) is None:
                raise _refuse(
                    KEY_NOT_ON_THIS_BILL,
                    f"row {row}: bill {invoice.invoice_no} was not priced from that meter",
                    row=row,
                )
            pins.readings[str(one.item)] = str(one.value)
        elif reason == "theft_restated":
            read_id = metering_seam.read_on_bill_for_meter(invoice, one.item)
            if read_id is None:
                raise _refuse(
                    KEY_NOT_ON_THIS_BILL,
                    f"row {row}: bill {invoice.invoice_no} was not priced from that meter",
                    row=row,
                )
            pins.assessed[read_id] = (Decimal(str(one.value)), row)
            pins.theft = True
        elif reason == "wrong_plan":
            plan_model = _rating_model("RatePlan")
            if not plan_model.objects.filter(tenant_id=tenant_id, pk=one.item).exists():
                raise _refuse(
                    KEY_ITEM_INVALID, f"row {row}: that plan is not this utility's", row=row
                )
            pins.plan_id = str(one.item)
            if one.value is not None:
                version = (
                    _rating_model("PlanVersion")
                    .objects.filter(
                        tenant_id=tenant_id,
                        pk=one.value,
                        rate_plan_id=one.item,
                        status="published",
                        superseded_by__isnull=True,
                        effective_from__isnull=False,
                    )
                    .values("id", "effective_from")
                    .first()
                )
                if version is None:
                    raise _refuse(
                        KEY_ITEM_INVALID,
                        f"row {row}: that version is not a priced version of the plan",
                        row=row,
                    )
                pins.plan_version_id = str(version["id"])
                pins.binding_day = version["effective_from"]
        elif reason == "wrong_rate":
            if one.value is not None:
                ok = (
                    _rating_model("TariffVersion")
                    .objects.filter(
                        tenant_id=tenant_id,
                        pk=one.value,
                        tariff_id=one.item,
                        effective_from__isnull=False,
                    )
                    .exists()
                )
                if not ok:
                    raise _refuse(
                        KEY_ITEM_INVALID,
                        f"row {row}: that version is not a priced version of the schedule",
                        row=row,
                    )
            pins.schedules[str(one.item)] = None if one.value is None else str(one.value)
        elif reason == "wrong_tax":
            pins.tax_rates[str(one.item)] = (
                None
                if one.value is None
                else (Decimal(str(one.value)) / Decimal("100")).quantize(Decimal("0.000001"))
            )
        elif reason == "missed_charge":
            pins.charges_add.append((str(one.item), Decimal(str(one.value or "1")), row))
        elif reason == "charge_billed_in_error":
            pins.lines_remove.append((str(one.item), row))
        elif reason == "wrong_discount":
            code = (
                _rating_model("Discount")
                .objects.filter(tenant_id=tenant_id, pk=one.item)
                .values_list("code", flat=True)
                .first()
            )
            if code is None:
                raise _refuse(
                    KEY_ITEM_INVALID, f"row {row}: that discount is not this utility's", row=row
                )
            (pins.discounts_add if one.act == "add" else pins.discounts_remove).append((code, row))
        elif reason == "wrong_deposit":
            pins.deposit = money.finalize(Decimal(str(one.value)))
        elif reason == "wrong_period_or_service":
            if one.item == "dates":
                pins.period = (date.fromisoformat(one.value), date.fromisoformat(one.value2))
            else:
                pins.services_off.add(str(one.item))
        elif reason == "goodwill":
            pins.goodwill = money.finalize(pins.goodwill + Decimal(str(one.value)))
        elif reason in REPRINT_FIELDS:
            pins.page[str(one.item)] = str(one.value)
    return pins


# ═══════════════════════════════════════════════════════════════════════════
# THE RE-PRICE — gather, lay the rows over it, price it. Writes nothing.
# ═══════════════════════════════════════════════════════════════════════════
def _scope_for(account_id: Any) -> Any:
    """The account to gather, the way `corrections.recompute` finds it — and,
    for an account no longer in the billable set (closed, J-FIX-TWENTY S13),
    customers' own row: a correction re-prices what WAS billed, and a closed
    account's issued bill is correctable when a clerk picks it (the PO's
    carve-out recorded with `DEF-BIL-5377`)."""
    try:
        return single.billable_account(account_id).account
    except gather.GatherProblem as problem:
        if getattr(problem, "reason", None) != single.SINGLE_NOT_BILLABLE:
            raise
        account_or_404 = runs._resolve("customers", "account_or_404")
        if account_or_404 is None:  # pragma: no cover - checked by billable_account
            raise
        return account_or_404(account_id)


def prepare_bill(invoice: models.Invoice, pins: Pins, *, keyed: bool) -> Any:
    """The billing data ONE corrected bill is priced from. **Writes nothing.**

    `keyed=True` (the preview) prices the typed readings without saving them;
    `keyed=False` (approve-and-issue, after `metering_seam.save_corrected_
    reading`) prices what Meter Reads now holds, so the new bill names — and
    its issue locks — the corrected reading.

    The PERIOD is the bill's own unless a row corrected it. The CYCLE length
    stays the original period's (B4.3 ❄️: base is prorated service days ÷
    cycle days, so a move-out date pulled in from the 31st to the 28th bills
    28/31 of the base, never a full base over a shorter cycle).

    A bill typed `cycle` (or a rebill of one) is cut at a mid-period rate or
    plan boundary exactly as the run cuts it (BR-RAT-114), so a corrected
    reading over a price change is re-priced per part (J-FIX-TWENTY S9). A row
    that PINS a plan version prices the whole period on that version — the
    clerk chose it — so that bill is not cut at a plan boundary.
    """
    account = _scope_for(invoice.account_id)
    period_start, period_end = pins.period or (invoice.period_start, invoice.period_end)
    cycle_days = (invoice.period_end - invoice.period_start).days + 1
    scope_services: tuple[str, ...] | None = None
    if pins.services_off:
        billed = sorted(
            {
                code
                for code in models.InvoiceLine.objects.filter(
                    tenant_id=invoice.tenant_id, invoice=invoice
                ).values_list("service__code", flat=True)
                if code
            }
        )
        unknown = sorted(pins.services_off - set(billed))
        if unknown:
            raise _refuse(
                KEY_NOT_ON_THIS_BILL, f"bill {invoice.invoice_no} did not bill {unknown[0]}"
            )
        scope_services = tuple(code for code in billed if code not in pins.services_off)
        if not scope_services:
            raise _refuse(
                KEY_ITEM_INVALID, f"bill {invoice.invoice_no} would bill no service at all"
            )
    keyed_reads = pins.keyed_reads() if keyed else None
    with rating_seam.grants_excluded(invoice.pk):
        readings, _unmeasured = runs.readings_for_account(
            account,
            period_start=period_start,
            period_end=period_end,
            scope_services=scope_services,
            keyed_reads=keyed_reads,
        )
        if pins.period is not None:
            readings = _share_usage_by_days(
                readings,
                invoice,
                pins,
                account=account,
                period_start=period_start,
                period_end=period_end,
                scope_services=scope_services,
                keyed_reads=keyed_reads,
            )
        data = gather.gather_account(
            account=account,
            service_date=invoice.service_date,
            period_start=period_start,
            period_end=period_end,
            cycle_days=cycle_days,
            readings=readings,
            scope_services=scope_services,
            rate_plan_id=pins.plan_id,
            binding_day=pins.binding_day,
        )
        if invoice.bill_type in ("cycle", "rebill") and pins.plan_id is None:
            from apps.billing import midperiod

            data = replace(
                data,
                split_segments=midperiod.gather_split(
                    account,
                    period_start=period_start,
                    period_end=period_end,
                    cycle_days=cycle_days,
                    scope_services=scope_services,
                    keyed_reads=keyed_reads,
                ),
            )
    from apps.billing.stages import resolve_subscription as subscription

    if data.behavior_class not in subscription.CLASSES_THAT_BILL:
        # DEF-BIL-10089 — the account is closed (or otherwise not billable)
        # NOW, but this bill WAS billed: a correction re-prices what was issued,
        # and the PO's carve-out of 2026-09-15 (`DEF-BIL-5377`) lets a clerk who
        # picks a closed account's bill correct it. Priced as the ordinary
        # billable class; the balance stays on the closed account.
        data = replace(
            data,
            behavior_class=subscription.CLASS_BILLABLE,
            # A bill cut at a mid-period price change prices each part from its
            # own gathered data, which carries the same class.
            split_segments=tuple(
                replace(seg, data=replace(seg.data, behavior_class=subscription.CLASS_BILLABLE))
                for seg in (getattr(data, "split_segments", ()) or ())
            ),
        )
    return _apply_rows(data, pins, invoice)


#: The reading flag a re-priced bill carries when its usage was shared by days.
USAGE_SHARED_BY_DAYS = "usage_shared_by_days"


def _share_usage_by_days(
    readings: Any,
    invoice: models.Invoice,
    pins: Pins,
    *,
    account: Any,
    period_start: date,
    period_end: date,
    scope_services: Any,
    keyed_reads: Any,
) -> tuple[Any, ...]:
    """PO ruling 2026-10-13 (decision log, *"⚖️ RULED 2026-10-13"* item 3): a
    period SHORTENED by a correction, with no reading on the new end date,
    bills the usage **shared by days**, exactly as base charges are prorated.

    Worked, as the PO was shown: 1–30 Sep shortened to 1–20 Sep bills 20/30 of
    the period's usage. A meter that DOES have a reading on the new end date
    keeps that reading (it measured the shorter period), so 1–31 Jul shortened
    to 1–28 Jul with a reading on 28 Jul is billed exactly as before.

    Before the ruling a shortened window with no reading in it found nothing
    and the bill was refused (*"water … has no reading"*), or the original
    reading's whole usage landed in the shorter period (J-FIX-TWENTY S10).

    The usage shared is the ORIGINAL period's (read over the bill's own
    dates), times the shortened period's days over the bill's days, in the
    reading's own unit (hard rule 3). The services shared are recorded on
    `pins.shared_by_days`, which the preview serves so the line can say
    *usage shared by days*."""
    billed_days = (invoice.period_end - invoice.period_start).days + 1
    days = (period_end - period_start).days + 1
    if days >= billed_days:
        return tuple(readings)
    meter_read = django_apps.get_model("metering", "MeterRead")

    def read_day(reading: Any) -> date | None:
        read_id = getattr(reading, "read_id", None)
        if not read_id:
            return None
        found = (
            meter_read.objects.filter(tenant_id=invoice.tenant_id, id=read_id)
            .values_list("read_at", flat=True)
            .first()
        )
        return None if found is None else found.date()

    def key(reading: Any) -> tuple[str, str | None]:
        return (str(reading.service_code), getattr(reading, "asset_id", None))

    on_end = {
        key(one): one
        for one in readings
        if getattr(one, "consumption", None) is not None and read_day(one) == period_end
    }
    whole, _unmeasured = runs.readings_for_account(
        account,
        period_start=invoice.period_start,
        period_end=invoice.period_end,
        scope_services=scope_services,
        keyed_reads=keyed_reads,
    )
    share = Decimal(days) / Decimal(billed_days)
    out: list[Any] = []
    shared: set[str] = set()
    for reading in whole:
        if key(reading) in on_end:
            out.append(on_end[key(reading)])
            continue
        quantity = getattr(reading, "consumption", None)
        if quantity is None or quantity.amount is None:
            out.append(reading)
            continue
        out.append(
            replace(
                reading,
                consumption=rating_seam.Quantity(
                    amount=quantity.amount * share, unit=quantity.unit
                ),
            )
        )
        shared.add(str(reading.service_code))
    pins.shared_by_days = tuple(sorted(shared))
    return tuple(out)


def price(data: Any) -> Any:
    """The priced bill — `runs.price_account`, the ONE pricing path."""
    return runs.price_account(data).priced


def _version_tariff_ids(version_ids: set[str]) -> dict[str, str]:
    if not version_ids:
        return {}
    return {
        str(pk): str(tariff_id)
        for pk, tariff_id in _rating_model("TariffVersion")
        .objects.filter(tenant_id=_tenant_id(), pk__in=list(version_ids))
        .values_list("id", "tariff_id")
    }


def _repin_schedules(data: Any, pins: Pins, invoice: models.Invoice, matched: set[str]) -> Any:
    """Each tariff priced by a pinned schedule, rebuilt on the pinned VERSION.

    Through `resolution_switch._schedule_from_chain` — the product's ONE way of
    swapping a schedule version into a tariff: the version's prices rebuilt by
    `gather.version_fields_from`, never an id stamped onto another version's
    money. The base charge stays the charge code's (`serve_base=True`;
    `DEF-BIL-7170`: the base comes from the code alone).
    """
    from apps.billing import resolution_switch

    targets = {schedule: version for schedule, version in pins.schedules.items() if version}
    if not targets:
        # A schedule row with no version re-prices at the version in force —
        # the price was fixed in Plans & Rates first (decision log item 3).
        tariff_of = _version_tariff_ids({str(c.version_id) for c in data.tariffs if c.version_id})
        matched.update(tariff_of.get(str(c.version_id)) for c in data.tariffs if c.version_id)
        return data
    tariff_of = _version_tariff_ids({str(c.version_id) for c in data.tariffs if c.version_id})
    rebuilt = []
    for config in data.tariffs:
        schedule = tariff_of.get(str(config.version_id)) if config.version_id else None
        if schedule is not None:
            matched.add(schedule)
        version = targets.get(schedule) if schedule else None
        if version is None or str(config.version_id) == version:
            rebuilt.append(config)
            continue
        try:
            changes = resolution_switch._schedule_from_chain(
                config,
                SimpleNamespace(schedule_version_id=version),
                service_date=invoice.service_date,
                serve_base=True,
            )
        except resolution_switch.RuledPathRefused as refusal:
            raise _refuse(KEY_ITEM_INVALID, str(getattr(refusal, "sentence", refusal))) from refusal
        rebuilt.append(replace(config, **{**changes, "version_id": version}))
    return replace(data, tariffs=tuple(rebuilt))


def _apply_rows(data: Any, pins: Pins, invoice: models.Invoice) -> Any:
    """The rows laid over the gathered data. Pure: returns new data.

    Tariffs and readings change on the parent AND every split part (each part
    is priced on its own tariffs); taxes, fees, deposits and discounts change
    on the PARENT only, because a split bill takes them once from the parent
    (`midperiod.price_split_bill`: *"one tax pass"*).
    """
    matched_schedules: set[str] = set()
    data = _repin_schedules(data, pins, invoice, matched_schedules)
    if data.split_segments:
        parts = []
        for segment in data.split_segments:
            part = _repin_schedules(segment.data, pins, invoice, matched_schedules)
            part = _assess(part, pins, invoice)
            parts.append(replace(segment, data=part))
        data = replace(data, split_segments=tuple(parts))
    missing = sorted(set(pins.schedules) - matched_schedules)
    if missing:
        raise _refuse(
            KEY_NOT_ON_THIS_BILL, f"bill {invoice.invoice_no} was not priced on that schedule"
        )
    if pins.assessed and data.split_segments:
        raise _refuse(
            KEY_ITEM_INVALID,
            f"bill {invoice.invoice_no} is cut at a price change; assess the usage per part",
        )
    data = _assess(data, pins, invoice)
    data = replace(
        data,
        taxes=_retax(data.taxes, pins, invoice),
        fees=_refee(data.fees, pins, invoice),
        discounts=_rediscount(getattr(data, "discounts", ()) or (), pins, invoice),
    )
    return data


def _assess(data: Any, pins: Pins, invoice: models.Invoice) -> Any:
    """A theft assessment (BR-BIL-019) — the assessed USAGE on the meter's read,
    in the read's own unit (hard rule 3: never a bare number)."""
    if not pins.assessed:
        return data
    readings = []
    for reading in data.readings:
        ids = {str(reading.read_id)} | {str(one) for one in (reading.chain_read_ids or ())}
        hit = next((pins.assessed[read_id] for read_id in pins.assessed if read_id in ids), None)
        if hit is None:
            readings.append(reading)
            continue
        quantity, row = hit
        if reading.consumption is None or not getattr(reading.consumption, "unit", None):
            raise _refuse(KEY_ITEM_INVALID, f"row {row}: that reading carries no unit", row=row)
        readings.append(
            replace(
                reading,
                consumption=rating_seam.Quantity(amount=quantity, unit=reading.consumption.unit),
            )
        )
    return replace(data, readings=tuple(readings))


def _retax(taxes: Any, pins: Pins, invoice: models.Invoice) -> tuple[Any, ...]:
    """A tax row: the authority's rate, as the clerk typed it (a %). Matched on
    the tax's identity (`tax_id`) or the name the bill prints; a row naming a
    tax the bill does not carry is refused (`notOnThisBill`) — adding a tax the
    plan never attached is a Plans & Rates change, not a correction."""
    if not pins.tax_rates:
        return tuple(taxes)
    seen: set[str] = set()
    out = []
    for rule in taxes:
        names = {
            str(getattr(rule, "tax_id", "") or ""),
            str(getattr(rule, "code", "") or "").lower(),
            str(getattr(rule, "bill_label", "") or "").lower(),
        }
        key = next((k for k in pins.tax_rates if k in names or k.lower() in names), None)
        if key is None:
            out.append(rule)
            continue
        seen.add(key)
        rate = pins.tax_rates[key]
        out.append(rule if rate is None else replace(rule, rate=rate, flat_amount=None))
    missing = sorted(set(pins.tax_rates) - seen)
    if missing:
        raise _refuse(
            KEY_NOT_ON_THIS_BILL, f"bill {invoice.invoice_no} carries no tax {missing[0]}"
        )
    return tuple(out)


#: The description a corrected deposit line carries — `first_bill`'s own.
DEPOSIT_DESCRIPTION = "Security deposit"


def _charge_code_of(charge_ids: set[str]) -> dict[str, str]:
    if not charge_ids:
        return {}
    return {
        str(pk): str(code)
        for pk, code in _rating_model("Charge")
        .objects.filter(tenant_id=_tenant_id(), pk__in=list(charge_ids))
        .values_list("id", "code")
    }


def _line_matches(line: Any, wanted: str, codes: dict[str, str]) -> bool:
    charge_id = str(getattr(line, "charge_id", "") or "")
    key = corrections._line_key(
        getattr(line, "kind", ""), None, None, str(getattr(line, "description", "") or "")
    )
    return wanted in {charge_id, codes.get(charge_id, ""), key} and bool(wanted)


def _refee(fees: Any, pins: Pins, invoice: models.Invoice) -> tuple[Any, ...]:
    """Charge codes and deposits on the corrected bill.

    1. **The original's own one-off lines are CARRIED.** A late fee, a
       connection charge or a deposit on the original is not re-generated by a
       fresh gather (only recurring and auto-apply codes are, BR-RAT-117), so a
       re-price that dropped them would silently remove charges nobody said
       were wrong. They ride across at their billed figures — a late fee is a
       ❄️ B4 figure and is never re-computed here.
    2. A *charge billed in error* row removes the line it names.
    3. A *missed charge* row adds the code × the quantity, at the code's price
       on the bill's service date (rating's `charge_by_code`).
    4. A *wrong deposit* row sets the deposit: untaxed, kind `deposit`, which
       issue stamps to the deposit-liability designation (BR-BIL-012, US-LED-
       001: *"deposit liability — never revenue"*).
    """
    present = list(fees)
    have_ids = {str(getattr(f, "charge_id", "") or "") for f in present} - {""}
    have_desc = {str(getattr(f, "description", "")).strip().lower() for f in present}
    for line in models.InvoiceLine.objects.filter(
        tenant_id=invoice.tenant_id, invoice=invoice, kind__in=("fee", "deposit")
    ).order_by("created_at", "id"):
        if line.kind == "fee" and line.charge_id and str(line.charge_id) in have_ids:
            continue
        if (
            line.kind == "fee"
            and not line.charge_id
            and line.description.strip().lower() in have_desc
        ):
            continue
        present.append(
            rating_seam.RatedLine(
                kind=line.kind,
                description=line.description,
                amount=money.finalize(line.amount),
                taxable=bool(line.taxable),
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price,
                charge_id=str(line.charge_id) if line.charge_id else None,
            )
        )
    codes = _charge_code_of({str(getattr(f, "charge_id", "") or "") for f in present} - {""})
    for wanted, row in pins.lines_remove:
        kept = [f for f in present if not _line_matches(f, wanted, codes)]
        if len(kept) == len(present):
            raise _refuse(
                KEY_NOT_ON_THIS_BILL,
                f"row {row}: bill {invoice.invoice_no} has no such charge",
                row=row,
            )
        present = kept
    charge_by_code = runs._resolve("rating", "charge_by_code")
    for code, quantity, row in pins.charges_add:
        if charge_by_code is None:
            raise _refuse(
                KEY_ITEM_INVALID, "charge codes cannot be read on this deployment", row=row
            )
        found = charge_by_code(code, invoice.service_date)
        if found is None:
            raise _refuse(KEY_ITEM_INVALID, f"row {row}: no live charge code {code}", row=row)
        unit_price = found.get("amount")
        if unit_price is None:
            raise _refuse(
                KEY_ITEM_INVALID,
                f"row {row}: {code} is not a flat charge; add it on its own bill",
                row=row,
            )
        if not found.get("gl_account_id"):
            # DEF-BIL-10083 — BR-BIL-010: a charge code carries its own GL, and
            # one with none can never issue. Refused at the preview, as
            # `fee_bill.charge_code_line` refuses it, rather than after approval.
            raise _refuse(
                KEY_ITEM_INVALID,
                f"row {row}: charge code {code} has no GL account, so it cannot be billed. "
                "Point it at an account in Taxes & fees -> charge codes first.",
                row=row,
                br_ref="BR-BIL-010",
            )
        unit_price = Decimal(str(unit_price))
        present.append(
            rating_seam.RatedLine(
                kind="fee",
                description=str(found.get("name") or code),
                amount=money.finalize(unit_price * quantity),
                taxable=bool(found.get("taxable_default")),
                quantity=quantity,
                # DEF-BIL-10081 — a count travels with what it counts (hard
                # rule 3), or issue refuses the line after approval. A charge
                # code is counted in units: `fee_bill.BASIS_UNITS["per unit"]`.
                unit="unit",
                unit_price=unit_price,
                charge_id=str(found["id"]),
            )
        )
    if pins.deposit is not None:
        present = [f for f in present if getattr(f, "kind", None) != "deposit"]
        if pins.deposit > ZERO:
            present.append(
                rating_seam.RatedLine(
                    kind="deposit",
                    description=DEPOSIT_DESCRIPTION,
                    amount=pins.deposit,
                    taxable=False,
                )
            )
    return tuple(present)


def _rediscount(discounts: Any, pins: Pins, invoice: models.Invoice) -> tuple[Any, ...]:
    """A discount row. **Remove** drops the programme from this bill. **Add**
    can only confirm a programme that now REACHES the bill — the account's
    enrolment and the plan's binding are the two signed gates (BR-RAT-069/110)
    and a correction may not walk round either, so an enrolment made after the
    bill is picked up by the re-gather and a programme that does not reach the
    bill is refused by name."""
    out = list(discounts)
    for code, row in pins.discounts_remove:
        kept = [d for d in out if str(getattr(d, "code", "")) != code]
        if len(kept) == len(out):
            raise _refuse(KEY_NOT_ON_THIS_BILL, f"row {row}: {code} is not on this bill", row=row)
        out = kept
    for code, row in pins.discounts_add:
        if not any(str(getattr(d, "code", "")) == code for d in out):
            raise _refuse(
                KEY_ITEM_INVALID, f"row {row}: enrol the account in {code} first", row=row
            )
    return tuple(out)


# ═══════════════════════════════════════════════════════════════════════════
# THE BILL, LAID OUT THE WAY IT PRINTS — old beside new (F4, item 8)
# ═══════════════════════════════════════════════════════════════════════════
def _qty(value: Any) -> str | None:
    if value is None:
        return None
    text = format(Decimal(str(value)).quantize(Decimal("0.000001")).normalize(), "f")
    return text


def _unit_price(value: Any) -> str | None:
    """PO 2026-10-02: *"Show unit prices with up to 4 decimals and keep every
    total at 2."* — as many places as the price carries, at least 2, at most 4."""
    if value is None:
        return None
    quantized = Decimal(str(value)).quantize(Decimal("0.0001"))
    text = format(quantized.normalize(), "f")
    if "." not in text:
        return f"{text}.00"
    whole, frac = text.split(".")
    return f"{whole}.{frac.ljust(2, '0')}"


def _amount(value: Any) -> str:
    return str(money.finalize(Decimal(str(value))))


def _rate_types(version_ids: set[str]) -> dict[str, str]:
    if not version_ids:
        return {}
    return {
        str(pk): str(model)
        for pk, model in _rating_model("TariffVersion")
        .objects.filter(tenant_id=_tenant_id(), pk__in=list(version_ids))
        .values_list("id", "model")
    }


def bill_layout(lines: list[dict[str, Any]], *, total: Any, currency: str) -> dict[str, Any]:
    """One side of the comparison, as the bill is laid out (decision log 2026-
    10-12 item 8): each service with its rate type, base and usage lines; then
    charge codes, discounts, deposits, the subtotal, taxes per authority WITH
    THEIR BASE, and the total. Every line carries quantity × unit price, and a
    `key` the two sides line up on (*"a change of rate type shows as — on one
    side"*). Reads only."""
    services: dict[str, dict[str, Any]] = {}
    charges: list[dict[str, Any]] = []
    discounts: list[dict[str, Any]] = []
    deposits: list[dict[str, Any]] = []
    taxes: list[dict[str, Any]] = []
    subtotal = ZERO
    taxable_base = ZERO
    for line in lines:
        row = {
            "key": f"{line['kind']}:{line.get('service') or ''}:{line['description'].strip().lower()}",
            "description": line["description"],
            "quantity": _qty(line.get("quantity")),
            "unit": line.get("unit"),
            "unit_price": _unit_price(line.get("unit_price")),
            "amount": _amount(line["amount"]),
        }
        kind = line["kind"]
        if kind != "tax":
            subtotal += Decimal(str(line["amount"]))
        if line.get("taxable"):
            taxable_base += Decimal(str(line["amount"]))
        if kind in ("usage", "base", "minimum_adjustment") and line.get("service"):
            bucket = services.setdefault(
                line["service"],
                {
                    "service": line["service"],
                    "rate_type": line.get("rate_type"),
                    "base": [],
                    "usage": [],
                },
            )
            if bucket["rate_type"] is None and line.get("rate_type"):
                bucket["rate_type"] = line.get("rate_type")
            bucket["base" if kind == "base" else "usage"].append(row)
        elif kind == "discount":
            discounts.append(row)
        elif kind == "deposit":
            deposits.append(row)
        elif kind == "tax":
            taxes.append(row | {"rate": _unit_price(line.get("unit_price"))})
        else:
            charges.append(row)
    for row in taxes:
        row["base"] = _amount(taxable_base)
    return {
        "services": list(services.values()),
        "charges": charges,
        "discounts": discounts,
        "deposits": deposits,
        "subtotal": _amount(subtotal),
        "taxes": taxes,
        "total": _amount(total),
        "currency": currency,
    }


def _old_lines(invoice: models.Invoice) -> list[dict[str, Any]]:
    rows = list(
        models.InvoiceLine.objects.filter(tenant_id=invoice.tenant_id, invoice=invoice)
        .select_related("service")
        .order_by("created_at", "id")
    )
    types = _rate_types({str(r.tariff_version_id) for r in rows if r.tariff_version_id})
    return [
        {
            "kind": r.kind,
            "description": r.description,
            "service": getattr(r.service, "code", None),
            "rate_type": types.get(str(r.tariff_version_id)) if r.tariff_version_id else None,
            "quantity": r.quantity,
            "unit": r.unit,
            "unit_price": r.unit_price,
            "amount": r.amount,
            "taxable": r.taxable,
            "tax_id": str(r.tax_id) if r.tax_id else None,
            "charge_id": str(r.charge_id) if r.charge_id else None,
            "discount_code": r.discount_code,
            "gl_account_id": str(r.gl_account_id) if r.gl_account_id else None,
        }
        for r in rows
    ]


def _new_lines(rated: Any) -> list[dict[str, Any]]:
    lines = list(getattr(rated, "lines", ()) or ())
    types = _rate_types(
        {
            str(getattr(r, "tariff_version_id", ""))
            for r in lines
            if getattr(r, "tariff_version_id", None)
        }
    )
    return [
        {
            "kind": r.kind,
            "description": r.description,
            "service": r.service,
            "rate_type": types.get(str(r.tariff_version_id)) if r.tariff_version_id else None,
            "quantity": r.quantity,
            "unit": r.unit,
            "unit_price": r.unit_price,
            "amount": r.amount,
            "taxable": r.taxable,
            "tax_id": str(r.tax_id) if r.tax_id else None,
            "charge_id": str(r.charge_id) if r.charge_id else None,
            "discount_code": getattr(r, "discount_code", None),
            "gl_account_id": None,
        }
        for r in lines
    ]


# ═══════════════════════════════════════════════════════════════════════════
# ONE BILL'S PREVIEW
# ═══════════════════════════════════════════════════════════════════════════
def _posting(day: date | None) -> tuple[date | None, bool]:
    """BR-BIL-045 / BR-TEN-038 — the date the books will take, through the
    ledger's ONE forward (`posting_seam.forward_for`), and whether it moved."""
    if day is None:
        return None, False
    landing, note = posting_seam.forward_for(day)
    return landing, note is not None


def _new_due_date(invoice: models.Invoice, on_date: date) -> str | None:
    """The corrected bill's due date — **the correction (issue) date plus the
    account's usual days to pay** (PO ruling 2026-10-13, decision log
    *"⚖️ RULED 2026-10-13"* item 2: *"this is correct"*). Worked: corrected on
    10/13 with 20 days to pay is due 11/02/2026; a customer is never late on a
    bill they have just received.

    ⚠ **THIS READ THE ORIGINAL RUN'S BILL DATE UNTIL THAT RULING**, so a
    corrected August bill came out due 09/22/2026 — already past. The rebill's
    run now carries the correction date as its bill date
    (`corrections.execute_restatement`), so the same derivation issue stamps
    (`issue.derive_due_date` over the run's days to pay) gives this figure:
    the preview's `as_of` and the approval's `on_date` are the same business
    day on the screen. None when the days to pay cannot be derived — said,
    not defaulted."""
    from apps.billing import issue

    run = invoice.bill_run
    if run is None:
        return None
    try:
        _bill_date, due_days = issue._due_terms_for(run)
        return issue.derive_due_date(
            on_date, due_days, cycle_less=getattr(run, "cycle_id", None) is None
        ).isoformat()
    except BillingRuleError:
        return None


def _page_changes(invoice: models.Invoice, page: dict[str, str]) -> list[dict[str, Any]]:
    """B6 — *What changes on the page*: field · was · becomes, against the
    document the customer has now (the latest reissue, else the issued page —
    `document_correction`'s accumulate rule, DEF-084)."""
    if not page:
        return []
    previous = (
        InvoiceDocumentInstance.objects.filter(tenant_id=invoice.tenant_id, invoice=invoice)
        .order_by("-instance_no")
        .first()
    )
    base = dict((previous.payload if previous else invoice.bill_payload) or {})
    return [
        {"field": key, "was": base.get(key), "becomes": value}
        for key, value in sorted(page.items())
    ]


@dataclass
class BillPreview:
    invoice: models.Invoice
    items: tuple[Item, ...]
    impact: dict[str, Any] | None
    excluded: dict[str, Any] | None = None
    data: Any = None
    rated: Any = None
    pins: Any = None


def _reasons(items: tuple[Item, ...]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for one in items:
        seen.setdefault(one.reason, None)
    return tuple(seen)


#: The reasons whose row picks a PLAN (decision log 2026-10-13, Q3).
_PLAN_REASONS = frozenset({"wrong_plan", "wrong_rate_plan"})


def _plan_warnings(
    invoice: models.Invoice, mine: tuple[Item, ...], rated: Any
) -> list[dict[str, Any]]:
    """Q3 (decision log 2026-10-13) — a Wrong plan row whose plan bills one of
    this bill's services at $0.00. **A warning, never a refusal**: a plan that
    does not cover a service the account takes is sometimes the correction
    itself, so the row is kept and the screen says *"Water is not on this plan.
    It bills $0.00."* beside the choice.

    A service warns when the OLD bill charged it something and the re-priced
    bill charges it nothing — the engine's own answer, so a plan that prices
    the service at a real $0.00 tier and a plan that does not price it at all
    read the same, which is what the clerk needs to see either way."""
    rows = [one for one in mine if one.reason in _PLAN_REASONS]
    if not rows or rated is None:
        return []
    old: dict[str, Decimal] = {}
    for line in _old_lines(invoice):
        if line.get("service") and line.get("kind") != "tax":
            old[line["service"]] = old.get(line["service"], ZERO) + Decimal(str(line["amount"]))
    new: dict[str, Decimal] = {}
    for line in _new_lines(rated):
        if line.get("service") and line.get("kind") != "tax":
            new[line["service"]] = new.get(line["service"], ZERO) + Decimal(str(line["amount"]))
    zeroed = sorted(
        code for code, amount in old.items() if amount != ZERO and new.get(code, ZERO) == ZERO
    )
    return [
        {"position": one.position, "service_code": code, "amount": "0.00"}
        for one in rows
        for code in zeroed
    ]


def preview_bill(
    invoice: models.Invoice,
    items: tuple[Item, ...],
    *,
    as_of: date,
    backbill_window_months: int,
    keyed: bool = True,
    with_layout: bool = True,
) -> BillPreview:
    """ONE bill's corrected figures, from the rows that apply to it. Writes nothing."""
    mine = tuple(one for one in items if one.applies_to(invoice.pk))
    if not mine:
        return BillPreview(
            invoice=invoice,
            items=mine,
            impact=None,
            excluded={
                "invoice_id": str(invoice.pk),
                "invoice_no": invoice.invoice_no,
                "code": "no_correction_for_this_bill",
            },
        )
    corrections.refuse_unless_latest_in_chain(invoice)
    klass = case_class(mine)
    reasons = _reasons(mine)
    pins = pins_for(invoice, mine)
    data = None
    rated = None
    if klass == CLASS_RESTATEMENT:
        data = prepare_bill(invoice, pins, keyed=keyed)
        rated = price(data)
        posting_date, forwarded = _posting(invoice.service_date)
        impact = corrections.build_impact(
            invoice,
            reason_codes=reasons,
            correction_class=klass,
            corrected=rated,
            posting_period=posting_date,
        )
    elif klass == CLASS_CREDIT_ONLY:
        posting_date, forwarded = _posting(as_of)
        impact = corrections.build_impact(
            invoice,
            reason_codes=reasons,
            correction_class=klass,
            goodwill_amount=pins.goodwill,
        )
    else:
        # BR-BIL-043 — a reprint must not hide a money change. Re-priced on the
        # SAME data path (split-aware), never on the unsplit `recompute`, so a
        # bill cut at a price change is not mistaken for one that moved.
        check = price(prepare_bill(invoice, Pins(), keyed=False))
        if money.finalize(check.total) != money.finalize(invoice.total):
            raise _refuse(
                "billing.correction.refused",
                f"bill {invoice.invoice_no}: re-pricing moves "
                f"{money.finalize(check.total) - money.finalize(invoice.total)}; "
                "pick the reason that describes what is wrong",
                br_ref="BR-BIL-043",
            )
        posting_date, forwarded = None, False
        impact = corrections.build_impact(invoice, reason_codes=reasons, correction_class=klass)
    beyond = corrections.beyond_backbill_window(
        impact,
        as_of=as_of,
        period_end=invoice.period_end,
        window_months=backbill_window_months,
        theft_exempt=pins.theft,
    )
    if beyond is not None:
        return BillPreview(
            invoice=invoice,
            items=mine,
            impact=None,
            excluded={
                "invoice_id": str(invoice.pk),
                "invoice_no": invoice.invoice_no,
                "account_id": str(invoice.account_id),
                "period_start": invoice.period_start.isoformat(),
                "period_end": invoice.period_end.isoformat(),
                **beyond,
            },
        )
    row = impact.as_dict()
    row.update(
        {
            "class": klass,
            "period_start": invoice.period_start.isoformat(),
            "period_end": invoice.period_end.isoformat(),
            "bill_month": invoice.service_date.isoformat() if invoice.service_date else None,
            "posting_period": posting_date.strftime("%Y-%m") if posting_date else None,
            "posting_date": posting_date.isoformat() if posting_date else None,
            "posting_forwarded": forwarded,
            "new_due_date": (_new_due_date(invoice, as_of) if klass == CLASS_RESTATEMENT else None),
            "goodwill": str(pins.goodwill) if pins.goodwill > ZERO else None,
            "page_changes": _page_changes(invoice, pins.page),
            "applied_rows": [one.position for one in mine],
            "plan_warnings": _plan_warnings(invoice, mine, rated),
            USAGE_SHARED_BY_DAYS: list(pins.shared_by_days),
        }
    )
    if with_layout:
        old = bill_layout(_old_lines(invoice), total=invoice.total, currency=invoice.currency)
        new = (
            bill_layout(_new_lines(rated), total=rated.total, currency=invoice.currency)
            if rated is not None
            else old
        )
        if pins.goodwill > ZERO:
            new = new | {"goodwill": str(pins.goodwill)}
        row["layout"] = {"old": old, "new": new}
    return BillPreview(invoice=invoice, items=mine, impact=row, data=data, rated=rated, pins=pins)


# ═══════════════════════════════════════════════════════════════════════════
# THE WHOLE PREVIEW — scope, rows, every bill, the hash
# ═══════════════════════════════════════════════════════════════════════════
SCOPE_KEYS = (
    "account_id",
    "invoice_ids",
    "bill_run_id",
    "cycle_id",
    "plan_id",
    "service_code",
    "period_start",
    "period_end",
    "wrong_kind",
    "wrong_id",
)


def _scope_args(scope: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(scope, dict):
        raise _refuse(KEY_NO_BILLS, "the scope is missing")
    kind = str(scope.get("kind") or scope.get("scope_kind") or "")
    args: dict[str, Any] = {}
    for key in (
        "bill_run_id",
        "cycle_id",
        "plan_id",
        "service_code",
        "account_id",
        "wrong_kind",
        "wrong_id",
    ):
        if scope.get(key) not in (None, ""):
            args[key] = scope[key]
    for key in ("period_start", "period_end"):
        if scope.get(key) not in (None, ""):
            try:
                args[key] = date.fromisoformat(str(scope[key]))
            except ValueError as bad:
                raise _refuse(KEY_NO_BILLS, f"{key} is not a date") from bad
    ids = scope.get("invoice_ids") or ([scope["invoice_id"]] if scope.get("invoice_id") else [])
    if ids:
        args["invoice_ids"] = tuple(str(one) for one in ids)
    return kind, args


def _hash(items: tuple[Item, ...], impacts: list[dict[str, Any]]) -> str:
    """BR-BIL-044's content hash — the rows AND the figures, so a changed row
    with identical figures is still a different artifact to approve."""
    canonical = json.dumps(
        {
            "items": [one.as_dict() for one in items],
            "bills": sorted(impacts, key=lambda impact: str(impact.get("invoice_id"))),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _aggregate(impacts: list[dict[str, Any]]) -> dict[str, Any]:
    """BR-BIL-046 — up and down APART, never netted alone; a display sum over
    the per-bill figures (the same arithmetic as `bulk_corrections.aggregate`,
    over rows not yet written)."""
    up_n = down_n = 0
    up = down = credit = rebill = net = ZERO
    taxes: dict[str, Decimal] = {}
    currency = impacts[0].get("currency") if impacts else None
    for impact in impacts:
        delta = Decimal(impact.get("delta", "0"))
        credit = money.finalize(credit + Decimal(impact.get("original_total", "0")))
        rebill = money.finalize(rebill + Decimal(impact.get("corrected_total", "0")))
        net = money.finalize(net + delta)
        if delta > ZERO:
            up_n += 1
            up = money.finalize(up + delta)
        elif delta < ZERO:
            down_n += 1
            down = money.finalize(down + delta)
        for entry in impact.get("tax_by_authority", []):
            name = entry.get("authority", "")
            taxes[name] = money.finalize(taxes.get(name, ZERO) + Decimal(entry.get("delta", "0")))
    return {
        "bills": len(impacts),
        "currency": currency,
        "credit_total": str(credit),
        "rebill_total": str(rebill),
        "net_delta": str(net),
        "up": {"count": up_n, "total": str(up)},
        "down": {"count": down_n, "total": str(down)},
        "accounts_ending_in_credit": down_n,
        "accounts_owing_more": up_n,
        "warned_rows": sum(1 for impact in impacts if impact.get("warnings")),
        "tax_by_authority": [
            {"authority": name, "delta": str(delta)} for name, delta in sorted(taxes.items())
        ],
    }


@dataclass
class Built:
    kind: str
    scope_args: dict[str, Any]
    items: tuple[Item, ...]
    previews: list[BillPreview]
    impacts: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    correction_class: str
    preview_hash: str


#: DEF-BIL-10096 — a bulk scope's bill that could not be re-priced (left out).
EXCLUDED_CANNOT_PRICE = "cannot_price"


def build(
    scope: dict[str, Any],
    raw_items: Any,
    *,
    as_of: date,
    keyed: bool = True,
    on_bill: Any = None,
) -> Built:
    """The preview's whole computation, shared by `preview` and `open_at_send`
    so the two cannot compute differently. Writes nothing.

    `on_bill(done, total)` (DEF-BIL-10091) is called after each bill, so the
    background preview can show *"Working out 38 bills · 12 done"*."""
    from apps.billing import settings_seam

    kind, args = _scope_args(scope)
    invoices = bulk_corrections.resolve_scope(kind=kind, exclude_in_flight=True, **args)
    # The bills the scope saw and does not offer — drafts, bills an open case
    # holds — listed with a code (contract §1), never dropped in silence.
    excluded = bulk_corrections.excluded_from_scope(kind=kind, **args)
    items = parse_items(
        raw_items, scope_kind=kind, bill_ids_in_scope=tuple(str(one.pk) for one in invoices)
    )
    klass = case_class(items)
    bulk_corrections.refuse_mixed_class_in_bulk(_reasons(items), scope_kind=kind)
    window = settings_seam.back_bill_cap_months()
    with_layout = kind in (SCOPE_ACCOUNT, SCOPE_SINGLE)
    previews: list[BillPreview] = []
    impacts: list[dict[str, Any]] = []
    with _read_memo(len(invoices)) as memo:
        for invoice in invoices:
            memo.step()
            one = _preview_one(
                invoice, items, as_of=as_of, window=window, keyed=keyed, with_layout=with_layout
            )
            previews.append(one)
            if one.impact is None:
                excluded.append(one.excluded or {})
            else:
                impacts.append(one.impact)
            if on_bill is not None:
                on_bill(len(previews), len(invoices))
    if not impacts:
        raise _refuse(KEY_NO_BILLS, "no bill in this list can be corrected")
    return Built(
        kind=kind,
        scope_args=args,
        items=items,
        previews=previews,
        impacts=impacts,
        excluded=excluded,
        correction_class=klass,
        preview_hash=_hash(items, impacts),
    )


#: DEF-BIL-10091 — how many bills share one read memo (`core.batch_reads`).
#: The bulk Check's own batch size (`check_engine.CHUNK`), for the same
#: reason: the memo lives for one batch and is dropped at its end, so a run of
#: 40,000 bills never holds 40,000 bills' answers at once.
READ_MEMO_BILLS = 500


class _ReadMemo:
    """`seam_batch.pass_cache()` for the whole pass and a `batch_reads.batch()`
    re-opened every `READ_MEMO_BILLS` bills — the two memos the bill run's
    prepare pass and the bulk Check already price under (`runs.prepare_run`,
    `check_engine.CheckContext.batches`).

    ⚠ **A MEMO, NEVER A CACHE, AND ONLY ON THE READ-ONLY PASS.** It is opened
    by `build` (the preview, and the approval's check), which writes nothing,
    and never by `execute_bill`, whose readings are saved and re-read between
    two prices. Both memos key on every argument and on the tenant (hard rule
    1), and drop every answer when the pass ends (`seam_batch.pass_cache`'s
    ruling: a memo inside one computation is not a stored answer). The
    correction preview's one context-dependent read, `grants_excluded`, is
    rating's `discount_services`, which memoises nothing.

    MEASURED (DEF-BIL-10091, the demo's September run, 48 bills, PostgreSQL
    16): the figures are in the defect row and the decision log."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.seen = 0
        self._stack: Any = None
        self._batch: Any = None

    def __enter__(self) -> _ReadMemo:
        from contextlib import ExitStack

        from apps.billing import seam_batch

        self._stack = ExitStack()
        self._stack.enter_context(seam_batch.pass_cache())
        return self

    def step(self) -> None:
        from core import batch_reads

        if self.seen % READ_MEMO_BILLS == 0:
            if self._batch is not None:
                self._batch.__exit__(None, None, None)
            self._batch = batch_reads.batch()
            self._batch.__enter__()
        self.seen += 1

    def __exit__(self, *exc: Any) -> None:
        try:
            if self._batch is not None:
                self._batch.__exit__(*exc)
        finally:
            self._stack.__exit__(*exc)


def _read_memo(total: int) -> _ReadMemo:
    return _ReadMemo(total)


def _preview_one(
    invoice: models.Invoice,
    items: tuple[Item, ...],
    *,
    as_of: date,
    window: int,
    keyed: bool,
    with_layout: bool,
) -> BillPreview:
    """One bill of `build` — refused for one customer, left out for bulk."""
    if with_layout:
        return preview_bill(
            invoice,
            items,
            as_of=as_of,
            backbill_window_months=window,
            keyed=keyed,
            with_layout=with_layout,
        )
    # DEF-BIL-10096 — in a BULK scope one bill that cannot be priced is left
    # out with its reason and the rest go on (BR-BIL-055's one named break;
    # the PO's 2026-09-15 rule that a bill is excluded, never the case). One
    # customer still refuses: that clerk picked the bill and must see why. A
    # savepoint, because a refusal raised after a failed statement would
    # poison the PostgreSQL transaction for every bill after it (law 14).
    try:
        with transaction.atomic():
            return preview_bill(
                invoice,
                items,
                as_of=as_of,
                backbill_window_months=window,
                keyed=keyed,
                with_layout=with_layout,
            )
    except BillingRuleError as refusal:
        return BillPreview(
            invoice=invoice,
            items=(),
            impact=None,
            excluded={
                "invoice_id": str(invoice.pk),
                "invoice_no": invoice.invoice_no,
                "account_id": str(invoice.account_id),
                "period_start": invoice.period_start.isoformat(),
                "period_end": invoice.period_end.isoformat(),
                "code": EXCLUDED_CANNOT_PRICE,
                "detail": str(refusal),
            },
        )


def _sections_for(built: Built, impact: dict[str, Any], actor: Any) -> dict[str, Any]:
    """BR-BIL-044's nine sections for one bill — `single_correction.nine_
    sections`, reused over a case that is NOT saved (BR-BIL-014: the preview
    writes nothing). The unsaved rows exist only to carry the arguments."""
    invoice = next(p.invoice for p in built.previews if str(p.invoice.pk) == impact["invoice_id"])
    case = CorrectionCase(
        tenant_id=invoice.tenant_id,
        reason_codes=list(impact.get("reason_codes") or []),
        correction_class=impact["class"],
        scope_kind=built.kind,
        scope={},
        status="preview",
        preview_hash=built.preview_hash,
        posting_period=(
            date.fromisoformat(impact["posting_date"]) if impact.get("posting_date") else None
        ),
        initiated_by_id=audit.actor_user_id(actor),
    )
    row = CorrectionCaseBill(impact=impact, warnings=list(impact.get("warnings") or []))
    return single_correction.nine_sections(
        single_correction.SingleCase(case=case, bill_row=row, invoice=invoice)
    )


def _row_plan_warnings(impacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[int, str], dict[str, Any]] = {}
    for impact in impacts:
        for warning in impact.get("plan_warnings") or ():
            key = (int(warning["position"]), str(warning["service_code"]))
            entry = seen.setdefault(key, {**warning, "bills": 0})
            entry["bills"] += 1
    return [seen[key] for key in sorted(seen)]


def answer_for(
    built: Built, *, actor: Any, page: int | None = None, per: int | None = None
) -> dict[str, Any]:
    """The preview's whole answer from a `Built` — the screen lane's A3 shape
    (`correction_answer.answer`), with this module's own per-bill figures
    (the BillImpact, the nine sections, the by-service layout) merged under
    each A3 row. Where a key is in both, A3's wins: it is the contract the
    screen was built to. Writes nothing."""
    from apps.billing import correction_answer

    body = correction_answer.answer(built, page=page, per=per)
    impacts = {impact["invoice_id"]: impact for impact in built.impacts}
    one_customer = built.kind in (SCOPE_ACCOUNT, SCOPE_SINGLE)
    bills = []
    for row in body["bills"]:
        impact = impacts[row["invoice_id"]]
        entry = {**impact, **row}
        if one_customer:
            entry["sections"] = _sections_for(built, impact, actor)
            entry["section_order"] = [name for _, name in single_correction.PREVIEW_SECTIONS]
        bills.append(entry)
    # Bulk: warned rows first, then the largest movement (BR-BIL-046).
    if not one_customer:
        bills.sort(
            key=lambda b: (0 if b.get("warnings") else 1, -abs(Decimal(b.get("delta", "0"))))
        )
    return {
        **body,
        "bills": bills,
        # Q3 (decision log 2026-10-13) — one warning per Wrong plan row and
        # service, across every bill it applies to; the screen shows it
        # beside that row's choice.
        "plan_warnings": _row_plan_warnings(built.impacts),
        "mechanism_in_words": correction_reasons.mechanism_in_words(built.correction_class),
        "items": [one.as_dict() for one in built.items],
        "aggregate": _aggregate(built.impacts),
        "excluded": built.excluded,
        "writes": WRITES_NOTHING,
    }


def preview(
    scope: dict[str, Any],
    raw_items: Any,
    *,
    as_of: date,
    actor: Any,
    page: int | None = None,
    per: int | None = None,
) -> dict[str, Any]:
    """`POST /corrections/preview` — the whole answer. **Writes nothing.**"""
    return answer_for(build(scope, raw_items, as_of=as_of), actor=actor, page=page, per=per)


# ═══════════════════════════════════════════════════════════════════════════
# SEND — the case is opened here, and only here
# ═══════════════════════════════════════════════════════════════════════════
def _unchanged(impact: dict[str, Any]) -> bool:
    """A re-priced bill whose total did not move and that carries nothing
    else to issue (DEF-BIL-10103)."""
    return (
        str(impact.get("class")) == CLASS_RESTATEMENT
        and Decimal(str(impact.get("delta") or "0")) == ZERO
        and not impact.get("goodwill")
        and not impact.get("page_changes")
    )


@transaction.atomic
def open_at_send(
    scope: dict[str, Any], raw_items: Any, *, as_of: date, preview_hash: str, actor: Any
) -> CorrectionCase:
    """`POST /corrections` with rows — opens the case at SEND (`CR-180` §2).

    Re-runs the preview's computation inside this transaction and REFUSES when
    its hash is not the one the clerk's screen was drawn from (BR-BIL-044;
    J-FIX-TWENTY S19). Then writes the case (`pending_approval`), its pinned
    bills (BR-BIL-046 — the pinned set is a table) and its rows (B3), and the
    hard-rule-7 audit row. **No money**: no credit note, no bill, no journal
    line, no saved reading — BR-BIL-014; those wait for approve-and-issue.

    ⚠ **ONE TRANSACTION (`DEF-BIL-10108`).** `DEF-BIL-10103` inserted
    `_unchanged` between this function and its `@transaction.atomic`, so the
    decorator wrapped the helper and Send ran in autocommit: a refusal after
    the case row (a bill another case holds, or no bill in a bulk list that
    changes) left a half-written case waiting for approval. A BULK Send reaches
    `open_from_preview` instead (`DEF-BIL-10091`), which is atomic too.
    """
    if not isinstance(preview_hash, str) or not preview_hash:
        raise _refuse(KEY_FIGURES_MOVED, "send the figures you checked", br_ref="BR-BIL-044")
    built = build(scope, raw_items, as_of=as_of)
    if built.preview_hash != preview_hash:
        raise _refuse(
            KEY_FIGURES_MOVED,
            "the figures changed since they were checked",
            br_ref="BR-BIL-044",
        )
    from apps.billing import correction_answer

    return _open_case(
        kind=built.kind,
        scope_args=built.scope_args,
        items=built.items,
        impacts=built.impacts,
        excluded=built.excluded,
        correction_class=built.correction_class,
        preview_hash=built.preview_hash,
        answer=correction_answer.answer(built),
        actor=actor,
        as_of=as_of,
    )


def built_record(built: Built) -> dict[str, Any]:
    """What a background preview keeps so Send can open the case from it
    without pricing the scope again (`DEF-BIL-10091`). JSON only."""
    return {
        "kind": built.kind,
        "scope_args": {
            key: (
                value.isoformat()
                if isinstance(value, date)
                else list(value) if isinstance(value, tuple) else value
            )
            for key, value in built.scope_args.items()
        },
        "items": [one.as_dict() for one in built.items],
        "excluded": built.excluded,
        "correction_class": built.correction_class,
    }


def _items_from(rows: Any) -> tuple[Item, ...]:
    return tuple(
        Item(
            position=int(row["position"]),
            reason=str(row["reason"]),
            correction_class=str(row["correction_class"]),
            item=row.get("item"),
            act=row.get("act"),
            value=row.get("value"),
            value2=row.get("value2"),
            bill_ids=None if row.get("bill_ids") is None else tuple(map(str, row["bill_ids"])),
        )
        for row in rows or ()
    )


@transaction.atomic
def open_from_preview(job: Any, *, preview_hash: str, actor: Any) -> CorrectionCase:
    """A BULK Send, from the preview a background job already priced
    (`DEF-BIL-10091`). **Prices nothing.**

    The case is opened from the stored preview — the figures the clerk's screen
    was drawn from — when `preview_hash` is that preview's. A different hash is
    *"Figures changed. Check again."*, as at a one-customer Send. What this
    does NOT do is price the scope a second time to see whether a price moved
    since the preview: that check is made once, at approval, where it binds
    (decision log 2026-10-13, Q5 — a bulk approval is refused when a figure
    moved after Send, exactly as one customer's is). Pricing at Send as well
    was half of the six minutes this defect measured.
    """
    if not isinstance(preview_hash, str) or not preview_hash or preview_hash != job.preview_hash:
        raise _refuse(
            KEY_FIGURES_MOVED, "the figures changed since they were checked", br_ref="BR-BIL-044"
        )
    stored = job.built or {}
    bills = list(job.bills.filter(tenant_id=job.tenant_id).order_by("seq"))
    answer = dict(job.answer or {})
    answer["bills"] = [
        one.row for one in sorted(bills, key=lambda one: one.position)  # the screen's order
    ]
    return _open_case(
        kind=str(stored.get("kind")),
        scope_args=dict(stored.get("scope_args") or {}),
        items=_items_from(stored.get("items")),
        impacts=[one.impact for one in bills],
        excluded=list(stored.get("excluded") or []),
        correction_class=str(stored.get("correction_class")),
        preview_hash=job.preview_hash,
        answer=answer,
        actor=actor,
        # G3 — the Send numbers under the business date the preview was
        # priced for (the Send job copies it from its preview), never a clock.
        as_of=job.as_of,
    )


def _open_case(
    *,
    kind: str,
    scope_args: dict[str, Any],
    items: tuple[Item, ...],
    impacts: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    correction_class: str,
    preview_hash: str,
    answer: dict[str, Any],
    actor: Any,
    as_of: date | None,
) -> CorrectionCase:
    """Write the case, its pinned bills, its rows and the audit row. The
    caller holds the transaction (`open_at_send`, `open_from_preview`).

    G3 (PO 2026-10-14, `DEF-BIL-10147`) — **the case takes its number HERE, at
    Send**, from the tenant's Correction case series, in this transaction: a
    refusal further down (a bill another case holds, no bill that changes)
    rolls the number back with the row it would have numbered. A missing
    series opens the case UNNUMBERED and says why on the audit row; it never
    refuses the Send (`corrections.allocate_case_no`).
    """
    tenant_id = _tenant_id()
    first = impacts[0]
    case_no, numbering_gap = corrections.allocate_case_no(as_of)
    case = CorrectionCase.objects.create(
        tenant_id=tenant_id,
        case_no=case_no,
        reason_codes=list(_reasons(items)),
        correction_class=correction_class,
        scope_kind=kind,
        scope={
            **{
                k: (
                    v
                    if not isinstance(v, (date, tuple))
                    else (v.isoformat() if isinstance(v, date) else list(v))
                )
                for k, v in scope_args.items()
            },
            bulk_corrections.ITEMS_SCOPE_MARKER: len(items),
        },
        status=CASE_PENDING_APPROVAL,
        posting_period=(
            date.fromisoformat(first["posting_date"])
            if len(impacts) == 1 and first.get("posting_date")
            else None
        ),
        initiated_by_id=audit.actor_user_id(actor),
    )
    # DEF-BIL-10103 — in a BULK case a re-priced bill whose total does not
    # move (no goodwill, no page change) is left as it is, as Check says: no
    # credit note and no identical new bill. One customer keeps every bill the
    # clerk picked.
    pinned = [
        impact
        for impact in impacts
        if not (kind not in (SCOPE_ACCOUNT, SCOPE_SINGLE) and _unchanged(impact))
    ]
    if not pinned:
        raise _refuse(KEY_NO_BILLS, "no bill in this list changes")
    for impact in pinned:
        try:
            with transaction.atomic():
                CorrectionCaseBill.objects.create(
                    tenant_id=tenant_id,
                    case=case,
                    invoice_id=impact["invoice_id"],
                    account_id=impact["account_id"],
                    impact=impact,
                    delta_amount=Decimal(impact["delta"]),
                    currency=impact["currency"],
                    direction=impact["direction"],
                    warnings=list(impact.get("warnings") or []),
                    status=BILL_QUEUED,
                )
        except IntegrityError as clash:
            # BR-BIL-048 from the other side — a case opened between this
            # clerk's preview and their Send holds the bill. The savepoint is
            # what lets the refusal be raised cleanly on PostgreSQL (law 14).
            raise _refuse(
                KEY_IN_OPEN_CASE,
                f"bill {impact.get('invoice_no')} is already inside an open correction",
                br_ref="BR-BIL-048",
            ) from clash
    for one in items:
        CorrectionCaseItem.objects.create(
            tenant_id=tenant_id,
            case=case,
            position=one.position,
            reason=one.reason,
            correction_class=one.correction_class,
            item=one.item,
            act=one.act,
            value=one.value,
            value2=one.value2,
            bill_ids=None if one.bill_ids is None else list(one.bill_ids),
        )
    case.preview = {
        "bills": pinned,
        "aggregate": bulk_corrections.aggregate(case).as_dict(),
        "excluded": excluded,
        "items": [one.as_dict() for one in items],
        # A4 — the A3 answer the clerk sent, stored with the case so the
        # approver reads exactly what was previewed (BR-BIL-044), never a
        # fresh computation made after the clerk pressed Send.
        "answer": answer,
    }
    case.preview_hash = preview_hash
    case.save(update_fields=["preview", "preview_hash", "updated_at"])
    audit.money_action(
        actor,
        "correction.case_sent",
        "correction_cases",
        str(case.pk),
        after={
            "class": correction_class,
            "scope_kind": kind,
            "bills": len(pinned),
            "rows": [one.as_dict() for one in items],
            "excluded": [
                {"invoice_no": one.get("invoice_no"), "code": one.get("code")} for one in excluded
            ],
            "preview_hash": preview_hash,
            "case_no": case_no,
            **({"numbering_gap": numbering_gap} if numbering_gap else {}),
            "money_written": "none — nothing money-bearing exists before approval",
        },
    )
    return case


def items_of(case: CorrectionCase) -> tuple[Item, ...]:
    """The rows a case was SENT with, as stored (B3)."""
    return tuple(
        Item(
            position=row.position,
            reason=row.reason,
            correction_class=row.correction_class,
            item=row.item,
            act=row.act,
            value=row.value,
            value2=row.value2,
            bill_ids=None if row.bill_ids is None else tuple(str(one) for one in row.bill_ids),
        )
        for row in CorrectionCaseItem.objects.filter(tenant_id=case.tenant_id, case=case).order_by(
            "position"
        )
    )


# ═══════════════════════════════════════════════════════════════════════════
# APPROVE AND ISSUE — one bill, one transaction, no batch rollback
# ═══════════════════════════════════════════════════════════════════════════
def execute_bill(
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
    """ONE bill of an approved item case. All of it, or none of it (BR-BIL-047).

    `data` (DEF-BIL-10091) is the billing data the approval's check
    (`figures_moved`) gathered for this bill moments earlier, so the bill is
    not gathered a second time; it is used only for a bill with no typed
    reading (a typed reading is SAVED first and the bill re-gathered from what
    Meter Reads then holds). The issued total is still checked against the
    approved one.

    Called by `bulk_corrections._execute_one` for a case sent with rows, inside
    the case loop that records a failure against the bill and carries on —
    **no batch rollback** (`bulk_corrections.explain_no_batch_rollback`).

    * **re-price** (R): the typed readings are SAVED to Meter Reads first
      (`metering_seam.save_corrected_reading` — BR-MET-053's billed door), the
      bill is re-priced from what is now held, the total is checked against
      the APPROVED figure (a drift fails this bill, nothing written), then the
      existing restatement runs on that data: credit note + reversal, the
      release of the old payments, the goodwill credit, the new bill
      (`corrects_invoice_id`), its issue entry, its delivery rows. Reprint rows
      are then reissued on the NEW bill's page.
    * **credit only** (C): the signed concession (`execute_credit_only`).
    * **reprint only** (D): a reissued document instance, and a delivery copy
      queued (J-FIX-TWENTY S8: *"the reissued document is queued"*).
    """
    invoice = models.Invoice.objects.get(tenant_id=case.tenant_id, pk=row.invoice_id)
    mine = tuple(one for one in items_of(case) if one.applies_to(invoice.pk))
    klass = str((row.impact or {}).get("class") or case.correction_class)
    reasons = _reasons(mine) or tuple(case.reason_codes)
    try:
        with transaction.atomic():
            pins = pins_for(invoice, mine)
            if klass == CLASS_RESTATEMENT:
                return _execute_restatement(
                    invoice,
                    row,
                    case=case,
                    pins=pins,
                    reasons=reasons,
                    issued_at=issued_at,
                    on_date=on_date,
                    template_id=template_id,
                    template_version=template_version,
                    actor=actor,
                    data=data,
                )
            if klass == CLASS_CREDIT_ONLY:
                impact = corrections.build_impact(
                    invoice,
                    reason_codes=reasons,
                    correction_class=klass,
                    goodwill_amount=pins.goodwill,
                )
                note = corrections.execute_credit_only(
                    invoice,
                    impact=impact,
                    amount=pins.goodwill,
                    reason="goodwill",
                    issued_at=issued_at,
                    actor=actor,
                )
                return corrections.ExecutedBill(
                    invoice_id=str(invoice.pk), credit_note_id=str(note.pk)
                )
            return _reissue(
                invoice, case=case, pins=pins, reasons=reasons, on_date=on_date, actor=actor
            )
    except BillingRuleError as failure:
        _audit_failure(actor, case, invoice, str(failure))
        raise
    except Exception as failure:  # noqa: BLE001 — every failure is ONE bill's, by rule
        # A refusal in another module's vocabulary (metering's BizError, a
        # payments refusal) must still be this BILL's failure and not the
        # batch's: the loop above catches `BillingRuleError` only.
        _audit_failure(actor, case, invoice, str(failure))
        raise BillingRuleError(
            f"bill {invoice.invoice_no} could not be corrected: {failure}", br_ref="BR-BIL-047"
        ) from failure


def _audit_failure(actor: Any, case: CorrectionCase, invoice: models.Invoice, reason: str) -> None:
    audit.money_action(
        actor,
        "correction.bill_failed",
        "invoices",
        str(invoice.pk),
        after={
            "case_id": str(case.pk),
            "invoice_no": invoice.invoice_no,
            "reason": reason,
            "artifacts": "none — one bill is one transaction",
        },
    )


def _execute_restatement(
    invoice: models.Invoice,
    row: CorrectionCaseBill,
    *,
    case: CorrectionCase,
    pins: Pins,
    reasons: tuple[str, ...],
    issued_at: datetime,
    on_date: date,
    template_id: Any,
    template_version: int | None,
    actor: Any,
    data: Any = None,
) -> corrections.ExecutedBill:
    if template_id is None or template_version is None:
        raise BillingRuleError(
            "a corrected bill is issued with a template version pinned (BR-BIL-026) and none "
            "was supplied.",
            br_ref="BR-BIL-026",
        )
    # DEF-BIL-10080 — Meter Reads prints this reason, so it names the BILL a
    # clerk can look up, never the case's database id (B14 rule 31). A case
    # has no number yet; an issued bill always has one.
    label = case.case_no or invoice.invoice_no or ""
    for asset_id, value in pins.readings.items():
        metering_seam.save_corrected_reading(
            invoice,
            asset_id=asset_id,
            value=value,
            reason=f"Fix a bill — {label}".rstrip(" —"),
            actor=actor,
        )
    if data is None or pins.readings:
        data = prepare_bill(invoice, pins, keyed=False)
    rated = price(data)
    approved = Decimal(str((row.impact or {}).get("corrected_total", "0")))
    if money.finalize(rated.total) != money.finalize(approved):
        raise _refuse(
            KEY_FIGURES_MOVED,
            f"bill {invoice.invoice_no} now prices {money.finalize(rated.total)}, "
            f"not the approved {money.finalize(approved)}",
            br_ref="BR-BIL-044",
        )
    impact = corrections.build_impact(
        invoice,
        reason_codes=reasons,
        correction_class=CLASS_RESTATEMENT,
        corrected=rated,
        posting_period=case.posting_period,
    )
    executed = corrections.execute_restatement(
        invoice,
        impact=impact,
        reason=", ".join(reasons),
        issued_at=issued_at,
        on_date=on_date,
        template_id=template_id,
        template_version=template_version,
        actor=actor,
        rebill_data=data,
        goodwill_amount=pins.goodwill if pins.goodwill > ZERO else None,
        goodwill_reason="goodwill",
    )
    if pins.page:
        rebill = models.Invoice.objects.get(
            tenant_id=invoice.tenant_id, pk=executed.rebill_invoice_id
        )
        reissued = _reissue(
            rebill, case=case, pins=pins, reasons=reasons, on_date=on_date, actor=actor
        )
        executed = replace(executed, document_instance_id=reissued.document_instance_id)
    return executed


def _reissue(
    invoice: models.Invoice,
    *,
    case: CorrectionCase,
    pins: Pins,
    reasons: tuple[str, ...],
    on_date: date,
    actor: Any,
) -> corrections.ExecutedBill:
    """The page rows, reissued on `invoice` (the original for a reprint-only
    case, the NEW bill for a re-priced one — B6, `DEF-BIL-5355`), and a delivery
    copy queued. Moves $0.00 (BR-BIL-041/043)."""
    from apps.billing import document_correction

    page_reasons = tuple(r for r in reasons if r in REPRINT_FIELDS) or reasons
    impact = corrections.build_impact(
        invoice, reason_codes=page_reasons, correction_class=CLASS_DOCUMENT
    )
    executed = document_correction.execute_document_correction(
        invoice,
        impact=impact,
        case=case,
        corrected_payload=dict(pins.page),
        on_date=on_date,
        actor=actor,
    )
    instance = InvoiceDocumentInstance.objects.get(
        tenant_id=invoice.tenant_id, pk=executed.document_instance_id
    )
    problems = list(executed.problems)
    try:
        with transaction.atomic():
            delivery_seam.queue_bill_delivery(invoice, copy_no=instance.instance_no, actor=actor)
    except BillingRuleError as refusal:
        problems.append({"code": "reissue_not_queued", "detail": str(refusal)})
    return replace(executed, problems=tuple(problems))


#: DEF-BIL-10091 — how many bills' gathered data the approval's check keeps
#: for the issue that follows it. Beyond this the issue gathers the bill again
#: (the behaviour before), so memory stays bounded at any run size (NFR-5: a
#: bound on what is KEPT, never on how many bills a case may hold).
PREPARED_KEEP = 2_000


@dataclass
class FiguresCheck:
    """What `figures_moved` found: the bills whose total moved (or that can no
    longer be priced), and the data it gathered for the ones that did not."""

    moved: list[dict[str, Any]]
    prepared: dict[str, Any]


def figures_moved(case: CorrectionCase, *, on_bill: Any = None) -> FiguresCheck:
    """BR-BIL-044 — does every re-priced bill still price at the figure SENT?
    **Writes nothing.** Typed readings are priced, not saved.

    `DEF-BIL-10099` made a one-customer approval refuse when a figure moved
    after Send; decision log 2026-10-13 Q5 extends it to bulk, *"exactly as
    for one customer"*. Bulk used to skip it because pricing a whole run twice
    in one request was `DEF-BIL-10091`'s cost; in the background job it is
    priced ONCE here, under the read memo, and the data is handed to the issue
    (`PREPARED_KEEP`) so the run is not gathered a second time.
    """
    items = items_of(case)
    rows = list(
        CorrectionCaseBill.objects.filter(tenant_id=case.tenant_id, case=case).order_by(
            "created_at", "id"
        )
    )
    invoices = {
        str(one.pk): one
        for one in models.Invoice.objects.filter(
            tenant_id=case.tenant_id, pk__in=[row.invoice_id for row in rows]
        )
    }
    moved: list[dict[str, Any]] = []
    prepared: dict[str, Any] = {}
    with _read_memo(len(rows)) as memo:
        for done, row in enumerate(rows, start=1):
            memo.step()
            impact = row.impact or {}
            invoice = invoices[str(row.invoice_id)]
            if str(
                impact.get("class") or case.correction_class
            ) == CLASS_RESTATEMENT and row.status not in (BILL_DONE, BILL_ABANDONED):
                mine = tuple(one for one in items if one.applies_to(invoice.pk))
                approved = money.finalize(Decimal(str(impact.get("corrected_total", "0"))))
                try:
                    with transaction.atomic():
                        pins = pins_for(invoice, mine)
                        data = prepare_bill(invoice, pins, keyed=True)
                        total = money.finalize(price(data).total)
                except BillingRuleError as refusal:
                    moved.append(
                        {
                            "invoice_id": str(invoice.pk),
                            "invoice_no": invoice.invoice_no,
                            "sent": str(approved),
                            "now": None,
                            "detail": str(refusal),
                        }
                    )
                else:
                    if total != approved:
                        moved.append(
                            {
                                "invoice_id": str(invoice.pk),
                                "invoice_no": invoice.invoice_no,
                                "sent": str(approved),
                                "now": str(total),
                            }
                        )
                    elif not pins.readings and len(prepared) < PREPARED_KEEP:
                        prepared[str(invoice.pk)] = data
            if on_bill is not None:
                on_bill(done, len(rows))
    return FiguresCheck(moved=moved, prepared=prepared)


def refuse_if_moved(check: FiguresCheck) -> None:
    """*Figures changed. Check again.* — before the approval is recorded."""
    if not check.moved:
        return
    first = check.moved[0]
    more = len(check.moved) - 1
    raise _refuse(
        KEY_FIGURES_MOVED,
        f"bill {first['invoice_no']} now prices {first['now'] or 'nothing'}, not the sent "
        f"{first['sent']}" + (f" (and {more} more)" if more else ""),
        br_ref="BR-BIL-044",
    )


def approve_and_issue(
    case: CorrectionCase,
    *,
    approver: Any,
    preview_hash: str,
    on_date: date,
    issued_at: datetime,
    template_id: Any,
    template_version: int | None,
    on_check: Any = None,
    on_issue: Any = None,
) -> bulk_corrections.ExecutionResult:
    """`POST /corrections/{id}/approve-and-issue` — the gate, then the job.

    The approval binds the hash the approver's screen was drawn from (a
    mismatch refuses with `figuresMoved` before anything moves), and every
    re-priced bill must still price at the figure sent (`figures_moved` —
    one customer and bulk alike, decision log 2026-10-13 Q5). Then the case
    loop runs every bill on its own (BR-BIL-047). A bulk case reaches here
    from the background job (`correction_jobs`), never from a request.

    A case ALREADY approved (a re-delivered job, a resumed worker) is not
    approved twice: the loop runs again and skips every bill already done
    (rule 6)."""
    if preview_hash != case.preview_hash:
        raise _refuse(
            KEY_FIGURES_MOVED, "the figures changed since they were checked", br_ref="BR-BIL-044"
        )
    prepared: dict[str, Any] = {}
    if case.status == CASE_PENDING_APPROVAL:
        check = figures_moved(case, on_bill=on_check)
        refuse_if_moved(check)
        prepared = check.prepared
        case = bulk_corrections.approve(
            case, approver=approver, on_date=on_date, preview_hash=preview_hash
        )
    return bulk_corrections.execute(
        case,
        issued_at=issued_at,
        on_date=on_date,
        template_id=template_id,
        template_version=template_version,
        actor=approver,
        prepared=prepared,
        on_bill=on_issue,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-180-BRC10@2026-10-12 (the CR file's server/screen contract · the
#         decision-log rows of 2026-10-12 *FIX A BILL REVAMP* items 1–12 ·
#         J-FIX-TWENTY · BR-BIL-004/011/014/018/041..048 · BR-PAY-010/031)
# generated: 2026-10-12 by the CR-180 SERVER lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(the SCREEN lane builds F1–F10) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: tests/test_cr180_fix_a_bill_revamp.py written first, all RED on the
#         untouched code, then green on sqlite and PostgreSQL 16
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
