"""The plan reads of the plans redesign — `CR-167-BRC10` §7.3 (round 2 task 3).

Every section the New-plan Review and the details Services / Charges / Billing
tabs draw (ruling 11: *one shared component for both*), read **as of a date**
(*"Priced as of"*, image 28): the plan version in force on that date
(`BR-RAT-1066`) and each referenced item's version in force on it.

── THE ONE REFERENCE SHAPE (`ref`) ──────────────────────────────────────────
Every place a plan names something carries::

    {id, kind, code, name, version, version_label, effective_from, effective_to,
     next: {version, effective_from} | null}

`kind` ∈ `schedule · base_code · charge_code · deposit_code · tax · discount`.
Ruling 8: *"on rate schedules, Base charges, charge codes, discounts, tax - on
all show version and effective date"*. The numbering is the server's, so no
screen counts (`CR-167` §7.4 J6, J7):

* **schedule** — the n-th dated version in start order; a correction keeps the
  number of the version it corrects; a draft has none. `version_label` is the
  utility's own filed label, served beside it.
* **charge code (base, plan charge, deposit)** — the number of distinct dates
  its prices changed on, up to the date shown; `effective_from` is the latest of
  those dates. Worked: a code started 08/01/2026 and re-priced 09/01/2026 reads
  **V2 from 09/01/2026** on 10/03/2026 and **V1 from 08/01/2026** on 08/15/2026.
* **tax** — the tax chain's own `version_no` and window (`taxes`).
* **discount** — the discount version in force (`discount_versions`).

⚠ **NAMES AND WORDS, NEVER IDS (B14 rule 31, `DEF-RAT-9285`, `DEF-RAT-9288`).**
`id` travels so a screen can link; nothing a clerk reads is one. Money and
percentages are served as display strings (`BR-RAT-087`).

⚠ **NOTHING HERE PRICES A BILL.** It is a read for screens; billing reads the
same bindings through the same version rule (`plan_versioning`), never this.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterable

from django.db.models import Q, Subquery

from apps.rating import charge_prices, models, plan_versioning, seams, selectors
from apps.rating import discounts as discount_models
from apps.rating.constants import ALL_SIZES

#: §7.6 — the base table's heading noun per service (images 20, 27).
_SIZED_BY = {"trash": "cart size", "fire": "fire line size"}
#: §7.6 — the usage table's heading (images 20, 27), and the schedule's model in words.
_KIND_LABEL = {
    "blocks": "Block (per month)",
    "per_size": "Per size, per month",
    "per_count": "Per item, per month",
    "flat": "Flat (per month)",
    "time_of_use": "Time of use",
    "demand": "Demand",
    "seasonal": "Seasonal",
    "percent": "Share of another service",
}
_MODEL_LABEL = {
    "tiered": "Tiered",
    "flat": "Flat",
    "time_of_use": "Time of use",
    "demand": "Demand",
    "seasonal": "Seasonal",
    "capacity": "Capacity",
    "percent_of_service": "Percent of service",
}

KIND_SCHEDULE = "schedule"
KIND_BASE = "base_code"
KIND_CHARGE = "charge_code"
KIND_DEPOSIT = "deposit_code"
KIND_TAX = "tax"
KIND_DISCOUNT = "discount"


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _today() -> date:
    return seams.tenant_today()


_SYMBOLS = {"USD": "$", "CAD": "$", "AUD": "$", "MXN": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥"}


def _money_words(value: Any) -> str | None:
    """A rate in finished words — the utility's currency symbol and two places."""
    shown = selectors._display_money(value)
    if shown is None:
        return None
    currency = seams.tenant_currency() or "USD"
    symbol = _SYMBOLS.get(currency)
    return f"{symbol}{shown}" if symbol else f"{currency} {shown}"


def _rate_words(value: Any) -> str | None:
    """A UNIT PRICE in finished words — up to four places, at least two
    (`wording.rate_text`; PO 2026-10-02, verbatim: *"Show unit prices with up to
    4 decimals and keep every total at 2."*). `DEF-RAT-9708`: `_usage` read
    every price through `_money_words`, so `$8.9375` per kgal printed `$8.94`.
    Amounts (a base, a minimum, a deposit) stay on `_money_words`."""
    if value is None:
        return None
    from apps.rating.pricing import wording

    shown = wording.rate_text(Decimal(value))
    currency = seams.tenant_currency() or "USD"
    symbol = _SYMBOLS.get(currency)
    return f"{symbol}{shown}" if symbol else f"{currency} {shown}"


def _gl(account_id: Any) -> dict[str, str] | None:
    code, name = selectors._gl_display(account_id)
    if code is None:
        return None
    return {"code": code, "name": name}


def _ref(
    *,
    id: Any,
    kind: str,
    code: str | None,
    name: str | None,
    version: int | None,
    effective_from: Any,
    effective_to: Any = None,
    version_label: str | None = None,
    next_: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(id),
        "kind": kind,
        "code": code,
        "name": name,
        "version": version,
        "version_label": version_label,
        "effective_from": _iso(effective_from),
        "effective_to": _iso(effective_to),
        "next": next_,
    }


# ── refs ────────────────────────────────────────────────────────────────────


def schedule_ref(tariff: models.Tariff, as_of: date) -> dict[str, Any]:
    """J6 — a schedule's version is COUNTED in start order, never stored."""
    rows = list(
        models.TariffVersion.objects.filter(
            tenant_id=tariff.tenant_id, tariff=tariff, effective_from__isnull=False
        ).order_by("effective_from", "created_at", "id")
    )
    originals = [row for row in rows if row.corrects_id is None]
    number = {row.id: index + 1 for index, row in enumerate(originals)}
    # A correction keeps the number of the version it corrects.
    for row in rows:
        if row.corrects_id is not None:
            number[row.id] = number.get(row.corrects_id)
    current = selectors.in_force_version(tariff, as_of)
    # `DEF-RAT-9517` — every live row, a CORRECTION included: once an upcoming
    # version is corrected its original is superseded, and reading originals
    # only dropped the version from *next* and from the plan's banner.
    later = [
        row
        for row in rows
        if row.effective_from > as_of and row.superseded_by_id is None
    ]
    nxt = later[0] if later else None
    return _ref(
        id=tariff.id,
        kind=KIND_SCHEDULE,
        # A schedule has no code of its own (`tariffs` stores a name); "" keeps
        # the shared shape's `code` a string for every kind.
        code="",
        name=tariff.name,
        version=number.get(current.id) if current is not None else None,
        version_label=current.version_label if current is not None else None,
        effective_from=current.effective_from if current is not None else None,
        effective_to=current.effective_to if current is not None else None,
        next_=(
            {"version": number.get(nxt.id), "effective_from": _iso(nxt.effective_from)}
            if nxt is not None
            else None
        ),
    )


def _charge_price_dates(charge_ids: list[Any]) -> dict[Any, list[date]]:
    """Every distinct date each code's prices changed on (empty rows excluded),
    read through THE one price lookup (`charge_prices.history`, `G141`)."""
    if not charge_ids:
        return {}
    out: dict[Any, set[date]] = {}
    for charge_id, rows in charge_prices.history(charge_ids).items():
        for row in rows:
            if row.effective_to is not None and row.effective_to < row.effective_from:
                continue
            out.setdefault(charge_id, set()).add(row.effective_from)
    return {key: sorted(value) for key, value in out.items()}


def charge_ref(
    charge: models.Charge, kind: str, as_of: date, dates: dict[Any, list[date]] | None = None
) -> dict[str, Any]:
    """J7 — a charge code's version is the number of price changes up to `as_of`."""
    changes = (dates if dates is not None else _charge_price_dates([charge.id])).get(charge.id, [])
    upto = [day for day in changes if day <= as_of]
    after = [day for day in changes if day > as_of]
    # A code whose terms sit on the code itself (no dated price row — a penalty
    # stating its percent and minimum on `charges`) has never been re-priced:
    # it is V1, and it states no from-date.
    return _ref(
        id=charge.id,
        kind=kind,
        code=charge.code,
        name=charge.name,
        version=len(upto) or (1 if not changes else None),
        effective_from=upto[-1] if upto else None,
        next_=(
            {"version": len(upto) + 1, "effective_from": _iso(after[0])} if after else None
        ),
    )


def tax_ref(tax: models.Tax, as_of: date) -> dict[str, Any]:
    chain = tax.chain_id or tax.id
    later = (
        models.Tax.objects.filter(
            Q(chain_id=chain) | Q(pk=chain),
            deleted_at__isnull=True,
            is_draft=False,
            superseded_by__isnull=True,
            effective_from__gt=as_of, tenant_id=selectors._tenant_id(),
        )
        .order_by("effective_from")
        .first()
    )
    return _ref(
        id=tax.id,
        kind=KIND_TAX,
        # Many taxes carry no code; "" keeps the shared shape's `code` a string.
        code=tax.code or "",
        name=tax.name,
        version=tax.version_no,
        effective_from=tax.effective_from,
        effective_to=tax.effective_to,
        next_=(
            {"version": later.version_no, "effective_from": _iso(later.effective_from)}
            if later is not None
            else None
        ),
    )


def discount_ref(discount: Any, as_of: date) -> dict[str, Any]:
    version = selectors.discount_version_in_force(discount, as_of)
    later = (
        discount_models.DiscountVersion.objects.filter(
            discount=discount,
            status=discount_models.VERSION_ACTIVE,
            effective_from__gt=as_of, tenant_id=selectors._tenant_id(),
        )
        .order_by("effective_from")
        .first()
    )
    return _ref(
        id=discount.id,
        kind=KIND_DISCOUNT,
        code=discount.code,
        name=discount.name,
        version=getattr(version, "version_no", None),
        effective_from=getattr(version, "effective_from", None),
        effective_to=getattr(version, "effective_to", None),
        next_=(
            {"version": later.version_no, "effective_from": _iso(later.effective_from)}
            if later is not None
            else None
        ),
    )


# ── the plan's versions ─────────────────────────────────────────────────────


