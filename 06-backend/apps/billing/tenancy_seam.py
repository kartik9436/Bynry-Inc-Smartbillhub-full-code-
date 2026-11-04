# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-01 (bill run — the holiday input to the late-fee grace clock)
#           Screens: S63 (Settings → Reference data → Holiday calendar, where a
#           tenant keeps these rows; this module only READS them)
#           NOTE: no US-ID is cited in this header ON PURPOSE, for the same
#           reason apps/billing/late_fee.py states it: G10 reads a Trace-header
#           US-ID as "this file ships that story's TCs". This file ships one
#           cross-module read that US-BIL-002 depends on, not the story. The
#           story is named in the docstring, where G10 does not read it as a
#           completion claim. Same precedent as late_fee.py / rating_seam.py.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           BR-TEN-039 (the holiday calendar is a tenant Reference-data card,
#           S63 — tenant data, not a platform constant) · BR-BIL-002 (grace mode
#           = calendar OR business days) · BR-BIL-008 (grace length is tenant
#           config) · BR-TEN-043 (event-time law: nothing here reads a clock)
# Tests:    06-backend/tests/test_bil_holiday_seam.py
# Impacts:  apps/billing/late_fee.py (consumes the frozenset this returns as its
#           `holidays` argument)
# ───────────────────────────────────────────────────────
"""billing → tenancy SEAM: the tenant's public-holiday dates, as real dates.

Serves US-BIL-002 (the Balances tab's late-fee candidates) without shipping it.

B1/BR-TEN-013: billing never touches tenancy's ORM. `holiday_calendars` is a
tenancy table (S63 card, BR-TEN-039) and stays one — this module resolves
tenancy's published read AT CALL TIME, the same idiom `apps/billing/gather.py`
uses for rating and metering, so no import binds billing to tenancy's internals.

WHY THIS MODULE EXISTS AT ALL — it is a type conversion, and the conversion is
the whole point. Tenancy publishes the S63 card's payload, which is shaped for
the screen:

    [{"id": "...", "date": "2026-12-25", "label": "Christmas Day"}, ...]

`date` there is an ISO **string**. `late_fee._business_days_between` tests
membership with a `datetime.date` cursor, and

    date(2026, 12, 25) in {"2026-12-25"}   ->  False

So a caller that passed tenancy's payload straight through would skip no
holidays whatsoever, silently, with every existing test still green — which is
exactly the behaviour the PO ruled against on 2026-08-11 (a bill due Thu 24 Dec
2026 with 5 business days' grace charged on Fri 1 Jan, New Year's Day, instead
of the ruled Tue 5 Jan). Hard-won law 2 in its quietest form: the skip would be
BUILT and not WIRED, and nothing would say so. `test_bil_holiday_seam.py` asserts
the membership that fails under the raw payload, so that mistake goes RED.

WHY IT REFUSES INSTEAD OF RETURNING AN EMPTY SET when tenancy has published no
read: an empty calendar and an unreachable calendar are different facts, and
conflating them reinstates the ruled-against behaviour for every caller that
simply had not been updated. A tenant that genuinely keeps no holidays returns
an empty frozenset from a WIRED seam and means it. Hard-won law 3 — the unsafe
option must be the one you type. This mirrors `grace_has_elapsed`'s refusal of
`holidays=None`, and the two refusals are deliberately the same shape.

NOT DONE HERE, deliberately: no date-range filter. A tenant's public holidays
are a handful of rows a year and the grace window is at most 30 days
(BR-BIL-008), so filtering would be an unmeasured optimisation on a set small
enough to hold whole. Tenant scoping is not optional and is not skipped — it
comes from tenancy's own read, which filters on the current tenant under RLS
FORCE (CLAUDE.md hard rule 1); this module adds no query and therefore no way
to lose that scoping.

NOTHING IS SEEDED. No signed document names a default holiday set for this
product, and inventing one (a US federal list, say) would push dates onto every
tenant in a multi-tenant, multi-country product that nobody ratified. An empty
calendar with correct behaviour is honest; a guessed calendar is not.
"""

