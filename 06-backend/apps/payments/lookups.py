# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-009 (the S8 Reference-data card grid — the card a utility's
#           own bank accounts were missing) · US-TEN-010 (per-list add / edit) ·
#           US-TEN-011 (deactivate / delete lock) · US-PAY-021 (the bank
#           statement import that SELECTS one and must never create one)
#           Screens: S8 · S38
#           Defects: DEF-203 (bank_accounts had a model, a unique key and two
#           readers and NO writer anywhere, so bank reconciliation could not
#           run for any real tenant)
# Rules:    BR-PAY-850 (this list's own law — name + display mask + active, the
#           mask is never the account number, one writer) · BR-TEN-031 (tenancy
#           RENDERS; the OWNING module validates and writes) · BR-TEN-029
#           (used-by and card counts computed live) · BR-TEN-030 (identity
#           unique per tenant, case-insensitive) · BR-TEN-034 (used > 0 → hard
#           delete blocked, deactivate allowed) · BR-PAY-019 (bank rec: the
#           statement is imported against ONE named account) · BR-PAY-028 (the
#           file+tags idempotency key whose tag half is this row) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 7 (every change audited —
#           written by tenancy's lookup framework, not here)
# Tests:    06-backend/tests/test_def_203_bank_account_crud.py
# Impacts:  apps.tenancy LOOKUP_LISTS `bank_accounts` (declared with owner
#           "payments") · GET/POST/PATCH/DELETE /lookups/bank_accounts ·
#           apps/payments/bankrec_read.bank_accounts (S38 step 1's picker, which
#           now has something to offer) · the S8 card grid count
# ───────────────────────────────────────────────────────
"""The /lookups handler payments owns — the tenant's own bank accounts.

**WHY THIS FILE EXISTS.** `bankrec_models.BankAccount` has existed since
2026-08-11 with a unique key, an RLS policy, a PROTECTed FK from every statement
import and TWO readers — `bankrec_read.bank_accounts` (S38 step 1's picker) and
the tag half of the import's idempotency key. It had no writer at all. The only
place in the repo that ever created one was a test fixture, which is exactly
what hid it: every bank-rec test passed because each minted its own account
(DEF-203). A real utility reached S38, met an empty picker, and bank
reconciliation was unreachable for them forever.

**WHERE THE PO PUT IT, AND WHY IT IS A CONFIG ROW AND NOT A SCREEN.** PO ruling
2026-08-28, verbatim: *"capture bank account in configure. Keep them in section
which is logical"*. The logical section is Settings → Configure → Reference
data, whose card grid is exactly this shape already: a tenant-maintained named
list with an active flag that is deactivated and never deleted. `BR-SHL-035`
makes that DATA rather than a screen — *"new reference data = a new card + its
config, never a new layout"* — so the whole frontend half is one row in
`referenceDataConfig.ts` and NO new screen ID is minted.

`BR-TEN-031` then fixes the boundary: tenancy renders and routes, the OWNING
module validates and writes. `bank_accounts` is payments' table, so the
validation below is payments' law and tenancy never touches the model.

════════════════════════════════════════════════════════════════════════════
THREE FIELDS, AND THE TWO THAT ARE DELIBERATELY ABSENT
════════════════════════════════════════════════════════════════════════════
**name** — *"Chase Operating"*. This list's identity: `UNIQUE (tenant, name)`.

**mask** — the last digits a human recognises, so a clerk picking from
*"Chase Operating ••4021"* knows which account they mean. It is **NOT the
account number** and must never be widened into one: the model's own docstring
states the posture — *"nothing in this product needs the full number, and B2 §6's
PII posture is that a column you do not store is a column that cannot leak"*.
That posture is only real if something REFUSES a long value, so `_MAX_MASK`
below is 4 digits and a fifth is refused by name. If a utility needs to tell two
accounts apart, that is what the name is for.

**active** — deactivate, never delete (BR-TEN-034's shape, which the model's own
comment cites). An account named on an imported statement stays resolvable: the
FK is PROTECT, so the database refuses the delete even if this handler did not.

**No GL account hangs off this row.** Reconciliation resolves `cash` BY
DESIGNATION (OQ-110's closure), one account per tenant, and which ledger account
a bank account maps to is a real question with no ratified answer. Nothing here
invents one, and a `gl_account` field sent to this handler is refused as unknown
rather than quietly dropped.

**No account number, no routing number, no bank address.** Same rule, same
reason: they are refused as unknown fields.

════════════════════════════════════════════════════════════════════════════
ONE WRITER FOR ONE FACT — S38 SELECTS, THIS CARD CREATES
════════════════════════════════════════════════════════════════════════════
S38 step 1 picks from `bankrec_read.bank_accounts` and has no create path, and
it must not gain one. Two places that can create a bank account is how two
screens come to disagree about which accounts a utility has (PO ruling
2026-08-28, recorded in the decision log).

════════════════════════════════════════════════════════════════════════════
WHAT THE FRAMEWORK'S `code` SLOT HOLDS HERE, REPORTED NOT HIDDEN
════════════════════════════════════════════════════════════════════════════
The shared list view draws Code · Name · <detail> · Used by · Status. This table
has no `code` column, so — exactly as `rating.lookups.TaxJurisdictionLookupHandler`
already does for `tax_jurisdictions` — the framework's code slot is served by the
NAME, and `code` and `name` in a payload both address the one stored column.

Two consequences of that, stated rather than discovered:

  * `used_by` counts the statement imports made against the account, so a used
    account renders its Code field read-only ("read-only once used", BR-TEN-030)
    while Name stays editable — and because both address one column, a rename
    still lands through Name. The rename is CORRECT (identity is the row id, not
    the text; the idempotency tag is `bank_account_id`), the frozen-looking Code
    field is the framework's presentation of a list whose identity is its name.
    Filed as DEF-2520 against the shared view rather than papered over here.
  * `is_system` is served False: no column exists, nothing seeds this list, and
    every row is the tenant's own. BR-TEN-036's "a seeded row is never deletable"
    therefore has nothing to bite on, and BR-TEN-034's used-by lock is the guard
    that IS live.
"""