def version_state(version: Any, today: date | None = None) -> str:
    """`draft · scheduled · in_force · ended · corrected` — derived, never stored."""
    today = today or _today()
    if version.superseded_by_id is not None:
        return "corrected"
    if version.status == plan_versioning.VERSION_DRAFT:
        return "draft"
    if version.status == plan_versioning.VERSION_HISTORY:
        return "ended"
    if version.effective_from is not None and version.effective_from > today:
        return "scheduled"
    if version.effective_to is not None and version.effective_to < today:
        return "ended"
    return "in_force"


def plan_versions_windows(plan: models.RatePlan) -> list[dict[str, Any]]:
    """Every version of the plan with its window and state, NEWEST FIRST — the
    filing rows (`selectors.plan_versions`) plus any draft, each carrying
    `version`, `status`, `effective_from`, `effective_to`."""
    filings = {row["id"]: row for row in selectors.plan_versions(plan)}
    rows = models.PlanVersion.objects.filter(rate_plan=plan, tenant_id=selectors._tenant_id()).order_by(
        "-version_no", "-created_at", "-id"
    )
    names = seams.user_display_names([row.submitted_by_id for row in rows])
    worded = _version_change_words([row for row in rows if row.status != plan_versioning.VERSION_DRAFT])
    out: list[dict[str, Any]] = []
    for row in rows:
        base = filings.get(str(row.id)) or {
            "id": str(row.id),
            "version_no": row.version_no,
            "change_reason": row.change_reason,
            "submitted_by": selectors._actor_ref(row.submitted_by_id, names),
            "created_at": row.created_at.isoformat(),
            "changes": {"fields": [], "total": 0},
            "corrects": str(row.corrects_id) if row.corrects_id else None,
            "superseded_by": str(row.superseded_by_id) if row.superseded_by_id else None,
            "correction_reason": row.correction_reason,
            "corrected_by": None,
        }
        out.append(
            {
                **base,
                "version": row.version_no,
                "status": version_state(row),
                "effective_from": _iso(row.effective_from),
                "effective_to": _iso(row.effective_to),
                "reason": row.correction_reason or row.change_reason,
                # `DEF-RAT-10031` — what this version changed against the one
                # before it, in History's words; `terms_recorded` False marks a
                # copy that predates the fix (the screen says so in its place).
                **worded.get(str(row.id), {"change_words": [], "terms_recorded": True}),
            }
        )
    return out


def version_terms_recorded(row: models.PlanVersion) -> bool:
    """`DEF-RAT-10031` — does this version's stored copy hold its OWN terms?

    PO 2026-10-09, option (b), verbatim: *"yes - old changes are not required
    (b) Fix it going forward only - this is okay"*. A copy `plan_writes._publish`
    takes since the fix says so (`TERMS_RECORDED_KEY`); a correction's copy
    carries the corrected version's terms under `version_terms`. Any OTHER copy
    is trusted only where its four terms equal the version row's own columns —
    the copies written before the fix took the plan's columns BEFORE they
    mirrored the new version, so v2 with a $12.00 minimum holds the $10.00 it
    replaced and fails this test, while a v1 (whose columns were its own) and a
    v2 that moved no term pass it. An empty copy (a backfilled or seeded row,
    `rating/0063`) records no terms at all.
    """
    snap = row.snapshot if isinstance(row.snapshot, dict) else {}
    if snap.get(plan_versioning.TERMS_RECORDED_KEY) is True or isinstance(snap.get("version_terms"), dict):
        return True
    if "minimum_bill_amount" not in snap:
        return False

    def _dec(value: Any) -> Decimal | None:
        return None if value is None or value == "" else Decimal(str(value))

    late = snap.get("late_fee_charge")
    late_id = late.get("id") if isinstance(late, dict) else None
    return (
        _dec(snap.get("minimum_bill_amount")) == _dec(row.minimum_bill_amount)
        and _dec(snap.get("outside_city_factor")) == _dec(row.outside_city_factor)
        and bool(snap.get("budget_billing")) == bool(row.budget_billing)
        and (str(late_id) if late_id else None) == (str(row.late_fee_charge_id) if row.late_fee_charge_id else None)
    )


def _version_change_words(filings: list[models.PlanVersion]) -> dict[str, dict[str, Any]]:
    """`{version id: {change_words, terms_recorded}}` for the plan's filings,
    newest first — each worded against the NEXT row (the version before it, or
    for a correction the row it corrects, the order `selectors.plan_versions`
    guarantees). Where this copy or the one before it does not record its terms,
    no change is claimed: `terms_recorded` is False and the words are empty."""
    from apps.rating import history_words

    recorded = [version_terms_recorded(row) for row in filings]
    pairs: list[tuple[Any, Any]] = []
    index_of: list[int] = []
    for index, row in enumerate(filings):
        if index + 1 < len(filings) and recorded[index] and recorded[index + 1]:
            pairs.append((_version_terms_view(filings[index + 1].snapshot), _version_terms_view(row.snapshot)))
            index_of.append(index)
    worded = history_words.snapshot_changes(pairs) if pairs else []
    out: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(filings):
        has_before = index + 1 < len(filings)
        out[str(row.id)] = {
            "change_words": [],
            # The oldest filing claims no change, so it needs no mark.
            "terms_recorded": (recorded[index] and recorded[index + 1]) if has_before else True,
        }
    for index, words in zip(index_of, worded, strict=True):
        out[str(filings[index].id)]["change_words"] = words
    return out


def _plan_version_block(plan: models.RatePlan, as_of: date) -> dict[str, Any] | None:
    version = plan_versioning.version_on(plan.pk, as_of)
    if version is None:
        return None
    return {
        "version": version.version_no,
        "status": version_state(version),
        "effective_from": _iso(version.effective_from or plan.effective_from),
        "effective_to": _iso(version.effective_to if version.effective_from else plan.effective_to),
        "reason": version.correction_reason or version.change_reason,
    }


# ── the sections (ruling 11: Review and the details tabs draw the same) ─────


def _class_codes(plan: models.RatePlan) -> list[str | None]:
    ids = list(plan.account_type_ids or [])
    codes = [seams.account_type_code_by_id(value) for value in ids]
    return [code for code in codes if code] or [None]


def _details(plan: models.RatePlan, terms: dict[str, Any]) -> dict[str, Any]:
    ids = [str(one) for one in (plan.account_type_ids or [])]
    names = seams.account_type_names(ids)
    eligibility = plan.eligibility or {}
    notes = []
    for rule in eligibility.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        value = rule.get("value")
        label = value
        # `DEF-RAT-9285` — a stored class ID is shown by the class's NAME.
        if isinstance(value, str) and value in names:
            label = names[value]
        elif isinstance(value, str) and selectors._valid_uuid(value):
            label = seams.account_type_names([value]).get(value, value)
        notes.append(
            {
                "attribute": rule.get("attribute"),
                "operator": rule.get("operator"),
                "value": value,
                "value_label": label,
            }
        )
    return {
        "name": plan.name,
        "code": plan.code,
        "customer_classes": [{"value": one, "label": names.get(one)} for one in ids],
        "description": plan.description,
        "intended_for": {
            key: bool(eligibility.get(key))
            for key in ("cap_proof", "min_demand_25kw", "owner_occupied")
        },
        "notes": notes,
        "minimum_bill_display": selectors._display_money(terms["minimum_bill_amount"]),
        "budget_billing": bool(terms["budget_billing"]),
    }


def _size_names(codes: Iterable[str]) -> dict[str, str]:
    return seams.size_class_names([code for code in codes if code and code != ALL_SIZES])


def _class_name_list(codes: Any) -> list[str]:
    """`DEF-CUS-9821` — a stored class-code list as NAMES (B14 rule 31); `[]`
    is every class, the reading `applies_to_customer_classes` has carried since
    `DEF-273`. A code no class carries is shown as itself."""
    if not codes:
        return []
    names = seams.account_type_names_by_code()
    return [names.get(str(one), str(one)) for one in codes]


