# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 2 task 3 — the three per-utility discount lists
#          (Program owner · Exclusivity group · Who qualifies), editable on
#          Settings › Reference data, and the server's half of
#          `GET /discounts/form-options` (CR-166 §9).
# Rules:   BR-TEN-031 (the owning module validates and writes its lists) ·
#          BR-TEN-036 (seeded rows deactivate, never delete) · BR-TEN-030/034
#          (a code freezes once used) · BR-RAT-076 (Automatic + proof refused) ·
#          PO 2026-10-03 rulings 3 (Automatic = a system-checked condition)
# Tests:   06-backend/tests/test_cr166_discounts_round2.py
# ───────────────────────────────────────────────────────
"""The three dropdowns a utility edits for its discounts, and the form's lists.

HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING — AI-authored 2026-10-03 (CR-166-BRC10 r2
t3) under the PO ruling of 2026-08-09. A `system` who-qualifies value's
`check_key` decides who the automatic-enrolment job GRANTS a subsidy to, so it
is reviewed with `discount_enrolment_job.py`. Row in
`12-governance/09-human-review-ledger.md`.

WHAT THE PO RULED, AND WHAT THEY DID NOT
----------------------------------------
PO 2026-10-03, verbatim: *"Program owner - make this drop down - give it
values"*, *"Exclusivity group - can you make this drop down"*, *"Who qualifies *
- drop down"*. The VALUES below are the coordinator's, shown in the approved
mock-up and recorded in the decision log as *"recommended editable per utility
in Settings, NOT ruled"* — so they are SEEDED DEFAULTS a utility edits, never
law, exactly as fire's six sizes are (CLAUDE.md's opening line).

THE STORED THING IS A CODE
--------------------------
A discount stores the code of a list value, never a foreign key: a version is
history (BR-RAT-037), and a utility renaming *Billing* to *Billing office* must
re-label every discount without touching one row of priced history. So a code
FREEZES once any discount carries it (BR-TEN-030's shape), and a seeded value
is deactivated rather than deleted (BR-TEN-036).

⚖️ **`assistance` — RULED 2026-10-03 (`CR-166` §7 open item 1).** Today CAP and
SENIOR share the free-text group *assistance*, so a senior on CAP gets ONE of
the two. Putting CAP in *Low-income programs* and SENIOR in *Age-based* would
let them STACK ($25.00 off a $60.00 bill becoming $25.00 plus up to $9.00
more). PO, verbatim: *"A Keep them excluding each other, so the customer gets
one of the two"*. So `assistance` maps to the utility's OWN group code
`assistance` labelled **Assistance programs** (`LEGACY_EXCLUSIVITY_GROUPS`),
never to either drawn group, and both discounts keep sharing it. The six drawn
groups stay the seeded defaults for new discounts.
"""

from __future__ import annotations

import re
from typing import Any

from django.db.models import Q

from apps.rating import discounts as discount_models
from core import errors
from core import tenancy as core_tenancy

# ── the seeded defaults — the drawing's values (README point 3) ─────────────
#: (code, label, checked_by, check_key). Order is the drawing's order.
SEEDED_PROGRAM_OWNERS: tuple[tuple[str, str], ...] = (
    ("billing", "Billing"),
    ("customer_service", "Customer service"),
    ("finance", "Finance"),
    ("conservation", "Conservation"),
    ("community_programs", "Community programs"),
    ("city_or_county_agency", "City or county agency"),
    ("state_agency", "State agency"),
    ("nonprofit_partner", "Nonprofit partner"),
)
SEEDED_EXCLUSIVITY_GROUPS: tuple[tuple[str, str], ...] = (
    (discount_models.EXCLUSIVITY_NONE, "None"),
    ("low_income", "Low-income programs"),
    ("age_based", "Age-based"),
    ("payment_method", "Payment method"),
    ("government_municipal", "Government and municipal"),
    ("military_veterans", "Military and veterans"),
)
SEEDED_ELIGIBILITY: tuple[tuple[str, str, str, str | None], ...] = (
    # The system checks
    ("everyone", "Everyone on the plan", "system", discount_models.CHECK_EVERYONE),
    ("autopay_on", "Autopay is on", "system", discount_models.CHECK_AUTOPAY),
    ("paperless_on", "Paperless billing is on", "system", discount_models.CHECK_PAPERLESS),
    (
        "government_account",
        "Government or municipal account",
        "system",
        discount_models.CHECK_GOVERNMENT,
    ),
    # The customer shows proof
    ("age_65_or_over", "Age 65 or over", "proof", None),
    ("household_income_limit", "Household income under a limit", "proof", None),
    ("state_assistance_program", "In a state assistance program", "proof", None),
    ("veteran_or_military", "Veteran or active military", "proof", None),
    ("disability", "Person with a disability", "proof", None),
    ("medical_equipment", "Medical equipment at home", "proof", None),
    ("nonprofit_or_worship", "Nonprofit or place of worship", "proof", None),
)

