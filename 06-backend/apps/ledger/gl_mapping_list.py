# ── Trace ──────────────────────────────────────────────
# CR:       CR-197-BRC10 (GL mapping becomes one list) — design source: the
#           claude.ai artifact https://claude.ai/artifact/Ue5p1oSzgQquUva1KZjf8Y v4
# Rules:    BR-LED-800 (one list, two groups, eleven types) · BR-LED-801 (class
#           revenue) · BR-LED-802 (Disable scope; new bills and payments only) ·
#           BR-LED-803 (refund account) · BR-LED-014 · BR-BIL-010 · NFR-3 ·
#           CLAUDE.md rules 1, 4, 7 · B14 rule 31 (no id on screen)
# Tests:    06-backend/tests/test_cr197_gl_mapping_list.py
# ───────────────────────────────────────────────────────
"""**THE ONE GL MAPPING LIST** — every place a bill line or a payment lands, as
rows, with add, edit, disable and enable.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — every act here re-points where money lands
(🔒 GL resolution). AI-authored 2026-10-29 under the PO ruling of 2026-08-09;
row in `12-governance/09-human-review-ledger.md`.

════════════════════════════════════════════════════════════════════════════
WHAT THE PO RULED (decision log 2026-10-29, four entries)
════════════════════════════════════════════════════════════════════════════
*"we neeed to create one single tabl on list view ; we should allow to user to
add, edit, update, disable"* — Q1–Q4 all **A**: Disable stops new use and keeps
history, only for charge, adjustment and discount rows · Add maps EXISTING items
only · a changed account applies to new bills and payments only · the four tabs
stay. Then the types *"based on Accounting practices"*: Billing (service revenue
with an optional customer-class split · charge code · discount · tax ·
adjustment) and Payments & balances (bill payment per way of paying · deposit ·
refund · write-off · other payments · system accounts, edit-only).

════════════════════════════════════════════════════════════════════════════
WHO WRITES WHAT — nothing here writes another module's row
════════════════════════════════════════════════════════════════════════════
  * service every-class account → TENANCY (`tenancy_seam.set_service_gl_accounts`)
  * class override               → THE LEDGER (`ServiceClassRevenueAccount`)
  * charge code · discount · tax → RATING (`gl_mapping_seams` → rating's own acts)
  * adjustment · way of paying   → TENANCY (its lookup handlers)
  * deposit · refund · write-off · other payments · system → THE LEDGER
    (a designation on a chart row, `services.update_account`)

════════════════════════════════════════════════════════════════════════════
⚠ PAGED ON THE SERVER, FILTERED IN PYTHON — AND WHY THAT IS NOT AN NFR-3 BREACH
════════════════════════════════════════════════════════════════════════════
The rows come from six tables in four modules, so no single SQL query can cut
the page. They are assembled, filtered and sliced here, and only the page goes
over the wire. The set is bounded by the tenant's CONFIGURATION — services ×
two parts × the class overrides it chose, its charge codes, reasons, tenders —
never by customers or transactions, the same reason the chart list is
(`chart_api` exception 4). No cap is added anywhere (NFR-5).

⚠ **A CHANGED ACCOUNT APPLIES TO NEW BILLS AND PAYMENTS ONLY, AND NOTHING HERE
HAS TO DO ANYTHING TO MAKE THAT TRUE.** Every issued bill line carries its
`gl_account_id`, stamped at issue and frozen by hard rule 4; every posted
journal line names its account. This module only ever moves POINTERS, which
are read at the next issue or posting. The test asserts it rather than this
comment (BR-LED-802).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import transaction

from apps.ledger import chart, gl_mapping_seams as seams, models, selectors, services, tenancy_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.pagination import ListParams, filter_values

GROUP_BILLING = "billing"
GROUP_PAYMENTS = "payments"

SERVICE_REVENUE = "service_revenue"
CHARGE_CODE = "charge_code"
DISCOUNT = "discount"
TAX = "tax"
ADJUSTMENT = "adjustment"
BILL_PAYMENT = "bill_payment"
DEPOSIT = "deposit"
REFUND = "refund"
WRITE_OFF = "write_off"
OTHER_PAYMENTS = "other_payments"
SYSTEM_ACCOUNT = "system_account"

#: The two groups and their types, in the order the list and the Add form read.
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (GROUP_BILLING, (SERVICE_REVENUE, CHARGE_CODE, DISCOUNT, TAX, ADJUSTMENT)),
    (
        GROUP_PAYMENTS,
        (BILL_PAYMENT, DEPOSIT, REFUND, WRITE_OFF, OTHER_PAYMENTS, SYSTEM_ACCOUNT),
    ),
)
TYPES: tuple[str, ...] = tuple(t for _g, ts in GROUPS for t in ts)
GROUP_OF = {t: g for g, ts in GROUPS for t in ts}
TYPE_ORDER = {t: i for i, t in enumerate(TYPES)}

STATUS_MAPPED = "mapped"
STATUS_NOT_MAPPED = "not_mapped"
STATUS_DISABLED = "disabled"
STATUSES = (STATUS_MAPPED, STATUS_NOT_MAPPED, STATUS_DISABLED)

#: BR-LED-800 — the kinds of account each type may point at.
KINDS: dict[str, tuple[str, ...]] = {
    SERVICE_REVENUE: ("revenue",),
    CHARGE_CODE: ("revenue",),
    DISCOUNT: ("contra_revenue",),
    TAX: ("liability",),
    ADJUSTMENT: ("contra_revenue", "revenue"),
    BILL_PAYMENT: ("asset",),
}

#: The designation rows: (type, designation, mapped-for words, detail words, kinds).
#: The words are the server's own for SEARCH; the screen shows its catalogue's
#: words through `mapped_for_key` / `detail_key`.
DESIGNATION_ROWS: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    (DEPOSIT, chart.DEPOSIT_LIABILITY, "Deposits held", "Customer's money held", ("liability",)),
    (
        DEPOSIT,
        chart.DEPOSIT_INTEREST_EXPENSE,
        "Deposit interest",
        "Interest paid on deposits",
        ("expense",),
    ),
    (
        REFUND,
        chart.REFUNDS_PAYABLE,
        "Refunds paid",
        "Credit balance or deposit paid back",
        ("liability", "asset"),
    ),
    (WRITE_OFF, chart.WRITE_OFF, "Bad debt", "Balance written off", ("expense",)),
    (
        WRITE_OFF,
        chart.ALLOWANCE_DOUBTFUL_ACCOUNTS,
        "Allowance",
        "Used when the allowance is on",
        ("asset",),
    ),
    (
        OTHER_PAYMENTS,
        chart.CUSTOMER_CREDIT_BALANCE,
        "Unapplied and overpaid",
        "Payments not matched to a bill",
        ("liability",),
    ),
    (SYSTEM_ACCOUNT, chart.AR, "Receivables", "Accounts receivable", ("asset",)),
    (SYSTEM_ACCOUNT, chart.CASH, "Bank", "Money in the bank", ("asset",)),
    (SYSTEM_ACCOUNT, chart.UNDEPOSITED_FUNDS, "Not banked", "Taken but not yet banked", ("asset",)),
)

PARTS = models.REVENUE_PARTS
AUDIT_PREFIX = "gl_mapping"


@dataclass
class Row:
    key: str
    type: str
    mapped_for: str
    detail: str | None
    account_id: str | None
    active: bool = True
    can_disable: bool = False
    can_enable: bool = False
    kinds: tuple[str, ...] = ()
    mapped_for_key: str | None = None
    detail_key: str | None = None
    detail_params: dict[str, Any] | None = None
    addable: bool = True  # may appear in the Add form when not mapped
    #: Order WITHIN one mapped-for name: a service reads Usage before Base, and
    #: the every-class row before its class rows (the drawing's order).
    order: tuple = ()
    exists: bool = True  # False for a class combination with no override yet


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _live_accounts() -> dict[str, dict[str, Any]]:
    return {
        row["account_id"]: row
        for row in services.chart_of_accounts(status="active")["rows"]
    }


def _class_labels() -> dict[str, str]:
    return {str(o["value"]): str(o["label"]) for o in seams.customer_classes()}


# ═══════════════════════════════════════════════════════════════════════════
# THE ROWS
# ═══════════════════════════════════════════════════════════════════════════
def _service_rows(classes: dict[str, str]) -> list[Row]:
    names = seams.service_names()
    rows: list[Row] = []
    try:
        codes = tenancy_seam.enabled_service_codes()
    except tenancy_seam.LedgerSeamNotWired as unwired:  # pragma: no cover — defensive
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-TEN-013", message_key="ledger.glMapping.ownerUnreachable",
            params={"owner": "tenancy"},
        ) from unwired
    overrides = list(
        models.ServiceClassRevenueAccount.objects.filter(tenant_id=_tenant_id()).values_list(
            "service_code", "part", "customer_class", "ledger_account_id"
        )
    )
    held = {(code, part, cls) for code, part, cls, _a in overrides}
    for code in codes:
        name = names.get(code) or code
        attributes = tenancy_seam.service_gl_attributes(code) or {}
        usage = attributes.get("revenue_account_id")
        base = attributes.get("base_revenue_account_id") or usage
        for part, account in (("usage", usage), ("base", base)):
            rows.append(
                Row(
                    key=f"svc:{code}:{part}:*",
                    type=SERVICE_REVENUE,
                    mapped_for=name,
                    detail=f"{part.title()} · All classes",
                    detail_key=f"glMapping.detail.{part}",
                    detail_params={"cls": None},
                    order=(PARTS.index(part), 0, ""),
                    account_id=str(account) if account else None,
                    kinds=KINDS[SERVICE_REVENUE],
                )
            )
            # The class combinations with NO override yet are offered by the
            # Add form only (`exists=False`); they are not rows of the list,
            # because an absent override is not a gap — the bill falls back.
            for cls, label in classes.items():
                if (code, part, cls) in held:
                    continue
                rows.append(
                    Row(
                        key=f"svc:{code}:{part}:{cls}",
                        type=SERVICE_REVENUE,
                        mapped_for=name,
                        detail=f"{part.title()} · {label}",
                        detail_key=f"glMapping.detail.{part}",
                        detail_params={"cls": label},
                        order=(PARTS.index(part), 1, label.lower()),
                        account_id=None,
                        kinds=KINDS[SERVICE_REVENUE],
                        exists=False,
                    )
                )
    for code, part, cls, account in overrides:
        label = classes.get(cls) or cls
        rows.append(
            Row(
                key=f"svc:{code}:{part}:{cls}",
                type=SERVICE_REVENUE,
                mapped_for=names.get(code) or code,
                detail=f"{part.title()} · {label}",
                detail_key=f"glMapping.detail.{part}",
                detail_params={"cls": label},
                order=(PARTS.index(part), 1, label.lower()),
                account_id=str(account),
                can_disable=True,
                kinds=KINDS[SERVICE_REVENUE],
            )
        )
    return rows


def _item_rows() -> list[Row]:
    rows: list[Row] = []
    for item in seams.charges():
        rows.append(
            Row(
                key=f"chg:{item['id']}",
                type=CHARGE_CODE,
                mapped_for=item["code"],
                detail=item["name"],
                detail_key=f"glMapping.detail.{item['kind']}Charge",
                detail_params={"name": item["name"]},
                account_id=item["gl_account_id"],
                active=item["active"],
                can_disable=item["active"],
                can_enable=not item["active"],
                kinds=KINDS[CHARGE_CODE],
            )
        )
    for item in seams.discounts():
        rows.append(
            Row(
                key=f"dsc:{item['id']}",
                type=DISCOUNT,
                mapped_for=item["code"],
                detail=item["name"],
                account_id=item["gl_account_id"],
                active=item["active"],
                can_disable=item["active"],
                can_enable=False,  # a retirement has no undo (BR-LED-802)
                kinds=KINDS[DISCOUNT],
            )
        )
    for item in seams.taxes():
        rows.append(
            Row(
                key=f"tax:{item['id']}",
                type=TAX,
                mapped_for=item["authority"],
                detail=item["name"],
                account_id=item["gl_account_id"],
                active=item["active"],
                kinds=KINDS[TAX],
            )
        )
    for item in seams.reasons():
        rows.append(
            Row(
                key=f"adj:{item['id']}",
                type=ADJUSTMENT,
                mapped_for=item["code"],
                detail=item["name"],
                account_id=item["gl_account_id"],
                active=item["active"],
                can_disable=item["active"],
                can_enable=not item["active"],
                kinds=KINDS[ADJUSTMENT],
            )
        )
    for item in seams.tenders():
        rows.append(
            Row(
                key=f"pay:{item['id']}",
                type=BILL_PAYMENT,
                mapped_for=item["name"],
                detail="Waits here until the bank confirms",
                detail_key="glMapping.detail.waitsForBank",
                account_id=item["gl_account_id"],
                kinds=KINDS[BILL_PAYMENT],
            )
        )
    return rows


def _designation_rows() -> list[Row]:
    held = selectors.designation_map()
    rows = []
    for type_, designation, mapped_for, detail, kinds in DESIGNATION_ROWS:
        account = held.get(designation)
        rows.append(
            Row(
                key=f"des:{designation}",
                type=type_,
                mapped_for=mapped_for,
                detail=detail,
                mapped_for_key=f"glMapping.for.{designation}",
                detail_key=f"glMapping.about.{designation}",
                account_id=str(account) if account else None,
                kinds=kinds,
                addable=type_ != SYSTEM_ACCOUNT,
            )
        )
    return rows


def all_rows(*, include_combinations: bool = False) -> list[Row]:
    """Every row, in list order. `include_combinations` adds the class
    combinations with no override yet — for the Add form only."""
    classes = _class_labels()
    rows = _service_rows(classes) + _item_rows() + _designation_rows()
    if not include_combinations:
        rows = [row for row in rows if row.exists]
    rows.sort(
        key=lambda r: (TYPE_ORDER[r.type], r.mapped_for.lower(), r.order, (r.detail or "").lower(), r.key)
    )
    return rows


def _status(row: Row, live: dict[str, dict[str, Any]]) -> str:
    if not row.active:
        return STATUS_DISABLED
    return STATUS_MAPPED if row.account_id and row.account_id in live else STATUS_NOT_MAPPED


def _account(row: Row, live: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    found = live.get(row.account_id or "")
    if found is None:
        return None
    return {"id": found["account_id"], "code": found["code"], "name": found["name"]}


def _wire(row: Row, live: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "key": row.key,
        "group": GROUP_OF[row.type],
        "type": row.type,
        "mapped_for": row.mapped_for,
        "mapped_for_key": row.mapped_for_key,
        "detail": row.detail,
        "detail_key": row.detail_key,
        "detail_params": row.detail_params or {},
        "account": _account(row, live),
        "status": _status(row, live),
        "can_disable": row.can_disable,
        "can_enable": row.can_enable,
        "kinds": list(row.kinds),
    }


def _matches(row: dict[str, Any], term: str) -> bool:
    account = row["account"] or {}
    haystack = " ".join(
        str(part or "")
        for part in (row["mapped_for"], row["detail"], account.get("code"), account.get("name"))
    ).lower()
    return term in haystack


LIST_FILTERS = ("type", "status", "gl_account")


def list_page(params: ListParams) -> dict[str, Any]:
    """`GET /ledger/gl-mappings/rows` — one page, the counts, and the facets."""
    live = _live_accounts()
    every = [_wire(row, live) for row in all_rows()]
    types = set(filter_values(params.filters.get("type")))
    statuses = set(filter_values(params.filters.get("status")))
    accounts = set(filter_values(params.filters.get("gl_account")))
    term = params.q.strip().lower()
    chosen = [
        row
        for row in every
        if (not types or row["type"] in types)
        and (not statuses or row["status"] in statuses)
        and (not accounts or (row["account"] or {}).get("id") in accounts)
        and (not term or _matches(row, term))
    ]
    per = params.per
    pages = max(1, -(-len(chosen) // per))
    page = min(max(params.page, 1), pages)
    start = (page - 1) * per
    used: dict[str, dict[str, Any]] = {}
    for row in every:
        if row["account"]:
            used.setdefault(row["account"]["id"], row["account"])
    return {
        "count": len(chosen),
        "page": page,
        "per": per,
        "results": chosen[start : start + per],
        "counts": {
            "total": len(every),
            "not_mapped": sum(1 for row in every if row["status"] == STATUS_NOT_MAPPED),
            "disabled": sum(1 for row in every if row["status"] == STATUS_DISABLED),
        },
        "groups": [{"group": g, "types": list(ts)} for g, ts in GROUPS],
        "gl_accounts": sorted(used.values(), key=lambda a: (a["code"], a["id"])),
    }


def add_options(type_: str | None = None) -> dict[str, Any]:
    """The Add form: per type, how many items still have no account; and for
    one type, those items and the accounts it may point at."""
    live = _live_accounts()
    rows = all_rows(include_combinations=True)
    open_rows = [
        row
        for row in rows
        if row.active and row.addable and _status(row, live) == STATUS_NOT_MAPPED
    ]
    types = [
        {"type": t, "group": GROUP_OF[t], "open": sum(1 for r in open_rows if r.type == t)}
        for t in TYPES
    ]
    out: dict[str, Any] = {"types": types}
    if type_:
        if type_ not in TYPES:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP, message_key="ledger.glMapping.unknownType"
            )
        out["items"] = [_wire(row, live) for row in open_rows if row.type == type_]
        out["accounts"] = accounts_for(KINDS.get(type_) or _designation_kinds(type_), live)
    return out


def _designation_kinds(type_: str) -> tuple[str, ...]:
    kinds: list[str] = []
    for t, _d, _f, _a, ks in DESIGNATION_ROWS:
        if t == type_:
            kinds.extend(k for k in ks if k not in kinds)
    return tuple(kinds)


def accounts_for(kinds: tuple[str, ...], live: dict[str, dict[str, Any]] | None = None) -> list:
    live = live if live is not None else _live_accounts()
    return [
        {"id": row["account_id"], "code": row["code"], "name": row["name"], "type": row["type"]}
        for row in sorted(live.values(), key=lambda r: (r["code"], r["account_id"]))
        if row["type"] in kinds
    ]


def edit_options(key: str) -> dict[str, Any]:
    live = _live_accounts()
    row = _find(key, include_combinations=False)
    return {"row": _wire(row, live), "accounts": accounts_for(row.kinds, live)}


# ═══════════════════════════════════════════════════════════════════════════
# THE ACTS
# ═══════════════════════════════════════════════════════════════════════════
def _find(key: str, *, include_combinations: bool) -> Row:
    for row in all_rows(include_combinations=include_combinations):
        if row.key == key:
            return row
    raise errors.NotFoundError()


def _entity_id(row: Row, before: Any, after: Any) -> str:
    """The first of: the account after, the account before, the item's own id
    (an unmapped charge being disabled has no account at all)."""
    for candidate in (after, before, row.key.partition(":")[2]):
        try:
            return str(UUID(str(candidate)))
        except (TypeError, ValueError):
            continue
    return str(_tenant_id())  # a role row with no account: the tenant is the subject


def _audit(actor: Any, act: str, row: Row, before: Any, after: Any) -> None:
    """Hard rule 7. ⚠ `audit_log.entity_id` IS A UUID COLUMN (`DEF-LED-10661`):
    the row's KEY (`dsc:<uuid>`) is not one, and naming it there made every act
    a 500 on the running server while the suite's capture sink accepted it. The
    entity is the ACCOUNT the act is about (the new one, or the one let go);
    the row's key and type travel in `before`/`after`."""
    core_audit.money_action(
        actor,
        f"{AUDIT_PREFIX}.{act}",
        "gl_mapping",
        _entity_id(row, before, after),
        before={"key": row.key, "type": row.type, "account_id": before},
        after={"key": row.key, "type": row.type, "account_id": after},
    )