import logging
import re
from typing import Any

from django.db.models import Q

from apps.payments import bankrec_models as bankrec
from core import errors
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.payments")

LIST_CODE = "bank_accounts"

#: A bank account NAME a person types on the card. 120 matches every other
#: hosted list; the shared form caps its own input at 60 first.
_MAX_NAME = 120

#: ⛔ **THE MASK IS FOUR DIGITS AND THAT IS THE WHOLE POINT.** B2 §6's posture —
#: "a column you do not store is a column that cannot leak" — is a promise this
#: number keeps. Without a cap the field is a free-text box a well-meaning clerk
#: fills with the full account number, and the column that could not leak now
#: holds the thing we refused to store. Four is r10's own rendering
#: (*"Chase Operating ••4021"*) and is what a bank statement prints.
_MAX_MASK = 4

#: The mask, exactly: one to four ASCII digits. See `_MAX_MASK`.
_MASK_RE = re.compile(rf"^[0-9]{{1,{_MAX_MASK}}}$")


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing reads or writes a tenant table without
    `app.tenant_id` set. Refuses rather than defaulting."""
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


class BankAccountLookupHandler:
    """/lookups/bank_accounts — the tenant's own banking relationships.

    Duck-typed to tenancy's contract (BR-TEN-031): search · count · get ·
    serialize · used_by · create · update · set_active · delete. Content
    validation lives here because the table is payments'."""

    model = bankrec.BankAccount

    #: The shared card sends `code`, `name` and the detail field. Everything
    #: else is REFUSED by name — an account number, a routing number or a GL
    #: account arriving here is a caller trying to widen a row we deliberately
    #: kept narrow, and a silent drop would look like it had been stored.
    _ALLOWED = frozenset({"code", "name", "mask"})

    def _qs(self) -> Any:
        return self.model.objects.filter(tenant_id=_tenant_id())

    def search(self, q: str | None) -> Any:
        qs = self._qs().order_by("name", "id")  # IS-2 stable secondary sort
        if q and len(q.strip()) >= 2:  # IS-3 server-side, min 2 chars
            term = q.strip()
            qs = qs.filter(Q(name__icontains=term) | Q(mask__icontains=term))
        return qs

    def count(self) -> int:
        return self._qs().count()

    def get(self, entry_id: Any) -> Any:
        try:
            return self._qs().filter(pk=entry_id).first()
        except (ValueError, TypeError):
            return None

    def used_by(self, row: Any) -> int:
        """BR-TEN-029 live count: the bank statements imported against this
        account. `bank_statement_imports.bank_account_id` is PROTECT, so the
        database enforces the same BR-TEN-034 delete-lock one layer down."""
        return bankrec.BankStatementImport.objects.filter(
            tenant_id=_tenant_id(), bank_account=row
        ).count()

    def serialize(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(row.pk),
            # No `code` column — the NAME is this list's identity (see the
            # module docstring). Same posture as `tax_jurisdictions`.
            "code": row.name,
            "name": row.name,
            # The card's detail slot. NULL is served as-is: the shared table
            # renders it blank, which is the truth ("no mask recorded"), and
            # writing "" would claim an empty mask was entered.
            "mask": row.mask,
            "active": row.active,
            # No column exists and nothing seeds this list — every row is the
            # tenant's own, so BR-TEN-036 has nothing to lock.
            "is_system": False,
            "used_by": self.used_by(row),
        }

    # ── validation — payments' own law (BR-TEN-031) ─────────────────────────
    def _clean_name(self, payload: dict[str, Any], fe: list[dict[str, Any]]) -> str | None:
        """`name` wins; `code` is the same column arriving under the framework's
        own label. Absent from BOTH on a PATCH means "leave it alone"."""
        source = "name" if "name" in payload else ("code" if "code" in payload else None)
        if source is None:
            return None
        value = str(payload[source] or "").strip()
        if not value:
            fe.append(_field_error("name", errors.VAL_REQUIRED, "payments.lookups.name_required"))
            return None
        if len(value) > _MAX_NAME:
            fe.append(
                _field_error("name", errors.VAL_RANGE, "payments.lookups.too_long", max=_MAX_NAME)
            )
            return None
        return value

    def _clean_mask(self, payload: dict[str, Any], fe: list[dict[str, Any]]) -> Any:
        """The last digits, or None. Empty string is a real answer — "clear the
        mask" — and is stored as NULL so the picker renders the bare name."""
        if "mask" not in payload:
            return "__absent__"
        value = str(payload["mask"] or "").strip()
        if value == "":
            return None
        # ⚠ ASCII digits, via a regex rather than `str.isdigit()`: that method
        # answers True for Arabic-Indic and other Unicode digit forms, which
        # would store a mask no bank statement can be compared against.
        if _MASK_RE.match(value) is None:
            # ⛔ The PII posture is only real if something refuses. See _MAX_MASK.
            fe.append(
                _field_error(
                    "mask", errors.VAL_FORMAT, "payments.lookups.mask_shape", max=_MAX_MASK
                )
            )
            return "__absent__"
        return value

    def _check_duplicate(self, name: str, exclude_pk: Any = None) -> None:
        """BR-TEN-030 applied to this list's identity, case-insensitively —
        and it is also the DB's `uq_bank_accounts_name`, so this refusal is a
        readable message in front of a constraint that would otherwise 500."""
        qs = self._qs().filter(name__iexact=name)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        existing = qs.first()
        if existing is not None:
            _refuse(
                [
                    _field_error(
                        "code",
                        errors.VAL_FORMAT,
                        "payments.lookups.duplicate_name",
                        existing=existing.name,
                    )
                ]
            )

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        for field in sorted(set(payload) - self._ALLOWED):
            # An account number, a routing number, a GL account: refused BY
            # NAME. This row is narrow on purpose (module docstring).
            fe.append(_field_error(field, errors.VAL_FORMAT, "payments.lookups.unknown_field"))
        name = self._clean_name(payload, fe)
        if name is None and not partial and not fe:
            fe.append(_field_error("name", errors.VAL_REQUIRED, "payments.lookups.name_required"))
        mask = self._clean_mask(payload, fe)
        _refuse(fe)
        cleaned: dict[str, Any] = {}
        if name is not None:
            cleaned["name"] = name
        if mask != "__absent__":
            cleaned["mask"] = mask
        return cleaned

    # ── writes ──────────────────────────────────────────────────────────────
    def create(self, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=False)
        self._check_duplicate(cleaned["name"])
        # Written as `bankrec.BankAccount.objects.create` and NOT through
        # `self.model`, so a source scan can prove this is the product's ONLY
        # writer (BR-PAY-850, one writer for one fact) —
        # `test_def_203_bank_account_crud.py` asserts exactly that.
        return bankrec.BankAccount.objects.create(tenant_id=_tenant_id(), active=True, **cleaned)

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
        """DEACTIVATE, NEVER DELETE — BR-TEN-034's shape and BR-PAY-850.

        A deactivated account is gone from S38's picker (`bankrec_read.
        bank_accounts` filters `active=True`) and `import_bank_statement`
        refuses it by name, while every statement already imported against it
        still resolves its name and mask. That is the whole reason this control
        exists instead of Delete."""
        row.active = bool(active)
        row.save(update_fields=["active", "updated_at"])
        return row

    def delete(self, row: Any) -> None:
        """Hard delete of an UNUSED account only.

        Tenancy applies the BR-TEN-034 lock from `used_by` above before it gets
        here, and `bank_statement_imports.bank_account_id` is PROTECT, so a
        raced delete is refused by the database as well."""
        row.delete()


