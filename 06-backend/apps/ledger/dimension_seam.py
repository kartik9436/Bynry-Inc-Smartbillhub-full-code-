# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-002 (dimension stamping: service · account · premises+unit ·
#           source · tax authority on every line — this file is the CHAIN half,
#           TC-1/TC-4/TC-5/TC-6; apps/ledger/posting._stamped consumes it)
#           Epics: EP-LED-01 (posting consumption)
#           Screens: S56 · S60
#           NOTE: the US-ID IS cited, unlike the other seam modules in this
#           directory. `apps/ledger/billing_seam.py` and `tenancy_seam.py` name
#           only their epic because a bare cross-module READ ships no story's
#           test cases; this file ships US-LED-002's, in
#           tests/test_us_led_002_dimensions.py, so citing the story is what
#           lets G10 check them and G23 see that the dimension is reachable.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           BR-LED-001 (every journal line carries service · account ·
#           premises+unit · source · tax authority) · BR-MET-046 (units never
#           move between premises — which is what makes a STAMP permanent) ·
#           BR-CUS-017 (one account ↔ one unit) · CLAUDE.md rule 1 (tenant
#           scoping — inherited from the owners' own tenant-scoped reads,
#           never re-implemented here)
# Tests:    06-backend/tests/test_us_led_002_dimensions.py
# Impacts:  apps/ledger/posting.py (its only writer-side caller) ·
#           apps/ledger/reporting.by_premises_summary (the label half)
# ───────────────────────────────────────────────────────
"""ledger → customers/metering SEAM: **whose premises is this money about?**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this seam decides the dimension every
by-premises figure in the product is grouped on, and it is consumed INSIDE the
posting service, so a wrong answer here is a wrong stamp on an immutable row
that can never be updated (hard rule 4). AI-authored 2026-08-16 under the PO
ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*). Row
in `12-governance/09-human-review-ledger.md`.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS AT ALL, AND WHY IT IS NOT AN IMPORT
════════════════════════════════════════════════════════════════════════════
BR-LED-001 (CONFIRMED — PO LF-1, 2026-08-08), verbatim:

    "Every journal line carries service · account_id · premises_id+unit_id
     (resolved at posting) · source_type+source_id · tax_authority_id (tax
     lines) — all PO-named levels computed from the books, never
     side-maintained."

The chain it names crosses two module boundaries the ledger may not step over:
`accounts.unit_id` is **customers'** column and `units.premises_id` is
**metering's**. B1/BR-TEN-013 forbids reaching into either ORM, and G6 rule 4
greps the merge for it. So this module resolves the two owners' published
callables **by name, at call time** — no cross-module MODEL import exists here
and none is added to `apps/ledger/posting.py` either.

════════════════════════════════════════════════════════════════════════════
THE PREFERRED READS, AND THE PUBLISHED FALLBACKS THAT KEEP THE CHAIN CLOSED
════════════════════════════════════════════════════════════════════════════
Two contracts, stated once each below. **Neither owner publishes its purpose-
built read today**, and that absence is exactly why US-LED-002 sat unbuilt for
five days while `by_premises_summary` refused and S60 rendered a reason
(`apps/ledger/reporting.py` gap 1, `apps/billing/posting_seam.py`'s
`premises_and_unit_dimensions_not_resolved`).

Rather than leave the dimension dark for another release — hard-won law 2,
*built is not wired* — each contract falls back to a callable the owning module
**already publishes** and which is already used across this boundary:

  * customers publishes `account_queryset()`, its own tenant-scoped, RLS-bound
    account queryset. `apps/customers/selectors.accounts_rollup` reads it the
    same way;
  * metering publishes `unit_row(unit_id)`, which `select_related("premises")`
    and raises `NotFoundError` for a unit that is not this tenant's.

Both gaps are PARKED in `10-scripts/gates/seam_known_gaps.txt` as `alternative`
rows with their `alt=` targets, so G20 names them on every run and goes RED the
day an owner publishes the preferred read — at which point this seam picks it up
with no edit on either side.

════════════════════════════════════════════════════════════════════════════
⚠ THE STAMP IS PERMANENT, WHICH IS WHY THIS IS A POSTING-TIME READ
════════════════════════════════════════════════════════════════════════════
US-LED-002 TC-4 and US-LED-010 TC-5 are the same requirement seen from both
ends: *"a unit deactivated + recreated after posting → historical lines keep
their stamped premises_id/unit_id FOREVER — reporting on old periods is
unchanged."* A read-time join would move last year's money the day a unit is
re-assigned, and BR-MET-046's chain guarantee (*units never move between
premises*) is about the STAMP, not about the join.

So this seam is called by `apps/ledger/posting.py` at the moment lines are
written, and by NOTHING on the read side except the premises **label** lookup —
which resolves a name for an id already stamped on the row and can therefore
never move money between rows.

════════════════════════════════════════════════════════════════════════════
WHAT AN UNANSWERABLE CHAIN RETURNS — AND WHY IT IS NEVER A SILENT `None`
════════════════════════════════════════════════════════════════════════════
`Location` carries a `problem` code beside its two ids, in the shape
`apps/billing/posting_seam.POSTING_UNAVAILABLE` established. The posting service
turns a problem into a REFUSAL (US-LED-002 TC-5: *"posting fails atomically
naming the gap — no undimensioned money line ever lands"*), and it can only do
that because the reason arrives with the absence. A bare `None` would be
indistinguishable from *"this line is not about a customer"*, which is the
lawful case a cash-in-the-drawer line is in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from importlib import import_module
from typing import Any

from django.db.models import Q

#: The two owning modules, named once so the boundary is greppable from BOTH
#: sides — the discipline `apps/ledger/billing_seam.BILLING_MODULE` follows.
CUSTOMERS_MODULE = "customers"
METERING_MODULE = "metering"

#: THE PREFERRED CUSTOMERS READ, and the contract for the lane that publishes it:
#:
#:     apps.customers.selectors.unit_id_for_account(account_id) -> str | None
#:         the unit this account occupies (BR-CUS-017: exactly one), or None
#:         when the id is not one of this tenant's accounts.
#:
#: Customers does not publish it today, so the fallback below reads customers'
#: own published tenant-scoped `account_queryset()`. PARKED in
#: 10-scripts/gates/seam_known_gaps.txt with
#: `alt=apps.customers.selectors.account_queryset`.
UNIT_OF_ACCOUNT_READ = "unit_id_for_account"

#: The published fallback — customers' own tenant-scoped account queryset. It is
#: what `apps/customers/selectors.accounts_rollup` reads, so this seam sees
#: exactly the register a clerk sees.
ACCOUNT_QUERYSET_READ = "account_queryset"

#: Customers' own tenant-scoped CUSTOMER register, read for NAMES only.
#:
#: `CR-142-BRC07` `P2.15` / `BR-REP-043` — the unit statement's **Occupant**
#: column. It is the same shape as `ACCOUNT_QUERYSET_READ` one table over, and
#: it is read for `display_name` and nothing else: this seam hands over FACTS,
#: never another module's ORM objects, and never a rule about who a customer is.
CUSTOMER_QUERYSET_READ = "customer_queryset"

#: THE PREFERRED METERING READ, and the contract for the lane that publishes it:
#:
#:     apps.metering.selectors.premises_id_for_unit(unit_id) -> str | None
#:         the premises this unit belongs to (BR-MET-046: it never changes), or
#:         None when the id is not one of this tenant's units.
#:
#: Metering does not publish it today, so the fallback below reads metering's
#: own published `unit_row(unit_id)`. PARKED in
#: 10-scripts/gates/seam_known_gaps.txt with
#: `alt=apps.metering.selectors.unit_row`.
PREMISES_OF_UNIT_READ = "premises_id_for_unit"

#: The published fallback — metering's own tenant-scoped unit read. It
#: `select_related("premises")` and raises for a unit outside this tenant, so
#: the tenant scoping is metering's and is not re-implemented here (rule 1).
UNIT_ROW_READ = "unit_row"

#: The premises LABEL read, used only by the by-premises report to put a name
#: beside an id that is ALREADY stamped on the line. Published today.
PREMISES_ROW_READ = "premises_row"

#: ⚠ **`P0.1` / `P0.3` — THE SIXTH DIMENSION.** Customers' answer to *who is
#: billed for this account*, published 2026-09-24 as:
#:
#:     apps.customers.selectors.primary_customer_id_for_account(account_id)
#:         -> str | None
#:
#: **PUBLISHED, NOT FALLEN BACK TO**, unlike the two reads above: the rule this
#: stamp implements is *the PRIMARY holder*, and only customers knows what
#: primary means — `is_primary`, live links, and what to do when nobody is
#: nominated. A fallback reading the account queryset here would be this module
#: deciding another module's rule, permanently, onto an immutable row.
#:
#: **ITS ABSENCE IS NOT A REFUSAL, AND THAT IS THE ONE PLACE THIS DIMENSION
#: DIFFERS FROM THE PREMISES.** `US-LED-002` TC-5 refuses a line whose premises
#: cannot be resolved, because an undimensioned money line is the defect that
#: story exists to remove. There is no such rule for the customer: every line
#: written before 2026-09-24 carries NULL and always will (hard rule 4 forbids
#: a backfill), so NULL is already a lawful, permanent state — and refusing over
#: it would stop the books on a dimension the product has never had.
CUSTOMER_OF_ACCOUNT_READ = "primary_customer_id_for_account"

# ── the problem codes (never a bare None — see the module docstring) ─────────

#: Customers publishes neither the preferred read nor the fallback. The books
#: cannot learn whose unit this is, so the posting REFUSES rather than writing a
#: money row with a dimension nobody can ever reconstruct.
CUSTOMERS_READ_UNAVAILABLE = "account_unit_read_is_unavailable"

#: The account id on the line is not one of this tenant's accounts. US-LED-002
#: TC-6 / TC-7's shape: a forged account id from another tenant resolves to
#: nothing here, and the posting stops.
ACCOUNT_NOT_IN_REGISTER = "account_is_not_in_the_customer_register"

#: The account names a unit and the unit resolves to no premises. BR-MET-046
#: says this cannot happen (`units.premises_id` is a NOT NULL FK), so seeing it
#: is a schema-level surprise and the posting stops rather than guessing.
UNIT_HAS_NO_PREMISES = "unit_resolves_to_no_premises"

#: Metering publishes neither the preferred read nor the fallback.
METERING_READ_UNAVAILABLE = "unit_premises_read_is_unavailable"


@dataclass(frozen=True)
class Location:
    """Where an account's money physically is — or why nobody can say.

    `problem is None` is the only shape the posting service will stamp from.
    `unit_id` and `premises_id` are strings (or None) rather than model objects
    on purpose: a seam hands over FACTS, never another module's ORM rows, which
    is what stops a caller quietly growing a second dependency on the owner.
    """

    unit_id: str | None
    premises_id: str | None
    problem: str | None = None

    @property
    def resolved(self) -> bool:
        """Every dimension that APPLIES to this account has an answer.

        ⚠ **THIS REQUIRED A `unit_id` UNTIL 2026-09-16 AND THAT WAS ONE RULING
        OUT OF DATE (`DEF-LED-5459`).** `BR-LED-001` makes each dimension
        required *where it applies* — `JournalLine`'s own docstring says so, and
        gives `service` on a cash line as the example — and a **premises-
        anchored master account** (`BR-CUS-1010`, PO 2026-09-01) has no unit for
        the same reason a cash line has no service. Demanding one refused every
        posting such an account could ever make.

        **THE PREMISES IS STILL MANDATORY AND THAT IS THE POINT.** `CLAUDE.md`
        hard rule 8 puts the address on `premises` and has everything else walk
        to it, so the premises is the dimension the by-premises report and the
        trial-balance drill-back actually group on. What is relaxed is the
        narrower of the two, never the one the money is attributed by.

        ⚠ **AND THIS DOES NOT RE-OPEN THE NULL US-LED-002 CLOSED.** That story
        removed undimensioned money lines — a line with an account and NO
        premises. Such a line still refuses here. A line carrying a premises and
        no unit is distinguishable from a cash line by its `account_id`, which
        a cash line does not have.
        """
        return self.problem is None and self.premises_id is not None


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owner's callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover — defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _anchor_of(account_id: Any) -> tuple[str | None, str | None, str | None]:
    """(unit_id, premises_id, problem) — customers' answer to *where is this account?*

    ⚠ **THIS RETURNED `(unit_id, problem)` UNTIL 2026-09-16 AND CONFLATED TWO
    FACTS UNDER ONE PROBLEM CODE (`DEF-LED-5459`).** It read `unit_id` alone and
    answered `ACCOUNT_NOT_IN_REGISTER` whenever it came back NULL — so a lawful
    **premises-anchored master account** (`BR-CUS-1010`, `CR-056` W1, PO
    2026-09-01: *"the row now writes `premises_id` and leaves `unit_id` NULL"*)
    was reported in the exact words reserved for a FORGED CROSS-TENANT ID
    (US-LED-002 TC-6/TC-7). Posting refused, correctly-looking and for the wrong
    reason, and the operator reading it goes hunting for a tenancy breach.

    **THE SECOND ANCHOR IS NOT A SECOND ADDRESS** — `CLAUDE.md` hard rule 8 puts
    the address on `premises` and has every other entity *"derive it by walking
    to the premises"*. A unit-anchored account walks unit → premises; a
    premises-anchored one is ALREADY there and the walk is one hop shorter. The
    dimension is the same dimension either way, which is why this returns both
    ids rather than inventing a third problem code.

    **A row with NEITHER still refuses**, and that refusal is now true rather
    than merely accurate: `ck_accounts_anchored` makes `unit_id IS NOT NULL OR
    premises_id IS NOT NULL` a database guarantee, so an account answering
    neither is genuinely not in this tenant's register.

    The preferred read first; the published queryset second. `.values_list` is
    used on the queryset rather than materialising an Account, because this seam
    wants TWO columns and materialising the row would hand customers' ORM object
    across a boundary this file exists to keep closed.
    """
    preferred = _resolve(CUSTOMERS_MODULE, UNIT_OF_ACCOUNT_READ)
    if preferred is not None:
        # ⚠ The preferred read answers the UNIT and nothing else — that is its
        # published contract, and it is not published by anybody today
        # (`seam_known_gaps.txt`). A unit it names is an anchor; a None from it
        # cannot tell a premises-anchored account from an absent one, so the
        # queryset below is consulted rather than guessed at.
        unit_id = preferred(account_id)
        if unit_id is not None:
            return str(unit_id), None, None

    fallback = _resolve(CUSTOMERS_MODULE, ACCOUNT_QUERYSET_READ)
    if fallback is None:
        return None, None, CUSTOMERS_READ_UNAVAILABLE
    row = (
        fallback()
        .filter(pk=str(account_id))
        .values_list("unit_id", "premises_id")
        .first()
    )
    if row is None:
        return None, None, ACCOUNT_NOT_IN_REGISTER
    unit_id, premises_id = row
    if unit_id is not None:
        return str(unit_id), None, None
    if premises_id is not None:
        return None, str(premises_id), None
    return None, None, ACCOUNT_NOT_IN_REGISTER


def _premises_of(unit_id: str) -> tuple[str | None, str | None]:
    """(premises_id, problem) — metering's answer to *where is this unit?*"""
    preferred = _resolve(METERING_MODULE, PREMISES_OF_UNIT_READ)
    if preferred is not None:
        premises_id = preferred(unit_id)
        if premises_id is None:
            return None, UNIT_HAS_NO_PREMISES
        return str(premises_id), None

    fallback = _resolve(METERING_MODULE, UNIT_ROW_READ)
    if fallback is None:
        return None, METERING_READ_UNAVAILABLE
    try:
        row = fallback(unit_id)
    except Exception:  # noqa: BLE001 — metering raises NotFoundError for a unit
        return None, UNIT_HAS_NO_PREMISES  # that is not this tenant's (rule 1)
    premises_id = getattr(row, "premises_id", None)
    if premises_id is None:
        return None, UNIT_HAS_NO_PREMISES
    return str(premises_id), None