#: `CR-166` §7 open item 3 — our judgment, recorded in the decision log: the
#: who-qualifies words the product shipped before the list existed, and the
#: drawn value each one MEANS. Matched case-insensitively. Anything else is
#: kept as the utility's own *customer shows proof* value (`map_or_add`).
LEGACY_ELIGIBILITY_TEXT: dict[str, str] = {
    "autopay enrolled": "autopay_on",
    "e-bill on": "paperless_on",
    "government account": "government_account",
    "age 65+": "age_65_or_over",
    "veteran id": "veteran_or_military",
    "program enrolment": "state_assistance_program",
}

#: `CR-166` §9 — the documents a *customer shows proof* condition accepts,
#: DERIVED from the condition because the approved drawing has no *documents
#: accepted* box (coordinator relay 2026-10-03; our judgment, decision log).
#: Every kind is one of `discounts.PROOF_KINDS`; restriction still derives from
#: the kind (BR-RAT-079). A value a utility added, or one not listed, accepts
#: `PROOF_DEFAULT` — a government ID or the utility's own record.
PROOF_BY_ELIGIBILITY: dict[str, list[str]] = {
    "age_65_or_over": ["government_id", "birth_certificate"],
    "household_income_limit": ["income_statement", "tax_return"],
    "state_assistance_program": ["programme_award_letter", "agency_file"],
    "veteran_or_military": ["veteran_id"],
    "disability": ["disability_award", "medical_certification"],
    "medical_equipment": ["medical_certification"],
    "nonprofit_or_worship": ["tax_return", "utility_record"],
}
PROOF_DEFAULT: list[str] = ["government_id", "utility_record"]


def proof_kinds_for(eligibility_code: str | None) -> list[str]:
    """The documents accepted for a who-qualifies code (see the table above)."""
    return list(PROOF_BY_ELIGIBILITY.get(str(eligibility_code or "").lower(), PROOF_DEFAULT))


#: PO 2026-10-03, verbatim: *"A Keep them excluding each other, so the
#: customer gets one of the two"* — today's free-text group `assistance` (CAP
#: and SENIOR) becomes ONE shared group of the utility's own list. Free text
#: (lower case) → (code, label).
LEGACY_EXCLUSIVITY_GROUPS: dict[str, tuple[str, str]] = {
    "assistance": ("assistance", "Assistance programs"),
}

#: The Settings › Reference data list codes (tenancy's registry) → this
#: module's own list code.
REFERENCE_LISTS: dict[str, str] = {
    "discount_program_owners": discount_models.LIST_PROGRAM_OWNER,
    "discount_exclusivity_groups": discount_models.LIST_EXCLUSIVITY_GROUP,
    "discount_eligibility": discount_models.LIST_ELIGIBILITY,
}

_MAX_LABEL = 60
_MAX_CODE = 40


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def slug(text: str) -> str:
    """A code minted from a label: lower case, words joined by `_`."""
    out = re.sub(r"[^a-z0-9]+", "_", str(text).strip().lower()).strip("_")
    return (out or "value")[:_MAX_CODE]


def seeded_rows(list_code: str) -> list[dict[str, Any]]:
    """The drawing's values for one list, as row dicts, in the drawing's order."""
    if list_code == discount_models.LIST_PROGRAM_OWNER:
        return [
            {"code": code, "label": label, "checked_by": None, "check_key": None}
            for code, label in SEEDED_PROGRAM_OWNERS
        ]
    if list_code == discount_models.LIST_EXCLUSIVITY_GROUP:
        return [
            {"code": code, "label": label, "checked_by": None, "check_key": None}
            for code, label in SEEDED_EXCLUSIVITY_GROUPS
        ]
    if list_code == discount_models.LIST_ELIGIBILITY:
        return [
            {"code": code, "label": label, "checked_by": by, "check_key": key}
            for code, label, by, key in SEEDED_ELIGIBILITY
        ]
    raise KeyError(list_code)


