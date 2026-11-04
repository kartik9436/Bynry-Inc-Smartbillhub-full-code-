# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-009 (the S8 Reference-data card grid — the two rating cards
#           that could not render) · US-TEN-010 (per-list add / edit) ·
#           US-TEN-011 (deactivate / delete lock) · US-RAT-008 (charge codes are
#           rating's content + validation) · US-RAT-009 (tenant-entered tax
#           jurisdictions)   Screens: S8 (Settings → Reference data), S12, S13
# Rules:    BR-TEN-031 (framework is tenancy's, CONTENT + validation belong to
#           the owning module — rating owns charges/tax) · BR-TEN-030 (codes
#           unique per list per tenant, case-insensitive; code immutable once
#           used) · BR-TEN-034 (Used-by > 0 → hard delete blocked, deactivate
#           allowed) · BR-TEN-036 (seeded defaults, tenant-extensible) ·
#           BR-TEN-037 (tax jurisdictions are TENANT-entered, no global
#           registry) · BR-TEN-029 (used-by + card counts computed live) ·
#           BR-RAT-035 (charge audit-lock inputs) · BR-SHL-035 (one shared list
#           view binds every card)
# Tests:    06-backend/tests/test_us_rat_charges_taxes.py (per-TC, extended)
# Impacts:  apps.tenancy LOOKUP_LISTS `charge_codes` + `tax_jurisdictions`
#           (declared with owner "rating", handler=None until now) ·
#           GET/POST/PATCH/DELETE /lookups/{list} · the S8 card grid count
# ───────────────────────────────────────────────────────
"""The /lookups handlers rating owns (BR-TEN-031 duck-typed contract: search ·
count · get · serialize · used_by · create · update · set_active · delete).

Both lists were declared in tenancy's registry with no handler, so their S8
cards could not render at all. Content validation lives HERE — the owning
module's law — and stays deliberately NARROW: the reference card mints and
renames the CODE, while the money-bearing fields (amount, percent, minimum,
GL account, tax rate, filing) belong to the S12/S13 screens and rating's own
endpoints. A reference card that could set an amount would be a back door into
B4-governed money configuration; this one cannot.

Two schema gaps, reported and NOT worked around (the tables are outside this
lane's territory and neither rule anchors the column):

1. **No `is_system` column** on `charges` or `tax_jurisdictions` (B2 §rating
   DDL has none, and neither r6.5 nor r6.6 adds one). A seeded row is therefore
   INDISTINGUISHABLE from a tenant-added one, so the "seeded rows are
   deactivatable but never deletable" half of BR-TEN-036 cannot be enforced for
   these two lists the way it is for the assets catalogs. `is_system` is served
   as `false` — the honest answer for a column that does not exist — and the
   BR-TEN-034 audit-lock (Used-by > 0 → no delete), which tenancy enforces from
   `used_by`, is the guard that IS live here. Candidate schema addition,
   flagged; nothing here pretends otherwise.

2. **No `code` and no active/`deleted_at` column** on `tax_jurisdictions` — the
   table is `name · authority · level · reference_no`. The shared list view
   (BR-SHL-035) is code+name, so the framework's `code` slot is served by the
   jurisdiction's NAME, which IS this list's identity (BR-TEN-030's uniqueness
   is applied to it, case-insensitively). And with no active column, there is
   nowhere to record a deactivation: `set_active` REFUSES loudly rather than
   accepting a click that would change nothing. Both are candidate schema
   additions, flagged.

`charges` carries `deleted_at`, which US-RAT-008 TC-7 already treats as the
deactivate flag (apps/rating/services.set_charge_active) — the charge-code card
reuses that exact convention rather than inventing a second one.
"""

import logging
from typing import Any

from django.db.models import Q
from django.db.models.functions import Now

from apps.rating import models, selectors
from core import errors
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.rating")

