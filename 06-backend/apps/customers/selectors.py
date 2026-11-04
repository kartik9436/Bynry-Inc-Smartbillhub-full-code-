# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-001 (S17 accounts table + header roll-up) · US-CUS-002 (S17
#           search + the AC-8 filter set) · US-CUS-003 (S18 — the created
#           account read back for the review step and the 201 body)
#           Screens: S17 · S18 · S21
#           AMENDED 2026-08-15 (tenant custom-fields lane): US-SHL-016 (EP-SHL-07 — `custom_data` on the S21 account detail read, so the
#           shared renderer shows the tenant's own values read-only)
# Rules:    BR-CUS-015 as AMENDED 2026-08-15 (S17 list contract; Balance is the
#           LEDGER's own position for the account — `accounts.balance` is a
#           cache nothing writes and serving it was DEF-127) ·
#           BR-CUS-016 (stored status comes from the lookup; aging is DERIVED
#           and never stored) · BR-CUS-017 (at most ONE active account per
#           unit — the occupying-account read the rule is enforced against) ·
#           BR-CUS-053 (search acct#/customer name/service address/meter #;
#           filters status · category · autopay · balance > 0; default sort
#           customer name A→Z) · BR-CUS-055 (the five seeded, tenant-extensible
#           statuses and their behaviour classes) · BR-CUS-045 (contact PII) ·
#           BR-MET-036 (occupancy DERIVES from the active account) ·
#           BR-SHL-011 (list param grammar via BE-05)
#           AMENDED 2026-08-11 (tenant custom-fields lane): `custom_data_for_account`,
#           PUBLISHED FOR BILLING (B2 r17.2 — the values live on the owning
#           module's row and are read through the owning module's selector).
# Tests:    06-backend/tests/test_us_cus_003_account_write.py ·
#           06-backend/tests/test_def_127_one_account_one_figure.py (the balance
#           this module serves, compared against every other surface that
#           states it — any disagreement fails)
# Impacts:  apps/customers/api.py (every read) · apps/customers/services.py
#           (the occupying-account query BR-CUS-017 is enforced with) ·
#           apps/metering/selectors.occupancy_of (through the customers seam
#           metering resolves by name)
# ───────────────────────────────────────────────────────
"""customers read path (LAW 0: api thin → services sole writer → selectors read).

Everything here is read-only and tenant-scoped through `app.tenant_id` context
(RLS FORCE on Postgres; the explicit tenant filters keep the same law true on
the sqlite test DB — no cross-tenant queryset, CLAUDE.md rule 1).

Money is serialized as the EXACT NUMERIC(18,6) string ("0.000000"). Nothing
here rounds, sums a price or computes a charge. No B4 math lives in this module
and none may.

════════════════════════════════════════════════════════════════════════════
WHAT A CUSTOMER OWES COMES FROM THE LEDGER (DEF-127, 2026-08-15)
════════════════════════════════════════════════════════════════════════════
This docstring used to say *"`balance` … is a CACHE whose source of truth is
the ledger"*, and that was true of the COLUMN and false of what this module
did with it: it served the cache as the answer. Nothing in this product has
ever written `accounts.balance`, so `GET /accounts` answered **0.000000** for
an account holding an ISSUED, UNPAID bill of **108.88** whose money the books
were carrying as `1200 AR` debit 108.880000 — and S17 rendered *Outstanding
$0.00*. A customer who owed money was told they owed nothing.

`balance` is now the ledger's own Σ over posted journal lines
(`apps.ledger.reporting.ar_positions`, reached through this module's seam —
customers touches no other module's ORM, B1). `balance_cached` still serves the
column, labelled as what it is. BR-REP-002 is the law being kept: one
derivation of "what is owed", never a side-maintained second one, because two
numbers for one thing agree on the day they are written and disagree the first
time a posting is reversed.

**AND AN ABSENCE IS NEVER SPELLED "0.00".** When the books cannot be asked, the
figure is null and `balance_unavailable` carries the reason. That distinction
IS the defect: a plausible zero looks exactly like a settled account.

TWO CELLS OF THE S17 ROW ARE HONESTLY ABSENT, and each says so in the payload
rather than being filled with a plausible value:

  · `aging` — BR-CUS-016 derives Current / 30d past / 60+ past from open-invoice
    due-date math and no module publishes the due dates
    (`apps/ledger/reporting.GAP_AGING_NEEDS_DUE_DATES` names the read). A
    fabricated "Current" would be a claim about a customer's money, so the
    field is null and the STORED status is all the row asserts.
    ⚠ **AMENDED 2026-08-24 (CR-030 W2 · 2.3/2.4): the row now also carries
    `ageing_segment`**, BR-CUS-016's OTHER half — the age of the account's own
    `account_opening_buckets` position, advanced by calendar days from the
    cutover date (BR-CUS-048), in the four bands BR-CUS-048 names. It is
    DERIVED on every read and stored nowhere.
    ⚠ **AMENDED AGAIN 2026-10-17 (`DEF-CUS-10181`): `ageing_segment` NOW READS
    THE BILLS TOO** — the oldest unpaid bill's due date from Who owes you's own
    debtor statement, the older of that and the opening position winning — so
    the sentence above about due dates being published by no module is no
    longer true of `ageing_segment`. It stays true of `aging`, billing's
    three-word display state, which nothing serves and nothing reads.
  · `plan` — BR-CUS-014 sc.6 prices from the ACCOUNT's plan snapshot, which is
    `account_plan_assignments` (BR-CUS-029) and has no DDL in any signed
    document. The unit's plan is NOT substituted for it: they are equal by
    construction only until the first override (BR-CUS-010), and a read that
    silently swaps one for the other would be wrong on exactly the accounts
    where it matters.

`last_bill_at` was a third until 2026-08-15 and is now served — see
`apps/customers/seams.last_issued_invoice_date` for why it was null for weeks
while `invoices` was full of issued bills.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from django.db.models import Count, OuterRef, Q, QuerySet, Subquery, Sum
from django.db.models.functions import Trim

from apps.customers import account_import, identity_match, models, portal_seam, seams
from core import batch_reads, crypto, errors
from core import tenancy as core_tenancy
from core.pagination import ListParams, order_terms

#: `DEF-CUS-6917` — the Services chips drop what they cannot resolve, and
#: until 2026-09-27 they dropped it in silence. Every skip is counted and
#: reported here at WARNING, once per account, naming the tenant and the
#: account id but never a customer name (BR-CUS-045: a log line is not a
#: place for PII).
logger = logging.getLogger("smartbillhub.customers")

SIX_PLACES = Decimal("0.000001")  # DB-3 storage precision — NOT money rounding
MIN_SEARCH_CHARS = 2  # IS-3: server-side search from 2 characters

# Capability-matrix vocabulary for S17 (BR-CUS-053, PO AC-8). BE-05 falls back
# to the default for anything outside the set, so an unknown sort or filter can
# never 4xx a list URL (BR-SHL-011).
ACCOUNT_SORTS: tuple[str, ...] = (
    "created",
    "account_no",
    "name",
    "balance",
    "last_bill",
    "status",
    # PO 2026-10-17 (`DEF-CUS-10180`) — *"sortable oldest ↔ newest by Opened"*.
    # `asc` is OLDEST first (the earliest Opened date), and an account never
    # opened (pending activation) sorts LAST in both directions.
    "account_age",
    # `DEF-CUS-10181` — *"filter and sort work for bill-only accounts"*. `desc`
    # is the most overdue first; an account owing nothing that ages is last
    # in both directions.
    "ageing",
)
#: `BR-CUS-1046` (PO 2026-09-10) — *"It should always sort it by the creation
#: order. The new newly created entries should always show on the top."*
#: ⚠ **THIS SUPERSEDES `BR-CUS-053`'s `default sort name A→Z` CLAUSE**, and only
#: that clause: the five search terms, the filters and the columns are untouched.
#:
#: ⚠ **`DEF-CUS-4996` IS FIXED HERE, AND NAMING IT IS THE POINT (`G67`).** That
#: row's surface column says *"selectors.py:111 (ACCOUNT_DEFAULT_SORT)"* — this
#: line — and for a few hours after it was closed this file did not mention the
#: id anywhere, so a lane grepping for `DEF-CUS-4996` in the file the register
#: sends it to would have found nothing and concluded the fix was never made.
#: `DEF-2792` sat `open` for twelve days over exactly that. The value above was
#: `"name"`, and the accounts list opened on the alphabet: measured on the demo
#: utility, the newest account came back at position 58 of 73 — page two.
ACCOUNT_DEFAULT_SORT = "created"
ACCOUNT_DEFAULT_DIR = "desc"

#: ── WHICH SORTS ARE AN `ORDER BY`, AND WHICH CANNOT BE (`NFR-3`) ───────────
#: The four below are columns this table holds (or, for `name`, a correlated
#: read of the account's own primary contact), so the ordering and the page are
#: both taken in the DATABASE and the request builds one page of rows.
ACCOUNT_SQL_SORTS: tuple[str, ...] = (
    "created",
    "account_no",
    "name",
    "status",
    "account_age",
    "ageing",
)
#: ⚠ **THE OTHER TWO ARE DERIVED FIGURES AND NO `ORDER BY` CAN REACH THEM**, so
#: a request that asks for one still builds every matching row and sorts in
#: Python. That is stated rather than hidden:
#:
#:   * `balance` lives in the LEDGER and no column holds it (`BR-CUS-016`, and
#:     `DEF-127`'s note above the `balance_gt` chip — the cached column is
#:     written by nothing). `apps/payments/outstandings.py` records the same
#:     disposition for its own sort.
#:   * `last_bill` is billing's, read through a seam per page.
#:
#: A WHERE or ORDER BY over either would be a SECOND implementation of a figure
#: that already has one, free to disagree with the cell the same response
#: renders — which is the trade `DEF-127` deliberately made and this pass does
#: not reopen. What changed is that the EXPENSIVE path is now the exception a
#: clerk opts into, instead of the default every clerk lands on.
ACCOUNT_DERIVED_SORTS: tuple[str, ...] = ("balance", "last_bill")
#: The two list filters that are also derived, for the same reason: both are
#: applied to BUILT ROWS, so either one forces the whole-tenant build as well.
ACCOUNT_DERIVED_FILTERS: tuple[str, ...] = ("balance_gt",)
#: `plan` is DELIBERATELY ABSENT from the AC-8 filter set: filtering by plan
#: needs the account plan snapshot (BR-CUS-029), which is not built. An
#: undeclared filter is ignored by BE-05 rather than silently returning wrong
#: rows — reported in the lane report, not worked around.
ACCOUNT_FILTERS: tuple[str, ...] = (
    "status",
    "category",
    "autopay",
    "balance_gt",
    "unit_id",
    # `CR-056` W1 / `BR-CUS-1010` — `f.premises_id` finds an account by its
    # ADDRESS. The owner's account names no unit, so `f.unit_id=` cannot reach it
    # and PRM-02's owner card would have nothing to ask for.
    "premises_id",
    # BR-CUS-068 — `f.kind` partitions regular | master, so the screen lane can
    # list the owner accounts without a second endpoint.
    "kind",
    # CR-030 W2 task 2.4 — the AGEING segment (`?ageing=` / `f.ageing=`). See
    # `ageing_segment_for_row` below for the derivation and its one judgment.
    "ageing",
)

#: The filter/query name for the CR-030 §5.1.2 `AGEING` segment. Named once so
#: the API's bare-`?ageing=` spelling and BE-05's `f.ageing=` cannot drift.
AGEING_FILTER = "ageing"


def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _money(value: Decimal | None) -> str | None:
    """The NUMERIC(18,6) string, normalized to the column's six places (DB-3).
    STORAGE precision only — half-up 2dp is a finalization/display concern that
    belongs to B4, and no figure here is ever rounded for money purposes."""
    if value is None:
        return None
    return str(Decimal(value).quantize(SIX_PLACES, rounding=ROUND_HALF_UP))


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def account_import_index() -> dict[str, dict[str, Any]]:
    """⛔ **CR-046 C4 — EVERY ACCOUNT ON FILE, KEYED THE WAY AN IMPORT FILE
    REFERENCES ONE.** The accounts target's `_existing_index`, published across
    the module boundary because `accounts` is this module's table and metering
    may not query it (B1/B2 §2).

    `assets.selectors.asset_import_index`'s shape, verbatim, and for the same
    reason: two keys per row in ONE dict, namespaced so they cannot collide.

      * `<lowered account_no>` — an operator quoting OUR number is naming a
        specific record, and that is the strongest statement available.
      * `ext:<lowered external_ref>` (BR-CUS-172) — the only identifier a first
        migration's corrected re-run carries, and lawful as a key because
        `uq_accounts_tenant_external_ref_ci` makes it unique per tenant.

    ⚠ **NAMESPACED, NEVER MERGED.** A legacy `AC-2026-00001` and one of OUR
    `AC-2026-00001`s must not collide in a flat dict — that would let a legacy
    string silently address a different account, and an account is a thing
    money is posted against. `import_runs._key_of` builds the same shape.

    ⚠ **SOFT-DELETED AND CLOSED ROWS ARE INCLUDED**, deliberately: both
    unique constraints count them, so a closed account still owns its number
    and its legacy reference. An index that skipped them would let the import
    believe a number was free and hand the database a duplicate.

    Carries only what the runner's rules, dry run and load need: the id (to
    address an update), the exact number and reference (for sentences), and the
    status behaviour class (an update of a CLOSED account is a different act).
    """
    index: dict[str, dict[str, Any]] = {}
    rows = models.Account.objects.filter(tenant_id=_tenant_id()).select_related("status")
    for row in rows:
        entry = {
            "id": str(row.id),
            "account_no": row.account_no,
            "external_ref": row.external_ref,
            "unit_id": str(row.unit_id) if row.unit_id else None,
            "behavior_class": row.status.behavior_class,
            # `DEF-PAY-10757` (L2-09) — the status CODE, so a payments import
            # can warn on an account in a disconnect (`marked_disconnect`,
            # `disconnected`) — a fact the behaviour class does not carry.
            "status_code": row.status.code,
        }
        if row.account_no:
            index[str(row.account_no).strip().lower()] = entry
        if row.external_ref:
            index[f"ext:{str(row.external_ref).strip().lower()}"] = entry
    return index


# ── the BR-CUS-017 read: which accounts OCCUPY a unit ───────────────────────
def account_queryset() -> QuerySet:
    return models.Account.objects.filter(tenant_id=_tenant_id()).select_related(
        "status", "account_type", "account_subtype"
    )


def occupying_accounts_for_unit(unit_id: Any, *, lock: bool = False) -> QuerySet:
    """Every account that OCCUPIES `unit_id` right now (BR-CUS-017/BR-MET-036).

    "Occupies" keys off the status's BEHAVIOUR CLASS, never its label, exactly
    as billing does (BR-CUS-055: "billing keys off the CLASS") — so a tenant
    that renames "Vacation hold/Suspended", or adds "Legal hold" (US-CUS-020
    TC-3), does not move the boundary. The two signed statements the class set
    is read from:

      · BR-CUS-018 (CONFIRMED) — a draft/pending account "never derives
        occupancy and does not block the unit for other move-ins" ⇒ the seeded
        `pending_activation` (class `non_billable`) does NOT occupy.
      · BR-MET-036 (CONFIRMED) — the unit flips to Vacant when the active
        account is CLOSED ⇒ the seeded `closed` (class `terminal`) does NOT
        occupy.

    The middle three seeded statuses — Active, Marked disconnect and Vacation
    hold/Suspended — are the occupant by both statements, and their classes are
    exactly `billable` and `billable_base_only`.

    RESIDUE, REPORTED not resolved: a tenant may add a NON-draft status in the
    `non_billable` class (BR-CUS-055 is tenant-extensible), and this reading
    would leave its unit pickable. Nothing signed says whether that is right.
    OQ-092's closure (PO 2026-08-10) ruled the ENFORCEMENT MECHANISM —
    service-layer, inside the transaction, with locking — not this class
    boundary. REPORTED in the lane report as a new question.

    `lock=True` locks the ACCOUNT rows and only those (`FOR UPDATE OF accounts`).
    Two reasons, both found on the live cluster rather than reasoned about:
    plain `FOR UPDATE` over `account_queryset()` is refused by PostgreSQL —
    "FOR UPDATE cannot be applied to the nullable side of an outer join",
    because `account_subtype` is a nullable FK and `select_related` makes it a
    LEFT JOIN — and locking `account_statuses` rows as a side effect would let
    one account write block every other account sharing its status.
    """
    from apps.customers import services

    # ⚠ **`CR-056` W1 / `BR-CUS-1012` — A NULL UNIT IS NOT A UNIT.** Since
    # migration 0036 `accounts.unit_id` is nullable, and `filter(unit_id=None)`
    # compiles to `unit_id IS NULL` — which would make EVERY `BR-CUS-1010` owner
    # account "occupy" the same imaginary unit. The first consequence is silent
    # and total: the second address in the product could not open an account,
    # because the first address's owner account would be found occupying it.
    # An account that names no unit neither occupies one nor blocks one.
    if unit_id in (None, ""):
        return models.Account.objects.none()
    base = models.Account.objects if lock else account_queryset()
    qs = base.filter(
        tenant_id=_tenant_id(),
        unit_id=unit_id,
        status__behavior_class__in=services.OCCUPYING_BEHAVIOR_CLASSES,
    )
    return qs.select_for_update(of=("self",)) if lock else qs


def owed_for_units(unit_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """**CR-089 wave E (`E1`/`PUJ-22`) — WHAT EACH UNIT OWES, FOR A LIST OF
    UNITS, IN THREE QUERIES.**

    The S15 units list carried **no money at all** across 1,109 units: a clerk
    scanning a building for arrears had to open each unit in turn. This is the
    figure that column shows.

    ⚠ **IT IS `_balance_cells`' OWN OUTPUT AND NOT A SECOND DERIVATION.** The
    number on the accounts list, the number in the S21 header, the number on the
    unit's Account tab and the number in this column are now ONE derivation
    grouped four ways — `DEF-127`'s whole lesson was that a money figure with two
    computations agrees on the day it is written and disagrees the first time a
    posting is reversed. So this resolves the occupying account exactly as
    `accounts_for_units` above does (`BR-CUS-055`'s behaviour class, first by
    `created_at`), asks the ledger ONCE for the whole page, and hands each row
    through the same cells the account row is built from.

    **THREE ABSENCES, SPELLED DIFFERENTLY, BECAUSE THEY ARE THREE FACTS:**

      * a unit **absent from the map** has no occupying account — nothing can be
        owed *by* it, and its base charges are the owner's business
        (`BR-CUS-1010`). The caller says *vacant*, never `0.00`;
      * `balance` **null** with `balance_unavailable` set means the books could
        not be asked. `DEF-127` is exactly the substitution of `0.00` for that,
        and it is the one thing this function must never do;
      * `balance_not_yet_billable` is `BR-CUS-510`'s real zero on an account
        that cannot be billed yet — a figure, and a fact about the figure.

    A PURE READ. Nothing here writes, and metering reaches it through its own
    seam rather than through this module's ORM (B1/B8).
    """
    from apps.customers import services

    ids = [unit_id for unit_id in unit_ids if unit_id not in (None, "")]
    if not ids:
        return {}
    rows = list(
        account_queryset()
        .filter(
            unit_id__in=ids,
            status__behavior_class__in=services.OCCUPYING_BEHAVIOR_CLASSES,
        )
        .select_related("status")
        .order_by("created_at", "id")
    )
    if not rows:
        return {}
    # ONE ledger read for the whole page (DEF-2723's discipline), and one bill
    # -date read, because `BR-CUS-510` clause 4 needs *has this ever been
    # billed* and asking it per row is the N+1 that measured 562 ms on S17.
    positions = _balance_positions_for([row.id for row in rows])
    last_bill_dates = seams.last_issued_invoice_dates([row.id for row in rows])
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        # First by (created_at, id) wins — `accounts_for_units`' own tie-break,
        # so the balance shown against a unit belongs to the same account whose
        # name and number are shown beside it.
        if str(row.unit_id) in out:
            continue
        cells = _balance_cells(
            row, positions, last_bill_at=last_bill_dates.get(str(row.id))
        )
        out[str(row.unit_id)] = {
            "account_id": str(row.id),
            "account_no": row.account_no,
            "balance": cells["balance"],
            "balance_currency": cells["balance_currency"],
            "balance_basis": cells["balance_basis"],
            "balance_unavailable": list(cells["balance_unavailable"]),
            "balance_not_yet_billable": cells["balance_not_yet_billable"],
        }
    return out

def accounts_for_units(unit_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """`active_account_for_unit`, for a LIST of units — two queries, not 2N.

    ⚠ **ADDED FOR CR-029 D7, AND IT ANSWERS THE IDENTICAL QUESTION.** Metering
    derives "how many accounts does this cycle bill" and "whose accounts does a
    missed read on this route affect" by asking `active_account_for_unit` once
    per unit, which is one account query plus one contact query EACH — the N+1
    D7 ruled against, on the two screens a utility opens most.

    The occupancy boundary is unchanged and is not restated here: the same
    `occupying_accounts_for_unit` reading (BR-CUS-055 — key off the behaviour
    CLASS, never the label), and the same first-by-`created_at` tie-break, so a
    unit answers identically whichever call site asks.

    Units with no occupying account are ABSENT from the map, exactly as the
    single-unit read answers `None`.
    """
    from apps.customers import services

    ids = [unit_id for unit_id in unit_ids if unit_id not in (None, "")]
    if not ids:
        return {}
    rows = list(
        account_queryset()
        .filter(
            unit_id__in=ids,
            status__behavior_class__in=services.OCCUPYING_BEHAVIOR_CLASSES,
        )
        .order_by("created_at", "id")
    )
    names = _primary_contact_names([row.id for row in rows])
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        # First by (created_at, id) wins, which is `active_account_for_unit`'s
        # own tie-break — `setdefault` keeps it without a second sort.
        out.setdefault(
            str(row.unit_id),
            {
                "id": str(row.id),
                "account_no": row.account_no,
                "customer_name": names.get(str(row.id)),
                "status": row.status.code,
                "unit_id": str(row.unit_id),
            },
        )
    return out


# Above this many units `account_ids_for_units` reads the tenant's occupying
# accounts whole instead of binding every unit id (`DEF-MET-8732`).
_BIND_UNITS_UP_TO = 2000


def account_ids_for_units(unit_ids: Any) -> dict[str, str]:
    """`{unit_id: account_id}` — `accounts_for_units` with only the id.

    ⛔ **`DEF-MET-8732` — A COUNT WAS PAYING FOR A WHOLE ROW.** `GET /cycles`
    counts each cycle's accounts by asking `accounts_for_units` for every unit
    in every cycle, and that read loads each account as a model with three
    joins, binds every unit id as a parameter and resolves every primary
    contact's NAME — 18.5 s of a 21 s read at 40,000 accounts (profiled, load
    7.7), to produce a number. This answers the same membership (the same
    occupying class set, BR-CUS-055; the same first-by-`(created_at, id)`
    tie-break, so a unit maps to the same account whichever read asks) in two
    narrow columns.

    Above `_BIND_UNITS_UP_TO` units it reads the tenant's occupying accounts
    without binding the ids and keeps the asked units — the same rows. Units
    with no occupying account are ABSENT, as in `accounts_for_units`.
    """
    from apps.customers import services

    ids = {str(unit_id) for unit_id in unit_ids if unit_id not in (None, "")}
    if not ids:
        return {}
    qs = models.Account.objects.filter(
        tenant_id=_tenant_id(),
        unit_id__isnull=False,
        status__behavior_class__in=services.OCCUPYING_BEHAVIOR_CLASSES,
    )
    if len(ids) <= _BIND_UNITS_UP_TO:
        qs = qs.filter(unit_id__in=ids)
    out: dict[str, str] = {}
    for unit_id, account_id in qs.order_by("created_at", "id").values_list("unit_id", "id"):
        key = str(unit_id)
        if key in ids and key not in out:
            out[key] = str(account_id)
    return out


def account_references(account_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """The NUMBER behind a stored `account_id`, for a whole page at a time.

    ⚠ **ADDED 2026-09-14 FOR `B30` — THE READING DETAIL'S ACCOUNT LINK.** A
    committed reading carries `meter_reads.account_id` (a reviewed cross-module
    FK, stamped at collection by `metering.services.collection_account_id`), and
    metering may not query `accounts` to turn that id into something a person
    can read. Every other seam it has answers a question about a UNIT — which is
    the wrong question here, and answering it would be WRONG rather than merely
    clumsy: a reading belongs to whoever was on supply the day it was taken, so
    resolving today's occupant would reassign a year of history to a new tenant
    the day somebody moves in. That is the exact hazard `collection_account_id`
    exists to avoid; re-introducing it at the display layer would undo it.

    **B14 rule 31 is why this returns `account_no` and not the id:** *"no
    database id is ever the visible value of a field"* — the screen shows the
    NUMBER and keeps the uuid on `title` as evidence.

    Batched, like `accounts_for_units` beside it and for the same reason: a
    reads LIST asks this of fifty rows, and asking it per row is a query per row
    on a screen a utility opens all day (`NFR-3` · the DEF-324 discipline).

    An id this tenant does not hold is ABSENT from the map, which is the same
    answer `owner_master_account_summary` gives and means the same thing: there
    is nothing to show. **It is never `{}` standing in for "we could not tell"**
    — this function either reads the tenant's own accounts or the module is not
    published at all, and the seam distinguishes those two.
    """
    ids = [account_id for account_id in account_ids if account_id not in (None, "")]
    if not ids:
        return {}
    rows = list(account_queryset().filter(pk__in=ids))
    names = _primary_contact_names([row.id for row in rows])
    return {
        str(row.id): {
            "id": str(row.id),
            "account_no": row.account_no,
            "customer_name": names.get(str(row.id)),
            "status": row.status.code,
        }
        for row in rows
    }


def message_identities(account_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """WHO a customer message is addressed to and WHERE their service is — for
    many accounts in a fixed number of statements (`CR-190-BRC10`, DEF-NOT-10440).

        -> {account_id: {account_no, customer_name, customer_kind, unit_id,
                         service_address: {line1, city, state, postal_code,
                                           unit_label} | None}}

    Published for `apps.notifications.customer_context`, the ONE place a
    customer letter's greeting, name, account number and service address are
    composed. Before it, five modules each built their own and the move-in
    welcome built none, so it printed `——` four times at a new customer.

    The service address is WALKED to the premises (hard rule 8) through
    metering's own `envelope_addresses` — four discrete columns plus the unit's
    label, never a composed string, so the composing happens once, on the far
    side. `customer_name` is `primary_contact_names_for`'s answer (the current
    customer's name, the contact's where no customer holds the account,
    `DEF-CUS-9776`), and `customer_kind` travels so a company is not greeted by
    the first word of its legal name.

    An id this tenant does not hold is ABSENT from the map (tenant-scoped
    queryset; RLS FORCE is the second guarantee, hard rule 1). Statements: one
    for the accounts, two for names, at most two for places — whatever the page
    holds (NFR-3).
    """
    ids = [str(a) for a in (account_ids or []) if a not in (None, "")]
    if not ids:
        return {}
    rows = list(account_queryset().filter(pk__in=ids))
    if not rows:
        return {}
    keys = [row.id for row in rows]
    names = primary_contact_names_for(keys)
    kinds = {key: one["kind"] for key, one in current_customers_for(keys).items()}
    unit_ids = [row.unit_id for row in rows if row.unit_id]
    premises_ids = [row.premises_id for row in rows if row.premises_id and not row.unit_id]
    envelopes = (
        seams.envelope_addresses(unit_ids=unit_ids, premises_ids=premises_ids)
        if (unit_ids or premises_ids)
        else None
    ) or {}
    by_unit = envelopes.get("units") or {}
    by_premises = envelopes.get("premises") or {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        env = (
            by_unit.get(str(row.unit_id))
            if row.unit_id
            else by_premises.get(str(row.premises_id)) if row.premises_id else None
        )
        out[str(row.id)] = {
            "account_no": (str(row.account_no).strip() or None) if row.account_no else None,
            "customer_name": names.get(str(row.id)) or None,
            "customer_kind": kinds.get(str(row.id)) or None,
            "unit_id": str(row.unit_id) if row.unit_id else None,
            "service_address": (
                {
                    "line1": env.get("line1"),
                    "city": env.get("city"),
                    "state": env.get("state"),
                    "postal_code": env.get("postal_code"),
                    "unit_label": env.get("unit_label"),
                }
                if env
                else None
            ),
        }
    return out


def _primary_contact_names(account_ids: list[Any]) -> dict[str, str | None]:
    """The name `primary_contact_name` resolves, for many accounts at once.

    The current customer's name, the primary contact's where no customer holds
    the account — `primary_contact_name`'s rule (`DEF-CUS-9776`).
    """
    # `DEF-CUS-9776` — delegates, so this cannot keep the contact-only rule
    # after `primary_contact_name` moved to the customer's name.
    return primary_contact_names_for(account_ids)


def billable_accounts() -> QuerySet:
    """BR-CUS-055's class set as a QUERYSET, with NO unit scope. Billing's seam.

    `accounts_for_bill_run` below is this plus a unit scope, and that is the
    whole relationship: **the question "may this account be billed?" is asked
    in exactly one place, and both readers ask it here.** Published separately
    because a reader that already knows the ACCOUNTS — a bulk correction
    resolving a cycle, a plan or a date range into issued bills — has no unit
    list to hand and would otherwise have to restate the class set for itself.
    A second statement of billability is a second thing to be wrong, and the
    thing it would be wrong about is who gets charged.

    ⚠ **IT IS A QUERYSET SO IT CAN BE A SUBQUERY, AND THAT IS THE POINT.**
    `NFR-5` puts no cap on a tenant and `NFR-3` pages every list, so the T5
    ceiling here is 40,000 accounts. A caller writes
    `…filter(account_id__in=billable_accounts().values("id"))` and the database
    resolves it in ONE statement; a caller that materialises the ids has
    re-introduced the limit the ceiling forbids. Nothing in this function
    fetches a row.

    Added 2026-09-15 for the PO's ruling that a bulk correction selects its
    accounts the way a bulk bill run does (`DEF-BIL-5377`) — verbatim: *"you
    will not select the bill/account in first place ; our rule to selct account
    will apply - we do this at the time of bulk billing also"*.
    """
    from apps.customers import services

    return account_queryset().filter(
        status__behavior_class__in=services.OCCUPYING_BEHAVIOR_CLASSES,
    )


def accounts_for_bill_run(unit_ids: list[str]) -> QuerySet:
    """The accounts a bill run over these units bills. Billing's scope seam.

    BILLABILITY IS A CLASS, NOT A LABEL (BR-CUS-055), and the class set here is
    deliberately the same `OCCUPYING_BEHAVIOR_CLASSES` occupancy uses: an
    account that occupies the unit is the account that gets the bill, and a
    tenant that renames "Vacation hold/Suspended" or adds a status of its own
    does not move either boundary. `billable_base_only` IS included — a
    vacation-hold account still owes its base charges, and whether THIS run
    bills it is a staff decision taken at prepare time (PO ruling 2026-08-11:
    *"you have to give option to user to opt in or opt out of this decision"*),
    not a filter applied silently here.

    Excluded classes are excluded SILENTLY on purpose, and this is the one
    place that deserves saying out loud: a `non_billable` (pending activation)
    or `terminal` (closed) account is not an exception the staff must clear —
    it is an account that is correctly not in this run, and putting 300 closed
    accounts on the exceptions screen every month is how a screen that matters
    stops being read. What DOES reach the screen is a unit in the cycle with
    no billable account at all; the run reports that, because a metered
    service point with nobody to bill is a real configuration problem.

    Ordered by account number so a run reads the same way twice.

    ⚠ **THE CLASS FILTER IS `billable_accounts()` ABOVE AND IS NOT RESTATED
    HERE** (2026-09-15). This read `account_queryset().filter(…,
    status__behavior_class__in=OCCUPYING_BEHAVIOR_CLASSES)` inline until the
    bulk-correction ruling gave billability a second reader; two inline copies
    of one class set is how a tenant discovers that a correction and a bill run
    disagree about who is billable. This function now adds ONE thing to that
    queryset — the unit scope — and that is all it has ever meant.
    """
    scope = [str(unit_id) for unit_id in unit_ids]
    return billable_accounts().filter(
        Q(unit_id__in=scope) | Q(id__in=_unit_less_masters_covering(scope)),
    ).order_by("account_no", "id")


def _unit_less_masters_covering(unit_ids: list[str]) -> list[Any]:
    """`CR-056` W1 — the master accounts in this run that name NO unit.

    ⚠ **WITHOUT THIS THE RUN CANNOT SEE THEM AT ALL, AND THE FAILURE LOOKS LIKE
    A CONFIGURATION PROBLEM RATHER THAN A MISSING ACCOUNT.** `BR-CUS-1010` moves
    the owner's account off the anchor unit and onto the address, so the
    `unit_id__in` filter above — the only way this seam has ever resolved scope
    — matches nothing for it. Every common area it covers would then be reported
    as *"in this cycle but has no billable account"* (the `DEF-572` sentence, on
    units that ARE billed) and `1408 Elm Street`'s **$69.60** would be billed to
    nobody at all.

    **IT COSTS NOTHING ON EVERY TENANT THAT EXISTS TODAY.** Every account in the
    product before 2026-09-01 names a unit, so the queryset below is empty and
    the union adds no row — which is exactly `CR-056` task 6's requirement that
    an existing Master Account bills what it billed before.

    **AND IT IS BOUNDED BY THE MASTERS, NEVER BY THE RUN.** The loop walks the
    unit-less masters (a handful — one per address whose owner has an account and
    no shared space) and asks each what it covers, rather than walking the run's
    units and asking who covers each. A 3,000-unit cycle therefore costs the same
    as a 30-unit one.
    """
    from apps.customers import services

    scope = set(unit_ids)
    if not scope:
        return []
    candidates = account_queryset().filter(
        kind=services.ACCOUNT_KIND_MASTER,
        unit_id__isnull=True,
        status__behavior_class__in=services.OCCUPYING_BEHAVIOR_CLASSES,
    )
    # 🔒 `DEF-CUS-9050` (PO 2026-10-02) — a master with NO common area still
    # owes the base of its building's empty homes (BR-CUS-170), so it is in the
    # run when ANY unit of its premises is: whether one was empty for any day of
    # the period is the gather's question (`base_charge_only_coverage` with the
    # period), and a master owing nothing is sorted `silent`, never blocked.
    # Before this it was in the run only through a common area it covered, so
    # Oak Court's owner — four homes, no hallway — was never billed at all.
    kept = []
    for account in candidates:
        reach = set(covered_unit_ids(account))
        premises_id = premises_id_for_account(account)
        if premises_id is not None:
            reach |= {str(unit.id) for unit in _units_on_premises(premises_id)}
        if scope & reach:
            kept.append(account.id)
    return kept


def last_closed_account_for_unit(unit_id: Any, *, exclude_id: Any = None) -> models.Account | None:
    """The unit's most recent FINISHED tenancy — the one whose move day
    BR-CUS-056 gives to the outgoing account.

    "Finished" is the TERMINAL behaviour class with a `closed_at` on it: the
    class is what BR-MET-036 keys occupancy off (labels are tenant-renamable),
    and the date is what the boundary rule compares against. A terminal account
    with no `closed_at` is skipped rather than treated as "closed on some
    unknown day" — slice 2 could write that state directly and the incoming
    tenancy has nothing to be measured against.

    Ordered by `closed_at` descending so a unit with several past tenancies
    answers with the latest, with `created_at`/`id` as the stable tiebreak
    (IS-2) when two closed on the same day.
    """
    from apps.customers import services

    qs = models.Account.objects.filter(
        tenant_id=_tenant_id(),
        unit_id=unit_id,
        closed_at__isnull=False,
        status__behavior_class=services.CLASS_TERMINAL,
    )
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs.order_by("-closed_at", "-created_at", "-id").first()


def active_account_for_unit(unit_id: Any) -> dict[str, Any] | None:
    """BR-MET-036's derived-occupancy input, in the shape metering's seam
    documents: `{account_no, customer_name, status}` or None."""
    row = occupying_accounts_for_unit(unit_id).order_by("created_at", "id").first()
    if row is None:
        return None
    return {
        "id": str(row.id),
        "account_no": row.account_no,
        "customer_name": primary_contact_name(row),
        "status": row.status.code,
    }


def master_account_at_premises(premises_id: Any) -> models.Account | None:
    """`BR-CUS-1011` — the active MASTER account AT this address, or None.

    ⛔ **THIS IS THE QUERY `_refuse_if_premises_has_master` ASKS, MOVED HERE SO
    THERE IS EXACTLY ONE OF IT** (`DEF-MET-6302`). The guard raises; this
    answers. A second copy of *who owns this building* is how two readers start
    disagreeing about who gets billed, which is the whole of `BR-CUS-171`'s
    history — so the guard now calls this rather than carrying its own filter.

    It keys off the status's BEHAVIOUR CLASS and never its label (`BR-CUS-055`),
    and it reads `accounts.premises_id`, which is *which premises this account
    covers*. ⚠ **THAT IS NOT THE SAME QUESTION AS *who owns this address***,
    which is `premises.master_account_id`'s and is answered by metering's
    `premises_master_account_link` — precedence 3 is never promoted to
    precedence 1 (decision log 2026-09-22). Both master and regular accounts
    carry `premises_id`; the `kind` filter here is what makes the narrower
    question lawful to ask this way.
    """
    from apps.customers import services

    if premises_id in (None, ""):
        return None
    # ⚠ **`CR-162-BRC10` — A PENDING MASTER IS ALREADY THE OWNER'S ACCOUNT.**
    # A New Connection now opens its owner master `pending_activation` (class
    # `non_billable`) until the build is approved. Keyed off the class alone,
    # that account was invisible here, so `BR-CUS-1011`'s one-master-per-address
    # guard would have let a second master open beside it. The seeded draft
    # status is named by CODE, as `activate_account` names it, never inferred
    # from the class: a `disconnected` or tenant-added non-billable master is
    # still not counted. Before 2026-10-02 no master ever opened pending, so no
    # existing answer changes.
    return (
        account_queryset()
        .filter(premises_id=premises_id, kind=services.ACCOUNT_KIND_MASTER)
        .filter(
            Q(status__behavior_class__in=services.OCCUPYING_BEHAVIOR_CLASSES)
            | Q(status__code__iexact=services.PENDING_STATUS_CODE)
        )
        .order_by("created_at", "id")
        .first()
    )


def master_account_covering_unit(unit_id: Any) -> models.Account | None:
    """BR-CUS-068: the active MASTER account covering `unit_id`, or None.

    Coverage is read through the linkage the master path writes — an OPEN
    service agreement on one of the unit's service points, held by a
    `kind='master'` account whose status class occupies (BR-CUS-055: key off
    the CLASS, never the label). `accounts.unit_id` alone cannot answer this:
    the master row ANCHORS on one common-area unit and covers the rest through
    its agreements, so the anchor test would miss every covered unit but one.

    ⚠ This is NOT `master_billing_account_for_unit` — the selector
    `apps/billing/final_bill.py` resolves for BR-BIL-013's balance-transfer
    path. That path's prerequisite is a LANDLORD-AGREEMENT FLAG (OQ-069,
    CLOSED: "transfer only when unit/premises linked to a master billing
    account under landlord-agreement flag") which has no column anywhere, so
    that name is deliberately still unpublished: publishing it against this
    read would move a closing stranger's balance onto the owner's common-area
    account on a flag nobody set. Recorded in the decision log 2026-08-22.
    """
    from apps.customers import services

    point_ids = [point["id"] for point in seams.service_points_for(unit_id)]
    if not point_ids:
        return None
    account_ids = models.ServiceAgreement.objects.filter(
        tenant_id=_tenant_id(), service_point_id__in=point_ids, ended_on__isnull=True
    ).values_list("account_id", flat=True)
    return (
        account_queryset()
        .filter(
            id__in=list(account_ids),
            kind=services.ACCOUNT_KIND_MASTER,
            status__behavior_class__in=services.OCCUPYING_BEHAVIOR_CLASSES,
        )
        .order_by("created_at", "id")
        .first()
    )


def common_area_requires_a_plan() -> bool:
    """`services.COMMON_AREA_REQUIRES_A_PLAN`, published for billing
    (`DEF-BIL-9252`). PO 2026-09-21, verbatim: *"common area dont need rate plan
    as of now; make this optional"*. The constant stays the ONE place that
    decides: billing's master gather reads it through this name, so setting it
    back to `True` restores the refusal on the bill as well as on activation."""
    from apps.customers import services

    return bool(services.COMMON_AREA_REQUIRES_A_PLAN)


def covered_unit_ids(account: models.Account) -> list[str]:
    """EVERY unit one bill for this account must price — ANCHOR FIRST.

    ⚠ **THIS IS THE READ BILLING WAS MISSING, AND ITS ABSENCE WAS DEF-571.**
    `apps/billing/gather.py` priced `account.unit_id` and nothing else, which
    is the whole truth for an ordinary account and two-thirds of a master
    account's obligation: on BR-MET-101's own worked case (1408 Elm — hallway
    lighting **$41.20** + shared irrigation **$28.40**) the owner's bill
    carried the ANCHOR's services and the second common area was billed to
    nobody, on a document that footed correctly.

    **An ordinary account answers `[unit_id]`** — the same single id billing
    has always used, so every non-master bill in this product prices
    byte-identically. The master branch is the only new behaviour.

    **A master account answers the anchor plus every OTHER unit reached
    through an OPEN service agreement** (BR-CUS-068: `accounts.unit_id` holds
    exactly one unit per BR-CUS-017, so *"attached to the premises'
    common-area units"* — plural — is expressed as one anchor plus the
    coverage `_open_master_service_agreements` writes). It is the INVERSE of
    `master_account_covering_unit`, which answers "who covers this unit"; this
    answers "what does this account cover", and both read the same rows.

    **CLOSED agreements are excluded**, exactly as `service_codes_for` excludes
    them: a common area detached from the master last month is not on this
    month's bill. **The anchor is always first and always present**, even when
    its own agreements were closed — it is what `accounts.unit_id` says, and a
    bill that silently stopped naming its own account's unit would be a
    different defect.

    Ordering after the anchor is by (label, id) — the SAME order
    `seams.common_area_units_for_premises` sorts by and therefore the order the
    anchor itself was chosen from (decision log 2026-08-22, judgment 2), so a
    run reads the same way twice (IS-2).
    """
    from apps.customers import services

    anchor = str(account.unit_id) if account.unit_id else None
    if account.kind != services.ACCOUNT_KIND_MASTER:
        return [anchor] if anchor else []
    others: set[str] = set()
    for agreement in service_agreements_for(account):
        if agreement.ended_on is not None:
            continue
        ref = seams.service_point_ref(agreement.service_point_id)
        unit_id = str(ref.get("unit_id")) if ref and ref.get("unit_id") else None
        if unit_id and unit_id != anchor:
            others.add(unit_id)
    ordered = sorted(others, key=lambda unit_id: (_unit_label(unit_id) or "", unit_id))
    return ([anchor] if anchor else []) + ordered


def _unit_label(unit_id: Any) -> str | None:
    """A unit's own label, or None when the seam cannot resolve it — used ONLY
    to order coverage deterministically, never to decide what is billed."""
    try:
        return getattr(seams.unit_row(unit_id), "label", None)
    except errors.NotFoundError:  # pragma: no cover — a PROTECTed FK cannot dangle
        return None


# ════════════════════════════════════════════════════════════════════════════
# BR-CUS-171 · A MASTER'S CHILDREN — DERIVED FROM THE PREMISES, NEVER STORED
# BR-CUS-170 · WHAT A MASTER'S ONE BILL MUST COVER
#
# 🔒 HUMAN-REVIEW-PENDING — these two reads decide WHOSE BILL a unit's base
# charge lands on, which is a money decision even though nothing here computes
# a figure. Ledger row: 12-governance/09-human-review-ledger.md.
#
# PO ruling 2026-08-27 (closing OQ-531), verbatim:
#
#   "so you are right if premise P has owner A and units U1 to U10; out of U1
#    to U5 - has accounts - regular accounts - all these accounts are child of
#    Owner A; common areas on premise P, also attached to owner A. when bill is
#    generated for A - we should consider common areas and U6 to U10 base
#    charges ; U1 to U5 bill be send to Accounts assocaited with U1 to U5; if
#    U1 leave and dont pay $500 then $500 Debt is shifted to Owner A, if clark
#    tied back to A during move out process"
#
# **NO COLUMN AND NO MIGRATION.** `accounts` gains no parent id: a stored copy
# of a fact the premises already carries is a second place for it to be wrong,
# and it would need a clerk to maintain it through every move-in and move-out.
# The link is READ, which is also why CR-040's "the master has no children" was
# a REPORTING gap rather than a data gap — `500 Main Street`'s five accounts
# have been children of `AC-2026-00052` since the day both were seeded.
# ════════════════════════════════════════════════════════════════════════════
def _premises_id_for_unit(unit_id: Any) -> str | None:
    """The premises a unit sits on, or None when the seam cannot answer.

    Read through metering's own row (B1: customers touches no other module's
    ORM). None is a real answer — an account with no `unit_id` has no premises
    and therefore no master and no children, which is every standalone account
    in the product.
    """
    if unit_id in (None, ""):
        return None
    try:
        row = seams.unit_row(unit_id)
    except errors.NotFoundError:  # pragma: no cover — a PROTECTed FK cannot dangle
        return None
    premises_id = seams.unit_dict(row).get("premises_id")
    return str(premises_id) if premises_id else None


def premises_id_for_account(account: models.Account) -> str | None:
    """The ADDRESS this account hangs off — the stored column first, the unit's
    premises second (`CR-056` W1 / `BR-CUS-1010`).

    ⚠ **THE ORDER IS THE WHOLE POINT AND IT IS NOT A FALLBACK CHAIN THAT CAN
    DISAGREE.** `accounts.premises_id` is written at creation from 2026-09-01 and
    backfilled FROM THE UNIT'S OWN PREMISES for every row that predates it, so
    where both are present they are the same address by construction. The unit
    leg exists for exactly one case: a row the 0036 backfill could not resolve
    (metering cannot answer for its unit), where the derivation is still the best
    honest answer and was the only one this module ever had.

    `None` is a real answer and always was — a standalone account whose unit the
    seam cannot resolve has no premises, therefore no master and no children.
    """
    stored = getattr(account, "premises_id", None)
    if stored not in (None, ""):
        return str(stored)
    return _premises_id_for_unit(getattr(account, "unit_id", None))


def _units_on_premises(premises_id: Any) -> list[Any]:
    """Every ACTIVE unit of one premises, common areas included, ordered.

    Reached through the GENERIC seam rather than a named wrapper because
    `apps.customers.seams.resolve` already reaches metering and this read wants
    the whole unit list, not the common-area slice
    `common_area_units_for_premises` carves out of it. An unpublished seam
    answers `[]`, which degrades every caller below to "this master covers only
    what its service agreements say" — today's behaviour, and the one that
    cannot invent a charge.
    """
    if premises_id in (None, ""):
        return []
    units_list = seams.resolve("metering", "units_list", kind="selectors")
    if units_list is None:
        return []
    rows = [
        row
        for row in units_list(filters={"premises_id": premises_id})
        if getattr(row, "deleted_at", None) is None
    ]
    rows.sort(key=lambda row: ((getattr(row, "label", "") or ""), str(row.id)))
    return rows


def master_account_for(account: models.Account) -> models.Account | None:
    """BR-CUS-171 as SUPERSEDED — the master account this account is a child of.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE GEOMETRIC DERIVATION IS RETIRED (PO ruling 2026-08-27, DEF-650)  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    **PO verbatim:** *"so premises owner is master accountin system … Bascially
    Premises -> owner = Master account"*, and, on the derivation itself
    (decision 4, after the PO said the question as first asked was not
    understandable): *"to find a building's master today, the code does not look
    at the owner at all — it looks at the building's COMMON AREAS (the hallway,
    the car park) and finds the account that pays for them. Whoever pays for the
    hallway is treated as the owner. … The ruling replaces all of it: the
    premises names its owner, the owner is the master, and nothing is inferred
    from hallways."*

    **WHAT THIS FUNCTION USED TO DO, kept in words because the behaviour change
    is the point:** it walked the premises' common areas, asked
    `master_account_covering_unit` for each, and answered `None` unless exactly
    one master came back. That had the two weaknesses the ruling names, and
    **both are gone by construction here rather than by a better tie-break**:

    * a premises with **no common area** — a single-family home, the PO's own
      next question — had nothing to look at and therefore no master at all;
    * where **two masters** covered two common areas the code could not tell
      which was the owner, so it refused by answering `None` and the building
      had no master either.

    ⚠ **RETIRED, NOT KEPT AS A FALLBACK, AND THE RULING GIVES THE REASON:**
    *"because a fallback that disagrees with the declared owner would silently
    bill a different party."* So there is no `or` here. A premises with no
    declared owner answers `None` — which is honest, is visible on the premises
    screen, and is fixed by declaring the owner rather than by inferring one.

    **A master is still not its own child**, for the same reason as before:
    without the guard the owner's own account would answer itself and
    `sub_accounts_for_master` would list the owner among their own tenants.
    """
    if account.kind == services_master_kind():
        return None
    # `CR-056` W1 — the account's OWN address when it has one, its unit's
    # premises otherwise. Identical answer for every row that predates 0036.
    premises_id = premises_id_for_account(account)
    if premises_id is None:
        return None
    master_id = seams.owner_master_account_for_premises(premises_id)
    if master_id in (None, ""):
        return None
    master = account_queryset().filter(pk=master_id).first()
    if master is None or str(master.id) == str(account.id):
        return None
    return master


def sub_accounts_for_master(master: models.Account) -> list[models.Account]:
    """BR-CUS-171 — every OCCUPYING account on this master's premises.

    The inverse of `master_account_for`, and it reads the same rows. "Occupying"
    keys off the status's BEHAVIOUR CLASS and never its label
    (`occupying_accounts_for_unit`, BR-CUS-055), so a closed tenant drops out of
    the list on the day they close and a pending one never appears — which is
    what makes the link maintenance-free. **The master itself is excluded**, as
    is any OTHER master covering the same premises: a landlord is not their own
    sub-account.

    Answers `[]` for an account that is not a master, rather than raising: the
    S17 row and the S21 header ask this of every account.
    """
    if master.kind != services_master_kind():
        return []
    # ⚠ **THE DECLARED OWNERSHIP FIRST (DEF-650, PO 2026-08-27).** The old
    # reading was *the premises my ANCHOR UNIT sits on* — the hallway inference
    # seen from the other end, and it would list one building's tenants under an
    # owner whose declared ownership says otherwise. The anchor unit is still
    # read where NOTHING declares this account as an owner, which is not a
    # disagreeing fallback: it is the pre-ruling master accounts, still covering
    # the common areas `create_master_account` attached them to.
    premises_ids = [
        pid for pid in seams.premises_ids_owned_by_account(master.id) if pid not in (None, "")
    ]
    if not premises_ids:
        # `CR-056` W1 — and the STORED address is read before the anchor's, so a
        # `BR-CUS-1010` owner account nobody has declared as an owner still finds
        # its own building instead of answering `[]` (it has no anchor unit to
        # derive one from). Same sentence as the comment above: this is not a
        # disagreeing fallback, it is *which premises this account covers*.
        anchor_premises_id = premises_id_for_account(master)
        if anchor_premises_id is None:
            return []
        premises_ids = [anchor_premises_id]
    children: list[models.Account] = []
    seen: set[str] = set()
    for unit in [row for premises_id in premises_ids for row in _units_on_premises(premises_id)]:
        for row in occupying_accounts_for_unit(unit.id).order_by("created_at", "id"):
            if str(row.id) == str(master.id) or row.kind == services_master_kind():
                continue
            if str(row.id) in seen:
                continue
            seen.add(str(row.id))
            children.append(row)
    return children


def vacant_days_in_period(unit_id: Any, period_start: Any, period_end: Any) -> int:
    """🔒 HUMAN-REVIEW-PENDING (money path) — `DEF-CUS-9050`, PO 2026-10-02.

    How many days of `[period_start, period_end]` (both inclusive) NO account
    occupied this unit. PO ruling 2026-10-02 (option A): an empty unit's base is
    the owner's *"until a tenant moves in"*, and *"the owner stops paying from
    the tenant's move-in date (prorated like any base); a unit empties again at
    move-out and the owner resumes"*. Worked: a move-in on 16 September is 15
    vacant days of 30 → the owner's $8.00 water base becomes **$4.00**.

    A tenancy occupies from `opened_at` (the move-in day) through `closed_at`
    (the move-out day) inclusive. The tenancies counted are the ones occupancy
    already counts — an OCCUPYING class (`occupying_accounts_for_unit`) — plus
    the FINISHED ones (terminal, with a `closed_at`), which is how a move-out
    inside the period hands the rest of it back to the owner. A draft or
    pending account occupies nothing (BR-CUS-018). An occupying account with no
    `opened_at` is read as occupying the whole period: an account with no
    move-in day is not evidence the unit was empty.
    """
    from apps.customers import services

    total = (period_end - period_start).days + 1
    if total <= 0:
        return 0
    occupied: set[Any] = set()
    tenancies = list(occupying_accounts_for_unit(unit_id).values_list("opened_at", "closed_at"))
    tenancies += list(
        models.Account.objects.filter(
            tenant_id=_tenant_id(),
            unit_id=unit_id,
            closed_at__isnull=False,
            status__behavior_class=services.CLASS_TERMINAL,
        ).values_list("opened_at", "closed_at")
    )
    for opened, closed in tenancies:
        start = max(opened or period_start, period_start)
        end = min(closed or period_end, period_end)
        day = start
        while day <= end:
            occupied.add(day)
            day = day + timedelta(days=1)
    return total - len(occupied)


def base_charge_only_coverage(
    account: models.Account, *, period_start: Any = None, period_end: Any = None
) -> list[dict[str, Any]]:
    """BR-CUS-170 — the units on this master's premises that NOBODY ELSE PAYS
    FOR, which is what the owner's bill must additionally carry.

    PO 2026-08-27: *"when bill is generated for A - we should consider common
    areas and U6 to U10 base charges ; U1 to U5 bill be send to Accounts
    assocaited with U1 to U5"*. **The master is NOT a consolidator** — it does
    not sweep up its children's charges; each occupied unit's customer gets
    their own bill. The master pays for the common parts and the empty units,
    which is what a landlord actually owes.

    **THE EXCLUSION TEST IS THE ACCOUNT, NEVER A FLAG.** A unit is on the
    owner's bill exactly when `occupying_accounts_for_unit` is empty for it, so
    a move-in takes it off the owner's bill on the day it happens and nobody
    has to remember to un-tick anything. A flag would be a second place for the
    same fact to live and a maintenance task no clerk would be told about.

    **COMMON AREAS ARE NOT IN THIS LIST.** They are already covered through the
    master's own open service agreements (`covered_unit_ids`), which is the
    linkage BR-CUS-068 signed; listing them twice would price them twice.

    Each entry carries the two facts billing needs to decide whether anything
    is actually being omitted — `has_plan` and `service_point_count`. A unit
    with neither has NO base charge to omit, which is why `1408 Elm`'s three
    ordinary units leave the signed $41.20 + $28.40 = $69.60 untouched.

    Answers `[]` for every account that is not a master, so an ordinary bill is
    byte-identical and issues no extra query.
    """
    if account.kind != services_master_kind():
        return []
    # `CR-056` W1 — the stored address first (`BR-CUS-1010`), the anchor unit's
    # premises for every master created before migration 0036. ⚠ THIS IS THE READ
    # THE 2026-08-31 PER-UNIT RULING LANDS ON: six empty flats at $30.50 bill
    # $183.00 to the owner, one line each, and a unit-less owner account that
    # answered `[]` here would bill none of them.
    premises_id = premises_id_for_account(account)
    if premises_id is None:
        return []
    covered = {str(unit_id) for unit_id in covered_unit_ids(account)}
    dated = period_start is not None and period_end is not None
    coverage: list[dict[str, Any]] = []
    for unit in _units_on_premises(premises_id):
        unit_id = str(unit.id)
        if unit_id in covered or getattr(unit, "is_common_area", False):
            continue
        entry: dict[str, Any] = {
            "unit_id": unit_id,
            "label": getattr(unit, "label", None),
        }
        if dated:
            # 🔒 `DEF-CUS-9050` (PO 2026-10-02) — ASKED FOR A PERIOD, the answer
            # is BY THE DAY: a unit let for part of the period is the owner's
            # for the days nobody occupied it, and the bill prorates its base
            # by `vacant_days / period_days`. A unit let for the whole period
            # is not on the list. Undated callers (screens, counts) keep the
            # right-now answer below, unchanged.
            vacant = vacant_days_in_period(unit.id, period_start, period_end)
            if vacant <= 0:
                continue
            entry["vacant_days"] = vacant
            entry["period_days"] = (period_end - period_start).days + 1
        elif occupying_accounts_for_unit(unit.id).exists():
            continue
        entry["has_plan"] = getattr(unit, "rate_plan_id", None) is not None
        entry["service_point_count"] = len(seams.service_points_for(unit.id))
        coverage.append(entry)
    return coverage


def premises_scope_for_account(account_id: Any) -> dict[str, Any] | None:
    """**WHICH UNITS A MASTER ACCOUNT MAY PAY FOR, AND WHO OCCUPIES EACH.**

    `CR-059` **CS-27**, the sub-metering core case, and this function is the
    published B1 seam it names: *"A premises-scoped read: the units of a
    premises, their occupying accounts and what each owes."* **What each owes is
    NOT here and must not be** — that is money, payments owns it
    (`apps/payments/premises_position.py` joins this answer to the open-bill
    position), and a customers read that priced bills would be this module
    deciding what a bill is.

    ⚠ **THIS EXISTS BECAUSE PAYMENTS HAD NO WAY TO ASK, AND REACHING THROUGH
    WOULD HAVE BEEN THE BUG.** Payments may not touch `accounts`,
    `customer_accounts` or metering's `units` (B1/B8), and CS-27's join —
    unit → premises → owner → master — is three modules wide. It is authored
    HERE, by the module that owns the tables, exactly as `customer_exists` was
    authored here for metering.

    **THE AUTHORITY QUESTION IS A RELATIONSHIP QUESTION, AND THAT IS A PO
    RULING (2026-09-01), not a simplification made here.** CS-27 first drew a
    consent check; the PO ruled that a master **may always** pay a unit's bill
    (*"anyone may pay any bill; the tenant's agreement is not required"*) and
    that paying it **does** give the master sight of that bill. So the only
    question left is *is this unit on this master's premises?* — which is what
    `account_ids` answers, and payments checks membership of that set and
    nothing else.

    **NOTHING NEW IS DERIVED HERE.** `sub_accounts_for_master` is BR-CUS-171's
    own read and already answers *every OCCUPYING account on this master's
    premises*, keyed off the status BEHAVIOUR CLASS (BR-CUS-055) so a closed
    tenant drops out on the day they close and a pending one never appears. This
    function groups that same answer by unit and states the premises it walked,
    so a screen can draw the building rather than a flat list of strangers.

    **`None` for an account that is not a master**, which is not an error and is
    the answer for nearly every account in the product: an ordinary account pays
    its own bills and has no premises scope. **An empty `units` list is a real
    measured answer** — a master whose premises nobody declares, or a building
    with no occupied unit — and the caller must be able to tell that apart from
    "this account is not a master", which is why the two are different returns.

    ⚠ **THE OWNER LINK IS NULLABLE AND AN UNOWNED PREMISES HAS NOBODY TO
    AUTHORISE**, which CS-27 names as *"the join to build carefully"*. That case
    arrives here as `premises_ids: []` and therefore `account_ids: []`, so every
    part of a premises tender is refused by name rather than silently allowed —
    the safe direction, and the one a clerk can act on by declaring the owner.
    """
    account = account_queryset().filter(pk=account_id).first()
    if account is None or account.kind != services_master_kind():
        return None
    # The DECLARED ownership first (DEF-650, PO 2026-08-27: *"Premises -> owner =
    # Master account"*), the anchor unit's premises for a master nobody has
    # declared as an owner. Identical reasoning and identical order to
    # `sub_accounts_for_master`, deliberately — two answers about one building
    # that disagreed on which building it was would be worse than either.
    premises_ids = [
        pid for pid in seams.premises_ids_owned_by_account(account.id) if pid not in (None, "")
    ]
    if not premises_ids:
        anchor = premises_id_for_account(account)
        premises_ids = [anchor] if anchor is not None else []

    payable = {str(row.id): row for row in sub_accounts_for_master(account)}
    units: list[dict[str, Any]] = []
    seen_accounts: set[str] = set()
    for premises_id in premises_ids:
        for unit in _units_on_premises(premises_id):
            occupants = []
            for row in occupying_accounts_for_unit(unit.id).order_by("created_at", "id"):
                if str(row.id) not in payable:
                    continue
                seen_accounts.add(str(row.id))
                occupants.append(
                    {
                        "account_id": str(row.id),
                        "account_no": row.account_no,
                        "customer_name": primary_contact_name(row),
                        "status_code": row.status.code if row.status_id else None,
                    }
                )
            units.append(
                {
                    "unit_id": str(unit.id),
                    "label": getattr(unit, "label", None),
                    "premises_id": str(premises_id),
                    "is_common_area": bool(getattr(unit, "is_common_area", False)),
                    "accounts": occupants,
                }
            )
    return {
        "payer_account_id": str(account.id),
        "payer_account_no": account.account_no,
        "payer_name": primary_contact_name(account),
        "premises_ids": [str(pid) for pid in premises_ids],
        "units": units,
        # The membership test, flat, because that is the whole of the authority
        # check and a caller should not have to re-walk the tree to make it.
        # ⚠ It is `payable`, not `seen_accounts`: BR-CUS-171's read is the
        # authority, and an account it names whose unit the metering seam cannot
        # resolve is still on this master's premises. Dropping it here would
        # refuse a lawful payment because a LABEL could not be looked up.
        "account_ids": sorted(payable),
    }


def services_master_kind() -> str:
    """`services.ACCOUNT_KIND_MASTER`, resolved lazily.

    A function and not a module-level import because `apps.customers.services`
    imports this module; the four readers above are the only callers and each
    is a read path, so the indirection costs nothing a query does not already."""
    from apps.customers import services

    return services.ACCOUNT_KIND_MASTER


# ── contacts / addresses / agreements (customers-owned children) ────────────
#: Which live `customer_accounts` link names an account when it has several
#: (a jointly-held account, BR-CUS-054's N:M): the OLDEST, which is
#: `customer_for_account`'s own order with `id` as the tiebreaker.
CUSTOMER_NAME_ORDER = ("created_at", "id")


def current_customers_for(account_ids: Any) -> dict[str, dict[str, str]]:
    """`{account_id: {"name", "kind"}}` — the CURRENT customer that NAMES each
    account, ONE query for a page. The single source behind
    `customer_names_for` (and so `primary_contact_name`, `DEF-CUS-9776`) and
    `company_names_for` (the partner API, `DEF-INT-9796`): the same link, the
    same order, the same blank-name skip, so a screen and a partner payload
    cannot pick two different customers for one account. Blank names are left
    out, so a caller falls back to the contact rather than printing nothing."""
    ids = [str(a) for a in (account_ids or []) if a]
    if not ids:
        return {}
    found: dict[str, dict[str, str]] = {}
    for account_id, display_name, kind in (
        models.CustomerAccount.objects.filter(
            tenant_id=_tenant_id(), account_id__in=ids, ended_at__isnull=True
        )
        .order_by(*CUSTOMER_NAME_ORDER)
        .values_list("account_id", "customer__display_name", "customer__kind")
    ):
        if (display_name or "").strip():
            found.setdefault(
                str(account_id), {"name": display_name.strip(), "kind": str(kind or "")}
            )
    return found


def customer_names_for(account_ids: Any) -> dict[str, str]:
    """`{account_id: customer display_name}` for the accounts a CURRENT customer
    holds — ONE query for a page (`current_customers_for`)."""
    return {key: one["name"] for key, one in current_customers_for(account_ids).items()}


#: `customers.kind` for an organisation (B2 r9 #1: person | company).
CUSTOMER_KIND_COMPANY = "company"


def company_names_for(account_ids: Any) -> dict[str, str]:
    """`{account_id: legal name}` for the accounts whose naming customer is a
    COMPANY — ONE query for a page. A company's `display_name` IS its legal
    name (`owner_lookup` serves it as `legal_name`). Read by the partner
    Customers API, PO ruling 2026-10-06 D3 (a) (`DEF-INT-9796`)."""
    return {
        key: one["name"]
        for key, one in current_customers_for(account_ids).items()
        if one["kind"] == CUSTOMER_KIND_COMPANY
    }


@batch_reads.memoised
def primary_contact_name(account: models.Account) -> str | None:
    """THE ACCOUNT'S NAME, wherever an account or an occupant is named —
    US-CUS-001 §5 "Name". The function keeps its old name because 60-odd
    callers across six modules resolve it by that name.

    ⚠ **IT IS THE CUSTOMER'S NAME, AND UNTIL 2026-10-06 IT WAS THE CONTACT'S
    (`DEF-CUS-9776`).** This read was written when the first-class customer
    entity (BR-CUS-054) was not built, so it named the primary CONTACT — and it
    went on doing that after the entity landed. For a person the two are the
    same name, which is why nothing saw it; for a COMPANY the contact is the
    person who answers the phone, so *Grace Fellowship of Cedar Ford* read
    *Ruth Okafor* on its own account title, unit and meter.

    **The rule now:** the CURRENT customer's `display_name` (a live link —
    `ended_at IS NULL`, so a sold account names its buyer, not its seller),
    the oldest link first; the primary contact's name only where no current
    customer holds the account (every account opened before BR-CUS-054's
    entity existed). Every plural form below applies the SAME rule —
    `primary_contact_names_for`, `prime_check_batch` and the list's ORDER BY
    subquery — so a list and a detail page cannot name one account twice."""
    names = customer_names_for([account.pk])
    if names:
        return names[str(account.pk)]
    row = (
        models.Contact.objects.filter(
            tenant_id=account.tenant_id, account=account, deleted_at__isnull=True
        )
        .order_by("-is_primary", "created_at", "id")
        .first()
    )
    return row.full_name if row is not None else None



def prime_check_batch(accounts: Any) -> dict[str, int]:
    """B27 — ONE BULK CHECK BATCH'S CUSTOMER FACTS, IN THREE QUERIES.

    Primes the batch memo (`core.batch_reads`) with each account's service
    agreements (`service_agreements_for`), primary contact's name
    (`primary_contact_name`) and dark days (`service_off_windows`) — the
    per-account reads the Check made one account at a time. Each list is
    ordered by the per-account read's own `ORDER BY` in the database, after
    `account_id`, and split by account; each row is built by the per-account
    read's own code (`disconnects.off_windows_from`). `accounts` are this
    module's own rows, already in the caller's hand. Nothing is primed outside
    a batch."""
    from apps.customers import disconnects

    if batch_reads.active() is None:
        return {}
    rows = [a for a in (accounts or ()) if getattr(a, "pk", None) is not None]
    if not rows:
        return {}
    ids = [a.pk for a in rows]
    tenant_id = _tenant_id()
    agreements: dict[str, list[Any]] = {str(i): [] for i in ids}
    for agreement in models.ServiceAgreement.objects.filter(
        tenant_id=tenant_id, account_id__in=ids
    ).order_by("account_id", "started_on", "id"):
        agreements.setdefault(str(agreement.account_id), []).append(agreement)
    names: dict[str, str | None] = {}
    for account_id, full_name in (
        models.Contact.objects.filter(
            tenant_id=tenant_id, account_id__in=ids, deleted_at__isnull=True
        )
        .order_by("account_id", "-is_primary", "created_at", "id")
        .values_list("account_id", "full_name")
    ):
        names.setdefault(str(account_id), full_name)
    # `DEF-CUS-9776` — the customer's name wins over the contact's, exactly as
    # in `primary_contact_name`; the batch must prime the same answer.
    names.update(customer_names_for(ids))
    cuts: dict[str, list[dict[str, Any]]] = {str(i): [] for i in ids}
    for row in (
        disconnects.DisconnectCase.objects.filter(
            tenant_id=tenant_id, account_id__in=ids, cut_on__isnull=False
        )
        .order_by("account_id", "-cut_on", "-created_at")
        .values("account_id", "id", "state", "cut_on", "reconnected_on", "services_cut")
    ):
        cuts.setdefault(str(row["account_id"]), []).append(row)
    # `CR-162-BRC10` — the awaiting-activation windows `service_off_windows`
    # adds, primed from ONE query for the batch so the Check and a single bill
    # read the same dark days.
    from apps.customers import activation_windows

    builds = seams.units_build_services([a.unit_id for a in rows if a.unit_id])
    for account in rows:
        key = str(account.pk)
        batch_reads.prime(service_agreements_for, list(agreements.get(key, [])), account)
        batch_reads.prime(primary_contact_name, names.get(key), account)
        batch_reads.prime(
            service_off_windows,
            tuple(disconnects.off_windows_from(cuts.get(key, [])))
            + activation_windows.awaiting_activation_windows(
                account, builds.get(str(account.unit_id), [])
            ),
            key,
        )
    return {"accounts": len(rows)}


def primary_contact_names_for(account_ids: Any) -> dict[str, str | None]:
    """The plural of `primary_contact_name` — **ONE query for a whole page.**

    ⛔ **DEF-2723's `contacts` statement per row.** The accounts list drew the
    Name cell by asking for one account's primary contact, once per account: at
    seventy-three accounts that is seventy-three round trips for one column, and
    it is one of the NINE statements per row behind a 562 ms list.

    ⚠ **THE ORDER IS THE SINGULAR'S ORDER, AND IT HAS TO BE.** `-is_primary,
    created_at, id` decides WHICH contact is "the" name when an account has
    several, and a batched read that sorted differently would quietly rename
    customers on the list while their detail page kept the old name — a
    regression no statement count can see. The rows come back in that order and
    the FIRST per account wins, which is `.first()` applied to a page.
    """
    ids = [str(a) for a in (account_ids or [])]
    if not ids:
        return {}
    names: dict[str, str | None] = {}
    for row in (
        models.Contact.objects.filter(
            tenant_id=_tenant_id(), account_id__in=ids, deleted_at__isnull=True
        )
        .order_by("-is_primary", "created_at", "id")
        .values_list("account_id", "full_name")
    ):
        names.setdefault(str(row[0]), row[1])
    # `DEF-CUS-9776` — `primary_contact_name`'s rule: a current customer's name
    # first, the contact's only where no customer holds the account.
    names.update(customer_names_for(ids))
    return names


def service_codes_for_accounts(accounts: Any) -> dict[str, list[str]]:
    """`{account_id: [service code, …]}` — the CHIPS half of
    `service_codes_and_drops_for_accounts`, kept as its own name because two
    callers outside this module read it (`apps/runbooks/seams/customers_seam`
    and `account_row`'s singular fallback) and neither has a use for the drop
    count."""
    return service_codes_and_drops_for_accounts(accounts)[0]


def service_codes_and_drops_for_accounts(
    accounts: Any,
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """`({account_id: codes}, {account_id: skipped})` — **a constant number of
    queries for a whole page**, whatever it holds.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  `DEF-CUS-6917` — WHY THE SECOND MAP EXISTS                          ║
    ╚══════════════════════════════════════════════════════════════════════╝
    The loop below skips an open agreement whose service point it cannot
    resolve to a code, and until 2026-09-27 it skipped it **in silence**: the
    row rendered as a perfectly good row with fewer chips, every test passed,
    and nothing anywhere carried a number. That is CLAUDE.md hard-won law 7's
    fifth shape verbatim — *a declared blind spot with no number beside it is
    indistinguishable from an empty one* — and it is the shape the PO's report
    of `AC-2026-00057` could not be answered in, because *two chips* is the
    same picture whether the account took two services or took four and this
    read lost two of them.

    **The count is not a guess at the cause; it is what separates the causes.**
    A drop count of zero says the chips are the whole truth of what this
    account agreed to take, so a short row is a move-in that ticked fewer
    services (`BR-CUS-672`) and the question moves upstream to the agreements.
    A non-zero count says this read lost something and names how much.

    **THREE WAYS IT CAN BE NON-ZERO, and a null service column is NOT one of
    them** — `service_points.service_id` is `NOT NULL` with a `PROTECT` FK and
    `services.code` is `NOT NULL` (measured against `information_schema` on
    2026-09-27), so a service point with no service cannot be stored:
      * the agreement names a point this tenant cannot see, or no longer holds
        a row — the hard-rule-1 boundary expressed, correctly, as absence;
      * the id is not a UUID, which both metering batch reads drop on the way
        in;
      * **metering's seam does not resolve at all**, in which case both reads
        answer `{}` and EVERY chip on the page disappears at once. That last
        one is why the count is per account and the log line is per account:
        a page-wide zero is a very different incident from one bad row, and
        the two are told apart by how many rows carry a count.

    ⛔ **DEF-2723's remaining six statements per row**, and they were six rather
    than the obvious one:

      * `service_agreements_for` ran TWICE per account — once inside
        `_service_by_point_for` and once in `service_codes_for` itself;
      * `seams.service_points_for` ran once per account;
      * every point that read then cost a catalog probe for its service CODE
        (three services meant three more);
      * and `seams.service_catalog_order()` — a read of the platform catalogue,
        identical for every row — ran once per account.

    All of it happens once now: one agreements query for the page, one points
    query for the page's units, `service_codes_for_points` for any point outside
    them, and one catalogue order.

    ⚠ **THE MASTER-ACCOUNT LEG IS KEPT** (`BR-CUS-068`). A master holds
    agreements on OTHER covered common-area units' points, which the anchor read
    does not cover; `_service_by_point_for` resolved those one at a time and
    this resolves them in one call. Dropping the leg would have made the Services
    cell undercount an owner's coverage — a speed-up that changes an ANSWER,
    which a statement count cannot see, and which is why the test beside this
    asserts the chips by value.
    """
    accounts = list(accounts or [])
    if not accounts:
        return {}, {}
    ids = [str(a.id) for a in accounts]
    agreements: dict[str, list[models.ServiceAgreement]] = {}
    for agreement in models.ServiceAgreement.objects.filter(
        tenant_id=_tenant_id(), account_id__in=ids
    ).order_by("started_on", "id"):
        agreements.setdefault(str(agreement.account_id), []).append(agreement)

    unit_ids = [str(a.unit_id) for a in accounts if a.unit_id]
    points_by_unit = seams.service_points_for_units(unit_ids)
    service_by_point: dict[str, str | None] = {}
    for points in points_by_unit.values():
        for point in points:
            service_by_point[str(point["id"])] = point["service"]

    # Whatever the anchor units did not cover — the master account's other
    # common areas — resolved in ONE more call rather than one per point.
    missing = {
        str(agreement.service_point_id)
        for rows in agreements.values()
        for agreement in rows
        if str(agreement.service_point_id) not in service_by_point
    }
    if missing:
        service_by_point.update(seams.service_codes_for_points(sorted(missing)))

    # `BR-CUS-1093` — the MASTER accounts' buildings, in ONE more call for the
    # whole page. Asked only for the accounts that need it: an ordinary account
    # takes its services from its unit and this read is not its question.
    premises_services = _premises_services_for_masters(accounts)

    catalog = seams.service_catalog_order()
    out: dict[str, list[str]] = {}
    drops: dict[str, int] = {}
    by_id = {str(a.id): a for a in accounts}
    for account_id in ids:
        codes: set[str] = set()
        skipped = 0
        for agreement in agreements.get(account_id, ()):
            if agreement.ended_on is not None:
                continue
            code = service_by_point.get(str(agreement.service_point_id))
            if code:
                codes.add(code)
            else:
                # NOT `continue`-and-forget. See this function's docstring:
                # the skip is the answer to the PO's question, so it is
                # counted here and reported by `_report_service_chip_drops`.
                skipped += 1
        codes.update(_premises_service_codes(by_id[account_id], premises_services))
        out[account_id] = sorted(
            codes,
            key=lambda code: (catalog.index(code) if code in catalog else len(catalog), code),
        )
        drops[account_id] = skipped
    _report_service_chip_drops(drops)
    return out, drops


def _report_service_chip_drops(drops: dict[str, int]) -> None:
    """`DEF-CUS-6917` — the number, said out loud, where an operator can read it.

    ⚠ **THE SCREEN IS NOT ENOUGH ON ITS OWN AND THE LOG IS NOT EITHER.** A chip
    in the cell tells the clerk in front of the row that this cell is short of
    what the account holds; it cannot tell anybody that it happened at all on a
    page nobody opened. This line is the other half: one WARNING per affected
    account, with the tenant and the account id, so *how often does this
    happen* is a question the product can answer rather than a thing somebody
    has to notice.

    **NO CUSTOMER NAME, NO ADDRESS, NO ACCOUNT NUMBER** — `BR-CUS-045` makes
    those PII and a log stream is not a place that holds PII. An account id is
    what an operator pastes into a query; it is also why B14 rule 31 does not
    apply here — a log line is not a screen and has no visible field.

    **SILENT WHEN THERE IS NOTHING TO SAY.** A page with no drops writes no
    line, so a line in the log means something, which is the only way a log
    line ever means anything.
    """
    affected = {account_id: n for account_id, n in drops.items() if n}
    if not affected:
        return
    tenant_id = _tenant_id()
    for account_id, n in sorted(affected.items()):
        logger.warning(
            "DEF-CUS-6917 service chips dropped: tenant=%s account=%s unresolved=%d",
            tenant_id,
            account_id,
            n,
        )


def _premises_services_for_masters(accounts: Any) -> dict[str, list[str] | None]:
    """`{premises_id: services}` for the MASTER accounts in this set — one call.

    `BR-CUS-1093` is a rule about one kind of account, so this asks metering
    only about the buildings that have one. On a page with no master account it
    makes **no query at all**, which is why the statement count
    `test_def2723_accounts_list_statement_count.py` pins does not move for the
    ordinary case.
    """
    master = services_master_kind()  # resolved ONCE, not once per row
    wanted = sorted(
        {str(a.premises_id) for a in (accounts or []) if a.kind == master and a.premises_id}
    )
    return seams.premises_services_for(wanted) if wanted else {}


def _premises_service_codes(
    account: models.Account, premises_services: dict[str, list[str] | None]
) -> set[str]:
    """`BR-CUS-1093` — what the BUILDING offers, for a master account only.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  TWO SIGNED RULES, EACH CORRECT, WHOSE INTERSECTION WAS EMPTY        ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `BR-CUS-1010` hangs a master account off the ADDRESS and leaves
    `accounts.unit_id` NULL. `BR-CUS-672` inherits an account's services FROM
    ITS UNIT. An account with no unit therefore got **no services**. The PO
    reported it — *"it is not taking utility service applicable also not taking
    plan"* — it was answered as correct-by-rule, and they ruled the missing
    clause instead: *"in case of mater account - we will have to take utility
    servcies from premies, since it belong to premises"* (`BR-CUS-1093`,
    2026-09-23).

    ⚠ **THE PLAN HALF OF THAT REPORT IS NOT THIS FUNCTION'S, AND THREE LIVE
    SURFACES SAID IT WAS** — `BR-CUS-1093`'s own body, the decision-log row of
    the same day and the lane briefing all state that an empty service set
    refused a plan through `plan_change_options`'s `no_services` branch.
    **It never reaches that branch.** `no_services` is a statement about a PLAN
    that prices nothing; the call refuses one step earlier, at
    `seams.unit_row(None)`, and a master account genuinely has no plan
    (`OQ-INT-12403`, CLOSED 2026-09-17 — renumbered from `OQ-INT-12398`,
    #    which is now a different question). So giving this account a service list
    does not and must not open the picker — `DEF-CUS-6310` is the wording of
    that refusal, not this.

    ⚠ **A READ, SO NOTHING IS STORED AND NOTHING IS BACKFILLED.** That is
    `BR-CUS-672`'s own second half — *"every inherited fact is held by
    reference, never copied"* — and it is the reason this is not a column: a
    service added to the building appears on the owner's account the next time
    the cell is drawn, with no migration and no second copy to drift.

    ⚠ **A UNION WITH THE AGREEMENTS, NOT A REPLACEMENT, AND THE DIFFERENCE IS A
    SERVICE THAT WOULD VANISH.** A master holds OPEN agreements on the
    premises' common areas (`BR-CUS-1010`: *"coverage still rides
    `service_agreements`"*), and nothing constrains those to be a subset of
    `services_available` — the column is a clerk's answer about the address,
    the agreements are what the account actually took. Replacing one with the
    other would DELETE a real service from an owner's cell wherever the two
    disagree; measured on the demo utility, `AC-2026-00051` draws
    `electric · water` from two common-area agreements and its premises records
    the same pair, so a union changes that account by nothing and cannot
    subtract from any other.

    ⚠ **`None` AND `[]` COLLAPSE HERE, DELIBERATELY, AND ONLY HERE.** `DEF-762`
    keeps *nobody was asked* apart from *this address offers nothing* all the
    way through metering's serialiser and this module's seam — and a CHIP ROW
    cannot say *unasked*, it can only be empty. B14 rule 33 puts rationale at
    zero words on screen, so the register says the FACT (*no services at this
    address*) and never the reason. The distinction is intact one call up for
    any screen that later needs it.

    ⚠ **EMPTY FOR EVERY ORDINARY ACCOUNT.** It is not *no services*; the
    question is simply not asked of an account that names a unit, which is what
    `BR-CUS-672` already answers for it.
    """
    if account.kind != services_master_kind():
        return set()
    premises_id = getattr(account, "premises_id", None)
    if premises_id in (None, ""):
        return set()
    return {str(code) for code in (premises_services.get(str(premises_id)) or ())}


def premise_cells_for(accounts: Any) -> dict[str, tuple[str | None, str | None]]:
    """The plural of `_premise_cell` — **two queries for a whole page.**

    ⛔ **DEF-2723's `units` statement per row.** One read for every unit the page
    names, one for every premises an account without a unit hangs off
    (`BR-CUS-1010` — the owner's account has no unit and still has an address to
    show), and nothing per row. Batching only the unit path would have left the
    premises one and quietly kept the defect for the customers who have the most
    of them.
    """
    accounts = list(accounts or [])
    if not accounts:
        return {}
    units = seams.unit_refs([a.unit_id for a in accounts if a.unit_id])
    premises = seams.premises_refs(
        [a.premises_id for a in accounts if not a.unit_id and a.premises_id]
    )
    cells: dict[str, tuple[str | None, str | None]] = {}
    for account in accounts:
        if account.unit_id:
            unit = units.get(str(account.unit_id))
            if unit is None:  # the same answer `_premise_cell` gives a 404
                cells[str(account.id)] = (None, None)
                continue
            address, label = unit.get("premise_address"), unit.get("label")
            cells[str(account.id)] = (
                label,
                f"{address} · {label}" if address and label else (address or label),
            )
            continue
        ref = premises.get(str(account.premises_id)) if account.premises_id else None
        cells[str(account.id)] = (None, ref.get("address_line") if ref else None)
    return cells


def contact_dict(row: models.Contact) -> dict[str, Any]:
    """BR-CUS-045: every column here is PII. `gov_id_last4` is the last four
    ONLY (never the full number) and DOB is a date the caller already supplied;
    display MASKING is the client's half of the rule (A12/US-CUS-009)."""
    return {
        "id": str(row.id),
        "full_name": row.full_name,
        "email": row.email,
        "phone": row.phone,
        "dob": row.dob.isoformat() if row.dob else None,
        "gov_id_last4": row.gov_id_last4,
        "is_primary": row.is_primary,
        # ⊕ DEF-CUS-10253 — *Contact by*, which the account page's contact
        # dialog edits (image 08); written since CR-171 P1.11, never served.
        "contact_by": row.contact_by,
        # `DEF-CUS-9168` — the utility's own contact fields, as recorded. The
        # DEFINITIONS come from tenancy's registry; a key with nothing recorded
        # is simply absent (US-SHL-016 TC-4).
        "custom_data": dict(row.custom_data or {}),
    }


def address_dict(row: models.Address) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "line1": row.line1,
        # `DEF-CUS-6460` — "Apt, suite or unit". The account door has stored it
        # since `3b0a8ee12` and `mailing_address_for_account` reads it for the
        # bill, but the account detail never served it, so the account page
        # printed the address without it.
        "line2": row.line2,
        "city": row.city,
        "state": row.state,
        "postal_code": row.postal_code,
        # `DEF-CUS-9169` — the utility's own mailing-address fields, as recorded.
        "custom_data": dict(row.custom_data or {}),
    }


def agreement_dict(
    row: models.ServiceAgreement, service_by_point: dict[str, str]
) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "service_point_id": str(row.service_point_id),
        "service": service_by_point.get(str(row.service_point_id)),
        "started_on": row.started_on.isoformat() if row.started_on else None,
        "ended_on": row.ended_on.isoformat() if row.ended_on else None,
        # `DEF-CUS-9170` — the utility's own service-agreement fields, as
        # recorded. Never priced (BR-TEN-048); shown on Account detail only.
        "custom_data": dict(row.custom_data or {}),
    }


@batch_reads.memoised(copy=True)
def service_agreements_for(account: models.Account) -> list[models.ServiceAgreement]:
    return list(
        models.ServiceAgreement.objects.filter(
            tenant_id=account.tenant_id, account=account
        ).order_by("started_on", "id")
    )


def billed_service_codes_for(
    account: models.Account,
    *,
    period_start: date,
    period_end: date,
) -> tuple[str, ...] | None:
    """**WHICH SERVICES THIS ACCOUNT HELD DURING THIS BILLING PERIOD** —
    `BR-CUS-1101`'s half of `BR-BIL-1048`.

    🔒 money path. HUMAN-REVIEW-PENDING — row in
    `12-governance/09-human-review-ledger.md`.

    **PO ruling 2026-09-25 (`BR-CUS-1101`), their own scenario:** a premises
    offers six services, the unit has six service points, five of them carry a
    meter or an asset, **and the account takes only three**. That rule made the
    account HOLD three; this read is how a bill finds out, and it is published
    here because the agreements are customers' rows and billing may not query
    them (B1, no cross-module ORM).

    ── DATED, AND THAT IS NOT A DETAIL ──────────────────────────────────────
    `service_codes_for` above answers *what does this account hold NOW* — an
    agreement with `ended_on` set is simply gone from it. **A bill is not asked
    now.** `_end_service_agreements` stamps the move-out date on every open
    agreement (`BR-CUS-030`), and the FINAL bill for that account is prepared
    AFTERWARDS, over a period the account plainly did hold its services in. So
    a read that asked *is it open today* would narrow every final bill to
    nothing and refuse it on `GATHER_NO_TARIFF`. An agreement counts here when
    it **overlaps the period**: it started on or before the last day, and it
    either never ended or ended on or after the first.

    ── THREE-VALUED, LIKE EVERY OTHER ABSENCE ON THE GATHER PATH ────────────
    **`None` means NOBODY CAN TELL, and billing must then narrow nothing.**
    It is answered when the account holds **no overlapping agreement at all**,
    which is not the same fact as *the clerk unticked everything*:

      * `BR-CUS-1101` refuses an EMPTY list at the move-in door for exactly
        that reason — *take nothing* is not a move-in — so no supported path
        produces an account that holds zero services on purpose;
      * accounts imported before agreements were written, and any row whose
        dates are incomplete, land here too.

    **Narrowing an account to nothing would zero a real customer's bill on an
    absence**, which is the mirror of the defect this read exists to fix
    (`DEF-BIL-6823`) and a far more expensive one. So this read can only ever
    SUBTRACT from a non-empty set, never empty one.

    ⚠ **A MASTER ACCOUNT'S OTHER COMMON AREAS ARE INCLUDED AND MUST BE**
    (`BR-CUS-068`): a master holds agreements on points of units it covers and
    not only on its anchor's, and `_service_by_point_for` already resolves
    those one seam call at a time. A read that looked only at the anchor's
    points would answer `None` for every service the master holds elsewhere
    and, worse, could subtract a covered area's service from its own bill.

    ⚠ **THIS IS DELIBERATELY NOT `service_codes_for`.** That read UNIONS the
    building's `services_available` for a master (`BR-CUS-1093`) so the S17
    Services cell shows an owner's whole coverage. An availability list is what
    the building COULD sell, not what this account BOUGHT, and billing from it
    would re-introduce the defect one indirection out.

    The codes come back de-duplicated and sorted so two runs read the same way
    twice (IS-2); a sub-metered unit's two water points are one *water*.
    """
    service_by_point = _service_by_point_for(account)
    codes: set[str] = set()
    held = False
    for agreement in service_agreements_for(account):
        started = agreement.started_on
        ended = agreement.ended_on
        if started is not None and started > period_end:
            continue
        if ended is not None and ended < period_start:
            continue
        held = True
        code = service_by_point.get(str(agreement.service_point_id))
        if code:
            codes.add(code)
    if not held or not codes:
        return None
    return tuple(sorted(codes))


def _service_by_point_for(account: models.Account) -> dict[str, str]:
    """{service_point_id: service_code} for every point this account's
    agreements can name. The anchor unit's points come in one seam call; a
    MASTER account (BR-CUS-068) also holds agreements on its OTHER covered
    common-area units' points, so any point the anchor read did not cover is
    resolved individually through `service_point_ref` — without this, every
    non-anchor agreement on a master account served `service: null` and the
    S17 Services cell undercounted the owner's coverage."""
    service_by_point = {
        str(point["id"]): point["service"] for point in seams.service_points_for(account.unit_id)
    }
    for agreement in service_agreements_for(account):
        point_id = str(agreement.service_point_id)
        if point_id not in service_by_point:
            ref = seams.service_point_ref(point_id)
            if ref is not None:
                service_by_point[point_id] = ref.get("service")
    return service_by_point


def service_codes_for(account: models.Account) -> list[str]:
    """US-CUS-001 §5 "Services": one tag per ACTIVE service agreement
    (BR-CUS-015). The service code lives on metering's service point, so it is
    read through that module's selector (B1).

    Ordered by the PLATFORM CATALOG's sort, not by whichever agreement row was
    written first — the prototype's chip row is "E · W · S" and a list cell
    whose order changes between requests is a defect, not a detail (IS-2's
    stable-order law applied to a cell).

    ⚠ **AND A MASTER ACCOUNT'S BUILDING, SINCE `BR-CUS-1093` (PO 2026-09-23).**
    It names no unit, so the walk above reaches nothing for it; the building's
    own `services_available` is unioned in, held by reference and never copied.
    `_premises_service_codes` carries the whole reasoning, including why this
    is a union rather than a substitution. **This and
    `service_codes_for_accounts` must always agree** — they are one answer with
    two query plans, and `test_br_cus_1093_master_services.py` asserts the two
    against each other on the same account for exactly that reason."""
    return service_codes_and_drops_for(account)[0]


def service_codes_and_drops_for(account: models.Account) -> tuple[list[str], int]:
    """`(codes, skipped)` — the singular of
    `service_codes_and_drops_for_accounts`, counting its skips for the same
    reason and reporting them down the same path (`DEF-CUS-6917`).

    ⚠ **IT HAS TO COUNT THEM TOO, OR THE FIX HAS A HOLE THE SHAPE OF ONE ROW.**
    `account_row` falls back to this whenever it is called without a page-wide
    map — the account DETAIL header, `runbooks`, and every test that builds one
    row — so leaving the count in the plural alone would have made the drop
    visible on the list and invisible on the screen a clerk opens to
    investigate it."""
    service_by_point = _service_by_point_for(account)
    codes: set[str] = set()
    skipped = 0
    for agreement in service_agreements_for(account):
        if agreement.ended_on is not None:
            continue
        code = service_by_point.get(str(agreement.service_point_id))
        if code:
            codes.add(code)
        else:
            skipped += 1
    codes.update(_premises_service_codes(account, _premises_services_for_masters([account])))
    catalog = seams.service_catalog_order()
    _report_service_chip_drops({str(account.id): skipped})
    return (
        sorted(
            codes, key=lambda code: (catalog.index(code) if code in catalog else len(catalog), code)
        ),
        skipped,
    )


# ── the DEF-127 balance: the LEDGER's figure, never the cache ───────────────
def _ar_positions_for(account_ids: Any = None) -> seams.ArPositions:
    """The ledger's per-account AR position, asked ONCE per response.

    Wrapped rather than called inline so every read in this module goes through
    one place and none of them can drift back to `account.balance` — the same
    discipline `apps/ledger/reporting._designated_account_id` uses to keep one
    derivation of "account 1200".
    """
    return seams.ar_positions(account_ids)


def _balance_positions_for(account_ids: Any = None) -> seams.ArPositions:
    """THE BALANCE CELL'S figure: the account's NET position in the books.

    ⚠ **`DEF-PAY-10707` (tester L2-01, 2026-10-30).** Farid Delacroix paid
    **$170.00 on a $165.00 bill**: $165.00 relieved `1200 AR` and **$5.00 was
    credited to `2400 Customer credit`** (BR-PAY-012). The cell read the 1200
    slice alone, so it said **$0.00** and nothing on the account told a clerk
    there was $5.00 to refund or apply. It now reads 1200 + 2400 for the
    account — **−$5.00**, negative meaning in credit (BR-PAY-041: the sign is
    never floored; a bounced cheque's −57.13 credit reads as +57.13 owed).

    Still the LEDGER's figure (DEF-127), just the account's whole position
    rather than the receivable's. Only the three balance-cell reads ask it: the
    S17 row, the S21 header and the unit's account cell, so they still agree
    with each other. `outstanding`, the statement total and the disconnect
    worklists keep `_ar_positions_for` — they are about what is RECEIVABLE.
    """
    return seams.ar_positions(account_ids, with_held_credit=True)


def _balance_cells(
    account: models.Account,
    positions: seams.ArPositions,
    *,
    last_bill_at: Any = None,
) -> dict[str, Any]:
    """WHAT THIS ACCOUNT OWES, as the S17 row and the S21 header state it.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  DEF-127 — THE NUMBER THE PRODUCT COULD NOT TELL A CUSTOMER          ║
    ╚══════════════════════════════════════════════════════════════════════╝
    Measured in a browser on 2026-08-15: account `E2E-10001` held an ISSUED,
    UNPAID bill of **108.88**, the books held `1200 AR` debit **108.880000**,
    `GET /finance/revenue-ar` answered `still_owed 108.880000` — and this row
    answered **`balance 0.000000`**, so S17 rendered *Outstanding $0.00*. The
    cause was one line: `_money(account.balance)`. `accounts.balance` is a CACHE
    (BR-CUS-015; B2's own column comment names the ledger as the source of
    truth) and **nothing in this product has ever written it**, so it read 0.00
    on every account that had ever been billed.

    **THE FIX IS NOT TO START WRITING THE CACHE.** BR-REP-002 forbids a
    side-maintained money number precisely because a second derivation agrees on
    the day it is written and disagrees the first time a bill issues without
    posting, a posting is reversed or a correction lands — and then a clerk has
    to decide which screen is lying. So this reads the LEDGER's own Σ, the same
    one `ar_control` publishes as the AR tie-out total and `revenue_and_ar`
    publishes as `still_owed`. The row, the header and the finance KPI are now
    one derivation grouped three ways and cannot disagree by construction.

    **ABSENT IS NOT ZERO, AND THE TWO ARE SPELLED DIFFERENTLY.** When the books
    cannot be asked — the ledger publishes no read, or this tenant has
    designated no AR account — `balance` is **null** and `balance_unavailable`
    carries the reason. The screen renders an awaiting cell. Nothing here
    substitutes 0.00 for "we could not tell", because that substitution IS the
    defect: it looks exactly like a settled account.

    The column is still SERVED, under `balance_cached`, and is the honest thing
    to serve it as. Nothing reads it for a money decision; it is there so that
    the day something does start writing it, the drift is visible on the same
    payload rather than discovered in a browser.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  DEF-628 — "NOTHING IS OWED" AND "NOTHING CAN BE OWED YET" ARE       ║
    ║  DIFFERENT FACTS, AND THE CELL SPELLED THEM THE SAME WAY             ║
    ╚══════════════════════════════════════════════════════════════════════╝
    DEF-127 above is about an absence spelled like a zero. This is its
    NEIGHBOUR and not the same defect: here the zero is **real** — the ledger
    was asked, it answered, and it answered nothing — but on a `Pending
    activation` account it is the wrong answer to render, because that account
    **cannot be billed yet**. B18 §5.1.5 is explicit that the shape shows a
    balance reading *awaiting* and never `$0.00`. Measured on a live seeded row:
    `balance='0.000000'`, `balance_unavailable=()`, `last_bill_at=None`,
    `ageing_segment=None` — every check in the repo green, and a fabricated-
    looking zero on the screen.

    ⛔ **AND DEF-628'S OWN PRESCRIBED FIX MUST NOT BE IMPLEMENTED AS WRITTEN.**
    Its `prevention` column (2026-08-24) reads *"the cell should key off
    `non_billable` rather than off the amount"*. **`BR-CUS-107` landed the next
    day** (2026-08-25, migration `0025`) and put a SIXTH status in that same
    behaviour class: `Disconnected`. That migration's own worked example is
    `A-11488`, **cut 2026-08-18 owing $612.75**, reading `Disconnected /
    non-billable`. Keying this cell off `non_billable` alone would render
    *awaiting* over that $612.75 — hiding the arrears on precisely the account
    the disconnect ladder exists to chase, which is a WORSE defect than the one
    being fixed and is DEF-127 all over again pointed at real money. The
    prevention was correct when it was written and was overtaken by a ruling
    twenty-four hours later; r11 step 0 is what catches that.

    **SO THE RULE IS FOUR CLAUSES AND A FIGURE IS NEVER HIDDEN (`BR-CUS-510`).**
    The cell may say *awaiting* only when ALL of:

      1. the ledger **ANSWERED** (`positions.available`) — when it could not,
         `balance_unavailable` already governs and says something different;
      2. the derived amount is **exactly zero** — any figure at all is rendered,
         which is the clause that saves `A-11488`;
      3. the status behaviour class is **`non_billable`** (BR-CUS-055 is
         tenant-extensible, so the CLASS is read and never a status code);
      4. **no bill has ever been issued** (`last_bill_at is None`) — a cut
         account that has been billed has a history, and a screen that called
         its settled zero *awaiting* would be inventing a future for a
         relationship that is over.

    ⚠ **THE FIGURE IS STILL SERVED AND IS STILL THE LEDGER'S.** `balance` keeps
    its `0.000000`; nothing is nulled. Nulling it would claim the books could
    not be asked — a false statement about derivability, and it would drop the
    row out of the `balance_gt` filter's "kept because unreadable" branch on a
    different premise from the one that branch documents. What is added is a
    FACT about the account, and the cell keys off the fact.
    """
    amount = positions.amount_for(account.id)
    # Clause 2 is deliberately `amount == 0` and not `not amount`: `None` is
    # clause 1's business, and a Decimal("0.000000") must compare equal to zero
    # without being spelled as falsy alongside it.
    not_yet_billable = bool(
        positions.available
        and amount is not None
        and amount == 0
        and account.status.behavior_class == "non_billable"
        and last_bill_at is None
    )
    return {
        # The figure. NUMERIC(18,6) as text, never a float (CLAUDE.md rule 2).
        "balance": _money(amount),
        # DEF-099 / rule 2 — the CHAR(3) the figure IS. The ledger DERIVES it
        # from the entries it summed; `account.currency` is the account's own
        # declared code and is what a screen falls back to when nothing posted.
        "balance_currency": positions.currency or account.currency,
        # BR-REP-001 — every money figure labels its basis, as DATA and not as a
        # caption a screen may forget to render.
        "balance_basis": positions.basis,
        "balance_source": "ledger" if positions.available else None,
        "balance_unavailable": positions.unavailable,
        # BR-CUS-510 / DEF-628 — NOT an absence, and it is served beside the
        # figure rather than instead of it. `true` means "this zero is real and
        # it is not an answer about money owed"; the cell renders *awaiting*.
        # `false` on every account that has ever been billable, on every
        # non-zero figure, and on every row where the books could not be asked.
        "balance_not_yet_billable": not_yet_billable,
        # BR-CUS-015's column, served as what it is. NOT the balance.
        "balance_cached": _money(account.balance),
    }


# ── the AGEING segment: DERIVED, never stored (CR-030 W2 · 2.3 back / 2.4) ──
#
# BR-CUS-016, VERBATIM (04-docs/05-modules/03-customers/02-business-rules.md):
#
#   "Stored status from the account-status lookup (B2 r5 #20); aging display
#    states (Current/30d/60+) DERIVED from open-invoice due-date math (and
#    opening-bucket age post-import, BR-CUS-048), never stored; extended
#    vocabulary now CONFIRMED per BR-CUS-055"
#
# BR-CUS-048 (forward aging), VERBATIM (EP-CUS-07 §US-CUS-021):
#
#   "Buckets age forward by CALENDAR DAYS from the cutover as-of date (an
#    amount imported 45 days past due is 75 days past due 30 days later); the
#    aging display derives — never re-stored (BR-CUS-016 pattern)."
#
# CR-030 §5.1.2 is what makes this a COLUMN: today's `STATUS` cell "mixes two
# things" — it draws `Pending` beside `30d past` — and the prototype splits it
# into `STATUS` (the stored lookup) and `AGEING` (this). Two cells, never one
# (TC-ACC-2), and the segment filter is TC-ACC-5.
#
# ⚠ WHAT THIS READS — AMENDED 2026-10-17 (`DEF-CUS-10181`, PO ruling *"ACCOUNT
# AGE ON THE ACCOUNTS LIST; AGING STAYS MONEY AND IS FIXED TO READ BILLS"*).
# This block used to say billing's open-invoice due dates *"are not published
# by anything"*, so an account whose debt was a BILL aged to null. That was
# true on 2026-08-24 and stopped being true when Who owes you began reading the
# oldest unpaid due date in SQL (`CR-138-BRC07` `P4.1`) — and the comment
# outlived it for seven weeks (hard-won law 1). Both halves of BR-CUS-016 are
# read now: the OLDEST UNPAID BILL's due date, from payments' own debtor
# statement (`seams.debtor_positions_queryset`), and the migrated opening
# buckets; the older of the two wins. See `ageing_anchor_expressions`.

#: BR-CUS-048's four bands with the INCLUSIVE upper edge, in days past due, of
#: each. The band NAMES come from the model (`AccountOpeningBucket.BUCKETS`) and
#: are never restated here; the day EDGES are declared once, here, and every
#: other figure below (floors, band lookup, ordering) is derived from this
#: tuple. The edges are the ones this product already ages by —
#: `apps/payments/outstandings.bucket_for` cuts at the same 30 / 60 / 90, with
#: its extra A2 §S34 `1-30` band folded into BR-CUS-048's wider `Current`.
#: They are read literally: `61–90` CONTAINS 90 and `90+` means MORE than 90.
AGEING_BAND_EDGES: tuple[tuple[str, int | None], ...] = (
    (models.AccountOpeningBucket.BUCKET_CURRENT, 30),
    (models.AccountOpeningBucket.BUCKET_31_60, 60),
    (models.AccountOpeningBucket.BUCKET_61_90, 90),
    (models.AccountOpeningBucket.BUCKET_90_PLUS, None),  # open-ended
)

#: The segment vocabulary, in ageing order — the model's own tuple, so a fifth
#: band could never appear on the wire without appearing in the schema first.
AGEING_SEGMENTS: tuple[str, ...] = models.AccountOpeningBucket.BUCKETS

#: Each band's FLOOR in days, derived from the edges above (0, 31, 61, 91).
AGEING_BAND_FLOORS: dict[str, int] = {
    bucket: (0 if index == 0 else (AGEING_BAND_EDGES[index - 1][1] or 0) + 1)
    for index, (bucket, _edge) in enumerate(AGEING_BAND_EDGES)
}

#: Wire spellings a client may send for a segment. The canonical values are the
#: model's; the aliases are the labels the screen draws (`31-60`, `90+`) and the
#: ones `apps/payments/outstandings` already accepts on its own `bucket` param,
#: so one segment string works against both endpoints.
AGEING_SEGMENT_ALIASES: dict[str, str] = {
    "31-60": models.AccountOpeningBucket.BUCKET_31_60,
    "31_60": models.AccountOpeningBucket.BUCKET_31_60,
    "61-90": models.AccountOpeningBucket.BUCKET_61_90,
    "61_90": models.AccountOpeningBucket.BUCKET_61_90,
    "90+": models.AccountOpeningBucket.BUCKET_90_PLUS,
    "90_plus": models.AccountOpeningBucket.BUCKET_90_PLUS,
    "90plus": models.AccountOpeningBucket.BUCKET_90_PLUS,
}

#: ⛔ AMENDED 2026-08-24 (DEF-620). This read `OQ_OPENING_CREDIT = "OQ-065"` and
#: described the importer as REFUSING a negative bucket by that id. **OQ-065
#: closed on 2026-08-08** → BR-CUS-061: an opening credit imports as a carried
#: ACCOUNT CREDIT and the aging buckets stay debit-only. So the importer no
#: longer refuses — it SPLITS the row (BR-CUS-077) — and no negative bucket row
#: is ever written.
#:
#: ⚠ THE GUARD BELOW STAYS ANYWAY, AND IS NOW AN INVARIANT CHECK RATHER THAN AN
#: OPEN QUESTION. A negative `account_opening_buckets` row is a state BR-CUS-061
#: says cannot exist; if one is ever found, something wrote it outside the one
#: writer and the honest answer is to stop, not to age it into a band. Citing a
#: CLOSED question there would tell the next reader to go and wait for a ruling
#: that already happened — which is the exact shape of DEF-620 itself.
OPENING_CREDIT_RULE = "BR-CUS-061"

#: Served beside a null segment ONLY when the bill half could not be asked —
#: payments publishes no debtor read in this deployment. Since `DEF-CUS-10181`
#: a null segment is otherwise an ANSWER (the account owes nothing that ages,
#: or holds a credit), and an answer needs no reason attached.
AGEING_BILL_HALF_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "debtor_read_not_published",
        "br_ref": "BR-CUS-016",
        "detail": "Ageing reads the oldest unpaid bill's due date from Who owes you's own "
        "debtor statement (apps.payments.billing_seam.debtor_positions_queryset). It is not "
        "published here, so only migrated opening balances can be aged.",
        "wanted_reads": ("apps.payments.billing_seam.debtor_positions_queryset() -> QuerySet",),
    },
)


def ageing_band_for_days(days_past_due: int) -> str:
    """The BR-CUS-048 band one age falls in. 30 and 31 land on opposite sides.

    Nothing here is a money figure and nothing rounds: it is calendar-day
    arithmetic over a band table declared in exactly one place.
    """
    for bucket, edge in AGEING_BAND_EDGES:
        if edge is None or days_past_due <= edge:
            return bucket
    return AGEING_BAND_EDGES[-1][0]  # pragma: no cover — the last edge is open


def _bucket_days_past_due(row: models.AccountOpeningBucket, as_of: date) -> int | None:
    """One opening bucket's age TODAY — BR-CUS-048's forward aging.

    ⚠ **THE ONE JUDGMENT IN THIS DERIVATION, WRITTEN DOWN RATHER THAN LEFT TO
    BE DISCOVERED** (the posture `AccountOpeningBucket`'s own docstring takes
    for its two). BR-CUS-048's worked sentence ages an amount that is "45 days
    past due" — a POINT. A bucket is a BAND, so the point inside it is not
    recorded, and the rule is silent on which point to age forward. Three
    readings exist (the band's floor, its ceiling, its midpoint) and all three
    reproduce the imported band exactly on cutover day, so no signed figure
    distinguishes them.

    **This reads the FLOOR** — the least age the stored data supports. It is the
    only one of the three that can never tell collections an account is worse
    than the import proves: a `31–60` bucket becomes `61–90` after 30 more days
    under the floor reading and after 1 more day under the ceiling reading, and
    the second would put a customer into a harsher band on evidence nobody has.
    Under-stating is recoverable by a clerk reading the ledger; over-stating
    sends a notice. **REPORTED for the decision log and the review ledger — it
    is an engineering judgment inside a PROPOSED derivation clause, not a rule
    this lane may confirm.**

    `as_of` is an ARGUMENT and never a clock (BR-TEN-043): the ageing a clerk
    sees at 23:58 and the ageing a job takes at 00:02 must be explainable.

    Elapsed days CLAMP AT ZERO. A cutover dated in the future is the import's
    own dating, and letting it run negative would un-age an imported `90+`
    into `Current` — money getting younger is never the answer to a date typo.
    """
    floor = AGEING_BAND_FLOORS.get(row.bucket)
    if floor is None:
        # A bucket code outside BR-CUS-048's closed vocabulary. One writer
        # (`import_writer`) produces these rows from the model's own constants,
        # so this cannot happen today; if it ever does, the row is NOT aged
        # into a band that was guessed for it.
        return None
    elapsed = max((as_of - row.as_of).days, 0)
    return floor + elapsed


def _opening_anchor_case(as_of: date) -> Any:
    """Each opening bucket's ANCHOR DATE, as a SQL `CASE` — or None if the tenant
    holds no positive bucket.

    The anchor is the day an amount WOULD have fallen due for
    `_bucket_days_past_due` to answer what it answers: `days = as_of − anchor`,
    so `anchor = min(cutover, as_of) − floor(band)`. The floor reading and the
    clamp at zero are that function's two judgments, carried and not re-made.

    ⚠ **ONE `WHEN` PER DISTINCT `(bucket, cutover)` PAIR, COMPUTED IN PYTHON,
    SO THE SQL HOLDS NO DATE ARITHMETIC.** A cutover file carries one as-of date
    for the whole batch (US-CUS-021 §5), so a tenant has four pairs per import
    run — the count follows the number of imports, never the number of
    accounts. Date-minus-interval reads differently on PostgreSQL and on the
    SQLite the suite runs on (hard-won law 14); a constant does not. `NFR-5`:
    no ceiling on the pairs — a tenant with many cutovers builds a longer
    `CASE`, never a wrong one.
    """
    from django.db.models import Case, DateField, Value, When

    pairs = (
        models.AccountOpeningBucket.objects.filter(tenant_id=_tenant_id(), amount__gt=0)
        .order_by()
        .values_list("bucket", "as_of")
        .distinct()
    )
    whens = []
    for bucket, cutover in pairs:
        floor = AGEING_BAND_FLOORS.get(bucket)
        if floor is None or cutover is None:
            continue  # outside BR-CUS-048's vocabulary — never aged into a guess
        anchor = min(cutover, as_of) - timedelta(days=floor)
        whens.append(When(bucket=bucket, as_of=cutover, then=Value(anchor)))
    if not whens:
        return None
    return Case(*whens, default=Value(None), output_field=DateField())


def ageing_anchor_expressions(as_of: date) -> dict[str, Any] | None:
    """THE AGEING ANCHOR of an account, as SQL over `accounts` — `DEF-CUS-10181`.

    Returns three annotations keyed for `Account` querysets, or None when
    payments publishes no debtor read (the caller then ages opening buckets
    only and says so). `ageing_anchor` is the date the account's OLDEST unpaid
    money fell due; `as_of − ageing_anchor` is its days past due and
    `ageing_band_for_days` names the band. **NULL means the account owes
    nothing that ages** — a zero or credit balance — and is the screen's `—`.

    PO 2026-10-17, verbatim from the ruling shown: *"the band (Current · 31–60 ·
    61–90 · 90+) comes from the oldest unpaid bill's due date — the same figure
    Who owes you uses — plus any migrated opening balance; filter and sort work
    for bill-only accounts."* Worked: a bill due 08/01/2026 unpaid on
    10/17/2026 = 77 days → **61–90**.

    **The two halves, and how they combine:**

      * **BILLS** — `seams.debtor_positions_queryset()`, which is
        `apps/payments/billing_seam._debtor_positions`: the SAME statement
        Who owes you pages, so an account is aged by a bill exactly when that
        screen lists it, on exactly its `oldest_due_on`. Not a second
        implementation of open balances, allocations or credit. A debtor whose
        open bills carry no due date anchors on `as_of` — CURRENT, which is
        `outstandings.bucket_for(None)`.
      * **OPENING BUCKETS** — the migrated receivable (BR-CUS-048), each
        positive bucket anchored by `_opening_anchor_case`; the account's
        oldest wins, as `ageing_segments_for` always took it.
      * **THE OLDER OF THE TWO WINS — WHILE THE OPENING MONEY IS STILL OWED.**
        ⚠ **A JUDGMENT, WRITTEN DOWN (decision log 2026-10-17).** Opening
        buckets are append-only and never shrink when paid; OQ-530 carries the
        opening balance onto the account's FIRST bill as its previous balance.
        So the buckets age the account only while (a) it has never been billed
        — the opening amount IS the receivable — or (b) its first bill is still
        among the unpaid ones (its oldest unpaid due date is the first bill's).
        Once that bill is paid the opening money was paid with it, and ageing
        it for ever would put a settled migration into collections.
        ⚠ **RESIDUE, STATED:** an opening-only account whose customer paid
        before any bill holds an unallocated credit this read does not
        subtract; it ages as it did before this change.

    Three correlated subqueries per account. They run over ONE PAGE for the
    cells and over the filtered set only when a clerk filters or sorts by
    ageing (`NFR-3`: in SQL, never a Python loop over the tenant).
    """
    from django.db.models import Case, DateField, Exists, F, OuterRef, Q, Subquery, Value, When
    from django.db.models.functions import Coalesce, Least

    debtors = seams.debtor_positions_queryset()
    if debtors is None:
        return None
    bills = seams.live_bills_queryset()
    far = date(9999, 12, 31)  # an undated FIRST bill sorts after every dated one

    bill_anchor = Subquery(
        debtors.filter(account_id=OuterRef("pk"))
        .annotate(_anchor=Coalesce("oldest_due_on", Value(as_of), output_field=DateField()))
        .values("_anchor")[:1],
        output_field=DateField(),
    )
    case = _opening_anchor_case(as_of)
    if case is None:
        return {
            "ageing_bill_anchor": bill_anchor,
            "ageing_open_anchor": Value(None, output_field=DateField()),
            "ageing_anchor": F("ageing_bill_anchor"),
        }
    open_anchor = Subquery(
        models.AccountOpeningBucket.objects.filter(
            tenant_id=_tenant_id(), account_id=OuterRef("pk"), amount__gt=0
        )
        .annotate(_anchor=case)
        .filter(_anchor__isnull=False)
        .order_by("_anchor")
        .values("_anchor")[:1],
        output_field=DateField(),
    )
    first_bill = Subquery(
        bills.filter(account_id=OuterRef("pk"))
        .annotate(_first=Coalesce("due_date", Value(far), output_field=DateField()))
        .order_by("_first")
        .values("_first")[:1],
        output_field=DateField(),
    )
    never_billed = ~Exists(bills.filter(account_id=OuterRef("pk")))
    opening_owed = Q(ageing_open_anchor__isnull=False) & (
        never_billed
        | Q(ageing_bill_anchor__isnull=False, ageing_bill_anchor__lte=first_bill)
    )
    anchor = Case(
        When(
            opening_owed,
            then=Least(
                Coalesce("ageing_bill_anchor", "ageing_open_anchor"),
                Coalesce("ageing_open_anchor", "ageing_bill_anchor"),
                output_field=DateField(),
            ),
        ),
        default="ageing_bill_anchor",
        output_field=DateField(),
    )
    return {
        "ageing_bill_anchor": bill_anchor,
        "ageing_open_anchor": open_anchor,
        "ageing_anchor": anchor,
    }


def annotate_ageing(qs: QuerySet, as_of: date) -> QuerySet:
    """`ageing_anchor` (and its two halves) on an `Account` queryset. Falls back
    to the opening half alone when the debtor read is not published."""
    exprs = ageing_anchor_expressions(as_of)
    if exprs is None:
        exprs = _opening_only_expressions(as_of)
    # Order matters: `ageing_anchor` refers to the two halves by name.
    return qs.annotate(
        ageing_bill_anchor=exprs["ageing_bill_anchor"],
        ageing_open_anchor=exprs["ageing_open_anchor"],
    ).annotate(ageing_anchor=exprs["ageing_anchor"])


def _opening_only_expressions(as_of: date) -> dict[str, Any]:
    from django.db.models import DateField, F, OuterRef, Subquery, Value

    none = Value(None, output_field=DateField())
    case = _opening_anchor_case(as_of)
    if case is None:
        return {"ageing_bill_anchor": none, "ageing_open_anchor": none, "ageing_anchor": none}
    open_anchor = Subquery(
        models.AccountOpeningBucket.objects.filter(
            tenant_id=_tenant_id(), account_id=OuterRef("pk"), amount__gt=0
        )
        .annotate(_anchor=case)
        .filter(_anchor__isnull=False)
        .order_by("_anchor")
        .values("_anchor")[:1],
        output_field=DateField(),
    )
    return {
        "ageing_bill_anchor": none,
        "ageing_open_anchor": open_anchor,
        "ageing_anchor": F("ageing_open_anchor"),
    }


def ageing_band_q(segment: str, as_of: date) -> Q:
    """`f.ageing=<segment>` as a WHERE over `ageing_anchor` — the SQL twin of
    `ageing_band_for_days`, built from the SAME `AGEING_BAND_EDGES`.
    `days ≤ edge` ⇔ `anchor ≥ as_of − edge`, so no day arithmetic runs in SQL.
    `test_def_cus_10181_*` asserts the two agree on every boundary day."""
    lower: date | None = None  # anchor must be >= lower (days <= upper edge)
    upper: date | None = None  # anchor must be <  upper (days >  previous edge)
    previous_edge: int | None = None
    for bucket, edge in AGEING_BAND_EDGES:
        if bucket == segment:
            if edge is not None:
                lower = as_of - timedelta(days=edge)
            if previous_edge is not None:
                upper = as_of - timedelta(days=previous_edge)
            break
        previous_edge = edge
    else:  # pragma: no cover — normalize_ageing_segment admits only the four
        return Q(pk__in=[])
    q = Q(ageing_anchor__isnull=False)
    if lower is not None:
        q &= Q(ageing_anchor__gte=lower)
    if upper is not None:
        q &= Q(ageing_anchor__lt=upper)
    return q


def _guard_no_negative_bucket(account_ids: list[Any]) -> None:
    """⛔ BR-CUS-061 makes the buckets debit-only and `import_writer` is the one
    writer; a negative row means something bypassed it. The SQL above ages only
    positive rows, so without this the row would be silently ignored — this
    stops instead, as the Python read always did. Defence in depth on a money
    path is cheap; a wrong band on a real customer is a letter in the post."""
    bad = (
        models.AccountOpeningBucket.objects.filter(
            tenant_id=_tenant_id(), account_id__in=list(account_ids), amount__lt=0
        )
        .values("account_id", "bucket", "amount")
        .first()
    )
    if bad is not None:
        raise NotImplementedError(
            f"{OPENING_CREDIT_RULE}: a negative opening bucket cannot exist — "
            f"account={bad['account_id']} bucket={bad['bucket']} amount={bad['amount']}"
        )


def ageing_segments_for(
    account_ids: list[Any], *, as_of: date | None = None
) -> dict[str, tuple[str | None, int | None]]:
    """The AGEING cell for a whole page — ONE statement, never one per row.

    Returns `{account_id: (segment, days_past_due)}` for the accounts that owe
    money that ages; an account absent from the map owes nothing (or holds a
    credit) — since `DEF-CUS-10181` that is an ANSWER, not a gap. The days are
    `as_of − ageing_anchor`, clamped at zero for a balance not yet due, and the
    band is `ageing_band_for_days` of them — the same function and the same
    edges `ageing_band_q` filters on.
    """
    return {key: (seg, days) for key, (seg, days, _src) in _ageing_for(account_ids, as_of).items()}


def _ageing_for(
    account_ids: list[Any], as_of: date | None = None
) -> dict[str, tuple[str, int, str]]:
    if not account_ids:
        return {}
    if as_of is None:
        as_of = seams.tenant_today()
    _guard_no_negative_bucket(account_ids)
    rows = annotate_ageing(
        models.Account.objects.filter(tenant_id=_tenant_id(), id__in=list(account_ids)), as_of
    ).values("id", "ageing_anchor", "ageing_open_anchor")
    out: dict[str, tuple[str, int, str]] = {}
    for row in rows:
        anchor = _as_date(row["ageing_anchor"])
        if anchor is None:
            continue
        days = max((as_of - anchor).days, 0)
        source = (
            "opening_buckets"
            if _as_date(row["ageing_open_anchor"]) == anchor
            else "bills"
        )
        out[str(row["id"])] = (ageing_band_for_days(days), days, source)
    return out


def _as_date(value: Any) -> date | None:
    """A DateField annotation as a `date` — SQLite hands a computed `CASE` back
    as text and PostgreSQL as a date; one comparison must see one type."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def ageing_cells(
    account_id: Any, segments: dict[str, tuple[str, int, str]] | None = None
) -> dict[str, Any]:
    """The four AGEING keys of one S17 row (CR-030 §5.1.2's column).

    `ageing_segment` is one of `AGEING_SEGMENTS` or **null** — the screen's `—`,
    meaning nothing owed ages. `segments` is `_ageing_for`'s page map.
    """
    if segments is None:
        segments = _ageing_for([account_id])
    found = segments.get(str(account_id))
    segment, days, source = found if found is not None else (None, None, None)
    unwired = segment is None and (
        seams.resolve("payments", "debtor_positions_queryset", kind="billing_seam") is None
    )
    return {
        "ageing_segment": segment,
        "ageing_days_past_due": days,
        # WHERE the claim comes from, as DATA — `opening_buckets` or `bills`, so
        # a screen can say "migrated opening balance" rather than imply a bill.
        "ageing_source": source,
        # A reason ONLY when the bill half could not be asked (hard-won law 1).
        "ageing_unavailable": (
            list(AGEING_BILL_HALF_UNAVAILABLE) if unwired else None
        ),
    }


def normalize_ageing_segment(raw: Any) -> str | None:
    """A `?ageing=` value → a canonical segment, or None for "do not filter".

    BR-SHL-011: a list URL can NEVER 4xx over its params, so an unrecognised
    segment falls back to no filter — the `f.kind` disposition, not an error.
    `all` is the CR-030 §5.1.2 default segment and means every row.
    """
    text = str(raw or "").strip().lower()
    if not text or text == "all":
        return None
    if text in AGEING_SEGMENTS:
        return text
    return AGEING_SEGMENT_ALIASES.get(text)


# ── the MIGRATED OPENING POSITION, published for billing (OQ-530, PO 2026-08-27)
def opening_position_for_account(account_id: Any) -> dict[str, Any]:
    """The account's migrated opening receivable — `account_opening_buckets`.

    PUBLISHED FOR BILLING. PO ruling 2026-08-27 closing OQ-530, verbatim:
    *"so when we run first bill; we have to take opening balance into account.
    you will generate first bill and against previous balance you will mention
    the opening balance."* Billing owns no opening bucket and must compute none
    (B1), so it asks this read BY NAME through `apps/billing/customers_seam.py`
    — the same shape it already asks payments for the allocated half of
    BR-BIL-035.

    ⚠ **THIS IS THE FOUR BUCKET ROWS AND NEVER `accounts.balance`.** That column
    is a CACHE (BR-CUS-015) which already carries the migrated opening AND
    everything else posted for the account, so a caller that summed it into a
    previous balance beside the account's own open bills would count the
    migrated money **twice**. The buckets are the migration's own append-only
    detail under `UNIQUE (account, bucket)` (US-CUS-021 §5), so the four bands
    cannot double each other either.

    ❄️ **Worked on GT-16's own account `A-12103`:** `84.20 / 62.10 / 0.00 /
    121.00` = **267.30**, `as_of` 2026-08-31. Nothing here rounds and nothing
    ages — BR-CUS-048's forward ageing is `ageing_segments_for`'s job, and a
    BILL prints an amount rather than a band.

    Returns `{"amount": Decimal, "buckets": int, "as_of": date|None,
    "currency": str|None}`. An account with no migration answers
    **`Decimal("0")` with `buckets: 0`**, and that zero is a DERIVED answer
    rather than a gap: the rows were read and there were none. The absence case
    — this module not deployed at all — is the caller's `_resolve` answering
    None, which is a different fact and is spelled differently there.
    """
    rows = list(
        models.AccountOpeningBucket.objects.filter(
            tenant_id=_tenant_id(), account_id=account_id
        ).values("amount", "as_of", "currency")
    )
    return _opening_from(rows)


def opening_positions_for_accounts(account_ids: Any) -> dict[str, dict[str, Any]]:
    """`opening_position_for_account` for a whole bill run (`DEF-BIL-8696`):
    `{account_id: answer}` for EVERY account asked about — `0` with `buckets: 0`
    where it has no rows, exactly the singular's derived zero — in ONE
    statement. `account_ids` may be a queryset of ids (read as a subquery, so
    40,000 accounts are never 40,000 bound parameters) or a list. The same
    `_opening_from` adds each account's rows up, so the two cannot disagree."""
    if hasattr(account_ids, "query"):
        keys = [str(account_id) for account_id in account_ids if account_id]
        scopes: list[Any] = [account_ids]
    else:
        keys = [str(account_id) for account_id in (account_ids or ()) if account_id]
        scopes = [keys[start : start + 900] for start in range(0, len(keys), 900)]
    rows_by: dict[str, list[dict[str, Any]]] = {key: [] for key in keys}
    for scope in scopes:
        for row in models.AccountOpeningBucket.objects.filter(
            tenant_id=_tenant_id(), account_id__in=scope
        ).values("account_id", "amount", "as_of", "currency"):
            key = str(row["account_id"])
            if key in rows_by:
                rows_by[key].append(row)
    return {key: _opening_from(rows) for key, rows in rows_by.items()}


def activity_key_for_accounts(account_ids: Any) -> str | None:
    """`DEF-BIL-8696` — a key that MOVES whenever an account row (its autopay
    flags, its type) or an opening bucket of these accounts is written. Billing's
    Sign off rebuilds its saved whole-run summary when it differs
    (`core.row_versions`). None where the database cannot say."""
    from core import row_versions

    if not row_versions.supported():
        return None
    scope = account_ids if hasattr(account_ids, "query") else [str(a) for a in account_ids]
    return row_versions.keys(
        models.Account.objects.filter(tenant_id=_tenant_id(), pk__in=scope),
        models.AccountOpeningBucket.objects.filter(tenant_id=_tenant_id(), account_id__in=scope),
    )


def _opening_from(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The four bands of ONE account added up — the arithmetic both reads above
    share."""
    total = Decimal("0")
    for row in rows:
        amount = row["amount"]
        if not isinstance(amount, Decimal):
            # Money arrives as a Decimal or not at all (CLAUDE.md rule 2). A
            # float that reached here would be a defect upstream, and coercing
            # it would hide the place where money became binary.
            raise TypeError(
                f"an opening bucket amount must be a Decimal, got {type(amount).__name__} "
                "— money is never a binary fraction and never cents (CLAUDE.md rule 2)"
            )
        total += amount
    return {
        "amount": total,
        "buckets": len(rows),
        # ONE date per batch (BR-CUS-049), so the EARLIEST is the batch's own
        # and a second migration shows as an older date rather than an average.
        "as_of": min((row["as_of"] for row in rows if row["as_of"]), default=None),
        # DEF-099 — a money figure never travels without the currency it is in.
        "currency": next((row["currency"] for row in rows if row["currency"]), None),
    }


#: `customers.addresses.kind` — B2 §2 declares the pair `mailing|service` and
#: the column defaults to `mailing`. Named here rather than spelled inline so
#: the ONE place that decides "which address does a bill get posted to" is
#: greppable; a second literal is how a fallback quietly appears.
MAILING_ADDRESS_KIND = "mailing"

#: The three parts `BR-NOT-029` clause (b) makes MANDATORY for a mailed piece.
#: A mail house cannot standardise, barcode or rate an address without all
#: three, so a bill missing any of them is REPORTED and held out of the file
#: rather than posted with the gap filled in by us.
REQUIRED_ADDRESS_PARTS = ("city", "state", "postal_code")


def mailing_address_for_account(account_id: Any) -> dict[str, Any] | None:
    """The DISCRETE mailing address a print vendor is handed — `BR-NOT-029` (a).

    PUBLISHED FOR BILLING, and it is a READ. `BR-CUS-674` (PO 2026-08-31,
    verbatim *"we cannot make chnges until account confirm it"*) says an address
    changes when the account holder tells us and by no other route, so the print
    hand-over runs ONE direction: this function selects columns and writes none.
    `G60` enforces the absence of the other direction.

    ⚠ **IT RETURNS COLUMNS, NEVER A COMPOSED STRING, AND IT NEVER SPLITS ONE.**
    `BR-NOT-029` clause (a): *"Every manifest address is written from DISCRETE
    columns, never assembled from or split out of a single field — splitting an
    address is guessing, and a guessed address is mail delivered to the wrong
    house."* `addresses.line1/city/state/postal_code` are four real columns and
    they are what travels. `service_requests.billing_address_as_given` is a
    free-text blob (`DEF-2703`) and is deliberately NOT read here: parsing it
    into parts is precisely the operation the rule forbids.

    ⚠ **`line2` AND `country` ARE REAL COLUMNS SINCE 2026-09-01 (`DEF-2847`,
    migration `customers 0039`), AND THEY ARE STILL EMPTY ON EVERY EXISTING
    ROW.** Two of the manifest's nine address fields had no column anywhere in
    the product, so the hand-over file emitted them blank on every bill while
    this function returned literal `None` for both. They are selected now.
    **Nothing was backfilled and nothing ever will be**: line 2 may not be
    carved out of line 1 (clause (a) — *"splitting an address is guessing"*),
    and `TenantSettings.country` is the UTILITY's own regional setting, so
    writing it here would assert where a CUSTOMER lives from a fact about us.
    NULL means *nobody has told us*, which is true, and clause (b) names city,
    state and postal code and neither of these — so their absence still does not
    hold a bill.

    ⚠ **NO FALLBACK TO THE SERVICE ADDRESS — AND SINCE 2026-09-24 THIS IS NO
    LONGER THE READ A PAPER BILL IS ADDRESSED FROM (`DEF-BIL-6373`).** This
    answers one question: *what MAILING row does this account hold?* A
    move-out's FORWARDING address is exactly that question (`RB-127`), and there
    the premises being left is the wrong answer, so this read still never falls
    back. **Where a bill is POSTED is a different question** and the PO has
    answered it (2026-09-23, *"ensure you update correct address - mailing or
    service"*, with B2 §2: an absent mailing row MEANS *same as service*): the
    mailing row, else the service address. `print_address_for_account` below
    answers that, through the SAME resolver the delivery queue uses, so the
    print-shop archive and the queue can no longer disagree about one bill. An
    account with no mailing address still answers HERE with `missing` naming
    `line1`.

    Returns `{"line1", "line2", "city", "state", "postal_code", "country",
    "missing": [...]}`, or **None** for an id this tenant does not hold — the
    HR-1 answer, byte-identical to *there is no such account*. `missing` is the
    subset of `REQUIRED_ADDRESS_PARTS` (plus `line1`) this address cannot
    supply, and an EMPTY list is the only thing that lets a bill into the file.
    """
    if account_id in (None, ""):
        return None
    tenant_id = _tenant_id()
    if not models.Account.objects.filter(tenant_id=tenant_id, pk=account_id).exists():
        return None
    row = (
        models.Address.objects.filter(
            tenant_id=tenant_id,
            account_id=account_id,
            kind=MAILING_ADDRESS_KIND,
            deleted_at__isnull=True,
        )
        # Oldest first, then id: a deterministic pick, so two runs of the same
        # print set address the same envelope. `created_at` alone is not enough
        # — two rows written in one statement share it.
        .order_by("created_at", "id")
        .values("line1", "line2", "city", "state", "postal_code", "country")
        .first()
    )
    if row is None:
        return {
            "line1": None,
            "line2": None,
            "city": None,
            "state": None,
            "postal_code": None,
            "country": None,
            "missing": ["line1", *REQUIRED_ADDRESS_PARTS],
        }
    missing = [
        part for part in ("line1", *REQUIRED_ADDRESS_PARTS) if not str(row.get(part) or "").strip()
    ]
    return {
        "line1": row["line1"],
        # A real column since migration 0039 (DEF-2847), and NULL on every row
        # written before it. Never carved out of line1 (clause (a)).
        "line2": row["line2"],
        "city": row["city"],
        "state": row["state"],
        "postal_code": row["postal_code"],
        # Likewise — and never the tenant's own regional setting.
        "country": row["country"],
        "missing": missing,
    }


def account_ids_without_print_address(account_ids: Any = None) -> QuerySet:
    """The accounts whose PAPER BILL cannot be posted — `print_address_for_account`
    in bulk, as a queryset of ids. `account_ids` narrows it to one page.

    ⚠ **IT REPLACED `account_ids_without_mailing_address` ON 2026-09-24
    (`DEF-BIL-6373`), WHOSE ANSWER WAS THE OLD RULE.** That read held every
    account with no complete MAILING row, so the print-shop archive held a bill
    the delivery queue was addressing to the premises. Its only reader was
    billing's print set, which now reads this.

    **The SAME two legs `_postal_recipient` walks, in the same order**, asked
    for many accounts at once rather than one:

      1. **the oldest live mailing row, when it has a street** — the row
         `_postal_snapshot` picks, judged on its own parts (a mailing row with a
         street and no postcode is HELD, not replaced by the premises: the
         customer gave that address and a mail house needs all of it);
      2. **otherwise the premises the account walks to** — asked of metering
         through `seams.envelope_addresses`, the read `_service_postal` uses.
         Metering unable to answer counts as a gap, because the archive then
         holds the bill as unreadable and a forecast must not promise it prints.

    Completeness is `line1` plus `REQUIRED_ADDRESS_PARTS` (`BR-NOT-029` (b)),
    exactly as `missing` computes it.

    ⚠ **A FEW STATEMENTS, NEVER ONE A ROW (`NFR-3`).** One for the mailing leg,
    one for the accounts that walk, and `envelope_addresses`' two at most —
    the same number for a page of 50 as for a tenant of 40,000. It cannot be
    one lazy subquery any more: the premises is metering's table, reached only
    through metering's read. The one measurable difference from the single read
    is whitespace — SQL trims spaces where `_postal_snapshot` calls
    `str.strip()`, so a street that is a lone TAB forecasts as present.
    """
    tenant_id = _tenant_id()
    accounts = models.Account.objects.filter(tenant_id=tenant_id)
    if account_ids is not None:
        accounts = accounts.filter(pk__in=list(account_ids))
    mailing = models.Address.objects.filter(
        tenant_id=tenant_id,
        account_id=OuterRef("pk"),
        kind=MAILING_ADDRESS_KIND,
        deleted_at__isnull=True,
    ).order_by("created_at", "id")
    annotated = accounts.annotate(
        **{
            f"posted_{part}": Trim(Subquery(mailing.values(part)[:1]))
            for part in ("line1", *REQUIRED_ADDRESS_PARTS)
        }
    )
    walks = Q(posted_line1__isnull=True) | Q(posted_line1="")
    # Leg 1 — the mailing row with a street IS the envelope; a hole in it holds.
    hole = Q()
    for part in REQUIRED_ADDRESS_PARTS:
        hole |= Q(**{f"posted_{part}__isnull": True}) | Q(**{f"posted_{part}": ""})
    gap = set(annotated.exclude(walks).filter(hole).values_list("id", flat=True))
    # Leg 2 — every other account walks to its premises (hard rule 8).
    walkers = list(annotated.filter(walks).values_list("id", "unit_id", "premises_id"))
    unit_ids = [unit for _, unit, _ in walkers if unit not in (None, "")]
    premises_ids = [
        premises
        for _, unit, premises in walkers
        if unit in (None, "") and premises not in (None, "")
    ]
    answered = (
        seams.envelope_addresses(unit_ids=unit_ids, premises_ids=premises_ids)
        if walkers
        else {"units": {}, "premises": {}}
    )
    for account_id, unit_id, premises_id in walkers:
        if answered is None:
            gap.add(account_id)
            continue
        if unit_id not in (None, ""):
            envelope = (answered.get("units") or {}).get(str(unit_id))
        elif premises_id not in (None, ""):
            envelope = (answered.get("premises") or {}).get(str(premises_id))
        else:
            envelope = None
        if envelope is None or _envelope_missing(envelope):
            gap.add(account_id)
    return models.Account.objects.filter(tenant_id=tenant_id, pk__in=gap).values_list(
        "id", flat=True
    )


def _envelope_missing(parts: dict[str, Any]) -> list[str]:
    """`line1` plus `BR-NOT-029` (b)'s three, whichever of them are blank."""
    return [
        part
        for part in ("line1", *REQUIRED_ADDRESS_PARTS)
        if not str(parts.get(part) or "").strip()
    ]


def print_address_for_account(account_id: Any) -> dict[str, Any] | None:
    """Where this account's PAPER BILL is posted — PUBLISHED FOR BILLING'S PRINT SET.

    ⚠ **THE SAME ANSWER THE DELIVERY QUEUE GIVES, FROM THE SAME RESOLVER
    (`DEF-BIL-6373`, decided 2026-09-23).** Until 2026-09-24 the print-shop
    archive read `mailing_address_for_account`, which never falls back, while
    `delivery_recipients_for_account` — since `DEF-PAY-6342` part 1 — addressed
    the same bill to the premises. So one bill was queued to *1408 Bluestem Ln*
    and held out of the print file as *no address*. The PO's ruling of
    2026-09-23 (*"ensure you update correct address - mailing or service"*) and
    B2 §2 (an absent mailing row MEANS *same as service*) settle which is right,
    and this is `_postal_recipient` — the queue's own function — answered in the
    discrete parts a mail house needs rather than as an envelope snapshot.

    **Parts, never a composed string (`BR-NOT-029` (a)).** For the mailing row:
    its own six columns. For the service address: the premises' four, and the
    unit's LABEL as `line2` — a unit refines its building by label and never by
    a second address (hard rule 8), and an envelope to a flat without its unit
    reaches the building and not the customer. `country` is left empty there:
    the premises holds none, and the utility's own country is not a fact about a
    customer (`DEF-2847`).

    Returns `{"line1", "line2", "city", "state", "postal_code", "country",
    "source", "missing"}` — `source` is `mailing_address` or `service_address`
    (the delivery snapshot's own words), or None when there is no address at
    all. **`{"unanswerable": True}`** means metering could not be asked, which
    is a fact about the PLATFORM and not an incomplete address (`BR-BIL-036`).
    **None** is an account this tenant does not hold (HR-1). It is a READ and
    writes nothing (`BR-CUS-674`).
    """
    if account_id in (None, ""):
        return None
    account = models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id).first()
    if account is None:
        return None
    answer = _postal_recipient(account, None)
    reason = answer.get("unavailable_reason")
    if reason == "recipient_not_resolvable":
        return {"unanswerable": True}
    snapshot = answer.get("snapshot") or {}
    source = snapshot.get("source")
    parts = {
        "line1": snapshot.get("line1"),
        "line2": (
            snapshot.get("line2")
            if source == POSTAL_SOURCE_MAILING
            else snapshot.get("unit_label")
        ),
        "city": snapshot.get("city"),
        "state": snapshot.get("state"),
        "postal_code": snapshot.get("postal_code"),
        "country": snapshot.get("country") if source == POSTAL_SOURCE_MAILING else None,
    }
    return {**parts, "source": source, "missing": _envelope_missing(parts)}


def _po_text(value: Any) -> str | None:
    """`DEF-BIL-9787` — a stored PO as bill text: trimmed, or None for blank."""
    return value.strip() or None if isinstance(value, str) else None


def account_po_number(account_id: Any) -> str | None:
    """`DEF-BIL-9787` — the PO this account's bills quote, or **None**.

    Published for billing's one-time preview, which shows the clerk the bill
    before it is drafted; the drafted bill itself stamps the same value through
    `bill_addressee_for_account`. A READ; writes nothing. None for an account
    this tenant does not hold (HR-1) and for one that names no PO."""
    if account_id in (None, ""):
        return None
    value = (
        models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id)
        .values_list("po_number", flat=True)
        .first()
    )
    return _po_text(value)


def bill_addressee_for_account(account_id: Any) -> dict[str, Any] | None:
    """WHO A BILL IS FOR AND WHERE IT GOES — PUBLISHED FOR BILLING'S STAGE 6.

    `DEF-BIL-8283` (PO report, 2026-09-30): an issued one-time fee bill printed
    no customer name, no service address and no mailing address, because the
    one-time kinds build their bill with an EMPTY gather snapshot and nothing
    at draft asked customers who the bill was for. This is the one question,
    asked once, at draft, so every bill kind — cycle and one-time — freezes the
    same answer into its own payload (BR-BIL-030).

    Returns `{"customer_name", "po_number", "service", "mailing"}`:

      * `customer_name` — the name the accounts list shows
        (`primary_contact_name`): the current customer's `display_name`, the
        primary contact's where no customer holds the account (`DEF-CUS-9776`),
        and any linked customer's name where the account has neither. For a
        master account this is the master's own holder, who is the payer.
      * `service` — the SERVICE address, WALKED to the premises (hard rule 8):
        `{"line1", "unit_label", "city", "state", "postal_code"}`, or None when
        the account reaches no property with a street. The same walk the
        delivery queue uses (`_service_postal`), so the envelope and the bill
        cannot disagree.
      * `mailing` — the account's live `kind='mailing'` row (the one named
        exception to rule 8), in its six parts, or None when it has none.

    **None** is an account this tenant does not hold (HR-1). A READ; writes
    nothing.
    """
    if account_id in (None, ""):
        return None
    account = models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id).first()
    if account is None:
        return None
    name = primary_contact_name(account)
    if not (name or "").strip():
        name = (
            models.CustomerAccount.objects.filter(
                tenant_id=account.tenant_id, account=account
            )
            .order_by("created_at", "id")
            .values_list("customer__display_name", flat=True)
            .first()
        )
    name = (name or "").strip() or None
    service_answer = _service_postal(account, name)
    service = service_answer.get("snapshot")
    mailing = _postal_snapshot(account, name)
    return {
        "customer_name": name,
        # `DEF-BIL-9787` — *"PO or reference on bills"*, the ACCOUNT's own column
        # (`accounts.po_number`, CR-171 `P1.01`): printed on every bill of this
        # account from the next one drafted. None when the account names none.
        "po_number": _po_text(account.po_number),
        "service": (
            {
                key: service.get(key)
                for key in ("line1", "unit_label", "city", "state", "postal_code")
            }
            if isinstance(service, dict)
            else None
        ),
        "mailing": (
            {
                key: mailing.get(key)
                for key in ("line1", "line2", "city", "state", "postal_code", "country")
            }
            if isinstance(mailing, dict)
            else None
        ),
    }


# ── row / detail serialization ──────────────────────────────────────────────
def owner_master_account_summary(account_id: Any) -> dict[str, Any] | None:
    """DEF-650 — an owner's account, as the PREMISES screens must show it.

    **PO 2026-08-27, verbatim:** *"you ahve to showall details form account"*.
    That sentence is the whole reason this selector exists rather than the
    premises row carrying a copied name: the details are READ FROM THE ACCOUNT
    at the moment of asking, so they cannot drift the way two writable copies of
    one fact drift (`OQ-501`'s own complaint about `owner_manager`).

    ⚠ **IT REUSES `account_row` RATHER THAN ASSEMBLING ITS OWN MONEY.** The
    balance cells are `DEF-127`'s hard-won shape — the ledger's Σ, with
    `balance_unavailable` carrying a REASON where the books cannot be asked, and
    never `0.00` substituted for *"we could not tell"*. A second assembly here
    would be a second derivation of the same figure, which is exactly what
    BR-REP-002 forbids.

    `None` for an id this tenant does not hold — the same answer as *no account
    is linked*, because from the premises screen's point of view they are the
    same fact: there is nothing to show.
    """
    if account_id in (None, ""):
        return None
    account = account_queryset().filter(pk=account_id).first()
    if account is None:
        return None
    row = account_row(account)
    return {
        **row,
        # `kind` is not on the S17 row and it is the point HERE: whether this
        # owner's account is a `master` or a `regular` one is what the
        # single-family ruling turns on (PO 2026-08-27, decision 3 — an
        # owner-occupier gets ONE regular account).
        "kind": account.kind,
        "opened_at": account.opened_at.isoformat() if account.opened_at else None,
        # ── CR-056 W3 task 18 · BR-MET-1020 — WHO, reached THROUGH the account
        # A premises owner used to reach a customer two ways, and one of them
        # skipped the account — the only row that holds a balance, receives a
        # bill and can be posted to. The shortcut is ruled out, so metering asks
        # THIS read for the party instead, one hop further along, and gets the
        # answer that also owns the money. `None` where the account has no
        # customer linked, which every account created before BR-CUS-054 does.
        "customer": customer_for_account(account.id),
    }


def master_account_numbers(account_ids: Any) -> dict[str, dict[str, Any]]:
    """`BR-MET-1181` — the NUMBER, name, status and kind of many accounts, in
    **TWO statements for the whole page**, whatever the page holds.

    ⛔ **THE BULK ANSWER TO ONE QUESTION `owner_master_account_summary` ABOVE
    ANSWERS ONE AT A TIME, AND IT IS NOT A CHEAPER COPY OF IT.** That one is an
    account read PLUS a ledger derivation per call — `DEF-324` measured the cost
    of doing that per row at *47 of 118 profiled seconds answering one question
    304 times* — so the premises list may not use it, and without this the list
    holds an account id it is forbidden to print (B14 rule 31) and no number it
    could print instead.

    ⚠ **`name` WAS ADDED 2026-09-23 AND IT COSTS THE SECOND STATEMENT — READ
    THIS BEFORE 'SIMPLIFYING' IT AWAY (`DEF-MET-6304`).** The premises list drew
    the Owner cell as *"No name recorded · AC-2026-00051"* on every row that had
    an account, because it had a number and no name. **`accounts` HAS NO `name`
    COLUMN**: what a clerk reads is the account's PRIMARY CONTACT's `full_name`,
    in `contacts`, which is how `account_row` below has always served it and why
    the DETAIL screen showed the real name the whole time. So the name could not
    ride free on the statement above it; it is one more `SELECT … WHERE
    account_id IN (…)` **for the page** — never per row, which is the whole
    point of this function.

    ⛔ **AND IT DELEGATES TO `primary_contact_names_for` RATHER THAN RE-READING
    `contacts` HERE.** That function decides WHICH contact is *"the"* name when
    an account has several (`-is_primary, created_at, id`), and its own docstring
    records why a second reading is dangerous: *"a batched read that sorted
    differently would quietly rename customers on the list while their detail
    page kept the old name — a regression no statement count can see."* A
    `Subquery` annotation here would have folded this into one statement and
    would have been exactly that second reading; it was considered and rejected
    on those grounds (decision log 2026-09-23).

    ⚠ **IT STILL DELIBERATELY CARRIES NO MONEY**, and the name does not weaken
    that. A balance on a list is a figure somebody quotes, and `DEF-127`'s shape
    — the ledger's Σ, with a REASON where the books cannot be asked, never
    `0.00` substituted for *we could not tell* — cannot be served cheaply in
    bulk. Ask `owner_master_account_summary` for one account when money is
    wanted. A name is not a figure and nobody reconciles against it.

    ⚠ **`kind` IS SERVED BECAUSE A CALLER HAS TO BE ABLE TO REFUSE ON IT.** An
    ordinary account at an address is a TENANT's, and naming one as the owner
    would bill the tenant for the landlord's charges — so the door that attaches
    a named account checks this, and can only check it if it is here.

    `{}` for an empty list, which costs NO statement at all. An id with no entry
    is one this tenant does not hold, which the caller renders as *no number*
    rather than as *no account*; `name: None` inside an entry is a different
    fact — this account names nobody — and a caller must keep the two apart.
    """
    ids = [str(value) for value in (account_ids or []) if value not in (None, "")]
    if not ids:
        return {}
    names = primary_contact_names_for(ids)
    return {
        str(row["id"]): {
            "account_no": row["account_no"],
            "kind": row["kind"],
            "status": row["status__code"],
            "name": names.get(str(row["id"])),
        }
        for row in account_queryset()
        .filter(pk__in=ids)
        .values("id", "account_no", "kind", "status__code")
    }


def _service_cells(
    account: models.Account,
    service_codes: dict[str, list[str]] | None,
    service_drops: dict[str, int] | None,
    account_key: str,
) -> dict[str, Any]:
    """The two keys the Services cell draws — `DEF-CUS-6917`.

    `services` is what this account is shown to take. `services_unresolved` is
    **how many open agreements did not make it into that list**, and it is
    served on EVERY row, always a number and never null, because a key that is
    sometimes absent is a blind spot with no number beside it wearing a
    slightly better disguise.

    ⚠ **A ZERO IS A CLAIM AND IS NOT FREE.** When a caller hands in a codes map
    with no drop map beside it, this does NOT assume zero — it asks the
    singular, which resolves the account's own agreements and counts honestly.
    Assuming zero there is the exact defect this whole change is about, one
    layer up."""
    if service_codes is None:
        codes, skipped = service_codes_and_drops_for(account)
        return {"services": codes, "services_unresolved": skipped}
    if service_drops is None:
        return {
            "services": service_codes.get(account_key, []),
            "services_unresolved": service_codes_and_drops_for(account)[1],
        }
    return {
        "services": service_codes.get(account_key, []),
        "services_unresolved": int(service_drops.get(account_key, 0)),
    }


def account_row(
    account: models.Account,
    *,
    positions: seams.ArPositions | None = None,
    last_bill_dates: dict[str, Any] | None = None,
    ageing: dict[str, tuple[str, int, str]] | None = None,
    customer_nos: dict[str, str | None] | None = None,
    contact_names: dict[str, str | None] | None = None,
    service_codes: dict[str, list[str]] | None = None,
    #: `DEF-CUS-6917` — how many of this account's OPEN service agreements this
    #: read could not resolve to a service code. Optional and defaulted so a
    #: caller that hands in `service_codes` without it still gets an honest
    #: answer: the singular below is then asked, rather than zero being assumed.
    service_drops: dict[str, int] | None = None,
    premise_cells: dict[str, tuple[str | None, str | None]] | None = None,
) -> dict[str, Any]:
    """One S17 row (US-CUS-001 §5), with the honestly-absent cells.

    Every keyword here is the same idea: the answer for the WHOLE page, resolved
    once by the caller (`account_list`). A row asked on its own resolves its own,
    which is a query or two for one row; a list that let every row do that issues
    them PER ROW on the product's busiest screen — and `apps/customers/api
    .accounts` builds every row before the paginator slices, so "per row" means
    per ACCOUNT, not per fifty.

    ⚠ **THE LAST THREE WERE ADDED 2026-09-01 (DEF-2723) AND THEY ARE SIX OF THE
    NINE STATEMENTS THIS LIST COST PER ACCOUNT.** The first four were batched in
    `DEF-127` and `CR-030` for exactly this reason and the comment saying so has
    sat above them ever since; the premise cell, the contact's name and the
    service chips were left per row and nothing measured them. Nine statements ×
    seventy-three accounts is the 562 ms the accounts list took on an IDLE
    system. Measured on this suite's fixtures: 44 statements for four accounts
    and 116 for twelve, before; 13 and 13, after.
    """
    account_key = str(account.id)
    if premise_cells is None:
        unit_label, premise_label = _premise_cell(account.unit_id, account=account)
    else:
        unit_label, premise_label = premise_cells.get(account_key, (None, None))
    if positions is None:
        positions = _balance_positions_for([account.id])
    if last_bill_dates is None:
        last_bill_at = seams.last_issued_invoice_date(account.id)
    else:
        last_bill_at = last_bill_dates.get(str(account.id))
    if customer_nos is None:
        customer_nos = customer_nos_for([account.id])
    return {
        "id": str(account.id),
        "account_no": account.account_no,
        # CR-030 W2 T2.9(b) / BR-CUS-053 (AMENDED 2026-08-24) — OUR number for
        # the customer this account belongs to, so the `CUSTOMER #` column has a
        # value to render and the search that now matches it has something to
        # show for a hit.
        #
        # ⚠ NULL IS A REAL ANSWER AND IS NOT AN ABSENCE-WITH-A-REASON. Three
        # ordinary states produce it: an account with no `customer_accounts`
        # link at all (every account created before BR-CUS-054's entity landed),
        # a linked customer whose `customer_no` the 0014 backfill has not
        # reached, and an import row that carried neither a customer reference
        # nor a name. None of the three is a gap in a computation, so this cell
        # needs no `*_unavailable` block — unlike `balance` and `ageing_segment`
        # above and below it, where a null means a figure could not be DERIVED.
        "customer_no": customer_nos.get(str(account.id)),
        "name": (
            primary_contact_name(account)
            if contact_names is None
            else contact_names.get(account_key)
        ),
        # ⚠ **NULL IS A REAL ANSWER SINCE `CR-056` W1, AND `str(None)` IS NOT.**
        # `accounts.unit_id` is nullable from migration 0036 (`BR-CUS-1010`: the
        # owner's account hangs off the ADDRESS), and the old expression here
        # served the four characters `"None"` — a value every screen would render
        # as a unit label and every client would treat as an id. B14 rule 31 says
        # no database id is ever the visible value of a field; a stringified null
        # is worse than an id.
        "unit_id": str(account.unit_id) if account.unit_id else None,
        "unit_label": unit_label,
        "premise": premise_label,
        # `CR-056` W1 — the address the account hangs off, served beside the unit
        # so PRM-02 and S17 can find an owner's account by premises rather than
        # by guessing which common area it was anchored on (`BR-CUS-1010`).
        "premises_id": (str(account.premises_id) if account.premises_id else None),
        **_service_cells(account, service_codes, service_drops, account_key),
        # `last_bill_at` is resolved above and is BR-CUS-510 clause 4's input:
        # a `non_billable` account that has been billed is not *awaiting* its
        # first bill, whatever its balance reads (DEF-628).
        **_balance_cells(account, positions, last_bill_at=last_bill_at),
        "currency": account.currency,
        "status": account.status.code,
        "status_name": account.status.name,
        "status_behavior_class": account.status.behavior_class,
        # BR-CUS-068: regular | master — served on every row so the S17 list
        # and the PRM-02 Common-areas tab read the same fact.
        "kind": account.kind,
        "account_type": account.account_type.code,
        "account_subtype": (
            account.account_subtype.code if account.account_subtype_id is not None else None
        ),
        # ⚠ **THE TENANT'S OWN LABEL, SERVED BESIDE THE CODE — `DEF-CUS-5000`,
        # 2026-09-12.** S21's Overview printed `small_commercial` at a clerk,
        # because the code was the only thing on the wire and the screen had
        # nothing else to render. B14 rule 31/32: no database id and no
        # internal code is the visible value of a field.
        #
        # This is `status` / `status_name` four lines up, and deliberately the
        # same shape rather than a new one: `account_subtypes` is TENANT-DEFINED
        # (BR-CUS-067's twelve-row tree seeds per tenant and a tenant may add to
        # it), so the label belongs to the tenant and cannot be a front-end
        # catalogue string — which is exactly the mistake `DEF-684` made for
        # `account_type`, where `customers.accounts.category.*` held four codes
        # and three newer ones fell through to their raw slug.
        #
        # `account_subtype` is already `select_related` in `account_queryset`,
        # so this costs no query. The CODE stays on the wire: a caller
        # filtering or branching needs it, and the screen falls back to it when
        # a row carries no label rather than inventing one.
        "account_subtype_name": (
            account.account_subtype.name if account.account_subtype_id is not None else None
        ),
        "autopay": account.autopay,
        "opened_at": account.opened_at.isoformat() if account.opened_at else None,
        "closed_at": account.closed_at.isoformat() if account.closed_at else None,
        # **WHY THIS TENANCY ENDED** (PO ruling 2026-09-20 item 3, option A) —
        # served beside the date it ended on, because the two are one fact read
        # together and a screen that had to make a second call for the second
        # half would render them a frame apart.
        #
        # ⚠ **A CODE, NEVER A WORD** — one of `models.CLOSE_REASONS`. The
        # catalogues hold what a clerk reads, per B14 rule 35, so this key is
        # safe to count on and safe to translate.
        #
        # ⚠ **NULL IS THE ORDINARY ANSWER AND NEEDS NO `*_unavailable` BLOCK.**
        # It means the close predates this column or nobody chose a reason —
        # `customer_no` above takes the same posture for the same reason: a
        # null that is a real state is not a figure that could not be derived.
        # It is what makes this readable on the MOVE RECORD too, which the
        # ruling asked for: `move_record_reads._completed` walks to the account
        # for it rather than copying it onto `move_records` (BR-CUS-150 — the
        # record is of the JOB, and nothing written by the close is copied in).
        "close_reason": account.close_reason or None,
        # US-CUS-001 §5 "Last bill" — SERVED since 2026-08-15 (DEF-127). It was
        # null on every row while `invoices` was full of issued bills, because
        # the seam resolved the wrong module attribute; the cell said "Awaits
        # billing" about accounts that had been billed. Still null when the
        # account genuinely has no issued bill, which is what that copy is for.
        "last_bill_at": last_bill_at.isoformat() if last_bill_at else None,
        # Honestly absent — see the module docstring. Never a fabricated value.
        # ⚠ THIS IS BILLING'S invoice-derived display state ("Current / 30d past
        # / 60+ past") and it is STILL unwired. It is NOT the CR-030 `AGEING`
        # column: that is `ageing_segment` below, in BR-CUS-048's four-band
        # vocabulary, derived from this account's own opening position. The two
        # spellings sitting side by side is deliberate and REPORTED — when
        # billing publishes `account_aging_state`, one vocabulary has to win and
        # that is a ruling, not a lane's merge.
        "aging": seams.aging_state(account.id),
        # CR-030 §5.1.2's NEW column — BR-CUS-016 derived, never stored.
        **ageing_cells(account.id, ageing),
    }


def _premise_cell(
    unit_id: Any, *, account: models.Account | None = None
) -> tuple[str | None, str | None]:
    """US-CUS-001 §5 "Premise" ("1408 Elm St · A"), read through metering.

    ⚠ **AN ACCOUNT THAT NAMES NO UNIT STILL HAS AN ADDRESS TO SHOW** (`CR-056`
    W1 / `BR-CUS-1010`). Before this, `unit_id=None` reached `seams.unit_row` and
    the cell came back empty on both halves, so the owner's account rendered with
    no premise at all — a stated absence about a fact the row is holding one
    column along. The UNIT half is genuinely absent (there is no unit) and stays
    `None`; the ADDRESS is read straight from the premises.
    """
    if unit_id not in (None, ""):
        try:
            unit = seams.unit_dict(seams.unit_row(unit_id))
        except errors.NotFoundError:  # pragma: no cover — a PROTECTed FK cannot dangle
            return None, None
        address = unit.get("premise_address")
        label = unit.get("label")
        return label, f"{address} · {label}" if address and label else (address or label)
    premises_id = getattr(account, "premises_id", None) if account is not None else None
    if premises_id in (None, ""):
        return None, None
    try:
        premises = seams.premises_ref(premises_id)
    except errors.NotFoundError:  # pragma: no cover — the backfill only writes resolvable ids
        return None, None
    return None, premises.get("address_line")


#: What `_unit_facts` answers when the unit or the premises cannot be read. It is
#: declared ONCE because the function has five returns and a key added to four of
#: them is a field that is present on most accounts and silently absent on the
#: rest — which reads to a screen exactly like a null, and is not one.
_NO_UNIT_FACTS: dict[str, Any] = {
    "unit_type": None,
    "premise_address": None,
    "unit_floor": None,
    "unit_square_feet": None,
    "premise_no": None,
    "service_premises_id": None,
}


def _unit_facts(account: models.Account) -> dict[str, Any]:
    """`ACC-02` R5's UNIT group — *what this account is attached to*.

    Two facts the Overview draws and this payload did not carry: the unit's
    TYPE and the building's STREET ADDRESS. Both are metering's and both are
    read through the seam (`unit_detail_dict`), never by importing a metering
    model — B2 §2's boundary, and the same door `_premise_cell` already uses.

    ⚠ **`premise_address` IS THE BUILDING'S AND `_premise_cell`'s `premise` IS
    NOT THE SAME STRING.** That one composes `"<address> · <label>"` for a list
    cell; the drawing gives `Premises` and `Unit` as two separate rows, so the
    two halves travel separately and the screen joins nothing.

    ⚠ **AN ACCOUNT WITH NO UNIT STILL HAS AN ADDRESS** (`BR-CUS-1010`) — a
    master account's is on `accounts.premises_id`, exactly as `_premise_cell`
    reads it. The UNIT half is genuinely absent there and stays `None`; hard
    rule 8's *everything walks to the premises* is why the address half is not.

    ⚠ **THREE MORE FACTS JOINED THE PICK ON 2026-09-13 AND NOTHING NEW IS READ
    (`DEF-CUS-5180`).** The transfer wizard's step 1 is drawn with `Floor`,
    `Floor area` and a premises reference on `Premises 310 Marigold Lane ·
    PR-0518`; `metering.unit_detail_dict` has returned `floor_label`,
    `square_feet` and `premise_no` all along and this function simply did not
    select them. So this is a WIDENED PICK out of a dict already in hand — one
    seam call, no second query, no column invented, nothing written — which is
    the decision table's *"the endpoint exists and nothing calls it: wire it,
    a defect and not a gap"*.

    ⚠ **THE PREMISES BRANCH SERVES `premise_no` AND NOT THE UNIT HALVES.**
    `premises_ref` answers about a BUILDING, so a master account with no unit
    has no floor and no floor area — and `None` there is the truth rather than
    a gap the screen should fill.
    """
    unit_id = getattr(account, "unit_id", None)
    if unit_id not in (None, ""):
        try:
            unit = seams.unit_dict(seams.unit_row(unit_id))
        except errors.NotFoundError:  # pragma: no cover — a PROTECTed FK cannot dangle
            return dict(_NO_UNIT_FACTS)
        return {
            "unit_type": unit.get("unit_type"),
            "premise_address": unit.get("premise_address"),
            "unit_floor": unit.get("floor_label"),
            "unit_square_feet": unit.get("square_feet"),
            "premise_no": unit.get("premise_no"),
            # `DEF-PAY-6342` — the premises this account's SERVICE address
            # lives on, as a LINK KEY for the returned-post clear step (a
            # service-address letter is fixed on the premises, never here). It
            # is not `premises_id` above, which is only the owner's-account
            # anchor and is null on every unit account. Never displayed (B14
            # rule 31).
            "service_premises_id": (
                str(unit.get("premises_id")) if unit.get("premises_id") else None
            ),
        }
    premises_id = getattr(account, "premises_id", None)
    if premises_id in (None, ""):
        return dict(_NO_UNIT_FACTS)
    try:
        premises = seams.premises_ref(premises_id)
    except errors.NotFoundError:  # pragma: no cover — the backfill only writes resolvable ids
        return dict(_NO_UNIT_FACTS)
    return {
        **_NO_UNIT_FACTS,
        "premise_address": premises.get("address_line"),
        "premise_no": premises.get("premise_no"),
        "service_premises_id": str(premises_id),
    }


def _account_co_owners(account: models.Account) -> list[dict[str, Any]]:
    """`DEF-CUS-9837` — name, kind and how to reach them; nothing that
    identifies (see the call site)."""
    from apps.customers.co_owner_models import AccountCoOwner

    return [
        {
            "kind": row.kind,
            "full_name": row.full_name,
            "email": row.email,
            "phone": row.phone,
        }
        for row in AccountCoOwner.objects.filter(
            tenant_id=account.tenant_id, account_id=account.pk
        ).order_by("created_at", "id")
    ]


def _premise_locality(account: models.Account) -> dict[str, Any] | None:
    """`BR-MET-1161` — the account's locality, taken from its premises.

    The premises is reached the way `_premise_cell` reaches it: through the
    UNIT when there is one, and through `accounts.premises_id` for an owner's
    account that names no unit (`BR-CUS-1010`). Nothing is stored on the
    account and nothing is composed here — three columns travel, and the
    screen writes the sentence.
    """
    premises_id = getattr(account, "premises_id", None)
    if premises_id in (None, "") and account.unit_id not in (None, ""):
        try:
            premises_id = seams.unit_dict(seams.unit_row(account.unit_id)).get("premises_id")
        except errors.NotFoundError:  # pragma: no cover — a PROTECTed FK cannot dangle
            return None
    return seams.premises_locality(premises_id)


def _deposit_waiver(account: models.Account) -> dict[str, Any] | None:
    """Who forgave this account's deposit, when, how much and why — or None.

    `DEF-CUS-6370`: the four `deposit_waived_*` columns, written together by
    `deposit.take()` and nowhere else. The amount is the plan's figure at the
    moment of the waive, in the account's own currency (`BR-TEN-042`), served
    at storage precision; the screen rounds for display (hard rule 2).

    ⚠ **A NAME, NEVER THE USER'S ID (B14 rule 31).** Read off the FK row the
    way `account_documents` reads `uploaded_by` — full name, else email — and
    `None` rather than an empty string, because a blank reads as *nobody*.
    """
    amount = getattr(account, "deposit_waived_amount", None)
    if amount is None:
        return None
    who = account.deposit_waived_by if account.deposit_waived_by_id else None
    name = (getattr(who, "full_name", "") or getattr(who, "email", "") or "").strip()
    return {
        "amount": str(Decimal(amount).quantize(Decimal("0.0001"))),
        "currency": account.currency,
        "waived_at": account.deposit_waived_at.isoformat() if account.deposit_waived_at else None,
        "waived_by_name": name or None,
        "reason": account.deposit_waive_reason,
    }


def account_detail_dict(account: models.Account) -> dict[str, Any]:
    """GET /accounts/{id} (11b §2.6 "account + services + plan + meters +
    balance"). `plan` is null with its reason attached — see the docstring."""
    service_by_point = _service_by_point_for(account)
    contacts = models.Contact.objects.filter(
        tenant_id=account.tenant_id, account=account, deleted_at__isnull=True
    ).order_by("-is_primary", "created_at", "id")
    addresses = models.Address.objects.filter(
        tenant_id=account.tenant_id, account=account, deleted_at__isnull=True
    ).order_by("kind", "created_at", "id")
    return {
        **account_row(account),
        # ── THE CONSUMER CATEGORY'S **ID**, BESIDE ITS CODE (`DEF-BIL-5318`,
        # 2026-09-15).
        #
        # 🔒 HUMAN-REVIEW-PENDING — this ONE key decides whether a customer's
        # FIRST bill carries the deposit their plan asks of their category, which
        # is a money decision even though nothing here computes a figure (the
        # same reading BR-CUS-171's block above this file already takes). Ledger
        # row: 12-governance/09-human-review-ledger.md. This file is NOT on
        # `10-scripts/gates/human_owned.txt` and a lane may not add it; the
        # marker is scoped to the read, as its neighbour's is.
        #
        # `account_row` above serves `account_type` — the CODE —
        # and until this line the detail served nothing else, so billing's
        # `one_time._account_type_id` read `account_type_id` off this blob, got
        # `None`, and EVERY first bill refused with *"names no consumer
        # category"*. The first kind had never drafted through S30's tab since
        # 2026-08-16. It hid because the PREVIEW needs no category: only the
        # DRAFT refused.
        #
        # ⚠ **THE ID AND NOT THE CODE, AND THE DIFFERENCE IS A SILENT
        # UNDER-BILL RATHER THAN A TIDINESS POINT.** `plan_deposit_rules` is
        # keyed rate_plan × account_type where `account_type_id` is a
        # `UUIDField` (`rating.models.PlanDepositRule`), and
        # `rating.selectors.deposit_rule_for` opens with
        # `_valid_uuid(account_type_id)` and answers `None` for anything that
        # is not one. `None` from that read is SIGNED to mean *this plan asks
        # this category for no deposit*, so a caller handed the code
        # `"residential"` would draft a first bill with the deposit line simply
        # ABSENT instead of refused — WE-6's **$150.00** off somebody's first
        # bill, on an immutable document, with every test green. The code is
        # served for DISPLAY; this is served for the MONEY, and they are not
        # interchangeable.
        #
        # ⚠ `str(None)` IS NOT A NULL — the same rule `account_row` states over
        # `unit_id`. The column is NOT NULL today, so this is belt-and-braces
        # and not a live case; it is written this way so the day the column
        # becomes nullable the seam serves a null rather than the four
        # characters a client would treat as an id.
        "account_type_id": (str(account.account_type_id) if account.account_type_id else None),
        "deposit_on_file": _money(account.deposit_on_file),
        "deposit_received_on": (
            account.deposit_received_on.isoformat() if account.deposit_received_on else None
        ),
        # ── A WAIVED DEPOSIT, KEPT ON THE ACCOUNT (`DEF-CUS-6370`, customers
        # 0066). `null` when nothing was waived — never a zero block — so the
        # Deposit tile can tell *waived $150.00* from *never asked*.
        "deposit_waiver": _deposit_waiver(account),
        "credit_tier": account.credit_tier,  # COMPUTED cache (BR-CUS-058) — no input path
        "tax_exempt": account.tax_exempt,
        "tax_exempt_ref": account.tax_exempt_ref,
        "tax_exempt_expires": (
            account.tax_exempt_expires.isoformat() if account.tax_exempt_expires else None
        ),
        # ── THE PER-TAX CERTIFICATES (`DEF-CUS-9774`, `DEF-CUS-9775`). The
        # three keys above are the BLANKET exemption (every tax), which PO
        # ruling (A) of 2026-10-05 keeps a move-in from setting: a certificate
        # removes only the tax it names. So an account can be exempt from the
        # City's tax with `tax_exempt` false, and the account page and the
        # move record read THIS to say so. Rating's rows, through the seam:
        # `{certificate_ref, expires_on, state, tax_name, category_name, ...}`.
        "tax_exemptions": seams.account_tax_exemptions(account.pk),
        # `DEF-CUS-9788` — *"PO or reference on bills"* (move-in step 2, image
        # 40; `accounts.po_number`). Served so the account page and the move's
        # Account tab can show what this account's bills quote. Display only.
        "po_number": _po_text(account.po_number),
        "bad_address": account.bad_address,
        "nsf_count": account.nsf_count,
        "preferred_language": account.preferred_language,
        # ── BR-CUS-028's delivery election, BUILT 2026-08-31 (CR-052 task 14).
        # ⚠ NEITHER TURNS PRINT OFF. BR-BIL-036 makes print the FLOOR — a
        # paperless customer still receives the document — so these say what
        # this account gets IN ADDITION, and `delivery_channel_election_for_
        # account` is the read the bill run uses. Serving them here is what lets
        # S21 render the preference it collected instead of a dead control.
        "paperless": account.paperless,
        "sms_reminders": account.sms_reminders,
        # ── PORTAL ACCESS, DERIVED (DEF-CUS-4625). ⚠ The S21 panel used to
        # announce that the portal was "out of scope for this version" and
        # that these two were "columns that were never built". CR-068 built
        # the portal, CR-082 seeded it, and both columns landed 2026-08-31 —
        # so all three claims were false and the screen had no way to know,
        # because the sentence was TYPED rather than READ. Nothing is typed
        # now: the panel states what this reads, and `unreadable` names
        # anything it could not read, with a number beside it.
        "portal_access": portal_seam.portal_access_for_account(account),
        # BR-BIL-025's account override — the first leg of the template chain.
        # NULL means "no override" and is every account today; the bill then
        # resolves the category default, then the tenant fallback.
        "template_override_id": (
            str(account.template_override_id) if account.template_override_id else None
        ),
        # EP-TEN-09 / US-SHL-016: the tenant's OWN values, so S21 can render
        # them read-only. The DEFINITIONS come from tenancy's registry — this
        # only carries what was recorded, and a field with nothing recorded is
        # simply absent from the blob (the renderer shows an empty cell, never
        # a null literal).
        "custom_data": dict(account.custom_data or {}),
        "contacts": [contact_dict(row) for row in contacts],
        # ⊕ `DEF-CUS-9837` — the second people on the account as move-in
        # (CR-171 P1.10) and New Connect (`DEF-CUS-9830`) save them: co-owners,
        # or a company's owners and officers. The account page's Co-applicant
        # panel lists them. ⚠ **NEVER AN IDENTIFIER** — no SSN, no licence, not
        # even their last four, and no date of birth (BR-CUS-092; the move's
        # own Account tab reads them the same way, `move_record_reads._co_owners`).
        "co_owners": _account_co_owners(account),
        "addresses": [address_dict(row) for row in addresses],
        # ── `BR-MET-1161` (PO ruling 2026-09-04) — WHERE THE METER IS, read
        # from the one home. `DEF-CUS-3653`: the header composed this line from
        # an `addresses` row of `kind='service'`, which is retired, so it comes
        # from the premises the account resolves to — `account → unit →
        # premises`, exactly the chain the PO drew.
        #
        # ⚠ NULL IS A REAL ANSWER and needs no `*_unavailable` block: a premises
        # whose city was never typed has no locality, and that is a fact rather
        # than a failed derivation. An account naming neither a unit nor a
        # premises has none either, and the header simply draws one part fewer.
        "premise_locality": _premise_locality(account),
        # ── `ACC-02` R5's UNIT group, the two facts it drew that never travelled.
        # `unit_type` and `premise_address` are metering's, read through the
        # seam. The drawing's `Service address` row is this street address plus
        # `premise_locality` above — composed ON THE SCREEN, because two halves
        # that travel separately cannot disagree with the header, which already
        # composes the same pair (`DEF-CUS-3653`'s lesson).
        **_unit_facts(account),
        "service_agreements": [
            agreement_dict(row, service_by_point) for row in service_agreements_for(account)
        ],
        # `CR-056` W1 — an account that names no unit has no meters ON a unit,
        # and asking the assets seam for `None` would ask "what stands on no
        # unit". A master's meters are the ones on the units it COVERS, which is
        # `covered_unit_ids` and a different question from this cell; nothing is
        # invented here to fill the gap.
        "meters": [
            {"id": m.get("id"), "asset_no": m.get("asset_no"), "qualifier": m.get("qualifier")}
            for m in (seams.assets_on_unit(account.unit_id) if account.unit_id else [])
        ],
        # BR-CUS-014 sc.6 prices from the ACCOUNT snapshot. It has no table
        # (BR-CUS-029), so this is null and says why. UNCHANGED, and it stays
        # unchanged deliberately — see `unit_plan` immediately below.
        "plan": None,
        "plan_snapshot_unavailable": "BR-CUS-029",
        # ── DEF-2419 · THE PLAN THIS ACCOUNT IS BILLED ON, READ THROUGH THE FK
        #
        # PO ruling 2026-09-01: *"It should be foreign key - it should take it
        # from Unit and display it there - that is important"* — confirming
        # their ruling of 2026-08-11, *"from unit you will derive the plan"*,
        # which `services._account_and_unit_plan` and the change-plan wizard
        # have followed since and which this payload never did.
        #
        # ⚠ **WHY THIS IS A SECOND KEY AND NOT `plan` ABOVE.** The comment above
        # used to end *"the unit's plan is NOT substituted, because the two
        # diverge the moment an override happens"*, and there is no override and
        # there cannot be one: no column anywhere can hold a plan for one
        # account differing from its unit, so the divergence it guarded against
        # has nowhere to be stored. The reasoning was wrong — but the CAUTION
        # was not, and it is preserved by the split. `plan` means "the snapshot
        # taken when this account was set up", which is what priced its old
        # bills and is still not held; `unit_plan` means "the plan the unit
        # stands on TODAY". A consumer reading today's plan out of a key named
        # `plan` would be reading it as the plan that priced an old bill, which
        # is the one substitution the original refusal was right to refuse.
        #
        # STORING vs SHOWING: nothing here is written. It is a read along keys
        # the schema already has — `accounts.unit_id` (reviewed cross-module FK,
        # B2 §2) → `units.rate_plan_id` → rating's `plan_ref` — and both ends
        # scope on their owning side (hard rule 1).
        #
        # None on three real absences, each stated by the screen rather than
        # filled: the account names no unit, the unit stands on no plan, or the
        # plan is no longer published. See `seams.unit_plan_in_force`.
        "unit_plan": seams.unit_plan_in_force(account.unit_id),
        # BR-CUS-054's first-class customer — SERVED as of 2026-08-11, when the
        # entity got its tables (migration 0005). This is the "all accounts for
        # this customer" capability the rule names (EP-CUS-03 §5): the customer
        # and every account linked to it, tenant-scoped.
        #
        # NULL is a real answer, not a gap: every account created before the
        # table existed has no link, and so does an imported row that carried
        # neither a customer reference nor a name. The S21 header falls back to
        # the primary CONTACT's name in that case, exactly as it always did.
        "customer": customer_for_account(account.pk),
        # BR-CUS-171 (PO 2026-08-27, closing OQ-531) — the parent/child link,
        # DERIVED from the premises and stored nowhere. A master answers its
        # children; every other account answers its master. Both are `[]`/null
        # for a standalone account, which is a real answer and not a gap.
        #
        # ⚠ THE COUNT IS WHAT THE FRONTEND HAS BEEN TYPING SINCE 2026-08-24 AND
        # NOTHING HAD EVER SERVED (hard-won law 2):
        # `07-frontend/src/features/customers/moveShared.tsx` declares and
        # renders `open_sub_accounts`, and OQ-531 recorded that it "renders 0 on
        # every tenant until this is ruled". It is ruled, so it is served.
        "sub_accounts": [
            {"id": str(row.id), "account_no": row.account_no, "unit_id": str(row.unit_id or "")}
            for row in sub_accounts_for_master(account)
        ],
        "master_account": _master_ref(account),
        # ── `CR-094-BRC01` R7 / `ACC-S17` — HOW MANY UNITS THIS MASTER COVERS
        #
        # The blueprint's Accounts tab draws the master's own row with its UNIT
        # cell reading *Common areas ×2*, and names the source: *"A real, direct
        # linkage — this account's own open service agreements …
        # `covered_unit_ids(account)`"*. A master names NO unit
        # (`BR-CUS-1010`), so `unit_label` is null on its row and the one cell
        # the tab exists to explain had nothing to render.
        #
        # ⚠ **A COUNT, NOT A LIST OF IDS.** B14 rule 31 keeps a database key off
        # the screen and nothing on this tab needs one, so the payload does not
        # carry ids to be leaked — the same posture `AccountUnitPlan` takes.
        #
        # ⚠ **ON THE DETAIL ONLY, AND THAT IS `NFR-3`.** `covered_unit_ids`
        # walks this account's service agreements and asks the metering seam for
        # each service point's unit. On ONE account that is a read; on
        # `account_row` it would be a per-row fan-out over a 40,000-account
        # list. The tab reads it from the detail it already has, because the tab
        # is on that account's own page.
        #
        # `None` for every ordinary account — it is not 0, because an ordinary
        # account's coverage is its own unit and the question is not asked of
        # it. `ACC-S17`: *"Waits on no new table and, for the most part, no new
        # endpoint."* This is the "for the most part".
        "covered_units": (
            len(covered_unit_ids(account))
            if account.kind == services_master_kind()
            else None
        ),
    }


def _master_ref(account: models.Account) -> dict[str, Any] | None:
    """BR-CUS-171's parent, as `{id, account_no}` — or None, which is the
    answer for a standalone account, for a master itself, and for the ambiguous
    two-masters-one-premises case `master_account_for` refuses to break."""
    master = master_account_for(account)
    if master is None:
        return None
    return {"id": str(master.id), "account_no": master.account_no}


# ── US-CUS-019 — the S68 import batch read model ────────────────────────────
def arrears_on_other_accounts(account_id: Any) -> Decimal:
    """What this customer owes on their OTHER accounts — PO 2026-08-12, OQ-135.

    The PO ruled that a customer holding a credit on one account and an arrear
    on another is **offset first**: the credit goes against the debt before any
    refund is paid. Payments resolves this read BY NAME to honour that, because
    it may not touch customers' tables (B1).

    Worked, on the repo fixture: **$57.13** credit on one account, **$948.20**
    overdue on another with a final notice already sent. This returns 948.20 and
    the refund does not go out.

    **THE CUSTOMER ENTITY IS WHAT MAKES "ANOTHER ACCOUNT" MEAN ANYTHING**
    (BR-CUS-054). Accounts that merely share an address, a surname or a phone
    number are NOT the same person, and offsetting across them would move money
    between strangers. So this walks the `customer_accounts` LINK and nothing
    else; an account with no linked customer returns zero rather than falling
    back to a looser match. The link is N:M deliberately — a jointly-held
    account has more than one holder, so "another account of this customer"
    means any account any HOLDER of this one also holds.

    ⚠ **THIS IS THE CACHED BALANCE** (`accounts.balance`, BR-CUS-015 — the ledger
    is the source of truth). It is used to answer *"is there a debt elsewhere at
    all"*, which a cache stale in either direction still answers well enough to
    stop and ask. It is deliberately NOT good enough to subtract from a refund —
    the same line `apps/billing/final_bill._prior_balance` draws for the same
    reason — which is why the caller REFUSES the refund and asks for a transfer
    rather than quietly netting this figure off it.
    """
    tenant_id = _tenant_id()
    # `customer_accounts` is an N:M LINK (B2 r9 #1), not a column — a joint
    # account has more than one holder, and "another account of this customer"
    # means any account linked to ANY holder of this one.
    customer_ids = list(
        models.CustomerAccount.objects.filter(
            tenant_id=tenant_id, account_id=account_id
        ).values_list("customer_id", flat=True)
    )
    if not customer_ids:
        return Decimal("0")
    sibling_ids = (
        models.CustomerAccount.objects.filter(tenant_id=tenant_id, customer_id__in=customer_ids)
        .exclude(account_id=account_id)
        .values_list("account_id", flat=True)
    )
    owed = (
        models.Account.objects.filter(tenant_id=tenant_id, pk__in=sibling_ids, balance__gt=0)
        .aggregate(total=Sum("balance"))
        .get("total")
    )
    return owed or Decimal("0")


def account_import_batch(batch_id: Any) -> dict[str, Any]:
    """`GET /accounts/imports/{id}` (11b §S68).

    The staged batch, its preview counts and EVERY row — accepted and failed
    alike, each carrying the file's own cells beside what they resolved to.
    That pairing is the point: an operator fixing 27 failures out of 1,240
    needs to see the cell they typed, not only the reason it was refused.
    """
    if not _is_uuid(batch_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    batch = models.AccountImportBatch.objects.filter(tenant_id=_tenant_id(), pk=batch_id).first()
    if batch is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    rows = models.AccountImportRow.objects.filter(tenant_id=batch.tenant_id, batch=batch).order_by(
        "row_no"
    )
    serialized = [
        {
            "row_no": row.row_no,
            "source": (row.raw or {}).get("source") or {},
            "resolved": (row.raw or {}).get("resolved") or {},
            "errors": row.errors or [],
            "account_id": str(row.account_id) if row.account_id else None,
        }
        for row in rows
    ]
    error_count = sum(1 for row in serialized if row["errors"])
    return {
        "id": str(batch.id),
        "filename": batch.filename,
        "cutover_date": batch.cutover_date.isoformat() if batch.cutover_date else None,
        "skip_errors": batch.skip_errors,
        "committed": batch.committed_at is not None,
        "committed_at": batch.committed_at.isoformat() if batch.committed_at else None,
        # BR-CUS-051's staged preview: what would go in, what would not.
        "preview": {
            "rows": len(serialized),
            "valid": len(serialized) - error_count,
            "errors": error_count,
        },
        "rows": serialized,
        # The published template's column list, so the wizard names the columns
        # the SERVER parses rather than a copy that can drift (hard-won law 5).
        "template_columns": list(account_import.PUBLISHED_HEADERS),
    }


def customer_dict(customer: models.Customer) -> dict[str, Any]:
    """BR-CUS-054's entity, as the S21 header chip and the import result read
    it. `accounts` is the "all accounts for this customer" capability the rule
    names — tenant-scoped, and it is a COUNT plus the numbers rather than the
    whole account rows, because the chip lists them and the list screen serves
    them."""
    links = (
        models.CustomerAccount.objects.filter(tenant_id=customer.tenant_id, customer=customer)
        .select_related("account")
        .order_by("account__account_no")
    )
    return {
        "id": str(customer.id),
        # ⚠ **CR-056 W3 task 18 — `customer_no` JOINED THIS PAYLOAD ON
        # 2026-08-31, AND IT IS AN ADDITION RATHER THAN A CHANGE.** B14 rule 31
        # says no database id is the visible value of a field, and until today
        # every consumer of this dict had only `id` to render. The premises
        # screens are the first that must NAME the party they reach through an
        # account, and a uuid is not a name.
        "customer_no": customer.customer_no,
        "kind": customer.kind,
        "display_name": customer.display_name,
        "external_ref": customer.external_ref,
        "accounts": [
            {"id": str(link.account_id), "account_no": link.account.account_no} for link in links
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-056 W5 TASK 25 — THE CUSTOMERS LIST. THERE WAS NO WAY TO BROWSE PEOPLE.
# ═══════════════════════════════════════════════════════════════════════════
# `apps/customers/api.py`'s own header recorded the absence in as many words:
# *"the BR-CUS-054 entity HAS a table as of 2026-08-11, but no story owns a
# customer LIST or DETAIL endpoint yet"*. So a person could only ever be
# reached BACKWARDS — find one of their accounts, then follow the customer chip
# — and a landlord whose account numbers nobody remembers was unreachable.
#
# ⚠ **THE SEARCH MATCHES ON WHAT A CLERK ACTUALLY HOLDS**, which is the same
# reasoning `account_list` gives for putting the account number and the
# customer number in ONE box: the person at the counter has a name, a number
# off a letter, or a phone. All three find them here.
#
# ⚠ **AND A PHONE IS SEARCHED THROUGH THE BLIND INDEX, NOT WITH `LIKE`.** The
# column is app-layer encrypted with a randomised scheme, so `icontains` over it
# would match nothing and look exactly like *"no such customer"* — the silently
# wrong answer `EncryptedTextField.get_lookup` refuses to allow. The index is an
# EQUALITY probe, so a phone search is exact: half a number finds nobody, and
# that is a property of the encryption rather than a bug in the box.
CUSTOMER_SORTS: tuple[str, ...] = ("display_name", "customer_no", "created_at")
CUSTOMER_DEFAULT_SORT = "display_name"  # BR-CUS-053's posture: people A→Z
CUSTOMER_FILTERS: tuple[str, ...] = ("kind",)


def customer_queryset() -> Any:
    """Every customer THIS tenant holds. Hard rule 1, and RLS behind it."""
    return models.Customer.objects.filter(tenant_id=_tenant_id())


def customer_list_queryset(params: ListParams) -> Any:
    """Every customer matching this request — searched, filtered, ordered, LAZY.

    ⚠ **LAZY IS THE WHOLE POINT (`NFR-3`), AND THE PREDICATES BELOW DID NOT
    MOVE.** Until 2026-09-18 the five search legs, the `kind` filter and the
    order lived inside `customer_list`, which returned a BUILT list, and
    `apps/customers/api.customers` handed that list to `paginate_queryset` —
    which needs the whole result set to slice, so every customer a tenant holds
    was built to draw fifty. This function is that same query with nothing
    evaluated, which is what lets `customer_page` put the `LIMIT` in SQL.

    One box, FIVE legs: the customer NUMBER, the legacy reference, the NAME, the
    phone through its blind index and — since CR-056 W2b — the **Tax ID**
    through its own. A clerk holding a scrap of paper does not know which of
    those the digits on it are.

    ⚠ **THE FIFTH LEG IS NOT A CONVENIENCE.** `BR-CUS-1022` makes the Tax ID the
    thing a company IS identified by, and without this leg a business could be
    matched by the machine and never FOUND by a person — the number on the
    letter in their hand would be the one field the search could not read.
    Exact, like the phone: both are equality probes over an HMAC, so half a
    number finds nobody. That is a property of the encryption rather than a bug
    in the box.
    """
    qs = customer_queryset()
    term = (params.q or "").strip()
    if len(term) >= MIN_SEARCH_CHARS:
        matches = Q(customer_no__icontains=term)
        matches |= Q(external_ref__icontains=term)
        matches |= Q(display_name__icontains=term)
        tokens = crypto.blind_index_candidates(term, context=identity_match.CRYPTO_CONTEXT["phone"])
        if tokens:
            matches |= Q(phone_bidx__in=tokens)
        tax_tokens = crypto.blind_index_candidates(
            term, context=identity_match.CRYPTO_CONTEXT["tax_id"]
        )
        if tax_tokens:
            matches |= Q(tax_id_bidx__in=tax_tokens)
        qs = qs.filter(matches)

    kind = params.filters.get("kind")
    if kind in ("person", "company"):
        qs = qs.filter(kind=kind)

    sort = params.sort if params.sort in CUSTOMER_SORTS else CUSTOMER_DEFAULT_SORT
    prefix = "-" if params.dir == "desc" else ""
    # IS-2 — a stable secondary key, so page 2 cannot repeat a row from page 1
    # when two customers share a name.
    return qs.order_by(f"{prefix}{sort}", "id")


def customer_page(params: ListParams) -> tuple[list[dict[str, Any]], int]:
    """THE `GET /customers` read: `(one page of rows, the whole set's count)`.

    ⚠ **`NFR-3`, AND IT IS `account_page`'S SHAPE ON PURPOSE.** That function's
    own docstring names the breach this one closes — *"40,000 accounts built to
    draw fifty"* — and the customers list was the same breach one screen over:
    `_paginated` sliced a Python list, so a landlord-heavy utility built every
    customer row, and every row cost its own query for that person's accounts.
    Measured on this suite's fixtures: **5 statements for 4 customers and 17 for
    16** before — one per person — and **61 to draw fifty rows out of sixty**.
    `test_def_cus_5753_customers_list_pages_in_sql.py` holds the after.

    The count is a `COUNT(*)` over the same queryset, so a clerk on page 1 of
    40,000 people is told there are 40,000 without 40,000 rows being built.
    `NFR-5` is honoured by there being no cap of any kind here: `per` clamps to
    the IS-2 page-size vocabulary and `page` is re-clamped by `_prepaged`
    (`BR-SHL-011`), and neither ever refuses a row that exists.

    ⚠ **THERE IS NO DERIVED-FIGURE FALLBACK AND NONE IS OWED.** `account_page`
    keeps an `O(tenant)` path because two of its sorts and two of its filters
    are over money that lives in the ledger. Every `CUSTOMER_SORTS` name and the
    one `CUSTOMER_FILTERS` name is a COLUMN on `customers`, so this list has no
    such case: it is `O(page)` for every request that can be made of it.
    """
    qs = customer_list_queryset(params)
    total = qs.count()
    start = max(params.page - 1, 0) * params.per
    return customer_rows(list(qs[start : start + params.per])), total


def customer_list(params: ListParams) -> list[dict[str, Any]]:
    """EVERY matching customer row, ordered — the stable API.

    ⚠ **PREFER `customer_page`.** This is `O(tenant)` by construction and the
    endpoint no longer calls it; it stays because a dozen cases and
    `customer_edit`'s own read-back use this shape, and because a search that
    returns everything it matched is the right answer to ask a selector for.
    """
    return customer_rows(list(customer_list_queryset(params)))


def customer_rows(customers: list[models.Customer]) -> list[dict[str, Any]]:
    """One page of customer rows, with the page-wide read resolved ONCE.

    ⚠ **THIS IS `account_rows`' SHAPE AND IT IS HERE FOR `DEF-2723`'S REASON.**
    Each row names every account that person holds, and `customer_row` asked for
    them PER ROW — one `customer_accounts` query per customer, so a page of
    fifty landlords cost fifty-one statements and a whole tenant cost one per
    customer in it. The answer for the WHOLE page is resolved here instead, and
    a row asked on its own (`customer_detail`) still resolves its own.
    """
    links = _customer_account_links(customers)
    emails = _customer_emails(links)
    reach = _customer_contact_by(links)
    # ⊕ PO 2026-10-22 — whether *Edit customer* offers the sign-in tick box;
    # one query for the page (`portal_seam.customers_with_portal_login`).
    logins = portal_seam.customers_with_portal_login(_tenant_id(), [row.id for row in customers])
    return [
        customer_row(
            row,
            links=links.get(str(row.id), []),
            email=emails.get(str(row.id)),
            contact_by=reach.get(str(row.id)),
            has_portal_login=str(row.id) in logins,
        )
        for row in customers
    ]


def _customer_contact_by(links: dict[str, list[models.CustomerAccount]]) -> dict[str, str]:
    """⊕ `DEF-CUS-10253` — *Contact by* for a page of customers, in ONE query:
    the primary contact's on the first account each holds now, exactly as
    `_customer_emails` picks the email (the Edit customer dialog pre-fills it)."""
    live: dict[str, list[str]] = {
        customer_id: [
            str(link.account_id) for link in rows if getattr(link, "ended_at", None) is None
        ]
        for customer_id, rows in links.items()
    }
    account_ids = sorted({account_id for ids in live.values() for account_id in ids})
    if not account_ids:
        return {}
    by_account: dict[str, str] = {}
    for account_id, contact_by in (
        models.Contact.objects.filter(
            tenant_id=_tenant_id(),
            account_id__in=account_ids,
            deleted_at__isnull=True,
            is_primary=True,
        )
        .exclude(contact_by__isnull=True)
        .exclude(contact_by="")
        .order_by("created_at", "id")
        .values_list("account_id", "contact_by")
    ):
        by_account.setdefault(str(account_id), str(contact_by))
    out: dict[str, str] = {}
    for customer_id, ids in live.items():
        for account_id in ids:
            if account_id in by_account:
                out[customer_id] = by_account[account_id]
                break
    return out


def _customer_emails(links: dict[str, list[models.CustomerAccount]]) -> dict[str, str]:
    """**How to reach each person, for a page of them, in ONE query** — T1,
    `DEF-CUS-6386`.

    The transfer's buyer search draws an EMAIL column (PO 2026-09-23, *"this si
    correct"* on Customer # · Name · Person or company · Email · Phone ·
    Accounts held). `customers` holds no email: a person's email lives on the
    `contacts` row of an account they hold (`BR-CUS-045`, keyed to the ACCOUNT).
    So the email served is the PRIMARY contact's on the first account the
    person holds NOW (a live link, `DEF-CUS-6046`'s reader), in account-number
    order — the account the list already prints first.

    Served whole and MASKED on screen (`BR-CUS-045`: display masking is the
    client's half), exactly as `phone` on this row already is.
    """
    live: dict[str, list[str]] = {}
    for customer_id, rows in links.items():
        live[customer_id] = [
            str(link.account_id) for link in rows if getattr(link, "ended_at", None) is None
        ]
    account_ids = sorted({account_id for ids in live.values() for account_id in ids})
    if not account_ids:
        return {}
    by_account: dict[str, str] = {}
    for account_id, email in (
        models.Contact.objects.filter(
            tenant_id=_tenant_id(),
            account_id__in=account_ids,
            deleted_at__isnull=True,
            is_primary=True,
        )
        .exclude(email__isnull=True)
        .exclude(email="")
        .order_by("created_at", "id")
        .values_list("account_id", "email")
    ):
        by_account.setdefault(str(account_id), str(email))
    out: dict[str, str] = {}
    for customer_id, ids in live.items():
        for account_id in ids:
            if account_id in by_account:
                out[customer_id] = by_account[account_id]
                break
    return out


def _customer_account_links(
    customers: list[models.Customer],
) -> dict[str, list[models.CustomerAccount]]:
    """Every link for a whole page of customers, in ONE query, grouped by person.

    Ordered by `account__account_no` exactly as the per-row read was, so the
    accounts under a customer arrive in the same order they always have — a
    batched read that reorders a cell is a speed-up wearing a regression's
    clothes, and a statement count cannot see it.

    Hard rule 1: the tenant predicate is the session's, which is the same tenant
    `customer_queryset` filtered these rows out of.
    """
    ids = [customer.id for customer in customers]
    if not ids:
        return {}
    grouped: dict[str, list[models.CustomerAccount]] = {}
    links = (
        models.CustomerAccount.objects.filter(tenant_id=_tenant_id(), customer_id__in=ids)
        .select_related("account", "account__status")
        .order_by("account__account_no")
    )
    for link in links:
        grouped.setdefault(str(link.customer_id), []).append(link)
    return grouped


def customer_row(
    customer: models.Customer,
    *,
    links: list[models.CustomerAccount] | None = None,
    email: str | None = None,
    contact_by: str | None = None,
    has_portal_login: bool | None = None,
) -> dict[str, Any]:
    """One person, as the list draws them.

    ⚠ **`links` IS THE PAGE-WIDE READ, RESOLVED ONCE BY THE CALLER** — the
    same idea every keyword on `account_row` carries, and here for the same
    reason (`DEF-CUS-5753`): asked on its own this row costs one
    `customer_accounts` query, and a list that let every row ask cost one PER
    PERSON. `customer_rows` resolves them for the whole page;
    `customer_detail` asks for one row and still resolves its own.

    ⚠ **NO FULL IDENTIFIER, EVER — BR-CUS-092(c)**: *"every read path renders
    last four only and the full value is never in a list response, an export, a
    log line or an audit `details` blob"*. The list serves whether an identifier
    is HELD and its last four; the digits before them are never sent to a
    browser at all.

    ⚠ **NO DATABASE ID IS A VISIBLE VALUE — B14 rule 31.** `id` is here as a
    machine handle for the row link; `customer_no` is the thing a screen prints.
    """
    accounts = (
        list(
            models.CustomerAccount.objects.filter(tenant_id=customer.tenant_id, customer=customer)
            .select_related("account", "account__status")
            .order_by("account__account_no")
        )
        if links is None
        else links
    )
    return {
        "id": str(customer.id),
        "customer_no": customer.customer_no,
        "display_name": customer.display_name,
        "kind": customer.kind,
        "external_ref": customer.external_ref,
        "phone": customer.phone,
        # CR-161-BRC10 W4 — the utility's own customer answers. On the ROW
        # because the Customer edit dialog opens from the Customers list and
        # pre-fills from the row it was opened on; no extra query (a column).
        "custom_data": dict(customer.custom_data or {}),
        # ⊕ T1 — the primary contact's email on the first account held now
        # (`_customer_emails`). NULL on a single-row read that did not ask.
        "email": email,
        # ⊕ DEF-CUS-10253 — *Contact by*, the same account's primary contact.
        "contact_by": contact_by,
        # ⊕ PO 2026-10-22 — a portal login that can sign in. A single-row read
        # asks its own one query; the page read resolves the whole page once.
        "has_portal_login": (
            bool(
                portal_seam.customers_with_portal_login(customer.tenant_id, [customer.id])
            )
            if has_portal_login is None
            else has_portal_login
        ),
        # `held` and `last4` are different facts and a screen needs both: *no
        # licence on file* and *licence ••••4417* read nothing alike.
        "identity": {
            "date_of_birth": (
                customer.date_of_birth.isoformat() if customer.date_of_birth else None
            ),
            "ssn_held": bool(customer.ssn),
            "ssn_last4": crypto.last_four(customer.ssn) if customer.ssn else None,
            "driving_licence_held": bool(customer.driving_licence),
            "driving_licence_last4": (
                crypto.last_four(customer.driving_licence) if customer.driving_licence else None
            ),
            # CR-056 W2b — the COMPANY half. `BR-CUS-1022`: a company is
            # identified by its Tax ID, and until this shipped a company row
            # read *"nothing on file"* however completely it was identified.
            # Last four only, like its two siblings and for the same reason.
            "tax_id_held": bool(customer.tax_id),
            "tax_id_last4": crypto.last_four(customer.tax_id) if customer.tax_id else None,
        },
        "account_count": len(accounts),
        "accounts": [
            {
                "id": str(link.account_id),
                "account_no": link.account.account_no,
                "kind": link.account.kind,
                "status_code": link.account.status.code if link.account.status_id else None,
                "status_name": link.account.status.name if link.account.status_id else None,
                # BR-CUS-089 — how this link came to be made, and by whom. NULL
                # on every link an import wrote, which is the honest state: a
                # legacy reference is a reconciliation key, not identity.
                "match_tier": link.match_tier,
                "match_basis": link.match_basis,
            }
            for link in accounts
        ],
    }


def customer_detail(customer_id: Any) -> dict[str, Any] | None:
    """One person and the accounts linked to them. `None` outside the tenant.

    404-never-403 is the CALLER's job (`errors.deny_as_not_found`); this answers
    `None` for an id this tenant does not hold, which is the same fact from
    here (HR-1/G4).
    """
    if not _is_uuid(customer_id):
        return None
    customer = customer_queryset().filter(pk=customer_id).first()
    return customer_row(customer) if customer is not None else None


#: **CR-060 C16 — the tiers a link may carry, and what each one means for
#: MONEY.** `BR-CUS-089` stores the tier a human committed at the door; an
#: import link carries **NULL** on purpose, because the bulk import matches on
#: `external_ref` — the legacy system's id, a reconciliation key and not
#: identity evidence (see `models.CustomerAccount`). C16 amends `BR-CUS-054`
#: with the money reading of that: *"a weak or untiered link is shown and
#: MARKED, never silently merged and never silently dropped — the tier already
#: refuses to carry a deposit, and a statement should be no braver than that."*
STATEMENT_CONFIDENT_TIERS: tuple[str, ...] = ("strong", "probable")


def customer_statement(customer_id: Any) -> dict[str, Any] | None:
    """**ONE CUSTOMER, THEIR ACCOUNTS, EACH BALANCE, AND A TOTAL ACROSS THEM.**

    `CR-060` **C16**, task **T17**. The change request's own summary of the
    build: *"ZERO SCHEMA. The link table already carries the pair, the
    confidence tier and the confirmer. The customer statement is a read over a
    table that has been ready the whole time."*

    ══════════════════════════════════════════════════════════════════════════
    THE FOUR MONEY RULES, WHICH ARE C16's AMENDMENT TO `BR-CUS-054`
    ══════════════════════════════════════════════════════════════════════════
    **1 · SUM WITHIN A CUSTOMER, NEVER ACROSS.** There is exactly one customer
    id in this function and it is the argument. `customer_accounts` is N:M, so
    the temptation is a group-by that walks from account back out to every other
    holder — and that would put a stranger's arrears on this person's statement.
    The account set is `links.filter(customer=this one)` and nothing widens it.

    **2 · A JOINTLY-HELD ACCOUNT APPEARS AT FULL VALUE ON BOTH HOLDERS'
    STATEMENTS**, which is joint and several liability correctly presented — and
    it is the reason this read does NOT apportion. Two people holding one
    account each owe the whole of it; halving it would tell each of them they
    owe less than they do. The row carries `held_with`, the OTHER holders'
    display names, so a reader can see why the same figure appears twice.

    **3 · A WEAK OR UNTIERED LINK IS SHOWN AND MARKED.** Never silently merged
    into the total and never silently dropped — both are lies of a different
    shape. `confident` is False on such a row, it is EXCLUDED from `total`, and
    `unconfident_total` states what was left out so the screen can say so with a
    figure rather than an adjective. **The precedent is not invented here:** the
    tier already refuses to carry a deposit forward (`BR-CUS-089` /
    `discounts._stored_match`), and a statement should be no braver than that.

    **4 · A CUSTOMER WITH NO LIVE ACCOUNT GETS AN EMPTY STATEMENT, NOT AN
    ERROR.** `rows` is empty, `total` is `"0.000000"`, and `account_count` is 0.
    That is a derived answer about a real person.

    ══════════════════════════════════════════════════════════════════════════
    WHAT IT DOES NOT DO
    ══════════════════════════════════════════════════════════════════════════
    **It recomputes no money.** Every per-account figure is the LEDGER's own Σ
    over posted journal lines, asked ONCE for the whole set through
    `seams.ar_positions` (B1: customers touches no other module's ORM) — the
    same derivation `ar_control` publishes as the AR tie-out and `revenue_and_ar`
    publishes as *Still owed*. The account row, the finance KPI and this
    statement are one derivation grouped three ways and cannot disagree.

    **AN ABSENCE IS NOT A ZERO, AND THE TOTAL REFUSES RATHER THAN GUESSING**
    (DEF-127). When the books cannot be asked — the ledger publishes no read,
    the tenant has designated no AR account, or DEF-081's mixed book — every
    `balance` is `None`, `total` is `None`, and `unavailable` carries the
    ledger's own reason. A statement footing 0.00 over books nobody could read
    is the exact defect that told a customer owing 108.88 they owed nothing.

    ⚠ **NO DATABASE ID IS A VISIBLE VALUE (B14 rule 31).** `id` travels as a
    machine handle for the row link; `account_no` and `customer_no` are what a
    screen prints.

    `None` for an id this tenant does not hold — 404-never-403 is the caller's
    job (HR-1/G4), and from in here the two are the same fact.
    """
    if not _is_uuid(customer_id):
        return None
    customer = customer_queryset().filter(pk=customer_id).first()
    if customer is None:
        return None

    links = list(
        models.CustomerAccount.objects.filter(
            tenant_id=_tenant_id(), customer_id=customer.id
        )
        .select_related("account", "account__status")
        .order_by("account__account_no")
    )
    account_ids = [str(link.account_id) for link in links]

    # RULE 2's evidence, and it is a SECOND query rather than a join because the
    # question is about the OTHER holders of these same accounts. It never
    # widens the account set — it only names who else is on the ones already
    # here — so rule 1 is not at risk from it.
    others: dict[str, list[str]] = {}
    if account_ids:
        for other_account_id, name in (
            models.CustomerAccount.objects.filter(
                tenant_id=_tenant_id(), account_id__in=account_ids
            )
            .exclude(customer_id=customer.id)
            .select_related("customer")
            .order_by("customer__display_name")
            .values_list("account_id", "customer__display_name")
        ):
            others.setdefault(str(other_account_id), []).append(name)

    # ONE seam call for the whole statement — a per-row call is a query per
    # account, which is the shape `account_list`'s DEF-127 comment forbids.
    positions = _ar_positions_for(account_ids) if account_ids else _ar_positions_for([])

    rows: list[dict[str, Any]] = []
    total = Decimal("0")
    unconfident = Decimal("0")
    for link in links:
        amount = positions.amount_for(link.account_id)
        confident = link.match_tier in STATEMENT_CONFIDENT_TIERS
        if amount is not None:
            if confident:
                total += amount
            else:
                unconfident += amount
        rows.append(
            {
                "id": str(link.account_id),
                "account_no": link.account.account_no,
                "kind": link.account.kind,
                "status_code": link.account.status.code if link.account.status_id else None,
                "status_name": link.account.status.name if link.account.status_id else None,
                "balance": _money(amount),
                # BR-CUS-089's tier, and the ONE thing it decides here.
                "match_tier": link.match_tier,
                "confident": confident,
                # Rule 2 made visible: WHY this figure also appears on somebody
                # else's statement, at its full value.
                "held_with": others.get(str(link.account_id), []),
            }
        )

    available = positions.available
    return {
        "basis": positions.basis,
        # DEF-099 / CLAUDE.md rule 2 — the CHAR(3) the ledger DERIVED from the
        # entries it summed, never a label applied here.
        "currency": positions.currency,
        "customer": {
            "id": str(customer.id),
            "customer_no": customer.customer_no,
            "display_name": customer.display_name,
            "kind": customer.kind,
        },
        "account_count": len(rows),
        "rows": rows,
        # RULE 3 — the confident sum, and what was deliberately left out of it.
        "total": _money(total) if available else None,
        "unconfident_total": _money(unconfident) if available else None,
        "unconfident_count": sum(1 for row in rows if not row["confident"]),
        "available": available,
        "unavailable": tuple(positions.unavailable),
    }


def customer_nos_for(account_ids: list[Any]) -> dict[str, str | None]:
    """CR-030 W2 T2.9(b) — OUR customer number for a whole PAGE of accounts.

    **BR-CUS-053 (AMENDED 2026-08-24, PO ruling), verbatim on this half:**
    *"(b) the list renders `CUSTOMER #` as a column, available through the
    shared column selector."* The stored column is `customers.customer_no`
    (CR-030 W0, migrations `0013_cr030_w0_customer_no` +
    `0014_cr030_w0_backfill_customer_no`).

    ⚠ **ONE QUERY FOR THE PAGE, AND THAT IS THE WHOLE REASON THIS FUNCTION
    EXISTS RATHER THAN A `customer_for_account` CALL PER ROW.** `account_list`
    serializes EVERY matching account before the paginator slices, so a per-row
    lookup is one query per ACCOUNT on the product's busiest screen — which is
    the shape the DEF-127 comment in `account_list` forbids for the ledger and
    billing reads, for exactly the same reason. The join to `customers` rides
    inside the same `values_list`.

    ⚠ **THE FIRST LINK WINS, BECAUSE THE DETAIL SCREEN ALREADY SAYS SO.**
    `customer_accounts` is N:M (BR-CUS-054: a jointly-held account has more than
    one holder), and `customer_for_account` below resolves the earliest link by
    `created_at`. This orders and de-duplicates the same way, so the `CUSTOMER #`
    cell on S17 and the customer chip on S21 can never name two different
    people for one account. A joint holder's OWN number is still findable — the
    SEARCH leg (`_account_ids_by_customer_no`) matches EVERY link, not the
    first — so a clerk typing the second holder's number still gets the row.

    An account with no link at all is simply absent from the map, which the
    caller reads as `None`: that is a real answer and not a gap — every account
    created before the entity existed has no link (see `customer_for_account`).
    """
    if not account_ids:
        return {}
    rows = (
        models.CustomerAccount.objects.filter(
            tenant_id=_tenant_id(), account_id__in=list(account_ids)
        )
        .order_by("account_id", "created_at")
        .values_list("account_id", "customer__customer_no")
    )
    numbers: dict[str, str | None] = {}
    for account_id, customer_no in rows:
        numbers.setdefault(str(account_id), customer_no)
    return numbers


def customer_for_account(account_id: Any) -> dict[str, Any] | None:
    """The customer an account belongs to, or None.

    None is a real answer, not a gap: every account created before the
    BR-CUS-054 entity existed has no link, and so does any account whose
    import row carried neither a `customer_ref` nor a name."""
    # ⚠ **`ended_at__isnull=True` IS LOAD-BEARING, NOT DEFENSIVE (0060).**
    # A property sale now ENDS the seller's link rather than deleting it, so
    # this table holds former owners too — and this query takes the OLDEST
    # row, which after a sale is the SELLER's. Without this clause every
    # account that has ever changed hands reports its PREVIOUS owner as its
    # customer, on every screen that asks.
    #
    # ⚠ **MEASURED, NOT ASSUMED:** adding the column without this clause took
    # the property-sale suite from **23 of 25 rows with nothing red to 5 of
    # 25** in one run — `account_customer_is_the_buyer: want True, saw False`
    # on nineteen scenarios. That is the whole reason `CustomerAccount.objects`
    # was left UNFILTERED and callers were made to say `live()` instead: a
    # filtered default manager would have hidden this regression AND hidden
    # the ended row from the one suite check the column exists to satisfy.
    link = (
        models.CustomerAccount.objects.filter(
            tenant_id=_tenant_id(), account_id=account_id, ended_at__isnull=True
        )
        .select_related("customer")
        .order_by("created_at")
        .first()
    )
    if link is None:
        return None
    # CR-161-BRC10 W4 — the customer's own fields ride HERE, on the account's
    # customer, because the Account detail header is where they are shown
    # (`custom_fields.SLOTS` customers · S21). There is no customer page.
    customer = link.customer
    return {
        **customer_dict(customer),
        "custom_data": dict(customer.custom_data or {}),
        # ⊕ `DEF-CUS-10054` (PO 2026-10-11) — the account's Customer section
        # shows SSN and Driver's license masked to the last four. LAST FOUR
        # ONLY, projected here (BR-CUS-092(c)); the full number never leaves
        # the server, exactly as `customer_row`'s `identity` block.
        "identity": {
            "ssn_last4": crypto.last_four(customer.ssn) if customer.ssn else None,
            "driving_licence_last4": (
                crypto.last_four(customer.driving_licence) if customer.driving_licence else None
            ),
            "tax_id_last4": crypto.last_four(customer.tax_id) if customer.tax_id else None,
        },
    }


def primary_customer_id_for_account(account_id: Any) -> str | None:
    """WHO IS BILLED for this account — `P0.2` / `P0.3`, published for the
    ledger's posting-time stamp.

    **AN ID AND NOTHING ELSE, DELIBERATELY**, for the same reason
    `customer_exists` below is a bare boolean: the caller is stamping a foreign
    key onto an immutable journal line, not rendering a person, and handing it a
    payload would invite it to start displaying fields this module owns.

    **THE ORDER OF PREFERENCE IS THE WHOLE RULE:**

      1. the LIVE link marked `is_primary` — `P0.2`'s nomination, which a human
         made and which `uq_customer_accounts_primary_live` guarantees there is
         at most one of;
      2. failing that, the OLDEST live link — exactly what
         `customer_for_account` above has always returned, so a singly-held
         account answers identically under both reads and nothing moves for the
         54 of 54 links `customers/0070` nominated;
      3. `None`.

    ⚠ **STEP 2 IS A FALLBACK AND NOT A GUESS, AND THE DIFFERENCE IS THAT IT
    CANNOT PICK THE WRONG PERSON.** It is reached only when no link is
    nominated, and `customers/0070` nominates every singly-held account — so
    what is left is a JOINTLY held account with nobody named. There, taking the
    oldest link is the reading this product has made everywhere else since
    `BR-CUS-054`, and changing it here alone would make the journal disagree
    with every screen. Whether a human must nominate one is `OQ-LED-12629`'s
    neighbourhood; this read does not answer it and does not pretend to.

    ⚠ **`ended_at IS NULL` ON BOTH BRANCHES.** A property sale ENDS the seller's
    link rather than deleting it (`BR-CUS-1030`, `0060`), so this table holds
    former owners; without the clause, every account that has ever changed hands
    would stamp its PREVIOUS owner onto today's money — permanently, because a
    posted line is immutable. The measurement behind that is recorded on
    `customer_for_account` above.

    **`None` IS A REAL ANSWER.** An account created before the `BR-CUS-054`
    entity existed has no link at all, and a line stamped `None` is honest about
    it. Tenant-scoped (hard rule 1).
    """
    links = models.CustomerAccount.objects.filter(
        tenant_id=_tenant_id(), account_id=account_id, ended_at__isnull=True
    )
    nominated = links.filter(is_primary=True).values_list("customer_id", flat=True).first()
    if nominated is not None:
        return str(nominated)
    oldest = links.order_by("created_at").values_list("customer_id", flat=True).first()
    return str(oldest) if oldest is not None else None


def customer_exists(customer_id: Any) -> bool:
    """Does this tenant hold this customer? — the metering seam's probe.

    ⚠ **AUTHORED HERE, BY THE OWNING MODULE, BECAUSE THAT IS WHAT THE SEAM
    CONTRACT ASKS FOR** (B1/B8: metering never touches this module's ORM).
    CR-039 wave C task 12 gives `premises_owners` an OPTIONAL link to *"the
    customer they already are"* (PO 2026-08-27) and metering has to validate
    that id without reading `customers`. `apps.metering.premises_owners`
    late-binds this function through `apps.metering.seams`.

    **A BOOLEAN AND NOTHING ELSE, DELIBERATELY.** The caller is answering *"is
    this a real id?"*, not rendering a customer — returning a dict here would
    hand metering a payload it has no rule about and invite it to start
    displaying fields this module owns. The premises-owner screen fetches the
    name through the ordinary customer read when it needs it.

    A cross-tenant id answers **False**, not an error, for the same reason
    `account_or_404` denies as not-found: from outside the tenant, an id that
    exists elsewhere and an id that does not exist are the same fact (HR-1/G4).
    """
    if not _is_uuid(customer_id):
        return False
    return models.Customer.objects.filter(tenant_id=_tenant_id(), pk=customer_id).exists()


def account_or_404(account_id: Any, *, lock: bool = False) -> models.Account:
    """Cross-tenant ids are indistinguishable from absent ones (HR-1 / G4).

    `lock=True` locks the account row and only it — `FOR UPDATE OF accounts`,
    for the same reason `occupying_accounts_for_unit` does."""
    if not _is_uuid(account_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    if lock:
        qs = models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id).select_for_update(
            of=("self",)
        )
    else:
        qs = account_queryset().filter(pk=account_id)
    row = qs.first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def account_detail(account_id: Any) -> dict[str, Any]:
    account = account_or_404(account_id)
    body = account_detail_dict(account)
    # CR-185-BRC10 — a closed account's tie-back to the owner: pending until
    # its final bill is sent, then posted. None when nobody tied it back. Only
    # a CLOSED account can carry one, so an open account costs no extra read.
    body["balance_to_owner"] = None
    if account.closed_at is not None:
        from apps.customers import move_out_settlement

        body["balance_to_owner"] = move_out_settlement.balance_to_owner_for(account)
    return body


# ── S17 list + header roll-up ───────────────────────────────────────────────
def account_list_queryset(params: ListParams) -> QuerySet:
    """US-CUS-001/002: the BR-CUS-053 capability row, as a LAZY queryset.

    Search covers account #, **customer #**, customer name, service address and
    meter #; the last two are metering/assets columns and are reached through
    their owning modules' selectors (B1).

    ⚠ **THE SEARCH SET IS FIVE, NOT FOUR, SINCE 2026-08-24 — BR-CUS-053 AMENDED
    BY PO RULING**, asked as a question about work they expected to be done:
    *"we were suppose to add customer # comlume what happened to that"*. The
    rule's own words for this half: *"(a) `selectors.account_list` MATCHES
    `customer_no` … joined into the same OR as `account_no`, so one box finds a
    person by either number."* That is why the clause below sits inside
    `matches` rather than filtering separately: a clerk holding a scrap of paper
    does not know whether the digits on it are ours for the ACCOUNT or ours for
    the CUSTOMER, and two search boxes would make them decide.

    ⚠ **THIS FUNCTION WAS THE FIRST HALF OF `account_list` UNTIL 2026-09-12
    (`BR-CUS-1046` / `DEF-CUS-5060`).** It is split out so the ORDER BY and the
    page can both be taken in the database — see `account_page`. Nothing about
    the search or the filters moved; every clause below is where it was, with
    its own note, and the two DERIVED filters stay where they were too, in
    `account_list`, because they can only be applied to a built row.
    """
    qs = account_queryset()
    term = (params.q or "").strip()
    if len(term) >= MIN_SEARCH_CHARS:
        unit_ids = set(seams.unit_ids_matching(term)) | set(seams.unit_ids_for_asset_search(term))
        matches = Q(account_no__icontains=term)
        # BR-CUS-053(a) — the SAME OR-group, which is the rule's own word for
        # it. `MIN_SEARCH_CHARS` gates this leg with the others: a one-character
        # `C` would otherwise return every customer in the tenant.
        matches |= Q(id__in=_account_ids_by_customer_no(term))
        matches |= Q(id__in=_account_ids_by_contact_name(term))
        # `CR-089` `PUJ-51` — the ADDRESS, reaching the accounts the unit leg
        # below cannot: `BR-CUS-1010`'s owner account names no unit, so *500
        # Main St* found five of the six accounts at that building and dropped
        # the one that owns it. Lazy, so this costs no extra round trip — see
        # `account_ids_at_matching_address`.
        matches |= Q(id__in=account_ids_at_matching_address(term))
        if unit_ids:
            matches |= Q(unit_id__in=list(unit_ids))
        qs = qs.filter(matches)

    status = params.filters.get("status")
    if status and status.lower() != "all":
        qs = qs.filter(status__code__iexact=status)
    category = params.filters.get("category")  # BR-CUS-053 "category" = account type
    if category:
        qs = qs.filter(account_type__code__iexact=category)
    autopay = params.filters.get("autopay")
    if autopay is not None and str(autopay).lower() in ("true", "false", "1", "0", "on", "off"):
        qs = qs.filter(autopay=str(autopay).lower() in ("true", "1", "on"))
    unit_id = params.filters.get("unit_id")
    if unit_id and _is_uuid(unit_id):
        qs = qs.filter(unit_id=unit_id)
    # `CR-056` W1 — find an account by its ADDRESS. Without this the only way to
    # reach a premises' accounts is `f.unit_id=` once per unit (`DEF-473`'s own
    # note on PRM-02), and the owner's account has no unit to be found by at all.
    premises_id = params.filters.get("premises_id")
    if premises_id and _is_uuid(premises_id):
        qs = qs.filter(premises_id=premises_id)
    kind = params.filters.get("kind")  # BR-CUS-068: regular | master
    if kind in ("regular", "master"):
        qs = qs.filter(kind=kind)
    # `DEF-CUS-10181` — the AGEING segment, in SQL. The anchor is annotated only
    # when the request filters or sorts on it: the default path pays nothing.
    # An unrecognised segment does not filter at all (BR-SHL-011: never 4xx).
    segment = normalize_ageing_segment(params.filters.get(AGEING_FILTER))
    if segment is not None or params.sort == "ageing":
        as_of = seams.tenant_today()
        qs = annotate_ageing(qs, as_of)
        if segment is not None:
            qs = qs.filter(ageing_band_q(segment, as_of))
    return _account_ordered(qs, params)


def _primary_contact_name_subquery() -> Any:
    """The Name cell's value as a CORRELATED SUBQUERY, for the ORDER BY only.

    ⚠ **IT IS `primary_contact_names_for`'s RULE, EXPRESSED IN SQL — NOT A
    SECOND RULE.** That helper decides WHICH contact is "the" name when an
    account has several, with `-is_primary, created_at, id` and first-one-wins,
    and its own docstring says a batched read that sorted differently *"would
    quietly rename customers on the list while their detail page kept the old
    name — a regression no statement count can see"*. The same three terms and
    the same `[:1]` are here for exactly that reason. If one moves, both move.

    ⚠ **`Lower` AND `Coalesce` ARE NOT TIDINESS, THEY ARE BACKEND PARITY.** The
    Python sort this replaces keyed on `(row.get("name") or "").lower()` — null
    becomes the empty string and case is folded. PostgreSQL's `en_US.UTF-8`
    collation folds case anyway and SQLite's does not, and NULL sorts at
    opposite ends of the two backends. `config/settings/test.py` hardcodes
    SQLite (hard-won law 14), so an expression that relied on the database's
    own defaults would order one way in the suite and another way in front of a
    clerk, and the suite would be green. Folding and coalescing HERE makes the
    ordering the same on both, and the same as the Python it replaces.
    """
    from django.db.models import OuterRef, Subquery, TextField, Value
    from django.db.models.functions import Coalesce, Lower

    # `DEF-CUS-9776` — the customer's name first, as `primary_contact_name`.
    customer_name = Subquery(
        models.CustomerAccount.objects.filter(
            tenant_id=_tenant_id(),
            account_id=OuterRef("pk"),
            ended_at__isnull=True,
        )
        .exclude(customer__display_name="")
        .order_by(*CUSTOMER_NAME_ORDER)
        .values("customer__display_name")[:1]
    )
    return Lower(
        Coalesce(
            customer_name,
            Subquery(
                models.Contact.objects.filter(
                    tenant_id=_tenant_id(),
                    account_id=OuterRef("pk"),
                    deleted_at__isnull=True,
                )
                .order_by("-is_primary", "created_at", "id")
                .values("full_name")[:1]
            ),
            Value(""),
            # contacts.full_name is a CharField and display_name a TextField.
            output_field=TextField(),
        )
    )


#: `services.PENDING_STATUS_CODE`, restated because selectors cannot import
#: services; `test_def_cus_10180_*` asserts the two are equal.
ACCOUNT_AGE_NOT_OPENED_STATUS = "pending_activation"


def _account_age_key() -> Any:
    """The Account age sort key — `opened_at`, and NULL for an account pending
    activation even when a move-in date is already typed on it. PO rule 5:
    *"Pending activation → 'Not opened'"* — the screen draws no age for it, so
    the sort must not rank it by one either; it goes last both ways."""
    from django.db.models import Case, DateField, F, Value, When

    return Case(
        When(status__code=ACCOUNT_AGE_NOT_OPENED_STATUS, then=Value(None)),
        default=F("opened_at"),
        output_field=DateField(),
    )


def _account_ordered(qs: QuerySet, params: ListParams) -> QuerySet:
    """The list's ORDER BY — one place, for both the SQL path and the fallback.

    ⚠ **A DERIVED SORT STILL GETS A TOTAL ORDER HERE, AND IT MATTERS.** When the
    clerk asks for `balance` or `last_bill` the Python sort in `account_list`
    decides the answer, and this ordering is only the order rows are fetched in
    — but `list.sort()` is STABLE, so rows that tie on a derived figure keep
    whatever order they arrived in. Fetching them in a defined order is what
    stops two accounts with identical balances swapping places between one
    request and the next.
    """
    from django.db.models import F
    from django.db.models.functions import Lower

    sort = params.sort or ACCOUNT_DEFAULT_SORT
    # ⚠ **`ListParams.dir` DEFAULTS TO `asc`, SO "NOBODY CHOSE" MUST BE READ FROM
    # `sort`, NOT FROM `dir` (found by a test, 2026-09-12).** The endpoint asks
    # `parse_list_params` for `default_dir` and gets `desc`, but a selector can
    # be called by a job, a report or a test with a bare `ListParams()` — and
    # that carries `dir="asc"`, which flips `created` to OLDEST first. A list
    # that opens newest-first through the API and oldest-first through every
    # other caller is `BR-CUS-1046` half-built.
    #
    # `sort is None` is the one signal that survives both layers: it means no
    # sort was chosen, so the DEFAULT PAIR applies — the same rule
    # `parse_list_params` states for itself, one layer down. An explicit
    # `sort="created", dir="asc"` is still honoured, because that is a choice.
    direction = ACCOUNT_DEFAULT_DIR if params.sort is None else params.dir
    columns: dict[str, tuple[Any, ...]] = {
        # `BR-CUS-1046` — the tiebreak is the id because `created_at` is
        # `auto_now_add` and a bulk import writes many rows inside one clock
        # tick. `uuid7` ids are themselves time-ordered, so the tiebreak agrees
        # with the lead term rather than fighting it.
        #
        # ⚠ **WRITTEN ASCENDING, LIKE EVERY TERM IN THIS MAP.** `order_terms`
        # flips it and `ACCOUNT_DEFAULT_DIR` is `desc`, which is what makes the
        # untouched screen open NEWEST first. The first draft of this pass stored
        # `-created_at` here AND defaulted to `desc`; the flip cancelled the
        # minus and the list opened on the OLDEST account — the exact inversion
        # of the ruling, with every test green. It was found by curling the
        # endpoint and reading the first three rows, which is why `2d` of the
        # build process says to prove it by clicking.
        "created": ("created_at", "id"),
        "account_no": (Lower("account_no").asc(), "id"),
        "name": (_primary_contact_name_subquery().asc(), "id"),
        "status": (Lower("status__code").asc(), "id"),
        # PO 2026-10-17 (`DEF-CUS-10180`) — Account age, by Opened. Ascending is
        # the OLDEST account first; `nulls_last` survives `_flip`, so an account
        # never opened (pending activation) is last in BOTH directions.
        "account_age": (_account_age_key().asc(nulls_last=True), "id"),
        # `DEF-CUS-10181` — Aging. Ascending is the LEAST overdue first (the
        # latest anchor), so `desc` — what a clerk chasing money clicks — is
        # the oldest unpaid money first. Owing nothing is last both ways.
        "ageing": (F("ageing_anchor").desc(nulls_last=True), "id"),
        # The two derived sorts fetch in the DEFAULT order and are re-sorted in
        # Python by `account_list`. They are named here so the fetch order is
        # defined rather than arbitrary — see the docstring.
        "balance": ("created_at", "id"),
        "last_bill": ("created_at", "id"),
    }
    if sort in ACCOUNT_DERIVED_SORTS:
        # Do NOT pass the clerk's `dir` here: it belongs to the Python sort that
        # actually answers a derived figure, and flipping the FETCH order would
        # make that stable sort's tiebreak depend on the direction of the thing
        # above it. The fetch order is the screen's default, always.
        return qs.order_by(
            *order_terms(
                ACCOUNT_DEFAULT_SORT,
                ACCOUNT_DEFAULT_DIR,
                columns=columns,
                default=ACCOUNT_DEFAULT_SORT,
            )
        )
    return qs.order_by(*order_terms(sort, direction, columns=columns, default=ACCOUNT_DEFAULT_SORT))


def account_rows(accounts: list[models.Account]) -> list[dict[str, Any]]:
    """One page of S17 rows, with every page-wide read resolved ONCE.

    ⚠ **THE BATCHING BELOW IS `DEF-127`, `CR-030` W2 AND `DEF-2723`, AND IT IS
    WHY THIS IS A FUNCTION OVER A LIST RATHER THAN A LOOP OVER ROWS.** Each
    call here answers the question for EVERY account handed in; a per-row
    equivalent is a query per account on the product's busiest screen, which is
    what 562 ms for seventy-three accounts was made of.

    ⚠ **AND SINCE 2026-09-12 THE LIST HANDED IN IS ONE PAGE, NOT ONE TENANT**
    (`BR-CUS-1046` / `DEF-CUS-5060`). The comment that used to sit here said
    *"this function serializes EVERY matching account and the paginator slices
    afterwards"* — true when it was written, and the whole of the `NFR-3` breach:
    the batching kept the STATEMENT count constant while every one of those
    statements grew with the tenant. Measured at 73 accounts, asking for one row
    cost the same as asking for fifty (0.107 s against 0.102 s). `account_page`
    takes the page in SQL and hands it here.
    """
    account_ids = [account.id for account in accounts]
    positions = _balance_positions_for(account_ids)
    last_bill_dates = seams.last_issued_invoice_dates(account_ids)
    # …and ONE ageing read for the page, for the same reason — the bills AND
    # the opening position, in one statement (`DEF-CUS-10181`).
    ageing = _ageing_for(account_ids)
    # …and ONE customer-number read for the page (CR-030 W2 T2.9(b)). Same
    # reason again: `customer_for_account` is a query per account.
    customer_nos = customer_nos_for(account_ids)
    # …and the three DEF-2723 closed on 2026-09-01, for the same reason a third
    # time: the Premise cell, the Name and the Services chips were read PER
    # ACCOUNT — nine statements a row.
    contact_names = primary_contact_names_for(account_ids)
    service_codes, service_drops = service_codes_and_drops_for_accounts(accounts)
    premise_cells = premise_cells_for(accounts)
    return [
        account_row(
            account,
            positions=positions,
            last_bill_dates=last_bill_dates,
            ageing=ageing,
            customer_nos=customer_nos,
            contact_names=contact_names,
            service_codes=service_codes,
            service_drops=service_drops,
            premise_cells=premise_cells,
        )
        for account in accounts
    ]


def account_list_is_sql_pageable(params: ListParams) -> bool:
    """Can this request's page be taken in the DATABASE? (`NFR-3`)

    ⚠ **THE ANSWER IS *YES* FOR EVERY REQUEST A CLERK MAKES BY OPENING THE
    SCREEN**, and *no* only for one they make deliberately — a sort or a filter
    over a figure that lives in the ledger rather than in a column. That is the
    whole of the trade: the default path is `O(page)`, and the exception is
    `O(tenant)` and says so.

    Two things force the fallback, and each is a DERIVED figure with exactly
    one implementation that this function refuses to duplicate:
      * `sort=balance` / `sort=last_bill`  — `ACCOUNT_DERIVED_SORTS`
      * `f.balance_gt`                     — `ACCOUNT_DERIVED_FILTERS`

    ⚠ **`f.ageing=` WAS A THIRD UNTIL 2026-10-17 (`DEF-CUS-10181`).** It is a
    WHERE now — `ageing_band_q` over `ageing_anchor`, the same anchor the cell
    is drawn from — because the PO ruled that filter and sort must work for
    bill-only accounts, and a Python filter over every built row is `O(tenant)`.
    """
    if (params.sort or ACCOUNT_DEFAULT_SORT) in ACCOUNT_DERIVED_SORTS:
        return False
    return not any(
        str(params.filters.get(name, "")).strip() in ("0", "true", "1")
        for name in ACCOUNT_DERIVED_FILTERS
    )


def account_page(params: ListParams) -> tuple[list[dict[str, Any]], int]:
    """THE S17 list read: `(one page of rows, the whole result set's count)`.

    ⚠ **THIS IS `NFR-3` ON THE PRODUCT'S BUSIEST SCREEN, AND `BR-CUS-1046` IS
    WHY IT WAS FIXED NOW RATHER THAN LATER.** The rule's own words: *"it must be
    fixed WITH the ordering, not before it … fix the default and the ordering
    together, or the fix makes the breach worse and hides it behind a feature."*

    The count comes from `COUNT(*)` over the same queryset, so a clerk on page 1
    of 40,000 accounts is told there are 40,000 without 40,000 rows being built
    — which is the difference between the fifth `NFR-3` breach and its absence.
    `NFR-5` is honoured by there being no cap of any kind here: `per` clamps to
    the IS-2 page-size vocabulary and `page` clamps into range, and neither ever
    refuses a row that exists.
    """
    if not account_list_is_sql_pageable(params):
        # The derived path, unchanged from what shipped: build every matching
        # row, filter and sort on the figures, then slice. It is `O(tenant)` and
        # that is recorded in `ACCOUNT_DERIVED_SORTS` rather than hidden.
        rows = account_list(params)
        start = max(params.page - 1, 0) * params.per
        return rows[start : start + params.per], len(rows)
    qs = account_list_queryset(params)
    total = qs.count()
    start = max(params.page - 1, 0) * params.per
    return account_rows(list(qs[start : start + params.per])), total


def account_list(params: ListParams) -> list[dict[str, Any]]:
    """EVERY matching S17 row, ordered — the DERIVED path and the stable API.

    ⚠ **PREFER `account_page`.** This function is `O(tenant)` by construction:
    it exists because two sorts and two filters on this screen are over figures
    that live in the LEDGER and in BILLING rather than in a column, and a row
    has to be built before those can be read. `account_list_is_sql_pageable`
    names the four, and `account_page` calls this one only for them.

    It is also the shape a dozen tests and callers already read, so it keeps
    returning a plain ordered list of every matching row.
    """
    accounts = list(account_list_queryset(params))
    rows = account_rows(accounts)

    # CR-030 §5.1.2's segment (`?ageing=` / `f.ageing=`, TC-ACC-5) is applied in
    # SQL by `account_list_queryset` since 2026-10-17 (`DEF-CUS-10181`) — over
    # the same `ageing_anchor` the cell is drawn from, so the two cannot disagree.

    # BR-CUS-053's "balance > 0" chip. APPLIED HERE AND NOT IN SQL SINCE
    # 2026-08-15 (DEF-127): it was `qs.filter(balance__gt=0)` on the cached
    # column, which nothing writes, so the filter matched NOTHING on a tenant
    # where every account had been billed — a chip that answered "no accounts
    # owe you money" to a utility owed 261.20. The figure lives in the ledger
    # and no column holds it, so the predicate runs where the figure does; the
    # same disposition `apps/payments/outstandings.py` records for its own sort.
    # An account whose balance could not be READ is kept rather than filtered
    # out: dropping it would hide a customer behind a gap in the books.
    if str(params.filters.get("balance_gt", "")).strip() in ("0", "true", "1"):
        rows = [row for row in rows if row["balance"] is None or Decimal(row["balance"]) > 0]

    # ⚠ **ONLY THE DERIVED SORTS ARE ANSWERED HERE NOW.** `created`,
    # `account_no`, `name` and `status` are an ORDER BY (`_account_ordered`), so
    # re-sorting them in Python would be a second implementation of an ordering
    # that already has one — and the two would be free to disagree about case,
    # about nulls and about the tiebreak. The rows arrive ordered; they stay
    # that way.
    sort = params.sort or ACCOUNT_DEFAULT_SORT
    reverse = params.dir == "desc"
    if sort == "balance":
        rows.sort(key=lambda row: (Decimal(row["balance"] or 0), row["id"]), reverse=reverse)
    elif sort == "last_bill":
        # A real ordering since 2026-08-15 (DEF-127) — the values are the dates
        # billing issued, and an account never billed sorts on the empty string
        # rather than being dropped.
        rows.sort(key=lambda row: (row["last_bill_at"] or "", row["id"]), reverse=reverse)
    return rows


def _account_ids_by_customer_no(term: str) -> QuerySet:
    """BR-CUS-053(a) — *"one box finds a person by either number"*.

    ⚠ **THIS RETURNS A LAZY QUERYSET, NOT A LIST, AND THAT IS THE "ONE QUERY"
    HALF OF THE RULE.** Handed to `Q(id__in=…)` unevaluated, Django renders it
    as a nested SQL subquery inside the list's own `WHERE`, so adding the fifth
    search leg costs the request **no extra round trip at all** — the search is
    still one statement. `_account_ids_by_contact_name` below materialises its
    ids and is left exactly as it was: changing how a shipped leg executes is
    not part of adding a new one.

    ⚠ **EVERY LINK, NOT THE FIRST.** `customer_nos_for` renders the FIRST link's
    number in the cell so S17 and S21 cannot disagree; the SEARCH deliberately
    matches all of them, because on a jointly-held account (BR-CUS-054 makes the
    link N:M) the second holder's number is a perfectly good way to find the
    row, and refusing it would make the box lie about what it searches.

    `icontains` matches the posture of `account_no` beside it — `C-00417` is
    stored with its prefix and a clerk reading digits off a bill types `417`.
    The unique constraint on the column is case-insensitive for the same reason
    (`uq_customers_tenant_customer_no_ci`), so a case-sensitive search would be
    able to miss a row the schema treats as the same customer.
    """
    return models.CustomerAccount.objects.filter(
        tenant_id=_tenant_id(), customer__customer_no__icontains=term
    ).values_list("account_id", flat=True)


def account_ids_at_matching_address(term: str) -> QuerySet:
    """`CR-089` `PUJ-51`/`PUJ-52`/`PUJ-53` — THE ACCOUNTS AT AN ADDRESS.

    The PO asked for one thing in one sentence — *"you will ahve changes when
    Premises, Units, Assets, Accounts, Bills, Payments are search by address"* —
    and this is the single read all three of the list screens that were missing
    it now use: the accounts list ORs it into its own `WHERE`, and payments and
    billing resolve it BY NAME (`_resolve("customers", …)`) for theirs. One
    definition of *which accounts are at this address*, so a clerk who searches
    the same street on three screens cannot be told three different things.

    ⚠ **IT WALKS `accounts.premises_id`, NOT THE UNIT, AND THAT IS THE POINT.**
    `account_list` has had an address leg since `BR-CUS-053` — through
    `seams.unit_ids_matching`, which walks `unit → premises`. An account that
    names NO unit is invisible to it, and `BR-CUS-1010` makes exactly one of
    those per building: **the owner's Master Account is at an ADDRESS**. On the
    demo utility, *500 Main St* returned five of the six accounts standing
    there and silently dropped `AC-2026-00051`, the account that owns the
    building. `accounts.premises_id` is filled on every row — migration 0037
    backfilled the existing ones and `services` writes it from the unit at
    create — so this one column reaches both kinds.

    ⚠ **IT RETURNS A LAZY QUERYSET AND MUST STAY ONE (`NFR-3`).** Handed to
    `Q(id__in=…)` / `Q(account_id__in=…)` unevaluated, Django renders it as a
    nested subquery, so the address leg costs the request **no extra round trip
    on any of the three screens** — the discipline `_account_ids_by_customer_no`
    above records, and the reason a fifth unpaginated Python-side list is not
    being added to the four `DEF-PAY-4221` already counts. Materialising it
    would ship every account id at a matching street through Python on every
    keystroke; at the top of the customer band that is 40,000 rows in the worst
    case, not the 78 the demo utility has.

    **WHAT COUNTS AS A MATCH IS METERING'S ANSWER, NOT A SECOND ONE.**
    `seams.premises_ids_matching` calls the same `premises_list(q=…)` the
    Properties screen searches with, so *address line · town · property number ·
    owner* all reach here. That is wider than the word "address" alone and it is
    deliberate: the Properties list already searches those four "thoroughly"
    (`CR-089` §6), and a narrower predicate written here would let the Bills
    screen and the Properties screen disagree about the same building.

    An empty queryset — never every account — while metering publishes no list:
    the leg then narrows the search instead of widening it, which is what the
    unit leg beside it has always done when metering is absent.
    """
    premises_ids = seams.premises_ids_matching(term)
    if premises_ids is None:  # metering unwired — the leg narrows, never widens
        return models.Account.objects.none().values_list("id", flat=True)
    return models.Account.objects.filter(
        tenant_id=_tenant_id(), premises_id__in=premises_ids
    ).values_list("id", flat=True)


def account_ids_matching_debtor_search(term: str) -> QuerySet:
    """p035's `q` — *"account number or customer name"*, as ONE lazy queryset.

    The AR ageing's search box, published HERE because the two things it
    searches are customers' columns and `B1`/`BR-TEN-013` forbid another module
    joining them. `apps/payments/billing_seam.py` composes it into the ageing's
    own `WHERE` with `Q(account_id__in=…)`.

    ⚠ **LAZY END TO END, INCLUDING THE NAME LEG (`NFR-3`).** Both legs are
    unevaluated querysets, so the search renders as nested subqueries and adds
    **no round trip**. `_account_ids_by_contact_name` above materialises its
    ids and is deliberately left as it is — changing how a shipped leg executes
    is not part of publishing a new one — but nothing lazy may be built on top
    of something that is not, so the name leg is re-expressed here rather than
    called.

    **TWO LEGS AND NOT FIVE.** The accounts list searches five things
    (`BR-CUS-053`); this searches the two the drawing names. A box that
    silently matched an address as well would be a search whose results a
    finance officer cannot explain from the label above it (B14 rule 33 —
    the label is three words and cannot carry the difference).

    `icontains`, matching every other account search in the product: a clerk
    reading digits off a bill types `417`, not `AC-2026-00417`.
    """
    names = models.Contact.objects.filter(
        tenant_id=_tenant_id(), full_name__icontains=term, deleted_at__isnull=True
    ).values_list("account_id", flat=True)
    return (
        models.Account.objects.filter(tenant_id=_tenant_id())
        .filter(Q(account_no__icontains=term) | Q(id__in=names))
        .values_list("id", flat=True)
    )


def account_ids_of_class(code: str) -> QuerySet:
    """The accounts of one ACCOUNT CLASS (`account_types.code`), LAZY.

    A14's ageing has been able to narrow to a class since it was written; it did
    it by materialising every debtor's account row and comparing in Python,
    which is one of the reads `DEF-REP-6607` counted. Same answer, as a nested
    subquery, so it costs the request no round trip.
    """
    return models.Account.objects.filter(
        tenant_id=_tenant_id(), account_type__code=code
    ).values_list("id", flat=True)


def account_ids_at_premises(premises_id: Any) -> QuerySet:
    """p035's `f.premises` — the accounts AT one property, LAZY.

    ⚠ **IT WALKS `accounts.premises_id` AND NOT THE UNIT**, for the reason
    `account_ids_at_matching_address` records: `BR-CUS-1010` puts exactly one
    account per building that names NO unit — the owner's Master Account — and
    a unit-walking predicate drops precisely the account that owns the
    property. Hard rule 8 is untouched: no address is read or stored here, only
    the pointer every account already carries.
    """
    return models.Account.objects.filter(
        tenant_id=_tenant_id(), premises_id=premises_id
    ).values_list("id", flat=True)


def _account_ids_by_contact_name(term: str) -> list[Any]:
    """BR-CUS-053 "customer name". BR-CUS-054 says a name search resolves the
    CUSTOMER entity so every linked account returns; that entity is
    PROPOSED-SCHEMA and not built, so the match is against `contacts` and a
    landlord with three accounts is found through the three contact rows.
    REPORTED — the customer-entity leg lands with BR-CUS-054's table."""
    return list(
        models.Contact.objects.filter(
            tenant_id=_tenant_id(), full_name__icontains=term, deleted_at__isnull=True
        ).values_list("account_id", flat=True)
    )


# ═══════════════════════════════════════════════════════════════════════════
# `CR-177-BRC10` task 1b · `BR-MET-1195` — the OWNER search on Add a premise
# ═══════════════════════════════════════════════════════════════════════════
#
# PO 2026-10-09: *"in owner - allow to search master account from master
# account list. if it is found then show the details, if it is not found then
# show this account not available"*. Metering asks this through its read-only
# seam (`metering.seams.master_account_search`); customers owns `accounts`.
#
# ⚠ **WHY NOT `GET /accounts?f.kind=master`.** That list searches five legs —
# address and meter number among them — so `500 Main` finds the owner of every
# account AT 500 Main, which is the wrong question for *who owns this new
# building*; and its row carries neither the account type's NAME nor whether
# the holder is a person or a company, both of which the drawing's card shows.
# This is the narrower read: a master account, by its NAME or its NUMBER.


def master_account_search_queryset(term: Any) -> QuerySet:
    """The tenant's MASTER accounts whose number, customer number or holder's
    name contains `term` — LAZY, so the caller's paginator pays for one page
    (NFR-3). Fewer than `MIN_SEARCH_CHARS` characters matches nothing (IS-3)."""
    text = str(term or "").strip()
    qs = account_queryset().filter(kind="master")
    if len(text) < MIN_SEARCH_CHARS:
        return qs.none()
    named = models.CustomerAccount.objects.filter(
        tenant_id=_tenant_id(), ended_at__isnull=True, customer__display_name__icontains=text
    ).values("account_id")
    matches = (
        Q(account_no__icontains=text)
        | Q(id__in=_account_ids_by_customer_no(text))
        | Q(id__in=named)
        | Q(id__in=_account_ids_by_contact_name(text))
    )
    return qs.filter(matches).order_by("account_no", "id")


def master_account_search_rows(accounts: Any) -> dict[str, dict[str, Any]]:
    """`{account_id: row}` for ONE PAGE of `master_account_search_queryset` —
    the account number, the holder's name, the account type's NAME, person or
    company, and the status's own label. ⚠ The `id` is for the link a clerk
    makes, never a visible value (B14 rule 31)."""
    page = list(accounts or [])
    ids = [str(row.id) for row in page]
    holders = current_customers_for(ids)
    contacts = primary_contact_names_for(ids)
    out: dict[str, dict[str, Any]] = {}
    for row in page:
        key = str(row.id)
        holder = holders.get(key) or {}
        out[key] = {
            "id": key,
            "account_no": row.account_no,
            "name": holder.get("name") or contacts.get(key),
            "account_type": row.account_type.code,
            "account_type_name": row.account_type.name,
            # `person` | `company` — the CUSTOMER's kind; `None` when no current
            # customer holds the account, drawn as an absence, never guessed.
            "party_kind": holder.get("kind") or None,
            "status": row.status.code,
            "status_name": row.status.name,
        }
    return out


def account_status_counts() -> list[dict[str, Any]]:
    """How many accounts sit on each of THIS TENANT'S statuses — ONE query.

    PO ruling 2026-09-28: the Accounts list carries four tiles — **Active ·
    Pending · Disconnecting · Suspended** — and each one both states a count
    and narrows the list to it. This is the read behind all four.

    ⚠ **IT IS ONE GROUPED QUERY AND NOT ONE QUERY PER TILE.** What it replaces
    is a second whole `GET /accounts` fired from the browser purely to read one
    envelope `count` (the `PENDING ACTIVATION` tile, CR-030 W2 T2.2, whose own
    note said *"a `rollup.pending_activation` … would pay for itself"*). Four
    tiles built that way would be four list reads, each materialising a page of
    rows to throw them away.

    ⚠ **THE JOIN RUNS FROM THE STATUS TABLE, NOT FROM `accounts`, AND THAT IS
    THE WHOLE DESIGN.** `accounts.values("status__code").annotate(Count())`
    returns a row only for a status some account is already on, so a tenant with
    no suspended customers today would be handed NO ROW for `vacation_hold` —
    and a screen cannot tell *"nobody is suspended"* from *"this utility has no
    such status"*. Those are different sentences and the tile draws them
    differently. Starting from `account_statuses` and LEFT JOINing gives a row
    for every status the tenant HAS, with `0` where it holds nobody, and gives
    NO row for a status it does not have at all.

    ⚠ **TENANT-EXTENSIBLE, SO THE CODE IS THE KEY AND THE NAME TRAVELS WITH IT**
    (BR-CUS-055 — a utility may rename a seeded status or add *Legal hold*).
    The four tiles pick their four SEED CODES out of this list, so a utility
    that renamed *Vacation hold/Suspended* is still counted; the `name` is
    served beside it so a caller that wants the tenant's own word has it without
    a second read. Every OTHER status the tenant holds — `closed`,
    `disconnected`, whatever they added — is served too and no tile draws it;
    serving only four would make this read the tiles' private index rather than
    the tenant's status census.

    ⚠ **INACTIVE STATUSES ARE COUNTED.** `account_statuses.active` governs
    whether a status may be CHOSEN, not whether accounts still sit on one that
    was switched off — and an account on a retired status is exactly the one a
    clerk needs to find. Filtering them out here would hide live customers
    behind a lookup flag.

    Tenant scoping is belt AND braces (CLAUDE.md hard rule 1): the status rows
    are filtered to this tenant, and the counted join is filtered to it again by
    name. RLS FORCE makes the second one redundant on PostgreSQL and the sqlite
    test database has no RLS at all, which is why it is written out.
    """
    tenant_id = _tenant_id()
    rows = (
        models.AccountStatus.objects.filter(tenant_id=tenant_id)
        .annotate(accounts=Count("account", filter=Q(account__tenant_id=tenant_id)))
        .order_by("code")
        .values_list("code", "name", "accounts")
    )
    return [{"code": code, "name": name, "accounts": total} for code, name, total in rows]


def accounts_rollup() -> dict[str, Any]:
    """US-CUS-001 §5 header roll-up ("N accounts · $X outstanding · N past-due
    60+").

    **`outstanding` IS THE LEDGER'S FIGURE SINCE 2026-08-15 (DEF-127).** It used
    to be Σ of `accounts.balance` over the tenant's accounts, with the comment
    *"Nothing writes `accounts.balance` yet, so it is honestly 0.0000000
    today"* — and it was not honest, because by then bills WERE issuing and
    posting. The header read **Outstanding $0.00** to a utility the books said
    was owed **261.20**. Same Σ as the row's own balance and as
    `apps/ledger/reporting.revenue_and_ar`'s `still_owed`, so the header and the
    rows and the S36 KPI cannot state three different numbers.

    Only POSITIVE positions are added, which is what "outstanding" has always
    meant here: a customer sitting on a credit reduces nothing that anybody else
    owes, and netting them in would understate the debt a collections ladder
    works from.

    ⚠ IT IS NOT THE SAME FIGURE AS `still_owed`, and the difference is real
    rather than a rounding artefact: `still_owed` is the AR control total,
    INCLUDING any posted AR line carrying no account dimension, while this sums
    the accounts a clerk can open. On a book where every line names its account
    they are equal, and the S36 tie-out panel (US-LED-004) is the thing that
    compares them; a screen must never do that subtraction itself.

    **UNREADABLE IS NULL, NOT 0.00.** If the books cannot be asked at all, the
    header renders its awaiting state with the reason — the same distinction the
    row makes, for the same reason: `$0.00 outstanding` is a claim.

    The third figure needs open invoices (BR-CUS-016) and is null, not zero —
    "18 past-due 60+" and "0 past-due 60+" are different claims.

    ⚠ **NO SCREEN DRAWS `accounts`, `outstanding` OR `past_due_60_plus` ANY
    MORE — PO ruling 2026-09-28** replaced S17's five tiles with four counted
    from `by_status`. The three fields STAY SERVED and stay honest: `accounts`
    is read by the reports dashboard seam
    (`tests/test_us_rep_019_dashboard.py`), `outstanding` is the one figure the
    ledger and this header ever agreed on (DEF-127) and dropping it would make
    that agreement unprovable, and `past_due_60_plus` is still the null whose
    expiry `tests/test_stated_absence_expiry.py` dates. **What changed is the
    RENDERER, not the read** — recorded here so the next lane does not read an
    unrendered field as dead weight and delete it.
    """
    qs = account_queryset()
    accounts = list(qs.values_list("id", "currency"))
    positions = _ar_positions_for([account_id for account_id, _currency in accounts])
    outstanding: Decimal | None = None
    if positions.available:
        outstanding = Decimal("0")
        for account_id, _currency in accounts:
            amount = positions.amount_for(account_id)
            if amount is not None and amount > 0:
                outstanding += amount
    return {
        "accounts": len(accounts),
        # DERIVED from posted journal lines (BR-REP-002), never a cache.
        "outstanding": _money(outstanding),
        # DEF-099 / CLAUDE.md rule 2 — the header's money figure never travels
        # without its CHAR(3). The ledger derives it from the entries summed;
        # with nothing posted there is no derived code and the accounts' own
        # declared currency is what the header labels an empty book with.
        "currency": positions.currency
        or next((currency for _id, currency in accounts if currency), None),
        "outstanding_basis": positions.basis,
        "outstanding_unavailable": positions.unavailable,
        "past_due_60_plus": None,
        # PO ruling 2026-09-28 — the four status tiles, from ONE grouped query.
        # See `account_status_counts` for why the join runs from the status
        # table and what a MISSING code means to the screen.
        "by_status": account_status_counts(),
    }


# ── S21 Notes tab + S22 Add-note modal (US-CUS-011 · US-CUS-015) ────────────
def note_dict(row: models.AccountNote) -> dict[str, Any]:
    """One note, as the card list renders it.

    `author_name` is resolved, not the raw id: the Notes tab shows "Alex Reed",
    and a screen that had to join identity itself would be a cross-module read
    from the browser. A note with no author is a SYSTEM note (the prototype's
    "Autopay enrollment confirmed · System") and renders as such — the null is
    the fact, and the sentence for it is the screen's own string.
    """
    return {
        "id": str(row.id),
        "account_id": str(row.account_id),
        "title": row.title,
        "body": row.body,
        "author_id": str(row.author_id) if row.author_id else None,
        "author_name": _author_name(row.author_id),
        "pinned": row.pinned,
        # BR-CUS-035: captured, INERT in v1. Served so the screen can show what
        # was captured; nothing anywhere may read it as a portal permission.
        "customer_visible": row.customer_visible,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _author_name(author_id: Any) -> str | None:
    """The note author's display name through identity's OWN read.

    Resolved BY NAME (the seam idiom) so customers imports no identity model. An
    unwired or unknown author answers None, and the screen says "System" for it
    rather than this function inventing a name."""
    if not author_id:
        return None
    from apps.customers import seams

    fn = seams.resolve("identity", "user_display_name", kind="selectors")
    if fn is None:
        return None
    try:
        return fn(author_id)
    except Exception:  # pragma: no cover - a read must never break the tab
        return None


def account_notes(account_id: Any) -> list[dict[str, Any]]:
    """The S21 Notes tab, in the capability matrix's own order: PINNED FIRST,
    then newest. The order is the index's (migration 0007), not a Python sort —
    an account can collect hundreds of notes over a tenancy."""
    account = account_or_404(account_id)
    rows = models.AccountNote.objects.filter(tenant_id=account.tenant_id, account=account).order_by(
        "-pinned", "-created_at", "-id"
    )
    return [note_dict(row) for row in rows]


# ── the delivery recipient read notifications resolves BY NAME ──────────────
def delivery_channel_election_for_account(account_id: Any) -> tuple[str, ...] | None:
    """The channels a BILL to this account goes on BEYOND the print floor (CR-052 task 14).

    **THIS IS THE READ `apps/billing/delivery_seam.py` HAS NAMED BY STRING SINCE
    W3.** That module's contract is quoted here verbatim so the two halves
    cannot drift:

        apps.customers.selectors.delivery_channel_election_for_account(account_id)
            -> tuple[str, ...] | None

        The EXTRA channels beyond the print floor (BR-BIL-036) — `("email",)`
        for an account with an email on file, `()` for one with neither, and
        **None when the question cannot be answered**.

    ⚠ **AMENDED 2026-10-22 (`DEF-BIL-10535`, PO ruling Q2, verbatim: *"B. Yes,
    every bill: paper plus an email copy whenever an email is on file."*).**
    Until then email was elected ONLY by `accounts.paperless`, so Daniel Thomas
    (AC-2026-00071, paperless off, `daniel.thomas@yopmail.com` on file) was
    mailed his bill and never emailed it. Now email is elected whenever the
    address the queue would send to exists — the primary contact's email, the
    one `delivery_recipients_for_account` addresses by, so *can we email them*
    has one answer — OR the customer chose paperless (which still queues an
    email row, unaddressed, when no email is on file: the row says why). SMS
    stays opt-in (`accounts.sms_reminders`).

    ⚠ **THIS IS A BILL RULE, NOT THE CUSTOMER'S PREFERENCE.** A screen that
    shows what the customer CHOSE (the portal's *Paperless* switch) reads
    `channel_preference_for_account` below, which is this function's old body
    unchanged. Reading this one there would show *Paperless: on* for every
    customer with an email (decision log 2026-10-22, *Building the
    corrected-bill rulings Q1–Q3*, point 5).

    ⚠ **SINCE 2026-10-29 WORK'S VISIT MESSAGES READ THIS ONE TOO**
    (`DEF-WRK-10663`, PO ruling B1 A — *visit messages go by email whenever the
    account has an address, as bills do*): `notifications.work_customer_messages`.

    ⚠ **PRINT IS NEVER IN THIS TUPLE, AND THAT IS THE POINT.** BR-BIL-036 makes
    print the FLOOR, applied inside `apps/notifications`
    (`CHANNEL_FLOOR_BY_SOURCE`). Returning `("email",)` ADDS a channel; it
    never replaces one. An account with no email still bills, on paper.

    ⚠ **`()` AND `None` ARE DIFFERENT ANSWERS.** `()` is a fact about the
    PERSON; `None` is *nobody can tell* — the account is not this tenant's.

    **WORKED, and this is the figure the tests are proved on:** an account with
    `paperless=False, sms_reminders=False` and **no** email queues **one** row
    for its bill — `pdf_print`. Give its primary contact an email and it queues
    **two** — `pdf_print` AND `email` — whatever `paperless` says (Daniel's
    case). Opt in to texts as well and it queues **three**. Nothing ever
    queues zero.

    Ordered `email` then `sms` so a caller comparing two tuples compares two
    sets, and the queue writes rows in a stable order across runs.
    """
    account = _account_for_election(account_id)
    if account is None:
        # A fact about the PLATFORM, not about a customer — see the docstring.
        return None
    elected: list[str] = []
    if account.paperless or _primary_contact_email(account) is not None:
        elected.append("email")
    if account.sms_reminders:
        elected.append("sms")
    return tuple(elected)


def channel_preference_for_account(account_id: Any) -> tuple[str, ...] | None:
    """What the CUSTOMER chose — paperless → `email`, text reminders → `sms`.

    `DEF-BIL-10535` (2026-10-22): `delivery_channel_election_for_account`'s body
    before the PO's Q2 ruling, unchanged and moved here, for the readers that
    show or honour a customer's own choice rather than send a bill: the
    portal's *Paperless* switch (`portal/seams/customers_seam.delivery_election`,
    `portal/selectors.py`'s account card). Work's visit messages read it until
    2026-10-29 and now read the bill's election above (`DEF-WRK-10663`).
    `None` when the account is not this tenant's; `()` when they chose nothing.
    """
    account = _account_for_election(account_id)
    if account is None:
        return None
    elected: list[str] = []
    if account.paperless:
        elected.append("email")
    if account.sms_reminders:
        elected.append("sms")
    return tuple(elected)


def _account_for_election(account_id: Any) -> models.Account | None:
    return (
        models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id).first()
        if _is_uuid(account_id) or isinstance(account_id, models.Account)
        else None
    )


def _primary_contact_email(account: models.Account) -> str | None:
    """The email a message to this account is addressed to, or None — the SAME
    contact `delivery_recipients_for_account` picks (primary first, then the
    oldest live one), so the election and the address cannot disagree."""
    contact = (
        models.Contact.objects.filter(
            tenant_id=account.tenant_id, account=account, deleted_at__isnull=True
        )
        .order_by("-is_primary", "created_at", "id")
        .first()
    )
    return ((contact.email if contact is not None else None) or "").strip() or None


def bill_template_election_for_account(account_id: Any) -> dict[str, Any] | None:
    """BR-BIL-025's two ACCOUNT facts — the override, and the consumer category.

    CR-052 task 12. `billing.templates_service.resolve_for` implements the ruled
    order — **account override → category default → tenant fallback** — and has
    always taken the override as an ARGUMENT, because (its own words) *"BR-BIL-025
    puts it on the ACCOUNT and the account is customers' row; billing has one
    reviewed FK into customers (`invoices.account_id`) and no column for this"*.
    This is the read that supplies both legs.

    Returns `{"template_override_id": <uuid|None>, "consumer_category": <code|None>}`
    or `None` when the account is not this tenant's. `None` and a dict of two
    `None`s are different answers and billing keeps them apart: the first means
    the question could not be asked and the run's own pin stands, the second
    means this account states no override and its category has no template — the
    fallback, which is what every tenant with one template already gets.

    The category is `account_types.code` — the PLATFORM consumer category, seven
    codes since BR-CUS-094 — and never the free-text subtype: `bill_templates
    .category` is keyed on the platform code and a subtype would silently match
    nothing and fall through to the fallback with no way to see it had.
    """
    account = (
        models.Account.objects.select_related("account_type")
        .filter(tenant_id=_tenant_id(), pk=account_id)
        .first()
        if _is_uuid(account_id) or isinstance(account_id, models.Account)
        else None
    )
    if account is None:
        return None
    return {
        "template_override_id": account.template_override_id,
        "consumer_category": getattr(account.account_type, "code", None),
    }


def account_preferred_language(account_id: Any) -> str | None:
    """This account's preferred language, or None (`BR-CUS-064`, r15 #2).

    ⚠ **EVERY MESSAGE TO THE ACCOUNT RESOLVES ON THIS AGAIN — 2026-10-29 (PO
    option B, decision log *"A message goes in the customer's preferred
    language"*, SUPERSEDING `OQ-CUS-12619` (a) for messages).** PO, verbatim:
    *"Question: which language should messages be sent in? - B"*. The column
    drives the portal AND the language variant of every email, text, letter
    and in-app message, on `BR-NOT-006`'s ladder: a language the utility has
    not published falls back to the utility's default. Read by
    `notifications.customers_seam.account_preferred_language` and applied in
    ONE place, `notifications.message_language.language_for`, which
    `queue_document` calls for every row it pins. (From 2026-09-23 to
    2026-10-29 it drove the portal alone — *"(a) Portal only; emails in
    English."* — and that is now history.)

    ⚠ **(HISTORY) THE THIRD AXIS `BR-BIL-025` RESOLVES ON, AND NOBODY COULD READ IT.**
    A template resolves on class, customer category and LANGUAGE.
    `queue_document` takes `language` as an argument *precisely* because this
    module published no read for it — its own docstring says so — so **every
    caller in this product has passed `None`**, and a utility could publish an
    `es-MX` variant that would never be selected for anybody. The column has
    existed since r15 #2; only the door was missing. Hard-won law 2 at the
    small end: the data, the fallback ladder and the recording of which
    language was used were all built, and nothing could answer the question.

    ⚠ **None MEANS TWO DIFFERENT THINGS AND THE CALLER MUST NOT MERGE THEM.**
    This account states no preference, OR there is no account. Both resolve on
    the utility's default variant, which is `BR-BIL-025`'s second fallback and
    is correct either way — but only one of them is worth showing a clerk, so
    the answer is not dressed up as `"en"` here.

    A SELECTOR read by id: the sanctioned cross-module path (B2 §2). It returns
    a string and never a row, because the caller wants an axis and not an
    account.
    """
    row = (
        models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id)
        .values_list("preferred_language", flat=True)
        .first()
    )
    return row or None


def account_counts_by_language() -> dict[str | None, int]:
    """`{preferred_language: number of accounts}` for this tenant — ONE grouped
    statement, never a row per account (`NFR-3`/`NFR-5`: an aggregate, so it
    stays one statement at 40,000 accounts and beyond).

    `CR-199-BRC10` (TPL-SRV-LANG) — the figure behind the Templates screen's
    *"Español · 312 customers"* (drawing image 16), which exists because since
    2026-10-29 every message goes in the account's preferred language (PO
    option B). The key `None` collects every account that states no preference
    (NULL or blank), which the caller files under the utility's default
    language — those accounts receive exactly that. Codes are returned as
    STORED (`es-MX` is not folded into `es`); the folding is the caller's,
    because which variant an `es-MX` account receives depends on what the
    utility published, not on this table."""
    from django.db.models import Count

    out: dict[str | None, int] = {}
    rows = (
        models.Account.objects.filter(tenant_id=_tenant_id())
        .values("preferred_language")
        .annotate(n=Count("id"))
        .order_by()
    )
    for row in rows:
        code = str(row["preferred_language"] or "").strip() or None
        out[code] = out.get(code, 0) + int(row["n"])
    return out


def delivery_recipients_for_account(
    account_id: Any, channels: tuple[str, ...] = ("pdf_print", "email", "sms")
) -> dict[str, dict[str, Any]]:
    """WHO a message to this account goes to, per channel (BR-TEN-017).

    THIS IS THE READ `apps/notifications/services.py` HAS NAMED SINCE W3 AND
    NOBODY PUBLISHED. Its docstring states the contract in so many words —
    `RECIPIENT_MODULE = "customers"`, `RECIPIENT_READ =
    "delivery_recipients_for_account"` — and until this function existed the
    resolver returned None, so EVERY queued bill, receipt and notice recorded
    `recipient_not_resolvable`: *"nobody could look"*. Hard-won law 2 at
    platform scale — the queue was built, wired and completely unaddressed.

    THE THREE ANSWERS, kept apart because a dashboard counts them:

      · `{"address": ..., "snapshot": {...}}` — we can speak to this channel.
      · `{"unavailable_reason": "no_email_address"}` — a fact about the PERSON.
        BR-BIL-036's normal case: print is the floor and an account with no
        email is ordinary, not an exception.
      · `{"unavailable_reason": "recipient_not_resolvable"}` — a fact about the
        PLATFORM: print only when metering cannot be asked for the
        service address; the portal copy of an account with no number.
        (It read *"Used ONLY for SMS"* while the print and portal branches both
        used it — corrected with `DEF-PAY-6342`.)
        ⚠ **THE REASON THIS SENTENCE GAVE IS NO LONGER TRUE AND IS REPLACED
        RATHER THAN LEFT STANDING (hard-won law 1, CR-052 task 14).** It read:
        *"the mobile-consent column (`accounts.sms_reminders`) is
        PROPOSED-SCHEMA and does not exist, so nobody has asked this customer
        whether they consent to texts."* **The column exists as of migration
        0034 and is read** — by `delivery_channel_election_for_account`, which
        is what decides whether an SMS row is queued for this bill at all. So
        consent is now a recorded fact.
        ⚠ **SUPERSEDED 2026-10-05 (`DEF-NOT-9668`, lane FIX-7).** This read
        *"What is still missing is the NUMBER … an SMS row is still queued
        UNADDRESSED"* (`DEF-2700`). The wizard that records the election offers
        it only with a phone and says *"Goes to the phone above."*, so the
        number IS recorded: `_text_recipient` below addresses a text to it, and
        only for a customer who chose texts. SMS no longer answers
        `recipient_not_resolvable`.

    The POSTAL address is the mailing address when one exists and the SERVICE
    address otherwise — B2 §2's own semantics, where the absence of a mailing
    row MEANS "same as service" (S21 renders exactly that sentence).

    ⚠ **THE PARAGRAPH ABOVE WAS FALSE FROM 2026-08-11 UNTIL 2026-09-23
    (`DEF-PAY-6342`), AND IT WAS REPEATED TO THE PRODUCT OWNER AS A FACT.** The
    code under it returned the MAILING address or nothing: with no mailing row
    the letter was queued UNADDRESSED as `recipient_not_resolvable`, because
    metering published no structured premises-address read. Hard-won law 1 in
    its plainest form — the docstring claimed the fallback, the code did not
    have it, and every test asserted the code. The PO ruled on 2026-09-23,
    verbatim: *"fx it - ensure you update correct address - mailing or
    service"*. It is now true, and `snapshot["source"]` says WHICH of the two a
    letter went to — `mailing_address` or `service_address` — because the
    returned-post clear step (`BR-PAY-018`) sends the clerk to a different
    address depending on the answer.

    **The four print answers, and they are four different facts:**
      · a mailing row with a street → that row, `source: mailing_address`;
      · otherwise the premises the account walks to (its unit's, or the owner's
        account's own premises — `BR-CUS-1010`), with the unit's LABEL beside
        the building's lines and never a second address (hard rule 8),
        `source: service_address`;
      · `no_postal_address` — the account reaches no premises, or the premises
        has no street. A fact about the PROPERTY or the RECORD, and the
        bad-address flag (`BR-PAY-018`) is the other half of it;
      · `recipient_not_resolvable` — metering could not be asked. A fact about
        the PLATFORM, and never merged with the one above (`BR-BIL-036`).

    ⚠ **A SNAPSHOT IS FROZEN AT QUEUE TIME (`BR-TEN-017`).** Letters queued
    before this change carry no address and are not backfilled: the row records
    what the platform could say when the letter was made.
    """
    account = account_or_404(account_id)
    contact = (
        models.Contact.objects.filter(
            tenant_id=account.tenant_id, account=account, deleted_at__isnull=True
        )
        .order_by("-is_primary", "created_at", "id")
        .first()
    )
    name = contact.full_name if contact is not None else None
    out: dict[str, dict[str, Any]] = {}
    for channel in channels:
        if channel == "email":
            email = (contact.email if contact is not None else None) or None
            out[channel] = (
                {"address": email, "snapshot": {"name": name}}
                if email
                else {"unavailable_reason": "no_email_address"}
            )
        elif channel == "pdf_print":
            # The mailing row, else the service address walked to through
            # metering (`DEF-PAY-6342`). `_postal_recipient` returns the whole
            # answer — an address and its snapshot, or ONE reason — so the two
            # absences it can report never collapse into each other here.
            out[channel] = _postal_recipient(account, name)
        elif channel == "portal":
            # ⚠ **`CR-084` — THE CUSTOMER PORTAL, AND IT IS THE ONE CHANNEL HERE
            # THAT IS NEVER UNAVAILABLE.**
            #
            # The address is the ACCOUNT NUMBER: the reference printed on the
            # bill the customer is holding, and the one the portal's own
            # enrolment asks them for. Not the account's uuid — a database id is
            # never a visible value (B14 rule 31) and `recipient_address` is
            # drawn on the staff dispatch home.
            #
            # **No `unavailable_reason` exists for an account nobody has enrolled
            # yet, and that is a decision rather than an oversight.** Publication
            # to the portal does not depend on anyone having signed up: the
            # document is there the day they do. Recording *not enrolled* would
            # make a bill's PERMANENT delivery record depend on a customer's
            # FUTURE sign-up, and that record would be wrong the day after they
            # enrolled — which is the same error as recording an unlooked-up
            # address as `no_email_address`, one branch up.
            #
            # An account this module cannot resolve never reaches here at all:
            # `account_or_404` above has already refused it.
            #
            # ⚠ The ONE absence that IS possible is an account with no NUMBER.
            # It is a fact about the PLATFORM — the row exists and we have no
            # human reference to address the copy with — so it takes the same
            # `recipient_not_resolvable` the postal branch uses for the same
            # shape of gap. It is emphatically NOT `no_email_address`'s kind of
            # answer: nothing about the customer is missing. Falling back to the
            # account's uuid was the first draft and would have put a database
            # id on the dispatch home (B14 rule 31).
            out[channel] = (
                {
                    "address": account.account_no,
                    "snapshot": {"name": name, "source": "account_number"},
                }
                if account.account_no
                else {"unavailable_reason": "recipient_not_resolvable"}
            )
        elif channel == "sms":
            out[channel] = _text_recipient(account, contact, name)
    return out


def _text_recipient(
    account: models.Account, contact: models.Contact | None, name: str | None
) -> dict[str, Any]:
    """The `sms` answer — `DEF-NOT-9668` / `DEF-NOT-9669` (lane FIX-7, 2026-10-05).

    ⚠ **THIS READ ANSWERED `recipient_not_resolvable` FOR EVERY TEXT FROM
    2026-08-31 UNTIL THIS CHANGE (`DEF-2700`)**, on the reasoning that
    `contacts.phone` is one free-text field and nothing declared it a mobile.
    That reasoning was overtaken by the product's own screens: the New Account
    wizard offers *Text reminders* ONLY when step 1 captured a phone, and says
    under the box, verbatim, *"Goes to the phone above."* — so a customer who
    ticks it has told us which number to text. Every work-order text a
    dispatcher queued then read *Address not looked up* beside a customer whose
    printed work order carried their number (Silver Creek Sample Millworks,
    `+1 (402) 555-1049`, WO-0056).

    **Three answers, each a different fact (`BR-BIL-036`), CONSENT FIRST:**

      * `accounts.sms_reminders` is false → `no_sms_opt_in`. Asked of EVERY
        caller, not left to each writer's election read: the payment receipt
        queues an `sms` row for every payment (`payments/receipts.py`), and an
        answer carrying an ADDRESS there would text a customer who never chose
        texts the day a dispatcher exists (`DEF-NOT-9669`).
      * chosen, and the primary contact — the SAME row the email branch above
        reads, the account screen shows and the work order prints
        (`work/seams/customers_seam.account`) — has a phone → addressed to it,
        `source: contact_phone`. Else the customer record's own phone
        (`customers.phone`, encrypted, linked through `customer_accounts`),
        `source: customer_phone`.
      * chosen and no phone anywhere → `no_mobile_number`: the row is written
        and says why; nothing is invented.

    The do-not-send list is the QUEUE's and is not read here: an addressed text
    whose number is listed is written and HELD (`DEF-NOT-5632`).
    """
    if not account.sms_reminders:
        return {"unavailable_reason": "no_sms_opt_in"}
    phone = ((contact.phone if contact is not None else None) or "").strip()
    source = "contact_phone"
    if not phone:
        link = (
            models.CustomerAccount.objects.filter(tenant_id=account.tenant_id, account=account)
            .select_related("customer")
            .order_by("created_at", "id")
            .first()
        )
        phone = ((link.customer.phone if link is not None else None) or "").strip()
        source = "customer_phone"
    if not phone:
        return {"unavailable_reason": "no_mobile_number"}
    return {"address": phone, "snapshot": {"name": name, "source": source}}


#: `snapshot["source"]` on a print recipient — WHICH address a letter went to.
#: Payments' returned-post clear step routes on it (`BR-PAY-018`, PO ruling
#: 2026-09-23: *"ensure you update correct address - mailing or service"*), so
#: the two spellings are named once, here, where they are written.
POSTAL_SOURCE_MAILING = "mailing_address"
POSTAL_SOURCE_SERVICE = "service_address"


def _postal_recipient(account: models.Account, name: str | None) -> dict[str, Any]:
    """The print recipient: `{"address", "snapshot"}` or `{"unavailable_reason"}`.

    See `delivery_recipients_for_account` for the four answers. Costs ONE
    statement when the account has a mailing row and TWO when it walks to the
    premises — the recipient read is called once per queued letter by its
    contract, and the premises leg is the batched `envelope_addresses` asked
    for one place, never a loop.
    """
    postal = _postal_snapshot(account, name)
    if postal is not None:
        return {"address": postal["line1"], "snapshot": postal}
    return _service_postal(account, name)


def _postal_snapshot(account: models.Account, name: str | None) -> dict[str, Any] | None:
    """The envelope, frozen at queue time — the MAILING address, or None.

    None means *this account has no live mailing row with a street*, and the
    caller then walks to the service address — B2 §2's *"same as service"*.

    ⚠ **`deleted_at` IS FILTERED, AND UNTIL `DEF-PAY-6342` IT WAS NOT.**
    `PATCH /accounts/{id}/mailing-address` with an empty street SOFT-deletes
    the row — that is how a clerk says *the bill goes to the service address* —
    and this read went on picking the deleted row, so the letter kept going to
    the address the clerk had just removed. The returned-post clear step offers
    exactly that removal, which is how it was found.
    """
    row = (
        models.Address.objects.filter(
            tenant_id=account.tenant_id,
            account=account,
            kind="mailing",
            deleted_at__isnull=True,
        )
        .order_by("created_at", "id")
        .first()
    )
    if row is None or not (row.line1 or "").strip():
        return None
    return {
        "name": name,
        "line1": row.line1,
        # `DEF-BIL-6373` — the print set reads this snapshot too, and its
        # manifest has a line 2 and a country (`DEF-2847`'s two columns). Both
        # NULL on every row written before `customers 0039`, and never invented.
        "line2": row.line2,
        "city": row.city,
        "state": row.state,
        "postal_code": row.postal_code,
        "country": row.country,
        "source": POSTAL_SOURCE_MAILING,
    }


def _service_postal(account: models.Account, name: str | None) -> dict[str, Any]:
    """The SERVICE address as an envelope — the premises the account walks to.

    Walked, never stored (hard rule 8): the account's unit → its premises, or,
    for an owner's account that names no unit, `accounts.premises_id`
    (`BR-CUS-1010`). The unit contributes its LABEL and nothing else.
    """
    unit_id = account.unit_id if account.unit_id not in (None, "") else None
    premises_id = getattr(account, "premises_id", None) if unit_id is None else None
    if unit_id is None and premises_id in (None, ""):
        # An account that reaches no property has nowhere to post — a fact
        # about the RECORD, not the platform.
        return {"unavailable_reason": "no_postal_address"}
    answered = seams.envelope_addresses(
        unit_ids=[unit_id] if unit_id is not None else [],
        premises_ids=[premises_id] if unit_id is None else [],
    )
    if answered is None:
        # Metering could not be asked: the PLATFORM's gap (`BR-BIL-036`).
        return {"unavailable_reason": "recipient_not_resolvable"}
    envelope = (
        (answered.get("units") or {}).get(str(unit_id))
        if unit_id is not None
        else (answered.get("premises") or {}).get(str(premises_id))
    )
    if envelope is None:
        # A PROTECTed FK cannot dangle, so this is a place the tenant cannot
        # see — the platform could not answer, which is not "no address".
        return {"unavailable_reason": "recipient_not_resolvable"}
    line1 = (envelope.get("line1") or "").strip()
    if not line1:
        return {"unavailable_reason": "no_postal_address"}
    label = (envelope.get("unit_label") or "").strip() or None
    snapshot = {
        "name": name,
        "line1": line1,
        "city": envelope.get("city"),
        "state": envelope.get("state"),
        "postal_code": envelope.get("postal_code"),
        # Hard rule 8: the unit refines the premises by LABEL. It travels as
        # its own key so an envelope renderer sets it on its own line and
        # never has to split a composed string (`BR-NOT-029` clause (a)).
        "unit_label": label,
        "source": POSTAL_SOURCE_SERVICE,
    }
    # `recipient_address` is the one-line summary the dispatch home prints; the
    # label is on it so two flats in one building are two different lines.
    return {"address": f"{line1} · {label}" if label else line1, "snapshot": snapshot}


# ── the r17.2 value read (US-BIL-028; DB-17) ────────────────────────────────
def custom_data_for_account(account_id: Any) -> dict[str, Any]:
    """One account's tenant-defined values + its unit — PUBLISHED FOR BILLING.

    `apps/billing/custom_snapshot.py` — the single module DB-17 allows to touch
    tenant-defined data inside a money path — resolves this by name. Billing
    never imports `apps.customers.models` (B1 / G6 module boundary): the values
    live on the owning module's row and are read through the owning module's
    selector, which is exactly why B2 r17.2 put them there instead of in a
    shared `custom_field_value` table.

    `unit_id` travels with them because it is THIS table's column and it is how
    the caller reaches the property side of the same account (metering's
    `custom_data_for_location`). Returning it here spares billing a second
    round trip and, more to the point, spares it from having to know that an
    account reaches its premises through a unit.

    An unknown or other-tenant account id returns empty values and a null unit
    — the same answer as an account with nothing defined. That is deliberate:
    the caller is stamping a document, and a missing account must not be
    distinguishable here from an empty one by anything except the caller's own
    lookup, which it has already done.
    """
    row = (
        models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id)
        .values_list("custom_data", "unit_id")
        .first()
    )
    if row is None:
        return {"accounts": {}, "unit_id": None}
    values, unit_id = row
    return {
        "accounts": values if isinstance(values, dict) else {},
        "unit_id": str(unit_id) if unit_id else None,
    }


# ── CR-075 wave Q′ · the read runbook 22 makes (US-RBS-034) ────────────────


def contact_channels_for(account_ids: Any) -> dict[str, dict[str, Any]]:
    """What each of these accounts can be reached ON — email, text, post.

    `RB-122` step 4, *Find the next channel on file*: **email → text → post →
    none**. The runbook needs the whole ladder for every account it is about to
    suppress a channel on, in ONE read, because asking per account would be one
    query per bounce and a morning's feedback is a few hundred of them.

    ⚠ **A CHANNEL IS DERIVED FROM WHAT IS ON FILE, AND `customers` HAS NO
    CHANNEL TABLE.** `Contact` carries `email` and `phone` as columns on the
    person, not a row per channel, and post is the account's own **mailing**
    address (`addresses.kind = 'mailing'`, CLAUDE.md hard rule 8's first
    exception — where the BILL goes, which for a landlord is another building).
    So *email* means at least one contact holds one; *post* means a mailing
    address exists. Composing a channel list that this module does not hold as
    rows is the read's job precisely so no other module invents its own.

    ⚠ **THERE IS NO `suppressed` HERE AND THAT IS THE POINT.** Nothing in
    `customers` records that a channel stopped working or when — which is why
    the `suppress_channel` port binds no writer (`DEF-RBS-4331`). A caller
    reading this must not treat *present* as *working*: it means *on file*.

    Also answers `13-selector-inventory.md` **S-10** — *accounts with no contact
    channel at all, nobody can be told anything* — for `RB-119` step 5: an
    account whose entry has all three false is one.
    """
    ids = [one for one in (account_ids or []) if one]
    if not ids:
        return {}
    tenant_id = _tenant_id()
    out: dict[str, dict[str, Any]] = {
        str(one): {"email": None, "text": None, "post": None, "channels": []} for one in ids
    }
    contacts = models.Contact.objects.filter(
        tenant_id=tenant_id, account_id__in=ids, deleted_at__isnull=True
    ).order_by("-is_primary", "created_at")
    for row in contacts:
        entry = out.get(str(row.account_id))
        if entry is None:
            continue
        if entry["email"] is None and (row.email or "").strip():
            entry["email"] = row.email.strip()
        if entry["text"] is None and (row.phone or "").strip():
            entry["text"] = row.phone.strip()
    addresses = models.Address.objects.filter(
        tenant_id=tenant_id, account_id__in=ids, kind="mailing", deleted_at__isnull=True
    ).order_by("created_at")
    for row in addresses:
        entry = out.get(str(row.account_id))
        if entry is None or entry["post"] is not None:
            continue
        line = ", ".join(
            part for part in (row.line1, row.city, row.state, row.postal_code) if (part or "").strip()
        )
        entry["post"] = line or None
    for entry in out.values():
        # The ladder's ORDER is the card's and it is fixed here once, so a
        # caller cannot re-order it into a different fall-back policy.
        entry["channels"] = [name for name in ("email", "text", "post") if entry[name]]
    return out


# ════════════════════════════════════════════════════════════════════════════
# CR-075 WAVE R′ — THE READ RUNBOOK 27 STARTS FROM (`RB-127`, `US-RBS-037`)
#
# *"Walks every closing account: the closing read due, the final bill issued,
# the deposit refunded or carried, the forwarding address captured."*
# ════════════════════════════════════════════════════════════════════════════

#: `BR-CUS-055`'s behaviour class for a closed account. The runbook's window
#: reaches BACKWARDS as well as forwards — *any closed account with no final
#: bill, however old* — and this is how a closed one is recognised without
#: keying on a tenant's own LABEL for it, which `AccountStatus` exists to let
#: them change.
CLOSED_BEHAVIOUR_CLASS = "terminal"


def closing_accounts(*, as_of: Any, window_days: int = 14) -> list[dict[str, Any]]:
    """Every account closing inside the window, plus every one already closed.

    `RB-127`'s scope, in one query: *accounts closing, move-out date inside the
    window* **and** *any closed account, however old* — the second half is what
    catches the move-out somebody processed in March and never billed.

    ⚠ **`as_of` IS STATED BY THE CALLER AND NEVER READ FROM A CLOCK**
    (`BR-TEN-043`, gate `G6`). A runbook knows the day its run is FOR; a
    selector that read `today` would answer differently inside one pinned scope.

    ⚠ **NO ADDRESS COLUMN IS READ OFF THE ACCOUNT, BECAUSE THERE IS NOT ONE**
    (CLAUDE.md hard rule 8, `BR-MET-1161`). `premises_id` travels so the caller
    can WALK to the one address home; the FORWARDING address is a different
    fact and comes from `mailing_address_for_account`, which is the first of the
    rule's three stated exceptions — where the BILL goes, which for somebody who
    has just moved is the whole point of asking.

    ⚠ **`deposit_held` CROSSES AS A STRING AT FOUR DECIMALS** (hard rule 2). It
    is never a float and it is not rounded here: rounding belongs at display and
    at finalisation, and a selector that returned `Decimal` would invite the
    caller to do arithmetic in whatever precision it happens to hold.

    ⚠ **`is_sample` TRAVELS RATHER THAN BEING FILTERED AWAY.** `RB-127`'s scope
    says *Never include: Sample*, and a guard applied inside a read cannot be
    SEEN on the screen that draws it (`BR-RBS-012`) — a guard nobody can see is
    a check that can never fire.
    """
    # ⚠ **`datetime` MUST BE IMPORTED FOR THIS LINE, AND IT WAS NOT
    # (`DEF-CUS-4376`).** The import above read `from datetime import date` —
    # the DATE class only — so this line raised `NameError: name 'datetime' is
    # not defined` on the first statement of the function, and the runbooks
    # conformance suite was red for every lane because of it. A narrowing
    # accepted for a reason: an instant and a calendar date are different
    # things (`BR-SHL-023`), and this function answers a calendar question, so
    # it takes either and reduces an instant to the tenant's own day.
    #
    # ⚠ **`timedelta` WAS MISSING TOO, ON THE VERY NEXT STATEMENT.** The
    # report this was salvaged from named only `datetime`, because a
    # NameError stops at the FIRST undefined name and says nothing about
    # the second. Fixing what the traceback names and shipping is how a
    # two-line fault becomes two round trips — running it after the fix is
    # what found this one.
    end = as_of.date() if isinstance(as_of, datetime) else as_of
    if not isinstance(end, date):
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-TEN-043",
            message_key="customers.closing_accounts.as_of_required",
            params={},
        )
    horizon = end + timedelta(days=int(window_days))
    rows = (
        account_queryset()
        .filter(closed_at__isnull=False, closed_at__lte=horizon)
        .select_related("status")
        .order_by("closed_at", "account_no")
    )
    accounts = list(rows)
    names = _primary_contact_names([account.id for account in accounts])
    return [
        {
            "account_id": str(account.id),
            "account_no": account.account_no,
            "customer_name": names.get(str(account.id)),
            "closed_at": account.closed_at.isoformat(),
            "already_closed": (account.status.behavior_class == CLOSED_BEHAVIOUR_CLASS),
            "status_label": account.status.name,
            "final_read_state": account.final_read_state,
            "deposit_held": str(account.deposit_on_file),
            "currency": account.currency,
            "premises_id": _premises_id_for_unit(account.unit_id),
            "unit_id": None if account.unit_id is None else str(account.unit_id),
            "is_sample": bool(account.is_sample),
        }
        for account in accounts
    ]


def request_co_applicant(request_id: Any) -> dict[str, Any] | None:
    """The CO-APPLICANT a service request names — contact only, or `None`.

    `CR-163-BRC10` item 26: the New Connection detail lets a clerk send a
    letter to the owner **or the co-applicant**. REQ-03.1 makes a co-applicant
    *"contact only"* — name, email, phone — so that is all this serves; no
    account, no liability, no identity. `None` where the request names nobody.
    Tenant-scoped by name (hard rule 1); another tenant's id reads as nobody.
    """
    if request_id is None:
        return None
    row = (
        models.ServiceRequest.objects.filter(tenant_id=_tenant_id(), pk=request_id)
        .values("co_applicant_name", "co_applicant_email", "co_applicant_phone")
        .first()
    )
    if row is None:
        return None
    name = (row["co_applicant_name"] or "").strip()
    email = (row["co_applicant_email"] or "").strip()
    phone = (row["co_applicant_phone"] or "").strip()
    if not (name or email or phone):
        return None
    return {"name": name or None, "email": email or None, "phone": phone or None}


# ── CR-179-BRC10 · THE RATE IMPACT REPORT'S TWO CUSTOMERS READS ─────────────
#
# `apps/reports/rate_impact.py` is the only caller, through
# `apps/reports/report_seams.py`. Read-only.

#: The one status class that never took service. `BR-CUS-055`'s vocabulary;
#: every other class — billable, base-only and terminal — was on the books at
#: some point, and the window decides whether that point is in the period.
_NEVER_IN_SERVICE_CLASS = "non_billable"


def accounts_on_units_in_window(unit_ids: Any, start: date, end: date) -> list[dict[str, Any]]:
    """Every account on these units that was open at some point in `[start, end]`.

    `{id, account_no, unit_id, class_code, class_name, opened_at, closed_at}`
    per account, ordered by
    account number. *Open in the period* is the account's own dates —
    `opened_at` on or before `end` (or not recorded) and `closed_at` on or
    after `start` (or still open) — so an account that moved out in March
    counts for a twelve-month window and one that moved in next month does
    not. A `non_billable` account (an application never activated) never took
    service and is not here.

    ⚠ **THE CLASS IS THE ACCOUNT'S OWN `account_type`** — the code a screen
    filters on and the name a person reads (B14 rule 31: never the id).
    """
    ids = [str(one) for one in unit_ids or () if one not in (None, "")]
    if not ids:
        return []
    rows = (
        account_queryset()
        .filter(unit_id__in=ids)
        .exclude(status__behavior_class=_NEVER_IN_SERVICE_CLASS)
        .filter(Q(opened_at__isnull=True) | Q(opened_at__lte=end))
        .filter(Q(closed_at__isnull=True) | Q(closed_at__gte=start))
        .order_by("account_no", "id")
    )
    return [
        {
            "id": str(row.id),
            "account_no": row.account_no,
            "unit_id": str(row.unit_id) if row.unit_id else None,
            "class_code": row.account_type.code if row.account_type_id else None,
            "class_name": row.account_type.name if row.account_type_id else None,
            "opened_at": row.opened_at,
            "closed_at": row.closed_at,
        }
        for row in rows
    ]


def account_type_options() -> list[dict[str, Any]]:
    """The utility's ACTIVE customer classes as `{value: code, label: name}`.

    The same rows `GET /lookups/account_types` serves, in their own sort order,
    so a report's class filter and the account screen's class select list one
    vocabulary (BR-REP-006).
    """
    return [
        {"value": code, "label": name}
        for code, name in models.AccountType.objects.filter(tenant_id=_tenant_id(), active=True)
        .order_by("sort_order", "name", "id")
        .values_list("code", "name")
    ]



# ═══════════════════════════════════════════════════════════════════════════
# CR-185-BRC10 D4 — WHO THE OWNER IS, AND WHICH PROPERTIES ARE THEIRS
# ═══════════════════════════════════════════════════════════════════════════
def owner_properties(
    account_id: Any, *, page: int = 1, per: int | None = None
) -> dict[str, Any] | None:
    """The owner behind one master account, and every master account they hold.

    PO 2026-10-14 (D4): *"one monthly statement with a section per property"*
    — the owner is **the customer who holds master accounts**, and a property
    is one of their master accounts (one per address, `BR-CUS-1010`). The
    report is opened on ANY of the owner's master accounts (the account finder
    is the one search box this product has for them) and this widens it to the
    person: every master account LIVE-linked to the same customer.

    ⚠ **THE LIST IS PAGED IN SQL (`NFR-3`) AND THE IDS ARE ALL RETURNED.** A
    landlord at T5 can hold hundreds of buildings. The page is cut by the
    database; `all_account_ids` is ids only, so the caller can total the WHOLE
    owner rather than the page in front of the clerk.

    `None` ⇒ no such account in this tenant (HR-1: indistinguishable from
    another tenant's). An account that is not a master answers with
    `is_owner_account: False` and no properties — the report says so by name.
    """
    if not _is_uuid(account_id):
        return None
    picked = account_queryset().filter(pk=account_id).first()
    if picked is None:
        return None
    master_kind = services_master_kind()
    if picked.kind != master_kind:
        return {"is_owner_account": False, "owner": None, "total": 0,
                "properties": [], "all_account_ids": []}
    customer_id = primary_customer_id_for_account(picked.id)
    masters = account_queryset().filter(kind=master_kind)
    if customer_id is not None:
        held = models.CustomerAccount.objects.filter(
            tenant_id=_tenant_id(), customer_id=customer_id, ended_at__isnull=True
        ).values("account_id")
        masters = masters.filter(pk__in=held)
        customer = models.Customer.objects.filter(
            tenant_id=_tenant_id(), pk=customer_id
        ).first()
        owner = {
            "customer_id": str(customer_id),
            "name": getattr(customer, "display_name", None),
            "customer_no": getattr(customer, "customer_no", None),
        }
    else:
        masters = masters.filter(pk=picked.pk)
        owner = {"customer_id": None, "name": customer_names_for([picked.id]).get(str(picked.id)),
                 "customer_no": None}
    masters = masters.order_by("account_no", "id")
    total = masters.count()
    all_ids = [str(one) for one in masters.values_list("id", flat=True)]
    page_no = max(1, int(page or 1))
    window = masters if per is None else masters[(page_no - 1) * per : page_no * per]
    rows = list(window)
    premises_ids = {str(row.id): premises_id_for_account(row) for row in rows}
    refs = seams.premises_refs([pid for pid in premises_ids.values() if pid])
    return {
        "is_owner_account": True,
        "owner": owner,
        "total": total,
        "all_account_ids": all_ids,
        "properties": [
            {
                "account_id": str(row.id),
                "account_no": row.account_no,
                "currency": row.currency,
                "premises_id": premises_ids[str(row.id)],
                "property": (refs.get(str(premises_ids[str(row.id)])) or {}).get("address_line"),
            }
            for row in rows
        ],
    }

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-005@bbed56d (slice 3 — the prior-tenancy read BR-CUS-056 compares against; co-packets US-CUS-004@bbed56d · US-CUS-003@bbed56d · EP-CUS-01@a2e1d59 · customers 02-business-rules@f125a9c)
# generated: 2026-08-11 by story-coder (W2 customers slice 2 = the account write path + its API · slice 3 = `last_closed_account_for_unit`) · AMENDED 2026-08-15 by story-coder (tenant custom-fields lane) · AMENDED 2026-08-16 by the balance lane (DEF-127 — the S17/S21 balance and the header roll-up read the LEDGER, not `accounts.balance`; the last-bill cell is served; both are ONE batched read per page)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests -m "not golden and not isolation"✔ · pytest tests -m isolation✔ (sqlite tier) + live-Postgres isolation run✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔
# exceptions: `last_closed_account_for_unit` SKIPS a terminal account carrying no `closed_at` — slice 2 could write exactly that state and "closed on an unknown day" cannot be compared against an incoming start date (BR-CUS-056); the skip is asserted, not assumed · `last_bill_at` · `aging` · `past_due_60_plus` · `plan` all render NULL because billing's `invoices` (W3) and the BR-CUS-029 account plan snapshot do not exist — each is null-with-a-reason rather than a plausible value (metering's `collected_read_count` precedent) · the BR-CUS-053 `plan` FILTER is not declared at all, because filtering by plan needs the same missing snapshot · the customer-name search leg matches `contacts`, not the BR-CUS-054 `customers` entity (PROPOSED-SCHEMA, not built) · the four A18 status SEGMENTS (All/Current/Past due/Closed) are not implemented: Current and Past due are derived from open invoices, so only All and Closed would be answerable and a half-implemented segment set is worse than none — REPORTED · DEF-127: `accounts.balance` is deliberately still UNWRITTEN and is served as `balance_cached` — writing it would rebuild the second source of truth BR-REP-002 forbids · the BR-CUS-053 `balance_gt` chip filters in PYTHON now, because no column holds the figure (the same disposition `apps/payments/outstandings.py` records for its sort) · a row whose balance could not be READ is KEPT by that filter rather than dropped, so a customer is never hidden behind a gap in the books
# AMENDED: 2026-08-24 by the CR-030 W2 ageing lane (tasks 2.3 backend half + 2.4) — the S17 `AGEING` column CR-030 §5.1.2 splits off `STATUS`. `ageing_segments_for` derives BR-CUS-048's four bands from the account's OWN `account_opening_buckets` position, aged forward by calendar days from the cutover as-of date (BR-CUS-016: DERIVED, never stored); one query per PAGE, never one per row; `account_list` filters on it in Python for the reason `balance_gt` does — a WHERE clause would be a SECOND implementation of the band math.
# exceptions (2026-08-24, ageing lane): (1) THE ONE JUDGMENT — a bucket is a BAND and BR-CUS-048's worked sentence ages a POINT ('45 days past due'), so where inside its band a dollar sits is not recorded and the clause is silent on it. This ages from the band's FLOOR (0/31/61/91), the least age the stored data supports, because it is the only reading that can never tell collections an account is worse than the import proves. **REPORTED for a decision-log row and the review ledger — an engineering judgment inside a clause whose status is PROPOSED, not a rule this lane may confirm.** `tests/test_cr030_w2_ageing.py::test_w2_tc7` is what goes red if it is changed silently · (2) the INVOICE half of BR-CUS-016 is still unreadable (billing publishes no `account_aging_state`), so an account whose receivable came from a BILL ages to NULL WITH ITS REASON on `ageing_unavailable` and never to `Current` — a fabricated Current is DEF-127's mistake in a different cell · (3) `aging` (billing's 'Current / 30d past / 60+ past') and `ageing_segment` (BR-CUS-048's four bands) now sit side by side in two different vocabularies; when billing wires its half, ONE vocabulary has to win and that is a ruling, not a lane's merge — REPORTED · (4) `accounts_rollup().past_due_60_plus` is deliberately still NULL: a bucket-derived count would silently UNDERCOUNT every account whose 60+ position came from an invoice, and a wrong 18 is worse than an honest absence (CR-030 task 2.2 owns that tile) · (5) a NEGATIVE bucket raises rather than being aged — BR-CUS-061 makes the buckets debit-only, so such a row cannot lawfully exist; AMENDED 2026-08-24 (DEF-620) — this cited `OQ-065`, which CLOSED on 2026-08-08 as that very rule, so the guard now names BR-CUS-061 and reads as the invariant check it is rather than as a question still waiting on the PO.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


def import_lookup_indexes() -> dict[str, dict[str, str]]:
    """CR-030 W1 — the accounts import target's four lookups, LOWERED → CODE.

    Published here rather than composed in the runner because these are
    customers' vocabularies: the four platform account types (B2 r5 #12's
    SIGNED consumer categories), the tenant's own sub-types and statuses
    (BR-CUS-055), and the tenant's enabled languages (BR-CUS-064).

    ⚠ CODE → CODE, not code → id. The runner stores what this returns and
    `services._validate_account` then resolves the CODE to a row, exactly as it
    does for a hand-typed account. A second resolver between a spreadsheet and a
    validated rule is how the import comes to accept something the wizard
    refuses.
    """
    from apps.customers import models, seams

    def _codes(queryset) -> dict[str, str]:
        return {str(code).lower(): str(code) for code in queryset if code}

    tenant_id = seams.tenant_id() if hasattr(seams, "tenant_id") else None
    subtypes = models.AccountSubtype.objects.all()
    statuses = models.AccountStatus.objects.all()
    # ⚠ `account_types` JOINED THIS LIST ON 2026-09-17 (PO: *"utility can get
    # their own account types"*). It was unscoped because it was a platform
    # table; scoping it is now the difference between "the codes this utility
    # uses" and "every code on the install".
    types = models.AccountType.objects.all()
    if tenant_id is not None:
        subtypes = subtypes.filter(tenant_id=tenant_id)
        statuses = statuses.filter(tenant_id=tenant_id)
        types = types.filter(tenant_id=tenant_id)
    return {
        "account_type": _codes(types.values_list("code", flat=True)),
        "account_subtype": _codes(subtypes.values_list("code", flat=True)),
        "status": _codes(statuses.values_list("code", flat=True)),
        "preferred_language": _codes(seams.tenant_languages() or ()),
    }


# ══════════════════════════════════════════════════════════════════════════
# BR-CUS-103 — THE CUT, PUBLISHED FOR BILLING (DEF-707, 2026-08-25)
# ══════════════════════════════════════════════════════════════════════════
@batch_reads.memoised(copy=True)
def temporary_stop_windows(
    account_id: Any, period_start: Any, period_end: Any
) -> tuple[tuple[Any, Any], ...]:
    """`CR-183-BRC10` T5 — the INCLUSIVE `(first, last)` days this account was
    on a TEMPORARY STOP inside the period. A thin forwarder to
    `temporary_stop.hold_windows`, under the name billing resolves (the
    `selectors` kind every cross-module read of this module goes through).

    ⚠ **`()` MEANS "NO TEMPORARY STOP", NOT "COULD NOT TELL"** — every account
    a clerk put on `vacation_hold` by hand before this CR answers `()` and
    billing leaves it exactly as it was."""
    from apps.customers import temporary_stop

    return temporary_stop.hold_windows(account_id, period_start, period_end)


def service_off_windows(account_id: Any) -> tuple[dict[str, Any], ...]:
    """The date ranges this account had NO service — `disconnects`' own read.

    A THIN FORWARDER, deliberately. The rule and the boundary arithmetic live
    once, in `apps/customers/disconnects.py::service_off_windows`, and this is
    the name billing resolves (`apps.customers.selectors.service_off_windows`)
    because `selectors` is the KIND every cross-module read of this module
    already goes through — DEF-035 is one seam that resolved `services` instead
    and returned None on every call for weeks.

    BR-CUS-103 (PO 2026-08-25, closing OQ-380): base charges STOP at the cut.
    `apps/billing/gather.py` subtracts these days from `service_days` and B4.3's
    frozen `service_days / cycle_days` factor does the rest — no new money math
    exists anywhere for this rule, which is why it could be built at all.

    ⚠ **`()` MEANS "NEVER CUT", NOT "COULD NOT TELL".** Every ordinary account
    answers `()`; a caller that read it as an absence would refuse every bill.
    """
    from apps.customers import activation_windows, disconnects

    cut = disconnects.service_off_windows(account_id)
    # ── `CR-162-BRC10` · BILLING WAITS UNTIL THE UNIT IS ACTIVATED ──────────
    # PO 2026-10-02, ruled B: *"allow it. The account opens, but billing waits
    # until the unit is activated"*. The days between a move-in and the unit's
    # activation are dark in exactly BR-CUS-103's sense, so they ride the same
    # read in the same shape and B4.3's frozen factor prices them as it prices
    # a cut — no new money math (see `activation_windows`). An account on a
    # unit no build touched — every account before CR-162 — adds nothing.
    account = models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id).only(
        "id", "unit_id", "opened_at"
    ).first()
    if account is None:
        return cut
    return tuple(cut) + activation_windows.awaiting_activation_windows(account)


# ── BR-CUS-057's deposit interest (CR-059 CS-20, task 30) ───────────────────
def deposit_interest_accrued(account_id: Any, as_of: date) -> Decimal | None:
    """THE NAME two other modules have resolved for weeks and never found.

    A THIN FORWARDER, on `service_off_windows`' precedent directly above: the
    arithmetic and the whole of BR-CUS-057's reasoning live once, in
    `apps/customers/deposit_interest.py`, and this is the name the seam looks
    for — `selectors` is the KIND every cross-module read of this module goes
    through, and DEF-035 is one seam that resolved `services` instead and
    returned None on every call for weeks.

    ⚠ **`move_out_settlement._deposit_interest` AND `billing.final_bill.
    deposit_credit_for` BOTH RESOLVE THIS BY NAME AND BOTH HAVE BEEN GETTING
    `None`**, which is why an account holding a deposit could not be closed by
    anybody. Neither of them is changing its posture: they still fail CLOSED on
    a `None`, and what changes is that there is now an answer.

    `as_of` is REQUIRED and has no default (BR-TEN-043, gate G6). See the
    engine's docstring: a settlement re-opened tomorrow must show the same
    figure it showed today unless somebody moved the date.
    """
    from apps.customers import deposit_interest

    return deposit_interest.deposit_interest_accrued(account_id, as_of)
# ── CR-075 wave S · the reads runbooks 16 and 19 make ─────────────────────
#
# `13-selector-inventory.md` row **S-9** (*duplicate customers by phone, tax id
# or email under two names*), and the account TYPE `RB-116` groups its movers by.


def duplicate_customer_groups() -> dict[str, Any]:
    """CUSTOMERS THAT LOOK LIKE ONE PERSON — same phone, tax id or email.

    `13-selector-inventory.md` **S-9**, for `RB-119` step 1. The card's own
    stated absence is the constraint this is built under: *"phone numbers are
    encrypted with a blind index, so 'same phone' here means a blind-index
    match. Fuzzy phone matching is not possible on an encrypted column."* So
    this is EQUALITY on `phone_bidx` and `tax_id_bidx` — the two tokens
    `BR-CUS-089` puts a btree on — and equality on a lower-cased contact email,
    which is `citext` and is not encrypted.

    ⚠ **THE MATCHES ARE COUNTED, THE PEOPLE ARE NOT MERGED, AND NO PII CROSSES
    THIS RETURN.** A group carries its customers' NUMBERS and display names —
    what a clerk reads on a merge screen — and never the phone, the tax id or
    the email that matched it: a duplicate report is read by whoever opens the
    runbook, and the matching VALUE is the sensitive half. `matched_on` says
    which of the three it was, which is all a person needs to decide.

    ⚠ **A GROUP OF ONE IS NOT A DUPLICATE AND IS NOT RETURNED.** `having
    count(*) > 1` in the ORM's words, done in Python over the tenant's own rows
    because a `values().annotate()` over three different keys would be three
    queries shaped differently from each other; this is three passes over one
    list.
    """
    tenant_id = _tenant_id()
    rows = list(
        # ⚠ NO `deleted_at` FILTER, AND THE ABSENCE IS THE REASON: `customers`
        # carries no soft-delete column at all (`Contact` and `Address` do).
        # Writing one here would fail at query time rather than silently, which
        # is how this was found — but a reader looking for the usual filter
        # needs to know it is missing rather than forgotten.
        models.Customer.objects.filter(tenant_id=tenant_id).only(
            "id", "customer_no", "display_name", "phone_bidx", "tax_id_bidx", "is_sample"
        )
    )
    facts = {
        str(row.id): {
            "customer_id": str(row.id),
            "customer_no": row.customer_no,
            "name": row.display_name,
            "is_sample": bool(row.is_sample),
        }
        for row in rows
    }
    emails: dict[str, set[str]] = {}
    links = {
        str(link.customer_id): str(link.account_id)
        for link in models.CustomerAccount.objects.filter(tenant_id=tenant_id)
    }
    account_to_customer = {value: key for key, value in links.items()}
    for contact in models.Contact.objects.filter(
        tenant_id=tenant_id, deleted_at__isnull=True
    ).exclude(email__isnull=True):
        address = (contact.email or "").strip().lower()
        customer_id = account_to_customer.get(str(contact.account_id))
        if not address or customer_id is None:
            continue
        emails.setdefault(address, set()).add(customer_id)

    groups: list[dict[str, Any]] = []

    def _collect(kind: str, buckets: dict[str, set[str]]) -> None:
        for token, members in sorted(buckets.items()):
            if len(members) < 2:
                continue
            groups.append(
                {
                    "matched_on": kind,
                    "customers": [facts[one] for one in sorted(members) if one in facts],
                    "count": len(members),
                    # ⚠ THE TOKEN ITSELF NEVER TRAVELS — see the docstring. This
                    # is a stable handle for a screen's row key and nothing else.
                    "group_key": f"{kind}:{len(groups) + 1}",
                }
            )

    by_phone: dict[str, set[str]] = {}
    by_tax: dict[str, set[str]] = {}
    for row in rows:
        if row.phone_bidx:
            by_phone.setdefault(str(row.phone_bidx), set()).add(str(row.id))
        if row.tax_id_bidx:
            by_tax.setdefault(str(row.tax_id_bidx), set()).add(str(row.id))
    _collect("phone", by_phone)
    _collect("tax_id", by_tax)
    _collect("email", emails)
    return {
        "groups": groups,
        "customers_checked": len(rows),
        # Hard-won law 7 — the number beside the blind spot. A tenant whose
        # customers carry no blind index at all cannot be checked on two of the
        # three, and a confident `0 duplicates` over that would be false.
        "customers_with_a_phone_token": len([one for one in rows if one.phone_bidx]),
        "customers_with_a_tax_id_token": len([one for one in rows if one.tax_id_bidx]),
        "emails_checked": len(emails),
    }


def account_types_for(account_ids: Any) -> dict[str, dict[str, Any]]:
    """`{account_id: {type_code, type_name}}` — what a utility calls this account.

    `RB-116`'s *Group by: account type* (Residential · Multi-unit · Irrigation ·
    Municipal). The card records an assumption the source never states — *"the
    grouping on this card needs the field to exist"* — and it does:
    `accounts.account_type_id` is NOT NULL and points at the PLATFORM catalog
    (`r5` #19), so the grouping is real rather than invented.

    ⚠ **THIS IS NOT `rating.rate_change_impact`'s `by_class_unavailable_reason`
    (`OQ-319`).** That read starts from a UNIT PLAN ASSIGNMENT and never reaches
    an account, which is why it cannot group by class; this one starts from the
    accounts a cycle actually billed. Both statements are true of their own
    read, and neither is a correction of the other.
    """
    ids = [one for one in (account_ids or []) if one]
    if not ids:
        return {}
    return {
        str(row.id): {
            "type_code": row.account_type.code if row.account_type_id else None,
            "type_name": row.account_type.name if row.account_type_id else None,
        }
        for row in account_queryset().filter(id__in=ids).select_related("account_type")
    }


def text_opt_in_for(account_ids: Any) -> dict[str, bool]:
    """`{account_id: has the account asked to be texted}` — ONE read.

    `RB-119` step 5's largest group is *"No mobile, or no consent"*, and the two
    halves have different fixes: one is a number nobody has captured, the other
    is a person who has not agreed. `accounts.sms_reminders` is what this
    product holds — the account's own election.

    ⚠ **IT IS AN ELECTION AND NOT A CONSENT RECORD, AND THE DIFFERENCE MATTERS
    TO WHOEVER SENDS THE STORM TEXT.** There is no date, no channel of capture
    and no withdrawal trail behind this boolean, so it answers *has this account
    asked for texts* and never *can we prove they agreed, and when*. A caller
    that needs the second fact does not have it here or anywhere.
    """
    ids = [one for one in (account_ids or []) if one]
    if not ids:
        return {}
    return {
        str(row_id): bool(flag)
        for row_id, flag in account_queryset()
        .filter(id__in=ids)
        .values_list("id", "sms_reminders")
    }


# ── S21 · the master account's UNITS tab (BR-CUS-1094) ──────────────────────
#
# PO 2026-09-23, verbatim: *"show all units with its status what wil be billed
# to master account - can we do that?"*
#
# ⚠ **NOTHING HERE IS STORED AND NOTHING HERE IS NEW ARITHMETIC.** `BR-CUS-1094`
# is a PROHIBITION as much as a rule — *"No column may cache which units a master
# account pays for, because a cached answer is wrong the first time a tenant
# moves in and nothing would go red"* — so this read answers the question the way
# the BILL RUN will answer it, from the same two functions `apps/billing/gather`
# resolves through the seam:
#
#   · `covered_unit_ids(account)`        → what this account's OWN open service
#                                          agreements reach (its common areas,
#                                          `BR-CUS-068`)
#   · `base_charge_only_coverage(account)` → every unit on the premises with NO
#                                          occupying account, which `BR-CUS-170`
#                                          (PO 2026-08-27) and `BR-CUS-1094`
#                                          (PO 2026-09-23) put on this bill
#
# The two sets are disjoint by construction — `base_charge_only_coverage` builds
# itself by EXCLUDING everything `covered_unit_ids` names — which is the same
# property `runs._billed_units` relies on. **A screen that re-derived either one
# would be a second answer to a money question** (`DEF-127`'s shape), and the
# first tenant move-in would make the two disagree.

#: The three payers a unit can have, and they are the screen's whole vocabulary.
UNIT_PAYER_THIS_ACCOUNT = "this_account"
UNIT_PAYER_TENANT = "tenant"
UNIT_PAYER_NOBODY = "nobody"

#: WHY this account pays — the two are different facts and a clerk acts on them
#: differently. A common area is covered by an agreement somebody wrote; a vacant
#: flat is covered by a RULE and stops being covered the day a tenant moves in.
UNIT_BASIS_AGREEMENT = "service_agreement"  # BR-CUS-068 — its own open coverage
UNIT_BASIS_VACANT = "vacant_base_only"  # BR-CUS-170 / BR-CUS-1094

#: WHY nothing is charged although the payer is known. Both are read from the
#: coverage entry billing itself uses, never guessed:
#: `gather._unbilled_unit_tariffs` skips a unit outright on `not has_plan`, and
#: a unit with no service point has no line to raise.
UNIT_NOT_CHARGED_NO_PLAN = "no_plan"
UNIT_NOT_CHARGED_NO_CONNECTION = "no_connection"

MASTER_UNIT_SORTS: tuple[str, ...] = ("label", "unit_no")
MASTER_UNIT_DEFAULT_SORT = "label"
MASTER_UNIT_DEFAULT_DIR = "asc"
#: `billed_to` is this screen's own question and takes the three payer values
#: above; `occupancy` is `BR-MET-036`'s derived answer and takes the same two
#: words metering's own list uses, so one word cannot mean two things.
MASTER_UNIT_FILTERS: tuple[str, ...] = ("billed_to", "occupancy")


def _master_premises_ids(account: models.Account) -> list[Any]:
    """The buildings this master covers — **the SAME order as
    `sub_accounts_for_master` and `premises_scope_for_account`, deliberately.**

    Declared ownership first (`DEF-650`, PO 2026-08-27: *"Premises -> owner =
    Master account"*), the anchor unit's premises for a master nobody has
    declared as an owner. Three answers about one building that disagreed on
    WHICH building it was would be worse than any of them.
    """
    premises_ids = [
        pid for pid in seams.premises_ids_owned_by_account(account.id) if pid not in (None, "")
    ]
    if premises_ids:
        return premises_ids
    anchor = premises_id_for_account(account)
    return [anchor] if anchor is not None else []


def master_unit_billing_page(
    account_id: Any, params: ListParams
) -> tuple[list[dict[str, Any]], int, dict[str, Any]] | None:
    """**EVERY unit at this master's address, its live occupancy, and who its
    bill goes to.** `(one page of rows, the whole set's count, the counts strip)`.

    `None` for an account that is not a master — the same return
    `premises_scope_for_account` uses for the same question, and not an error:
    an ordinary account has no building to answer for.

    ── WHAT EACH ROW SAYS, AND WHERE EVERY WORD OF IT COMES FROM ─────────────

    The UNIT half is metering's own list row (`unit_list_rows`), so this tab and
    the property's Units tab cannot disagree about a label, a meter, an occupant
    or a status. The PAYER half is the two seam reads named in the block comment
    above. **Nothing in between is computed here.**

    ⚠ **THE OCCUPANCY IS DERIVED AT READ TIME, WHICH IS THE POINT OF THE RULE.**
    `units` carries no occupancy column (`BR-MET-036`) and `BR-CUS-1094` forbids
    one being added for this: *"Occupancy is resolved at bill-run start and only
    then."* This screen resolves it at SCREEN-OPEN time by the same test, so it
    shows what a run started now would decide — never a stored answer that was
    true last month.

    ⚠ **IT STATES A PAYER AND NEVER A PRICE.** `BR-CUS-1040` already settles
    that: *"NO PRICE IS STATED — a single what the empty unit will cost figure
    is the rating engine's and nothing publishes a per-unit standing charge
    outside a bill run."* What a unit OWES today is a different question and is
    metering's `owed` column, carried through untouched.

    ⚠ **A VACANT UNIT THAT WILL BE CHARGED NOTHING SAYS SO AND IS NEVER
    SILENT.** `gather._unbilled_unit_tariffs` skips a coverage entry outright
    when `has_plan` is false, and raises no line for a unit with no service
    point — so *"billed to this account"* alone would be a promise the run does
    not keep. Both reasons are read from the coverage entry billing itself uses.
    This is `BR-CUS-1094`'s own clause one screen earlier: *"the refusal must
    name the UNIT, not a count."*

    ── THE COST, STATED RATHER THAN HIDDEN (`NFR-3` / `NFR-5`) ───────────────

    The page is taken in Python over the premises' unit list, exactly as
    `metering.units_page` records for its own derived path and for the same
    reason: `base_charge_only_coverage` answers for the WHOLE premises in one
    call, and slicing before it would mean re-deriving the money rule per page.
    The bound is **units on one building**, never units in the tenant, and
    **there is no cap of any kind here** — `per` clamps to the `IS-2` vocabulary
    and `page` clamps into range, and neither ever refuses a row that exists.

    ⚠ **THE UNIT LIST CAN BE WIDER THAN THE COVERAGE, AND THAT IS DELIBERATE
    RATHER THAN A MISMATCH TO TIDY.** This read lists the units of **every**
    premises this account is the declared owner of (`premises_ids_owned_by_account`,
    the plural, the same read `sub_accounts_for_master` and
    `premises_scope_for_account` use). `base_charge_only_coverage` answers for
    **one** premises — `premises_id_for_account`, the account's own stored
    address — and so, therefore, does the bill run that reads it.

    So a master declared as the owner of TWO buildings sees both buildings here,
    and the second building's empty units come back `payer: nobody`. **That is
    the truth about the next bill and not a bug in this read**: nothing on that
    premises reaches a payer today, which is exactly the fact `BR-CUS-1094` says
    the product must STATE rather than skip. Narrowing this list to the anchor
    premises would hide those units instead, which is the one thing the ruling
    forbids. If billing later covers every owned premises, this list does not
    move and those rows simply change payer.
    """
    account = account_queryset().filter(pk=account_id).first()
    if account is None or account.kind != services_master_kind():
        return None

    premises_ids = _master_premises_ids(account)
    covered = {str(unit_id) for unit_id in covered_unit_ids(account)}
    # The coverage entries carry `has_plan` and `service_point_count`, which are
    # the two facts `gather._unbilled_unit_tariffs` tests before it raises a
    # line. Keyed by unit so a row can read its own.
    vacant_cover = {
        str(entry.get("unit_id")): entry
        for entry in base_charge_only_coverage(account)
        if entry.get("unit_id")
    }

    units = [unit for pid in premises_ids for unit in _units_on_premises(pid)]
    by_id = {str(unit.id): unit for unit in units}
    rows = [_master_unit_row(unit, covered, vacant_cover) for unit in units]

    counts = {
        "units": len(rows),
        "occupied": sum(1 for row in rows if row["occupancy"] == "occupied"),
        "vacant": sum(1 for row in rows if row["occupancy"] == "vacant"),
        "billed_here": sum(1 for row in rows if row["payer"] == UNIT_PAYER_THIS_ACCOUNT),
        "billed_nobody": sum(1 for row in rows if row["payer"] == UNIT_PAYER_NOBODY),
    }

    rows = _master_unit_filtered(rows, params)
    rows = _master_unit_sorted(rows, params)
    total = len(rows)
    start = max(params.page - 1, 0) * params.per
    page = rows[start : start + params.per]
    return _master_unit_with_metering(page, by_id), total, counts


def _master_unit_row(
    unit: Any, covered: set[str], vacant_cover: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """One unit's PAYER answer — the only judgment this module makes here, and
    it is a lookup in two sets billing built.

    ⚠ **THE ORDER OF THESE BRANCHES IS THE RULE AND NOT A STYLE**, and it is
    `OccupantCell`'s order one layer down. The account's OWN coverage is asked
    first, because a common area is never *occupied* and must never read like a
    vacant flat (`BR-MET-101`). Then the live occupancy test, which is the
    signed fact (`BR-MET-036`). Only then the vacancy coverage.

    ⚠ **`occupying_accounts_for_unit` IS THE OCCUPANCY TEST, NEVER
    `closed_at IS NULL`.** It keys off the status's BEHAVIOUR CLASS
    (`BR-CUS-055`), so a closed tenant drops out on the day they close and a
    pending one never appears — which is exactly what a bill run starting now
    would see.
    """
    unit_id = str(unit.id)
    occupant = occupying_accounts_for_unit(unit.id).order_by("created_at", "id").first()
    occupancy = "occupied" if occupant is not None else "vacant"
    row: dict[str, Any] = {
        "unit_id": unit_id,
        "label": getattr(unit, "label", None),
        "unit_no": getattr(unit, "unit_no", None),
        "is_common_area": bool(getattr(unit, "is_common_area", False)),
        "occupancy": occupancy,
        "payer": UNIT_PAYER_NOBODY,
        "payer_basis": None,
        # ⚠ **THE OCCUPYING ACCOUNT'S NUMBER, UNDER METERING'S OWN FIELD NAME.**
        # It is the same fact `unit_list_dict` publishes, and one fact with two
        # names on one row is `DEF-127`'s shape — the `Occupant` cell and the
        # `Billed to` cell would then be reading two spellings of one answer.
        "account_no": None,
        "not_charged": None,
    }
    if unit_id in covered:
        # This account's OWN open service agreement reaches it (BR-CUS-068).
        # It is billed here whether or not anybody occupies it, which is why
        # this branch is asked before the occupancy one.
        row["payer"] = UNIT_PAYER_THIS_ACCOUNT
        row["payer_basis"] = UNIT_BASIS_AGREEMENT
        return row
    if occupant is not None:
        row["payer"] = UNIT_PAYER_TENANT
        row["payer_basis"] = "occupying_account"
        row["account_no"] = occupant.account_no
        return row
    entry = vacant_cover.get(unit_id)
    if entry is None:
        # Vacant, uncovered and absent from the coverage billing builds. The
        # honest answer is that this bill will carry nothing for it, and
        # `BR-CUS-1094` says the run STATES that rather than skipping it.
        return row
    row["payer"] = UNIT_PAYER_THIS_ACCOUNT
    row["payer_basis"] = UNIT_BASIS_VACANT
    if not entry.get("has_plan"):
        row["not_charged"] = UNIT_NOT_CHARGED_NO_PLAN
    elif not entry.get("service_point_count"):
        row["not_charged"] = UNIT_NOT_CHARGED_NO_CONNECTION
    return row


def _master_unit_filtered(rows: list[dict[str, Any]], params: ListParams) -> list[dict[str, Any]]:
    """`q`, `f.billed_to` and `f.occupancy` — every one over DERIVED values, so
    every one is applied here and none of them is an `ORDER BY`'s `WHERE`."""
    filters = params.filters or {}
    term = (params.q or "").strip().lower()
    out = rows
    if term:
        out = [
            row
            for row in out
            if term in str(row.get("label") or "").lower()
            or term in str(row.get("unit_no") or "").lower()
            or term in str(row.get("account_no") or "").lower()
        ]
    billed_to = filters.get("billed_to")
    if billed_to:
        out = [row for row in out if row["payer"] == billed_to]
    occupancy = filters.get("occupancy")
    if occupancy:
        out = [row for row in out if row["occupancy"] == occupancy]
    return out


def _master_unit_sorted(rows: list[dict[str, Any]], params: ListParams) -> list[dict[str, Any]]:
    """The blueprint's own default: **the LABEL leads and sorts** (*"the label
    leads and the unit number sits under it … what changes is which of the two
    the eye meets first, and what the table sorts by"*).

    The tie-break is the unit id, so a building with two units labelled the same
    pages deterministically rather than shuffling between requests.
    """
    key = params.sort if params.sort in MASTER_UNIT_SORTS else MASTER_UNIT_DEFAULT_SORT
    reverse = (params.dir or MASTER_UNIT_DEFAULT_DIR) == "desc"
    return sorted(
        rows,
        key=lambda row: ((str(row.get(key) or "")).lower(), row["unit_id"]),
        reverse=reverse,
    )


def _master_unit_with_metering(
    page: list[dict[str, Any]], units: dict[str, Any]
) -> list[dict[str, Any]]:
    """Fold metering's OWN list row onto the page — **one call for the page, and
    never one per unit** (`DEF-2723`'s shape, `unit_list_rows`' own contract).

    ⚠ **THE UNIT FACTS ARE READ AND NEVER RE-DERIVED.** `unit_type`,
    `floor_label`, `meters`, `occupant`, `owed` and `status` are metering's
    answers under metering's rules, so this tab and the property's Units tab
    draw one fact one way. What this module adds is the PAYER and nothing else.

    ⚠ **THE UNIT ROWS ARE THE ONES ALREADY IN HAND AND ARE NOT RE-FETCHED.**
    `metering.unit_row` raises its 404-never-403 for an id it cannot see, so
    calling it per page row would be one query per unit AND a refusal path on a
    read that has already resolved every one of them.

    An unpublished metering seam leaves the payer half intact and the unit half
    absent, which degrades to *the building could not be described* rather than
    to a wrong description.
    """
    if not page:
        return page
    rows_fn = seams.resolve("metering", "unit_list_rows", kind="selectors")
    if rows_fn is None:
        return page
    ordered = [units[row["unit_id"]] for row in page if row["unit_id"] in units]
    detail = {str(one.get("id")): one for one in rows_fn(ordered)}
    for row in page:
        one = detail.get(row["unit_id"])
        if one is None:
            continue
        row.update(
            {
                "unit_type": one.get("unit_type"),
                "floor_label": one.get("floor_label"),
                "meters": one.get("meters") or [],
                "metered_services": one.get("metered_services") or [],
                "occupant": one.get("occupant"),
                "owed": one.get("owed"),
                "status": one.get("status"),
                # ⚠ **METERING'S OWN DERIVED OCCUPANCY, CARRIED BESIDE OURS AND
                # NEVER INSTEAD OF IT.** Both key off `BR-CUS-055`'s behaviour
                # class — metering through `active_account_for_unit`, this read
                # through `occupying_accounts_for_unit` — so they must agree,
                # and `test_the_two_occupancy_reads_agree` is what goes red if
                # they ever stop. The PAYER is decided by ours, because ours is
                # the one `base_charge_only_coverage` and the bill run use.
                "metering_occupancy": one.get("occupancy"),
            }
        )
    return page