class BankRecReasonLookupHandler:
    """/lookups/bank_rec_difference_reasons — CS-18 (CR-059 task 46).

    **The gap it closes.** The reason on a reconciliation difference was FREE
    TEXT, so no two clerks described the same difference the same way and nobody
    could report on cause. CS-18's new rule: *"Reconciliation difference reasons
    are a seeded, tenant-extensible list, deactivated and never deleted, like
    every other reference list."*

    **NO NEW SCREEN ID** — a reference list is DATA, so it is a card on the
    existing S8 grid exactly as bank accounts were ruled to be (BR-SHL-035, and
    CS-18 says so in terms). The frontend half is one row in
    `referenceDataConfig.ts` and belongs to CR-059 task 48; **until it lands
    this list has a seeder, a handler and an API and NO card on the screen** —
    hard-won law 2, said out loud rather than left for a reviewer.

    Duck-typed to tenancy's contract (BR-TEN-031), same as the handler above.
    Content validation lives here because the table is payments'.
    """

    model = bankrec.BankRecDifferenceReason

    #: `code` and `name` are the list's two fields. `default_gl_account_id` is
    #: deliberately NOT settable from this card: it is a LEDGER account id, the
    #: shared reference-data form has no account picker, and a uuid typed into a
    #: text box is B14 rule 31 arriving through the back door. It is refused by
    #: name — a silent drop would look as though it had been stored.
    _ALLOWED = frozenset({"code", "name"})

    _MAX_CODE = 60
    _MAX_NAME = 120

    def _qs(self) -> Any:
        return self.model.objects.filter(tenant_id=_tenant_id())

    def search(self, q: str | None) -> Any:
        qs = self._qs().order_by("name", "id")  # IS-2 stable secondary sort
        if q and len(q.strip()) >= 2:  # IS-3 server-side, min 2 chars
            term = q.strip()
            qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
        return qs

    def count(self) -> int:
        return self._qs().count()

    def get(self, entry_id: Any) -> Any:
        try:
            return self._qs().filter(pk=entry_id).first()
        except (ValueError, TypeError):
            return None

    def used_by(self, row: Any) -> int:
        """BR-TEN-029 live count — the explanations written under this reason.

        Counted on the CODE rather than on an FK, because
        `bank_rec_resolutions.reason_code` stores the code as text on purpose (a
        resolution is append-only financial history and must still read
        correctly after the list row is renamed). The consequence is stated:
        renaming a used reason leaves the old explanations reading the OLD code,
        which is the correct behaviour for a history column and the reason
        BR-TEN-030's "read-only once used" lock matters on this list.
        """
        return bankrec.BankRecResolution.objects.filter(
            tenant_id=_tenant_id(), reason_code=row.code
        ).count()

    def serialize(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(row.pk),
            "code": row.code,
            "name": row.name,
            # NULL is served as-is: no default account is mapped, which is the
            # SEEDED state and a real answer. S40 then asks for the account,
            # which BR-PAY-019 requires on every difference anyway.
            "default_gl_account_id": (
                str(row.default_gl_account_id) if row.default_gl_account_id else None
            ),
            "active": row.active,
            "is_system": row.is_system,
            "used_by": self.used_by(row),
        }

    # ── validation — payments' own law (BR-TEN-031) ─────────────────────────
    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        for field in sorted(set(payload) - self._ALLOWED):
            fe.append(_field_error(field, errors.VAL_FORMAT, "payments.lookups.unknown_field"))
        cleaned: dict[str, Any] = {}
        for name, cap in (("code", self._MAX_CODE), ("name", self._MAX_NAME)):
            if name not in payload:
                if not partial:
                    fe.append(
                        _field_error(name, errors.VAL_REQUIRED, "payments.lookups.name_required")
                    )
                continue
            value = str(payload[name] or "").strip()
            if not value:
                fe.append(_field_error(name, errors.VAL_REQUIRED, "payments.lookups.name_required"))
                continue
            if len(value) > cap:
                fe.append(
                    _field_error(name, errors.VAL_RANGE, "payments.lookups.too_long", max=cap)
                )
                continue
            cleaned[name] = value
        _refuse(fe)
        return cleaned

    def _check_duplicate(self, code: str, exclude_pk: Any = None) -> None:
        """BR-TEN-030, case-insensitively — and it is also the DB's
        `uq_bank_rec_diff_reasons_code_ci`, so this is a readable message in
        front of a constraint that would otherwise 500."""
        qs = self._qs().filter(code__iexact=code)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        existing = qs.first()
        if existing is not None:
            _refuse(
                [
                    _field_error(
                        "code",
                        errors.VAL_FORMAT,
                        "payments.lookups.duplicate_name",
                        existing=existing.code,
                    )
                ]
            )

    # ── writes ──────────────────────────────────────────────────────────────
    def create(self, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=False)
        self._check_duplicate(cleaned["code"])
        return bankrec.BankRecDifferenceReason.objects.create(
            tenant_id=_tenant_id(), active=True, is_system=False, **cleaned
        )

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=True)
        if "code" in cleaned and cleaned["code"].lower() != row.code.lower():
            self._check_duplicate(cleaned["code"], exclude_pk=row.pk)
        if cleaned:
            for field, value in cleaned.items():
                setattr(row, field, value)
            row.save(update_fields=[*cleaned.keys(), "updated_at"])
        return row

    def set_active(self, row: Any, active: bool) -> Any:
        """DEACTIVATE, NEVER DELETE — BR-TEN-034, and CS-18 says so in terms.

        A deactivated reason disappears from S40's picker and
        `reconciliation._canonical_reason` refuses it for a NEW explanation,
        while every explanation already written under it still reads correctly:
        the code is stored as text on an append-only row. That is the whole
        reason this control exists instead of Delete."""
        row.active = bool(active)
        row.save(update_fields=["active", "updated_at"])
        return row

    def delete(self, row: Any) -> None:
        """Hard delete of an UNUSED, NON-SEEDED reason only.

        Tenancy applies BR-TEN-036 (a seeded row is never deletable) from
        `is_system` and BR-TEN-034's used-by lock from `used_by` above before it
        gets here. Both matter: a seeded reason is part of the vocabulary every
        report is written against, and a used one has history hanging off it."""
        row.delete()