_MAX_CODE = 20  # rating's own charge-code length (services._validate_charge)
_MAX_NAME = 120  # rating's own charge-name length


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _field_error(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _refuse(field_errors: list[dict[str, Any]]) -> None:
    if field_errors:
        raise errors.ValidationError(
            field_errors[0]["code"],
            message_key=field_errors[0]["message_key"],
            params=field_errors[0]["params"],
            field_errors=field_errors,
        )


def _clean_text(
    payload: dict[str, Any],
    field: str,
    fe: list[dict[str, Any]],
    *,
    required: bool,
    max_length: int,
) -> str | None:
    if field not in payload:
        if required:
            fe.append(_field_error(field, errors.VAL_REQUIRED, "rating.lookups.required"))
        return None
    value = str(payload[field] or "").strip()
    if not value:
        fe.append(_field_error(field, errors.VAL_REQUIRED, "rating.lookups.required"))
        return None
    if len(value) > max_length:
        fe.append(_field_error(field, errors.VAL_RANGE, "rating.lookups.too_long", max=max_length))
        return None
    return value


class ChargeCodeLookupHandler:
    """/lookups/charge_codes — the S8 card over rating's `charges` catalog
    (BR-TEN-031: rating owns the content). The card mints and renames codes;
    amounts, percents, minimums and GL accounts stay with S12 (US-RAT-008),
    because a fee's MONEY is rating law, not reference-data plumbing."""

    model = models.Charge

    def _qs(self) -> Any:
        return self.model.objects.filter(tenant_id=_tenant_id())

    def search(self, q: str | None) -> Any:
        qs = self._qs().order_by("code", "id")  # IS-2 stable secondary sort
        if q and len(q.strip()) >= 2:  # IS-3 server-side, min 2 chars
            term = q.strip()
            qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
        return qs

    def count(self) -> int:
        return self._qs().count()

    def get(self, entry_id: Any) -> Any:
        try:
            return self._qs().filter(pk=entry_id).first()
        except (ValueError, TypeError):  # a non-uuid id is simply absent
            return None

    def used_by(self, row: Any) -> int:
        """BR-TEN-029/034 live count = BR-RAT-035's own audit-lock inputs: plan
        attachments (local) + invoice lines (billing seam).

        ⚠ **AN UNANSWERABLE INVOICE-LINE COUNT COUNTS AS IN-USE, NOT AS ZERO**
        (DEF-079). This used to add `int(used["invoice_lines"])` over a seam
        that returned 0 whenever billing published nothing, and the count feeds
        BR-TEN-030/034 — a code freezes once used, and a used row cannot be
        deleted. A 0 nobody could verify would unfreeze a code live bills cite.
        `None` therefore contributes 1: the screen says *in use*, the delete
        refuses, and a clerk sees a lock rather than a silent success.
        """
        used = selectors.charge_used_by(row)
        lines = used["invoice_lines"]
        return int(used["plans"]) + (1 if lines is None else int(lines))

    def serialize(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(row.pk),
            "code": row.code,
            "name": row.name,
            # US-RAT-008 TC-7's own convention: deleted_at set = deactivated.
            "active": row.deleted_at is None,
            "is_system": False,  # no column exists — module docstring, gap 1
            "used_by": self.used_by(row),
            # The card's third column (BR-SHL-035 detail slot): what KIND of
            # charge it is. Money fields deliberately absent — S12 owns those.
            "charge_type": row.charge_type,
        }

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        allowed = {"code", "name"}
        for field in sorted(set(payload) - allowed):
            # Money fields land here if a client tries the back door: refused
            # by name so the message says where they belong (S12).
            fe.append(_field_error(field, errors.VAL_FORMAT, "rating.lookups.unknown_field"))
        cleaned: dict[str, Any] = {}
        code = _clean_text(payload, "code", fe, required=not partial, max_length=_MAX_CODE)
        if code is not None:
            cleaned["code"] = code
        name = _clean_text(payload, "name", fe, required=not partial, max_length=_MAX_NAME)
        if name is not None:
            cleaned["name"] = name
        _refuse(fe)
        return cleaned

    def _check_duplicate(self, code: str, exclude_pk: Any = None) -> None:
        qs = self._qs().filter(code__iexact=code)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        existing = qs.first()
        if existing is not None:  # BR-TEN-030 / US-RAT-008 TC-5
            _refuse(
                [
                    _field_error(
                        "code",
                        errors.VAL_FORMAT,
                        "rating.lookups.duplicate_code",
                        existing=existing.code,
                    )
                ]
            )

    def create(self, payload: dict[str, Any]) -> Any:
        """BR-TEN-036 tenant-extensible add. The row is a CODE only: amount_rule
        and the amounts stay NULL until S12 configures them — rating's charge
        validator (which requires amount_rule) governs THAT screen, not this
        card, and a fee amount invented here would be exactly the "guess in
        billing" CLAUDE.md forbids."""
        cleaned = self._validate(payload, partial=False)
        self._check_duplicate(cleaned["code"])
        return self.model.objects.create(tenant_id=_tenant_id(), **cleaned)

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=True)
        if "code" in cleaned and cleaned["code"].lower() != row.code.lower():
            self._check_duplicate(cleaned["code"], exclude_pk=row.pk)
        for field, value in cleaned.items():
            setattr(row, field, value)
        if cleaned:
            row.save(update_fields=[*cleaned.keys(), "updated_at"])
        return row

    def set_active(self, row: Any, active: bool) -> Any:
        """IS-1/BR-TEN-029: deactivation is always allowed, reactivation too.
        `Now()` is the stamp apps/rating/services.set_charge_active uses — the
        database clock, so a deactivation written here and one written through
        S12 are the same act, not two conventions."""
        row.deleted_at = None if active else Now()
        row.save(update_fields=["deleted_at", "updated_at"])
        row.refresh_from_db(fields=["deleted_at"])
        return row

    def delete(self, row: Any) -> None:
        """Hard delete. The BR-TEN-034 audit-lock (Used-by > 0) is enforced by
        tenancy's delete_lookup_entry from `used_by` above, freshly counted
        inside its transaction; there is no is_system row to protect here
        (module docstring, gap 1).

        ⚠ CR-156-BRC10 — a flat amount is an *All sizes* row of
        `charge_code_amounts` now (PROTECT foreign key), so a priced code's
        rows go first, through the one writer; without this a seeded code with
        a price would answer `ProtectedError` (HTTP 500) where it used to
        delete. A code in use never reaches here (the used-by lock above)."""
        from apps.rating import charge_prices

        charge_prices.remove_all(row)
        row.delete()