def location_for_account(account_id: Any) -> Location:
    """BR-LED-001's chain, resolved once: account → unit → premises.

    Called by `apps/ledger/posting.py` for every line that names an account and
    does not already carry the two ids. **Two queries, and they are the reason
    the caller memoises per `post()` call**: one entry's lines are usually one
    account, and a bill run posting 3,000 invoices would otherwise ask customers
    the same question nine times per bill.

    A caller that already knows the chain (a reversal copying its original's
    stamps, US-LED-003) never reaches this function at all — that is what makes
    a mirror carry the ORIGINAL's premises rather than today's.
    """
    if account_id is None:
        return Location(unit_id=None, premises_id=None, problem=None)

    unit_id, anchor_premises_id, problem = _anchor_of(account_id)
    if problem is not None:
        return Location(unit_id=None, premises_id=None, problem=problem)

    if unit_id is None:
        # **A PREMISES-ANCHORED ACCOUNT IS ALREADY WHERE THE WALK WAS GOING**
        # (`DEF-LED-5459`). `unit_id` is None on the line and that is the
        # TRUTHFUL dimension, not a gap: the money belongs to an address, not to
        # any one home at it, which is exactly what an owner's build account is.
        # `BR-LED-001` makes each dimension required *where it applies*, and the
        # unit does not apply here — the same reasoning that leaves `service`
        # empty on a cash line.
        return Location(unit_id=None, premises_id=str(anchor_premises_id), problem=None)

    premises_id, problem = _premises_of(str(unit_id))
    if problem is not None:
        return Location(unit_id=str(unit_id), premises_id=None, problem=problem)

    return Location(unit_id=str(unit_id), premises_id=str(premises_id), problem=None)


