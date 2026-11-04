# ── Trace ──────────────────────────────────────────────
# Change:   CR-180-BRC10 — contract additions A1–A5 by the SCREEN lane (the
#           shapes the revamped Fix a bill screen reads; CR file §"Contract
#           additions by the SCREEN lane")
#           Screens: S30 (Fix a bill — Bills · Fix · Check · Send)
# Rules:    BR-BIL-044 (the approver reads exactly what was previewed) ·
#           BR-BIL-045 (the posting month, named) · BR-BIL-046 (up and down
#           apart) · B14 rule 31 (no database id is a VISIBLE value — ids here
#           are select values and keys, never text) · CLAUDE.md rule 2 (money
#           as decimal strings)
# Tests:    06-backend/tests/test_cr180_fix_a_bill_revamp.py (the contract-
#           shape cases at the end)
# ───────────────────────────────────────────────────────
"""The screen's view of a correction — READS ONLY, and decides nothing.

`correction_items` computes; this module LAYS OUT what it computed in the
shape the screen lane built against (A2 options, A3 preview answer, A4
approval block). Every figure here is a figure `correction_items` produced
or a stored column read back; the only arithmetic is display sums of those
(a section total, a totals row), the same discipline `bulk_corrections.
aggregate` keeps (*"the bulk layer performs no arithmetic of its own"*).

Kept apart from `correction_items` because that module is 🔒 money and this
one is presentation: a reviewer reading the money path should not have to
read the layout to find it.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from django.apps import apps as django_apps

from apps.billing import customers_seam, models, payments_seam, runs, single_correction
from apps.billing.correction_models import (
    CLASS_CREDIT_ONLY,
    CLASS_DOCUMENT,
    CLASS_RESTATEMENT,
    SCOPE_ACCOUNT,
    SCOPE_SINGLE,
)
from core import tenancy as core_tenancy

ZERO = Decimal("0")
FOUR = Decimal("0.0001")

#: A3 — the screen's rate-type vocabulary, from rating's stored model names.
RATE_TYPES: dict[str, str] = {
    "flat": "flat",
    "tiered": "tiered",
    "seasonal": "seasonal",
    "time_of_use": "tou",
    "demand": "demand",
    "percent_of_service": "percent_of",
    "capacity": "flat_per_unit",
}

#: A3 — what each reprint REASON shows as its field (the screen names the
#: reason; the payload key is `correction_items.REPRINT_FIELDS`').
_FIELD_REASON: dict[str, str] = {
    "customer_name": "customer_name",
    "service_address": "service_or_mailing_address",
    "mailing_address": "service_or_mailing_address",
    "premises_label": "premises_or_unit_label",
    "unit_label": "premises_or_unit_label",
    "meter_number": "meter_number_or_read_dates",
    "read_dates": "meter_number_or_read_dates",
    "message": "template_or_language",
    "language": "template_or_language",
}


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _money(value: Any) -> str | None:
    if value is None:
        return None
    return str(Decimal(str(value)).quantize(FOUR))


def _qty(value: Any) -> str | None:
    if value is None:
        return None
    # Six places at most (the stored scale of a quantity), then trimmed: a
    # day-share of 700 kWh is 233.333333, never a 28-digit division.
    return format(Decimal(str(value)).quantize(Decimal("0.000001")).normalize(), "f")


def _pct(fraction: Any) -> str | None:
    if fraction is None:
        return None
    return str((Decimal(str(fraction)) * 100).quantize(Decimal("0.000001")))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "line"


def _service_key(service: str, line: dict[str, Any]) -> str:
    """A key STABLE across was and becomes (A3): `water.base`, `water.tier2`,
    a split part suffixed with its first day so two parts never collide."""
    text = str(line.get("description") or "").lower()
    if line["kind"] == "base":
        stem = "base"
    elif line["kind"] == "minimum_adjustment":
        stem = "minimum"
    else:
        tier = re.search(r"tier\s*(\d+)", text)
        stem = f"tier{tier.group(1)}" if tier else _slug(text.replace(service, "", 1))
    days = re.findall(r"\d{4}-\d{2}-\d{2}", text)
    return f"{service}.{stem}" + (f"@{days[0]}" if days else "")


def _charge_codes(ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    return {
        str(pk): str(code)
        for pk, code in django_apps.get_model("rating", "Charge")
        .objects.filter(tenant_id=_tenant_id(), pk__in=list(ids))
        .values_list("id", "code")
    }


def document(
    lines: list[dict[str, Any]],
    *,
    invoice_no: str | None,
    plan_name: str | None,
    plan_version: str | None,
    currency: str,
    total: Any,
) -> dict[str, Any]:
    """A3 `DOC` — one bill, as it is laid out: each service with its rate type,
    then charges, discounts, deposits; subtotal; taxes per authority with
    their base; total."""
    codes = _charge_codes({line["charge_id"] for line in lines if line.get("charge_id")})
    services: dict[str, dict[str, Any]] = {}
    charges: list[dict[str, Any]] = []
    discounts: list[dict[str, Any]] = []
    deposits: list[dict[str, Any]] = []
    taxes: list[dict[str, Any]] = []
    subtotal = ZERO
    taxable = ZERO
    tax_total = ZERO
    for line in lines:
        amount = Decimal(str(line["amount"]))
        kind = line["kind"]
        if kind == "tax":
            tax_total += amount
        else:
            subtotal += amount
        if line.get("taxable"):
            taxable += amount
        row = {
            "label": line["description"],
            "qty": _qty(line.get("quantity")),
            "unit": line.get("unit"),
            "unit_price": _money(line.get("unit_price")) if kind != "tax" else None,
            "base": None,
            "percent": None,
            "amount": _money(amount),
        }
        service = line.get("service")
        if kind in ("usage", "base", "minimum_adjustment") and service:
            section = services.setdefault(
                service,
                {
                    "key": service,
                    "kind": "service",
                    "service_code": service,
                    "rate_type": None,
                    "total": ZERO,
                    "lines": [],
                },
            )
            if section["rate_type"] is None and line.get("rate_type"):
                section["rate_type"] = RATE_TYPES.get(line["rate_type"], line["rate_type"])
            section["total"] += amount
            section["lines"].append({"key": _service_key(service, line), **row})
        elif kind == "discount":
            code = line.get("discount_code") or _slug(line["description"])
            discounts.append({"key": f"discount.{code}", **row})
        elif kind == "deposit":
            deposits.append({"key": "deposit", **row})
        elif kind == "tax":
            code = line.get("tax_id") or _slug(line["description"])
            taxes.append(
                {
                    "key": f"tax.{code}",
                    "label": line["description"],
                    "rate": _pct(line.get("unit_price")),
                    "base": None,
                    "amount": _money(amount),
                }
            )
        else:
            code = codes.get(str(line.get("charge_id"))) or _slug(line["description"])
            charges.append({"key": f"charge.{code}", **row})
    for tax in taxes:
        tax["base"] = _money(taxable)
    sections = [{**section, "total": _money(section["total"])} for section in services.values()]
    for key, kind, rows in (
        ("charges", "charges", charges),
        ("discounts", "discounts", discounts),
        ("deposits", "deposits", deposits),
    ):
        if rows:
            sections.append(
                {
                    "key": key,
                    "kind": kind,
                    "service_code": None,
                    "rate_type": None,
                    "total": _money(sum((Decimal(r["amount"]) for r in rows), ZERO)),
                    "lines": rows,
                }
            )
    return {
        "invoice_no": invoice_no,
        "plan_name": plan_name,
        "plan_version": plan_version,
        "currency": currency,
        "sections": sections,
        "subtotal": _money(subtotal),
        "taxes": taxes,
        "tax_total": _money(tax_total),
        "total": _money(total),
    }


def _plan_of(invoice: models.Invoice) -> tuple[str | None, str | None]:
    plan = (invoice.bill_payload or {}).get("plan") or {}
    version = plan.get("version")
    return plan.get("name"), (None if version in (None, "") else f"v{version}")


def _settlement(impact: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    settled = impact.get("settlement") or None
    if settled:
        return (
            _money(settled.get("paid_to_date")),
            _money(settled.get("rebill_takes")),
            _money(settled.get("still_owed")),
        )
    return None, None, None


def bill_answer(
    preview: Any, *, with_documents: bool, names: dict[str, str | None]
) -> dict[str, Any]:
    """A3 `bills[]` — one bill, from what `correction_items.preview_bill` built."""
    from apps.billing import correction_items

    invoice = preview.invoice
    impact = preview.impact
    klass = impact["class"]
    goodwill = Decimal(impact["goodwill"]) if impact.get("goodwill") else ZERO
    was_total = Decimal(impact["original_total"])
    plan_name, plan_version = _plan_of(invoice)
    was = becomes = None
    if with_documents:
        was = document(
            correction_items._old_lines(invoice),
            invoice_no=invoice.invoice_no,
            plan_name=plan_name,
            plan_version=plan_version,
            currency=invoice.currency,
            total=invoice.total,
        )
        if klass == CLASS_RESTATEMENT and preview.rated is not None:
            data = preview.data
            becomes = document(
                correction_items._new_lines(preview.rated),
                invoice_no=None,
                plan_name=getattr(data, "rate_plan_name", None) or plan_name,
                plan_version=(
                    f"v{data.rate_plan_version}"
                    if getattr(data, "rate_plan_version", None) not in (None, "")
                    else plan_version
                ),
                currency=invoice.currency,
                total=preview.rated.total,
            )
        elif klass == CLASS_DOCUMENT:
            becomes = {**was, "invoice_no": None}
    becomes_total = Decimal(impact["corrected_total"])
    if klass == CLASS_CREDIT_ONLY:
        becomes_total = was_total - goodwill
    credit_note = None
    if goodwill > ZERO:
        credit_note = {
            "lines": [
                {
                    "key": "goodwill",
                    "label": f"Goodwill credit · {invoice.invoice_no}",
                    "amount": _money(-goodwill),
                }
            ],
            "total": _money(-goodwill),
        }
    delta = becomes_total - was_total if klass != CLASS_RESTATEMENT else Decimal(impact["delta"])
    paid, moves, still = _settlement(impact)
    if paid is None:
        applied = payments_seam.allocated_against_invoice(invoice.pk)
        paid = _money(applied)
        if applied is not None and klass != CLASS_RESTATEMENT:
            still = _money(max(ZERO, becomes_total - Decimal(str(applied))))
    return {
        "invoice_id": str(invoice.pk),
        "invoice_no": invoice.invoice_no,
        "account_id": str(invoice.account_id),
        "account_no": getattr(invoice.account, "account_no", None),
        "customer_name": names.get(str(invoice.account_id)),
        "period_start": invoice.period_start.isoformat(),
        "period_end": invoice.period_end.isoformat(),
        "was": was,
        "becomes": becomes,
        "credit_note": credit_note,
        "was_total": _money(was_total),
        "becomes_total": _money(becomes_total),
        "delta": _money(delta),
        "paid": paid,
        "moves_to_new_bill": moves,
        "still_owed": still,
        "posting_period": impact.get("posting_period"),
        "new_due_date": impact.get("new_due_date"),
    }


def _names_for(account_ids: list[str]) -> dict[str, str | None]:
    found = customers_seam.primary_contact_names_for(account_ids) if account_ids else {}
    return dict(found or {})


def _owes(account_id: Any) -> Decimal | None:
    """What the account owes now: Σ open balances less the credit it holds —
    payments' own reads, the subledger the finance tie-out compares."""
    positions = payments_seam.open_positions_for_accounts([account_id])
    credit = payments_seam.credit_position_for_account(account_id)
    if positions is None or credit is None:
        return None
    position = positions.get(str(account_id))
    rows = getattr(position, "invoices", ()) or ()
    outstanding = sum((Decimal(str(getattr(row, "balance", 0))) for row in rows), ZERO)
    return outstanding - Decimal(str(credit))