REASON_LIST_CODE = "bank_rec_difference_reasons"


def seed_reference_list(list_code: str, entries: list[dict[str, Any]], fixture_version: str) -> int:
    """tenancy's BR-TEN-012/013 seam — payments' own reference lists.

    **Insert-missing by natural key**, which is what makes a re-run silent: a
    replay finds every code present, creates nothing and returns 0. Nothing here
    updates an existing row, so a tenant that renamed *"Bank charge"* to their
    own wording keeps it forever.

    ⚠ **THE FIXTURE CARRIES NO ENTRIES FOR THIS LIST AND THAT IS DELIBERATE** —
    the `premises_types` / BR-MET-034 posture, which
    `apps.tenancy.services.SEED_LIST_OWNERS` states in its own comment: the
    ratified source is ONE constant in the owning module
    (`bankrec_models.SEED_DIFFERENCE_REASONS`) and a second copy in
    `lookup_defaults.json` is a copy free to drift. So `entries` is honoured
    when tenancy passes any, and falls back to the constant when it passes none,
    which is every run today.

    Raises `KeyError` for a list code payments does not own — that is the
    contract tenancy's `_seed_reference_data` catches and treats as *"not mine
    yet"*, and it is why `bank_accounts` (which no fixture can ever fill) is not
    handled here.
    """
    if list_code != REASON_LIST_CODE:
        raise KeyError(f"payments owns no reference list {list_code!r}")
    rows = [
        {"code": str(entry["code"]), "name": str(entry.get("name") or entry["code"])}
        for entry in (entries or [])
        if entry.get("code")
    ] or [{"code": code, "name": name} for code, name in bankrec.SEED_DIFFERENCE_REASONS]
    tenant_id = _tenant_id()
    present = {
        str(code).lower()
        for code in bankrec.BankRecDifferenceReason.objects.filter(tenant_id=tenant_id).values_list(
            "code", flat=True
        )
    }
    missing = [row for row in rows if row["code"].lower() not in present]
    if not missing:
        return 0
    bankrec.BankRecDifferenceReason.objects.bulk_create(
        [
            bankrec.BankRecDifferenceReason(
                tenant_id=tenant_id,
                code=row["code"],
                name=row["name"],
                is_system=True,  # BR-TEN-036 — a seeded row is never deletable
                active=True,
            )
            for row in missing
        ]
    )
    return len(missing)