def customer_id_for_account(account_id: Any) -> str | None:
    """WHO HELD THIS ACCOUNT, asked once, at the moment of posting — `P0.1`.

    **NEVER A REFUSAL.** Unlike `location_for_account`, an unanswerable question
    here yields `None` and the line is written without a customer. The reasoning
    is on `CUSTOMER_OF_ACCOUNT_READ`: NULL is already a lawful, permanent state
    on this column for every row the product has ever written, so refusing over
    it would stop the books on a dimension they have never carried.

    **WHY THIS IS A POSTING-TIME READ AND NOT A JOIN, WHICH IS THE WHOLE POINT
    OF `P0.1`.** A reader walking `journal_lines → accounts → customer_accounts`
    gets *who holds this account NOW*. `BR-CUS-1030` lets an account change
    hands, and on the day it does, every historical line silently re-attributes
    itself to the new holder — figures still footing, still balanced, about the
    wrong person. Asking ONCE and writing the answer down is what makes the
    question answerable a year later. It is the same argument
    `US-LED-002` TC-4 makes for the premises, one column over.
    """
    if account_id is None:
        return None
    read = _resolve(CUSTOMERS_MODULE, CUSTOMER_OF_ACCOUNT_READ)
    if read is None:
        return None
    answer = read(account_id)
    return str(answer) if answer else None