def seed_lists(tenant_id: Any = None, model: Any = None) -> int:
    """Insert-missing the drawn values for this utility. Returns rows created.

    Idempotent by `(list_code, code)` case-insensitively; a row the utility has
    renamed or deactivated is LEFT ALONE (BR-TEN-012). `model` lets the data
    migration pass its historical model.
    """
    tenant_id = tenant_id or _tenant_id()
    model = model or discount_models.DiscountListValue
    created = 0
    for list_code in discount_models.DISCOUNT_LIST_CODES:
        for index, row in enumerate(seeded_rows(list_code)):
            if model.objects.filter(
                tenant_id=tenant_id, list_code=list_code, code__iexact=row["code"]
            ).exists():
                continue
            model.objects.create(
                tenant_id=tenant_id,
                list_code=list_code,
                code=row["code"],
                label=row["label"],
                checked_by=row["checked_by"],
                check_key=row["check_key"],
                is_system=True,
                active=True,
                sort_order=(index + 1) * 10,
            )
            created += 1
    return created


def map_or_add(list_code: str, text: Any, tenant_id: Any = None, model: Any = None) -> str | None:
    """Today's FREE TEXT → the code of this utility's list value that means it.

    `CR-166` §7 open items 2 and 3, our judgment (decision log 2026-10-03):
      1. empty → None;
      2. an existing CODE or LABEL of this list, case-insensitively → that code;
      3. eligibility only: a legacy phrase in `LEGACY_ELIGIBILITY_TEXT` → its
         drawn value;
      4. otherwise the text is ADDED to this utility's own list, verbatim as
         the label, so no recorded fact changes (an eligibility value added
         this way is *customer shows proof* — the product cannot check a
         sentence it does not know).

    ⚠ `assistance` is the ruled exception (`LEGACY_EXCLUSIVITY_GROUPS`): ONE
    shared group *Assistance programs*, never a drawn one (see the
    module docstring): it matches no drawn label, so it is added, named exactly
    as today, and CAP and SENIOR keep sharing it.
    """
    value = str(text or "").strip()
    if not value:
        return None
    tenant_id = tenant_id or _tenant_id()
    model = model or discount_models.DiscountListValue
    rows = model.objects.filter(tenant_id=tenant_id, list_code=list_code)
    hit = rows.filter(Q(code__iexact=value) | Q(label__iexact=value)).first()
    if hit is not None:
        return hit.code
    if list_code == discount_models.LIST_ELIGIBILITY:
        legacy = LEGACY_ELIGIBILITY_TEXT.get(value.lower())
        if legacy and rows.filter(code__iexact=legacy).exists():
            return legacy
    if list_code == discount_models.LIST_EXCLUSIVITY_GROUP:
        ruled = LEGACY_EXCLUSIVITY_GROUPS.get(value.lower())
        if ruled is not None:
            ruled_code, ruled_label = ruled
            model.objects.create(
                tenant_id=tenant_id,
                list_code=list_code,
                code=ruled_code,
                label=ruled_label,
                is_system=False,
                active=True,
                sort_order=1000,
            )
            return ruled_code
    code = slug(value)
    base, n = code, 2
    while rows.filter(code__iexact=code).exists():
        code = f"{base[: _MAX_CODE - 4]}_{n}"
        n += 1
    model.objects.create(
        tenant_id=tenant_id,
        list_code=list_code,
        code=code,
        label=value[:_MAX_LABEL] if len(value) > _MAX_LABEL else value,
        checked_by=(
            discount_models.CHECKED_BY_PROOF
            if list_code == discount_models.LIST_ELIGIBILITY
            else None
        ),
        check_key=None,
        is_system=False,
        active=True,
        sort_order=1000,
    )
    return code


# ── reads ───────────────────────────────────────────────────────────────────
def value_row(list_code: str, code: str | None) -> Any:
    """This utility's list row for a stored code, or None."""
    if not code:
        return None
    return discount_models.DiscountListValue.objects.filter(
        tenant_id=_tenant_id(), list_code=list_code, code__iexact=code
    ).first()


