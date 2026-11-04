"""The S9 History in a clerk's words — `DEF-RAT-10029`.

A presentation read: it words the stored values of `rate_change_log` for a
screen, does no arithmetic, and never writes. The two guarded files it changed
the behaviour of (`selectors.py`, `plan_writes.py`) carry the review row in
`12-governance/09-human-review-ledger.md` (2026-10-09, DEF-RAT-10029).

── WHAT WAS WRONG ───────────────────────────────────────────────────────────
`selectors.history_row` served the log row as stored — `actor_user_id` and the
two raw `before`/`after` snapshots — and the screen printed them: the WHO column
read `01a0f319-…`, the CHANGE column read *account_type_id — → 01a0f27b-… and 89
more*, and *Change details* dumped the whole plan as JSON with every id in it.
B14 rule 31 (PO: *"no Databse ID on screen - that is a rule"*).

── WHAT THIS DOES ───────────────────────────────────────────────────────────
ONE function, `history_rows`, serves the list AND the dialog, so the two cannot
describe one change differently:

* `actor.name` — the person's NAME, batched through the identity seam the rest
  of this module already uses (`seams.user_display_names`). The id stays on the
  row only because the History filter takes it; no screen prints it.
* `changes` — `[{field, before, after}]`, every changed FACT in words:
  a clerk label (*Minimum bill*, *Tier 1 · Rate*, *Taxes*), and each value
  worded — money with its symbol at two places, a unit price at up to four
  (hard rule 2's one exception), dates as dates, yes/no, and every FOREIGN ID
  RESOLVED to the thing's name or code (customer class, tax, jurisdiction,
  charge code, rate schedule, discount, person). An id this tenant cannot name
  reads `—`; **a uuid never reaches the words**, and `_finish` enforces that as
  a last line rather than trusting every branch above it.
* Internal-only keys are dropped: ids, `*_display` duplicates of a key already
  worded, `*_unavailable` markers, version counters, timestamps, and the reason
  (it has its own column).
* `before_kept` — False when the row stored no `before`. Such a row is NOT
  "everything changed": `changes` then lists the saved values with `—` on the
  left, and the screen says the earlier values were not kept. The plan publish
  path wrote rows like that until this fix (`plan_writes._publish`).

Collections are compared BY IDENTITY (a tax by its name, a tier by its number,
a price row by its size and class), never by position — so adding a tax reads
*Taxes: None → State tax*, not *tax_attachments[0].name — → State tax*. A
killed price row is not a price (`charge_prices`), so it is left out.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.rating import models, seams, selectors

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

#: Never a fact a clerk reads: identity, bookkeeping, and things another column says.
_SKIP = {
    "id", "version", "version_no", "versions", "accounts", "created_at", "updated_at",
    "corrects", "superseded_by", "corrected_by", "correction_reason", "change_reason",
    "reason", "submitted_by", "killed", "seq", "currency", "version_terms",
    "tax_lines", "combined_tax_rate_display", "price_range", "used_by_plans",
    "used_by_invoice_lines", "used_by_schedules", "outside_city_factor",
    # the plan's singular mirror of `account_type_ids` (`DEF-RAT-5768`) — the
    # list is the fact, the scalar would say it twice.
    "account_type_id", "gl_account_name", "unavailable", "version_label",
    "money_display", "applied_to_accounts",
    # `DEF-RAT-10031` — a version copy's schema flag, never a fact.
    "terms_recorded",
}

#: The clerk's word for a key. `""` flattens the level away (`structure`).
_LABELS = {
    "name": "Name", "code": "Code", "description": "Description", "status": "Status",
    "minimum_bill_amount": "Minimum bill", "minimum_bill": "Minimum bill",
    "budget_billing": "Budget billing", "outside_city_percent": "Outside-city surcharge",
    "effective_from": "Starts", "effective_to": "Ends",
    "account_type_ids": "Customer classes", "applies_to_customer_classes": "Customer classes",
    "customer_class": "Customer class", "account_subtype": "Customer subtype",
    "eligibility": "Notes", "services": "Services", "rate_schedules": "Rate schedules",
    "tariff": "Rate schedule", "charge_rules": "Charge codes", "deposit_rules": "Deposits",
    "tax_rules": "Tax jurisdictions", "tax_attachments": "Taxes", "rate_override": "Rate override", "discounts": "Discounts",
    "late_fee_charge": "Late fee", "penalty_rule": "Late fee", "base_charges": "Base charges",
    "base_charge": "Base charge", "base_charge_code": "Base charge code",
    "schedule_minimum_amount": "Schedule minimum", "outside_city_exempt": "Outside-city exempt",
    "gl_account": "GL account", "gl_account_code": "GL account",
    "structure": "", "tiers": "", "seasons": "", "windows": "", "size_rows": "Sizes",
    "model": "Pricing model", "uom": "Unit", "unit": "Unit",
    "unit_price": "Rate", "from_qty": "From", "to_qty": "To",
    "season": "Season", "size_class": "Size",
    "filing_authority": "Filing authority", "filed_on": "Filed on",
    "regulator_approved_on": "Approved on", "regulator_approver": "Approved by",
    "regulator_ref": "Regulator reference", "approved_by": "Approved by",
    "notify_customers": "Notify customers", "publish_public": "Publish publicly",
    "charge_type": "Type", "amount_rule": "Priced by", "amount": "Amount",
    "percent": "Percent", "min_amount": "Minimum", "max_amount": "Maximum",
    "is_base": "Base charge", "kind": "Kind", "taxable_default": "Taxable",
    "auto_apply": "Applied automatically", "waivable": "Waivable",
    "separate_line": "Own bill line", "grace_days": "Grace days", "grace_mode": "Grace",
    "is_application_fee": "Application fee", "is_nsf_fee": "NSF fee", "size_amounts": "Size prices",
    "class_terms": "Class prices", "prices": "Prices", "service": "Service",
    "rate": "Rate", "flat_amount": "Flat amount", "jurisdiction": "Jurisdiction",
    "authority": "Authority", "level": "Level", "reference_no": "Reference",
    "tax": "Tax", "charge": "Charge code", "discount": "Discount",
    "offered_from": "Offered from", "offered_until": "Offered until",
}

#: Keys whose id values are resolved, and to which kind — the rest fall back to
#: "any thing this tenant can name", then `—`.
_UNIT_PRICE_KEYS = {"unit_price", "price", "energy_rate", "demand_rate"}
_MONEY_PARTS = ("amount", "charge", "minimum", "fee", "cap", "budget", "floor", "deposit", "bill")

_STATUS = {"draft": "Draft", "published": "Published", "archived": "Archived", "active": "Active"}


#: Keys whose `_display` sibling IS the fact in words (`DEF-RAT-10032`). Any
#: `_display` ending in `%` wins as well: a percentage stored as a fraction.
_DISPLAY_WINS = {"rate", "value"}


def _display_wins(key: str, value: dict[str, Any]) -> bool:
    shown = value.get(f"{key}_display")
    return isinstance(shown, str) and bool(shown) and (shown.endswith("%") or key in _DISPLAY_WINS)


class _Coll(dict):
    """A list of records, keyed by each record's identity in words."""