def _usage(version: Any) -> dict[str, Any]:
    """The schedule's usage charges as rows of words (ruling 12's vocabulary)."""
    if version is None:
        return {"kind": None, "kind_label": None, "rows": []}
    structure = selectors.version_structure(version)
    unit = structure.get("unit")
    rows: list[dict[str, Any]] = []
    tiers = structure.get("tiers") or []
    per_size = any(tier.get("size_class") for tier in tiers)
    sizes = _size_names(tier.get("size_class") for tier in tiers)

    def _price(value: Any) -> str | None:
        # The server's FINISHED words (§7.6): *$4.24 per kgal*.
        shown = _rate_words(Decimal(value)) if value is not None else None
        return f"{shown} per {unit}" if shown and unit else shown

    def _row(label: str, rate_display: str | None, *, key: str | None = None, args: dict[str, Any] | None = None,
             season: str | None = None, amount: str | None = None, per: str | None = None) -> dict[str, Any]:
        """One usage row: its English words AND the codes behind them
        (`DEF-RAT-9502`). `label_key` names the product's own word (*Over*,
        *Each month*, *Energy*, *Demand*, *Share of*); null means the label is
        the utility's own data (a size, a window). `rate_amount` and
        `rate_unit` let a screen say *per* in its own language; the English
        `label` and `rate_display` stay for the CSV and any older reader."""
        return {
            "label": label,
            "rate_display": rate_display,
            "label_key": key,
            "label_args": args or {},
            "season": season,
            "rate_amount": amount,
            "rate_unit": per,
        }

    for tier in tiers:
        price = tier.get("unit_price")
        amount = _rate_words(Decimal(price)) if price is not None else None
        key, args = None, {}
        if per_size:
            if tier.get("size_class"):
                label = sizes.get(tier["size_class"], tier["size_class"])
            else:
                label, key = ALL_SIZES, "allSizes"
        elif tier.get("to_qty") is None:
            from_qty = Decimal(tier["from_qty"]) if tier.get("from_qty") is not None else Decimal("0")
            if from_qty > 0:
                label, key, args = f"Over {tier.get('from_qty_display')}", "over", {"qty": tier.get("from_qty_display")}
            else:
                label, key = "Each month", "eachMonth"
        else:
            label = f"{tier.get('from_qty_display')} – {tier.get('to_qty_display')}"
        season = tier.get("season") or None
        if season:
            label = f"{season} · {label}"
        rows.append(_row(label, _price(price), key=key, args=args, season=season, amount=amount, per=unit if amount else None))
    for window in structure.get("windows") or []:
        price = window.get("unit_price")
        amount = _rate_words(Decimal(price)) if price is not None else None
        rows.append(_row(window["label"], _price(price), amount=amount, per=unit if amount else None))
    capacity = structure.get("capacity")
    if capacity:
        shown = _rate_words(Decimal(capacity["rate_per_unit"])) if capacity.get("rate_per_unit") else None
        if capacity.get("unit_label"):
            rows.append(_row(capacity["unit_label"], shown, amount=shown))
        else:
            rows.append(_row("Each", shown, key="each", amount=shown))
    demand = structure.get("demand")
    if demand:
        energy = demand.get("energy_rate_per_kwh")
        energy_amount = _rate_words(Decimal(energy)) if energy is not None else None
        rows.append(_row("Energy", _price(energy), key="energy", amount=energy_amount, per=unit if energy_amount else None))
        demand_amount = _rate_words(Decimal(demand["demand_rate_per_kw"])) if demand.get("demand_rate_per_kw") else None
        rows.append(
            _row(
                "Demand",
                f"{demand_amount} per kW" if demand_amount else None,
                key="demand",
                amount=demand_amount,
                per="kW" if demand_amount else None,
            )
        )
    if structure.get("percent") is not None:
        basis = structure.get("basis_service")
        shown = f"{Decimal(structure['percent']).quantize(Decimal('0.01'))}%"
        rows.append(
            _row(
                f"Share of {basis or 'service'}",
                shown,
                key="share" if basis else "shareAny",
                args={"service": basis} if basis else {},
                amount=shown,
            )
        )
    kind = {
        "tiered": "blocks",
        "flat": "flat",
        "time_of_use": "time_of_use",
        "demand": "demand",
        "seasonal": "seasonal",
        "capacity": "per_size" if per_size else "per_count",
        "percent_of_service": "percent",
    }.get(version.model, version.model)
    if per_size and kind == "blocks":
        kind = "per_size"
    label = _KIND_LABEL.get(kind)
    if kind == "per_size" and version.tariff.service.code in _SIZED_BY:
        label = {"trash": "Per cart, per month", "fire": "Per line, per month"}[version.tariff.service.code]
    return {"kind": kind, "kind_label": label, "unit": unit, "rows": rows}