def as_option(list_code: str, code: str | None) -> dict[str, Any] | None:
    """`{value, label}` (eligibility also `checked_by`) for a stored code.

    ⚠ A code with no row (a value deleted after it was stored, which the
    used-by lock is meant to prevent) is served with its code as the label
    rather than as null: the discount DOES carry it, and a blank would say it
    carries nothing. The exclusivity group's NULL is *None*.
    """
    if list_code == discount_models.LIST_EXCLUSIVITY_GROUP and not code:
        row = value_row(list_code, discount_models.EXCLUSIVITY_NONE)
        return {
            "value": discount_models.EXCLUSIVITY_NONE,
            "label": row.label if row is not None else "None",
        }
    if not code:
        return None
    row = value_row(list_code, code)
    out: dict[str, Any] = {"value": code, "label": row.label if row is not None else code}
    if list_code == discount_models.LIST_ELIGIBILITY:
        out["checked_by"] = (
            row.checked_by if row is not None and row.checked_by else discount_models.CHECKED_BY_PROOF
        )
    return out


def options(list_code: str) -> list[dict[str, Any]]:
    """The ACTIVE values of one list, in order — what a dropdown offers."""
    rows = discount_models.DiscountListValue.objects.filter(
        tenant_id=_tenant_id(), list_code=list_code, active=True
    ).order_by("sort_order", "label", "id")
    out = []
    for row in rows:
        option: dict[str, Any] = {"value": row.code, "label": row.label}
        if list_code == discount_models.LIST_ELIGIBILITY:
            option["checked_by"] = row.checked_by or discount_models.CHECKED_BY_PROOF
        out.append(option)
    return out


def check_key_for(code: str | None) -> str | None:
    """The system check behind an eligibility code, or None (a proof value)."""
    row = value_row(discount_models.LIST_ELIGIBILITY, code)
    if row is None or row.checked_by != discount_models.CHECKED_BY_SYSTEM:
        return None
    return row.check_key


# ── write-side validation — one gate per list, every door uses it ──────────
def clean_code(list_code: str, field: str, raw: Any, fe: list[dict[str, Any]]) -> Any:
    """A submitted code → the stored value, or a field error naming the field.

    Returns `...` (Ellipsis) when the field is refused, so a caller can tell
    *refused* from *cleared* (None).
    """
    value = str(raw or "").strip()
    if not value:
        return None
    if list_code == discount_models.LIST_EXCLUSIVITY_GROUP and value.lower() == (
        discount_models.EXCLUSIVITY_NONE
    ):
        return None
    row = value_row(list_code, value)
    if row is None:
        # A LABEL is accepted as well as a code, case-insensitively, so a
        # screen that has not moved to the dropdown yet (it sends the words it
        # shows) lands on the same value instead of a refusal.
        row = discount_models.DiscountListValue.objects.filter(
            tenant_id=_tenant_id(), list_code=list_code, label__iexact=value
        ).first()
    if row is None or not row.active:
        fe.append(
            {
                "field": field,
                "code": errors.VAL_UNKNOWN_LOOKUP,
                "message_key": f"rating.discounts.unknown_{list_code}",
                "params": {"value": value},
            }
        )
        return ...
    return row.code


