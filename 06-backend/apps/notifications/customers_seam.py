# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-6344 (PO 2026-09-23, on the deployed build: *"this modal is
#           showing db keys"* — Payments → Summary → Mark returned post) ·
#           DEF-1122 (the same cell, filed 2026-08-27)
#           NOTE: no US-ID is cited in this header ON PURPOSE, for the reason
#           `tenancy_seam.py` gives: G10 reads a Trace-header US-ID as "this
#           file ships that story's test cases", and this file ships one read.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           B14 rule 31 (no database id is ever the visible value of a field) ·
#           NFR-3 (every list is paged in the database, so a label read is per
#           PAGE and never per row) · CLAUDE.md hard rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_def_pay_6344_outbound_account_no.py
# Impacts:  apps/notifications/selectors.py (`queue_page`, the list's rows)
# ───────────────────────────────────────────────────────
"""notifications → customers SEAM: the account NUMBER behind a queue row.

One read, PUBLISHED today and resolved BY NAME at call time, so nothing here
imports customers' internals (B1 / BR-TEN-013):

  apps.customers.selectors.account_queryset() -> QuerySet[Account]
    customers' own tenant-scoped account queryset — the one payments'
    collections ladder, outstandings, reporting and write-offs already read the
    account number through. It filters on `app.tenant_id` itself and RLS FORCE
    is the second guarantee (hard rule 1), so this file is never given a tenant
    to look at and issues no query of its own design.

╔══════════════════════════════════════════════════════════════════════════╗
║  ONE STATEMENT PER PAGE, WHATEVER THE PAGE HOLDS — NEVER ONE PER ROW.    ║
╚══════════════════════════════════════════════════════════════════════════╝
`GET /outbound` is a list that can reach hundreds of rows at a utility of
40,000 accounts. The number is read for the whole page's ids in one
`WHERE id IN (…)`; a caller that loops over this function has re-created
`DEF-324`'s shape (*47 of 118 profiled seconds answering one question 304
times*). The test compares two page sizes with a DIFFERENT account on every
row, because a statement count alone cannot tell a batch from an N+1.

⚠ **THE NUMBER ONLY — NO NAME AND NO ADDRESS, DELIBERATELY.** The queue list
already withholds `recipient_snapshot` (a customer's name and full postal
address) for BR-AUD-006's posture, and an account NUMBER is neither of those
things. Serving it takes nothing from that posture; serving the contact's name
here would, so this read does not ask for it.

⚠ **BLANK IS NOT A NUMBER.** `customers.Account.account_no` is a `TextField`,
so an account nobody has numbered holds `""` rather than NULL — `DEF-2580`
recorded the trap on the collections ladder. `""` would slip past a screen's
`?? "No account number"` and draw an EMPTY cell, which B14 rule 31 forbids in
the same sentence as the id. So it is normalised to `None` HERE, once.

⚠ **NO DATABASE ERROR IS CAUGHT.** Nothing here catches and continues, so
hard-won law 14's poisoned-transaction trap cannot arise from this read.
`None` from the resolver means customers publishes no such callable — then the
page carries no numbers and every screen says *"No account number"* in words,
which is a smaller honest answer than a 500 over a list that is otherwise fine.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

#: The customers read this module depends on, named once so the contract is
#: greppable from BOTH sides of the boundary — the discipline
#: `apps/notifications/tenancy_seam.py` states and G20 harvests.
CUSTOMERS_MODULE = "customers"
ACCOUNT_QUERYSET_READ = "account_queryset"


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time — the idiom `tenancy_seam.py`, `payments_seam.py` and
    `apps/metering/seams.py` all use.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def account_numbers(account_ids: Any) -> dict[str, str | None]:
    """`{account_id: account_no}` for a PAGE of ids — ONE statement, or none.

    `{}` for an empty page, which costs NO statement at all. An id with no entry
    is an account this tenant does not hold (or a customers module that
    publishes no queryset); a value of `None` is an account that exists and has
    never been numbered. A caller renders both as *"No account number"* — and
    never as the id.
    """
    ids = sorted({str(value) for value in (account_ids or []) if value not in (None, "")})
    if not ids:
        return {}
    queryset = _resolve(CUSTOMERS_MODULE, ACCOUNT_QUERYSET_READ)
    if queryset is None:  # pragma: no cover - customers publishes it
        return {}
    # `values_list`, never `.only(...)`: `account_queryset()` carries a
    # `select_related`, and Django refuses that combined with a deferral by
    # name (`DEF-RBS-4397`). Two columns cannot collide with anything the owning
    # module puts on its queryset, and `values_list` drops the join.
    return {
        str(pk): (str(number).strip() or None) if number is not None else None
        for pk, number in queryset().filter(pk__in=ids).values_list("id", "account_no")
    }


#: `CR-190-BRC10` — the read behind `apps.notifications.customer_context`.
MESSAGE_IDENTITIES_READ = "message_identities"


def message_identities(account_ids: Any) -> dict[str, dict[str, Any]]:
    """`{account_id: {account_no, customer_name, customer_kind, unit_id,
    service_address}}` for a page of ids, resolved BY NAME from
    `apps.customers.selectors.message_identities` (BR-TEN-013).

    `{}` for an empty page (no statement) or while customers publishes no such
    read — then every customer token prints its named absence, which is a
    smaller honest answer than a guessed name.
    """
    ids = sorted({str(value) for value in (account_ids or []) if value not in (None, "")})
    if not ids:
        return {}
    read = _resolve(CUSTOMERS_MODULE, MESSAGE_IDENTITIES_READ)
    if read is None:  # pragma: no cover - customers publishes it
        return {}
    return dict(read(ids) or {})


# ══════════════════════════════════════════════════════════════════════════
# CR-199-BRC10 S1 — THE CUSTOMER-CATEGORY AXIS OF A TEMPLATE VARIANT
# ══════════════════════════════════════════════════════════════════════════
#: The utility's own customer classes (`account_types`, tenant-owned since the
#: PO ruling of 2026-09-17, *"utility can get their own account types"*). The
#: SAME read the reports' class filter uses, so a template's *Customers* picker
#: and the account screen's class select list one vocabulary.
ACCOUNT_TYPE_OPTIONS_READ = "account_type_options"
#: `{account_id: {type_code, type_name}}` — which class one account is in.
ACCOUNT_TYPES_FOR_READ = "account_types_for"


def account_category_options() -> list[dict[str, str]] | None:
    """`[{value: code, label: name}]` — the utility's ACTIVE customer classes,
    in their own picker order. `None` while customers publishes no such read,
    which a caller must say rather than read as "this utility has none"."""
    read = _resolve(CUSTOMERS_MODULE, ACCOUNT_TYPE_OPTIONS_READ)
    if read is None:  # pragma: no cover - customers publishes it
        return None
    return [
        {"value": str(row["value"]), "label": str(row["label"])} for row in (read() or [])
    ]


def account_category(account_id: Any) -> str | None:
    """The class code of ONE account (`residential`, a utility's own
    `irrigation` …), or None when the account names none or cannot be read.
    ONE statement.

    ⚠ CATEGORY ONLY. A customer's PROGRAMMES (discount enrolments such as
    low-income assistance) are deliberately not read here — an account holds
    several at once and no ruling orders them, so they are not a variant axis
    (decision log 2026-10-29, *"Templates: customer-category variants"*).
    """
    if account_id in (None, ""):
        return None
    read = _resolve(CUSTOMERS_MODULE, ACCOUNT_TYPES_FOR_READ)
    if read is None:  # pragma: no cover - customers publishes it
        return None
    from django.core.exceptions import ValidationError as DjangoValidationError

    try:
        rows = read([account_id]) or {}
    except (DjangoValidationError, ValueError, TypeError):
        # A malformed id is refused by Django BEFORE any SQL runs, so no
        # transaction is poisoned (law 14); it is an account we cannot name.
        return None
    row = rows.get(str(account_id)) or {}
    code = row.get("type_code")
    return str(code) if code else None


def preferred_languages_in_use() -> tuple[str, ...]:
    """The distinct `accounts.preferred_language` values of this utility.

    Under the PO's ruling of 2026-10-29 (*a message goes in the customer's
    preferred language*), a language a customer of this utility has chosen is a
    language this utility must be able to write in — which is why it counts as
    switched on for the *New variant* language list (A4 B). Read through the
    published queryset: one column, DISTINCT, one statement. Empty when
    customers publishes no queryset.
    """
    queryset = _resolve(CUSTOMERS_MODULE, ACCOUNT_QUERYSET_READ)
    if queryset is None:  # pragma: no cover - customers publishes it
        return ()
    values = (
        queryset()
        .exclude(preferred_language__isnull=True)
        .exclude(preferred_language="")
        .order_by()
        .values_list("preferred_language", flat=True)
        .distinct()
    )
    return tuple(sorted({str(value) for value in values}))


#: `CR-199-BRC10` (TPL-SRV-LANG) — the read behind
#: `apps.notifications.message_language.account_language`.
ACCOUNT_LANGUAGE_READ = "account_preferred_language"


def account_preferred_language(account_id: Any) -> str | None:
    """The account's stated language, or None — resolved BY NAME from
    `apps.customers.selectors.account_preferred_language` (BR-TEN-013).

    Since 2026-10-29 (PO option B) this drives the language variant of every
    message to the account, on `BR-NOT-006`'s fallback ladder
    (`message_language.language_for`). None while customers publishes no such
    read, which resolves on the utility's language exactly as before."""
    if account_id in (None, ""):
        return None
    read = _resolve(CUSTOMERS_MODULE, ACCOUNT_LANGUAGE_READ)
    if read is None:  # pragma: no cover - customers publishes it
        return None
    found = str(read(account_id) or "").strip()
    return found or None


#: `CR-199-BRC10` (TPL-SRV-LANG) — the aggregate behind the Templates screen's
#: per-language customer count.
LANGUAGE_COUNTS_READ = "account_counts_by_language"


def account_counts_by_language() -> dict[str | None, int]:
    """`{preferred_language or None: accounts}`, resolved BY NAME from
    `apps.customers.selectors.account_counts_by_language` — one grouped
    statement. `{}` while customers publishes no such read."""
    read = _resolve(CUSTOMERS_MODULE, LANGUAGE_COUNTS_READ)
    if read is None:  # pragma: no cover - customers publishes it
        return {}
    return dict(read() or {})