def _base_block(
    service_code: str,
    named: Any,
    class_codes: list[str | None],
    as_of: date,
    dates: dict[Any, list[date]],
) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING (`DEF-RAT-9832`). The base the bill charges for
    this service (ruling 7) — the schedule's NAMED code and nothing else.

    ⚠ **THE POOL IS GONE (PO 2026-10-06, verbatim: *"if it is provided then you
    will take it if it is not provided then you will take it zeo ; but you
    cannot take W-COM because it is availabel in charge coede"*).** Until then
    a schedule naming none read the class-narrowed `is_base` codes here and
    showed one, or *ambiguous* with several. Now it is `not_named`: `$0.00`,
    the figure the bill charges (`selectors._no_base_code_named`), and the
    screen's *Choose a base code*. A service with no base code at all keeps
    `none`. `ambiguous` is no longer served; an older client still reads it."""
    if named is not None:
        candidates = [named]
    else:
        has_a_base_code = models.Charge.objects.filter(
            deleted_at__isnull=True, is_base=True, service__code=service_code, tenant_id=selectors._tenant_id()
        ).exists()
        if has_a_base_code:
            return {
                "code": None,
                "by_size": [],
                "flat_display": selectors._display_money(Decimal("0")),
                "state": "not_named",
                "codes": [],
                "options": [],
                "sized_by_label": None,
                "monthly_amount": "0.0000",
                "named": False,
                "classes": [],
            }
        candidates = []
    # `DEF-CUS-9821` — `named`: the schedule's version in force names its base
    # code (New Connect's *"its rate schedule names no base code"* is true
    # exactly when this is false). `classes`: the served code's customer
    # classes by NAME, `[]` = every class (the block's *Applies to*).
    empty = {"sized_by_label": None, "monthly_amount": None, "named": named is not None, "classes": []}
    if not candidates:
        return {"code": None, "by_size": [], "flat_display": None, "state": "none", "codes": [], **empty}
    if len(candidates) > 1:
        # `DEF-RAT-9504` — an every-class plan: the bill picks the base by the
        # ACCOUNT's class, so no one figure is honest; say which class pays
        # which code, by NAME (B14 rule 31).
        class_names = seams.account_type_names_by_code()
        return {
            "code": None,
            "by_size": [],
            "flat_display": None,
            "state": "ambiguous",
            "codes": [code.code for code in candidates],
            "options": [
                {
                    "code": code.code,
                    "classes": [
                        class_names.get(str(one), str(one)) for one in (code.applies_to_customer_classes or [])
                    ],
                }
                for code in candidates
            ],
            **empty,
        }
    code = candidates[0]
    rows = charge_prices.rows_in_force([code.id], as_of).get(code.id, [])
    wanted = {one for one in class_codes if one}
    rows = [row for row in rows if row.customer_class is None or row.customer_class in wanted]
    flat = None
    flat_amount = None
    sized_amounts: list[Decimal] = []
    by_size = []
    names = _size_names(row.size_class for row in rows)
    for row in sorted(rows, key=lambda r: (r.size_class or "", r.customer_class or "")):
        if row.size_class == ALL_SIZES or getattr(row, "is_flat", False):
            flat = selectors._display_money(row.amount)
            flat_amount = row.amount
            continue
        if row.amount is not None:
            sized_amounts.append(row.amount)
        by_size.append(
            {
                "size_class": row.size_class,
                "size_label": names.get(row.size_class, row.size_class),
                "customer_class": row.customer_class,
                "amount_display": selectors._display_money(row.amount),
            }
        )
    state = "ok" if (flat is not None or by_size) else "refused"
    # §7.6 (lane PLAN-FORM) — J8's figure per service as a 4-place string the
    # form SUMS exactly: the flat base, else the smallest size's.
    monthly = flat_amount if flat_amount is not None else (min(sized_amounts) if sized_amounts else None)
    return {
        "code": charge_ref(code, KIND_BASE, as_of, dates),
        "sized_by_label": _SIZED_BY.get(service_code, "meter size") if by_size else None,
        "by_size": by_size,
        "flat_display": flat,
        "state": state,
        "codes": [code.code],
        "monthly_amount": None if monthly is None else str(Decimal(monthly).quantize(Decimal("0.0001"))),
        "named": named is not None,
        "classes": _class_name_list(code.applies_to_customer_classes),
    }


def _minimum_block(version: Any) -> dict[str, Any]:
    if version is None:
        return {"by_size": [], "flat_display": None}
    rows = list(
        models.RateSizeRow.objects.filter(tariff_version=version, tenant_id=selectors._tenant_id()).order_by("size_class")
    )
    names = _size_names(row.size_class for row in rows)
    figures = [row for row in rows if row.minimum_bill is not None]
    flat = None
    if figures and len({row.minimum_bill for row in figures}) == 1 and len(figures) == len(rows):
        flat = selectors._display_money(figures[0].minimum_bill)
    return {
        "by_size": [
            {
                "size_class": row.size_class,
                "size_label": names.get(row.size_class, row.size_class),
                "amount_display": selectors._display_money(row.minimum_bill),
            }
            for row in rows
        ],
        "flat_display": flat,
    }


def _services(
    plan: models.RatePlan, terms: dict[str, Any], as_of: date, classes: list[str] | None = None
) -> list[dict[str, Any]]:
    # `DEF-CUS-9821` — `classes` (an ACCOUNT's class, New Connect step 2)
    # narrows the base exactly as the plan's own classes do, because the bill
    # picks a base by the account's class. Absent, the plan's classes, as before.
    wanted = [one for one in (classes or []) if one]
    class_codes: list[str | None] = list(wanted) if wanted else _class_codes(plan)
    lines = list(
        models.PlanService.objects.filter(rate_plan=plan, tenant_id=selectors._tenant_id())
        .select_related("service")
        .order_by("service__sort", "service__code")
    )
    bound = {
        str(row.service_id): row
        for row in models.PlanRateSchedule.objects.filter(rate_plan=plan, tenant_id=selectors._tenant_id()).select_related("tariff")
    }
    named_codes = []
    versions: dict[str, Any] = {}
    for key, binding in bound.items():
        version = selectors.in_force_version(binding.tariff, as_of)
        versions[key] = version
        if version is not None and version.base_charge_code_id:
            named_codes.append(version.base_charge_code_id)
    base_ids = list(
        models.Charge.objects.filter(is_base=True, deleted_at__isnull=True, tenant_id=selectors._tenant_id()).values_list(
            "id", flat=True
        )
    )
    dates = _charge_price_dates(base_ids + named_codes)
    factor = terms.get("outside_city_factor")
    percent = selectors._outside_city_percent_value(factor) if factor is not None else None
    surcharging = percent is not None and percent != 0
    out = []
    for line in lines:
        key = str(line.service_id)
        binding = bound.get(key)
        version = versions.get(key)
        named = version.base_charge_code if version is not None and version.base_charge_code_id else None
        gl_id = line.gl_account_id or seams.service_revenue_gl_account_id(line.service.code)
        out.append(
            {
                "service": line.service.code,
                "name": line.service.name,
                "gl": _gl(gl_id),
                "schedule": (
                    _schedule_with_model(binding.tariff, version, as_of) if binding is not None else None
                ),
                "base": _base_block(line.service.code, named, class_codes, as_of, dates),
                "minimum": _minimum_block(version),
                "usage": _usage(version),
                "outside_city": {
                    "surcharged": bool(surcharging and not line.outside_city_exempt),
                    "percent_display": (
                        selectors._display_percent_points(percent)
                        if surcharging and not line.outside_city_exempt
                        else None
                    ),
                },
            }
        )
    return out


def _schedule_with_model(tariff: models.Tariff, version: Any, as_of: date) -> dict[str, Any]:
    model = getattr(version, "model", None)
    return {**schedule_ref(tariff, as_of), "model": model, "model_label": _MODEL_LABEL.get(model or "")}


def _rate_percent(tax: models.Tax) -> str | None:
    """§7.6 — the rate in percentage POINTS, six places, for the form's exact sum."""
    if tax.kind != "percent" or tax.rate is None:
        return None
    return str((Decimal(tax.rate) * 100).quantize(Decimal("0.000001")))


def _base_total(services: list[dict[str, Any]]) -> dict[str, Any]:
    """J8 — monthly base charges = each service's base at its SMALLEST size.

    A display figure; it moves no money. `unavailable` names the first service
    whose base cannot be stated (none, ambiguous, refused)."""
    total = Decimal("0")
    for line in services:
        base = line["base"]
        if base["state"] == "not_named":
            # `DEF-RAT-9832` — the schedule names no base code: the bill
            # charges `$0.00` for this service, and so does this total.
            continue
        if base["state"] != "ok":
            return {"amount_display": None, "unavailable": f"{line['service']}:{base['state']}"}
        if base["flat_display"] is not None:
            figure = base["flat_display"]
        else:
            figures = [row["amount_display"] for row in base["by_size"] if row["amount_display"]]
            if not figures:
                return {"amount_display": None, "unavailable": f"{line['service']}:refused"}
            figure = min(figures, key=lambda text: Decimal(text.replace("$", "").replace(",", "")))
        total += Decimal(figure.replace("$", "").replace(",", ""))
    return {"amount_display": selectors._display_money(total), "unavailable": None}


def _priced_rows(charge: models.Charge, as_of: date, class_names: dict[str, str]) -> tuple[str, list[dict[str, Any]]]:
    amounts = charge_prices.rows_in_force([charge.id], as_of).get(charge.id, [])
    terms = charge_prices.rows_in_force([charge.id], as_of, terms=True).get(charge.id, [])
    sizes = _size_names(row.size_class for row in amounts)
    rows: list[dict[str, Any]] = []
    for row in terms:
        rows.append(
            {
                "class_or_size_label": class_names.get(row.customer_class or "", row.customer_class) if row.customer_class else "Everyone",
                # `DEF-RAT-9502` — the code behind *Everyone*, so a screen words it.
                "everyone": not row.customer_class,
                "amount_display": None,
                "percent_display": selectors._display_percent(row.percent),
                "min_display": selectors._display_money(row.min_amount),
            }
        )
    for row in amounts:
        if row.customer_class:
            label = class_names.get(row.customer_class, row.customer_class)
        elif row.size_class and row.size_class != ALL_SIZES:
            label = sizes.get(row.size_class, row.size_class)
        else:
            label = "Everyone"
        rows.append(
            {
                "class_or_size_label": label,
                "everyone": label == "Everyone",
                "amount_display": selectors._display_money(row.amount),
                "percent_display": None,
                "min_display": None,
            }
        )
    if not rows and charge.percent is not None:
        rows.append(
            {
                "class_or_size_label": "Everyone",
                "everyone": True,
                "amount_display": None,
                "percent_display": selectors._display_percent(charge.percent),
                "min_display": selectors._display_money(charge.min_amount),
            }
        )
    by_size = any(row.size_class and row.size_class != ALL_SIZES and not row.customer_class for row in amounts)
    by_class = any(row.customer_class for row in [*amounts, *terms])
    if by_size:
        priced_by = "size"
    elif by_class:
        priced_by = "class"
    elif terms or charge.percent is not None:
        priced_by = "percent"
    else:
        priced_by = "one_amount"
    return priced_by, rows


_WHEN = {
    "recurring": "Every bill",
    "one_time": "Once",
    "penalty": "After the due date",
    "refundable": "At move-in",
}


def _class_names() -> dict[str, str]:
    """`{account_types.code: name}` — the words a price row's class is printed in."""
    return seams.account_type_names_by_code()


def _grace(charge: models.Charge, plan: models.RatePlan | None = None) -> dict[str, Any] | None:
    """🔒 PO ruling 2026-10-06 11 (a) — a PENALTY code's late-fee grace, as the
    plan shows it: `{days, mode, from}`; None on any other type. For the
    plan's own late-fee code a grace override the plan stated before the
    ruling still applies (`from: "plan"`), exactly as billing reads it
    (`selectors._late_fee_grace`)."""
    if charge.charge_type != "penalty":
        return None
    override = (
        models.PlanPenaltyRule.objects.filter(rate_plan=plan, tenant_id=selectors._tenant_id())
        .values("grace_days", "grace_mode")
        .first()
        if plan is not None
        else None
    ) or {}
    default_days, default_mode = seams.late_grace_default()
    if override.get("grace_days") is not None:
        days, source = override["grace_days"], "plan"
    elif charge.grace_days is not None:
        days, source = charge.grace_days, "charge_code"
    else:
        days, source = default_days, "billing_defaults"
    mode = override.get("grace_mode") or charge.grace_mode or default_mode
    return {"days": int(days), "mode": mode, "from": source}


def _charge_codes(plan: models.RatePlan, terms: dict[str, Any], as_of: date) -> list[dict[str, Any]]:
    """The plan's charge codes as ONE list, the late fee included ONCE
    (`BR-RAT-1011`, `DEF-RAT-9328`); base codes never (`BR-RAT-088`)."""
    rules = list(
        models.PlanChargeRule.objects.filter(rate_plan=plan, role="charge", tenant_id=selectors._tenant_id())
        .select_related("charge")
        .order_by("charge__code")
    )
    charges = [rule.charge for rule in rules if not rule.charge.is_base and rule.charge.deleted_at is None]
    late_id = terms.get("late_fee_charge_id")
    late = None
    if late_id is not None:
        late = models.Charge.objects.filter(pk=late_id, deleted_at__isnull=True, tenant_id=selectors._tenant_id()).first()
        if late is not None and late.id not in {charge.id for charge in charges}:
            charges.insert(0, late)
    dates = _charge_price_dates([charge.id for charge in charges])
    names = _class_names()
    out = []
    for charge in charges:
        priced_by, rows = _priced_rows(charge, as_of, names)
        out.append(
            {
                "ref": charge_ref(charge, KIND_CHARGE, as_of, dates),
                "late_fee": late is not None and charge.id == late.id,
                # 🔒 2026-10-06 11 (a) — the grace the late fee is assessed on.
                "grace": _grace(charge, plan if late is not None and charge.id == late.id else None),
                "priced_by": priced_by,
                "rows": rows,
                "gl": _gl(charge.gl_account_id),
                "type_label": charge.charge_type,
                "when_label": _WHEN.get(charge.charge_type or "", None),
            }
        )
    return out


def _deposits(plan: models.RatePlan, as_of: date) -> list[dict[str, Any]]:
    """Ruling 9 — the deposit codes the plan names, priced by CUSTOMER CLASS or
    by METER SIZE (`OQ-RAT-12786` CLOSED 2026-10-03, PO verbatim *"(a) Class or
    size: the deposit table gets a size column, like charge codes have."*) —
    `priced_by` says which and each row's `class_or_size_label` names the class
    or the size; then any typed `plan_deposit_rules` rows a plan still carries
    from before 2026-09-08, shown with no code."""
    rules = list(
        models.PlanChargeRule.objects.filter(rate_plan=plan, role="deposit", tenant_id=selectors._tenant_id())
        .select_related("charge")
        .order_by("charge__code")
    )
    dates = _charge_price_dates([rule.charge_id for rule in rules])
    names = _class_names()
    out = []
    for rule in rules:
        priced_by, rows = _priced_rows(rule.charge, as_of, names)
        out.append(
            {
                "ref": charge_ref(rule.charge, KIND_DEPOSIT, as_of, dates),
                "priced_by": priced_by,
                "rows": [
                    {
                        "class_or_size_label": row["class_or_size_label"],
                        "everyone": row["everyone"],
                        "amount_display": row["amount_display"],
                    }
                    for row in rows
                ],
                "gl": _gl(rule.charge.gl_account_id),
                # `DEF-CUS-9821` — the code's own type says it comes back.
                "refundable": rule.charge.charge_type == "refundable",
            }
        )
    legacy = list(models.PlanDepositRule.objects.filter(rate_plan=plan, tenant_id=selectors._tenant_id()).order_by("account_type_id"))
    if legacy:
        type_names = seams.account_type_names([row.account_type_id for row in legacy])
        out.append(
            {
                "ref": None,
                "priced_by": "class",
                "rows": [
                    {
                        "class_or_size_label": type_names.get(str(row.account_type_id)),
                        "amount_display": selectors._display_money(row.amount),
                    }
                    for row in legacy
                ],
                "gl": None,
                "refundable": None,
            }
        )
    return out


def _taxed_codes(tax: models.Tax) -> list[str]:
    """`DEF-RAT-9502` — what a tax is levied on, as codes (`usage`, `base`), so
    a screen words *Usage and base charges* in its own language."""
    return [code for code, on_it in (("usage", tax.base_includes_usage), ("base", tax.base_includes_base)) if on_it]


def _taxes(
    plan: models.RatePlan, as_of: date, classes: list[str] | None = None
) -> tuple[list[dict[str, Any]], str | None]:
    bound = set(
        models.PlanTaxRule.objects.filter(rate_plan=plan, tax__isnull=True, tenant_id=selectors._tenant_id()).values_list(
            "jurisdiction_id", flat=True
        )
    )
    taxes = selectors._plan_taxes(plan)
    # ⊕ `DEF-CUS-9836` — an account's class (`?classes=`) decides who pays, as
    # it decides the base in `_services`; absent, the plan's own classes.
    wanted = [one for one in (classes or []) if one]
    class_codes = wanted or selectors.plan_class_codes(plan)
    out = []
    for tax in taxes:
        jurisdiction = tax.jurisdiction if tax.jurisdiction_id else None
        what = []
        if tax.base_includes_usage:
            what.append("Usage")
        if tax.base_includes_base:
            what.append("base")
        out.append(
            {
                "ref": tax_ref(tax, as_of),
                "rate_percent": _rate_percent(tax),
                "rate_display": selectors._display_percent(tax.rate)
                if tax.kind == "percent"
                else selectors._display_money(tax.flat_amount),
                "what_is_taxed_label": (" and ".join(what) + " charges").capitalize() if what else None,
                "what_is_taxed": _taxed_codes(tax),
                "gl": _gl(tax.liability_gl_account_id),
                "authority": (jurisdiction.authority or jurisdiction.name) if jurisdiction else None,
                "brought_by": "jurisdiction" if tax.jurisdiction_id in bound else "attached",
                # `DEF-RAT-9519` — `none`: listed, marked, not in *combined*.
                "reaches_plan_classes": selectors.tax_reach_of_classes(tax, class_codes),
                # `DEF-CUS-9821` — who pays it, by NAME; `[]` = every class.
                "customer_classes": _class_name_list(tax.applies_to_customer_classes),
            }
        )
    return out, selectors.plan_combined_tax_rate_display(plan, wanted or None)


def _discounts(plan: models.RatePlan, as_of: date) -> list[dict[str, Any]]:
    rows = selectors.plan_discount_rules(plan, as_of)
    by_id = {
        str(one.id): one
        for one in discount_models.Discount.objects.filter(pk__in=[row["discount_id"] for row in rows], tenant_id=selectors._tenant_id())
    }
    out = []
    for row in rows:
        discount = by_id.get(row["discount_id"])
        if discount is None:
            continue
        version = selectors.discount_version_in_force(discount, as_of)
        out.append(
            {
                "ref": discount_ref(discount, as_of),
                # `DEF-CUS-9821` — how a customer gets it and whether proof is
                # asked, from the version in force (New Connect's *How*, *Proof*).
                "enrolment_mode": getattr(version, "enrolment_mode", None),
                "proof_required": getattr(version, "proof_required", None),
                "value_display": row["value_display"],
                "gl": _gl(getattr(discount, "gl_account_id", None)),
                "enrolled": row["enrolled"],
                "offered_from": row["available_from"],
                "offered_until": row["available_to"],
            }
        )
    return out


def _upcoming(plan: models.RatePlan, sections: dict[str, Any], as_of: date) -> list[dict[str, Any]]:
    """Ruling 13's banner — the earliest later version of the plan or of any
    item it names, earliest first."""
    found: list[dict[str, Any]] = []
    later = (
        models.PlanVersion.objects.filter(
            rate_plan=plan,
            status=plan_versioning.VERSION_PUBLISHED,
            superseded_by__isnull=True,
            effective_from__gt=as_of, tenant_id=selectors._tenant_id(),
        )
        .order_by("effective_from")
        .first()
    )
    if later is not None:
        found.append(
            {
                "kind": "plan",
                "code": plan.code,
                "name": plan.name,
                "version": later.version_no,
                "effective_from": _iso(later.effective_from),
            }
        )

    def _take(ref: Any) -> None:
        if ref and ref.get("next"):
            found.append(
                {
                    "kind": ref["kind"],
                    "code": ref["code"],
                    "name": ref["name"],
                    "version": ref["next"]["version"],
                    "effective_from": ref["next"]["effective_from"],
                }
            )

    for line in sections["services"]:
        _take(line.get("schedule"))
        _take(line["base"].get("code"))
    for group in ("charge_codes", "taxes", "deposits", "discounts"):
        for item in sections[group]:
            _take(item.get("ref"))
    return sorted(found, key=lambda row: (row["effective_from"] or "", row["kind"]))


def _read_day(plan_id: Any, day: date) -> date:
    """`DEF-RAT-9516` — the day a plan READ prices from.

    A day some published version's window covers is itself. A day NO window
    covers — before the plan's first start — is read as the first version that
    starts after it: the version that will apply first. Without this the read
    fell through `plan_versioning.version_on` to the HEAD, the NEWEST version,
    so a plan from 11/01/2026 with a v2 from 01/01/2027 showed v2's $12.00
    minimum today and *Fix a mistake* corrected v2. READS ONLY: billing's
    `version_on` (and every bill) is untouched — a bill never prices a day
    before the plan starts."""
    versions = models.PlanVersion.objects.filter(
        rate_plan_id=plan_id,
        status=plan_versioning.VERSION_PUBLISHED,
        superseded_by__isnull=True,
        effective_from__isnull=False, tenant_id=selectors._tenant_id(),
    )
    covered = versions.filter(effective_from__lte=day).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=day)
    )
    if covered.exists():
        return day
    first = versions.filter(effective_from__gt=day).order_by("effective_from").first()
    return first.effective_from if first is not None else day