# ── Settings › Reference data — one handler, three lists (BR-TEN-031) ──────
class DiscountListHandler:
    """The S8 card for one discount list. Mints, renames, deactivates and
    deletes VALUES; a value a discount carries keeps its code (BR-TEN-030) and
    cannot be deleted (BR-TEN-034); a seeded value is never deleted
    (BR-TEN-036); a utility cannot invent a new *system* check (ruling 3)."""

    def __init__(self, list_code: str) -> None:
        self.list_code = list_code
        self.model = discount_models.DiscountListValue

    def _qs(self) -> Any:
        return self.model.objects.filter(tenant_id=_tenant_id(), list_code=self.list_code)

    def search(self, q: str | None) -> Any:
        qs = self._qs().order_by("sort_order", "label", "id")
        if q and len(q.strip()) >= 2:
            term = q.strip()
            qs = qs.filter(Q(code__icontains=term) | Q(label__icontains=term))
        return qs

    def count(self) -> int:
        return self._qs().count()

    def get(self, entry_id: Any) -> Any:
        try:
            return self._qs().filter(pk=entry_id).first()
        except (ValueError, TypeError):
            return None

    def used_by(self, row: Any) -> int:
        """How many discounts carry this code (any version, any status)."""
        if self.list_code == discount_models.LIST_PROGRAM_OWNER:
            return discount_models.Discount.objects.filter(
                tenant_id=_tenant_id(), programme_owner__iexact=row.code
            ).count()
        field = (
            "exclusivity_group__iexact"
            if self.list_code == discount_models.LIST_EXCLUSIVITY_GROUP
            else "eligibility_code__iexact"
        )
        return (
            discount_models.DiscountVersion.objects.filter(tenant_id=_tenant_id(), **{field: row.code})
            .values("discount_id")
            .distinct()
            .count()
        )

    def serialize(self, row: Any) -> dict[str, Any]:
        out = {
            "id": str(row.pk),
            "code": row.code,
            "name": row.label,
            "active": row.active,
            "is_system": row.is_system,
            "used_by": self.used_by(row),
        }
        if self.list_code == discount_models.LIST_ELIGIBILITY:
            out["checked_by"] = row.checked_by or discount_models.CHECKED_BY_PROOF
        return out

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        allowed = {"code", "name"}
        if self.list_code == discount_models.LIST_ELIGIBILITY:
            allowed.add("checked_by")
        for field in sorted(set(payload) - allowed):
            fe.append(_fe(field, errors.VAL_FORMAT, "rating.lookups.unknown_field"))
        out: dict[str, Any] = {}
        for field, column, limit in (("code", "code", _MAX_CODE), ("name", "label", _MAX_LABEL)):
            if field in payload:
                value = str(payload[field] or "").strip()
                if not value:
                    fe.append(_fe(field, errors.VAL_REQUIRED, "rating.lookups.required"))
                elif len(value) > limit:
                    fe.append(_fe(field, errors.VAL_RANGE, "rating.lookups.too_long", max=limit))
                else:
                    out[column] = value
            elif not partial:
                fe.append(_fe(field, errors.VAL_REQUIRED, "rating.lookups.required"))
        if "checked_by" in payload:
            # Ruling 3: a *system* value is one the product can run. A utility
            # adds PROOF values; the four checks are seeded and fixed.
            if str(payload["checked_by"] or "") != discount_models.CHECKED_BY_PROOF:
                fe.append(
                    _fe(
                        "checked_by",
                        errors.VAL_RANGE,
                        "rating.discounts.list_system_check_fixed",
                    )
                )
        _raise(fe)
        return out

    def _check_duplicate(self, code: str, exclude_pk: Any = None) -> None:
        qs = self._qs().filter(code__iexact=code)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        existing = qs.first()
        if existing is not None:
            _raise(
                [
                    _fe(
                        "code",
                        errors.VAL_FORMAT,
                        "rating.lookups.duplicate_code",
                        existing=existing.code,
                    )
                ]
            )

    def create(self, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=False)
        self._check_duplicate(cleaned["code"])
        return self.model.objects.create(
            tenant_id=_tenant_id(),
            list_code=self.list_code,
            checked_by=(
                discount_models.CHECKED_BY_PROOF
                if self.list_code == discount_models.LIST_ELIGIBILITY
                else None
            ),
            is_system=False,
            active=True,
            sort_order=1000,
            **cleaned,
        )

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=True)
        if "code" in cleaned and cleaned["code"].lower() != row.code.lower():
            if row.is_system or self.used_by(row) > 0:
                # BR-TEN-030: a code a discount carries (or a seeded one) is
                # frozen — renaming it would orphan every discount storing it.
                _raise(
                    [
                        _fe(
                            "code",
                            errors.VAL_FORMAT,
                            "rating.discounts.list_code_frozen",
                            existing=row.code,
                        )
                    ]
                )
            self._check_duplicate(cleaned["code"], exclude_pk=row.pk)
        for field, value in cleaned.items():
            setattr(row, field, value)
        if cleaned:
            row.save(update_fields=[*cleaned.keys(), "updated_at"])
        return row

    def set_active(self, row: Any, active: bool) -> Any:
        row.active = bool(active)
        row.save(update_fields=["active", "updated_at"])
        return row

    def delete(self, row: Any) -> None:
        if row.is_system:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-TEN-036",
                message_key="settings.lookups.system_row_not_deletable",
                params={"code": row.code},
            )
        row.delete()


def _fe(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _raise(fe: list[dict[str, Any]]) -> None:
    if fe:
        raise errors.ValidationError(
            fe[0]["code"],
            message_key=fe[0]["message_key"],
            params=fe[0]["params"],
            field_errors=fe,
        )

