# ── Trace ──────────────────────────────────────────────
# Change:   CR-179-BRC10 — the Rate Impact report (Billing · Readiness): proposed
#           flat rates against billed revenue, by rate schedule or charge code,
#           capacity and class. Screens: the standard report viewer (no page,
#           no route and no `api._VIEWERS` entry of its own — CR-179 §5).
# Drawing:  05-prototype/rate-impact-2026-10-12/ (read as images, B14 rule 42)
# Contract: the server/screen lane contract of 2026-10-12 (scratchpad
#           `rate-impact-contract.md`); every deviation is in this docstring.
# Rules:    CR-179 §1 input · §2 process · §3 output · §4 the five confirmed
#           rules (PO 2026-10-12, *"this is also correct"*) · CLAUDE.md hard
#           rule 1 (every read tenant-scoped, by the owner) · hard rule 2 (money
#           to 4 places, never a float; a unit price shows up to 4) · hard rule
#           3 (a quantity always carries its unit — kgal and kWh never added) ·
#           BR-REP-001 (the report states its date basis) · B14 rule 31 (no id
#           is a visible value)
# Tests:    06-backend/tests/test_cr179_rate_impact.py
# Impacts:  apps/reports/runner.py (`MODULE_INPUTS` passes `runner.bind`) ·
#           apps/reports/report_seams.py (every cross-module read) ·
#           apps/reports/exports.py (`RATE_IMPACT`) ·
#           apps/reports/migrations/0010_cr179_rate_impact.py (the card)
# ───────────────────────────────────────────────────────
"""RATE IMPACT — WHAT A PROPOSED FLAT RATE WOULD HAVE BILLED, AGAINST WHAT WAS.

WHAT IT IS, IN THE PO'S WORDS (CR-179 §0)
─────────────────────────────────────────
*"run a proposed rate change against the prior year's consumption to show
revenue by customer class and the bill impact … before Board or Council
adoption"* — and, deciding the method: *"we can take compption and multipl it
by rate diretcly - dot use pricing engine"*, *"we dont want to calculate bill"*.

So this module is a VIEWER over five owners' published reads, and the only
arithmetic it does is the flat arithmetic the PO dictated. **It calls no
pricing engine and builds no bill.** **It writes nothing**: the proposed
figures travel in the run's own parameters and are never written to Plans &
Rates (CR-179 §1 row 12).

THE INPUT (`controls.inputs`, the framework's generic declared inputs)
──────────────────────────────────────────────────────────────────────
Four parameters, every one a STRING so the URL, an export's filters and the
run history carry them unchanged: `services` and `classes` (comma lists),
`months` (`1 2 3 6 9 12`, default 12) and `rows` — ONE JSON string, an array of
`{type, item, version, capacity, base, price, min}`. `MODULE_INPUTS` below is
the static declaration `runner.bind` reads, so these four reach this viewer and
nothing else does; `controls.inputs` is the same four, drawn.

THE PROCESS (CR-179 §2), STEP BY STEP
─────────────────────────────────────
1–2. The accounts on each chosen schedule / carrying each charge code: the
     units whose plan carried it in the window (`rating.units_on_items`), then
     the accounts open in the period on those units
     (`customers.accounts_on_units_in_window`).
3.   Class: the account's own `account_type`; `classes` narrows it.
4.   Capacity: a METERED account's size is today's meter size
     (`metering.connection_sizes_for_units`); a COUNTED account's (trash,
     fire) is its items of each size on file today
     (`metering.billable_size_groups_for_units`).
5.   Revenue now: billing's issued lines, corrections included, each in the
     month its period ENDS (`billing.rate_impact_billed`).
6.   Usage: the stored monthly usage the bill prints
     (`metering.monthly_usage_by_account`).
7.   Revenue proposed — the PO's flat arithmetic, at the typed figures:
       metered  Σ over the account's usage months of
                max(base + usage × price, minimum)      (no minimum: no floor)
       counted  items × price per item × months
       charge   amount × months
     where *months* for a counted item or a charge is the number of months of
     the period the account was open in (a part month counts whole), and for a
     metered item the months that HAVE usage — an unread month is absent,
     never zero (BR-MET-106), so it is not priced either.
8.   Not worked out, by reason (`unavailable`).

THE FIVE CONFIRMED RULES (CR-179 §4), AND WHERE EACH IS ENFORCED
────────────────────────────────────────────────────────────────
1. A bill crossing the start of the period counts in the month its period
   ENDS — `billing.rate_impact_billed` windows on the line's `period_end`.
2. Usage with no bill is NOT worked out — the bill check runs first, so such
   an account is `no_bills_in_period` whatever its usage.
3. An older version changes only the NOW figures — the version picks the
   capacities and their now figures; revenue now is the schedule's billed
   revenue whichever version priced it.
4. Today's size is used for every month — sizes are read ONCE, on the
   utility's today, and the payload carries the `size_today_used` note.
5. Item counts are the items on file — read from assets through metering; the
   `rows` input has no count field and a count in it would be ignored.

WHICH ACCOUNTS ARE IN A GROUP
─────────────────────────────
An account is in a (schedule or charge code, version) group when EVERY
capacity it holds has a row typed for that group. The clerk chooses which
capacities to model, so an account at a size nobody typed is out of scope —
not "not worked out". A counted account holding two sizes (a 6" and a 2" fire
line) is ONE line whose capacity names both, priced at each size's own figure;
its billed revenue cannot be split by size (billing prints one line per
service since `DEF-BIL-8151`), so it is never split.

DEVIATIONS FROM THE SCREEN CONTRACT — read these before wiring a screen
──────────────────────────────────────────────────────────────────────
* **A FIFTH not-worked-out reason, `usage_unit_differs`.** Hard rule 3: an
  account whose stored months disagree about the unit, or whose unit is not
  the version's billed unit, cannot be multiplied by a price per unit without
  assuming a conversion. It is counted beside the contract's four.
* **`unavailable` lists only reasons with a non-zero count**, each as
  `{code, count, message_key, field: "rows"}`; the today's-size note is ALSO
  an entry there, `{code: "size_today_used", message_key}` with no count (the
  screen lane's reading), besides `notes`.
* **`item_noun` is pluralised by the English `-s` rule** over the schedule's
  billed unit (`connection` → `connections`), because the screen prints it as
  served. The billed-unit vocabulary has no plural form of its own.
* **A counted item's `now.base` is the price PER ITEM** — the schedule's flat
  price for the size PLUS its named base code's price for the size, because a
  bill charges both per item (`gather._per_size_configs`, PO 2026-09-30
  option B: *"2 × ($15.00 + $3.00) = $36.00"*).
* **The schedule's now `base` comes from the version's NAMED base charge code,
  and is `0` where it names none** (`DEF-RAT-9832`), not from
  `tariff_versions.base_charge`, which no bill charges any more.
* **Extra keys, all additive:** each group row also carries `item_label`,
  `type`, `service`, `service_label`, `version_label`, `effective_from`,
  `capacities` and `not_worked_out`; each fact row carries `item_label`; the
  payload carries `proposed_used` (*Proposed figures used*) and `notes`.
* **`services` empty means every enabled service**, so the item list is not
  empty on first open.
* **A metered row with no `price`, or a counted/charge row with no `base`, is
  refused** — a proposed revenue with no proposed price is not a figure.
  A metered row's empty `base` is `0` and an empty `min` is *no floor*.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from core import errors

from apps.reports import queries
from apps.reports import report_seams as seams

KEY = "rate_impact"

#: The four run parameters this viewer declares — `runner.bind` passes exactly
#: these through (see `runner.declared_inputs`). Every value is a STRING.
PARAM_SERVICES = "services"
PARAM_CLASSES = "classes"
PARAM_MONTHS = "months"
PARAM_ROWS = "rows"
INPUT_PARAMS: tuple[str, ...] = (PARAM_SERVICES, PARAM_CLASSES, PARAM_MONTHS, PARAM_ROWS)

#: CR-179 §1 row 3, PO verbatim: *"1 month, 3 months, 6 months and 9 months an
#: 12 mnoths options"* · *"also give me option for 2 months"*.
MONTH_CHOICES: tuple[int, ...] = (1, 2, 3, 6, 9, 12)
DEFAULT_MONTHS = 12

#: CR-179 §1 row 4 — *"Change all prices by −10% … +20%"*, applied on the
#: screen to the proposed boxes. Declared here so the list has one home.
PERCENT_SHORTCUTS: tuple[str, ...] = ("-10", "-5", "2", "3", "5", "8", "10", "15", "20")

TYPE_RATE = "rate"
TYPE_CHARGE = "charge"
KIND_METERED = "metered"
KIND_CAPACITY = "capacity"
KIND_CHARGE = "charge"

#: The columns of one line, in the drawn order.
#: ⚠ `unit` and `item_noun` are FIELDS on every line and NOT columns — the
#: screen prints them beside `usage` and `items` through `column_meta`'s
#: `unit_from` (the screen lane's reading, 2026-10-12).
COLUMNS: tuple[str, ...] = (
    "capacity",
    "class",
    "accounts",
    "usage",
    "items",
    "revenue_now",
    "revenue_proposed",
    "change",
    "change_pct",
)
MONEY_COLUMNS: tuple[str, ...] = ("revenue_now", "revenue_proposed", "change")

#: Not worked out, by reason (CR-179 §2 step 8). The order is the order a
#: clerk fixes them in.
NO_BILLS = "no_bills_in_period"
NO_USAGE = "no_usage_in_period"
NO_CAPACITY = "no_capacity_on_file"
NO_PLAN = "no_plan_on_unit"
UNIT_DIFFERS = "usage_unit_differs"
REASONS: tuple[str, ...] = (NO_BILLS, NO_USAGE, NO_CAPACITY, NO_PLAN, UNIT_DIFFERS)
REASON_KEYS: dict[str, str] = {
    NO_BILLS: "reports.rateImpact.notWorkedOut.noBills",
    NO_USAGE: "reports.rateImpact.notWorkedOut.noUsage",
    NO_CAPACITY: "reports.rateImpact.notWorkedOut.noCapacity",
    NO_PLAN: "reports.rateImpact.notWorkedOut.noPlan",
    UNIT_DIFFERS: "reports.rateImpact.notWorkedOut.unitDiffers",
}
NOTE_SIZE_TODAY = "size_today_used"
NOTE_SIZE_TODAY_KEY = "reports.rateImpact.note.sizeToday"
DRILL_UNAVAILABLE = "rate_impact_no_drill"

#: The basis BR-REP-001 makes every money report state: a billed line counts
#: in the month its SERVICE PERIOD ends (confirmed rule 1), which is an event
#: date and neither a posting nor a clearing date.
BASIS = "event"

FOUR_PLACES = Decimal("0.0001")
SIX_PLACES = Decimal("0.000001")
HUNDRED = Decimal("100")
ZERO = Decimal("0")


# ── refusals ─────────────────────────────────────────────────────────────────
def _refuse(message_key: str, **params: Any) -> errors.ValidationError:
    """One input refusal, naming the field it is about (`rows` unless said)."""
    field = params.pop("field", PARAM_ROWS)
    code = params.pop("code", errors.VAL_FORMAT)
    return errors.ValidationError(
        code,
        message_key=message_key,
        params=params,
        field_errors=[{"field": field, "code": code}],
    )


# ── small helpers ────────────────────────────────────────────────────────────
def _money(value: Decimal | None) -> str | None:
    """Money at its STORED precision — 4 places (hard rule 2). Display is the
    screen's: 2 for an amount, up to 4 for a unit price."""
    if value is None:
        return None
    return f"{value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP):f}"