class _Names:
    """Every id on one page of rows, resolved in one read per kind."""

    def __init__(self, blobs: list[Any], actor_ids: list[Any]) -> None:
        ids: set[str] = set()
        codes: set[str] = set()
        _collect(blobs, ids, codes)
        self.users = seams.user_display_names([*actor_ids, *ids])
        self.things: dict[str, str] = {}
        if ids:
            self.things.update(seams.account_type_names(list(ids)))
            tenant = selectors._tenant_id()
            for row in models.Tax.objects.filter(tenant_id=tenant, pk__in=ids).values("id", "name"):
                self.things[str(row["id"])] = row["name"]
            for row in models.TaxJurisdiction.objects.filter(tenant_id=tenant, pk__in=ids).values("id", "name"):
                self.things[str(row["id"])] = row["name"]
            for row in models.Charge.objects.filter(tenant_id=tenant, pk__in=ids).values("id", "code"):
                self.things[str(row["id"])] = row["code"]
            for row in models.Tariff.objects.filter(tenant_id=tenant, pk__in=ids).values("id", "name"):
                self.things[str(row["id"])] = row["name"]
            from apps.rating import discounts as discount_models

            for row in discount_models.Discount.objects.filter(tenant_id=tenant, pk__in=ids).values("id", "code", "name"):
                self.things[str(row["id"])] = f"{row['code']} · {row['name']}"
            self.things.update(self.users)
        self.class_codes = seams.account_type_names_by_code() if codes else {}

    def thing(self, value: Any) -> str:
        return self.things.get(str(value), "—")