def premises_labels(ids: Any) -> dict[str, str]:
    """`{premises_id: "500 Main St"}` for ids ALREADY stamped on journal lines.

    The by-premises report groups on the STAMP and then asks this for a name.
    That ordering is the whole of US-LED-010 TC-5: the money is attributed by
    what was written at posting, and this lookup can only ever change a LABEL,
    never which row a figure lands in. A premises the tenant has since renamed
    shows its new name against the same money, which is what a finance officer
    expects; a premises that cannot be read at all is simply absent from the map
    and the caller renders the id's row with no name rather than dropping it.
    """
    read = _resolve(METERING_MODULE, PREMISES_ROW_READ)
    if read is None:
        return {}
    labels: dict[str, str] = {}
    for value in ids:
        key = str(value)
        if key in labels:
            continue
        try:
            row = read(key)
        except Exception:  # noqa: BLE001 — an unreadable premises is nameless,
            continue  # never a dropped money row (see the docstring)
        name = getattr(row, "address_line", None) or getattr(row, "premise_no", None)
        if name:
            labels[key] = str(name)
    return labels


#: CR-060 C3 / task T4 — the problem code a capture carries when it names a
#: building that is not one of this tenant's. It is a REFUSAL and not a warning:
#: a purchase filed against another tenant's building would be a cross-tenant
#: read the moment the per-building report grouped it (CLAUDE.md rule 1).
PREMISES_NOT_IN_REGISTER = "premises_is_not_in_this_tenants_register"