def _pct(change: Decimal, now: Decimal) -> str | None:
    """A percentage at 6 places (hard rule 2), or None over a zero base — a
    change over nothing is undefined, never 0.0% (BR-REP-024)."""
    if now == ZERO:
        return None
    return f"{(change / now * HUNDRED).quantize(SIX_PLACES, rounding=ROUND_HALF_UP):f}"


def _quantity(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f") if value == value.to_integral() else f"{value:f}"


def _iso(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        parts = [str(one) for one in raw]
    else:
        parts = str(raw).split(",")
    return [part.strip() for part in parts if part and part.strip()]


def _get(params: Any, name: str) -> Any:
    getter = getattr(params, "get", None)
    if getter is None:
        return None
    value = getter(name)
    if value is None:
        value = getter(f"f.{name}")
    return value


def _first_of_month(day: date) -> date:
    return day.replace(day=1)


def _add_months(first: date, months: int) -> date:
    index = first.year * 12 + (first.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def _month_end(first: date) -> date:
    return _add_months(first, 1) - timedelta(days=1)


def window_for(today: date, months: int) -> tuple[date, date, list[date]]:
    """`(start, end, [first of each month])` — `months` whole months ending
    LAST month on the utility's own calendar (CR-179 §1 row 3)."""
    last = _add_months(_first_of_month(today), -1)
    first = _add_months(last, -(months - 1))
    return first, _month_end(last), [_add_months(first, step) for step in range(months)]


def _open_months(account: dict[str, Any], months: list[date]) -> int:
    """How many of the period's months this account was open in — a part
    month counts whole, the same reading `accounts_on_units_in_window` makes
    of *open in the period*."""
    opened = account.get("opened_at")
    closed = account.get("closed_at")
    count = 0
    for first in months:
        last = _month_end(first)
        if opened is not None and opened > last:
            continue
        if closed is not None and closed < first:
            continue
        count += 1
    return count


def _decimal(raw: Any, *, label: str) -> Decimal | None:
    """A typed figure: a decimal string, number or null. Never a float in
    arithmetic (hard rule 2) — a JSON number is read through its text."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, bool):
        raise _refuse("reports.rateImpact.refusal.badFigure", figure=label)
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        raise _refuse("reports.rateImpact.refusal.badFigure", figure=label) from None
    if not value.is_finite() or value < ZERO:
        raise _refuse("reports.rateImpact.refusal.badFigure", figure=label)
    return value


# ── the input half ───────────────────────────────────────────────────────────
def _services(params: Any) -> tuple[list[dict[str, Any]], list[str]]:
    overview = seams.services_overview()
    if overview is None:  # pragma: no cover — tenancy publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.rateImpact.unavailable")
    enabled = [
        {"value": row.get("service"), "label": row.get("name") or row.get("service")}
        for row in overview
        if row.get("enabled")
    ]
    codes = [row["value"] for row in enabled]
    asked = [code for code in _list(_get(params, PARAM_SERVICES)) if code in codes]
    return enabled, asked or codes


def _months(params: Any) -> int:
    raw = _get(params, PARAM_MONTHS)
    if raw is None or str(raw).strip() == "":
        return DEFAULT_MONTHS
    try:
        value = int(str(raw).strip())
    except ValueError:
        value = 0
    if value not in MONTH_CHOICES:
        raise _refuse(
            "reports.rateImpact.refusal.badMonths",
            field=PARAM_MONTHS,
            code=errors.VAL_RANGE,
            allowed=list(MONTH_CHOICES),
        )
    return value


def _choices(service_codes: list[str], service_labels: dict[str, str]) -> dict[str, Any]:
    """`items`, `versions` and `capacities` for the chosen services — the
    dependent dropdowns of the table input. Labels only on screen (rule 31)."""
    items = seams.rate_impact_items(service_codes)
    if items is None:  # pragma: no cover — rating publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.rateImpact.unavailable")
    counted = {code: bool(seams.bills_one_line_per_size(code)) for code in service_codes}
    item_rows: list[dict[str, Any]] = []
    for item in items:
        service = item.get("service_code")
        if item["type"] == TYPE_CHARGE:
            kind = KIND_CHARGE
        elif counted.get(service):
            kind = KIND_CAPACITY
        else:
            kind = KIND_METERED
        item_rows.append(
            {
                "value": item["id"],
                "label": item["name"],
                "type": item["type"],
                "service": service,
                "service_label": service_labels.get(service or "", service),
                "item_kind": kind,
                "unit": item.get("unit") if kind == KIND_METERED else None,
                # A counted item's noun is its schedule's billed unit — `cart`,
                # `connection` — the word the bill prints beside the count.
                "item_noun": item.get("unit") if kind == KIND_CAPACITY else None,
            }
        )
    tariff_ids = [row["value"] for row in item_rows if row["type"] == TYPE_RATE]
    charge_ids = [row["value"] for row in item_rows if row["type"] == TYPE_CHARGE]
    versions = seams.rate_impact_versions(tariff_ids, charge_ids) or []
    by_item = {row["value"]: row for row in item_rows}
    version_rows = [
        {
            "value": row["id"],
            "label": row.get("label") or _iso(row["effective_from"]),
            "item": row["item"],
            "effective_from": _iso(row["effective_from"]),
            "effective_to": _iso(row.get("effective_to")),
            "in_force": bool(row.get("in_force")),
        }
        for row in versions
    ]
    refs = [(by_item[row["item"]]["type"], row["item"], row["id"]) for row in versions]
    capacities = seams.rate_impact_capacities(refs) or {}
    capacity_rows: list[dict[str, Any]] = []
    for row in versions:
        item = by_item[row["item"]]
        for size in capacities.get(row["id"], ()):
            capacity_rows.append(
                {
                    "value": size["value"],
                    "label": size["label"],
                    "version": row["id"],
                    "now": _now_figures(item["item_kind"], size["now"]),
                }
            )
    return {"items": item_rows, "versions": version_rows, "capacities": capacity_rows}


def _now_figures(kind: str, now: dict[str, Any]) -> dict[str, Any]:
    """The figures on file, in the contract's three boxes.

    A counted item's one box is the price PER ITEM — its flat price for the
    size plus its base for the size, both of which a bill charges per item.
    A tiered or non-flat price is None (*Billed*), and so is a per-item price
    built on one.
    """
    base, price, minimum = now.get("base"), now.get("price"), now.get("min")
    if kind == KIND_CAPACITY:
        per_item = None if price is None else price + (base or ZERO)
        return {"base": _money(per_item), "price": None, "min": None}
    if kind == KIND_CHARGE:
        return {"base": _money(base), "price": None, "min": None}
    return {"base": _money(base), "price": _money(price), "min": _money(minimum)}


def _inputs(
    services: list[dict[str, Any]], classes: list[dict[str, Any]], choices: dict[str, Any]
) -> list[dict[str, Any]]:
    """`controls.inputs` — the four declared parameters, drawn by the standard
    viewer. ONE declaration per parameter in `INPUT_PARAMS`, in that order."""
    return [
        {
            "param": PARAM_SERVICES,
            "kind": "multi",
            "label_key": "reports.rateImpact.input.services",
            "options": services,
        },
        {
            "param": PARAM_CLASSES,
            "kind": "multi",
            "label_key": "reports.rateImpact.input.classes",
            "options": classes,
            "all_label_key": "reports.input.allClasses",
        },
        {
            "param": PARAM_MONTHS,
            "kind": "select",
            "label_key": "reports.rateImpact.input.months",
            "default": str(DEFAULT_MONTHS),
            "options": [
                {
                    "value": str(count),
                    "label_key": "reports.input.months_one"
                    if count == 1
                    else "reports.input.months_other",
                    "params": {"count": count},
                }
                for count in MONTH_CHOICES
            ],
        },
        {
            "param": PARAM_ROWS,
            "kind": "table",
            "label_key": "reports.rateImpact.input.rows",
            "add_label_key": "reports.rateImpact.input.addRow",
            "columns": [
                {
                    "name": "type",
                    "kind": "select",
                    "options": [
                        {"value": TYPE_RATE, "label_key": "reports.rateImpact.input.type.rate"},
                        {"value": TYPE_CHARGE, "label_key": "reports.rateImpact.input.type.charge"},
                    ],
                },
                {"name": "item", "kind": "select", "choices": "items", "depends_on": "type"},
                {"name": "version", "kind": "select", "choices": "versions", "depends_on": "item"},
                {"name": "effective_from", "kind": "display", "from": "versions"},
                {"name": "service", "kind": "display", "from": "items"},
                {
                    "name": "capacity",
                    "kind": "select",
                    "choices": "capacities",
                    "depends_on": "version",
                },
                {"name": "base", "kind": "money", "now_from": "capacities"},
                {
                    "name": "price",
                    "kind": "unit_price",
                    "now_from": "capacities",
                    "hidden_for_item_kinds": [KIND_CAPACITY, KIND_CHARGE],
                },
                {
                    "name": "min",
                    "kind": "money",
                    "now_from": "capacities",
                    "hidden_for_item_kinds": [KIND_CAPACITY, KIND_CHARGE],
                },
            ],
            "choices": choices,
            "shortcuts": [
                {
                    "kind": "percent",
                    "label_key": "reports.rateImpact.input.changeAll",
                    "options": list(PERCENT_SHORTCUTS),
                }
            ],
        },
    ]


def _parse_rows(raw: Any, choices: dict[str, Any]) -> list[dict[str, Any]]:
    """The `rows` JSON string, every value checked against the CHOICES this
    run offered — so an item of another utility, a draft version or a size the
    version does not use is refused by name and never reaches a read."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return []
    try:
        decoded = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        raise _refuse("reports.rateImpact.refusal.badRows") from None
    if not isinstance(decoded, list):
        raise _refuse("reports.rateImpact.refusal.badRows")
    items = {row["value"]: row for row in choices["items"]}
    versions = {row["value"]: row for row in choices["versions"]}
    capacities: dict[str, dict[str, dict[str, Any]]] = {}
    for row in choices["capacities"]:
        capacities.setdefault(row["version"], {})[row["value"]] = row
    parsed: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    # (item, capacity) -> the version it is modelled on. See the refusal below.
    capacity_version: dict[tuple[str, str], str] = {}
    for index, entry in enumerate(decoded, start=1):
        if not isinstance(entry, dict):
            raise _refuse("reports.rateImpact.refusal.badRows")
        kind = str(entry.get("type") or "")
        item = items.get(str(entry.get("item") or ""))
        if kind not in (TYPE_RATE, TYPE_CHARGE) or item is None or item["type"] != kind:
            raise _refuse("reports.rateImpact.refusal.unknownItem", row=index)
        version = versions.get(str(entry.get("version") or ""))
        if version is None or version["item"] != item["value"]:
            raise _refuse("reports.rateImpact.refusal.unknownVersion", row=index)
        capacity = str(entry.get("capacity") or "")
        size = capacities.get(version["value"], {}).get(capacity)
        if size is None:
            raise _refuse("reports.rateImpact.refusal.unknownCapacity", row=index)
        key = (item["value"], version["value"], capacity)
        if key in seen:
            raise _refuse("reports.rateImpact.refusal.duplicateRow", row=index)
        seen.add(key)
        # ⚠ **MONEY: ONE CAPACITY OF ONE ITEM IS MODELLED ON ONE VERSION.** The
        # walk of 2026-10-12 put a water schedule's 5/8" on two versions and got
        # two groups holding the same 40 accounts and the same billed $7,991.50,
        # and the grand total added both. Confirmed rule 3 makes revenue now the
        # SCHEDULE's billed revenue whichever version is picked, so a second
        # version of the same capacity is the same accounts' same money again —
        # an alternative, never an addition. Refused here, at the input, so the
        # grand total cannot double count by construction: an account is in a
        # group only when every capacity it holds is typed for that group, so
        # with each capacity on one version it is in at most one group per item.
        # (Decision log 2026-10-12, *ONE CAPACITY, ONE VERSION*.)
        held = capacity_version.setdefault((item["value"], capacity), version["value"])
        if held != version["value"]:
            raise _refuse("reports.rateImpact.refusal.capacityOnTwoVersions", row=index)
        base = _decimal(entry.get("base"), label="base")
        price = _decimal(entry.get("price"), label="price")
        minimum = _decimal(entry.get("min"), label="min")
        if item["item_kind"] == KIND_METERED and price is None:
            raise _refuse("reports.rateImpact.refusal.priceRequired", row=index)
        if item["item_kind"] != KIND_METERED and base is None:
            raise _refuse("reports.rateImpact.refusal.amountRequired", row=index)
        parsed.append(
            {
                "item": item,
                "version": version,
                "capacity": capacity,
                "capacity_label": size["label"],
                "sized": capacity != "",
                "base": base,
                "price": price if item["item_kind"] == KIND_METERED else None,
                "min": minimum if item["item_kind"] == KIND_METERED else None,
            }
        )
    return parsed


# ── the process half ─────────────────────────────────────────────────────────
class _Line:
    """One capacity × class line of one group, accumulating in Decimal."""

    def __init__(self, capacity: str, capacity_label: str | None, class_code: str | None,
                 class_label: str | None) -> None:
        self.capacity = capacity
        self.capacity_label = capacity_label
        self.class_code = class_code
        self.class_label = class_label
        self.accounts: set[str] = set()
        self.usage = ZERO
        self.units: set[str] = set()
        self.items = 0
        self.now = ZERO
        self.proposed = ZERO


def _metered_proposed(row: dict[str, Any], months: list[dict[str, Any]]) -> Decimal:
    """CR-179 §2 step 7, metered: per month `base + usage × price`, at least
    the minimum. No engine, no tiers, no proration — the PO's flat sum."""
    base = row["base"] or ZERO
    total = ZERO
    for month in months:
        figure = base + month["quantity"] * row["price"]
        if row["min"] is not None and figure < row["min"]:
            figure = row["min"]
        total += figure
    return total


def _compute(
    rows: list[dict[str, Any]],
    *,
    classes: list[str],
    start: date,
    end: date,
    months: list[date],
    today: date,
) -> dict[str, Any]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["item"]["value"], row["version"]["value"])
        group = groups.setdefault(
            key, {"item": row["item"], "version": row["version"], "rows": {}}
        )
        group["rows"][row["capacity"]] = row
    if not groups:
        return {"groups": [], "accounts": set(), "not_worked_out": {}, "currencies": set()}

    tariff_ids = sorted({k[0] for k, g in groups.items() if g["item"]["type"] == TYPE_RATE})
    charge_ids = sorted({k[0] for k, g in groups.items() if g["item"]["type"] == TYPE_CHARGE})
    units_by_item = seams.rate_impact_units(tariff_ids, charge_ids, start, end) or {}
    all_units = sorted({unit for units in units_by_item.values() for unit in units})
    accounts = seams.rate_impact_accounts(all_units, start, end) or []
    if classes:
        accounts = [acc for acc in accounts if acc.get("class_code") in classes]
    accounts_by_unit: dict[str, list[dict[str, Any]]] = {}
    for account in accounts:
        accounts_by_unit.setdefault(str(account.get("unit_id")), []).append(account)

    billed: dict[tuple[str, str], Decimal] = {}
    currencies: set[str] = set()
    for line in seams.rate_impact_billed(
        tariff_ids=tariff_ids, charge_ids=charge_ids, start=start, end=end
    ) or []:
        item_id = line["tariff_id"] or line["charge_id"]
        key = (line["account_id"], item_id)
        billed[key] = billed.get(key, ZERO) + line["amount"]
        if line.get("currency"):
            currencies.add(line["currency"])

    # Today's sizes and items, read ONCE per service (confirmed rules 4 and 5).
    sizes_cache: dict[str, dict[str, Any]] = {}
    groups_cache: dict[str, dict[str, Any]] = {}
    usage_cache: dict[str, dict[str, list[dict[str, Any]]]] = {}

    def _sizes(service: str) -> dict[str, Any]:
        if service not in sizes_cache:
            sizes_cache[service] = seams.rate_impact_connection_sizes(all_units, service) or {}
        return sizes_cache[service]

    def _items(service: str) -> dict[str, Any]:
        if service not in groups_cache:
            groups_cache[service] = seams.rate_impact_size_groups(all_units, service, today) or {}
        return groups_cache[service]

    def _usage(service: str) -> dict[str, list[dict[str, Any]]]:
        if service not in usage_cache:
            usage_cache[service] = (
                seams.rate_impact_usage(
                    [acc["id"] for acc in accounts], service, months[0], months[-1]
                )
                or {}
            )
        return usage_cache[service]

    out_groups: list[dict[str, Any]] = []
    everyone: set[str] = set()
    tally: dict[str, int] = {}
    for (item_id, version_id), group in groups.items():
        item, version, typed = group["item"], group["version"], group["rows"]
        service = item.get("service") or ""
        kind = item["item_kind"]
        sized = any(capacity != "" for capacity in typed)
        lines: dict[tuple[str, str | None], _Line] = {}
        reasons: dict[str, set[str]] = {}
        units = units_by_item.get(item_id, [])
        for unit_id in units:
            for account in accounts_by_unit.get(unit_id, ()):
                account_id = account["id"]
                # ── capacity (step 4): what this account holds, today ──────
                holding: dict[str, int] = {}
                if kind == KIND_CAPACITY:
                    groups_now = _items(service).get(unit_id)
                    if groups_now is None or (sized and None in groups_now):
                        reasons.setdefault(NO_CAPACITY, set()).add(account_id)
                        continue
                    if sized:
                        holding = {str(k): int(v) for k, v in groups_now.items() if int(v or 0)}
                    else:
                        holding = {"": sum(int(v or 0) for v in groups_now.values())}
                    if not any(holding.values()):
                        continue
                elif sized:
                    size = _sizes(service).get(unit_id) if service else None
                    if size is None:
                        reasons.setdefault(NO_CAPACITY, set()).add(account_id)
                        continue
                    holding = {str(size): 1}
                else:
                    holding = {"": 1}
                # The clerk models the capacities they typed; an account holding
                # one nobody typed is out of scope, not "not worked out".
                if any(capacity not in typed for capacity in holding):
                    continue
                # ── revenue now (step 5) first: confirmed rule 2 ────────────
                if (account_id, item_id) not in billed:
                    reasons.setdefault(NO_BILLS, set()).add(account_id)
                    continue
                now = billed[(account_id, item_id)]
                usage_total: Decimal | None = None
                usage_unit: str | None = None
                if kind == KIND_METERED:
                    stored = _usage(service).get(account_id, [])
                    if not stored:
                        reasons.setdefault(NO_USAGE, set()).add(account_id)
                        continue
                    units_seen = {month["unit"] for month in stored}
                    wanted_unit = item.get("unit")
                    if len(units_seen) != 1 or (wanted_unit and units_seen != {wanted_unit}):
                        reasons.setdefault(UNIT_DIFFERS, set()).add(account_id)
                        continue
                    (capacity,) = holding
                    proposed = _metered_proposed(typed[capacity], stored)
                    usage_total = sum((month["quantity"] for month in stored), ZERO)
                    usage_unit = units_seen.pop()
                    item_count = 0
                else:
                    open_months = _open_months(account, months)
                    proposed = sum(
                        (
                            Decimal(count) * typed[capacity]["base"] * Decimal(open_months)
                            for capacity, count in holding.items()
                        ),
                        ZERO,
                    ) if kind == KIND_CAPACITY else typed[next(iter(holding))]["base"] * Decimal(
                        open_months
                    )
                    item_count = sum(holding.values()) if kind == KIND_CAPACITY else 0
                capacity_key = "+".join(sorted(holding))
                capacity_label = (
                    " + ".join(
                        typed[capacity]["capacity_label"] or capacity
                        for capacity in sorted(holding)
                    )
                    if capacity_key
                    else None
                )
                line_key = (capacity_key, account.get("class_code"))
                line = lines.get(line_key)
                if line is None:
                    line = lines[line_key] = _Line(
                        capacity_key, capacity_label, account.get("class_code"),
                        account.get("class_name"),
                    )
                line.accounts.add(account_id)
                line.now += now
                line.proposed += proposed
                line.items += item_count
                if usage_total is not None:
                    line.usage += usage_total
                    line.units.add(usage_unit or "")
                everyone.add(account_id)
        for reason, ids in reasons.items():
            tally[reason] = tally.get(reason, 0) + len(ids)
        out_groups.append(
            {
                "item": item,
                "version": version,
                "typed": typed,
                "lines": sorted(
                    lines.values(),
                    key=lambda ln: (ln.capacity_label or "", ln.class_label or ""),
                ),
                "not_worked_out": {reason: len(ids) for reason, ids in reasons.items()},
            }
        )
    return {
        "groups": out_groups,
        "accounts": everyone,
        "not_worked_out": tally,
        "currencies": currencies,
    }


def _fact_row(group: dict[str, Any], line: _Line) -> dict[str, Any]:
    item = group["item"]
    change = line.proposed - line.now
    metered = item["item_kind"] == KIND_METERED
    one_unit = len(line.units) == 1
    return {
        "capacity": line.capacity_label,
        "class": line.class_label or line.class_code,
        "accounts": len(line.accounts),
        "usage": _quantity(line.usage) if metered and one_unit else None,
        "unit": next(iter(line.units)) if metered and one_unit else None,
        "items": line.items if item["item_kind"] == KIND_CAPACITY else None,
        "item_noun": (
            _noun(item.get("item_noun"), line.items)
            if item["item_kind"] == KIND_CAPACITY
            else None
        ),
        "revenue_now": _money(line.now),
        "revenue_proposed": _money(line.proposed),
        "change": _money(change),
        "change_pct": _pct(change, line.now),
        "item_label": item["label"],
    }


def _noun(noun: str | None, count: int) -> str | None:
    """The billed unit as the screen PRINTS it beside a count — `1 cart`,
    `3 carts`. The screen prints it as served (the screen lane, 2026-10-12),
    so the plural is made here, by the English `-s` rule over the stored unit
    word (`cart`, `connection`); a unit word already ending in `s` is kept."""
    if not noun:
        return None
    if count == 1 or noun.endswith("s"):
        return noun
    return f"{noun}s"


def _group_label(item: dict[str, Any], version: dict[str, Any]) -> str:
    """`<item> · <version>, from <date>` — the drawn group head. A schedule
    version with no label of its own is named by its date alone."""
    stated = version.get("label")
    date_text = version.get("effective_from")
    if stated and stated != date_text:
        return f"{item['label']} · {stated}, from {date_text}"
    return f"{item['label']}, from {date_text}"


def _shape(computed: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Decimal], list]:
    rows: list[dict[str, Any]] = []
    grand_now = grand_proposed = ZERO
    proposed_used: list[dict[str, Any]] = []
    for group in computed["groups"]:
        item, version = group["item"], group["version"]
        lines = group["lines"]
        now = sum((ln.now for ln in lines), ZERO)
        proposed = sum((ln.proposed for ln in lines), ZERO)
        accounts = set().union(*(ln.accounts for ln in lines)) if lines else set()
        grand_now += now
        grand_proposed += proposed
        label = _group_label(item, version)
        rows.append(
            {
                "__kind__": "group",
                "level": 0,
                "dimension": "item",
                "value": label,
                "path": [{"dimension": "item", "column": "item", "value": label}],
                "filters": None,
                "drill_unavailable": DRILL_UNAVAILABLE,
                "rows": len(lines),
                "subtotals": {
                    "accounts": len(accounts),
                    "revenue_now": _money(now),
                    "revenue_proposed": _money(proposed),
                    "change": _money(proposed - now),
                    "change_pct": _pct(proposed - now, now),
                },
                "item_label": item["label"],
                "type": item["type"],
                "service": item.get("service"),
                "service_label": item.get("service_label"),
                "version_label": version.get("label"),
                "effective_from": version.get("effective_from"),
                "capacities": [
                    typed["capacity_label"] for typed in group["typed"].values()
                ],
                "not_worked_out": dict(group["not_worked_out"]),
            }
        )
        rows.extend(_fact_row(group, line) for line in lines)
        for typed in group["typed"].values():
            proposed_used.append(
                {
                    "type": item["type"],
                    "item_label": item["label"],
                    "version_label": version.get("label"),
                    "effective_from": version.get("effective_from"),
                    "capacity": typed["capacity_label"],
                    "base": _money(typed["base"]),
                    "price": _money(typed["price"]),
                    "min": _money(typed["min"]),
                }
            )
    return rows, {"now": grand_now, "proposed": grand_proposed}, proposed_used


def rate_impact(params: Any) -> dict[str, Any]:
    """`GET /reports/rate_impact` — the inputs, then (with `rows`) the result.

    With `rows` empty this returns the inputs and an EMPTY result: the screen
    draws the inputs first (contract). Nothing here writes anything.
    """
    today = seams.tenant_today()
    if today is None:  # pragma: no cover — tenancy publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.rateImpact.unavailable")
    services, chosen = _services(params)
    service_labels = {row["value"]: row["label"] for row in services}
    classes_offered = seams.account_type_options() or []
    class_codes = {row["value"] for row in classes_offered}
    classes = [code for code in _list(_get(params, PARAM_CLASSES)) if code in class_codes]
    months_n = _months(params)
    start, end, months = window_for(today, months_n)
    choices = _choices(chosen, service_labels)
    rows = _parse_rows(_get(params, PARAM_ROWS), choices)

    computed = _compute(rows, classes=classes, start=start, end=end, months=months, today=today)
    result_rows, grand, proposed_used = _shape(computed)

    currencies = computed["currencies"]
    regional = seams.regional_settings() or {}
    currency = (
        next(iter(currencies)) if len(currencies) == 1
        else (None if currencies else regional.get("currency"))
    )
    change = grand["proposed"] - grand["now"]
    has_result = bool(rows)
    unavailable = [
        {
            "field": PARAM_ROWS,
            "code": reason,
            "count": computed["not_worked_out"][reason],
            "message_key": REASON_KEYS[reason],
        }
        for reason in REASONS
        if computed["not_worked_out"].get(reason)
    ]
    if has_result:
        # The screen reads the confirmed-rule-4 note as an `unavailable`
        # entry with NO count (the screen lane, 2026-10-12).
        unavailable.append(
            {"field": PARAM_ROWS, "code": NOTE_SIZE_TODAY, "message_key": NOTE_SIZE_TODAY_KEY}
        )
    mixed = "rate_impact_window_holds_more_than_one_currency" if len(currencies) > 1 else None
    payload = queries._report(
        KEY,
        basis=BASIS,
        window={"start": start.isoformat(), "end": end.isoformat(), "months": months_n},
        currency=currency,
        columns=COLUMNS,
        rows=result_rows,
        kpis=[
            queries._kpi(
                "revenue_now", _money(grand["now"]) if has_result and not mixed else None,
                reason_code=None if has_result and not mixed else (mixed or "rate_impact_no_rows"),
            ),
            queries._kpi(
                "revenue_proposed",
                _money(grand["proposed"]) if has_result and not mixed else None,
                reason_code=None if has_result and not mixed else (mixed or "rate_impact_no_rows"),
            ),
            queries._kpi(
                "change", _money(change) if has_result and not mixed else None,
                reason_code=None if has_result and not mixed else (mixed or "rate_impact_no_rows"),
            ),
            queries._kpi(
                "change_pct",
                _pct(change, grand["now"]) if has_result and not mixed else None,
                kind="percent",
                reason_code=(
                    None
                    if has_result and not mixed and grand["now"] != ZERO
                    else (mixed or ("rate_impact_no_rows" if not has_result else "no_revenue_now"))
                ),
            ),
        ],
        totals={
            "accounts": len(computed["accounts"]),
            "revenue_now": _money(grand["now"]),
            "revenue_proposed": _money(grand["proposed"]),
            "change": _money(change),
            "change_pct": _pct(change, grand["now"]),
        },
        unavailable=unavailable,
        grain="rate_impact_line",
        controls={"inputs": _inputs(services, classes_offered, choices)},
        column_meta={
            **{
                name: {"type": "money", "unit": None, "unit_from": None,
                       "money_basis": BASIS, "scale": 4}
                for name in MONEY_COLUMNS
            },
            # The walk of 2026-10-12: the group row's ACCOUNTS cell printed
            # `$47.00`, because a subtotal under an undeclared column is drawn
            # as money. A count of accounts is a count.
            "accounts": {"type": "count", "unit": None, "unit_from": None,
                         "money_basis": None, "scale": None},
            "usage": {"type": "quantity", "unit": None, "unit_from": "unit",
                      "money_basis": None, "scale": 6},
            "items": {"type": "count", "unit": None, "unit_from": "item_noun",
                      "money_basis": None, "scale": None},
            "change_pct": {"type": "percent", "unit": None, "unit_from": None,
                           "money_basis": None, "scale": 6},
        },
        column_choices=COLUMNS,
    )
    payload["proposed_used"] = proposed_used
    payload["notes"] = (
        [{"code": NOTE_SIZE_TODAY, "message_key": NOTE_SIZE_TODAY_KEY}] if has_result else []
    )
    return payload


def export_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The LINES of a served result, for a file — group heads are a screen's
    furniture and every line already names its schedule or charge code."""
    return [
        row for row in payload.get("rows") or ()
        if isinstance(row, dict) and row.get("__kind__") != "group"
    ]


# ── the run history's one line per run (B14 rule 31) ─────────────────────────
#: The figure columns of a row, in the drawn order, with the KIND the screen
#: formats them by — an amount at 2 places, a unit price up to 4 (hard rule 2).
_SUMMARY_FIGURES: tuple[tuple[str, str], ...] = (
    ("base", "money"),
    ("price", "unit_price"),
    ("min", "money"),
)


def describe_run(filters: dict[str, Any], cache: dict[str, Any] | None = None) -> list | None:
    """What a stored run modelled, in WORDS — for History's PARAMETERS cell.

    The walk of 2026-10-12: that cell printed the raw `rows` JSON, schedule and
    version DATABASE IDS and size codes (`W-58`) among it — B14 rule 31. The
    filters stay exactly as stored (*Open in report* replays them); this is a
    second, read-only reading of them through the SAME choices a run offers,
    so every id becomes the label the input table showed.

    Shape — a list of lines, each `{parts: [...], figures?: [...]}`:
      · the first line: services · classes (or *all classes*) · months;
      · one line per modelled row: item · version · capacity, then each typed
        figure as `{label_key, kind, value}` at its STORED precision — the
        screen rounds for display.
    A part is `{text}` (a label already in the tenant's words) or
    `{label_key, params?}` (a catalogue word). No id is ever a part.

    `None` when the stored rows no longer resolve (an item archived since, a
    hand-edited link) — the screen then shows no rows rather than an id.
    `cache` holds the choices for one services list across a page of runs.
    """
    try:
        services, chosen = _services(filters)
        labels = {row["value"]: row["label"] for row in services}
        key = ",".join(chosen)
        store = cache if cache is not None else {}
        if key not in store:
            store[key] = _choices(chosen, labels)
        choices = store[key]
        rows = _parse_rows(_get(filters, PARAM_ROWS), choices)
        offered = {row["value"]: row["label"] for row in seams.account_type_options() or []}
        classes = [offered[code] for code in _list(_get(filters, PARAM_CLASSES)) if code in offered]
        months = _months(filters)
    except errors.ValidationError:
        return None
    head: list[dict[str, Any]] = [
        {"text": ", ".join(labels[code] for code in chosen if labels.get(code))},
        {"text": ", ".join(classes)} if classes else {"label_key": "reports.input.allClasses"},
        {
            "label_key": "reports.input.months_one" if months == 1 else "reports.input.months_other",
            "params": {"count": months},
        },
    ]
    lines: list[dict[str, Any]] = [{"parts": head}]
    for row in rows:
        parts = [{"text": row["item"]["label"]}]
        if row["version"].get("label"):
            parts.append({"text": row["version"]["label"]})
        if row["capacity_label"]:
            parts.append({"text": row["capacity_label"]})
        figures = [
            {
                "label_key": f"reports.rateImpact.input.rows.column.{name}",
                "kind": kind,
                "value": _money(row[name]),
            }
            for name, kind in _SUMMARY_FIGURES
            if row.get(name) is not None
        ]
        lines.append({"parts": parts, "figures": figures})
    return lines


#: KEY -> how a stored run of this report is described on History
#: (`run_history.present` asks; a report absent here has no summary).
MODULE_RUN_SUMMARIES: dict[str, Any] = {KEY: describe_run}


#: KEY -> the run parameters this viewer DECLARES. `runner.bind` passes a
#: declared name through for this key and for no other (`runner.declared_inputs`),
#: which is the framework's generic half of CR-179 §5's *server-declared inputs*.
MODULE_INPUTS: dict[str, tuple[str, ...]] = {KEY: INPUT_PARAMS}

#: KEY -> every column this viewer can serve (`runner.served_columns`).
MODULE_COLUMNS: dict[str, tuple[str, ...]] = {KEY: COLUMNS}

#: KEY -> viewer, owned by THIS module (`runner.queries_for` asks first).
MODULE_VIEWERS: dict[str, Any] = {KEY: rate_impact}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-179-BRC10 (12-governance/change-requests/CR-179-BRC10-rate-impact-report.md) · the server/screen contract of 2026-10-12
# screens: the standard report viewer at /reports/rate_impact (CR-179 §5 — no page of its own)
# generated: 2026-10-12 by lane RI-SERVER
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — see 06-backend/tests/test_cr179_rate_impact.py's module docstring
# exceptions: the contract deviations listed in the module docstring (a fifth reason `usage_unit_differs`; non-zero reasons only; a counted item's now box is per item; the schedule base is the NAMED code's, else 0; additive keys; empty `services` = every enabled service; a missing proposed price/amount is refused)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
