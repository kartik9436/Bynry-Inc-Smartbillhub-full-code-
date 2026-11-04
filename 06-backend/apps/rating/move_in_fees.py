# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 P1.12 / P1.16 — the move-in redesign's Fees table
#           (images 41, 43) and its *See full rates* narrowing (image 42).
# Rules:    BR-BIL-007 (a fee is a tenant charge code, never a literal) ·
#           BR-RAT-108 (a code's class list is an INCLUSION list; empty = every
#           class) · BR-RAT-088 (an `is_base` code is the service's base and is
#           never a fee) · BR-RAT-730 (the charge code's own type decides when
#           it bills) · CR-156-BRC10 (ONE price lookup — `charge_prices.
#           price_on_date` — and no direct query of the price table) ·
#           PO 2026-08-19 ruling 1 (*"no plan cannot override prices"*:
#           `plan_charge_rules.amount_override` is never consulted) ·
#           OQ-BIL-12788 CLOSED (a) 2026-10-05 (a move-in fee is never taxed
#           at move-in) · CLAUDE.md rule 1 · rule 2
# Tests:    06-backend/tests/test_cr171_p1_12_move_in_fees.py
# ───────────────────────────────────────────────────────
"""🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — the PRICE of a move-in fee.

AI-authored 2026-10-05 (lane MVI-MONEY, `CR-171-BRC10` P1.12) under the PO
ruling of 2026-08-09; row in `12-governance/09-human-review-ledger.md`
(*"CR-171 MOVE-IN MONEY"*).

WHAT THIS FILE ANSWERS, AND NOTHING ELSE
----------------------------------------
Two questions the move-in's Fees table asks of RATING, because a module never
reads another module's tables (BR-TEN-013) and the price of a charge code is
rating's:

  1. **Which one-time fees does this unit's plan name for this customer?**
     (`plan_move_in_charges`) — the locked *From plan* rows of image 41.
  2. **What does this one code cost this customer?** (`price_code`) — the
     *+ Add fee* row a clerk types a code into (image 43).

Every figure comes from `charge_prices.price_on_date`, the ONE lookup
`CR-156-BRC10` locked every reader onto. Nothing here sums, rounds or taxes.

WHICH CODES COUNT AS A MOVE-IN FEE
----------------------------------
A code the plan names on its **Charges** table (`role="charge"`) whose own
type is **`one_time`** — the charge code decides, never the plan that named it
(BR-RAT-730, `DEF-RAT-5784`). A `penalty` (late fee, NSF) or a `recurring`
code is not something a move-in charges, and an `is_base` code is the
service's base (BR-RAT-088), so none of them is offered. The code must reach
this customer's CLASS (BR-RAT-108) and either be account-level (no service) or
belong to one of the services this move-in starts.

A code PRICED BY SIZE is priced at the connection's recorded size for its
service; where no size is recorded the row comes back UNPRICED with rating's
own refusal name, never at a guessed size. A `per_case` code comes back with
no amount: the clerk types it (`DEF-RAT-8753`). A `percent` code needs a basis
a move-in does not have and comes back unpriced, named.

⚠ **NO TAX IS DECIDED HERE, AND NONE IS OWED.** `OQ-BIL-12788` was CLOSED by
the PO on 2026-10-05, option (a), verbatim: *"this si correct - a (recommended)
$25.00 (never taxed at move-in)"*. A move-in fee is never taxed at move-in,
whether taken today or added to the first bill. So the answers below carry
`taxed_at_move_in: False` on every row and no tax figure at all — the code's
own `taxable_default` is deliberately NOT forwarded, because on this screen it
would read as *"this fee will be taxed"*, which the ruling says it will not.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Mapping

from apps.rating import charge_prices, models, seams
from core import errors
from core import tenancy as core_tenancy

#: The one charge type a move-in fee may have (BR-RAT-730 — the code decides).
ONE_TIME = "one_time"
#: How a fee row's figure was found — the screen's *From* reads these.
PRICED_FLAT = "flat"
PRICED_BY_SIZE = "size"
PRICED_PER_CASE = "per_case"
PRICED_PERCENT = "percent"

#: Refusals that are this module's own, beside `charge_prices`' four.
NOT_ONE_TIME = "not_a_one_time_code"
NOT_FOR_CLASS = "not_for_this_class"
UNKNOWN_CODE = "unknown_code"
PERCENT_HAS_NO_BASIS = "percent_has_no_basis"

MONEY_PLACES = Decimal("0.0001")


def _tenant_id() -> Any:
    """Tenant scope, explicit on every query (CLAUDE.md rule 1)."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _money(value: Any) -> str | None:
    """Four places as a STRING (hard rule 2) — never a float."""
    if value is None:
        return None
    return str(Decimal(str(value)).quantize(MONEY_PLACES))