def _channels(account_id: Any) -> list[str]:
    """Post always (BR-BIL-036's floor), plus the account's elected channels."""
    from apps.billing import delivery_seam

    channels, _problem = delivery_seam.elected_channels(account_id)
    out = ["post"]
    for one in channels or ():
        word = {"email": "email", "portal": "portal"}.get(str(one))
        if word and word not in out:
            out.append(word)
    return out


def _approver() -> dict[str, Any]:
    """A3 `approver` — the role that signs (BR-BIL-014 v1) and, when exactly
    one person holds it, their name. Never an id (B14 rule 31)."""
    membership = django_apps.get_model("identity", "TenantMembership")
    holders = list(
        membership.objects.filter(tenant_id=_tenant_id(), role__code="system_admin")
        .select_related("user")
        .values_list("user__full_name", flat=True)[:2]
    )
    name = (holders[0] or "").strip() or None if len(holders) == 1 else None
    return {"role_name": single_correction.APPROVER_ROLE, "user_name": name}


def _issue_gl(line: dict[str, Any]) -> str | None:
    """The GL account issue will stamp on a NEW line (BR-BIL-010), asked
    through issue's own rule and readers — or None when it cannot place it
    (the approval would then refuse that bill by name; a preview never does)."""
    from apps.billing import issue
    from apps.billing.exceptions import BillingRuleError

    readers = {
        "revenue": issue._resolve(issue.GL_MODULE, issue.GL_REVENUE_READ),
        "designation": issue._resolve(issue.GL_MODULE, issue.GL_DESIGNATION_READ),
        "is_live": issue._resolve(issue.GL_MODULE, issue.GL_LIVENESS_READ),
        "charge_gl": issue._resolve(issue.CHARGE_GL_MODULE, issue.CHARGE_GL_READ),
        "tax_liability": issue._resolve(issue.TAX_GL_MODULE, issue.TAX_GL_READ),
    }
    if any(reader is None for reader in readers.values()):
        return None
    facts = {
        "kind": line["kind"],
        "description": line.get("description") or "",
        "service_code": line.get("service"),
        "charge_id": line.get("charge_id"),
        "tax_id": line.get("tax_id"),
    }
    try:
        return issue._gl_account_for(facts, **readers)
    except BillingRuleError:
        return None