def register() -> None:
    """Called from AppConfig.ready(). tenancy's registry raises KeyError for a
    list code it does not declare — logged and skipped so a registry that has
    not landed the list cannot break app startup (skip-until-wired,
    BR-TEN-013)."""
    from apps.tenancy import services as tenancy_services

    for code, handler in (
        (LIST_CODE, BankAccountLookupHandler()),
        (REASON_LIST_CODE, BankRecReasonLookupHandler()),
    ):
        try:
            tenancy_services.register_lookup_handler(code, handler)
        except KeyError:  # pragma: no cover — the registry declares both today
            logger.warning("tenancy LOOKUP_LISTS has no %r entry — handler not registered", code)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-203 (defect register row) + PO ruling 2026-08-28 "BANK ACCOUNTS ARE CAPTURED IN SETTINGS → CONFIGURE" (12-governance/02-decision-log.md) + EP-PAY-06 US-PAY-021 + EP-TEN-07 US-TEN-009/010/011
# generated: 2026-08-28 by story-coder (DEF-203 bank-account capture lane)
# checklist: A✔ B✔ C✔ D=deferred(served through tenancy's /lookups endpoints — no payments route of its own, which is BR-TEN-031) E✔(the card row in referenceDataConfig.ts) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: NO `code` column on `bank_accounts` — the framework's code slot is served by `name`, exactly as rating does for `tax_jurisdictions`; BR-TEN-030's uniqueness is applied to it and matches the DB's `uq_bank_accounts_name` · NO `is_system` column — served False, nothing seeds this list, so BR-TEN-036 has nothing to lock and BR-TEN-034's used-by lock is the guard that IS live · `bank_accounts` is deliberately in UNSEEDABLE_REFERENCE_LISTS: a bank account is the tenant's OWN banking relationship and no platform fixture can carry one · the mask is capped at 4 DIGITS on purpose (B2 §6 PII posture) and a fifth digit is refused by name — this is a judgment recorded in the decision log, not a ratified figure · the shared card's Code field renders read-only on a USED account while Name stays editable, and both address one column, so a rename still lands — filed as DEF-2520 against the shared view rather than worked around here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