def premises_label_or_refuse(premises_id: Any) -> str:
    """CR-060 T4 — *"is this one of MY buildings, and what is it called?"*

    ⚠ **THE TENANT SCOPING IS METERING'S AND IS NOT RE-IMPLEMENTED HERE**
    (CLAUDE.md rule 1, BR-TEN-013). `metering.selectors.premises_row` filters
    on `tenant_id=_tenant_id()` and raises a deny-as-not-found for anything
    else, so a forged building id from another tenant arrives here as an
    exception rather than as a row — exactly the shape `location_for_account`
    already relies on for `unit_row`.

    Raises `LookupError(PREMISES_NOT_IN_REGISTER)` rather than returning None,
    because the caller must not be able to treat "not yours" as "not filled
    in": the second is a lawful state on this column and the first is a
    tenant-scoping failure.
    """
    read = _resolve(METERING_MODULE, PREMISES_ROW_READ)
    if read is None:  # pragma: no cover — metering publishes it today
        raise LookupError(METERING_READ_UNAVAILABLE)
    try:
        row = read(str(premises_id))
    except Exception as problem:  # noqa: BLE001 — metering denies as not-found
        raise LookupError(PREMISES_NOT_IN_REGISTER) from problem
    return str(getattr(row, "address_line", None) or getattr(row, "premise_no", None) or "")