def _collect(value: Any, ids: set[str], codes: set[str], key: str = "") -> None:
    if isinstance(value, dict):
        for sub_key, sub in value.items():
            _collect(sub, ids, codes, sub_key)
    elif isinstance(value, list):
        for item in value:
            _collect(item, ids, codes, key)
    elif isinstance(value, str):
        if selectors._valid_uuid(value):
            ids.add(value)
        elif key in ("applies_to_customer_classes", "customer_class"):
            codes.add(value)


def _label(key: str) -> str:
    if key in _LABELS:
        return _LABELS[key]
    return key.replace("_", " ").strip().capitalize()


def _humanise(text: str) -> str:
    return text.replace("_", " ").strip().capitalize()


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _scalar(key: str, value: Any, names: _Names) -> str:
    """One stored value in words."""
    from apps.rating import plan_reads

    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str) and selectors._valid_uuid(value):
        return names.thing(value)
    if key in ("applies_to_customer_classes", "customer_class") and isinstance(value, str):
        return names.class_codes.get(value, _humanise(value))
    if key == "status" and isinstance(value, str):
        return _STATUS.get(value, _humanise(value))
    if isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-":
        try:
            return date.fromisoformat(value).strftime("%m/%d/%Y")
        except ValueError:
            pass
    number = _decimal(value)
    if number is not None and not isinstance(value, int):
        if "percent" in key:
            return f"{number.quantize(Decimal('0.01'))}%"
        if key in _UNIT_PRICE_KEYS:
            return plan_reads._rate_words(number) or str(value)
        if any(part in key for part in _MONEY_PARTS):
            return plan_reads._money_words(number) or str(value)
        normal = number.normalize()
        return f"{normal:f}"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and key in ("service", "model", "uom", "unit", "charge_type", "amount_rule", "kind", "grace_mode", "level", "season", "lapse_behaviour"):
        return _humanise(value) if value.islower() else value
    return str(value)


def _ref_words(value: dict[str, Any], names: _Names) -> str:
    for field in ("name", "code", "tariff_name"):
        text = value.get(field)
        if text and not selectors._valid_uuid(str(text)):
            return str(text)
    if value.get("id"):
        return names.thing(value["id"])
    return "—"


def _is_ref(value: dict[str, Any]) -> bool:
    """`{id, name, …}` held under a key — a pointer at another thing (the late
    fee's charge code, the person who approved), worded by its name or code
    rather than walked."""
    return "id" in value and ("name" in value or "code" in value)


def _item_label(index: int, item: Any, key: str) -> str:
    if not isinstance(item, dict):
        return f"#{index + 1}"
    if key in ("tiers",) or ("seq" in item and "unit_price" in item):
        season = item.get("season")
        tier = f"Tier {item.get('seq') or index + 1}"
        return f"{season} · {tier}" if season else tier
    if key == "prices":
        parts = [str(item.get("size_class") or "All sizes")]
        if item.get("customer_class"):
            parts.append(str(item["customer_class"]))
        return " · ".join(parts)
    for field in ("name", "tariff_name", "jurisdiction", "code", "label", "service", "size_class"):
        text = item.get(field)
        if text and not selectors._valid_uuid(str(text)):
            return _humanise(str(text)) if field == "service" else str(text)
    return f"#{index + 1}"