def _reaches_class(charge: models.Charge, customer_class: str | None) -> bool:
    """BR-RAT-108: NULL or `[]` is every class; otherwise an inclusion list."""
    classes = [str(code) for code in (charge.applies_to_customer_classes or [])]
    return not classes or (customer_class is not None and customer_class in classes)


def _priced(
    charge: models.Charge,
    *,
    customer_class: str | None,
    size_by_service: Mapping[str, str | None],
    on_date: date,
) -> dict[str, Any]:
    """One code's row: identity, how it is priced and the figure — or a name."""
    service = charge.service.code if charge.service_id else None
    rule = charge.amount_rule or "flat"
    row: dict[str, Any] = {
        "charge_id": str(charge.id),
        "code": charge.code,
        "name": charge.name,
        "service": service,
        "charge_type": charge.charge_type,
        "amount_rule": rule,
        "gl_account_id": str(charge.gl_account_id) if charge.gl_account_id else None,
        "amount": None,
        "priced_by": None,
        "size_class": None,
        "refusal": None,
        # OQ-BIL-12788 (a) — see the module docstring. Constant, and stated.
        "taxed_at_move_in": False,
    }
    if rule == "per_case":
        row["priced_by"] = PRICED_PER_CASE
        # 🔒 HUMAN-REVIEW-PENDING · DEF-RAT-9807 (`BR-RAT-1054` AMENDED) — optional
        # default, which the Fees row's amount box starts at. `amount` stays
        # None: the clerk's typed figure is what Complete writes.
        row["default_amount"] = _money(
            charge_prices.flat_amount(charge, on_date, customer_class)
        )
        return row
    if rule != "flat":
        row["priced_by"] = PRICED_PERCENT
        row["refusal"] = PERCENT_HAS_NO_BASIS
        return row
    size = size_by_service.get(service) if service is not None else None
    answer = charge_prices.price_on_date(
        charge, size_class=size, customer_class=customer_class, on_date=on_date
    )
    row["priced_by"] = PRICED_BY_SIZE if answer.per_size else PRICED_FLAT
    row["size_class"] = answer.size_class if answer.per_size else None
    row["refusal"] = answer.refusal
    row["amount"] = _money(answer.amount) if answer.refusal is None else None
    return row


def plan_move_in_charges(
    plan_id: Any,
    *,
    customer_class: str | None,
    size_by_service: Mapping[str, str | None] | None = None,
    services: Iterable[str] | None = None,
    on_date: date | None = None,
) -> list[dict[str, Any]]:
    """The plan's one-time fees for THIS customer, priced — image 41's locked
    *From plan* rows, in code order.

    `size_by_service` — `{service_code: size_class | None}`, the connection's
    recorded size per service (metering's `connection_size_for`); `services` —
    the services this move-in starts (an account-level code always counts).
    Both are the CALLER's facts: rating knows neither a unit nor an account.

    Empty when the plan names no such code, or `plan_id` is not this tenant's.
    """
    if not plan_id:
        return []
    day = on_date or seams.tenant_today()
    started = set(services) if services is not None else None
    sizes = dict(size_by_service or {})
    rules = (
        models.PlanChargeRule.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id=plan_id, role="charge"
        )
        .select_related("charge", "charge__service")
        .order_by("charge__code")
    )
    out: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for rule in rules:
        charge = rule.charge
        if charge.id in seen or charge.deleted_at is not None or charge.is_base:
            continue
        if (charge.charge_type or "") != ONE_TIME:
            continue
        if not _reaches_class(charge, customer_class):
            continue
        service = charge.service.code if charge.service_id else None
        if service is not None and started is not None and service not in started:
            continue
        seen.add(charge.id)
        out.append(
            _priced(charge, customer_class=customer_class, size_by_service=sizes, on_date=day)
        )
    return out