from __future__ import annotations

from datetime import date
from importlib import import_module
from typing import Any

from apps.billing import seam_batch
from apps.billing.exceptions import BillingConfigError

#: The tenancy read this seam depends on: `apps.tenancy.selectors.holidays()`,
#: the S63 card's list (BR-TEN-039). Named once so the contract is greppable
#: from both sides of the boundary.
HOLIDAY_READ_MODULE = "tenancy"
HOLIDAY_READ_ATTRIBUTE = "holidays"

#: The second tenancy read this module carries: `service_ids_by_code()`, the
#: platform catalog's `{code: id}` (BR-TEN-025). Stage 6 of the bill run needs
#: it to fill `invoice_lines.service_id`, the reviewed cross-module FK
#: BR-BIL-010's revenue map is keyed on. Named here for the same reason the
#: holiday read is: the contract is greppable from both sides of the boundary.
SERVICE_CATALOG_ATTRIBUTE = "service_ids_by_code"

#: The third: `service_names_by_code()`, the same catalog's `{code: name}`.
#: `DEF-2852` — stage 6 stamps the NAME into `bill_payload["services"]` beside
#: the code, so `documents._groups` can head a charge block *Water* instead of
#: the service's UUID. Read at DRAFT time and frozen, never joined at render:
#: BR-BIL-030 says a bill renders from its own locked snapshot, and tc2 of
#: `test_us_bil_022_documents.py` pins the render to two queries so that a
#: renderer reaching for this would go red on the count.
SERVICE_NAMES_ATTRIBUTE = "service_names_by_code"

#: The fifth: `unmetered_service_codes()`, the services this tenant has
#: declared CAPACITY-basis (`BR-RAT-081` · `BR-TEN-1180`). A capacity service's
#: quantity is a COUNT OF THE UNIT'S ASSETS and never a meter read — carts,
#: fire lines, panels — which is a different KIND of fact from a reading, and
#: the billing register is the one place the two arrive in the same cell.
#:
#: ⚠ **IT IS READ TO LABEL A QUANTITY, NEVER TO PRICE ONE.** Nothing in this
#: seam reaches the money path: `measure_consumption._counted_quantity` already
#: owns that decision and is untouched. This says only *which units on this
#: bill came from a count*, so a register can tell `0 cart` — nobody has a cart
#: here — from `0 kgal`, which is a meter that was read and read zero.
CAPACITY_SERVICES_ATTRIBUTE = "unmetered_service_codes"

#: The fourth: `bill_masthead()`, the three strings A19 §1.1 puts at the top of
#: a bill — who sent it, from where, and how to reach them. `DEF-2865`: they were
#: never stamped, so every bill this product issued printed an em-dash for all
#: three. Read at ISSUE and frozen (BR-BIL-030), never joined at render.
MASTHEAD_ATTRIBUTE = "bill_masthead"

#: `CR-172-BRC10` — WHICH LOGO a bill is stamped with (`bill_logo`) and its
#: PNG for drawing (`logo_png_for_documents`). The logo lives in the common
#: document store; billing stamps the stored document's id (BR-TEN-017,
#: BR-BIL-030 *"branding reference"*) and the page reads that write-once object.
LOGO_STAMP_ATTRIBUTE = "bill_logo"
LOGO_PNG_ATTRIBUTE = "logo_png_for_documents"


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one.

    Resolution is getattr-at-call-time, deliberately: the same shape
    `apps/billing/gather.py` and `apps/tenancy/seams.py` use, so the moment a
    lane lands its function every seam call starts using it with no re-wiring
    step, and no import statement binds this module to tenancy's internals.

    ⚠ **CR-051 task 22 · MEMOISED FOR THE LENGTH OF ONE PASS**, exactly as
    `gather._resolve` is and through the same named list. The one seam it
    reaches on that list is `tenancy.service_ids_by_code`, which stage 6 calls
    ONCE PER ACCOUNT to stamp `invoice_lines.service_id` — measured at 979
    calls over 979 accounts for a platform catalogue that is the same answer
    every time.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    if not callable(found):
        return None
    return seam_batch.wrap(module, attribute, found)