def plan_sections(plan_id: Any, as_of: date | None = None, classes: list[str] | None = None) -> dict[str, Any]:
    """`GET /plans/{id}?as_of=` — the §7.3 additions, read AS OF the date
    (a day before the plan starts reads its first version, `_read_day`).
    `classes` (`?classes=`, `DEF-CUS-9821`) narrows each service's BASE to an
    account's class; absent, the read is what it always was."""
    plan = selectors.plan_or_404(plan_id)
    asked = as_of or _today()
    when = _read_day(plan.pk, asked)
    terms = plan_versioning.terms_on(plan, when)
    with plan_versioning.pricing_day(when):
        services = _services(plan, terms, when, classes)
        taxes, combined = _taxes(plan, when, classes)
        sections: dict[str, Any] = {
            "as_of": asked.isoformat(),
            "plan_version": _plan_version_block(plan, when),
            "versions": plan_versions_windows(plan),
            "details": _details(plan, terms),
            "services": services,
            "base_total": _base_total(services),
            "charge_codes": _charge_codes(plan, terms, when),
            "taxes": taxes,
            "combined_tax_rate_display": combined,
            "deposits": _deposits(plan, when),
            "discounts": _discounts(plan, when),
        }
        sections["outside_city_percent_display"] = (
            selectors._display_percent_points(
                selectors._outside_city_percent_value(terms["outside_city_factor"])
            )
            if terms.get("outside_city_factor") is not None
            else None
        )
        surcharged = [line["name"] for line in services if line["outside_city"]["surcharged"]]
        sections["outside_city_surcharge"] = (
            {
                "percent_display": sections["outside_city_percent_display"],
                "service_names": surcharged,
            }
            if sections["outside_city_percent_display"] and surcharged
            else None
        )
        sections["currency"] = seams.tenant_currency()
        sections["upcoming"] = _upcoming(plan, sections, asked)
    return sections


# ── the list (image 01) ────────────────────────────────────────────────────


def list_additions(plans: list[Any]) -> dict[str, dict[str, Any]]:
    """Per plan on ONE page: `schedules` (count), `units` (current
    assignments — the Units tab's number), the version in force today with its
    window, and `upcoming_version`. Bounded by the page (`NFR-3`).

    `customer_classes` (`DEF-RAT-9354`) is the details read's shape —
    `[{value, label}]`, `[]` for every class — named by ONE read for the whole
    page, so the list never reads the tenant's class list a second time."""
    today = _today()
    out: dict[str, dict[str, Any]] = {}
    class_ids = sorted({str(one) for plan in plans for one in (plan.account_type_ids or [])})
    class_names = seams.account_type_names(class_ids) if class_ids else {}
    for plan in plans:
        with plan_versioning.pricing_day(today):
            schedules = models.PlanRateSchedule.objects.filter(rate_plan=plan, tenant_id=selectors._tenant_id()).count()
        # `DEF-RAT-9516` — before its first start a plan lists the version it
        # will start with, not the newest.
        version = plan_versioning.version_on(plan.pk, _read_day(plan.pk, today))
        later = (
            models.PlanVersion.objects.filter(
                rate_plan=plan,
                status=plan_versioning.VERSION_PUBLISHED,
                superseded_by__isnull=True,
                effective_from__gt=today, tenant_id=selectors._tenant_id(),
            )
            .order_by("effective_from")
            .first()
        )
        single = version is None or not models.PlanVersion.objects.filter(
            rate_plan=plan, superseded_by__isnull=True, tenant_id=selectors._tenant_id()
        ).exclude(pk=version.pk).exclude(status=plan_versioning.VERSION_HISTORY).exists()
        out[str(plan.id)] = {
            "customer_classes": [
                {"value": one, "label": class_names[one]}
                for one in (str(value) for value in (plan.account_type_ids or []))
                if one in class_names  # an id nobody can name is left out (B14 rule 31)
            ],
            "schedules": schedules,
            "units": int(getattr(plan, "account_count", 0) or 0),
            "version": version.version_no if version is not None else plan.version,
            "effective_from": _iso(
                plan.effective_from if single or version is None else version.effective_from
            ),
            "effective_to": _iso(
                plan.effective_to if single or version is None else version.effective_to
            ),
            "upcoming_version": (
                {"version": later.version_no, "effective_from": _iso(later.effective_from)}
                if later is not None
                else None
            ),
        }
    return out


# ── Units (images 31–33) ─────────────────────────────────────────────────────

OCCUPANCY_VALUES = ("occupied", "vacant")