def _clean_account(row: Row, account_id: Any) -> str:
    live = _live_accounts()
    text = str(account_id or "").strip()
    account = live.get(text)
    if account is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="ledger.glMapping.accountNotLive",
            field_errors=[{"field": "account_id", "code": errors.VAL_UNKNOWN_LOOKUP,
                           "message_key": "ledger.glMapping.accountNotLive"}],
        )
    if account["type"] not in row.kinds:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.glMapping.wrongKind",
            field_errors=[{"field": "account_id", "code": errors.VAL_FORMAT,
                           "message_key": "ledger.glMapping.wrongKind"}],
        )
    return text


def _point(actor: Any, row: Row, account_id: str) -> None:
    """Re-point ONE row, through the module that owns it."""
    prefix, _, rest = row.key.partition(":")
    if prefix == "svc":
        code, part, cls = rest.split(":", 2)
        if cls == "*":
            field = "revenue_account_id" if part == "usage" else "base_revenue_account_id"
            tenancy_seam.set_service_gl_accounts(actor, code, {field: account_id})
            return
        obj, created = models.ServiceClassRevenueAccount.objects.get_or_create(
            tenant_id=_tenant_id(),
            service_code=code,
            part=part,
            customer_class=cls,
            defaults={"ledger_account_id": account_id,
                      "created_by_user_id": getattr(actor, "id", None)},
        )
        if not created:
            obj.ledger_account_id = account_id
            obj.save(update_fields=["ledger_account", "updated_at"])
        return
    writer = {
        "chg": seams.set_charge_gl_account,
        "dsc": seams.set_discount_gl_account,
        "tax": seams.set_tax_gl_account,
        "adj": seams.set_reason_gl_account,
        "pay": seams.set_tender_gl_account,
    }.get(prefix)
    if writer is not None:
        writer(actor, rest, account_id)
        return
    if prefix == "des":
        _point_designation(actor, rest, account_id)
        return
    raise errors.NotFoundError()  # pragma: no cover — every key has a prefix above


