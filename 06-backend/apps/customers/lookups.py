# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-009 (the S8 Reference-data card grid — the two customers
#           cards that could not render) · US-TEN-010 (per-list add / edit) ·
#           US-TEN-011 (deactivate / delete lock) · US-CUS-001 (the S17 status
#           pill vocabulary these cards own) · US-CUS-003 (the S18 customer-type
#           select)   Screens: S8 · S17 · S18
# Rules:    BR-TEN-031 (framework is tenancy's; CONTENT + validation belong to
#           the owning module) · BR-TEN-030 (codes unique per list per tenant,
#           case-insensitive; code immutable once used) · BR-TEN-034 (Used-by
#           > 0 → hard delete blocked, deactivate allowed) · BR-TEN-036
#           (seeded defaults, tenant-extensible; a seeded row is deactivatable
#           but never deletable) · BR-TEN-029 (used-by + card counts computed
#           live) · BR-CUS-055 (five seeded statuses, tenant-extensible, every
#           one behaviour-class mapped) · BR-CUS-016 (stored status comes from
#           this lookup)
# Tests:    06-backend/tests/test_us_cus_schema_and_seed.py
# Impacts:  apps.tenancy LOOKUP_LISTS `account_statuses` + `account_types`
#           (declared with owner "customers", handler=None until now) ·
#           GET/POST/PATCH/DELETE /lookups/{list} · the S8 card grid count ·
#           apps.tenancy.services.reference_data_report() (which can only
#           COUNT a list through its registered handler)
# ───────────────────────────────────────────────────────
"""The /lookups handlers customers owns (BR-TEN-031 duck-typed contract:
search · count · get · serialize · used_by · create · update · set_active ·
delete). Content validation lives HERE — the owning module's law.

Both lists were declared in tenancy's registry with owner "customers" and no
handler, so their S8 cards could not render and `reference_data_report()` could
not even count them. That is the second half of the DEF-016 shape: a list can
be seeded and STILL look absent if nothing can count it.

All three cards are the same shape since 2026-09-17. They were not, and the
paragraphs below keep the history because the asymmetry is what the PO's defect
report was actually about:

  · `account_statuses` is TENANT-scoped and tenant-extensible by rule
    (BR-CUS-055; US-CUS-020 TC-3 adds "Legal hold" and maps a legacy code onto
    it). Full CRUD, with `behavior_class` REQUIRED on every row — billing keys
    off the class, so a status without one would be a silent non-billing
    account.

  · `account_types` WAS a PLATFORM table (r5 #12 [D5]: "platform-seeded";
    RLS-excluded) and its card was READ-ONLY for exactly that reason: four rows
    shared by every utility, so a tenant admin renaming one would have renamed
    it for all of them. ⚠ **THE PO REVERSED THAT ON 2026-09-17 — *"utility can
    get their own account types"* — SUPERSEDING `BR-CUS-094`'s platform
    posture.** The table is tenant-scoped and RLS `FORCE`-protected
    (`customers.0054`/`0055`), the ratified seven are the SEED rather than the
    vocabulary, and this card has full CRUD like its two siblings. The three
    cards are now SYMMETRIC, which is worth saying because the asymmetry is
    what made the original defect unreadable: two cards that looked identical
    behaved oppositely.

  · `account_subtypes` (CR-010, 2026-08-17) is the tree's SECOND level: 13
    seeded per tenant, each under one type of the SAME tenant (parent REQUIRED
    — BR-CUS-067), full CRUD. It was the tenant-editable half of [D5] when the
    first level was not; both levels belong to the utility now.

REPORTED, not worked around: `used_by` for both lists counts `accounts` rows.
That table exists as of this slice but nothing writes it yet, so the counts are
honestly 0 today and BR-TEN-030/034 cannot bite until the account-CRUD slice
lands. BR-TEN-036 still does: no seeded (is_system) row is deletable meanwhile.
"""

import logging
from typing import Any

from django.db.models import Q

from apps.customers import models, services
from core import errors
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.customers")