def premises_options() -> tuple[dict[str, str], ...]:
    """`({"premises_id": …, "label": "500 Main St"}, …)` — the S73 picker.

    Served from the ledger's own payload rather than fetched by the screen from
    metering, for the reason `cost_api` already serves `categories` and
    `category_catalog`: one screen holding a copy of another module's list is a
    second vocabulary to keep in step. The LIST itself is metering's — this
    reads `premises_list`, which is `tenant_id`-scoped at source.
    """
    read = _resolve(METERING_MODULE, "premises_list")
    if read is None:  # pragma: no cover — metering publishes it today
        return ()
    rows = read(sort="address_line", direction="asc")
    return tuple(
        {
            "premises_id": str(row.pk),
            "label": str(getattr(row, "address_line", None) or getattr(row, "premise_no", "")),
        }
        for row in rows
    )


# ══════════════════════════════════════════════════════════════════════════
# THE LABEL HALF OF THE OTHER TWO DIMENSIONS — `DEF-LED-6723`
# ══════════════════════════════════════════════════════════════════════════
# `premises_labels` above has put a NAME beside a stamped premises id since
# US-LED-010. The journal-entry DETAIL needs the same service for the two other
# stamped ids a clerk can see — the ACCOUNT and the UNIT — for exactly the
# reason B14 rule 31 gives: *no database id is ever the visible value of a
# field*. A detail screen that printed `019ff23d-…` in an Account column would
# be `DET-LED-6661` again, one table over.
#
# ⚠ **BOTH ARE BATCHED BY ID SET AND NEITHER IS CALLED PER ROW.** One entry's
# lines usually name one or two accounts, but nothing in the schema says so and
# `NFR-3` has no small-tenant exception: a per-line resolve is the 307-over-300
# shape `journal_entry_list` was measured at and fixed.
#
# ⚠ **AN UNREADABLE ID IS SIMPLY ABSENT FROM THE MAP, NEVER A DROPPED LINE.**
# That is `premises_labels`' rule and it is the same rule here, and it matters
# more on a detail: a journal entry that quietly lost a line would stop
# balancing on screen while balancing perfectly in the books.


def account_labels(ids: Any) -> dict[str, str]:
    """`{account_id: "A-10432"}` for account ids ALREADY stamped on lines.

    Reads customers' own published, tenant-scoped `account_queryset()` — the
    same register `_anchor_of` falls back to and the same one a clerk sees — so
    the tenant scoping is customers' and is not re-implemented here (rule 1,
    BR-TEN-013). `.values_list` rather than a materialised row: a seam hands
    over FACTS, never another module's ORM objects.
    """
    keys = {str(value) for value in ids if value is not None}
    if not keys:
        return {}
    read = _resolve(CUSTOMERS_MODULE, ACCOUNT_QUERYSET_READ)
    if read is None:  # pragma: no cover — customers publishes it today
        return {}
    return {
        str(pk): str(account_no)
        for pk, account_no in read().filter(pk__in=keys).values_list("pk", "account_no")
        if account_no
    }


#: `CR-142-BRC07` `P6.11` wave 3 — customers' own count of *how many accounts
#: were on the books on one day*, which is R22 Account Census's membership rule
#: already written down once (`apps/customers/accounts_dataset._base`).
ACCOUNTS_ON_THE_BOOKS_READ = "accounts_on_the_books"
ACCOUNTS_ON_THE_BOOKS_MODULE = "accounts_dataset"