def _normalise(key: str, value: Any, names: _Names) -> Any:
    """A snapshot turned into nested `{label key: words}`; collections keyed by
    identity. Only words leave this function."""
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            rows = [item for item in value if not (key == "prices" and item.get("killed"))]
            out = _Coll()
            for index, item in enumerate(rows):
                label = _item_label(index, item, key)
                while label in out:
                    label = f"{label} ({index + 1})"
                # Walked, not worded as a pointer: a plan's charge-code row
                # carries its own override amount, and that is a price.
                out[label] = _normalise("", item, names)
            return out
        if not value:
            # An empty class list means EVERY class (`DEF-RAT-5768`), the
            # plan screen's own words; any other empty list is *None*.
            if key in ("account_type_ids", "applies_to_customer_classes"):
                return "Every customer class"
            return "None"
        words = [_scalar(key, item, names) for item in value]
        words = [word for word in words if word != "—"]
        return ", ".join(words) if words else "—"
    if isinstance(value, dict):
        if key and _is_ref(value):
            return _ref_words(value, names)
        out: dict[str, Any] = {}
        for sub_key, sub in value.items():
            if sub_key in _SKIP or sub_key.endswith("_unavailable"):
                continue
            if sub_key.endswith("_display"):
                stem = sub_key[: -len("_display")]
                if stem in _SKIP:
                    continue
                if stem in value:
                    # `DEF-RAT-10032` — a tax's `rate` is stored as a FRACTION
                    # (`0.020000`) and a discount's `value` as points, money or
                    # a quantity by its type; only the server's display words
                    # say which (*2.00%*, *15.00%*, *$5.00*). Those words the
                    # stem; every other raw value is worded below as before.
                    if _display_wins(stem, value):
                        out[stem] = str(sub)
                    continue
                if sub is None:
                    out[stem] = "—"
                elif any(part in stem for part in _MONEY_PARTS) and _decimal(sub) is not None:
                    out[stem] = _scalar(stem, sub, names)
                else:
                    out[stem] = str(sub)
                continue
            if _display_wins(sub_key, value):
                continue  # worded from its `_display` sibling (above or below)
            if sub_key.endswith("_ref") and isinstance(sub, dict):
                out[sub_key[: -len("_ref")]] = _ref_words(sub, names)
                continue
            if f"{sub_key}_ref" in value:
                continue
            if sub_key.endswith("_name") and f"{sub_key[: -len('_name')]}_id" in value:
                out[sub_key[: -len("_name")]] = _scalar(sub_key, sub, names)
                continue
            if sub_key.endswith("_id") and any(
                f"{sub_key[: -len('_id')]}{suffix}" in value for suffix in ("_name", "_code", "")
            ):
                continue
            stem = sub_key
            if sub_key.endswith("_ids") and sub_key not in _LABELS:
                stem = sub_key[: -len("_ids")]
            elif sub_key.endswith("_id"):
                stem = sub_key[: -len("_id")]
            out[stem] = _normalise(sub_key, sub, names)
        return out
    return _scalar(key, value, names)


def _summary(value: Any) -> str:
    if isinstance(value, _Coll):
        return ", ".join(value.keys()) if value else "None"
    if isinstance(value, dict):
        # A record on one side only — say what it is, not what is inside it.
        for field in ("name", "code"):
            if isinstance(value.get(field), str) and value[field] != "—":
                return value[field]
        return "—" if not value else "Set"
    if value is None:
        return "—"
    return str(value)


def _diff(path: list[str], old: Any, new: Any, out: list[dict[str, str]]) -> None:
    if isinstance(old, _Coll) or isinstance(new, _Coll):
        old_c = old if isinstance(old, _Coll) else _Coll()
        new_c = new if isinstance(new, _Coll) else _Coll()
        if list(old_c.keys()) != list(new_c.keys()):
            _emit(path, _summary(old if old is not None else "None"), _summary(new if new is not None else "None"), out)
        for label in new_c:
            if label in old_c:
                _diff([*path, label], old_c[label], new_c[label], out)
        return
    # A record present on one side only is walked against an empty one, so its
    # facts are named one by one rather than as "Set".
    if isinstance(old, dict) and new is None:
        new = {}
    if isinstance(new, dict) and old is None:
        old = {}
    if isinstance(old, dict) and isinstance(new, dict):
        for key in [*new.keys(), *[k for k in old.keys() if k not in new]]:
            _diff([*path, _label(key)], old.get(key), new.get(key), out)
        return
    if isinstance(old, dict) or isinstance(new, dict):
        if _summary(old) != _summary(new):
            _emit(path, _summary(old), _summary(new), out)
        return
    before = "—" if old is None else str(old)
    after = "—" if new is None else str(new)
    if before != after:
        _emit(path, before, after, out)