_MAX_CODE = 40
_MAX_NAME = 120


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
            fe.append(_field_error(field, errors.VAL_REQUIRED, "customers.lookups.required"))
        return None
    value = str(payload[field] or "").strip()
    if not value:
        fe.append(_field_error(field, errors.VAL_REQUIRED, "customers.lookups.required"))
        return None
    if len(value) > max_length:
        fe.append(
            _field_error(field, errors.VAL_RANGE, "customers.lookups.too_long", max=max_length)
        )
        return None
    return value


class AccountStatusLookupHandler:
    """/lookups/account_statuses — the S8 card over the BR-CUS-055 vocabulary.

    Tenant-scoped and tenant-extensible: a tenant may rename a seeded status
    and add its own. Every row MUST carry one of the four behaviour classes,
    including a tenant-added one (US-CUS-020 TC-3: "behavior class of the new
    status follows the reference-data definition")."""

    def _qs(self) -> Any:
        return models.AccountStatus.objects.filter(tenant_id=_tenant_id())

    def search(self, q: str | None) -> Any:
        qs = self._qs().order_by("code", "id")  # IS-2 stable secondary sort
        if q and len(q.strip()) >= 2:  # IS-3 server-side, min 2 chars
            term = q.strip()
            qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
        return qs

    def count(self) -> int:
        return self._qs().count()

    def get(self, entry_id: Any) -> Any:
        return self._qs().filter(pk=entry_id).first()

    def used_by(self, row: Any) -> int:
        """BR-TEN-029 live count. `accounts.status_id` is a PROTECTed FK, so
        the database enforces the BR-TEN-034 delete-lock alongside this."""
        return models.Account.objects.filter(tenant_id=_tenant_id(), status=row).count()

    def serialize(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "behavior_class": row.behavior_class,
            "is_system": row.is_system,
            "active": row.active,
            "used_by": self.used_by(row),
        }

    def _clean(self, payload: dict[str, Any], *, row: Any = None) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        creating = row is None
        cleaned: dict[str, Any] = {}
        code = _clean_text(payload, "code", fe, required=creating, max_length=_MAX_CODE)
        if code is not None:
            duplicate = self._qs().filter(code__iexact=code)
            if row is not None:
                duplicate = duplicate.exclude(pk=row.pk)
            if duplicate.exists():  # BR-TEN-030 per-tenant, case-insensitive
                fe.append(
                    _field_error("code", errors.VAL_FORMAT, "customers.lookups.duplicate_code")
                )
            cleaned["code"] = code
        name = _clean_text(payload, "name", fe, required=creating, max_length=_MAX_NAME)
        if name is not None:
            cleaned["name"] = name
        if creating or "behavior_class" in payload:
            behavior_class = _clean_text(
                payload, "behavior_class", fe, required=creating, max_length=_MAX_CODE
            )
            if behavior_class is not None:
                if behavior_class not in services.BEHAVIOR_CLASSES:
                    # BR-CUS-055 names exactly four. A fifth would be a status
                    # billing cannot classify — refused, never stored.
                    fe.append(
                        _field_error(
                            "behavior_class",
                            errors.VAL_UNKNOWN_LOOKUP,
                            "customers.lookups.unknown_behavior_class",
                            allowed=list(services.BEHAVIOR_CLASSES),
                        )
                    )
                else:
                    cleaned["behavior_class"] = behavior_class
        _refuse(fe)
        return cleaned

    def create(self, payload: dict[str, Any]) -> Any:
        cleaned = self._clean(payload)
        return models.AccountStatus.objects.create(
            tenant_id=_tenant_id(), is_system=False, active=True, **cleaned
        )

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        cleaned = self._clean(payload, row=row)
        for field, value in cleaned.items():
            setattr(row, field, value)
        if cleaned:
            row.save(update_fields=[*cleaned, "updated_at"])
        return row

    def set_active(self, row: Any, active: bool) -> Any:
        row.active = bool(active)
        row.save(update_fields=["active", "updated_at"])
        return row

    def delete(self, row: Any) -> None:
        if row.is_system:
            # BR-TEN-036: a seeded row is deactivatable, never deletable.
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-TEN-036",
                message_key="customers.lookups.seeded_not_deletable",
            )
        row.delete()