def _finance(built: Any) -> dict[str, Any]:
    """A3 `finance` — the two entries per bill as totals (never netted), the
    net, the GL accounts the old bills' own stamps reverse and the new bills
    re-credit (matched by line identity to the stamped original), and the
    closed-period facts the Check step names."""
    credits = rebills = goodwill = ZERO
    change: dict[str, Decimal] = {}
    for preview in built.previews:
        impact = preview.impact
        if impact is not None and impact.get("goodwill"):
            # DEF-BIL-10085 — the concession posts its own entry (DR write-off,
            # CR customer credit balances; server lane judgment 2), so the
            # approver sees it here — on a credit-only case it is the ONLY one.
            goodwill += Decimal(impact["goodwill"])
        if impact is None or impact["class"] != CLASS_RESTATEMENT:
            continue
        from apps.billing import correction_items

        credits += Decimal(impact["original_total"])
        rebills += Decimal(impact["corrected_total"])
        old = correction_items._old_lines(preview.invoice)
        by_identity: dict[tuple, str] = {}
        for line in old:
            gl = line.get("gl_account_id")
            if not gl:
                continue
            by_identity[
                (line["kind"], line.get("service"), line.get("tax_id"), line.get("charge_id"))
            ] = gl
            change[gl] = change.get(gl, ZERO) - Decimal(str(line["amount"]))
        for line in correction_items._new_lines(preview.rated):
            gl = by_identity.get(
                (line["kind"], line.get("service"), line.get("tax_id"), line.get("charge_id"))
            )
            if not gl:
                # DEF-BIL-10084 — a line the old bill did not have (an added
                # charge, a deposit, a new tax) is stamped by issue's own rule;
                # dropped, the table stopped adding up to the net.
                gl = _issue_gl(line)
            if gl:
                change[gl] = change.get(gl, ZERO) + Decimal(str(line["amount"]))
    ledger_account = django_apps.get_model("ledger", "LedgerAccount")
    named = {
        str(pk): (code, name)
        for pk, code, name in ledger_account.objects.filter(
            tenant_id=_tenant_id(), pk__in=list(change)
        ).values_list("id", "code", "name")
    }
    accounts = [
        {
            "code": named.get(gl, (None, None))[0],
            "name": named.get(gl, (None, None))[1],
            "change": _money(amount),
        }
        for gl, amount in sorted(change.items(), key=lambda kv: named.get(kv[0], ("", ""))[0] or "")
    ]
    closed_through = earliest_open = None
    forwarded = [
        p.impact
        for p in built.previews
        if p.impact is not None and p.impact.get("posting_forwarded")
    ]
    if forwarded:
        earliest_open = min(one["posting_period"] for one in forwarded)
        first_day = date.fromisoformat(f"{earliest_open}-01")
        prior = date(first_day.year - (first_day.month == 1), (first_day.month - 2) % 12 + 1, 1)
        closed_through = prior.strftime("%Y-%m")
    return {
        "entries": [
            {"entry": "credit_notes", "amount": _money(credits)},
            {"entry": "new_bills", "amount": _money(rebills)},
            *([{"entry": "goodwill", "amount": _money(goodwill)}] if goodwill > ZERO else []),
        ],
        "net": _money(rebills - credits),
        "accounts": accounts,
        "closed_through": closed_through,
        "earliest_open": earliest_open,
    }