def _finish(text: str) -> str:
    """The last line of B14 rule 31: whatever happened above, no uuid leaves."""
    return UUID_RE.sub("—", text) if UUID_RE.search(text) else text


def _emit(path: list[str], before: str, after: str, out: list[dict[str, str]]) -> None:
    field = " · ".join(part for part in path if part) or "Value"
    out.append({"field": _finish(field), "before": _finish(before), "after": _finish(after)})


def changes(before: Any, after: Any, names: _Names) -> list[dict[str, str]]:
    """`[{field, before, after}]` in words. With no `before`, the saved values
    are listed against `—` (never as N changes)."""
    new = _normalise("", after if isinstance(after, dict) else {}, names)
    out: list[dict[str, str]] = []
    if not isinstance(before, dict):
        _diff([], {}, new, out)
        return [{**row, "before": "—"} for row in out if row["after"] not in ("—", "None")]
    old = _normalise("", before, names)
    _diff([], old, new, out)
    # A charge code's flat `amount` and its one dated price row are the same
    # move; say it once (*Amount: $2.00 → $5.00*), not twice.
    kept: list[dict[str, str]] = []
    for row in out:
        if any(
            row["field"].endswith(f" · {seen['field']}")
            and (row["before"], row["after"]) == (seen["before"], seen["after"])
            for seen in kept
        ):
            continue
        kept.append(row)
    # `DEF-RAT-10032` — the figure a bill charges leads (*Rate: 2.00% → 6.00%*,
    # not *Status: Active → Scheduled and 3 more*); otherwise the stored order.
    kept.sort(key=lambda row: 0 if row["field"].rsplit(" · ", 1)[-1] in _PRICE_FIELDS else 1)
    return kept


#: The labels of the figures a bill charges — listed first in a change.
_PRICE_FIELDS = {"Rate", "Value", "Amount", "Flat amount", "Per unit amount", "Per meter amount", "Minimum bill"}




# ── Taxes and discounts on History (`DEF-RAT-10032`, PO ruling 2026-10-09) ──
#
# PO, verbatim: *"Question: should the History button on Plans & Rates also
# list changes made to taxes and discounts? (a) Show them on History too"*.
#
# ⚠ **ONE SOURCE PER KIND, AND FOR TAXES AND DISCOUNTS IT IS `audit_log`.**
# Their edits are written there by every tax and discount writer (some forty
# call sites) and nowhere else; the plan's own Audit tab already reads them
# from there (`plan_reads.plan_audit_queryset`, J10). History therefore reads
# the same rows through the rating seam, in ONE SQL `UNION` with
# `rate_change_log` (`selectors.history_list_queryset`) — never a second copy
# written beside them, which would be free to disagree, and never a Python merge
# of two unbounded lists (`NFR-3`). The cost is stated, not hidden: `audit_log`
# is pruned on its retention schedule (hard rule 4, `OQ-1340` ruled 2026-09-23
# *"when audit log is delete - it is deleted thats okay"*), so an old tax
# change leaves History when it leaves the tax's own Audit tab, together.
#
# ⚠ **A NEW RATE IS TWO AUDIT ROWS AND ONE ACT.** `new_tax_rate` ends the old
# version (`tax.ended_for_new_rate`, carrying the old terms as `before`) and
# creates the next one (`tax.new_rate_created`, `after` only). A correction is
# the same pair. History lists the act ONCE — the row creating the new version —
# and words it against the partner's `before`, so it reads *Rate: 2.00% →
# 6.00%* rather than *Earlier values not kept* beside a second row saying only
# that a date moved.