class AccountSubtypeLookupHandler:
    """/lookups/account_subtypes — the S8 card over the BR-CUS-067 tree
    (CR-010, PO 2026-08-17 "Part-10 confirmations" 10.0: *"add them"*).

    TENANT-scoped and tenant-extensible — deliberately unlike its PLATFORM
    parent list: the PO's item-1 ruling makes the rows the tenant's own
    vocabulary (*"where you will add Hospital, Church etc"*). The card is the
    tree's second level: every row serializes `parent_code`/`parent_name`
    from the platform `account_types` row it belongs to, and the ONE list
    view draws the parent column and the parent picker the `areas` card
    already proved (BR-MET-066b's mechanism, parents from ANOTHER list).

    A parent is REQUIRED on every row created or edited here: the ratified
    tree is two-level and a floating sub-type is a sub-type of nothing. Rows
    that PREDATE the ruling may carry NULL (migration 0011's nullable choice)
    and render as top level until somebody edits them — at which point the
    picker demands an answer."""

    def _qs(self) -> Any:
        return models.AccountSubtype.objects.filter(tenant_id=_tenant_id()).select_related(
            "account_type"
        )

    def search(self, q: str | None) -> Any:
        qs = self._qs().order_by("code", "id")  # IS-2 stable secondary sort
        if q and len(q.strip()) >= 2:  # IS-3 server-side, min 2 chars
            term = q.strip()
            qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
        return qs

    def count(self) -> int:
        return self._qs().count()

    def get(self, entry_id: Any) -> Any:
        return self._qs().filter(pk=entry_id).first()

    def used_by(self, row: Any) -> int:
        """BR-TEN-029 live count. `accounts.account_subtype_id` is a PROTECTed
        FK; rating's `account_subtype_id` column is still DEFERRED (B11 F-3),
        so accounts are the only referencing table today."""
        return models.Account.objects.filter(tenant_id=_tenant_id(), account_subtype=row).count()

    def serialize(self, row: Any) -> dict[str, Any]:
        parent = row.account_type
        return {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "parent_code": parent.code if parent else None,
            "parent_name": parent.name if parent else None,
            "is_system": row.is_system,
            "active": row.active,
            "used_by": self.used_by(row),
        }

    def _resolve_parent(self, value: Any, fe: list[dict[str, Any]]) -> Any:
        parent_code = str(value or "").strip()
        if not parent_code:
            fe.append(
                _field_error(
                    "parent_code", errors.VAL_REQUIRED, "customers.lookups.parent_required"
                )
            )
            return None
        parent = models.AccountType.objects.filter(code__iexact=parent_code).first()
        if parent is None:
            fe.append(
                _field_error(
                    "parent_code",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "customers.lookups.parent_unknown",
                    value=parent_code,
                    allowed=[row[0] for row in services.SEED_ACCOUNT_TYPES],
                )
            )
        return parent

    def _clean(self, payload: dict[str, Any], *, row: Any = None) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        creating = row is None
        cleaned: dict[str, Any] = {}
        code = _clean_text(payload, "code", fe, required=creating, max_length=_MAX_CODE)
        if code is not None:
            duplicate = self._qs().filter(code__iexact=code)
            if row is not None:
                duplicate = duplicate.exclude(pk=row.pk)
            if duplicate.exists():  # BR-TEN-030 per-tenant, case-insensitive
                fe.append(
                    _field_error("code", errors.VAL_FORMAT, "customers.lookups.duplicate_code")
                )
            cleaned["code"] = code
        name = _clean_text(payload, "name", fe, required=creating, max_length=_MAX_NAME)
        if name is not None:
            cleaned["name"] = name
        if creating or "parent_code" in payload:
            # REQUIRED both ways: the tree is two-level by ruling, so an edit
            # that sends an empty parent is refused rather than promoting the
            # row to a level the tree does not have.
            parent = self._resolve_parent(payload.get("parent_code"), fe)
            if parent is not None:
                cleaned["account_type"] = parent
        _refuse(fe)
        return cleaned

    def create(self, payload: dict[str, Any]) -> Any:
        cleaned = self._clean(payload)
        return models.AccountSubtype.objects.create(
            tenant_id=_tenant_id(), is_system=False, active=True, **cleaned
        )

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        cleaned = self._clean(payload, row=row)
        for field, value in cleaned.items():
            setattr(row, field, value)
        if cleaned:
            row.save(update_fields=[*cleaned, "updated_at"])
        return row

    def set_active(self, row: Any, active: bool) -> Any:
        row.active = bool(active)
        row.save(update_fields=["active", "updated_at"])
        return row

    def delete(self, row: Any) -> None:
        if row.is_system:
            # BR-TEN-036: a seeded row is deactivatable, never deletable.
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-TEN-036",
                message_key="customers.lookups.seeded_not_deletable",
            )
        row.delete()  # a referenced row is stopped by the PROTECTed FK (BR-TEN-034)