def price_code(
    code: str,
    *,
    customer_class: str | None,
    size_by_service: Mapping[str, str | None] | None = None,
    on_date: date | None = None,
) -> dict[str, Any]:
    """Any ONE live code of this tenant, priced for this customer — the
    *+ Add fee* row. Never None: an unusable code comes back with `refusal`
    set (`unknown_code`, `not_a_one_time_code`, `not_for_this_class`, or one of
    `charge_prices`' names) so the screen and the commit refuse it BY NAME."""
    day = on_date or seams.tenant_today()
    text = str(code or "").strip()
    charge = (
        models.Charge.objects.filter(tenant_id=_tenant_id(), code=text, deleted_at__isnull=True)
        .select_related("service")
        .first()
        if text
        else None
    )
    if charge is None:
        return {"code": text, "amount": None, "refusal": UNKNOWN_CODE, "taxed_at_move_in": False}
    row = _priced(
        charge,
        customer_class=customer_class,
        size_by_service=dict(size_by_service or {}),
        on_date=day,
    )
    if charge.is_base or (charge.charge_type or "") != ONE_TIME:
        row.update(amount=None, refusal=NOT_ONE_TIME)
    elif not _reaches_class(charge, customer_class):
        row.update(amount=None, refusal=NOT_FOR_CLASS)
    return row


# ═══════════════════════════════════════════════════════════════════════════
# P1.16 — *See full rates*, narrowed to THIS move-in (image 42)
# ═══════════════════════════════════════════════════════════════════════════
def _class_reaches(classes: Iterable[Any] | None, customer_class: str | None) -> bool:
    wanted = {str(code).strip().lower() for code in (classes or [])}
    return not wanted or (customer_class is not None and customer_class.strip().lower() in wanted)