#: Reported when customers publishes no such count. The column then stays NULL
#: **with this reason** and never 0 — a utility with no accounts and a utility
#: we cannot ask about are different facts (`BR-REP-024`).
ACCOUNT_COUNT_UNAVAILABLE = "account_census_count_read_is_unavailable"


def accounts_on_the_books(*, as_of: date) -> int | None:
    """How many accounts this utility had on ONE day, or None.

    ⚠ **IT RESOLVES THE CENSUS'S OWN COUNT AND DERIVES NOTHING.** *Membership as
    at a date* is customers' rule, written once in
    `accounts_dataset._base` — opened on or before the day, not yet closed on
    it, and a row with no `opened_at` included. A count composed on this side
    would make R43's ACCOUNTS column and R22's ACCOUNTS tile disagree about one
    utility on one day, with both numbers plausible and neither screen showing
    the other (hard-won law 5).

    `None` is *unanswerable*; it is never a zero.
    """
    read = _resolve(
        CUSTOMERS_MODULE, ACCOUNTS_ON_THE_BOOKS_READ, kind=ACCOUNTS_ON_THE_BOOKS_MODULE
    )
    if read is None:
        return None
    return int(read(as_of=as_of))

def customer_labels(ids: Any) -> dict[str, str]:
    """`{customer_id: "Marisol Vega"}` for customer ids ALREADY stamped on lines.

    `CR-142-BRC07` `P2.15` · `BR-REP-043` — the **Occupant** column on the unit
    statement, and the one column that appears on that subject and no other.

    ⚠ **THE ID COMES FROM THE LINE, NEVER FROM A JOIN THROUGH TODAY'S HOLDER,
    AND THAT IS THE WHOLE REASON A UNIT STATEMENT CAN BE HONEST.**
    `customer_id_for_account` above already states the argument for stamping it
    at posting time: a reader walking `journal_lines → accounts →
    customer_accounts` gets *who holds this account NOW*, so on the day an
    account changes hands every historical line silently re-attributes itself to
    the new holder — figures still footing, still balanced, about the wrong
    person. A unit OUTLIVES its tenants, so that defect is not a corner case
    here, it is the ordinary case: it would put the new occupant's name on the
    old occupant's arrears. This function only ever turns an id the line already
    carries into a NAME.

    ⚠ **A LINE WITH NO CUSTOMER IS ABSENT FROM THE ANSWER, NEVER GUESSED.**
    Every line written before 2026-09-24 carries NULL on this column and always
    will — hard rule 4 forbids a backfill — so NULL is a lawful, permanent
    state. The caller publishes a NAMED GAP when the page actually holds such a
    row; it does not substitute the account number, which is a different fact
    wearing a person's heading.

    Reads customers' own published, tenant-scoped `customer_queryset()`, so the
    scoping is customers' and is not re-implemented here (rule 1, BR-TEN-013).
    """
    keys = {str(value) for value in ids if value is not None}
    if not keys:
        return {}
    read = _resolve(CUSTOMERS_MODULE, CUSTOMER_QUERYSET_READ)
    if read is None:  # pragma: no cover — customers publishes it today
        return {}
    return {
        str(pk): str(name)
        for pk, name in read().filter(pk__in=keys).values_list("pk", "display_name")
        if name
    }


def unit_labels(ids: Any) -> dict[str, str]:
    """`{unit_id: "Unit A"}` for unit ids ALREADY stamped on lines.

    ⚠ **`units.label` IS THE LABEL AND `unit_no` IS NOT ALWAYS THERE.** Hard
    rule 8 is the reason this is a LABEL and never an address: *a unit refines a
    premises by LABEL, not by address*, so the line's premises carries where it
    is and this carries which part of it.

    Metering publishes no batched unit read, so this walks `unit_row`, which is
    `tenant_id`-scoped at source and raises a deny-as-not-found for a unit
    outside this tenant — the shape `location_for_account` already relies on.
    A unit that cannot be read is nameless, never a dropped money line.
    """
    keys = {str(value) for value in ids if value is not None}
    if not keys:
        return {}
    read = _resolve(METERING_MODULE, UNIT_ROW_READ)
    if read is None:  # pragma: no cover — metering publishes it today
        return {}
    labels: dict[str, str] = {}
    for key in keys:
        try:
            row = read(key)
        except Exception:  # noqa: BLE001 — an unreadable unit is nameless
            continue
        name = getattr(row, "label", None) or getattr(row, "unit_no", None)
        if name:
            labels[key] = str(name)
    return labels