def plan_units_filtered(plan_id: Any, q: str = "", occupancy: str | None = None) -> Any:
    """The Units tab's queryset with search and the occupancy filter, all SQL
    (`NFR-3`; J11 — occupancy is asked of customers as a sub-select)."""
    qs = selectors.plan_units_queryset(plan_id)
    term = (q or "").strip()
    if len(term) >= selectors.MIN_SEARCH_CHARS:
        qs = qs.filter(
            Q(unit__label__icontains=term)
            | Q(unit__unit_no__icontains=term)
            | Q(unit__premises__address_line__icontains=term)
        )
    if occupancy in OCCUPANCY_VALUES:
        occupied = seams.occupied_unit_ids_subquery()
        qs = qs.filter(unit_id__in=occupied) if occupancy == "occupied" else qs.exclude(unit_id__in=occupied)
    return qs


UNIT_CSV_HEADER = ("Unit", "Premises", "City", "Services", "Account", "Customer", "Occupancy", "On this plan since")


def plan_units_csv(plan_id: Any, q: str = "", occupancy: str | None = None) -> Iterable[str]:
    """The WHOLE filtered set as CSV, in chunks of 500 (streamed)."""
    qs = plan_units_filtered(plan_id, q, occupancy)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(UNIT_CSV_HEADER)
    yield buffer.getvalue()
    chunk: list[Any] = []

    def _flush(items: list[Any]) -> str:
        out = io.StringIO()
        w = csv.writer(out)
        for row in selectors.plan_unit_rows(items):
            w.writerow(
                (
                    row.get("unit_label") or row.get("unit_no") or "",
                    row.get("premises_address") or "",
                    row.get("premises_city") or "",
                    " ".join(row.get("services") or []),
                    row.get("account_no") or "",
                    row.get("customer_name") or "",
                    "Vacant" if row.get("vacant") else "Occupied",
                    row["assigned_from"].strftime("%m/%d/%Y") if row.get("assigned_from") else "",
                )
            )
        return out.getvalue()

    for item in qs.iterator(chunk_size=500):
        chunk.append(item)
        if len(chunk) >= 500:
            yield _flush(chunk)
            chunk = []
    if chunk:
        yield _flush(chunk)


# ── form options (§7.3) ─────────────────────────────────────────────────────


def form_options(on: date | None = None, classes: list[str] | None = None) -> dict[str, Any]:
    """`GET /plans/form-options` — what the New/Edit form offers on `?on=` (the
    date the version starts), each item in the SAME section shape the plan
    read serves (`ref` + what its row shows), so Review builds the shared
    sections from these without a second shape (ruling 11, `CR-167` §7.6)."""
    day = on or _today()
    # `?classes=<id>,<id>` — the customer classes ticked on step 1, so each
    # schedule's base is narrowed exactly as the plan's own read narrows it
    # (a Residential plan's water base is BASE-W, not *several base codes*).
    class_codes = [seams.account_type_code_by_id(one) for one in (classes or [])]
    class_codes = [one for one in class_codes if one] or [None]
    #: `DEF-RAT-9519` — the same classes decide which taxes the plan's
    #: customers pay; no class ticked reads as every class.
    plan_classes = selectors.class_codes_of_ids(list(classes or []))
    services = []
    for code in seams.enabled_service_codes():
        row = seams.service_catalog_row(code)
        if row is None:
            continue
        services.append(
            {"value": code, "label": row["name"], "gl": _gl(seams.service_revenue_gl_account_id(code))}
        )
    base_ids = list(
        models.Charge.objects.filter(is_base=True, deleted_at__isnull=True, tenant_id=selectors._tenant_id()).values_list("id", flat=True)
    )
    base_dates = _charge_price_dates(base_ids)
    schedules = []
    for tariff in selectors.plan_builder_queryset().order_by("name", "id"):
        version = selectors.in_force_version(tariff, day) or selectors.latest_version(tariff)
        named = version.base_charge_code if version is not None and version.base_charge_code_id else None
        schedules.append(
            {
                "ref": _schedule_with_model(tariff, version, day),
                "service": tariff.service.code,
                "base": _base_block(tariff.service.code, named, class_codes, day, base_dates),
                "minimum": _minimum_block(version),
                "usage": _usage(version),
            }
        )
    charges = list(
        models.Charge.objects.filter(deleted_at__isnull=True, is_base=False, tenant_id=selectors._tenant_id()).order_by("code")
    )
    dates = _charge_price_dates([charge.id for charge in charges])
    names = _class_names()
    default_late = services_default_late_fee()
    charge_rows = []
    deposit_rows = []
    for charge in charges:
        priced_by, rows = _priced_rows(charge, day, names)
        if charge.charge_type == "refundable":
            deposit_rows.append(
                {
                    "ref": charge_ref(charge, KIND_DEPOSIT, day, dates),
                    "priced_by": priced_by,
                    "rows": rows,
                    "gl": _gl(charge.gl_account_id),
                }
            )
            continue
        charge_rows.append(
            {
                "ref": charge_ref(charge, KIND_CHARGE, day, dates),
                "priced_by": priced_by,
                "rows": rows,
                "gl": _gl(charge.gl_account_id),
                "type_label": charge.charge_type,
                "when_label": _WHEN.get(charge.charge_type or "", None),
                "grace": _grace(charge),
                # `DEF-RAT-9328` (§7.6) — the utility's default late-fee code is
                # a VISIBLE, removable row on a new plan; the server never adds
                # it to a body that does not name it.
                "default_on_new_plan": default_late is not None and charge.id == default_late.id,
            }
        )
    taxes = []
    for tax in (
        models.Tax.objects.filter(deleted_at__isnull=True, is_draft=False, tenant_id=selectors._tenant_id())
        .select_related("jurisdiction")
        .order_by("name")
    ):
        if selectors.tax_status(tax, day) != "active":
            continue
        what = [part for part, on_it in (("Usage", tax.base_includes_usage), ("base", tax.base_includes_base)) if on_it]
        taxes.append(
            {
                "ref": tax_ref(tax, day),
                "rate_display": selectors._display_percent(tax.rate)
                if tax.kind == "percent"
                else selectors._display_money(tax.flat_amount),
                "rate_percent": _rate_percent(tax),
                "what_is_taxed_label": (" and ".join(what) + " charges").capitalize() if what else None,
                "what_is_taxed": _taxed_codes(tax),
                "gl": _gl(tax.liability_gl_account_id),
                "authority": (tax.jurisdiction.authority or tax.jurisdiction.name)
                if tax.jurisdiction_id
                else None,
                "brought_by": "attached",
                "reaches_plan_classes": selectors.tax_reach_of_classes(tax, plan_classes),
            }
        )
    discounts = []
    for discount in discount_models.Discount.objects.filter(tenant_id=selectors._tenant_id()).order_by("code"):
        version = selectors.discount_version_in_force(discount, day)
        if version is None:
            continue
        discounts.append(
            {
                "ref": discount_ref(discount, day),
                "value_display": selectors.discount_value_display(
                    version.discount_type,
                    version.value,
                    selectors.discount_allowance_unit(version),
                    version.currency,
                ),
                "gl": _gl(getattr(discount, "gl_account_id", None)),
                "enrolled": selectors.discount_enrolled_count(discount),
                "offered_from": None,
                "offered_until": None,
            }
        )
    return {
        "on": day.isoformat(),
        "currency": seams.tenant_currency(),
        "services": services,
        "schedules": schedules,
        "charge_codes": charge_rows,
        "deposit_codes": deposit_rows,
        "taxes": taxes,
        "discounts": discounts,
        # *Every customer class* is the screen's own first row (ruling 4).
        "customer_classes": [
            {"value": row["id"], "label": row["name"]} for row in seams.customer_class_options()
        ],
    }


def services_default_late_fee() -> Any:
    from apps.rating import services

    return services.default_late_fee_charge()


# ── Audit, in words (images 34–36; `DEF-RAT-9288`'s server half) ───────────
# 🔒 HUMAN-REVIEW-PENDING (`DEF-RAT-9360`, `DEF-RAT-9363`, lane PLAN-FIXES,
# 2026-10-03) — what a correction is said to have changed is read from the
# corrected VERSION's terms; row in `12-governance/09-human-review-ledger.md`.

AUDIT_KINDS = ("plan", "underneath")

#: What a plan-audit row's ACTION means, in the screen's words (ruling 13).
_PLAN_CHANGE = {
    "plan.created": "created",
    "plan.updated": "edited",
    "plan.details_updated": "edited",
    "plan.version_created": "new_version",
    "plan.version_saved": "new_version",
    "plan.version_published": "published",
    "plan.version_corrected": "correction",
    "plan.published": "published",
    "plan.archived": "archived",
}

#: Labels for the leaves a before → after line can name. Anything unlisted is
#: humanised from its key; ids are never shown (B14 rule 31).
_LABELS = {
    "name": "Name",
    "code": "Code",
    "description": "Description",
    "minimum_bill_amount": "Minimum bill",
    "budget_billing": "Budget billing",
    "outside_city_percent": "Outside-city surcharge",
    "effective_from": "Starts",
    "effective_to": "Ends",
    "status": "Status",
    "rate": "Rate",
    "amount": "Amount",
    "value": "Value",
    "unit_price": "Rate",
    "base_charge": "Base charge",
    "percent": "Percent",
    "min_amount": "Minimum",
    # `DEF-RAT-9360` — the plan's list facts by the names the screens use.
    "base_charges": "Base charges",
    "outside_city_percent": "Outside-city surcharge",
    "account_type_ids": "Customer classes",
    "eligibility": "Notes",
    "services": "Services",
    "rate_schedules": "Rate schedules",
    "charge_rules": "Charge codes",
    "deposit_rules": "Deposits",
    "tax_rules": "Taxes",
    "tax_attachments": "Taxes",
    "discounts": "Discounts",
    "late_fee_charge": "Late fee",
    "penalty_rule": "Late fee",
}

_SKIP_KEYS = {
    "id", "version", "version_no", "accounts", "versions", "updated_at", "created_at",
    "outside_city_factor", "outside_city_percent_display", "base_charges_display",
    "base_charges_unavailable", "account_type_id", "tax_lines",
    # `DEF-RAT-9360` / `DEF-RAT-9363` — the REASON has its own column, and the
    # combined rate is derived from the taxes the row already names.
    "reason", "combined_tax_rate_display", "version_terms",
}