class AccountTypeLookupHandler:
    """/lookups/account_types — the S8 card over the tenant's OWN consumer
    categories.

    ⚠ **READ-ONLY UNTIL 2026-09-17, WHEN THE PO RULED *"utility can get their
    own account types"*.** Until that day this handler refused create, update,
    set_active and delete by name through `_PLATFORM_REFUSAL`, because r5 #12
    [D5] made `account_types` a PLATFORM table and a tenant admin editing one
    row would have been editing every utility's vocabulary. That reasoning was
    sound and the posture it defended is gone: `customers.0054` gave the table a
    `tenant_id`, `0055` gave it RLS, and the rows a clerk sees on this card are
    now their own utility's and nobody else's.

    ⚠ **THE DEFECT THAT MADE THE QUESTION REAL IS WORTH KEEPING IN VIEW
    (`DEF-CUS-5647`/`DEF-CUS-5648`).** The card rendered **Add · Edit ·
    Deactivate · Delete** over a server that refused all four — four live
    controls on a door designed never to open, which is hard-won law 2's mirror
    — and the refusal's message key existed in the backend and **in no
    catalogue**, so the clerk got no sentence at all. The PO's report was *"if
    they add entry in this table - look up it does not reflect in these
    places"*, which is exactly what that combination produces. Every refusal
    this handler can now raise has copy in all eleven catalogues.

    It is `AccountStatusLookupHandler`'s shape, deliberately, because the two
    tables are the same kind of thing again: `BR-TEN-030` (codes unique per
    tenant, case-insensitive), `BR-TEN-034` (a used row is not deletable; a
    deactivated row stops being pickable) and `BR-TEN-036` (a seeded row is
    deactivatable, never deletable).

    ⚠ **ONE THING THIS CARD HAS THAT ITS SIBLINGS DO NOT: `legacy`.** It is a
    THIRD axis and not a synonym for `active` — `active=False` retires a code
    from every surface, `legacy=True` keeps it working everywhere it already
    works and only closes the PICKER (`BR-CUS-094`). ⚠ **WRITABLE HERE SINCE
    `DEF-CUS-9808` (2.549.x, 2026-10-06).** This docstring said *"not writable
    here: nothing has ruled who may retire a code from new business"* — and the
    PO HAD ruled, on 2026-09-18 (`OQ-CUS-12407` option (a), verbatim *"go with
    option a"*): **any tenant admin may set or clear `legacy` on any row, seeded
    rows included**, `government` named as the case. The ruling reached the
    register and not this file, so a utility that bills school districts could
    never offer Government again and its four seeded sub-types (Schools among
    them) sat unreachable on every form (`DEF-CUS-9786`, the PO's M7). An UPDATE
    may now carry `legacy` as a boolean; CREATE still never does (a row created
    today is new business — see `create`). Clearing it on `government` does NOT
    re-label one existing record: `BR-CUS-094`'s *"no row is re-labelled by
    guess"* is about RECORDS, and this changes only what a picker offers.
    """

    def _qs(self) -> Any:
        return models.AccountType.objects.filter(tenant_id=_tenant_id())

    def search(self, q: str | None) -> Any:
        # IS-2 stable secondary sort, by `code` like every other reference card.
        # `sort_order` is the PICKER's order and deliberately not the card's —
        # see `models.AccountType`.
        qs = self._qs().order_by("code", "id")
        if q and len(q.strip()) >= 2:  # IS-3 server-side, min 2 chars
            term = q.strip()
            qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
        return qs

    def count(self) -> int:
        return self._qs().count()

    def get(self, entry_id: Any) -> Any:
        return self._qs().filter(pk=entry_id).first()

    def used_by(self, row: Any) -> int:
        """`BR-TEN-029` live count across every table that references a type.

        ⚠ **THREE TABLES, NOT ONE, AND THAT CHANGED WITH THE RULING.** While the
        rows were platform-wide the honest question was only *"can I touch this
        from here?"* and `accounts` answered it, because the PROTECTed FK
        enforced the rest across all tenants anyway. Now the row IS this
        tenant's, so every referencing row that could block a delete is this
        tenant's too: `accounts`, `service_requests` and the `account_subtypes`
        sitting under it as the tree's second level. Counting only accounts
        would offer a Delete that the database then refuses — a control that
        lies, which is the exact fault this whole change is fixing."""
        tenant_id = _tenant_id()
        return (
            models.Account.objects.filter(tenant_id=tenant_id, account_type=row).count()
            + models.AccountSubtype.objects.filter(tenant_id=tenant_id, account_type=row).count()
            + models.ServiceRequest.objects.filter(tenant_id=tenant_id, account_type=row).count()
        )

    def serialize(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "is_system": row.is_system,
            "active": row.active,
            # BR-CUS-094's third axis — writable on UPDATE since DEF-CUS-9808.
            "legacy": row.legacy,
            "used_by": self.used_by(row),
        }

    def _clean(self, payload: dict[str, Any], *, row: Any = None) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        creating = row is None
        cleaned: dict[str, Any] = {}
        code = _clean_text(payload, "code", fe, required=creating, max_length=_MAX_CODE)
        if code is not None:
            duplicate = self._qs().filter(code__iexact=code)
            if row is not None:
                duplicate = duplicate.exclude(pk=row.pk)
            if duplicate.exists():  # BR-TEN-030 per-tenant, case-insensitive
                fe.append(
                    _field_error("code", errors.VAL_FORMAT, "customers.lookups.duplicate_code")
                )
            elif row is not None and code.lower() != row.code.lower():
                # BR-TEN-030's second half: a code is FROZEN once used. Renaming
                # it would silently re-point every account, request and sub-type
                # that carries it, and `rating` stores the CODE as text in charge
                # narrowing and in the plan/tax targeting lists — none of which
                # this handler can see, let alone rewrite. The NAME is always
                # editable, which is what a clerk actually wants when they meant
                # "Commercial" to read "Business".
                if self.used_by(row):
                    fe.append(
                        _field_error(
                            "code",
                            errors.VAL_FORMAT,
                            "customers.lookups.code_frozen_once_used",
                            value=row.code,
                        )
                    )
                else:
                    cleaned["code"] = code
            elif row is None or code != row.code:
                cleaned["code"] = code
        name = _clean_text(payload, "name", fe, required=creating, max_length=_MAX_NAME)
        if name is not None:
            cleaned["name"] = name
        if not creating and "legacy" in payload:
            # DEF-CUS-9808 — OQ-CUS-12407 (a): any tenant admin, any row. A
            # boolean and nothing else: "no" read as truthy would retire a code.
            if isinstance(payload["legacy"], bool):
                if payload["legacy"] != row.legacy:
                    cleaned["legacy"] = payload["legacy"]
            else:
                fe.append(
                    _field_error("legacy", errors.VAL_FORMAT, "customFields.not_a_boolean")
                )
        _refuse(fe)
        return cleaned

    def create(self, payload: dict[str, Any]) -> Any:
        tenant_id = _tenant_id()
        cleaned = self._clean(payload)
        cleaned.pop("legacy", None)
        return models.AccountType.objects.create(
            tenant_id=tenant_id,
            is_system=False,
            active=True,
            # A tenant-added row is never legacy: `legacy` retires a code from
            # NEW business and a row created today is new business.
            legacy=False,
            sort_order=services.next_account_type_sort_order(tenant_id),
            **cleaned,
        )

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        cleaned = self._clean(payload, row=row)
        for field, value in cleaned.items():
            setattr(row, field, value)
        if cleaned:
            row.save(update_fields=[*cleaned, "updated_at"])
        return row

    def set_active(self, row: Any, active: bool) -> Any:
        """`BR-TEN-034`: deactivating is always allowed, however many accounts
        use the row. A deactivated type stops being PICKABLE and every account
        already carrying it keeps it, keeps billing and keeps reporting under
        it — the same shape `legacy` has, arrived at from the other side."""
        row.active = bool(active)
        row.save(update_fields=["active", "updated_at"])
        return row

    def delete(self, row: Any) -> None:
        if row.is_system:
            # BR-TEN-036: a seeded row is deactivatable, never deletable.
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-TEN-036",
                message_key="customers.lookups.seeded_not_deletable",
            )
        if self.used_by(row):
            # BR-TEN-034. The three PROTECTed FKs would refuse this anyway, but
            # a `ProtectedError` reaches the clerk as a 500 with no sentence in
            # it, and on PostgreSQL it poisons the transaction (CLAUDE.md law
            # 14). Refusing here is the same answer with words on it.
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-TEN-034",
                message_key="customers.lookups.type_in_use",
                params={"used_by": self.used_by(row)},
            )
        row.delete()