#: The audit row that creates a successor → the row its partner writes on the
#: version it replaces, in the same transaction, holding the old terms.
SUCCESSOR_PARTNERS = {
    "tax.new_rate_created": "tax.ended_for_new_rate",
    "tax.correction_created": "tax.corrected",
    "discount.correction_created": "discount.version_corrected",
}
PARTNER_ACTIONS = tuple(SUCCESSOR_PARTNERS.values())

#: The tax and discount acts History lists — each a change to what a bill
#: charges or to how the item reads. Not listed: a CREATION (History lists
#: changes, as it does for plans), the partner half of a pair (above), a draft
#: being written, and the per-account rows (enrolments, grants) no plan prices.
HISTORY_AUDIT_ACTIONS = (
    "tax.updated",
    "tax.new_rate_created",
    "tax.correction_created",
    "tax.activated",
    "tax.retired",
    "tax.deactivated",
    "tax.reactivated",
    "discount.updated",
    "discount.details_updated",
    "discount.gl_account_updated",
    "discount.new_value",
    "discount.correction_created",
    "discount.version_approved",
    "discount.version_self_approved",
    "discount.retired",
    "discount.funding_exhausted",
)
#: `audit_log.entity_type` → the History's word for it.
HISTORY_AUDIT_TYPES = {"tax": "tax", "discount": "discount", "discount_version": "discount"}


class Entry:
    """One History line, from either source. `record_type`/`record_id` are the
    row's OWN entity (a tax VERSION, a discount version); `entity_id` is what a
    screen links to (a discount version → its discount)."""

    __slots__ = (
        "id", "created_at", "entity_type", "entity_id", "before", "after", "reason",
        "actor_id", "batch_id", "action", "record_type", "record_id",
    )

    def __init__(self, **values: Any) -> None:
        for name in self.__slots__:
            setattr(self, name, values.get(name))


def entry_of(row: Any) -> Entry:
    """A `rate_change_log` row, or one row of a UNION of `_`-prefixed columns
    (`selectors.history_list_queryset`, `plan_reads.plan_audit_queryset`)."""
    if isinstance(row, dict):
        raw_type = row["_etype"]
        return Entry(
            id=row["_rid"],
            created_at=row["_at"],
            entity_type=HISTORY_AUDIT_TYPES.get(raw_type, raw_type),
            entity_id=row["_eid"],
            before=row["_before"],
            after=row["_after"],
            reason=row.get("_reason") or "",
            actor_id=row["_actor"],
            batch_id=row.get("_batch"),
            action=row.get("_act"),
            record_type=raw_type,
            record_id=row.get("_vid") or row["_eid"],
        )
    return Entry(
        id=row.id,
        created_at=row.created_at,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        before=row.before,
        after=row.after,
        reason=row.reason,
        actor_id=row.actor_id,
        batch_id=row.batch_id,
        action=None,
        record_type=row.entity_type,
        record_id=row.entity_id,
    )


def pair_successors(entries: list[Entry]) -> None:
    """Give a successor's row (a tax's new rate, a correction) the `before` its
    partner stored — one read per kind for the page, never one per row."""
    wanted = [entry for entry in entries if entry.before is None and entry.action in SUCCESSOR_PARTNERS]
    if not wanted:
        return
    from django.db.models import Q

    from apps.rating import discounts as discount_models

    tenant = selectors._tenant_id()
    predecessor: dict[str, Any] = {}
    tax_ids = [entry.record_id for entry in wanted if entry.record_type == "tax"]
    if tax_ids:
        for row in models.Tax.objects.filter(tenant_id=tenant, pk__in=tax_ids).values("id", "follows_id", "corrects_id"):
            predecessor[str(row["id"])] = row["corrects_id"] or row["follows_id"]
    version_ids = [entry.record_id for entry in wanted if entry.record_type == "discount_version"]
    if version_ids:
        for row in discount_models.DiscountVersion.objects.filter(tenant_id=tenant, pk__in=version_ids).values(
            "id", "corrects_id"
        ):
            predecessor[str(row["id"])] = row["corrects_id"]
    ids = [str(one) for one in predecessor.values() if one]
    if not ids:
        return
    partners: dict[tuple[str, str], list[Any]] = {}
    for row in seams.rating_audit_queryset(Q(entity_id__in=ids, action__in=PARTNER_ACTIONS)):
        partners.setdefault((str(row.entity_id), row.action), []).append(row)
    for entry in wanted:
        before_id = predecessor.get(str(entry.record_id))
        candidates = [
            row
            for row in partners.get((str(before_id), SUCCESSOR_PARTNERS[entry.action]), [])
            if entry.created_at is None or row.created_at <= entry.created_at
        ]
        if candidates:
            chosen = max(candidates, key=lambda row: row.created_at)
            if isinstance(chosen.before, dict):
                entry.before = chosen.before