def narrowed_sections(
    plan_id: Any,
    *,
    customer_class: str | None,
    size_by_service: Mapping[str, str | None] | None = None,
    services: Iterable[str] | None = None,
    on_date: date | None = None,
) -> dict[str, Any]:
    """The plan's shared sections (`plan_reads.plan_sections`, the read
    `PlanSections.tsx` draws — CR-167's one component) NARROWED to what this
    move-in will actually be billed. PO, mock-up v11: *"we dont have to show all
    the base and usage rates only mathichg one we should show"*.

    Narrowed, never recomputed — every figure is the shared read's own string:

    * **services** — only the ones this move-in starts; each base and minimum
      table keeps the row for THIS connection's size (all rows where no size is
      recorded, so the clerk sees the choice rather than a guess) and the rows
      for this class or every class;
    * **charge codes** — only those that reach this class (BR-RAT-108);
    * **taxes** — only those that reach this class (`tax_reach_of_classes`,
      the bill's own class gate), and each says `move_in_fees_taxed: False`:
      `OQ-BIL-12788` (a) — a move-in fee is never taxed at move-in, so this
      block no longer lists a fee among what a tax applies to;
    * **deposits** and **discounts** — forwarded (the deposit FIGURE for this
      class is customers' `deposit.standard_for_unit`, served beside this);
    * **claimable_discounts** — the discounts a clerk may CLAIM: the plan's,
      less every AUTOMATIC one (`DEF-CUS-9779`), read from the stored
      `enrolment_mode` — since 2026-10-06 (`DEF-RAT-9833`, PO D2 (b)) less
      only the ones no person may add (`hand_refused_discount_ids`), with
      `pairs_with` naming the setting an Autopay/Paperless row switches On.

    Unit prices read at up to four places (`DEF-RAT-9708`).
    """
    from apps.rating import plan_reads, selectors

    sections = plan_reads.plan_sections(plan_id, on_date)
    started = set(services) if services is not None else None
    sizes = dict(size_by_service or {})

    def keep_row(row: dict[str, Any], service: str) -> bool:
        size = sizes.get(service)
        if size is not None and row.get("size_class") not in (None, size):
            return False
        row_class = row.get("customer_class")
        return row_class is None or customer_class is None or row_class == customer_class

    narrowed_services = []
    for line in sections.get("services") or []:
        service = line.get("service")
        if started is not None and service not in started:
            continue
        base = dict(line.get("base") or {})
        base["by_size"] = [row for row in base.get("by_size") or [] if keep_row(row, service)]
        minimum = dict(line.get("minimum") or {})
        minimum["by_size"] = [
            row for row in minimum.get("by_size") or [] if keep_row(row, service)
        ]
        narrowed_services.append(
            {**line, "base": base, "minimum": minimum, "size_class": sizes.get(service)}
        )

    charge_ids = [
        (row.get("ref") or {}).get("id") for row in sections.get("charge_codes") or []
    ]
    classes_of = {
        str(charge.id): charge.applies_to_customer_classes
        for charge in models.Charge.objects.filter(
            tenant_id=_tenant_id(), id__in=[one for one in charge_ids if one]
        )
    }
    charges = [
        row
        for row in sections.get("charge_codes") or []
        if _class_reaches(classes_of.get(str((row.get("ref") or {}).get("id"))), customer_class)
    ]

    tax_ids = [(row.get("ref") or {}).get("id") for row in sections.get("taxes") or []]
    taxes_by_id = {
        str(tax.id): tax
        for tax in models.Tax.objects.filter(
            tenant_id=_tenant_id(), id__in=[one for one in tax_ids if one]
        )
    }
    taxes = []
    for row in sections.get("taxes") or []:
        tax = taxes_by_id.get(str((row.get("ref") or {}).get("id")))
        classes = [customer_class] if customer_class else None
        if tax is not None and selectors.tax_reach_of_classes(tax, classes) == "none":
            continue
        taxes.append({**row, "move_in_fees_taxed": False})

    # DEF-CUS-9779 — the Billing step's *Discounts to claim* lists only what a
    # person applies for. An AUTOMATIC discount (Municipal account, Paperless,
    # Autopay) is granted and ended by the nightly sync from the account's own
    # facts, so a clerk's claim of one was ended the next night. `discounts`
    # stays whole: the plan panel shows every discount the plan carries.
    from apps.rating import discount_services

    #
    # ⚖️ AMENDED 2026-10-06 (`DEF-RAT-9833`) — PO D2 (b), verbatim: *"Offer
    # Autopay and Paperless at move-in as drawn … Clark has to add those
    # discounts"*. The list now drops only what NO PERSON may add
    # (`hand_refused_discount_ids` — Municipal account, *Everyone on the
    # plan*); Autopay and Paperless are offered again, each row carrying
    # `pairs_with` (`autopay` / `paperless`) so the step switches that
    # preference On when the clerk picks it (ruling 4, reading (b)).
    discount_rows = sections.get("discounts") or []
    ids = [(row.get("ref") or {}).get("id") for row in discount_rows]
    day = on_date or seams.tenant_today()
    refused = discount_services.hand_refused_discount_ids(ids, day)
    paired = discount_services.setting_paired_discount_ids(ids, day)
    claimable = [
        {**row, "pairs_with": paired.get(str((row.get("ref") or {}).get("id")))}
        for row in discount_rows
        if str((row.get("ref") or {}).get("id")) not in refused
    ]

    return {
        **sections,
        "services": narrowed_services,
        # DEF-RAT-9738 — the Plan panel's *Base charge* is the base of the
        # services THIS move-in starts: the shared read's own `_base_total`,
        # run over the narrowed lines (Water only → $8.00, not the plan's
        # $20.00). Same function, same strings; nothing recomputed by hand.
        "base_total": plan_reads._base_total(narrowed_services),
        "charge_codes": charges,
        "taxes": taxes,
        "claimable_discounts": claimable,
        "narrowed_to": {
            "customer_class": customer_class,
            "services": sorted(started) if started is not None else None,
            "sizes": sizes,
        },
    }