def _settle_in_order(live: list[Any], rows: list[dict[str, Any]]) -> None:
    """DEF-BIL-10087 — the bills of ONE account settle against ONE pool.

    Each bill's own settlement is computed against the account's WHOLE carried
    credit, so with two bills the credit was promised twice (AC-2026-00050:
    $1,045.09 on both). Approval runs the bills in this order (the case rows
    are created, and executed, in it): each release adds that bill's payments
    to the pool and each new bill draws from it — `apply_credit_at_issue`'s
    arithmetic, repeated here so Check promises what approval does. An account
    with one re-priced bill is left exactly as it was."""
    by_account: dict[str, list[tuple[Any, dict[str, Any]]]] = {}
    for preview, row in zip(live, rows):
        if preview.impact["class"] == CLASS_RESTATEMENT and preview.impact.get("settlement"):
            by_account.setdefault(str(preview.invoice.account_id), []).append((preview, row))
    for pairs in by_account.values():
        if len(pairs) < 2:
            continue
        first = pairs[0][0].impact["settlement"]
        pool = Decimal(str(first.get("credit_on_account") or "0"))
        for preview, row in pairs:
            settled = preview.impact["settlement"]
            pool += Decimal(str(settled.get("released") or "0"))
            corrected = Decimal(str(preview.impact["corrected_total"]))
            take = min(corrected, max(pool, ZERO))
            pool -= take
            row["moves_to_new_bill"] = _money(take)
            row["still_owed"] = _money(corrected - take)