def change_lists(entries: list[Entry], extra_actors: list[Any] | None = None) -> tuple[list[list[dict[str, str]]], _Names]:
    """Every entry's `[{field, before, after}]` with one name batch for the page —
    History and a plan's Audit tab word a change through this one function."""
    pair_successors(entries)
    names = _Names(
        [entry.before for entry in entries] + [entry.after for entry in entries],
        [entry.actor_id for entry in entries] + list(extra_actors or []),
    )
    return [changes(entry.before, entry.after, names) for entry in entries], names


def snapshot_changes(pairs: list[tuple[Any, Any]]) -> list[list[dict[str, str]]]:
    """`changes` for several `(before, after)` snapshot pairs with one name batch
    — the plan Versions table words each version against the one before it in
    History's form (`DEF-RAT-10031`)."""
    names = _Names([before for before, _ in pairs] + [after for _, after in pairs], [])
    return [changes(before, after, names) for before, after in pairs]


def _discount_names(entries: list[Entry]) -> dict[str, str]:
    ids = [
        str(entry.entity_id)
        for entry in entries
        if entry.entity_type == "discount" and selectors._valid_uuid(str(entry.entity_id))
    ]
    if not ids:
        return {}
    from apps.rating import discounts as discount_models

    return {
        str(pk): name
        for pk, name in discount_models.Discount.objects.filter(tenant_id=selectors._tenant_id(), pk__in=ids).values_list(
            "id", "name"
        )
    }


def history_rows(entries: list[Any]) -> list[dict[str, Any]]:
    """The S9 History rows for one page — list and dialog read the same rows.
    Takes `rate_change_log` rows or the History UNION's rows (`entry_of`)."""
    entries = [entry_of(row) for row in entries]
    if not entries:
        return []
    batch_actor = {
        str(row["id"]): row["actor_id"]
        for row in models.RateChangeBatch.objects.filter(
            pk__in={entry.batch_id for entry in entries if entry.batch_id}
        ).values("id", "actor_id")
    }
    found_all, names = change_lists(entries, list(batch_actor.values()))
    discount_names = _discount_names(entries)
    rows = []
    for entry, found in zip(entries, found_all, strict=True):
        publisher = batch_actor.get(str(entry.batch_id)) if entry.batch_id else None
        snapshot = entry.after if isinstance(entry.after, dict) else entry.before
        name = snapshot.get("name") if isinstance(snapshot, dict) else None
        if entry.entity_type == "discount":
            name = discount_names.get(str(entry.entity_id)) or name
        rows.append(
            {
                "id": str(entry.id),
                "changed_at": entry.created_at.isoformat() if entry.created_at else None,
                "entity_type": entry.entity_type,
                "entity_id": str(entry.entity_id),
                "entity_name": name,
                # The stored payloads stay on the API and the CSV export (a
                # regulator's copy); no screen prints them.
                "before": entry.before,
                "after": entry.after,
                "reason": entry.reason,
                # The id is the History filter's value only; the screen prints `actor.name`.
                "actor_user_id": selectors._uuid_or_none(entry.actor_id),
                "actor": {"name": names.users.get(str(entry.actor_id)) if entry.actor_id else None},
                "batch_id": selectors._uuid_or_none(entry.batch_id),
                "is_batch": entry.batch_id is not None,
                "published_by": {"name": names.users.get(str(publisher)) if publisher else None},
                "before_kept": isinstance(entry.before, dict),
                "changes": found,
                "change_count": len(found),
            }
        )
    return rows