#: `DEF-RAT-9360` — a plan's stored status in the words its pill uses.
_STATUS_WORDS = {"draft": "Draft", "published": "Published", "archived": "Archived"}

#: `DEF-RAT-9363` — the four TERMS of a version. On a plan row they mirror the
#: HEAD (`plan_versioning`), so for a correction the corrected VERSION's own
#: copy (`version_terms`) is the truth on both sides.
_TERM_KEYS = ("minimum_bill_amount", "outside_city_factor", "outside_city_percent", "budget_billing", "late_fee_charge")


def _is_uuid(value: Any) -> bool:
    return isinstance(value, str) and selectors._valid_uuid(value)


def _word(key: str, value: Any) -> str:
    """One fact in a clerk's words. ⚠ `DEF-RAT-9360`: money reads WITH its
    currency (`$20.00`, never `20.00` — hard rule 2's display half), an empty
    list reads *None*, and customer classes read by NAME (B14 rule 31)."""
    if value == []:
        return "None"
    if value is None or value == "":
        return "—"
    if key == "status" and isinstance(value, str) and value in _STATUS_WORDS:
        return _STATUS_WORDS[value]
    if key == "account_type_ids" and isinstance(value, list):
        names = seams.account_type_names(value)
        shown = [names.get(str(one)) for one in value if names.get(str(one))]
        return ", ".join(shown) if shown else f"{len(value)} classes"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (float, Decimal)):
        value = str(value)
    if isinstance(value, str):
        if len(value) == 10 and value[4] == "-" and value[7] == "-":
            try:
                return date.fromisoformat(value).strftime("%m/%d/%Y")
            except ValueError:
                return value
        try:
            number = Decimal(value)
        except Exception:  # noqa: BLE001 — not a number: words as stored
            return value
        if "percent" in key:
            return f"{number.quantize(Decimal('0.01'))}%"
        if key == "rate" and number < 1:
            return selectors._display_percent(number) or value
        if any(part in key for part in ("amount", "charge", "price", "bill", "fee", "minimum", "base", "value")):
            return _money_words(number) or value
        return value
    if isinstance(value, list):
        names = [
            str(
                item.get("name")
                or item.get("code")
                or item.get("tariff_name")
                or item.get("jurisdiction")
                or item.get("service")
                or ""
            )
            for item in value
            if isinstance(item, dict)
        ]
        names = [name for name in names if name and not _is_uuid(name)]
        return ", ".join(names) if names else f"{len(value)} items"
    if isinstance(value, dict):
        return str(value.get("name") or value.get("code") or "—")
    return str(value)


def _leaves(blob: Any) -> dict[str, tuple[str, Any]]:
    """`{path: (key, value)}` of a snapshot's TOP-LEVEL facts (a list or an
    object is one fact, worded by its names) — so a line reads *Services:
    Water, Sewer → Water* and never a JSON path."""
    if not isinstance(blob, dict):
        return {}
    return {
        key: (key, value)
        for key, value in blob.items()
        if key not in _SKIP_KEYS and not key.endswith("_id") and not key.endswith("_ids")
    }


def _version_terms_view(blob: Any) -> Any:
    """`DEF-RAT-9363` — a snapshot that carries `version_terms` (a correction's
    before and after) read with the corrected VERSION's terms in place of the
    plan-level columns, which mirror the head and so name a later version's
    figures (v2's $12.00 minimum on a v1 correction). Every other snapshot is
    returned untouched."""
    if not isinstance(blob, dict) or not isinstance(blob.get("version_terms"), dict):
        return blob
    terms = blob["version_terms"]
    out = {key: value for key, value in blob.items() if key not in _TERM_KEYS}
    out["minimum_bill_amount"] = terms.get("minimum_bill_amount")
    factor = terms.get("outside_city_factor")
    out["outside_city_percent"] = selectors._outside_city_percent(Decimal(str(factor))) if factor is not None else None
    out["budget_billing"] = terms.get("budget_billing")
    late = terms.get("late_fee_charge_id")
    if late:
        charge = models.Charge.objects.filter(pk=late, tenant_id=selectors._tenant_id()).values("code", "name").first()
        out["late_fee_charge"] = charge or {"code": "—"}
    else:
        out["late_fee_charge"] = None
    return out


def words_diff(before: Any, after: Any) -> tuple[str | None, str | None]:
    """`(before_display, after_display)` — the changed facts, in words, three at
    most each side (*Minimum bill: $10.00 · Starts: 09/01/2026*)."""
    before, after = _version_terms_view(before), _version_terms_view(after)
    old, new = _leaves(before), _leaves(after)
    changed = [key for key in sorted(set(old) | set(new)) if old.get(key, (key, None))[1] != new.get(key, (key, None))[1]]
    if not changed:
        return None, None

    def _side(source: dict[str, tuple[str, Any]]) -> str:
        parts = []
        for key in changed[:3]:
            label = _LABELS.get(key, key.replace("_", " ").capitalize())
            parts.append(f"{label}: {_word(key, source.get(key, (key, None))[1])}")
        if len(changed) > 3:
            parts.append(f"+{len(changed) - 3} more")
        return " · ".join(parts)

    return (_side(old) if before else None), _side(new)


def _fact(key: str, value: Any) -> dict[str, Any]:
    """One changed fact with the code behind its words (`DEF-RAT-9502`):
    `key` (the screen's catalogue names the field), `kind` and `raw` where the
    VALUE is a product word or a date a screen should show its own way
    (`bool`, `date`, `status`), and `value` — the English words, which are
    the utility's own data for every other kind."""
    label = _LABELS.get(key, key.replace("_", " ").capitalize())
    if value == []:
        # *None* (`DEF-RAT-9360`) is the product's word for an empty list.
        return {"key": key, "label": label, "kind": "none", "raw": None, "value": _word(key, value)}
    if isinstance(value, bool):
        return {"key": key, "label": label, "kind": "bool", "raw": value, "value": _word(key, value)}
    if key == "status" and isinstance(value, str):
        return {"key": key, "label": label, "kind": "status", "raw": value, "value": value}
    if isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-":
        try:
            date.fromisoformat(value)
            return {"key": key, "label": label, "kind": "date", "raw": value, "value": _word(key, value)}
        except ValueError:
            pass
    return {"key": key, "label": label, "kind": "text", "raw": None, "value": _word(key, value)}


def words_facts(before: Any, after: Any) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None, int]:
    """`words_diff` as CODES: `(before_facts, after_facts, more)` — the same
    three changed facts a side, so a screen can word *Starts: 01/01/2027* in
    its own language; `more` is how many changed facts are not listed.
    Reads the same view as `words_diff` (`_version_terms_view`), so the codes
    and the English never describe two different changes."""
    before, after = _version_terms_view(before), _version_terms_view(after)
    old, new = _leaves(before), _leaves(after)
    changed = [key for key in sorted(set(old) | set(new)) if old.get(key, (key, None))[1] != new.get(key, (key, None))[1]]
    if not changed:
        return None, None, 0

    def _side(source: dict[str, tuple[str, Any]]) -> list[dict[str, Any]]:
        return [_fact(key, source.get(key, (key, None))[1]) for key in changed[:3]]

    return (_side(old) if before else None), _side(new), max(0, len(changed) - 3)


def _bound_ids(plan: models.RatePlan) -> dict[str, list[Any]]:
    """Everything this plan binds in ANY of its versions (`all_versions`)."""
    keep = Q(rate_plan=plan)
    tariffs = list(models.PlanRateSchedule.all_versions.filter(keep, tenant_id=selectors._tenant_id()).values_list("tariff_id", flat=True).distinct())
    charges = list(models.PlanChargeRule.all_versions.filter(keep, tenant_id=selectors._tenant_id()).values_list("charge_id", flat=True).distinct())
    late = list(
        models.PlanVersion.objects.filter(rate_plan=plan, late_fee_charge_id__isnull=False, tenant_id=selectors._tenant_id())
        .values_list("late_fee_charge_id", flat=True)
        .distinct()
    )
    if plan.late_fee_charge_id:
        late.append(plan.late_fee_charge_id)
    taxes = list(models.PlanTaxRule.all_versions.filter(keep, tax__isnull=False, tenant_id=selectors._tenant_id()).values_list("tax_id", flat=True))
    jurisdictions = list(models.PlanTaxRule.all_versions.filter(keep, tax__isnull=True, tenant_id=selectors._tenant_id()).values_list("jurisdiction_id", flat=True))
    if jurisdictions:
        taxes += list(models.Tax.objects.filter(jurisdiction_id__in=jurisdictions, tenant_id=selectors._tenant_id()).values_list("id", flat=True))
    if taxes:
        # `DEF-RAT-10033` — a new rate from a date and a correction are NEW
        # rows in the tax's chain (`chain_id`), and the binding names the row it
        # was made on. Without the chain the row carrying *Rate: 2.00% → 6.00%*
        # was never this plan's.
        chains = models.Tax.objects.filter(pk__in=taxes, tenant_id=selectors._tenant_id()).values("chain_id")
        taxes += list(
            models.Tax.objects.filter(chain_id__in=Subquery(chains), tenant_id=selectors._tenant_id()).values_list("id", flat=True)
        )
    discounts = list(discount_models.PlanDiscountRule.all_versions.filter(keep, tenant_id=selectors._tenant_id()).values_list("discount_id", flat=True).distinct())
    discount_versions = list(
        discount_models.DiscountVersion.objects.filter(discount_id__in=discounts, tenant_id=selectors._tenant_id()).values_list("id", flat=True)
    )
    return {
        "schedule": tariffs,
        "charge": list(dict.fromkeys([*charges, *late])),
        "tax": list(dict.fromkeys(taxes)),
        "discount": discounts,
        "discount_version": discount_versions,
    }