def _as_date(value: Any) -> date:
    """One holiday row's date as a `datetime.date`, or refuse.

    Accepts the ISO string tenancy's S63 payload carries and a real `date` (so
    this keeps working if tenancy's read ever hands back dates directly).
    Anything else REFUSES rather than being coerced: a shape this module does
    not understand must not silently become "no holiday on that day", which is
    the failure the whole seam exists to prevent.
    """
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise BillingConfigError(
                f"the tenant holiday calendar carries {value!r}, which is not an "
                "ISO date. The late-fee grace clock cannot skip a day it cannot "
                "read, and skipping nothing would charge the fee early "
                "(PO ruling 2026-08-11)."
            ) from exc
    raise BillingConfigError(
        f"the tenant holiday calendar carries a {type(value).__name__} where a "
        "date was expected. Nothing is guessed — see apps/billing/tenancy_seam.py."
    )


def holiday_dates() -> frozenset[date]:
    """The CURRENT tenant's public holidays, as `datetime.date` objects.

    Feed the result straight to `late_fee.assess_late_fee(holidays=...)`. An
    empty frozenset is a legitimate answer and means "this tenant keeps no
    holiday calendar" — it is a statement, not a fallback.

    Refuses (BillingConfigError) when tenancy publishes no holiday read at all,
    because "unreachable" and "empty" are different facts and only one of them
    is safe to bill on.
    """
    read = _resolve(HOLIDAY_READ_MODULE, HOLIDAY_READ_ATTRIBUTE)
    if read is None:
        raise BillingConfigError(
            f"apps.{HOLIDAY_READ_MODULE}.selectors.{HOLIDAY_READ_ATTRIBUTE} is not "
            "published, so the tenant's public holidays cannot be read. This does "
            "NOT fall back to an empty calendar: business-day grace that skips no "
            "holidays charges the late fee up to four days early and can assess it "
            "ON a public holiday — a bill due Thu 24 Dec 2026 with 5 business days' "
            "grace would be charged Fri 1 Jan instead of the ruled Tue 5 Jan "
            "(PO ruling 2026-08-11)."
        )
    return frozenset(_as_date(row["date"] if isinstance(row, dict) else row) for row in read())


def service_ids_by_code() -> dict[str, str]:
    """`{service_code: service_id}` for the ACTIVE platform catalog.

    Stage 6 writes `invoice_lines.service_id` from this. Until 2026-08-11 it
    wrote NULL, and the consequence was not cosmetic: BR-BIL-010 resolves a
    usage or base line's revenue account from the SERVICE, so every line of
    every real bill was unstampable and the bill refused at issue — a defect
    the issue lane could only report, because stage 6 was another lane's file
    (hard-won law 2: the FK existed, the column existed, and nothing filled it).
    The PO's per-service revenue requirement of the same day is uncomputable
    from `invoice_lines` for exactly the same reason.

    REFUSES rather than answering `{}` when tenancy publishes no such read. An
    empty catalog and an unreachable catalog have the same shape and only one
    of them is safe to bill on — the same posture, and for the same reason, as
    `holiday_dates` above. `{}` would let every line quietly carry no service
    and push the failure to issue time, where the message would name the wrong
    cause.
    """
    read = _resolve(HOLIDAY_READ_MODULE, SERVICE_CATALOG_ATTRIBUTE)
    if read is None:
        raise BillingConfigError(
            f"apps.{HOLIDAY_READ_MODULE}.selectors.{SERVICE_CATALOG_ATTRIBUTE} is not "
            "published, so a bill line cannot name the service it charged for. This does "
            "NOT fall back to an unset service: BR-BIL-010 resolves a usage or base "
            "line's revenue account from the service, so an unset one means the bill "
            "cannot be issued at all and per-service revenue cannot be reported. "
            "Nothing here infers a service from a line's description or its unit — "
            "water and sewer are both metered in kgal."
        )
    return dict(read())