def answer(built: Any, *, page: int | None = None, per: int | None = None) -> dict[str, Any]:
    """A3 — `POST /corrections/preview`'s full answer, from `correction_items.
    build`. Writes nothing."""
    one_customer = built.kind in (SCOPE_ACCOUNT, SCOPE_SINGLE)
    live = [p for p in built.previews if p.impact is not None]
    account_ids = sorted({str(p.invoice.account_id) for p in live})
    names = _names_for(account_ids)
    rows = [bill_answer(p, with_documents=one_customer, names=names) for p in live]
    _settle_in_order(live, rows)
    up = [r for r in rows if Decimal(r["delta"]) > ZERO]
    down = [r for r in rows if Decimal(r["delta"]) < ZERO]
    totals = {
        "was": _money(sum((Decimal(r["was_total"]) for r in rows), ZERO)),
        "becomes": _money(sum((Decimal(r["becomes_total"]) for r in rows), ZERO)),
        "net": _money(sum((Decimal(r["delta"]) for r in rows), ZERO)),
        "up": {"count": len(up), "amount": _money(sum((Decimal(r["delta"]) for r in up), ZERO))},
        "down": {
            "count": len(down),
            "amount": _money(sum((Decimal(r["delta"]) for r in down), ZERO)),
        },
        "unchanged": len(rows) - len(up) - len(down),
    }
    restated = [p for p in live if p.impact["class"] == CLASS_RESTATEMENT]
    if not one_customer:
        # DEF-BIL-10103 — a bulk bill whose total does not move is left as it
        # is (no credit note, no new bill), so it is not counted as one.
        from apps.billing import correction_items as _items

        restated = [p for p in restated if not _items._unchanged(p.impact)]
    goodwill_notes = [p for p in live if p.impact.get("goodwill")]
    reprints = [p for p in live if p.impact.get("page_changes")]
    customer = None
    bulk = None
    if one_customer and live:
        account_id = live[0].invoice.account_id
        owes_before = _owes(account_id)
        goodwill = sum((Decimal(p.impact["goodwill"]) for p in goodwill_notes), ZERO)
        net = sum((Decimal(p.impact["delta"]) for p in restated), ZERO)
        owes_after = None if owes_before is None else owes_before + net - goodwill
        customer = {
            "name": names.get(str(account_id)),
            "account_no": getattr(live[0].invoice.account, "account_no", None),
            "owes_before": _money(owes_before),
            "owes_after": _money(owes_after),
            "refund": None,
            "credit_notes": len(restated) + len(goodwill_notes),
            "new_bills": len(restated),
            "reprints": len(reprints),
            "channels": _channels(account_id),
            "new_due_date": next((r["new_due_date"] for r in rows if r.get("new_due_date")), None),
        }
    else:
        moved = ZERO
        for p, row in zip(live, rows):
            if p.impact["class"] == CLASS_RESTATEMENT and row.get("moves_to_new_bill"):
                moved += Decimal(str(row["moves_to_new_bill"]))
        bulk = {
            "credit_notes": len(restated) + len(goodwill_notes),
            "new_bills": len(restated),
            "reprints": len(reprints),
            "refunds": None,
            "payments_moved": _money(moved),
            "channels": ["post"],
        }
    page_changes: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for p in live:
        for change in p.impact.get("page_changes") or []:
            reason = _FIELD_REASON.get(change["field"], change["field"])
            key = (reason, change.get("was"), change["becomes"])
            if key in seen:
                continue
            seen.add(key)
            page_changes.append(
                {"field": reason, "was": change.get("was"), "becomes": change["becomes"]}
            )
    count = len(rows)
    if page and per and not one_customer:
        start = (int(page) - 1) * int(per)
        rows = rows[start : start + int(per)]
    return {
        "correction_class": built.correction_class if live else None,
        "scope_kind": built.kind,
        "currency": live[0].invoice.currency if live else None,
        "count": count,
        "accounts": len(account_ids),
        "bills": rows,
        "totals": totals,
        "customer": customer,
        "bulk": bulk,
        "finance": _finance(built),
        "page_changes": page_changes,
        "approver": _approver(),
        "preview_hash": built.preview_hash,
        "problems": [
            {
                "code": one.get("code"),
                # DEF-BIL-10096 — a bulk bill left out because it cannot be
                # priced names itself; the screen lists it and goes on.
                "message_key": {
                    "cannot_price": "billing.fixBill.leftOut.cannotPrice",
                    "beyond_the_back_bill_cap": "billing.fixBill.leftOut.backBill",
                }.get(str(one.get("code"))),
                "detail": one.get("invoice_no"),
            }
            for one in built.excluded
            if one.get("code") not in (None, "draft", "open_case")
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# A2 · GET /corrections/options — what the row selects offer. Writes nothing.
# ═══════════════════════════════════════════════════════════════════════════
def _rating(name: str) -> Any:
    return django_apps.get_model("rating", name)


def _plans() -> list[dict[str, Any]]:
    out = []
    for plan in _rating("RatePlan").objects.filter(tenant_id=_tenant_id()).order_by("name"):
        versions = (
            _rating("PlanVersion")
            .objects.filter(
                tenant_id=_tenant_id(),
                rate_plan_id=plan.pk,
                status="published",
                superseded_by__isnull=True,
                effective_from__isnull=False,
            )
            .order_by("effective_from", "version_no")
        )
        out.append(
            {
                "id": str(plan.pk),
                "name": plan.name,
                "versions": [
                    {
                        "id": str(v.pk),
                        "label": f"v{v.version_no}",
                        "effective_from": v.effective_from.isoformat(),
                    }
                    for v in versions
                ],
            }
        )
    return out


def _schedules() -> list[dict[str, Any]]:
    out = []
    tariffs = (
        _rating("Tariff")
        .objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
        .select_related("service")
        .order_by("name")
    )
    for tariff in tariffs:
        versions = (
            _rating("TariffVersion")
            .objects.filter(
                tenant_id=_tenant_id(),
                tariff_id=tariff.pk,
                effective_from__isnull=False,
                # DEF-BIL-10101 — a version corrected over its own window
                # (BR-RAT-1016 verb 2) is no longer a price; only the live
                # statement is offered, as `_plans()` already does.
                superseded_by__isnull=True,
            )
            .order_by("effective_from", "id")
        )
        out.append(
            {
                "id": str(tariff.pk),
                "name": tariff.name,
                "service_code": getattr(tariff.service, "code", None),
                "versions": [
                    {
                        "id": str(v.pk),
                        "label": f"v{n}",
                        "effective_from": v.effective_from.isoformat(),
                    }
                    for n, v in enumerate(versions, start=1)
                ],
            }
        )
    return out


def _taxes() -> list[dict[str, Any]]:
    return [
        {"code": str(pk), "name": name, "rate": _pct(rate)}
        for pk, name, rate in _rating("Tax")
        .objects.filter(tenant_id=_tenant_id())
        .order_by("name")
        .values_list("id", "name", "rate")
    ]


def _charges() -> list[dict[str, Any]]:
    by_code = runs._resolve("rating", "charge_by_code")
    out = []
    for code, name in (
        _rating("Charge")
        .objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True, is_base=False)
        .order_by("code")
        .values_list("code", "name")
    ):
        found = by_code(code) if by_code is not None else None
        amount = (found or {}).get("amount")
        out.append({"code": code, "name": name, "amount": _money(amount)})
    return out


def _discounts() -> list[dict[str, Any]]:
    in_force = runs._resolve("rating", "discount_version_in_force")
    out = []
    for discount in _rating("Discount").objects.filter(tenant_id=_tenant_id()).order_by("name"):
        version = in_force(discount) if in_force is not None else None
        number = getattr(version, "version_no", None)
        out.append(
            {
                "id": str(discount.pk),
                "name": discount.name,
                "version_label": None if number is None else f"v{number}",
            }
        )
    return out


def options(scope: dict[str, Any] | None) -> dict[str, Any]:
    """A2 — the tenant's lists, and with a scope the meters, the bill lines and
    what the (first) bill was billed on."""
    taxes = _taxes()
    schedules = _schedules()
    charges = _charges()
    body: dict[str, Any] = {
        "plans": _plans(),
        "rate_schedules": schedules,
        "taxes": taxes,
        "charge_codes": charges,
        "discounts": _discounts(),
        "price_targets": (
            [{"kind": "rate", "id": s["id"], "label": s["name"]} for s in schedules]
            + [{"kind": "tax", "id": t["code"], "label": t["name"]} for t in taxes]
            + [
                {"kind": "charge", "id": str(pk), "label": f"{name} · {code}"}
                for pk, code, name in _rating("Charge")
                .objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True, is_base=False)
                .order_by("code")
                .values_list("id", "code", "name")
            ]
        ),
    }
    if not scope or not (scope.get("kind") or scope.get("scope_kind")):
        return body
    from apps.billing import bulk_corrections, correction_items

    kind, args = correction_items._scope_args(scope)
    invoices = bulk_corrections.resolve_scope(kind=kind, exclude_in_flight=True, **args)
    body["meters"] = _meters(invoices)
    body["bill_lines"] = _bill_lines(invoices)
    body["billed"] = _billed(invoices[0]) if invoices else None
    return body