def _point_designation(actor: Any, designation: str, account_id: str) -> None:
    """Move a ROLE to another chart row: the old holder lets go first, because
    one role is held by one account (`uq_ledger_accounts_designation`)."""
    holder = selectors.designation_map().get(designation)
    if holder and str(holder) == account_id:
        return
    target = models.LedgerAccount.objects.filter(tenant_id=_tenant_id(), pk=account_id).first()
    if target is not None and target.designation and target.designation != designation:
        # One account carries one role. Silently moving `cash` off an account to
        # make it the refund account would stop every payment posting.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-LED-014",
            message_key="ledger.glMapping.accountHasRole",
            field_errors=[{"field": "account_id", "code": errors.BIZ_STATE,
                           "message_key": "ledger.glMapping.accountHasRole"}],
        )
    if holder:
        services.update_account(actor, account_id=holder, designation=None)
    services.update_account(actor, account_id=account_id, designation=designation)


def save(actor: Any, payload: Any) -> dict[str, Any]:
    """`POST /ledger/gl-mappings/rows` — `{act: add|edit, key, account_id}`.

    **Add** maps an item that has NO account yet (Q2: existing items only) and
    refuses one that has, so two clerks adding at once cannot overwrite each
    other silently. **Edit** re-points any live row. Both: the account must be
    live and of the kind the type allows (BR-LED-800).
    """
    body = payload if isinstance(payload, dict) else {}
    act = str(body.get("act") or "").strip()
    if act not in ("add", "edit"):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="ledger.glMapping.unknownAct")
    key = str(body.get("key") or "").strip()
    with transaction.atomic():
        row = _find(key, include_combinations=(act == "add"))
        live = _live_accounts()
        if not row.active:
            raise errors.BizError(
                errors.BIZ_STATE, br_ref="BR-LED-802", message_key="ledger.glMapping.rowDisabled"
            )
        if act == "add" and _status(row, live) != STATUS_NOT_MAPPED:
            raise errors.BizError(
                errors.BIZ_STATE, br_ref="BR-LED-800", message_key="ledger.glMapping.alreadyMapped"
            )
        account_id = _clean_account(row, body.get("account_id"))
        before = row.account_id
        _point(actor, row, account_id)
        _audit(actor, "added" if act == "add" else "edited", row, before, account_id)
        fresh = _find(key, include_combinations=False)
        return _wire(fresh, _live_accounts())