def service_names_by_code() -> dict[str, str]:
    """`{service_code: display name}` for the ACTIVE platform catalog.

    ⚠ **DEGRADES TO `{}` RATHER THAN REFUSING, WHICH IS THE OPPOSITE POSTURE TO
    `service_ids_by_code` ABOVE, AND THE DIFFERENCE IS DELIBERATE.** That read
    refuses because a line with no `service_id` cannot resolve a revenue
    account and the bill cannot be issued at all — an unanswered catalog there
    is a money failure. This one supplies a WORD for a heading. A deployment
    whose tenancy lane has not landed this selector must go on issuing bills;
    what it gets is `documents._groups`'s neutral heading and a recorded
    absence, which is the same treatment `DEF-2852` gives every bill issued
    before the stamp existed.

    **AND IT NEVER FALLS BACK TO THE ID.** *"No name"* is a better bill than a
    UUID — B14 rule 31, and the whole of the defect this seam was added for.
    """
    read = _resolve(HOLIDAY_READ_MODULE, SERVICE_NAMES_ATTRIBUTE)
    if read is None:
        return {}
    return {str(code): str(name) for code, name in (read() or {}).items() if name}


def active_reason_codes() -> tuple[str, ...] | None:
    """The tenant's ACTIVE `reason_codes` (S8 reference data), or None if unreadable.

    The one-time bill's step 1 offers a catch-up or penalty reason from a
    dropdown fed by Settings (design §2, *"Reason code — dropdown from
    Settings"*) and build-plan task A2 checks the posted code against the same
    rows, so a code a tenant deactivated — or one nobody ever created — is
    refused on its field (`billing.oneTime.err.reasonUnknown`) instead of being
    written onto a bill kept for seven years.

    ⚠ **IT IS THE SAME READ THE PICKER USES.** `GET /payments/reason-codes`
    serves `tenancy.selectors.active_reason_codes` to the clerk's dropdown, and
    this reads that function too — a picker and a check built on two copies of
    one list would eventually offer a code the check refuses.

    `None` means tenancy has not published the read, and the caller then checks
    only that a code is present: refusing every reason because a seam is absent
    would stop every catch-up bill on a deployment fault rather than a clerk's.
    """
    read = _resolve(HOLIDAY_READ_MODULE, "active_reason_codes")
    if read is None:
        return None
    return tuple(str(row.get("code")) for row in (read() or ()) if row.get("code"))


def bill_logo() -> dict[str, Any] | None:
    """The logo a bill is stamped with — `{"document_id", "content_type"}` or None.

    DEGRADES like `bill_masthead`: a logo is a picture on a heading, never a
    fact money depends on, so a tenancy that cannot answer leaves the bill
    without one rather than refusing it.
    """
    read = _resolve(HOLIDAY_READ_MODULE, LOGO_STAMP_ATTRIBUTE)
    if read is None:
        return None
    try:
        stamped = read()
    except Exception:  # noqa: BLE001 — a missing picture must never stop a bill
        return None
    return dict(stamped) if stamped else None


def logo_png(document_id: Any) -> bytes | None:
    """The PNG bytes of the logo a bill was stamped with, or None."""
    read = _resolve(HOLIDAY_READ_MODULE, LOGO_PNG_ATTRIBUTE)
    if read is None or not document_id:
        return None
    return read(document_id)


def bill_masthead() -> dict[str, Any]:
    """The utility's name, address and contact — or `{}` while unpublished.

    DEGRADES rather than refusing, like `service_names_by_code` above and for
    the same reason: this supplies WORDS for a heading, not a fact any money
    depends on. A deployment whose tenancy lane has not landed goes on billing
    and its bills print the named absences they print today (`DEF-2865`).

    Values are passed through unchanged, `None` included — a tenant that has
    written no address has written none, and `documents._field` says so with its
    rule beside it. Nothing here composes one.
    """
    read = _resolve(HOLIDAY_READ_MODULE, MASTHEAD_ATTRIBUTE)
    if read is None:
        return {}
    return dict(read() or {})