class TaxJurisdictionLookupHandler:
    """/lookups/tax_jurisdictions — BR-TEN-037: tenant-entered authorities, no
    global registry. The table has no `code` and no active flag (module
    docstring, gap 2): the framework's code slot is the jurisdiction's NAME,
    and deactivation refuses rather than pretending."""

    model = models.TaxJurisdiction

    def _qs(self) -> Any:
        return self.model.objects.filter(tenant_id=_tenant_id())

    def search(self, q: str | None) -> Any:
        qs = self._qs().order_by("name", "id")
        if q and len(q.strip()) >= 2:
            term = q.strip()
            qs = qs.filter(Q(name__icontains=term) | Q(authority__icontains=term))
        return qs

    def count(self) -> int:
        return self._qs().count()

    def get(self, entry_id: Any) -> Any:
        try:
            return self._qs().filter(pk=entry_id).first()
        except (ValueError, TypeError):
            return None

    def used_by(self, row: Any) -> int:
        """BR-TEN-029/034 live count: taxes pointing at this authority (the FK
        is PROTECT, so the database enforces the same lock one layer down) plus
        the plan tax rules written against it."""
        tenant_id = _tenant_id()
        taxes = models.Tax.objects.filter(tenant_id=tenant_id, jurisdiction=row).count()
        plan_rules = models.PlanTaxRule.objects.filter(
            tenant_id=tenant_id, jurisdiction=row
        ).count()
        return taxes + plan_rules

    def serialize(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(row.pk),
            # gap 2: no code column — the NAME is this list's identity.
            "code": row.name,
            "name": row.name,
            "active": True,  # no active/deleted_at column exists (see set_active)
            "is_system": False,  # no column exists — module docstring, gap 1
            "used_by": self.used_by(row),
            # The card's detail slot: which level of government it is (S13).
            "level": row.level,
        }

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        """`code` and `name` both address the one stored column; `authority`,
        `level` and `reference_no` belong to S13 (US-RAT-009) and are refused
        here so the shared card cannot half-fill a tax authority."""
        fe: list[dict[str, Any]] = []
        allowed = {"code", "name"}
        for field in sorted(set(payload) - allowed):
            fe.append(_field_error(field, errors.VAL_FORMAT, "rating.lookups.unknown_field"))
        name = None
        if "name" in payload:
            name = _clean_text(payload, "name", fe, required=True, max_length=_MAX_NAME)
        elif "code" in payload:
            name = _clean_text(payload, "code", fe, required=True, max_length=_MAX_NAME)
        elif not partial:
            fe.append(_field_error("name", errors.VAL_REQUIRED, "rating.lookups.required"))
        _refuse(fe)
        return {"name": name} if name is not None else {}

    def _check_duplicate(self, name: str, exclude_pk: Any = None) -> None:
        qs = self._qs().filter(name__iexact=name)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        existing = qs.first()
        if existing is not None:  # BR-TEN-030, applied to this list's identity
            _refuse(
                [
                    _field_error(
                        "code",
                        errors.VAL_FORMAT,
                        "rating.lookups.duplicate_code",
                        existing=existing.name,
                    )
                ]
            )

    def create(self, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=False)
        self._check_duplicate(cleaned["name"])
        return self.model.objects.create(tenant_id=_tenant_id(), **cleaned)

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=True)
        if "name" in cleaned and cleaned["name"].lower() != row.name.lower():
            self._check_duplicate(cleaned["name"], exclude_pk=row.pk)
        if cleaned:
            for field, value in cleaned.items():
                setattr(row, field, value)
            row.save(update_fields=[*cleaned.keys(), "updated_at"])
        return row

    def set_active(self, row: Any, active: bool) -> Any:
        """No active/deleted_at column exists on `tax_jurisdictions` (module
        docstring, gap 2). Accepting the click would record NOTHING and the row
        would keep appearing in pickers, so the refusal is loud and names the
        gap — BR-TEN-029's deactivate semantics have no storage here yet."""
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-TEN-029",
            message_key="rating.lookups.deactivate_unsupported",
            params={"list": "tax_jurisdictions", "name": row.name},
        )

    def delete(self, row: Any) -> None:
        """Hard delete; the BR-TEN-034 Used-by lock is applied by tenancy from
        `used_by` above (and PROTECT enforces it again in the database)."""
        row.delete()