def set_enabled(actor: Any, payload: Any, *, enabled: bool) -> dict[str, Any]:
    """`POST /ledger/gl-mappings/rows/disable|enable` — `{key}` (BR-LED-802)."""
    body = payload if isinstance(payload, dict) else {}
    key = str(body.get("key") or "").strip()
    with transaction.atomic():
        row = _find(key, include_combinations=False)
        prefix, _, rest = row.key.partition(":")
        allowed = row.can_enable if enabled else row.can_disable
        if not allowed:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-LED-802",
                message_key=(
                    "ledger.glMapping.discountCannotReturn"
                    if prefix == "dsc" and enabled
                    else "ledger.glMapping.cannotDisable"
                ),
            )
        if prefix == "svc":
            # A class override's Disable REMOVES the override: the every-class
            # account applies to the next bill. Issued lines keep their stamp.
            code, part, cls = rest.split(":", 2)
            models.ServiceClassRevenueAccount.objects.filter(
                tenant_id=_tenant_id(), service_code=code, part=part, customer_class=cls
            ).delete()
            _audit(actor, "override_removed", row, row.account_id, None)
            return {"key": key, "removed": True}
        {
            "chg": seams.set_charge_enabled,
            "dsc": seams.set_discount_enabled,
            "adj": seams.set_reason_enabled,
        }[prefix](actor, rest, enabled)
        _audit(actor, "enabled" if enabled else "disabled", row, row.account_id, row.account_id)
        fresh = _find(key, include_combinations=False)
        return _wire(fresh, _live_accounts())


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-197-BRC10 (12-governance/change-requests/CR-197-BRC10-gl-mapping-one-list.md) · decision log 2026-10-29 (four GL mapping entries + "Mapped for, start") · BR-LED-800..803 · BR-LED-014 · BR-BIL-010
# generated: 2026-10-29 by the CR-197-BRC10 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row)
# gates: tests/test_cr197_gl_mapping_list.py (RED first: ModuleNotFoundError)
# exceptions: (1) paged in Python over assembled rows — bounded by configuration, see the docstring · (2) class combinations with no override are Add-form items, not list rows · (3) Enable on a retired discount refused by name
# status: HUMAN-REVIEW-PENDING · VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