def plan_audit_queryset(
    plan_id: Any, kind: str | None = None, date_from: date | None = None, date_to: date | None = None
) -> Any:
    """ONE paged read across the plan's own changes and what moved underneath
    it, NEWEST FIRST — a SQL UNION of `audit_log` (the plan, taxes, discounts)
    and `rate_change_log` (schedules, charge codes), so the count is a SQL
    `COUNT` and the page a `LIMIT` (`NFR-3`). *Underneath* now covers taxes and
    discounts too, through `audit_log` (`DEF-RAT-5738`'s gap)."""
    from django.apps import apps as django_apps
    from django.db.models import F, TextField, Value
    from django.db.models.functions import Cast

    plan = selectors.plan_or_404(plan_id)
    audit_model = django_apps.get_model("audit", "AuditLog")
    tenant = selectors._tenant_id()
    bound = _bound_ids(plan)
    want_plan = kind in (None, "", "all", "plan")
    want_under = kind in (None, "", "all", "underneath")

    audit_q = Q(pk__in=[])
    if want_plan:
        audit_q |= Q(entity_type="rate_plan", entity_id=plan.id)
    if want_under:
        from apps.rating import history_words

        for entity in ("tax", "discount", "discount_version"):
            if bound[entity]:
                # `DEF-RAT-10033` — a new rate or a correction is ONE act written
                # as two rows; the successor's row carries it, worded against
                # its partner's `before` (`history_words.pair_successors`).
                audit_q |= Q(entity_type=entity, entity_id__in=bound[entity]) & ~Q(
                    action__in=history_words.PARTNER_ACTIONS
                )
    rcl_q = Q(pk__in=[])
    if want_under:
        for entity in ("schedule", "charge"):
            if bound[entity]:
                rcl_q |= Q(entity_type=entity, entity_id__in=bound[entity])

    def _window(qs: Any) -> Any:
        if date_from is not None:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to is not None:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    shape = ("_at", "_src", "_rid", "_etype", "_eid", "_act", "_actor", "_before", "_after", "_reason")
    audit_rows = _window(audit_model.objects.filter(tenant_id=tenant).filter(audit_q)).annotate(
        _at=F("created_at"),
        _src=Value("audit", output_field=TextField()),
        _rid=Cast("id", TextField()),
        _etype=F("entity_type"),
        _eid=Cast("entity_id", TextField()),
        _act=F("action"),
        _actor=Cast("actor_user_id", TextField()),
        _before=F("before"),
        _after=F("after"),
        _reason=Value(None, output_field=TextField()),
    ).values(*shape)
    rcl_rows = _window(models.RateChangeLog.objects.filter(tenant_id=tenant).filter(rcl_q)).annotate(
        _at=F("created_at"),
        _src=Value("rate_change", output_field=TextField()),
        _rid=Cast("id", TextField()),
        _etype=F("entity_type"),
        _eid=Cast("entity_id", TextField()),
        _act=Value("rate_change", output_field=TextField()),
        _actor=Cast("actor_id", TextField()),
        _before=F("before"),
        _after=F("after"),
        _reason=F("reason"),
    ).values(*shape)
    return audit_rows.union(rcl_rows, all=True).order_by("-_at", "-_rid")


def _entity_names(rows: list[dict[str, Any]]) -> dict[tuple[str, str], tuple[str, str | None]]:
    """`{(entity_type, id): (kind, name)}` for one page, batched per kind."""
    wanted: dict[str, set[str]] = {}
    for row in rows:
        wanted.setdefault(row["_etype"], set()).add(row["_eid"])
    out: dict[tuple[str, str], tuple[str, str | None]] = {}
    for one in models.RatePlan.objects.filter(pk__in=wanted.get("rate_plan", set()), tenant_id=selectors._tenant_id()):
        out[("rate_plan", str(one.id))] = ("plan", one.name)
    for one in models.Tariff.objects.filter(pk__in=wanted.get("schedule", set()), tenant_id=selectors._tenant_id()):
        out[("schedule", str(one.id))] = ("schedule", one.name)
    for one in models.Charge.objects.filter(pk__in=wanted.get("charge", set()), tenant_id=selectors._tenant_id()):
        out[("charge", str(one.id))] = ("charge_code", f"{one.code} · {one.name}")
    for one in models.Tax.objects.filter(pk__in=wanted.get("tax", set()), tenant_id=selectors._tenant_id()):
        out[("tax", str(one.id))] = ("tax", one.name)
    for one in discount_models.Discount.objects.filter(pk__in=wanted.get("discount", set()), tenant_id=selectors._tenant_id()):
        out[("discount", str(one.id))] = ("discount", f"{one.code} · {one.name}")
    for one in discount_models.DiscountVersion.objects.filter(
        pk__in=wanted.get("discount_version", set()), tenant_id=selectors._tenant_id()
    ).select_related("discount"):
        out[("discount_version", str(one.id))] = (
            "discount",
            f"{one.discount.code} · {one.discount.name}",
        )
    return out


def _change_word(row: dict[str, Any]) -> str:
    if row["_src"] == "rate_change":
        if not row["_before"]:
            return "added"
        return "new_version" if row["_etype"] == "schedule" else "edited"
    action = row["_act"] or ""
    if action in _PLAN_CHANGE:
        return _PLAN_CHANGE[action]
    if action.endswith(".created"):
        return "created"
    if "approved" in action or "published" in action or "activated" in action:
        return "published"
    if "correct" in action:
        return "correction"
    if "removed" in action or "retired" in action or "deactivated" in action:
        return "removed"
    return "edited"


def plan_audit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One page, in words: who (a NAME), what (kind and name), the change, the
    reason, before → after, and the version it produced."""
    if not rows:
        return []
    from apps.rating import history_words

    names = seams.user_display_names([row["_actor"] for row in rows if row["_actor"]])
    entities = _entity_names(rows)
    # `DEF-RAT-10033` (PO 2026-10-09, *"we should show the changes in tax and
    # discount on plan change history"*) — what moved UNDERNEATH the plan, in
    # History's own words (`history_words.change_lists`: names never ids,
    # *Rate: 2.00% → 6.00%*). The plan's own rows keep their facts below.
    under = [row for row in rows if row["_etype"] != "rate_plan"]
    worded = dict(
        zip(
            (row["_rid"] for row in under),
            history_words.change_lists([history_words.entry_of(row) for row in under])[0] if under else [],
            strict=True,
        )
    )
    out = []
    for row in rows:
        after = row["_after"] if isinstance(row["_after"], dict) else {}
        before = row["_before"] if isinstance(row["_before"], dict) else None
        kind, name = entities.get((row["_etype"], row["_eid"]), (row["_etype"], None))
        before_display, after_display = words_diff(before, after)
        before_facts, after_facts, more = words_facts(before, after)
        reason = row["_reason"] or after.get("reason")
        version = None
        if row["_etype"] == "rate_plan" and after.get("version_no") is not None:
            version = {
                "kind": "plan",
                "version": after.get("version_no"),
                "effective_from": after.get("effective_from"),
            }
        elif row["_etype"] == "rate_plan" and after.get("version") is not None:
            # `DEF-RAT-9360` — a row with no `version_no` (a *Name and
            # details* edit, `BR-RAT-1067`: SAME version) carries the plan's
            # HEAD counter, which names v2 while v1 is in force. The version
            # it changed is the one in force on the day it was made.
            day = row["_at"].date() if row["_at"] else None
            # `DEF-RAT-9516` — before the plan's first start, the version it
            # will start with (never the newest, which may not exist yet).
            in_force = plan_versioning.version_on(row["_eid"], _read_day(row["_eid"], day)) if day else None
            version = {
                "kind": "plan",
                "version": in_force.version_no if in_force is not None else after.get("version"),
                "effective_from": _iso(in_force.effective_from) if in_force is not None else after.get("effective_from"),
            }
        elif row["_etype"] == "schedule" and isinstance(after, dict) and after.get("effective_from"):
            version = {"kind": "schedule", "version": None, "effective_from": after.get("effective_from")}
        out.append(
            {
                "id": row["_rid"],
                "at": row["_at"].isoformat() if row["_at"] else None,
                "actor": {"name": names.get(str(row["_actor"])) if row["_actor"] else None},
                "what": {"kind": kind, "name": name},
                "change": _change_word(row),
                "reason": reason,
                "before_display": before_display,
                "after_display": after_display,
                "before_facts": before_facts,
                "after_facts": after_facts,
                "facts_more": more,
                "version": version,
                # `[{field, before, after}]` for a row underneath; `[]` for the
                # plan's own (its facts above say it).
                "changes": worded.get(row["_rid"], []),
            }
        )
    return out


AUDIT_CSV_HEADER = ("When", "Who", "What", "Change", "Reason", "Before", "After")


def plan_audit_csv(plan_id: Any, kind: str | None, date_from: date | None, date_to: date | None) -> Iterable[str]:
    qs = plan_audit_queryset(plan_id, kind, date_from, date_to)
    head = io.StringIO()
    csv.writer(head).writerow(AUDIT_CSV_HEADER)
    yield head.getvalue()
    total = qs.count()
    for start in range(0, total, 500):
        page = plan_audit_rows(list(qs[start : start + 500]))
        out = io.StringIO()
        writer = csv.writer(out)
        for row in page:
            writer.writerow(
                (
                    row["at"],
                    row["actor"]["name"] or "",
                    f"{row['what']['kind']} · {row['what']['name'] or ''}",
                    row["change"],
                    row["reason"] or "",
                    row["before_display"] or "",
                    row["after_display"] or "",
                )
            )
        yield out.getvalue()


def plan_page(params: Any) -> tuple[list[dict[str, Any]], int]:
    """`GET /plans` — today's page (`selectors.plan_page`, SQL-paged) plus the
    §7.3 additions for the plans ON that page (one more read per page row, so
    the cost is bounded by `per`, never by the tenant)."""
    rows, total = selectors.plan_page(params)
    if not rows:
        return rows, total
    plans = list(
        selectors.plan_queryset().filter(pk__in=[row["id"] for row in rows])
    )
    extra = list_additions(plans)
    for row in rows:
        row.update(extra.get(row["id"], {}))
    return rows, total