def _meters(invoices: Any) -> list[dict[str, Any]]:
    """A2 `meters` — the meters the bills were priced from, with the reading
    each bill charged (off the bills' frozen snapshots; `metering_seam.
    read_ids_on`)."""
    from apps.billing import metering_seam

    service_of: dict[str, str | None] = {}
    for invoice in invoices[:200]:
        for entry in (invoice.bill_payload or {}).get("services") or []:
            if isinstance(entry, dict) and entry.get("read_id"):
                service_of[str(entry["read_id"])] = entry.get("code")
        for read_id in metering_seam.read_ids_on(invoice):
            service_of.setdefault(str(read_id), None)
    if not service_of:
        return []
    reads = django_apps.get_model("metering", "MeterRead")
    rows = list(
        reads.objects.filter(tenant_id=_tenant_id(), id__in=list(service_of))
        .order_by("asset_id", "-read_at")
        .values("id", "asset_id", "current_value", "unit")
    )
    labels = {
        str(pk): asset_no
        for pk, asset_no in django_apps.get_model("assets", "Asset")
        .objects.filter(tenant_id=_tenant_id(), pk__in=list({r["asset_id"] for r in rows}))
        .values_list("id", "asset_no")
    }
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row["asset_id"])
        if key in out:
            continue
        out[key] = {
            "asset_id": key,
            "label": labels.get(key),
            "service_code": service_of.get(str(row["id"])),
            "unit": row["unit"],
            "billed_reading": None if row["current_value"] is None else str(row["current_value"]),
        }
    return list(out.values())