def register() -> None:
    """Called from AppConfig.ready(). tenancy's registry raises KeyError for a
    list code it does not declare — logged and skipped so a registry that has
    not landed a list cannot break startup (skip-until-wired)."""
    from apps.rating import discount_lists
    from apps.tenancy import services as tenancy_services

    for list_code, handler in (
        ("charge_codes", ChargeCodeLookupHandler()),
        ("tax_jurisdictions", TaxJurisdictionLookupHandler()),
        # CR-166-BRC10 — the three discount dropdowns, one handler class.
        *(
            (reference_code, discount_lists.DiscountListHandler(own_code))
            for reference_code, own_code in discount_lists.REFERENCE_LISTS.items()
        ),
    ):
        try:
            tenancy_services.register_lookup_handler(list_code, handler)
        except KeyError:  # pragma: no cover - the registry declares both today
            logger.warning(
                "tenancy LOOKUP_LISTS has no %r entry — handler not registered", list_code
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-009@178c282 (EP-TEN-07 reference-data epic — the card grid these two handlers make live; also US-TEN-010/011@178c282 · US-RAT-008/009@7d1a8ef for the content law — hash = sha256/7 of each source epic)
# generated: 2026-08-09 by story-coder v1 (API-gap lane — the two declared-but-unhandled Reference-data lists)
# checklist: A✔ B✔ C✔ D=deferred(served through tenancy's /lookups endpoints — no route of its own) E=deferred(no-frontend-half — the shared card view already exists) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ py_compile✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (green at handoff in a SHARED tree — concurrent tenancy/settings + billing/payments lanes landed work during this lane; 594 was the baseline when this lane started, this lane adds 26 active TCs + 2 isolation halves) · run_gates 11-PASS/0-FAIL/1-SKIP✔ (this lane adds no migration and no 🔒 guarded file; a transient G7 FAIL seen mid-lane was a CONCURRENT lane's un-ledgered migration and cleared when they landed its row) · trace_lint✔ · mypy NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: NO `is_system` column on charges/tax_jurisdictions (B2 §rating; r6.5/r6.6 add none) — seeded rows are indistinguishable from tenant rows, so BR-TEN-036's "system rows never deletable" cannot bite for these two lists; served as false, BR-TEN-034's used-by lock is the guard that IS live — REPORTED as a candidate schema addition, not invented · NO `code` column on tax_jurisdictions — the framework's code slot is served by `name` (this list's identity; BR-TEN-030 uniqueness applied to it) — REPORTED · NO active/deleted_at column on tax_jurisdictions — set_active REFUSES (409 BIZ-STATE, BR-TEN-029) instead of accepting a click that records nothing — REPORTED · the cards create/rename CODES only; amounts, percents, GL accounts, rates and filing fields are refused as unknown fields and stay with S12/S13 (a reference card must never be a back door into B4-governed money config) · rating implements NO `seed_reference_list` seam yet (apps/rating/services.py — outside this lane's territory), so the W0 `charge_codes`/`tax_jurisdictions` fixture entries are still SKIPPED at provisioning and both cards start empty on a fresh tenant; one function there fixes it — REPORTED · the tax_jurisdictions fixture entries carry `code` + `rate`, which the jurisdiction table has no columns for (they read like TAXES, not jurisdictions) — REPORTED to the PO batch, fixture untouched
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