def capacity_service_codes() -> frozenset[str]:
    """The service codes whose quantity is a COUNT, not a reading — or `frozenset()`.

    ⚠ **DEGRADES TO EMPTY RATHER THAN REFUSING, AND THE DIRECTION IS THE SAFE
    ONE.** `service_names_by_code` above sets the precedent: a read that
    supplies a LABEL degrades, a read that decides MONEY refuses. This one is a
    label. An empty answer means *treat every quantity as a reading*, which is
    exactly what the register did before this seam existed — so a deployment
    whose tenancy lane has not published the selector renders byte-for-byte
    what it rendered yesterday, and nothing on a bill moves.

    ⚠ **`unmetered_service_codes()` IS ALREADY THE NARROW SET THIS NEEDS.** Its
    own docstring: *"being on this list means NO READ IS EVER OWED for this
    service"*, and `BR-TEN-1180` narrowed its filter to `capacity` ALONE
    precisely because that is the basis meaning *the quantity is a count of the
    unit's assets*. A service that is merely unpriced or unmetered by accident
    is NOT on it, which is why this is a rename at the boundary rather than a
    second rule.
    """
    read = _resolve(HOLIDAY_READ_MODULE, CAPACITY_SERVICES_ATTRIBUTE)
    if read is None:
        return frozenset()
    return frozenset(str(code) for code in (read() or ()))


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — carried from the
#         late_fee.py packet this seam serves; no new frozen source is involved)
# generated: 2026-08-11 by story-coder (late-fee holiday lane — PO ruling 2026-08-11 option A) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: `service_ids_by_code` — the catalog read stage 6 needs to fill `invoice_lines.service_id`)
# checklist: A✔ B✔ C✔ D=deferred(not an API surface — a cross-module read) E=deferred(no-frontend-half; the S63 card that WRITES these rows is tenancy's and already ships) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_bil_holiday_seam.py 7 passed✔ · pytest tests/test_gt08_late_fee_grace.py 10 passed✔ · RED PROOF EXECUTED 2026-08-11 (not predicted — the numbers below are the run's own output): the seam was patched to forward tenancy's raw payload unparsed (`row["date"]` instead of `_as_date(row["date"])`) and the file re-run → `4 failed, 3 passed in 12.51s`. FAILED test_holiday_dates_are_real_dates_not_iso_strings — `AssertionError: assert frozenset({'2026-12-25'}) == frozenset({da...026, 12, 25)})` / `Extra items in the left set: '2026-12-25'` / `Extra items in the right set: datetime.date(2026, 12, 25)`. FAILED test_holiday_dates_are_scoped_to_the_current_tenant. FAILED test_an_unreadable_holiday_row_refuses_rather_than_being_dropped — `Failed: DID NOT RAISE BillingConfigError`. FAILED test_the_po_worked_case_end_to_end_through_the_seam — `AssertionError: assert Decimal('8.13') == Decimal('0.00')`, i.e. the fee back ON New Year's Day, which is the defect. Patch reverted; 17 passed across this file + test_gt08_late_fee_grace.py
# exceptions: (1) No production caller feeds this seam yet, and that is PRE-EXISTING, not introduced here — `assess_late_fee` has no production caller at all (billing publishes it as a pure calculation for rating_seam/GT-8; the S31.2 Balances tab that will call it is US-BIL-002, unbuilt). What this module changes is that a B1-legal path to the holidays now EXISTS; before it, late_fee.py's own docstring pointed callers at a direct `apps.tenancy.selectors` import returning ISO strings that silently match nothing. REPORTED rather than papered over. (2) No date-range filter on the read (see docstring) — whole-calendar read, justified by size, not benchmarked. (3) NOTHING IS SEEDED: no signed document names a default holiday set, so tenants start with an empty calendar and the behaviour is correct rather than guessed.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