def _bill_lines(invoices: Any) -> list[dict[str, Any]]:
    rows = list(
        models.InvoiceLine.objects.filter(
            tenant_id=_tenant_id(), invoice_id__in=[i.pk for i in invoices[:200]], kind="fee"
        ).values_list("description", "charge_id")
    )
    codes = _charge_codes({str(c) for _d, c in rows if c})
    out: dict[str, dict[str, Any]] = {}
    for description, charge_id in rows:
        code = codes.get(str(charge_id)) if charge_id else None
        key = f"charge.{code}" if code else f"charge.{_slug(description)}"
        out.setdefault(
            key, {"key": key, "label": f"{description} · {code}" if code else description}
        )
    return list(out.values())


def _billed(invoice: models.Invoice) -> dict[str, Any]:
    payload = invoice.bill_payload or {}
    plan = payload.get("plan") or {}
    plan_id = plan.get("id")
    version_id = None
    if plan_id and plan.get("version") not in (None, ""):
        version_id = (
            _rating("PlanVersion")
            .objects.filter(
                tenant_id=_tenant_id(), rate_plan_id=plan_id, version_no=plan["version"]
            )
            .values_list("id", flat=True)
            .first()
        )
    lines = list(models.InvoiceLine.objects.filter(tenant_id=_tenant_id(), invoice=invoice))
    tax_rates = {
        str(line.tax_id): _pct(line.unit_price)
        for line in lines
        if line.kind == "tax" and line.tax_id
    }
    deposit = sum((line.amount for line in lines if line.kind == "deposit"), ZERO)
    fields: dict[str, Any] = {}
    for reason, keys in (
        ("customer_name", ("customer_name",)),
        ("service_or_mailing_address", ("service_address", "mailing_address")),
        ("premises_or_unit_label", ("premises_label", "unit_label")),
        ("meter_number_or_read_dates", ("meter_number", "read_dates")),
        ("template_or_language", ("message", "language")),
    ):
        value = next((payload.get(k) for k in keys if payload.get(k) not in (None, "")), None)
        fields[reason] = value if value is None or isinstance(value, str) else str(value)
    return {
        "plan_id": plan_id,
        "plan_version_id": None if version_id is None else str(version_id),
        "tax_rates": tax_rates,
        "deposit": _money(deposit),
        "fields": fields,
    }


# ═══════════════════════════════════════════════════════════════════════════
# A4 · the approval block a case carries
# ═══════════════════════════════════════════════════════════════════════════
def approval(case: Any) -> dict[str, Any]:
    approver = _approver()
    return {
        "role_name": approver["role_name"],
        "approver_name": approver["user_name"],
        "initiated_by_name": single_correction._name_of(case, "initiated_by"),
        "sent_on": (
            case.created_at.date().isoformat() if getattr(case, "created_at", None) else None
        ),
        "approved_by_name": single_correction._name_of(case, "approved_by"),
    }