def register() -> None:
    """Called from AppConfig.ready(). tenancy's registry raises KeyError for a
    list code it does not declare — logged and skipped so a registry that has
    not landed a list cannot break app startup (skip-until-wired)."""
    from apps.tenancy import services as tenancy_services

    for list_code, handler in (
        ("account_statuses", AccountStatusLookupHandler()),
        ("account_types", AccountTypeLookupHandler()),
        # CR-010 (PO 2026-08-17): the sub-type tree's own card — the tenant-
        # editable second level under the read-only platform first level.
        ("account_subtypes", AccountSubtypeLookupHandler()),
    ):
        try:
            tenancy_services.register_lookup_handler(list_code, handler)
        except KeyError:  # pragma: no cover — the registry declares both today
            logger.warning(
                "tenancy LOOKUP_LISTS has no %r entry — handler not registered", list_code
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-001@a2e1d59 (story+rules snapshot — EP-CUS-01 lead story; co-packets EP-CUS-02@bbed56d · customers 02-business-rules@f125a9c)
# generated: 2026-08-10 by story-coder (W2 customers SCHEMA + SEAM slice — the two S8 cards the seam makes countable)
# checklist: A✔ B✔ C✔ D=deferred(served through tenancy's /lookups endpoints — no customers api.py in this slice) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests -m "not golden and not isolation"✔ · pytest tests -m isolation✔ (sqlite tier) + live-Postgres isolation run✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔
# exceptions: `account_types` was a PLATFORM table so its card was READ-ONLY — create/update/set_active/delete all REFUSED with the reason rather than editing every tenant's vocabulary. ⚠ SUPERSEDED 2026-09-17 (PO: *"utility can get their own account types"*): the table is tenant-scoped with RLS FORCE (customers.0054/0055) and the card has full CRUD, so the refusal and its uncatalogued message key are both gone (DEF-CUS-5647, DEF-CUS-5648) · `legacy` was SERVED and not WRITABLE on this card — SUPERSEDED 2026-10-06 (DEF-CUS-9808): the PO had ruled on 2026-09-18 that any tenant admin may set or clear it on any row (OQ-CUS-12407 option a), so an UPDATE now writes it · `used_by` is honestly 0 for both lists today because nothing writes `accounts` yet, so BR-TEN-030 (code frozen once used) and BR-TEN-034 (a used row is not deletable) cannot bite until the account-CRUD slice — BR-TEN-036 (seeded rows never deletable) DOES bite meanwhile and is enforced here · `account_subtypes` gets NO card in this slice: no story asks for one and r5 #12 states no parent-type link, so there is nothing to validate against — SUPERSEDED 2026-08-18 (CR-010 lane): the PO ratified the parent link and the 12-row tree on 2026-08-17 (*"add them"*), so AccountSubtypeLookupHandler above IS the card's handler, parent REQUIRED on new/edited rows, seeded via SEED_ACCOUNT_SUBTYPES (BR-CUS-067)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