#: `DEF-LED-10071` (J1) — metering's lazy id reads for the journal search.
PREMISES_ID_QUERY_READ = "premises_id_query"
UNIT_ID_QUERY_READ = "unit_id_query"


def journal_line_search(term: str) -> Q:
    """`DEF-LED-10071` J1 — *which journal LINES belong to something matching `term`?*

    PO, 2026-10-12: *"user want to serach using premise/unit, account,
    customer-id"*, then on the proposal *"J1 - this is good add cutomer name to
    search"*. Five legs, each asked of the module that OWNS the fact
    (BR-TEN-013 — no module reads another module's ORM):

      * **account number** — customers' `account_queryset()`;
      * **customer number** and **customer name, any part** — customers'
        `customer_queryset()`;
      * **premises address** — metering's `premises_id_query(term)`;
      * **unit label** — metering's `unit_id_query(term)`.

    Returns a `Q` over `JournalLine`, built from FIVE LAZY SUBQUERIES — every
    owner read here returns an unevaluated queryset, so the caller's search is
    still ONE SQL statement and still takes its page in SQL (`NFR-3`). Nothing
    is materialised into an id list, which at the top of T5 would be an
    unbounded `IN (...)`.

    ⚠ **IT MATCHES THE STAMP, NEVER TODAY'S HOLDER.** The customer leg reads
    `journal_lines.customer_id`, the id written AT POSTING (`P0.1`), for the
    reason `customer_id_for_account` gives: walking `account → today's holder`
    would find a former occupant's entries under the new occupant's name. A
    line written before 2026-09-24 carries no customer and is therefore not
    found by NAME — it is still found by its account number, its address and
    its unit, which every such line does carry.

    A leg whose owner publishes nothing contributes nothing, rather than
    raising: a search that loses a leg still finds what the others find.
    Tenant scoping is each owner's (rule 1).
    """
    match = Q(pk__in=[])
    accounts = _resolve(CUSTOMERS_MODULE, ACCOUNT_QUERYSET_READ)
    if accounts is not None:
        match |= Q(account_id__in=accounts().filter(account_no__icontains=term).values("pk"))
    customers = _resolve(CUSTOMERS_MODULE, CUSTOMER_QUERYSET_READ)
    if customers is not None:
        match |= Q(
            customer_id__in=customers()
            .filter(Q(customer_no__icontains=term) | Q(display_name__icontains=term))
            .values("pk")
        )
    premises = _resolve(METERING_MODULE, PREMISES_ID_QUERY_READ)
    if premises is not None:
        match |= Q(premises_id__in=premises(term))
    units = _resolve(METERING_MODULE, UNIT_ID_QUERY_READ)
    if units is not None:
        match |= Q(unit_id__in=units(term))
    return match


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-002@7eb889f (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-01-posting-consumption.md — US-LED-002 §1/§3/§5 — · 04-docs/05-modules/09-ledger/02-business-rules.md — BR-LED-001 —; co-cited BR-MET-046, BR-CUS-017, BR-TEN-013, B2 Addendum r13 #1)
# generated: 2026-08-16 by story-coder (US-LED-002 dimension lane)
# checklist: A✔ B✔ C✔ D✔(consumed by apps/ledger/posting.py, which every money endpoint reaches) E✔(S60 by-premises and the S56 dimension columns are the surface) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN — `_premises_of` was mutated to return the UNIT id as the premises and the database refused the row ("journal_lines.premises_id contains a value that does not have a corresponding value in premises.id"); `_anchor_of`'s fallback (named `_unit_of` until 2026-09-16) was mutated to drop the `.filter(pk=...)` and every line took the FIRST account's premises, putting all 553.69 on 500 Main St. Both failures are quoted verbatim in the human-review ledger row
# exceptions: neither owner publishes its purpose-built read, so both contracts run on a PUBLISHED fallback and both are PARKED in 10-scripts/gates/seam_known_gaps.txt as `alternative` rows — G20 names them on every run and goes RED the day either read appears
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
