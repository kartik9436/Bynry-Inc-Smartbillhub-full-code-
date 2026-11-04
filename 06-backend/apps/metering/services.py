# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-001 (S14 premises writes — create/edit/deactivate/delete) ·
#           US-MET-002 (S15 unit writes; occupancy is DERIVED, never written) ·
#           US-MET-003 (S16 guided add: premise + unit + meter grid + default
#           plan) · US-MET-004 (S16 bulk: premises CSV · unit pattern · units
#           CSV) · US-MET-005 (S26/S27 read-only ops tabs — no writes here) ·
#           US-MET-006 (S8 Routes & Cycles config + route membership) ·
#           US-MET-013 (S29 Dispute — the marker BR-MET-024 defines and DEF-046
#           found had no writer anywhere)
#           Screens: S14, S15, S16, S26, S27, S8, S29
# Rules:    BR-MET-001 · BR-MET-002 · BR-MET-003 · BR-MET-004 · BR-MET-005 ·
#           BR-MET-006 · BR-MET-007 · BR-MET-008 · BR-MET-009 · BR-MET-010 ·
#           BR-MET-031 · BR-MET-033 · BR-MET-034 · BR-MET-035 · BR-MET-036 ·
#           BR-MET-037 · BR-MET-038 · BR-MET-039 · BR-MET-040 · BR-MET-041 ·
#           BR-MET-042 · BR-MET-043 · BR-MET-044 · BR-MET-046 · BR-MET-047 ·
#           BR-MET-048 · BR-AST-028 · BR-TEN-036 · BR-MET-024 (dispute =
#           marker + reason; the account is HELD from the bill run until a
#           System Admin clears — OQ-043 closure, PO R6)
# Tests:    06-backend/tests/test_us_met_001_002_lists.py ·
#           test_us_met_003_wizard.py · test_us_met_004_bulk.py ·
#           test_us_met_005_006_routes_cycles.py (schema half: test_w1_models.py) ·
#           test_us_met_quantity_seams.py (the two published quantity seams) ·
#           test_us_met_013_tc_dispute.py (record · hold · clear)
# Impacts:  apps/metering/api.py · apps/metering/selectors.py · apps.assets
#           (service_point + inline asset creation seam) · rating unit plan
#           history seam · J2 steps 1–3 handoff (unit exists, occupancy derived)
# ───────────────────────────────────────────────────────
"""metering service layer — the ONLY write path into this module's tables
(LAW 0 / B8: api thin → services sole writer → selectors read).

Cross-module calls go through apps/metering/seams.py exclusively (B1) — this
module never imports another module's models. Every write lands its BR-MET-048
audit row through core.audit (BE-03); every refusal is a catalog exception
(BE-02). No money is computed anywhere in this module (the plan panels store a
reference and render rating-owned values — US-MET-003 §7).

Eng dispositions recorded in the build report (not silently resolved):
- premise_no / unit_no allocate from the tenant number series (BR-MET-001).
  ✔ **RESOLVED 2026-08-17 by CR-005** — this entry used to read *"EP-TEN-08 /
  BE-06 KNOWN_SERIES define NO 'premises' or 'unit' series and tenant
  provisioning seeds no row for them"*, which is why every premises and unit
  this module created carried a NULL number. Both series now exist
  (`core.numbering.PREMISES` = `P-{00000}`, `UNIT` = `U-{00000}`, and
  `READ_BATCH` = `RB-{YY}{MM}-{0000}` for the batches below), are seeded at
  provisioning, and are editable by a System Admin on S8 → Numbering. **The
  refusal path stays and is still correct**: a tenant provisioned before that
  date has no row until `manage.py seed_demo --tenant <subdomain>` runs, and for
  it the row is still created with a NULL number plus an explicit
  `numbering_series_missing` warning — never an invented number, never a silent
  blank.
- Unit DEACTIVATION uses `units.deleted_at` because US-MET-002 §5 forbids a
  stored unit status column (occupancy/status are display-derived). Premises
  deactivation uses `premises.status = inactive` per US-MET-001 §5.
- `unit_plan_assignments` history rows are RATING-owned (B2 r16 #6); the
  metering half of an assignment commits and the response reports
  `history_recorded: false` while the rating seam is unwired.
- premises_types is a metering-hosted Reference-data list (BR-MET-034) but
  tenancy's LOOKUP_LISTS registry has no 'premises_types' key, so it cannot be
  registered as a /lookups list today — it is seeded and served through this
  module. Reported.
"""

import logging
import time
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

# ⛔ **`IntegrityError` AND `DataError` ARE IMPORTED FOR `commit_read_batch`'s
# PER-ROW SAVEPOINT (CR-054 task 14, BR-MET-940).** In PostgreSQL a failed
# statement poisons the WHOLE transaction — every later query answers
# `current transaction is aborted, commands ignored until end of transaction
# block` — so `except IntegrityError: continue` is not merely untidy, it CANNOT
# WORK: the next row's first read would fail and the batch would be lost at
# COMMIT anyway. **The nested `transaction.atomic()` around each `_post_row` is
# a SAVEPOINT, and it is the only thing that makes the catch legal.** It is not
# the tidy option and it must not be "simplified" away — `config/settings/
# test.py` hardcodes in-memory SQLite, which has no aborted-transaction state,
# so the broken version passes this entire suite green on every machine
# (CLAUDE.md hard-won law 14; `import_runs`' own note says the same thing about
# the same trap, one importer over).
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DataError, IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.metering import (
    completeness,
    counted_reading,
    estimation,
    high_consumption,
    import_progress,
    models,
    monthly_usage_service,
    period_engine,
    quantities,
    quantity_display,
    read_import,
    read_rejects,
    register_units,
    schedule,
    seams,
    selectors,
    submeter_reconciliation,
    validation,
    write_modes,
)
from core import audit as core_audit
from core import dbfields as core_dbfields
from core import errors
from core import jobs as core_jobs
from core import numbering as core_numbering
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, EXECUTIVE, SYSTEM_ADMIN, require_role

logger = logging.getLogger("smartbillhub.metering")

# BR-MET-001 / US-MET-002 §5: the tenant series keys these tables draw from.
# Neither key exists in BE-06 KNOWN_SERIES nor in tenancy's provisioning
# defaults — see the module docstring disposition.
PREMISES_SERIES = "premises"
UNIT_SERIES = "unit"

# BR-MET-034 (PO PU-1): the SEEDED premises types, tenant-extensible.
SEED_PREMISES_TYPES: tuple[tuple[str, str], ...] = (
    ("apartment_complex", "Apartment complex"),
    ("commercial_building", "Commercial building"),
    ("single_family", "Single-family"),
    ("mixed_use", "Mixed-use"),
    ("mobile_home_park", "Mobile-home park"),
    # CR-010 item 4 (PO 2026-08-17, verbatim: *"you can alos make them
    # Govtment building also"*) — BR-MET-034 amended 5 → 6 the same commit.
    ("government_building", "Government building"),
)

# ══════════════════════════════════════════════════════════════════════════
# `BR-MET-1179` — A COMMON AREA IS **OPTIONAL ON EVERY PREMISE TYPE, AND NEVER
# PRE-SELECTED.** PO ruling 2026-09-21: *"build this rule - no common area for
# single family or related classes"*, corrected the same day in the PO's own
# words: *"i said Comemrcial Building also Common area is optional not
# mandetory , I did not say No common area"*.
# ══════════════════════════════════════════════════════════════════════════
#
# ⛔ **THERE IS NO REFUSAL HERE AND THERE MUST NOT BE ONE.** This block briefly
# held a four-code list — `single_family`, `mobile_home_park`,
# `commercial_building`, `government_building` — that refused a shared unit on
# those types BY NAME. **The PO never said that.** The list came from a
# tick-box question that asked *"which types should have no common area at
# all?"*, and four ticks were recorded as a prohibition rather than as *not
# mandatory*. **No premise type forbids a common area. Nothing is refused for
# having one.**
#
# ⚠ **WHAT THE RULING IS ACTUALLY ABOUT IS THE DEFAULT, AND THAT LIVES ON THE
# SCREEN.** The trap the acceptance walk found is that New Connect's step 3
# opened with *Include a common-area unit* ALREADY TICKED and no unit numbers
# typed, so a clerk building a house carried on and got **one common area and
# no dwelling at all**. `newConnectShared.tsx` no longer pre-selects it and the
# wizard refuses a build with no DWELLING. **The defect was the pre-tick, not
# the possibility.**
#
# ⚠ **AND THE FACT THAT INVERTS EVERYONE'S INTUITION, KEPT HERE SO NOBODY
# REASONS FROM TYPE NAMES AGAIN:** measured on the seeded demo, 79 properties
# hold exactly ONE common area — and it is on a `commercial_building` with 31
# units, while all three `apartment_complex` rows have none. The type everyone
# assumes needs one has none in our own data.
#
# **So this file enforces nothing about premise type and common areas.** The
# rule is a DEFAULT, it is stated in `BR-MET-1179`'s row, and it is built where
# defaults live.


# US-MET-001 §5 status set (draft from Save-draft; deactivate → inactive).
PREMISES_STATUSES = ("draft", "pending", "active", "inactive")
# US-MET-002 §5 unit-type option set (5 options) — since CR-010 A-4 (PO
# 2026-08-17: *"this is correct"*, BR-MET-084) this tuple is the LEGACY
# FALLBACK, not the law: the allowed set lives in the tenant's own
# `unit_types` rows (seeded from SEED_UNIT_TYPES below), and `_resolve_
# unit_type` consults the table FIRST. The tuple stays so that (a) a tenant
# with no rows — provisioned before the table, or with the S111 toggle off —
# can still create units, and (b) every value ever stored remains valid.
UNIT_TYPES = (
    "residential",
    "residential_submetered",
    "commercial",
    "commercial_master",
    "common_area",
)

# BR-MET-084 — the ratified seed rows for the `unit_types` table (CR-010 A-4).
# Codes are US-MET-002 §5's option set verbatim; display names are the
# product's own established copy (the `metering.units.type.*` catalogue
# entries every unit screen has rendered since W1) — no new naming invented.
# All five seed `is_system` (BR-TEN-036). Single ratified source: the
# platform fixture deliberately carries no `unit_types` entries (the DEF-026
# premises_types posture — one copy of the law, nothing to drift).
SEED_UNIT_TYPES = (
    ("residential", "Residential"),
    ("residential_submetered", "Residential · sub-metered"),
    ("commercial", "Commercial"),
    ("commercial_master", "Commercial · master"),
    ("common_area", "Common area"),
)
# US-MET-006 §5: the modal offers walk/drive; AMI routes arrive via the B7 seam.
ROUTE_TYPES = ("walk", "drive", "ami")

# The BR-MET-005/038 caps (10 MB · 10,000 rows · 3,000 units per run) live in
# apps/metering/importers.py — one source of truth, enforced where parsing
# happens rather than restated here.


# ── shared plumbing (same shape as apps/tenancy/services.py) ────────────────
def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _audit(
    actor: Any,
    action: str,
    entity_type: str,
    entity_id: Any,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """BR-MET-048: EVERY premises/unit/route/cycle change writes who/when/
    before→after through BE-03."""
    core_audit.write_row(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before=before,
        after=after,
    )


def _field_error(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _refuse_fields(field_errors: list[dict[str, Any]]) -> None:
    if field_errors:
        raise errors.ValidationError(
            field_errors[0]["code"],
            message_key=field_errors[0]["message_key"],
            params=field_errors[0]["params"],
            field_errors=field_errors,
        )


def _payload_dict(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="metering.payload_not_object")
    return payload


def _text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


#: ── 2026-09-17 · `DEF-INT-5629` · `BR-MET-1173` ─────────────────────────────
#: The GIS key history and the verified stamp — what `gis_parcels._persist`
#: writes on a premises and on a unit, and the only fields in either validator
#: that arrive from a RUN rather than from a form.
#:
#: ⚠ **THE TWO INSTANTS ARE PASSED THROUGH AND NOT PARSED FROM A CLERK'S TEXT.**
#: The one writer hands a `datetime` (`timezone.now()`); a string reaching here
#: is a client calling `PATCH /premises/{id}` by hand, and it is refused rather
#: than coerced, because guessing a timezone for a stamp that answers *when did
#: the City last agree this row exists* is a wrong answer nobody can see.
_GIS_STAMP_FIELDS = ("gis_key_changed_at", "gis_verified_at")
_GIS_KEY_HISTORY_FIELDS = ("gis_parcel_id_was", "gis_point_id_was")


def _gis_run_fields(payload: dict[str, Any], out: dict[str, Any], fe: list[dict[str, Any]]) -> None:
    """Copy the reconciliation run's own fields into the cleaned payload.

    ⚠ **BEING IN `known` IS NOT ENOUGH AND THAT IS `DEF-MET-5604`'s WHOLE
    SHAPE.** `_validate_premises` builds `out` field by field, so a name added
    to `known` and to nothing else is ACCEPTED, answers 200, and is never
    written — the silent drop `DEF-836` records on a list filter. Every field
    this function accepts is copied here, and `tests/test_cr115_run_now.py`
    asserts the round trip rather than the acceptance.
    """
    for field in _GIS_KEY_HISTORY_FIELDS:
        if field in payload:
            out[field] = _text(payload[field], 120)
    for field in _GIS_STAMP_FIELDS:
        if field not in payload:
            continue
        value = payload[field]
        if value is None or isinstance(value, datetime):
            out[field] = value
        else:
            fe.append(_field_error(field, errors.VAL_FORMAT, "metering.unknown_field"))
    if "gis_verified" in payload:
        out["gis_verified"] = bool(payload["gis_verified"])


def _allocate_number(series: str, warnings: list[dict[str, Any]]) -> str | None:
    """BR-MET-001 numbering. A missing series row is REPORTED, never faked."""
    try:
        return core_numbering.next_number(series, seams.tenant_today())
    except core_numbering.NumberingError:
        warnings.append({"code": "numbering_series_missing", "series": series})
        return None


def _highest_number_in_use(series_format: str, values: Any, issue_date: Any) -> int:
    """The largest counter value the tenant's CURRENT format would have had to
    stand at to write any number already in this column — 0 when none of them
    could have come from this format at all.

    `sequence_of` returns None for a number this format cannot produce, and
    those are skipped rather than guessed at: `SCW-U-001` is not a `U-{00000}`
    number at any counter value, so it can never collide with one and must not
    drag the counter anywhere (BR-TEN-035 — gaps are fine, but an unnecessary
    jump of 300 is still a lie about what has been issued).
    """
    highest = 0
    for value in values:
        sequence = core_numbering.sequence_of(series_format, value, issue_date)
        if sequence is not None and sequence > highest:
            highest = sequence
    return highest


def _allocate_unused_number(
    actor: Any,
    series: str,
    warnings: list[dict[str, Any]],
    *,
    model: Any,
    field: str,
    case_insensitive: bool = False,
) -> str | None:
    """🔒 HUMAN-REVIEW-PENDING (numbering, DEF-577 — row in 12-governance/09-human-review-ledger.md).

    `_allocate_number`, plus THE INVARIANT IT NEVER HELD: a series must never
    hand out a number that already exists.

    ⚠ **`case_insensitive` EXISTS BECAUSE THE CALLER'S OWN DUPLICATE GUARD
    DECIDES WHAT "ALREADY EXISTS" MEANS (DEF-2870).** `uq_units_tenant_unit_no`
    is a case-SENSITIVE unique, so units and premises ask exactly as they are
    constrained; `create_cycle` and `create_route` refuse on `code__iexact`, so
    for them `cy-001` and `CY-001` are the same number and a check that could
    not see that would hand out a code the very next statement refuses. The
    parameter is the caller telling this function which of the two it is —
    never a default, because a default would be a guess about somebody else's
    unique index.

    **DEF-577.** Two paths write a premises/unit number without allocating it —
    a caller-supplied `unit_no` (the BR-TEN-063 sample plant writes 48 of them)
    and the CR-023 import load stage, which writes the customer's own numbers
    straight from their CSV. Both leave the counter standing behind the table.
    Measured on the demo database: `unit` stood at **102** with units up to
    **U-00420** on file, so "Add unit" answered a **500** —
    `duplicate key value violates unique constraint "uq_units_tenant_unit_no"`
    — and would have done so **319 times in a row**, once per number in the
    block, with the operator clicking through each failure.

    **THE SHAPE: allocate, and only if that number is already taken, catch the
    series up past everything that exists and allocate once more.** The healthy
    path costs ONE indexed existence check on a unique column. The repair path
    costs one scan of the column, one forward-only move (BR-TEN-035, through
    tenancy's own service — `number_series` is not this module's table) and one
    more allocation, and it clears the WHOLE block in a single move rather than
    one number per click.

    **The second allocation cannot collide**, and that is by construction, not
    by hope: the counter is put at one past the HIGHEST value this format could
    have written, so no larger one exists to collide with. It is still checked,
    because a guarantee that is not asserted is a comment (hard-won law 1).
    """
    number = _allocate_number(series, warnings)
    if number is None:
        return None  # the series row is missing — already reported as a warning
    tenant_id = _tenant_id()

    lookup = f"{field}__iexact" if case_insensitive else field
    prefix_lookup = f"{field}__istartswith" if case_insensitive else f"{field}__startswith"

    def taken(candidate: str) -> bool:
        # No `deleted_at` filter, deliberately: the unique constraint counts
        # soft-deleted rows too, so a retired unit still owns its number.
        return model.objects.filter(tenant_id=tenant_id, **{lookup: candidate}).exists()

    if not taken(number):
        return number

    series_format = seams.number_series_format(series)
    issue_date = seams.tenant_today()
    if series_format is None:  # pragma: no cover - allocation above would have failed first
        raise core_numbering.NumberingError(
            f"series {series!r} allocated {number!r} but has no stored format — refuse, never guess"
        )
    # Narrowed by the format's literal prefix so the scan stays index-friendly;
    # an empty prefix (the mandatory plain `{00000}` option) narrows to nothing,
    # which is correct rather than clever.
    prefix = core_numbering.literal_prefix(series_format)
    values = model.objects.filter(
        tenant_id=tenant_id, **{prefix_lookup: prefix}
    ).values_list(field, flat=True)
    minimum = _highest_number_in_use(series_format, values, issue_date) + 1
    seams.advance_number_series(actor, series, minimum)

    number = _allocate_number(series, warnings)
    if number is None or taken(number):
        # Unreachable by construction; asserted anyway, because a guarantee that
        # is not checked is a comment (hard-won law 1).
        raise core_numbering.NumberingError(
            f"series {series!r} handed out {number!r} again after a catch-up to "
            f"{minimum} — the counter and the {field} column still disagree"
        )
    return number


#: How many issued numbers `preview_unit_numbers` prints before it stops. Five,
#: matching `seams.PREVIEW_NUMBERS_SHOWN` and `assets.selectors
#: .PREVIEW_NUMBERS_SHOWN`, so every rehearsal panel in the product shows the
#: same shape and a clerk never has to learn a second one.
UNIT_PREVIEW_NUMBERS_SHOWN = 5


def preview_unit_numbers(count: int) -> dict[str, Any]:
    """**CR-089 wave E (`E6`/`PUJ-26`) — THE NUMBERS THE REVIEW SHOWS, TAKEN BY
    NOBODY (`BR-MET-1165`).**

    A review step that names `U-00421`..`U-00423` and then allocates something
    else is worse than no review at all, so this answers the same arithmetic
    the commit will do — and **allocates nothing, advances nothing, locks
    nothing**. `BR-MET-1165` is the rule and it has two halves; this function is
    the second one:

      (a) the number is taken **on the press**, inside the create's own
          transaction, and never reserved by the preview — so two clerks
          reviewing at the same moment are both shown `U-00421` and the second
          one to press gets `U-00424`;
      (b) what the preview shows is what a create **starting now** would take.

    ⚠ **AND (b) MEANS SIMULATING `_allocate_unused_number`, NOT REPRODUCING ITS
    IDEA (`DEF-MET-4719` — the first draft of this function got it wrong and a
    browser caught it).** That draft always caught the counter up past the
    highest number on file, on the reasoning that `DEF-577` proved the counter
    can stand behind the table. Measured on the `brazosbend` demo database on
    2026-09-09, the `unit` series read `next_number = 1` with `U-00420` already
    on file, so the draft answered `U-00421`..`U-00423` — **and the create
    issued `U-00001`, `U-00002`, `U-00003`.** Both had read `DEF-577`; only one
    had read what its fix actually does.

    **`_allocate_unused_number` catches up ONLY ON A COLLISION.** It allocates,
    asks whether that exact value is already in the column, and moves the
    counter past everything only when the answer is yes. `U-00001` is not taken
    on a tenant whose units are `U-00101-A`, `U-00420` and `SCW-U-001`, so it is
    issued, and the invariant that defect exists to protect — *a series must
    never hand out a number that already exists* — holds perfectly. The
    counter being behind the highest number on file is not by itself a
    collision.

    So this walks the same loop the commit walks, N times, without writing:
    render at the counter, and where that value is already on file, jump the
    counter past everything this format could have written and render again.
    The collision test and the catch-up arithmetic are the allocator's own
    (`_highest_number_in_use`, and the same prefix narrowing), so the two cannot
    drift apart without one shared change.

    ⚠ **THE RUN'S OWN NUMBERS COUNT AS TAKEN.** A block of three is three
    separate allocations against a moving counter, so number two must not be
    predicted as though number one had never been issued.

    Returns `series_missing` rather than a range when the tenant has no `unit`
    series row: BE-06 makes seeding a series provisioning's job, and a wizard
    that invented `U-00001` for a tenant whose numbering was never set up would
    be inventing the one thing this whole rule exists to protect.

    ⚠ **A CR-005 RESTART PERIOD IS NOT MODELLED**, exactly as
    `seams.number_series_preview` states of itself: a review run on the last day
    of a period can name numbers a commit on the next day would not use. Stated
    rather than hidden, and it is the same limit in both places by choice.
    """
    tenant_id = _tenant_id()
    if count <= 0:
        return {"series_missing": False, "numbers": [], "last": None, "count": 0}
    series_format = seams.number_series_format(UNIT_SERIES)
    if not series_format:
        return {"series_missing": True, "numbers": [], "last": None, "count": count}
    try:
        row = _unit_series_row()
    except errors.NotFoundError:  # pragma: no cover - the format read above already answered
        return {"series_missing": True, "numbers": [], "last": None, "count": count}
    issue_date = seams.tenant_today()
    counter = int(row.get("next_number") or 1)
    # Narrowed by the format's literal prefix so the scan stays index-friendly,
    # exactly as the allocator narrows it; an empty prefix narrows to nothing,
    # which is correct rather than clever. Read ONCE for the whole run — the
    # allocator asks the database per allocation, and a preview that did the
    # same would be N round trips to answer one screen.
    prefix = core_numbering.literal_prefix(series_format)
    in_use = set(
        models.Unit.objects.filter(
            tenant_id=tenant_id, unit_no__startswith=prefix
        ).values_list("unit_no", flat=True)
    )
    caught_up = False
    numbers: list[str] = []
    last: str | None = None
    for index in range(count):
        try:
            candidate = core_numbering.preview(series_format, counter, issue_date)
        except core_numbering.NumberingError:
            # A malformed stored format must not break a review; the clerk is
            # trying to find out what they are about to create.
            candidate = None
        if candidate is not None and candidate in in_use:
            # The allocator's repair path, as a read: put the counter one past
            # the highest value this format could have written, then render
            # again. It clears the whole block in one move rather than one
            # number per collision, which is what makes it safe to model once.
            counter = _highest_number_in_use(series_format, in_use, issue_date) + 1
            caught_up = True
            try:
                candidate = core_numbering.preview(series_format, counter, issue_date)
            except core_numbering.NumberingError:  # pragma: no cover - the first render answered
                candidate = None
        if candidate is not None:
            in_use.add(candidate)  # this run's own allocations are taken too
            last = candidate
            if index < UNIT_PREVIEW_NUMBERS_SHOWN:
                numbers.append(candidate)
        counter += 1
    return {
        "series_missing": False,
        "series_format": series_format,
        "next_number": int(row.get("next_number") or 1),
        "count": count,
        "numbers": numbers,
        "last": last,
        # `true` when a collision forced the catch-up. The wizard says nothing
        # about it, but the field exists so a support question ("why did it jump
        # 300?") has an answer on the payload rather than in somebody's memory.
        "caught_up": caught_up,
    }


def preview_premise_number() -> dict[str, Any]:
    """**CR-089 wave B (`B7`/`PUJ-08`) — the premise number the review shows.**

    PO 2026-09-08, verbatim: *"you ahve to show P-00080 also in header"*. The
    premises twin of `preview_unit_numbers` above, and it is deliberately the
    SAME loop rather than a second idea about the same question.

    ⚠ **`DEF-MET-4719` WAS FOUND TWICE, INDEPENDENTLY, ON THE SAME DAY.** Wave E
    hit it on the unit series and a browser caught it; this lane hit it on the
    premises series and a test caught it, with the identical wrong reasoning in
    both drafts — *`DEF-577` proved the counter can stand behind the table, so
    catch it up*. It does not follow: `_allocate_unused_number` catches up **only
    on a collision**, so on a tenant whose properties are numbered in some other
    format the counter is behind AND the number it renders to is free, and the
    allocator uses it. Measured on `brazosbend` 2026-09-09 through the shipped
    endpoint: the preview said `U-00421` and the create issued `U-00003`.
    **Two lanes reading the same defect note reached the same wrong conclusion,
    which is why this function follows the code above rather than the note.**

    ⚠ **ONE PROPERTY, SO ONE PASS — but the collision test and the catch-up are
    the allocator's own (`_highest_number_in_use`, the same prefix narrowing),
    exactly as they are one function up.** The two previews and the allocator
    cannot drift apart without one shared change.

    `BR-MET-1165` half (a) is untouched: the number is taken ON THE PRESS, and
    this reserves nothing — two clerks reviewing at the same moment are both
    shown `P-00080` and the second to press gets `P-00081`.

    `series_missing` rather than an invented `P-00001` when the tenant has no
    `premises` series row — seeding one is provisioning's job (BE-06).
    """
    tenant_id = _tenant_id()
    series_format = seams.number_series_format(PREMISES_SERIES)
    if not series_format:
        return {"series_missing": True, "number": None}
    from apps.tenancy import selectors as tenancy_selectors

    try:
        row = tenancy_selectors.number_series_row(PREMISES_SERIES)
    except errors.NotFoundError:  # pragma: no cover — the format read above already answered
        return {"series_missing": True, "number": None}
    issue_date = seams.tenant_today()
    counter = int(row.get("next_number") or 1)
    prefix = core_numbering.literal_prefix(series_format)
    in_use = set(
        models.Premises.objects.filter(
            tenant_id=tenant_id, premise_no__startswith=prefix
        ).values_list("premise_no", flat=True)
    )
    caught_up = False
    try:
        candidate = core_numbering.preview(series_format, counter, issue_date)
    except core_numbering.NumberingError:
        # A malformed stored format must not break a review — the clerk is
        # trying to find out what they are about to create.
        return {"series_missing": False, "number": None}
    if candidate in in_use:
        # The allocator's repair path, as a read.
        counter = _highest_number_in_use(series_format, in_use, issue_date) + 1
        caught_up = True
        try:
            candidate = core_numbering.preview(series_format, counter, issue_date)
        except core_numbering.NumberingError:  # pragma: no cover - the first render answered
            return {"series_missing": False, "number": None}
    return {
        "series_missing": False,
        "number": candidate,
        "next_number": counter,
        "caught_up": caught_up,
    }


def _unit_series_row() -> dict[str, Any]:
    """The tenant's stored `unit` series row, through tenancy's own selector —
    `number_series` is tenancy-owned (B2 PM owner map) and metering never reads
    another module's ORM directly."""
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.number_series_row(UNIT_SERIES)


# ── BR-MET-034 / BR-TEN-036 reference catalog (premises types) ──────────────
def ensure_reference_catalogs() -> dict[str, int]:
    """Idempotent seed of this module's Reference-data lists for the CURRENT
    tenant (BR-MET-034 seeded set, is_system rows: deactivatable, never
    deletable). Called from the write paths that need a type and from the
    documented `seed_reference_list` seam — tenancy's provisioning fixture
    routes no premises_types entries today (reported)."""
    tenant_id = _tenant_id()
    created = 0
    from apps.metering import premises_capacity

    for code, name in SEED_PREMISES_TYPES:
        _, made = models.PremisesType.objects.get_or_create(
            tenant_id=tenant_id,
            code=code,
            defaults={
                "name": name,
                "is_system": True,
                "active": True,
                # `CR-162-BRC10` — the seeded ACCOUNT TYPE (master or
                # regular); a utility may change it on Settings.
                "account_kind": premises_capacity.seed_answer(code),
            },
        )
        created += int(made)
    return {"premises_types": created}


def seed_reference_list(list_code: str, entries: list[dict[str, Any]], fixture_version: str) -> int:
    """The tenancy seeding seam (apps/tenancy/seams.py contract). Metering is the
    registry owner in tenancy's LOOKUP_LISTS for the four asset catalogs
    ('meter_types' · 'read_methods' · 'asset_types' · 'asset_statuses'); the
    tables live in the assets doc-module app, so all four are ROUTED there
    (BR-TEN-013/031 — metering never writes another module's tables). An empty
    fixture entry list falls back to the owning module's own ratified seed set
    — the rules, not a guess.

    DEF-017 (2026-08-10): `meter_types` used to short-circuit to 0 here and
    `read_methods` was not handled at all — it would have raised KeyError the
    moment tenancy declared it. Both are now forwarded exactly like their two
    twins. The old comment said B2 r4 gives read methods no lookup table; that
    was superseded by BR-AST-043 (PO 2026-08-09, two seeded tenant-extensible
    lists) and apps/assets/migrations/0003 built both tables — apps/assets
    reported the gap here at the time and could not reach into this file.
    """
    if list_code == "premises_types":
        if entries:
            return _seed_premises_types_from(entries)
        return ensure_reference_catalogs()["premises_types"]
    if list_code == "unit_types":
        # CR-010 A-4 (BR-MET-084): same posture as premises_types — the
        # fixture carries no entries, SEED_UNIT_TYPES is the single ratified
        # source; the entry path exists so a future fixture bump CAN carry
        # the list without a code change here.
        if entries:
            return _seed_unit_types_from(entries)
        return ensure_unit_types()
    if list_code in ("asset_types", "asset_statuses", "meter_types", "read_methods"):
        fn = seams.resolve("assets", "seed_reference_list")
        if fn is None:  # pragma: no cover - assets lane ships in the same packet
            return 0
        return int(fn(list_code, entries, fixture_version))
    raise KeyError(f"metering owns no reference list {list_code!r} (BR-TEN-031)")


def _seed_premises_types_from(entries: list[dict[str, Any]]) -> int:
    tenant_id = _tenant_id()
    created = 0
    for entry in entries:
        code = str(entry.get("code", "")).strip()
        name = str(entry.get("name", "")).strip()
        if not code or not name:
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="metering.reference_fixture_invalid",
                params={"list": "premises_types"},
            )
        exists = models.PremisesType.objects.filter(tenant_id=tenant_id, code__iexact=code).exists()
        if not exists:
            from apps.metering import premises_capacity

            answer = str(entry.get("account_kind") or "").strip().lower() or None
            models.PremisesType.objects.create(
                tenant_id=tenant_id,
                code=code,
                name=name,
                is_system=True,
                active=True,
                # `CR-162-BRC10` — the fixture's own answer where it carries
                # one, the seeded answer for a system code otherwise.
                account_kind=(
                    answer
                    if answer in premises_capacity.ACCOUNT_KINDS
                    else premises_capacity.seed_answer(code)
                ),
            )
            created += 1
    return created


def ensure_unit_types() -> int:
    """Idempotent seed of BR-MET-084's five unit types for the CURRENT tenant
    (is_system rows: deactivatable, never deletable). Called from the
    `seed_reference_list` seam; deliberately NOT from `ensure_reference_
    catalogs`, because that runs on premises WRITE paths regardless of the
    S111 toggle and unit types are DISCRETIONARY (BR-TEN-067: nothing
    schema-required needs one — `units.unit_type` is nullable TEXT, and
    validation falls back to the legacy tuple for a tenant with no rows)."""
    tenant_id = _tenant_id()
    created = 0
    for code, name in SEED_UNIT_TYPES:
        _, made = models.UnitType.objects.get_or_create(
            tenant_id=tenant_id,
            code=code,
            defaults={"name": name, "is_system": True, "active": True},
        )
        created += int(made)
    return created


def _seed_unit_types_from(entries: list[dict[str, Any]]) -> int:
    tenant_id = _tenant_id()
    created = 0
    for entry in entries:
        code = str(entry.get("code", "")).strip()
        name = str(entry.get("name", "")).strip()
        if not code or not name:
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="metering.reference_fixture_invalid",
                params={"list": "unit_types"},
            )
        exists = models.UnitType.objects.filter(tenant_id=tenant_id, code__iexact=code).exists()
        if not exists:
            models.UnitType.objects.create(
                tenant_id=tenant_id, code=code, name=name, is_system=True, active=True
            )
            created += 1
    return created


def _resolve_unit_type(value: str) -> str | None:
    """BR-MET-084: resolve a unit-type code against the tenant's OWN rows
    FIRST, the legacy UNIT_TYPES tuple second.

    Three outcomes, each deliberate:
      · the tenant HAS the row → its canonical code if active, None if the
        tenant deactivated it (BR-TEN-034: a deactivated row stops being
        pickable — the fallback must not resurrect it);
      · no such row → the legacy tuple decides, so a tenant with no rows at
        all (pre-CR-010, or S111 toggle off) keeps working and every code
        ever stored stays valid;
      · known to neither → None, and the caller refuses with the allowed set.
    """
    row = models.UnitType.objects.filter(tenant_id=_tenant_id(), code__iexact=value).first()
    if row is not None:
        return row.code if row.active else None
    return value if value in UNIT_TYPES else None


def _allowed_unit_types() -> list[str]:
    """The refusal's `allowed` list: the tenant's active rows where any exist,
    the legacy tuple where none do. (A tenant holding ONLY its own custom rows
    still has the seeded five — is_system rows are undeletable — so the one
    understatement possible is a toggle-off tenant's custom-only list, which
    is that tenant's own vocabulary and the honest answer.)"""
    qs = models.UnitType.objects.filter(tenant_id=_tenant_id())
    if qs.exists():
        return sorted(qs.filter(active=True).values_list("code", flat=True))
    return list(UNIT_TYPES)


def uom_used_by_count(uom_code: str) -> int:
    """The tenancy BR-TEN-029 seam: metering-side references to a UoM. Assets
    carry the explicit unit (B2 r4 `assets.unit`) — routed to the assets lane
    so the count stays live and this module never reads its tables."""
    fn = seams.resolve("assets", "uom_used_by_count")
    return int(fn(uom_code)) if fn is not None else 0


# ── the metering half of apps/billing/rating_seam.py (GT-4/GT-14 · GT-9) ────
#
# `rating_seam._require("metering", <name>, "services", ...)` resolves these two
# by name ON THIS MODULE, so this is where metering PUBLISHES them — the seam
# needs no edit and, per hard-won law 2, "built" becomes "wired" the moment
# these names exist. They are re-exported rather than redefined so there is one
# signature, not a copy that can drift from the one the golden fixtures bind to.
#
# Deliberately unlike everything else in this file: both are PURE (no ORM, no
# tenant context, no clock, no audit row) and neither is a write path. They can
# be called without a database, which is what lets the frozen B5 fixtures
# exercise them directly. Both return QUANTITIES — no rate is read and no money
# figure is produced anywhere in this module.
consumption_from_registers = quantities.consumption_from_registers
true_up_quantity = quantities.true_up_quantity


# ── premises (US-MET-001 / US-MET-003 · BR-MET-001/003/034/037/047/048) ─────
def _premises_row(premises_id: Any, *, locked: bool = False) -> models.Premises:
    if not _is_uuid(premises_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    qs = models.Premises.objects.filter(tenant_id=_tenant_id(), pk=premises_id)
    if locked:
        qs = qs.select_for_update()
    row = qs.first()
    if row is None:
        # Cross-tenant ids are indistinguishable from absent ones (HR-1/G4).
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _resolve_premises_type(value: Any, field: str = "premises_type") -> models.PremisesType | None:
    """BR-MET-034: an ACTIVE Reference-data entry, by id or code."""
    if value in (None, ""):
        return None
    ensure_reference_catalogs()
    qs = models.PremisesType.objects.filter(tenant_id=_tenant_id(), active=True)
    row = qs.filter(code__iexact=str(value)).first()
    if row is None:
        try:
            row = qs.filter(pk=UUID(str(value))).first()
        except (ValueError, AttributeError, TypeError):
            row = None
    if row is None:
        _refuse_fields(
            [
                _field_error(
                    field,
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.premises.type_unknown",
                    value=str(value),
                )
            ]
        )
    return row


def _clean_services(value: Any, field: str) -> list[str] | None:
    """BR-MET-003: service availability ⊆ the tenant's ENABLED services."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        _refuse_fields([_field_error(field, errors.VAL_FORMAT, "metering.services_not_a_list")])
    enabled = seams.enabled_service_codes()
    cleaned: list[str] = []
    fe: list[dict[str, Any]] = []
    for raw in value:
        code = str(raw).strip()
        if code not in enabled:
            fe.append(
                _field_error(
                    field, errors.VAL_UNKNOWN_LOOKUP, "metering.service_not_enabled", service=code
                )
            )
        elif code not in cleaned:
            cleaned.append(code)
    _refuse_fields(fe)
    return cleaned


#: ── BR-RAT-101's THREE STATES, AND WHY THIS IS NOT A CHECKBOX ──────────────
#: `True` inside the city · `False` outside it · `None` **nobody recorded it**.
#: A checkbox has TWO states, so a checkbox cannot express the third and every
#: premises anyone opened would silently become an answer — and the answer a
#: checkbox defaults to (`False`, outside) is the one that ADDS a surcharge to
#: every future bill at that address. BR-RAT-101, verbatim: *"assuming inside
#: under-charges a customer the utility may be entitled to surcharge, while
#: assuming outside over-charges one who never agreed to it. A default of
#: either would be a silent pricing decision on data nobody entered."*
#:
#: So the three states are three VALUES a caller states, and an absent key on a
#: PATCH means *leave it alone* — the same posture `services_available` takes
#: for the same reason (DEF-762): an unanswered question must survive a clerk
#: correcting a street name.
def _jurisdiction_flag(value: Any, fe: list[dict[str, Any]]) -> "bool | None":
    """`premises.inside_city_limits`, parsed strictly (BR-RAT-101, CR-039 C10).

    Three values, because BR-RAT-101 has three states: `True` inside the city ·
    `False` outside it · `None` **nobody recorded it**. `""` is accepted as a
    second spelling of `None` so a form's empty option can CLEAR an answer.

    ⚠ **A VALUE THIS FUNCTION CANNOT READ IS AN ERROR, NEVER A GUESS.** It is
    the posture the CSV importer already takes on this one column
    (`PRM.VALUES_PARSE`: *"a BLANK cell is NULL and never an error, because
    NULL is a real third state; a cell with words in it nobody can read IS an
    error, because guessing which way it meant is a silent pricing decision"*).
    Written here in the same words so the two writers of this column agree.

    ⚠ **`1` AND `0` ARE REFUSED ON PURPOSE.** Python makes `1 == True`, so a
    lazy `bool(value)` or a `value in (True, False)` test would take them
    silently — and it would also take `"outside"`, `2` and `[]`, each as
    *inside the city*. This column decides whether a surcharge lands on every
    future bill at an address; the type is checked, not coerced.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    if isinstance(value, bool):
        return value
    fe.append(
        _field_error(
            "inside_city_limits",
            errors.VAL_FORMAT,
            "metering.premises.jurisdiction_unreadable",
            value=str(value),
        )
    )
    return None


def _resolve_owner(value: Any, fe: list[dict[str, Any]]) -> Any:
    """`premises.owner_id` — the typed party record (BR-MET-150, CR-039 C12).

    Three outcomes, and the empty one is a real answer: a blank value CLEARS
    the link (*this address has no typed owner recorded*), which is a different
    fact from *nobody was ever asked* only in that a person has now looked. An
    id this tenant does not hold is REFUSED rather than silently dropped —
    dropping it would let a caller believe it had linked an owner that a bill
    would later fail to find.

    ⚠ **CLEARING THE LINK DOES NOT CLEAR `owner_manager`** and must not: the
    free text is what `customers.services.open_account` reads for the default
    payer, and taking it away here would change who a new account bills from a
    screen that was tidying up a pointer (`OQ-500`, BR-MET-151 clause 4).

    ⚠ **AN INACTIVE OWNER IS REFUSED.** A retired party may keep the addresses
    already on it (that is what `deactivate_premises_owner`'s blocker list is
    about) and may not take a new one.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    row = models.PremisesOwner.objects.filter(tenant_id=_tenant_id(), pk=str(value).strip()).first()
    if row is None:
        fe.append(
            _field_error(
                "owner_id",
                errors.VAL_UNKNOWN_LOOKUP,
                "metering.premises.owner_unknown",
                value=str(value),
            )
        )
        return None
    if not row.active:
        fe.append(
            _field_error(
                "owner_id",
                errors.VAL_UNKNOWN_LOOKUP,
                "metering.premises.owner_inactive",
                value=str(row.id),
            )
        )
        return None
    return row


def _validate_premises(
    payload: dict[str, Any],
    *,
    partial: bool,
    except_premises_id: Any = None,
    person_form: bool = False,
) -> dict[str, Any]:
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}
    known = {
        "address_line",
        "city",
        "state",
        "postal_code",
        "name",
        "premises_type",
        "services_available",
        "owner_manager",
        "external_ref",
        "status",
        # BR-MET-071 / BR-MET-083 (PO ruling 2026-08-17: *"when we add premises
        # you should allow to select areas and sub areas on premises"*). The
        # COLUMN shipped with CR-006 and this validator refused the field, so
        # `premises.area_id` had never held a value on any tenant and the area
        # filter on the route picker could only ever return zero rows
        # (DEF-220). One column answers both levels: a premises tagged to a
        # sub-area is by construction inside that sub-area's parent.
        "area_code",
        "area_id",
        # ── CR-039 wave C task 10 · BR-RAT-101's flag becomes WRITABLE ──────
        # DEF-517 (2026-08-21) filed it: the column has decided money since
        # `gather._jurisdiction_factor_for` started reading it, and nothing in
        # the product could set it — `create_premises`/`update_premises`
        # refused the field with `metering.unknown_field`, no serializer
        # carried it and no screen drew a control. DEF-507 then served it
        # READ-ONLY and said in its own comment *"where an edit control
        # belongs (and whether changing it re-rates issued bills) is a bigger
        # question than this defect — REPORTED, not invented"*. This is the
        # write half; the re-rating question is `OQ-423` below.
        "inside_city_limits",
        # ── CR-039 wave C task 12 · the TYPED owner (BR-MET-150) ────────────
        # PO 2026-08-27, verbatim: *"category is okay, no richer text"*. The
        # premises names its owner by POINTING at a `premises_owners` row.
        # `owner_manager` above stays writable beside it — BR-MET-151 keeps the
        # free text until every tenant is matched, and `OQ-500`/`OQ-501` are
        # what would retire it.
        "owner_id",
        # ── CR-069 wave M · `OQ-INT-1471` RULED 2026-09-04, option (b) ──────
        # *"(b) type it, marked unchecked"*. `integrations/seams/metering.py`
        # sets this when a clerk creates the property by typing while the
        # City's address service is unreachable. It is accepted here rather
        # than written directly, because a premises is metering's row and a
        # cross-module write is forbidden (B2 §2) — the seam calls this
        # service, which is the reviewed interface.
        "gis_unchecked",
        # ── CR-069 wave M · `BR-INT-049` — the City's own pin, at creation ──
        # ⚠ **A THIRD WRITER OF `lat`/`lng`, AND IT IS RECORDED RATHER THAN
        # SLIPPED IN.** The model names two: the deterministic sample seed and
        # the `geocode_premises` command, and *"a set value is never
        # overwritten by either"*. This is a CREATE, so the row is empty by
        # construction and that rule is untouched — and a coordinate the City
        # returned for the parcel it also returned is better evidence than a
        # geocoder's guess at the same address.
        #
        # ⚠ **AND SINCE CR-089 WAVE A IT IS A FOURTH WRITER: THE EDIT FORM.**
        # These four lines used to end *"`update_premises` does NOT accept
        # these"*, and the partial path refused them as `metering.unknown_field`
        # — which made a wrong pin permanent. `PUJ-19` is the PO asking for the
        # opposite: *"05 Edit a property PRM-02 and create property screen
        # should match"*, and a property placed on the wrong side of the street
        # is corrected on the form that edits it. **A CLERK IS THE ONLY WRITER
        # WHO MAY OVERWRITE A SET VALUE**; the seed and the geocoder still may
        # not, and both still guard on `lat IS NULL` in their own code.
        # ⚠ Dragging the pin is NOT how it is corrected — PO 2026-09-08,
        # verbatim: *"we dont need this right now - Drag the pin to correct
        # it"*. The two figures are typed.
        "lat",
        "lng",
        # ── 2026-09-17 · `BR-MET-1173` — the City's parcel key and status ────
        # ⚠ **THIS IS WHERE THE PARCEL KEY GOES NOW, AND IT USED TO GO INTO
        # `external_ref` ABOVE.** `CR-069` wave M wrote
        # `"external_ref": candidate.get("parcel")`, which collides on the
        # first run with every row a MIGRATING utility already has there:
        # `external_ref` is `BR-MET-403`'s import match key under
        # `uq_premises_tenant_external_ref_ci`. The two are different facts and
        # now have different columns. `external_ref` stays writable and keeps
        # its own job.
        "gis_parcel_id",
        # Stored as the City gives it and never filtered — we do not own their
        # vocabulary, and a row dropped for an unrecognised status is a row
        # nobody can see we dropped (ruling 10, 2026-09-17).
        "gis_status",
        # ── 2026-09-17 · `DEF-INT-5629` — WHAT THE RECONCILIATION RUN WRITES ─
        # ⚠ **WITHOUT THESE FOUR, `gis_parcels._persist` COULD NOT WRITE ONE
        # ROW.** It patches `gis_parcel_id_was` + `gis_key_changed_at` on a
        # REPLACED key (`BR-MET-1173`) and the verified pair on every key the
        # City confirmed — and this set carried none of them, so the first
        # apply answered `metering.unknown_field` on row 1. Worse than a
        # refusal: `_persist`'s savepoint catches `DatabaseError`, and a
        # `ValidationError` is not one, so the whole run died rather than
        # counting one refused row. Proved by calling this function with the
        # exact patch the run builds; it named all four.
        #
        # ⚠ **THEY ARE FACTS ABOUT WHAT THE CITY SAID, NOT THINGS A CLERK MAY
        # TYPE**, so `integrations/seams/metering.NEVER_FROM_A_FORM` still
        # strips the two that a create form could reach. Accepting them HERE is
        # what makes the reviewed interface usable (B2 §2 — the seam calls
        # metering's own service and writes no metering row itself); a second
        # write path that bypassed this validator to reach the same columns is
        # the outcome that rule exists to prevent.
        "gis_parcel_id_was",
        "gis_key_changed_at",
        "gis_verified",
        "gis_verified_at",
    }
    for field in payload:
        if field not in known and field not in (
            "units",
            "unit",
            "auto_create_unit",
            "route",
            # ── `DEF-MET-5844` — the owner's account type, read by
            # `_ensure_owner_master_account`, never written to `premises` ────
            # ⚠ **IT IS A FACT ABOUT THE OWNER'S ACCOUNT AND NOT ABOUT THE
            # ADDRESS**, which is why it is tolerated here rather than added to
            # `known`: `known` is the column set this validator returns for
            # `Premises.objects.create(**cleaned)`, and a key in it would try to
            # write a column that does not exist. The three keys above it are
            # tolerated for the same reason — they are read from `data` by the
            # caller after the row is written.
            #
            # ⚠ **THE NAME IS THE IMPORT'S OWN** (`import_runs.owner_account_verdict`
            # reads `mapped["owner_account_type"]`). One vocabulary for one fact
            # across the two doors that collect it, so a lane reading either can
            # find the other — B14 rule 34's principle applied to a payload key.
            "owner_account_type",
            # ── `OQ-MET-12472` (PO ruling 2026-09-19) — WHO THE OWNER IS ─────
            # ⛔ **THE PO CHOSE *"the form asks"*.** Put to them in plain
            # English: *"The Add Premises form must collect an identifier — it
            # gains the same kind + identifier fields the import already has,
            # and no account exists until they're supplied."* Their answer was
            # *"this is correct"*. So the September rule (`BR-CUS-1024`,
            # *"Without identifier we cannot create Customer ID or master
            # account ot regular account"*) STANDS, and the August rule (*every
            # address gets its owner a Master Account*) yields on this path.
            #
            # ⚠ **THE FIVE NAMES ARE THE IMPORT'S OWN, EXACTLY**
            # (`import_runs.OWNER_IDENTIFIER_COLUMNS` +
            # `KIND_OWNER_KIND`). The two doors that collect this fact now
            # spell it identically, which is what lets ONE function —
            # `owner_account_verdict` — judge both. A sixth spelling here would
            # be a second vocabulary for one fact and the two would drift.
            #
            # ⚠ **TOLERATED, NEVER STORED.** None of these is a `premises`
            # column and none becomes one: they are read from `data` by
            # `_ensure_owner_master_account` and handed to the account door,
            # which is where identity LIVES (decision log 2026-09-19 —
            # `premises_owners` has no encryption story and `BR-MET-1020`
            # already rules the metering→customer shortcut out by name).
            "owner_kind",
            "owner_ssn",
            "owner_driving_licence",
            "owner_phone",
            "owner_tax_id",
            # ── `BR-MET-1181` (PO 2026-09-22) — THE ACCOUNT A CLERK NAMES ─────
            # ⚠ **IT IS A REAL `premises` COLUMN AND IT IS STILL NOT IN
            # `known`**, which is the opposite of the reason the keys above are
            # tolerated and is worth saying. `known` is the set this validator
            # hands to `Premises.objects.create(**cleaned)`, so putting it there
            # would write the link with **no check that the id names a real,
            # `master`-kind account in this tenant, and no audit row**. An
            # ordinary account at an address belongs to a TENANT, and declaring
            # one as the owner bills the tenant for the landlord's charges.
            # `_attach_named_master_account` is the door: it asks `customers`
            # what the id is, refuses by name, and writes through the one
            # audited writer.
            "master_account_id",
            # ── `CR-161-BRC10` W2 · `DEF-MET-9226` — the tenant's own fields ──
            # Tolerated here and validated by the CALLER, because only the
            # caller knows which screen the form is (a required field binds
            # only where it is typed in) and an edit must merge into the
            # stored answers. See `_premises_custom_data`.
            "custom_data",
            # ── `CR-177-BRC10` · `BR-MET-1190` — *Add it anyway* ─────────────
            # The clerk's answer to *"This address already exists."* on Add a
            # premise. Read by `create_premises`, never a column: it says the
            # clerk SAW the other premise and chose to add this one regardless,
            # the only way an exact duplicate address is saved from a person's
            # form (PO 2026-10-09: *Open it* / *Add it anyway*).
            "add_anyway",
        ):
            fe.append(_field_error(field, errors.VAL_FORMAT, "metering.unknown_field"))
    _refuse_fields(fe)

    if "address_line" in payload or not partial:
        address = _text(payload.get("address_line"), 500)
        if not address:  # US-MET-001 §5: address_line required
            fe.append(
                _field_error(
                    "address_line", errors.VAL_REQUIRED, "metering.premises.address_required"
                )
            )
        out["address_line"] = address
    for field, limit in (("city", 120), ("state", 60), ("postal_code", 20), ("name", 200)):
        if field in payload:
            out[field] = _text(payload[field], limit)
    for field, limit in (("owner_manager", 200), ("external_ref", 120)):
        if field in payload:
            out[field] = _text(payload[field], limit)
    # ── 2026-09-17 · `BR-MET-1173` — the City's key and status, trimmed only ──
    # ⚠ **NOT NORMALISED, NOT UPPER-CASED, NOT VALIDATED AGAINST A PATTERN.**
    # A parcel key is the City's string and we are not the ones who decide what
    # a valid one looks like; a second city on the same connector spells theirs
    # differently. Comparison is case-insensitive (`BR-INT-073`) and STORAGE is
    # as given, which is `premises.external_ref`'s own posture one loop up.
    for field, limit in (("gis_parcel_id", 120), ("gis_status", 60)):
        if field in payload:
            out[field] = _text(payload[field], limit)
    # CR-069 wave M — a boolean, coerced rather than validated: the only
    # writer is `integrations/seams/metering.py` and the only two values that
    # mean anything are the two a boolean has.
    if "gis_unchecked" in payload:
        out["gis_unchecked"] = bool(payload["gis_unchecked"])
    _gis_run_fields(payload, out, fe)
    for field in ("lat", "lng"):
        if field not in payload:
            continue
        # CR-089 wave A `PUJ-19` — accepted on BOTH paths now. See the note
        # beside "lat" in `known` above for why the create-only fence moved.
        raw = payload[field]
        if raw in (None, ""):
            out[field] = None
            continue
        try:
            value = Decimal(str(raw)).quantize(Decimal("0.000001"))
        except (ArithmeticError, TypeError, ValueError):
            fe.append(_field_error(field, errors.VAL_FORMAT, "metering.premises.coordinate_format"))
            continue
        # ⚠ **A NUMBER OUTSIDE THE WORLD IS A TYPO, AND IT HAS TO BE REFUSED AT
        # THE FIELD (CR-089 wave A).** Until the edit form existed the only
        # writers were the City and a deterministic seed, so a range check
        # bought nothing; a clerk typing `-98.238391` into the LATITUDE box is
        # the ordinary mistake this path now has to survive, and unrefused it
        # puts a marker in the Southern Ocean with every test green.
        limit = Decimal("90") if field == "lat" else Decimal("180")
        if value < -limit or value > limit:
            fe.append(
                _field_error(field, errors.VAL_FORMAT, "metering.premises.coordinate_range")
            )
            continue
        out[field] = value
    # ⚠ **BOTH OR NEITHER (CR-089 wave A `PUJ-19`).** The edit form sends both
    # boxes on every save, so the only way to reach here with one is a clerk
    # clearing ONE of them — and half a point is not a place. Everything
    # downstream already survives it (the **Needs a location** filter reads
    # `lat IS NULL OR lng IS NULL`, and the property page draws *No point
    # recorded*), which is exactly why it must be refused HERE: a state every
    # reader quietly tolerates is a state nobody ever notices they created.
    if ("lat" in out) != ("lng" in out):
        pass  # one was refused above for format/range; that error is enough
    elif "lat" in out and (out["lat"] is None) != (out["lng"] is None):
        fe.append(
            _field_error(
                "lat" if out["lat"] is None else "lng",
                errors.VAL_REQUIRED,
                "metering.unit.point_needs_both",
            )
        )
    if "premises_type" in payload:
        out["premises_type"] = _resolve_premises_type(payload["premises_type"])
    # BR-MET-071: absent leaves the tag alone (a PATCH that renames a premises
    # must not untag it); an explicit empty string CLEARS it.
    area_present, area = _resolve_area(payload, message_key="metering.premises.area_unknown")
    if area_present:
        out["area"] = area
    if "services_available" in payload:
        out["services_available"] = _clean_services(
            payload["services_available"], "services_available"
        )
    if "inside_city_limits" in payload:
        out["inside_city_limits"] = _jurisdiction_flag(payload["inside_city_limits"], fe)
    if "owner_id" in payload:
        out["owner"] = _resolve_owner(payload["owner_id"], fe)
    # ── CR-089 wave B `B1` — THE OWNER IS OPTIONAL AT CREATION ─────────────
    #
    # **PO ruling 2026-09-08, verbatim:** *"Owner = search ( it should be
    # optional)"*. This REVERSES `BR-MET-1181`'s create-time refusal, which stood
    # from 2026-08-27 (DEF-650, PO: *"when presmies are created you have owner
    # for it, without owner how you can create premsies = owner = master
    # account"*). CR-089 §2.1 carries the supersedes chain in full.
    #
    # ⚠ **WHAT IS REVERSED IS THE REFUSAL, NOT THE REASON FOR IT.** The owner is
    # still the party an empty unit's base charge bills to (BR-MET-105) and
    # still the only thing a move-out shortfall can be sent to (DEF-650). What
    # the ruling changes is WHEN that has to be answered: a clerk standing at a
    # counter with an address and no owner may now record the address, and the
    # property lands on the **Needs an owner** list (`B2`) where somebody can
    # finish it. Refusing the whole form for a fact the clerk does not yet hold
    # was the ninth click of a twelve-click job and it lost the other eleven.
    #
    # ⚠ **THE ONLY THING THAT STOPS THIS CREATING ORPHANS NOBODY CAN FIND IS
    # THAT LIST, WHICH IS WHY IT IS NOT AN OPTIONAL EXTRA.** `premises_list`'s
    # `owner=needs_owner` filter is the reader for the rows this line now
    # allows; `unmatched_premises_qs()` only ever covered the ones carrying a
    # free-text NAME, which on the demo utility is 8 of 79 — the other 65 were
    # on no list at all. Deleting the filter without restoring the refusal would
    # make this a hole rather than a ruling.
    #
    # ⚠ **PATCH IS UNCHANGED AND WAS NEVER THE POINT.** `partial` still governs
    # nothing here because there is no requirement left to fence, but the
    # reasoning that fenced it is worth keeping where the next reader meets it:
    # every premises on every tenant predates the typed owner and `metering
    # 0041` backfills none of them, so a required field on PATCH would make a
    # ten-year-old address unsaveable for a reason about OUR schema.
    #
    # ⚠ **AND THE ROLLBACK IS THE ONE IN THIS CR THAT IS NOT FREE (§8).**
    # Restoring the refusal makes every owner-less property created meanwhile
    # unsaveable ON EDIT — because a create-only rule is enforced by
    # `create_premises`, and PRM-02's edit form posts the whole record back. So
    # a restore must be paired with a backfill or a PATCH exemption. **Do not
    # add a second place that requires an owner**; there is exactly one rule
    # here and this comment is where it is written down.
    #
    # The resolution above still runs, so `{"owner_id": "<a real id>"}` still
    # links a party and `{"owner_id": "<nonsense>"}` is still refused BY NAME.
    # What is gone is the refusal for saying nothing at all.
    if "status" in payload:
        status = str(payload["status"] or "").strip()
        if status not in PREMISES_STATUSES:
            fe.append(
                _field_error(
                    "status",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.premises.status_unknown",
                    allowed=list(PREMISES_STATUSES),
                )
            )
        else:
            out["status"] = status
    _refuse_fields(fe)
    # ── CR-089 wave B · `DEF-MET-4727` — A TAKEN PARCEL IS A SENTENCE ───────
    #
    # ⚠ **THIS REACHED A CLERK AS AN HTTP 500 UNTIL TODAY.**
    # `uq_premises_tenant_external_ref_ci` is one outside reference per tenant,
    # case-insensitively, and typing one already on another property produced
    # `IntegrityError: duplicate key value violates unique constraint
    # "uq_premises_tenant_external_ref_ci"` — a database error on a form.
    #
    # ⚠ **THE GUARD WAS NOT MISSING; IT WAS WIRED TO ONE WRITER OF TWO.**
    # `selectors.premises_external_ref_taken` exists, is tested, and says in its
    # own docstring that it exists *"so a collision is a sentence and not a
    # `500`"* (`DEF-INT-4273`) — and only `integrations/seams/metering.py` called
    # it, because until CR-089 wave A `A2` drew the **Parcel ID** box the City
    # address lookup was the ONLY writer of this column. Putting the field in
    # front of a person added a second writer and no second check.
    # **A validator covers a COLUMN, not a code path, and nothing in this repo
    # asks whether it covers every writer of one.**
    #
    # ⚠ **AFTER `_refuse_fields`, SO A REAL FORMAT ERROR IS REPORTED FIRST**, and
    # a `BizError` rather than a `ValidationError` because that is this repo's
    # shape for a uniqueness refusal (`_duplicate_name_error`, `BIZ_STATE` →
    # 409). It still carries `field_errors`, so CR-089 `B8` puts the clerk back
    # on the **Parcel ID** box rather than on a dead end.
    #
    # ⚠ **THIS SAID *CREATE ONLY* UNTIL 2026-09-10, AND THAT LEFT THE SAME `500`
    # STANDING ON THE EDIT FORM (`DEF-MET-4757`).** The reasoning was sound as
    # far as it went — on a PATCH the row already holds this value and would
    # collide with ITSELF — and it ended on the sentence *"The index still
    # refuses a true duplicate there."* **That sentence is true and it is the
    # defect.** The index refusing it IS `IntegrityError: duplicate key value
    # violates unique constraint "uq_premises_tenant_external_ref_ci"`, escaping
    # unhandled, reaching a clerk as *"Something went wrong on our side"* — the
    # exact failure this block was written to remove, one writer along.
    #
    # ⚠ **SO THE FIX IS NOT A SECOND CHECK, IT IS THE MISSING ARGUMENT.** The
    # self-collision the old comment worried about is real, and `except_id` is
    # what answers it: ask *"does ANOTHER row hold this"* rather than *"does any
    # row hold this"*. A clerk resending their own parcel passes; a clerk moving
    # a parcel between properties still gets the sentence, which is what
    # `BR-MET-1163` asks for.
    #
    # ⚠ **THE LESSON IS THE ONE THE PARAGRAPH ABOVE ALREADY WROTE DOWN AND THEN
    # REPEATED:** *a validator covers a COLUMN, not a code path.* `DEF-MET-4727`
    # found this column had two writers and guarded one of them. This is the
    # second. **When you guard a column, enumerate its writers** — here they are
    # `create_premises`, `update_premises` and the integrations seam.
    if taken_ref := str(out.get("external_ref") or "").strip():
        from apps.metering import selectors as _premises_selectors

        if _premises_selectors.premises_external_ref_taken(
            taken_ref, except_id=except_premises_id
        ):
            raise _parcel_taken("external_ref", taken_ref, except_id=except_premises_id)
    # ── `DEF-MET-9847` · THE TYPED CITY PARCEL, ON A PERSON'S FORM ONLY ──────
    # ⚠ **`gis_parcel_id` HAS NO UNIQUE INDEX AND MUST NOT GET ONE** — two
    # premises on one parcel is a real City fact (`BR-INT-073`) and the
    # reconciliation QUEUES it rather than refusing (ruling 7, 2026-09-17).
    # But `premises_gis_parcel_taken`'s own docstring draws the line: *a clerk
    # creating a second property on a parcel that already has one is almost
    # always the accident it looks like*, so the City PICK is refused
    # (`DEF-INT-4273`). Until 2026-10-07 the same clerk TYPING the same parcel
    # into the same box was accepted silently — the pick asked and the typed
    # path never did. `person_form` is true exactly when the caller is a screen
    # (`custom_fields_screen` set); an import, the sample seed and the
    # reconciliation pass `None` and are never refused here.
    if person_form and (typed_parcel := str(out.get("gis_parcel_id") or "").strip()):
        from apps.metering import selectors as _premises_selectors

        if _premises_selectors.premises_gis_parcel_taken(
            typed_parcel, except_id=except_premises_id
        ):
            raise _parcel_taken("gis_parcel_id", typed_parcel, except_id=except_premises_id)
    return out


def same_address_refusal(same: dict[str, Any]) -> errors.BizError:
    """`BR-MET-1190` — *"This address already exists."*, naming the premise.

    `params` carry the premise NUMBER and the address a clerk reads, and the
    `premises_id` the screen's *Open it* link needs (B14 rule 31 — never shown).
    A `BIZ_STATE` 409 with a field error on `address_line`, so a screen that
    knows nothing about this refusal still lands the clerk on the street box.
    """
    params = {
        "premise_no": same["premise_no"],
        "address": compose_address(
            same.get("address_line"), same.get("city"), same.get("state"), same.get("postal_code")
        ),
        "premises_id": same["id"],
        "units": same.get("units", 0),
        "status": same.get("status"),
    }
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-MET-1190",
        message_key="metering.premises.same_address_exists",
        params=params,
        field_errors=[
            {
                "field": "address_line",
                "code": errors.BIZ_STATE,
                "message_key": "metering.premises.same_address_exists",
                "params": params,
            }
        ],
    )


def compose_address(street: Any, city: Any, state: Any, postal_code: Any) -> str:
    """`3721 S Village Dr, Avenel, NJ 07001` — and never `Dr,, Avenel`.

    `CR-177-BRC10` task 5 / `DEF-MET-10034`: the review read *"3721 S Village
    Dr,, Avenel"* because a part ending in a comma was joined with another
    comma. Each part is trimmed of spaces AND commas, an empty part is skipped,
    and the ZIP follows the state after a space (how a North American address
    is written). The screen's `composeAddress` is the same rule in TypeScript.
    """
    tidy = [str(part or "").strip().strip(",").strip() for part in (street, city, state, postal_code)]
    street_t, city_t, state_t, zip_t = tidy
    region = " ".join(part for part in (state_t, zip_t) if part)
    return ", ".join(part for part in (street_t, city_t, region) if part)


#: The one index a typed parcel number can collide with (`BR-MET-403`'s import
#: match key, which the Parcel box on Edit premise and New Connection writes).
_PARCEL_INDEX = "uq_premises_tenant_external_ref_ci"


def _parcel_taken(field: str, value: str, *, except_id: Any = None) -> errors.BizError:
    """`DEF-MET-9847` — ONE sentence for every parcel refusal, naming WHERE.

    *"This parcel already belongs to {{address}}."* (B14 rule 33: a fact, six
    words.) The key is still `metering.premises.external_ref_taken` — its
    consumers and tests read it — and only its words changed: the old
    *"That Parcel ID is already used."* made the clerk search the register to
    learn which property. `field` is the COLUMN, so CR-089 `B8` puts the clerk
    back on the box that caused it. `value` stays in the params for support.
    """
    from apps.metering import selectors as _premises_selectors

    address = (
        _premises_selectors.premises_holding_parcel(value, column=field, except_id=except_id)
        or value
    )
    params = {"value": value, "address": address}
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-MET-1163",
        message_key="metering.premises.external_ref_taken",
        params=params,
        field_errors=[
            {
                "field": field,
                "code": errors.BIZ_STATE,
                "message_key": "metering.premises.external_ref_taken",
                "params": params,
            }
        ],
    )


def _is_parcel_collision(exc: BaseException) -> bool:
    """Did THIS `IntegrityError` come from the parcel index, and no other?

    ⚠ **A WALK, NOT ONE HOP (hard-won law 14).** Django's `IntegrityError` wraps
    another `IntegrityError` which wraps the driver's, and only the driver's
    carries `diag.constraint_name`; the index name is also in every layer's text
    on both PostgreSQL and SQLite. Any OTHER integrity failure — a premise
    number from a series that wrapped — is not this refusal and is re-raised.
    """
    seen: BaseException | None = exc
    for _hop in range(8):
        if seen is None:
            return False
        diag = getattr(seen, "diag", None)
        if getattr(diag, "constraint_name", None) == _PARCEL_INDEX or _PARCEL_INDEX in str(seen):
            return True
        seen = seen.__cause__ or seen.__context__
    return False


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def _gis_check_stamp(payload: dict[str, Any], actor: Any) -> dict[str, Any]:
    """CR-089 wave A — *Checked against GIS*, with **who and when**.

    PO ruling 2026-09-08: the `gis_unchecked` flag *"becomes **Checked against
    GIS**, with who and when"*. This is where the who and the when are written.

    ⚠ **IT FIRES ON AN EXPLICIT STATEMENT AND NEVER ON A DEFAULT, WHICH IS THE
    WHOLE OF IT.** `gis_unchecked` is `NOT NULL DEFAULT false`, so *false* is
    what all 673 existing properties hold and what every create that never
    mentions the field gets. Reading that default as *a person checked this*
    would mark the entire estate checked by nobody, on a screen that then names
    a person — the exact shape of a fact nobody stated (hard-won law 3). So the
    stamp is written only when the CALLER NAMED the field:

      * named and `false` → a person pressed **Mark checked**: stamp them, now.
      * named and `true`  → it is not checked (the `OQ-INT-1471` branch, or a
        clerk withdrawing the check): CLEAR both, because a stale checker beside
        an unchecked flag is worse than no checker at all.
      * not named         → untouched. An edit that renames a property does not
        re-date its GIS check.

    Returns field/value pairs for the caller to apply WITH the rest of the
    change, so the audit row carries one before/after (BR-MET-048).

    ⚠ `gis_checked_by_id` and never `gis_checked_by`: the update path compares
    `getattr(row, field)` against the new value, and asking a row for the
    OBJECT would fetch a user per premises to decide whether it changed.
    """
    if "gis_unchecked" not in payload:
        return {}
    if bool(payload["gis_unchecked"]):
        return {"gis_checked_by_id": None, "gis_checked_at": None}
    return {
        "gis_checked_by_id": getattr(actor, "id", None),
        "gis_checked_at": timezone.now(),
    }


#: `DEF-MET-5844` — what the Add Premises form did about the owner's account,
#: said out loud. Every branch reports; **none of them is silent**, because a
#: door that quietly declines is the defect this whole block exists to close.
OWNER_ACCOUNT_NOT_CREATED = "owner_account_not_created"
OWNER_ACCOUNT_CREATED = "owner_account_created"
#: ⛔ **RENAMED FROM `no_typed_owner` ON 2026-09-22 (`BR-MET-1181`), AND THE OLD
#: NAME IS QUOTED HERE RATHER THAN DELETED (hard-won law 1).** It used to read
#: *"the premises names no typed party, so there is nobody to open an account
#: FOR. Nothing is read off the free-text `owner_manager` box"* — which was true
#: while the chain ran `premises → owner record → account`, and is the exact
#: sentence that discarded a clerk's name, kind and tax id because they had not
#: also picked a row from a table no screen can fill (`DEF-MET-6139`).
#:
#: **THE CONDITION NOW IS SIMPLY THAT NOBODY WAS NAMED.** The PO ruled the owner
#: record out of the chain — *"owner IDs are not required hence no screens or
#: fucntionality for it"* — so the party this account is FOR is the name on the
#: form, and this reports the one case where there is not one.
#:
#: ⚠ **`BR-MET-151` CLAUSE 3 IS NOT CROSSED, AND THE DISTINCTION IS EXACT.** It
#: forbids reading a party's CATEGORY off a name. Nothing here reads a category
#: off anything: **no `premises_owners` row is created by this path at all.** The
#: name is used as a NAME — the same string `create_master_account` has always
#: fallen back to out of `owner_manager` for the contact and the customer.
#: ⚠ **AND `BR-MET-112` IS NOT WEAKENED EITHER.** An account is not minted
#: because a field was filled in: it takes a name AND a kind AND an identifier of
#: that kind AND an account type — four deliberate answers, which is
#: `owner_account_verdict`'s ELIGIBLE and is `OQ-MET-12472`'s ruling in as many
#: words (*"no account exists until they're supplied"*). Nothing is written until
#: the last button; what changed is what that one press writes.
OWNER_ACCOUNT_OWNER_NOT_NAMED = "owner_not_named"
#: ⚠ **THE OLD SPELLING, KEPT AS AN ALIAS FOR ONE REASON ONLY: TESTS AND
#: WALKTHROUGHS WRITTEN AGAINST `DEF-MET-5844` IMPORT IT BY NAME.** It is the
#: same string's old value and nothing emits it any more — the register's reason
#: column now reads `owner_not_named` on every path. Delete it when the last
#: importer goes; a grep for it is the list.
OWNER_ACCOUNT_NO_TYPED_OWNER = OWNER_ACCOUNT_OWNER_NOT_NAMED
#: A named owner and no account type. `customers.create_master_account` refuses a
#: missing one by name and is right to: the account type is the consumer category
#: the bill is priced and reported by. Counted apart from the refusal below
#: because the work it asks of a person is different — this is a choice from a
#: list on this screen, that is a trip to find a document.
OWNER_ACCOUNT_NO_ACCOUNT_TYPE = "no_account_type"
#: The door was walked through and it refused. Its OWN `message_key` travels
#: with this, never a second wording of it.
OWNER_ACCOUNT_REFUSED = "refused"
#: ⛔ **`BR-MET-1181` — THE CLERK NAMED AN ACCOUNT THAT ALREADY EXISTS AND IT IS
#: NOW THIS ADDRESS'S.** PO 2026-08-27, `BR-MET-400`: *"it can be existing master
#: account also so at the time of premises creation we should check"*. Reported
#: apart from `owner_account_created` because no account was opened and no
#: customer was resolved — saying *created* over an account opened last month is
#: the lie `OWNER_ACCOUNT_ALREADY_LINKED` below exists to prevent, one case over.
OWNER_ACCOUNT_ATTACHED = "owner_account_attached"
#: ⚠ **THE OWNER ALREADY HELD AN ACCOUNT, SO NOTHING WAS CREATED — AND THIS
#: CONSTANT EXISTS BECAUSE THE FIRST DRAFT OF THIS CODE REPORTED IT AS A
#: CREATION.** `ensure_owner_master_account` is *ensure*: an owner already
#: linked gets that account back, writes nothing and audits nothing, and it
#: returns THE SAME SHAPE it returns after a create. A caller that reads only
#: the return value cannot tell the two apart, so this one asks the owner row
#: BEFORE the call. Reporting *account created* over an account created last
#: month is a check that passes wrongly (CLAUDE.md hard-won law 7) — and on a
#: receipt a clerk reads, it is a lie about a money object.
OWNER_ACCOUNT_ALREADY_LINKED = "owner_account_already_linked"

#: ⛔ **`BR-MET-1181` / `DEF-MET-6139` — EVERY OUTCOME CARRIES A SENTENCE A CLERK
#: CAN READ, AND EXACTLY ONE WORDING OF IT.**
#:
#: **THE DEFECT THIS CLOSES IS NOT THAT THE SERVER WAS SILENT — IT IS THAT THE
#: SERVER SPOKE AND NOBODY LISTENED.** Measured 2026-09-22 across the whole of
#: `07-frontend/src`: the five strings below appear NOWHERE outside the import
#: receipt. `create_premises` computed a distinct answer every time and the
#: wizard fired one toast — *"Premise created"* — and threw the array away. So a
#: clerk who typed a name, a kind and a tax id was told the address was saved and
#: never told that the account was not opened or why.
#:
#: ⚠ **ONE KEY PER OUTCOME, NEVER A SECOND WORDING OF ONE.** B14 rule 34's
#: principle applied to a machine-readable reason: the same condition must read
#: the same way on this receipt and on an import receipt. `refused` is
#: deliberately ABSENT from this map — the door that refused carries its own
#: `message_key`, and re-wording it here is how two doors start explaining one
#: refusal differently.
#:
#: ⚠ **G32 IS A RATCHET AT ZERO**, so each of these resolves in `en.json` in the
#: same commit that raises it. A key that renders as its own dotted path is worse
#: than no key at all.
OWNER_ACCOUNT_MESSAGE_KEYS: dict[str, str] = {
    OWNER_ACCOUNT_CREATED: "metering.premises.ownerAccount.created",
    OWNER_ACCOUNT_ATTACHED: "metering.premises.ownerAccount.attached",
    OWNER_ACCOUNT_ALREADY_LINKED: "metering.premises.ownerAccount.alreadyLinked",
    OWNER_ACCOUNT_OWNER_NOT_NAMED: "metering.premises.ownerAccount.ownerNotNamed",
    "awaiting_identity": "metering.premises.ownerAccount.awaitingIdentity",
    OWNER_ACCOUNT_NO_ACCOUNT_TYPE: "metering.premises.ownerAccount.noAccountType",
    #: `identity_mismatch` splits by its own `reason`, because the two ask a
    #: clerk for entirely different things: one is *say which kind*, the other is
    #: *that number belongs to the other kind*.
    "kind_not_stated": "metering.premises.ownerAccount.kindNotStated",
    "identifier_belongs_to_the_other_kind": (
        "metering.premises.ownerAccount.identifierWrongKind"
    ),
}


def _owner_account_mapped(owner_name: str, data: dict[str, Any]) -> dict[str, Any]:
    """The form's owner answers, in the IMPORT FILE'S OWN VOCABULARY.

    ⛔ **`OQ-MET-12472` — ONE FUNCTION DECIDES WHAT THESE CELLS EARN, AND IT IS
    NOT THIS ONE.** `import_runs.owner_account_verdict` is that function; this
    only re-spells the form's payload into the `mapped` row it reads, so the
    screen and the spreadsheet cannot answer differently about what a name plus
    a phone earns. A second judgment on this side is exactly what
    `BR-MET-096`'s *"one runner serves every target"* and `CR-058`'s *"no door
    repeats the logic"* forbid — and on this path the two answers would be
    shown to the same clerk, one before the save and one after it.

    ⚠ **`owner_ref` IS THE TYPED PARTY'S OWN NAME AND NEVER THE FREE-TEXT BOX.**
    `BR-MET-151` clause 3: a name in `Managed by` is a NAME and not a party, and
    reading one as the other is how a wizard mints an account because a field
    was filled in (`BR-MET-112`). The form's own *no typed owner → nothing* gate
    runs first, so the verdict's `no_owner` branch is unreachable from here by
    construction — which is stated rather than relied on silently.
    """
    from apps.metering import import_runs

    mapped: dict[str, Any] = {
        "owner_ref": owner_name,
        "owner_kind": _text(data.get("owner_kind"), 40),
        "owner_account_type": _text(data.get("owner_account_type"), 120),
    }
    for column in import_runs.OWNER_IDENTIFIER_COLUMNS:
        mapped[column] = _text(data.get(column), 120)
    return mapped


def _owner_contact_block(owner_row: Any, owner_name: str) -> dict[str, Any]:
    """`DEF-MET-5847` — how this owner is REACHED, from the owner's own row.

    ⛔ **WITHOUT THIS THE DOOR REFUSED EVERY OWNER PICKED FROM THE LIST.**
    Measured on `brazosbend`, real PostgreSQL, 2026-09-19: a property saved with
    `Ridge Property LLC` picked and `Managed by` left empty answered
    `customers.contact.name_required` — **not** the identity gate everybody was
    looking at. `create_master_account` falls back to the premises' own
    free-text `owner_manager` when no contact block arrives, and after `CR-089`
    `p008` split the owner picker from `Managed by` that box is ordinarily
    EMPTY. The owner row has carried `contact_name`, `email` and `phone` since
    `BR-MET-150` and this door forwarded none of them.

    ⚠ **`full_name`, NOT `name`.** `_validate_contact` refuses an unknown key
    BY NAME, so `{"name": …}` is `customers.account.unknown_field` and not a
    contact at all. The shape is the Common Areas door's verbatim.

    ⚠ **THE PARTY'S NAME IS THE FALLBACK, AND IT IS NOT A GUESS.** All three
    contact columns are optional by ruling (*"refusing to record a party at all
    because nobody has their phone number would be worse"*), so an owner with no
    named contact is an ordinary state. `premises_owners.name` is the party this
    account is FOR — the same string `create_master_account` would have taken
    out of `owner_manager` — so using it changes who is billed not at all.
    """
    return {
        "full_name": (_text(getattr(owner_row, "contact_name", None), 200) or owner_name)[:200],
        "email": _text(getattr(owner_row, "email", None), 254),
        "phone": _text(getattr(owner_row, "phone", None), 40),
        "is_primary": True,
    }


#: ⛔ **`BR-MET-1181` — THE KEYS THAT MEAN *THIS SAVE IS ABOUT THE OWNER'S
#: ACCOUNT*.** On a PATCH, absent is this API's documented *leave it alone*, and
#: a clerk correcting a postal code must not be handed a warning about an owner
#: they never mentioned. Writing the list out rather than deriving it keeps it
#: greppable: a sixth identifier column added to the form and not added here is
#: an edit that silently stops opening accounts.
OWNER_ACCOUNT_PAYLOAD_KEYS: tuple[str, ...] = (
    "master_account_id",
    "owner_id",
    "owner_manager",
    "owner_account_type",
    "owner_kind",
    "owner_ssn",
    "owner_driving_licence",
    "owner_phone",
    "owner_tax_id",
)


#: `CR-177-BRC10` · `BR-MET-1195` — the keys that OPENED an owner account from
#: Add a premise (`BR-MET-1176`), refused by name from that door since the
#: screen became a search-and-link. `owner_manager` is NOT here: it is a real
#: `premises` column the Edit form and the import still write.
S16_REFUSED_OWNER_KEYS: tuple[str, ...] = (
    "owner_account_type",
    "owner_kind",
    "owner_ssn",
    "owner_driving_licence",
    "owner_phone",
    "owner_tax_id",
)


def _payload_touches_owner_account(data: dict[str, Any]) -> bool:
    """Did this save say anything at all about who owns the address?

    ⚠ **PRESENCE, NEVER TRUTHINESS.** `{"master_account_id": None}` is a clerk
    CLEARING the declaration and must run the path; `{}` is a clerk saying
    nothing. Reading the value instead of the key would collapse the two, which
    is `DEF-762`'s shape — *nobody was asked* and *the answer is empty* are
    different facts and a serialiser is the last place to merge them.
    """
    return any(key in data for key in OWNER_ACCOUNT_PAYLOAD_KEYS)


def _ensure_owner_master_account(
    actor: Any, row: Any, data: dict[str, Any], warnings: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """`BR-MET-1181` / `BR-MET-1010` — the owner's Master Account, from the Add
    Premises form, and the ONE place this form opens or attaches one.

    ⛔ **`DEF-MET-6139` (PO ruling 2026-09-22) — THE PREMISES NAMES ITS MASTER
    ACCOUNT DIRECTLY, AND THE OWNER RECORD IS OUT OF THE CHAIN.** PO verbatim:
    *"why you are point is at owner id - why not directly at master accoutn Id -
    it will solev the problem … owner IDs are not required hence no screens or
    fucntionality for it"*.

    **WHAT THIS FUNCTION USED TO DO, QUOTED RATHER THAN DELETED (hard-won law
    1):** it read `row.owner_id` FIRST and, when it was empty, appended
    `no_typed_owner` and **returned before it ever looked at the identity
    payload** — so a clerk typed a name, a kind and a tax id and the code
    discarded all three because they had not also picked a row from
    `premises_owners`, a table **no screen in the product can write to**
    (`createPremisesOwner` is defined in two places and called by nothing). The
    gate could not be satisfied from the product at all.

    **MEASURED BEFORE A LINE WAS CHANGED**, on real PostgreSQL, a clone of the
    `brazosbend` beta, 2026-09-22: a property saved with `Harriet Vane`, kind
    `person`, an SSN and account type `residential` left master accounts at
    **1 → 1**, no account on the address, and one warning — `no_typed_owner`. The
    same payload for a company with a Tax ID answered identically. On that
    database **0 of 79 properties** had an owner account the money path could
    find.

    ⚠ **IT IS `OQ-790`'s OWN MECHANISM, NAMED BY THE SAME PERSON ON 2026-08-27:**
    *"you ahev to call master account creation logic by passing the details and
    generate account number using Setting -> numbering and use this number to
    write premsies"*. Nothing here is a new ruling.

    ⚠ **IT GOES THROUGH THE EXISTING DOOR AND IS NOT A THIRD CREATION PATH.**
    `premises_owners.ensure_master_account_for_premises` reaches
    `customers.create_master_account` through the seam, so `BR-CUS-017`'s family,
    `BR-CUS-1011`'s one-owner-account-per-address and the whole customer
    resolution travel with it (B1/B2 §2 — customers owns `accounts`). It writes
    `premises.master_account_id` and, **where a typed owner exists, still writes
    `premises_owners.master_account_id` beside it** — the pre-ruling link that 19
    backend files read is not taken away. **It is IDEMPOTENT**, which is what
    makes saving twice safe.

    ⚠ **THREE GATES NOW, AND NOT ONE OF THEM IS GUESSED.**

      * **A NAMED ACCOUNT WINS.** `master_account_id` on the payload attaches an
        account that already exists — `BR-MET-400`, PO's own words, *"it can be
        existing master account also so at the time of premises creation we
        should check"*. Nothing is created and no customer is resolved, so it is
        reported as `owner_account_attached` and never as *created*.
      * **NO OWNER NAMED -> NOTHING.** The one remaining absence: nobody typed a
        party. See `OWNER_ACCOUNT_OWNER_NOT_NAMED` for why using the name a clerk
        typed crosses neither `BR-MET-151` clause 3 (no category is read off
        anything; **no party record is created here at all**) nor `BR-MET-112`
        (four deliberate answers, not a filled-in field).
      * **EVERYTHING ELSE -> `owner_account_verdict`, THE IMPORT'S OWN
        FUNCTION, CALLED AND NOT COPIED (`OQ-MET-12472`).** Its four remaining
        verdicts — awaiting an identifier, an identifier belonging to the other
        kind, a kind nobody stated, no account type — are reported here in its
        own words. The premises row's `premises_type` is a PROPERTY type and not
        a consumer category, so nothing is derived from it either (decision log
        2026-09-01, CR-058 W3 judgment 1).

    ⛔ **`OQ-MET-12472` IS CLOSED AND THIS FUNCTION IS WHERE IT LANDED (PO
    2026-09-19).** Two signed rulings collided on this path — *every address
    gets its owner a Master Account* (2026-08-31) against *"Without identifier
    we cannot create Customer ID or master account ot regular account"*
    (2026-09-01) — and the PO was asked which gives, in plain English, with the
    option worded as *"The Add Premises form must collect an identifier — it
    gains the same kind + identifier fields the import already has, and no
    account exists until they're supplied."* They answered **"this is
    correct"**. So the September rule stands, the August rule yields HERE, and
    the form asks. Nothing is invented to get past the gate: no kind read off a
    category, no identifier read off a phone number, no `require_identity`
    excuse taken.

    ⚠ **THE IDENTITY IS PASSED THROUGH AND IS NOT STORED ON THE OWNER**
    (decision log 2026-09-19). `premises_owners` gains no kind and no
    identifier column: identity has one home, which is `customers`, and that is
    the module with the field encryption and the blind indexes a government
    number needs. The cost a clerk actually pays is bounded: the door returns the
    account this address already holds before it reads this payload at all, so a
    second save of one address asks for nothing.
    ⚠ **AND THAT SENTENCE IS NARROWER THAN IT WAS, WHICH IS STATED RATHER THAN
    LEFT TO BE DISCOVERED.** Until 2026-09-22 the ask was *once per OWNER* — the
    owner RECORD carried the link, so a second address for the same party reused
    it. The premises carries the link now, so the ask is **once per ADDRESS for a
    party with no owner record**, and still once per owner where one exists. The
    PO ruled owner records out of the screens knowing this (*"owner IDs are not
    required"*); whether a second address for one party should find the first
    address's account by name is `OQ-MET-12573` and is OPEN. **Nothing here
    guesses at it** — matching a party by the string somebody typed is exactly
    what `BR-MET-151` clause 3 forbids.

    ⚠ **A REFUSAL NEVER COSTS THE ADDRESS, AND THE SAVEPOINT IS WHY**
    (CLAUDE.md hard-won law 14). `create_premises` is ONE transaction. In
    PostgreSQL a failed statement poisons the whole of it, so without a nested
    `atomic()` a refused owner account would make every later query raise
    `InFailedSqlTransaction` and the premises already written would be lost at
    COMMIT. **The suite runs on in-memory SQLite, which has no aborted-transaction
    state, so the version without this savepoint passes every test and destroys a
    real save.** A lane that "simplifies" it away re-breaks the address. The shape
    is copied from `import_runs.py`'s caller, which learned it first.

    **And the address is kept deliberately, not incidentally:** an address is a
    real address whether or not anybody can be billed for it — the 2026-08-27
    ruling — so the refusal is REPORTED rather than raised.

    Returns the door's own answer, or `None`. Appends exactly one warning either
    way — hard-won law 2's mirror: an outcome nothing reports is an outcome
    nobody can see.
    """
    from apps.metering import import_runs, premises_owners, seams

    # ── ALREADY DECLARED? ────────────────────────────────────────────────────
    # ⚠ **ASKED BEFORE THE CALL, BECAUSE AFTERWARDS IT IS UNANSWERABLE.** See
    # `OWNER_ACCOUNT_ALREADY_LINKED`: the door returns one shape for *created*
    # and for *found*, so this is the only moment the difference exists.
    held_before, _held_source = premises_owners.premises_master_account_link(row.pk)

    # ── GATE 1 · A NAMED ACCOUNT WINS (`BR-MET-400`, `BR-MET-1181`) ───────────
    # PO 2026-08-27: *"it can be existing master account also so at the time of
    # premises creation we should check"*. This is that check, and it runs first
    # because a clerk who names an account is making a DECLARATION — opening a
    # second one over it would be the product overruling them.
    named = _text(data.get("master_account_id"), 64)
    if named:
        return _attach_named_master_account(actor, row, named, held_before, warnings)
    if "master_account_id" in data:
        # ⚠ **AN EXPLICIT `null` IS A CLERK TAKING THE DECLARATION BACK, AND IT
        # IS A DIFFERENT FACT FROM SAYING NOTHING** (`DEF-762`'s distinction,
        # which is why `_payload_touches_owner_account` reads the KEY). It is
        # read here rather than left to fall through, because falling through
        # would OPEN a new account for an address whose owner a clerk had just
        # said they were unsure about.
        #
        # **The account itself is untouched** — hard rule 4 is nowhere near this;
        # what is withdrawn is a metering row's claim about who owns a building,
        # and the audit row records the claim that was withdrawn.
        premises_owners.declare_premises_master_account(actor, row.pk, None)
        return None

    # ── GATE 2 · WAS ANYBODY NAMED AT ALL? ──────────────────────────────────
    # ⛔ **THIS USED TO READ `row.owner_id` AND RETURN BEFORE IT LOOKED AT THE
    # IDENTITY PAYLOAD (`DEF-MET-6139`).** The owner RECORD is out of the chain
    # under the ruling of 2026-09-22; the party this account is FOR is whoever
    # the form named. `premises_owners.name` where a record was picked (its
    # contact details come with it), the free-text box otherwise — and **the
    # free-text box is what the screen now labels *Owner*.**
    owner_row = (
        models.PremisesOwner.objects.filter(tenant_id=_tenant_id(), pk=row.owner_id)
        .only("id", "name", "contact_name", "email", "phone", "master_account_id")
        .first()
        if row.owner_id
        else None
    )
    owner_name = _text(
        owner_row.name if owner_row is not None else getattr(row, "owner_manager", None),
        200,
    )
    if not owner_name:
        warnings.append(_owner_account_warning(OWNER_ACCOUNT_OWNER_NOT_NAMED))
        return None

    # ── GATE 3 · `OQ-MET-12472` — WHAT THESE ANSWERS EARN, JUDGED BY THE
    # IMPORT'S OWN FUNCTION ──────────────────────────────────────────────────
    # ⚠ **FIVE VERDICTS, ONE DEFINITION OF *ENOUGH*.** Every branch below is
    # `owner_account_verdict`'s answer re-reported in this door's vocabulary;
    # none of them re-decides anything. `no_owner` cannot be reached — the gate
    # above has already returned — and that is why it is not handled here.
    mapped = _owner_account_mapped(owner_name, data)
    verdict = import_runs.owner_account_verdict(mapped)
    if verdict["verdict"] != import_runs.OWNER_ACCOUNT_ELIGIBLE:
        # ⚠ **THE REASON IS THE VERDICT'S OWN STRING AND NOT A SECOND WORDING
        # OF IT** — `awaiting_identity`, `no_account_type`, `identity_mismatch`
        # read identically on this receipt and on an import receipt, which is
        # B14 rule 34's principle applied to a machine-readable reason.
        #
        # ⚠ **AND AN ADDRESS THAT ALREADY HAS ITS ACCOUNT IS NOT HELD BY THIS
        # GATE.** It gets that account back and nothing is written, so demanding
        # a Social Security number for a save that will write nothing would be a
        # demand with no effect.
        if not held_before:
            warnings.append(
                _owner_account_warning(
                    verdict["verdict"],
                    identity_reason=verdict.get("reason"),
                    borrowed=verdict.get("borrowed"),
                )
            )
            return None
    door_payload: dict[str, Any] = {
        "account_type": _text(data.get("owner_account_type"), 120),
        # The tenant's today, never the server's — an account that opened
        # "yesterday" in the utility's timezone dates its charges into a period
        # that may already be closed.
        "opened_at": str(seams.tenant_today()),
        # ── `DEF-MET-5847` — HOW THE OWNER IS REACHED ────────────────────────
        # Without it the door refuses by name before it looks at anything else.
        # See `_owner_contact_block`.
        #
        # ⚠ **`{}` WHERE NO OWNER RECORD WAS PICKED, AND THAT IS NOT A GAP.**
        # `create_master_account` reads an empty contact as *none supplied* and
        # falls back to the premises' own `owner_manager` — which IS the name
        # above on that branch, down to the character. So the account's contact
        # is the party a clerk typed either way, through one rule rather than a
        # second copy of it here.
        "contact": (
            _owner_contact_block(owner_row, owner_name) if owner_row is not None else {}
        ),
    }
    if verdict["verdict"] == import_runs.OWNER_ACCOUNT_ELIGIBLE:
        # ── `OQ-MET-12472` — WHO THE OWNER IS ────────────────────────────────
        # ⚠ **ASSEMBLED BY THE IMPORT'S OWN BUILDER AND RESOLVED BY CUSTOMERS.**
        # `owner_customer_block` is the same function the spreadsheet path hands
        # over, so the two doors present identical evidence; matching a
        # customer, creating one on no match, and deciding whether the minimum
        # was met are all `customers`', under `CR-058`'s *"no door repeats the
        # logic"*. Nothing here matches and nothing here creates.
        #
        # ⚠ **OMITTED RATHER THAN SENT EMPTY**, which is only reachable for an
        # address that already holds an account: an absent block is not an empty
        # one, and `create_master_account` reads the two differently.
        door_payload["customer"] = import_runs.owner_customer_block(mapped, verdict)
    try:
        # ⚠ **THE SAVEPOINT IS INSIDE THE `try`, NOT AROUND IT.** The block has to
        # EXIT by exception for PostgreSQL to roll the savepoint back; catching
        # inside it would leave the outer transaction poisoned exactly as if
        # there were no savepoint at all.
        with transaction.atomic():
            # ⛔ **ONE DOOR FOR BOTH SHAPES SINCE `BR-MET-1181`.** This used to
            # call `ensure_owner_master_account`, which takes an OWNER id and
            # therefore could not be reached at all without one — the whole of
            # `DEF-MET-6139`. `ensure_master_account_for_premises` takes the
            # ADDRESS, which is what the account belongs to (`BR-CUS-1010`), and
            # links the owner record too wherever there is one.
            answer = premises_owners.ensure_master_account_for_premises(
                actor, row.pk, door_payload
            )
    except (errors.ApiError, errors.NotFoundError) as refusal:
        warnings.append(
            {
                "code": OWNER_ACCOUNT_NOT_CREATED,
                "reason": OWNER_ACCOUNT_REFUSED,
                # The door's own sentence key and rule id. A second wording here
                # is how two doors start explaining one refusal differently, and
                # it is why `refused` is NOT in `OWNER_ACCOUNT_MESSAGE_KEYS`.
                "message_key": getattr(refusal, "message_key", None),
                "br_ref": getattr(refusal, "br_ref", None),
            }
        )
        return None
    account_id = answer.get("account_id")
    warnings.append(
        _owner_account_warning(
            OWNER_ACCOUNT_ALREADY_LINKED if held_before else OWNER_ACCOUNT_CREATED,
            account_id=account_id,
        )
    )
    return {**answer, "account_no": _master_account_no(account_id)}


def _master_account_no(account_id: Any) -> str | None:
    """The NUMBER a person quotes, for the id a machine uses.

    ⛔ **B14 RULE 31 IS SIGNED LAW: no database id is ever the visible value of a
    field.** A receipt reading *Owner's account opened* beside a UUID is exactly
    what that rule exists for — and without this the screen's only options are to
    print the id or to fetch the account again purely to print its number.

    `None` where customers cannot answer, which the caller renders as the account
    without its number rather than as no account (`DEF-127`'s posture: an absence
    is a first-class answer, never a substituted value).
    """
    from apps.metering import seams

    if account_id in (None, ""):
        return None
    numbers = seams.master_account_numbers([account_id])
    return (numbers.get(str(account_id)) or {}).get("account_no")


def _owner_account_warning(
    reason: str,
    *,
    account_id: Any = None,
    identity_reason: str | None = None,
    borrowed: Any = None,
) -> dict[str, Any]:
    """ONE warning, in the shape every consumer of this receipt reads.

    ⛔ **IT EXISTS SO THE `message_key` CANNOT BE FORGOTTEN ON A BRANCH.** Five
    outcomes were assembled inline before `BR-MET-1181`, each as its own dict
    literal, and a sixth would have been written the same way — which is how one
    branch ends up with no sentence and reaches a clerk as silence. **That is
    `G32`'s own finding one layer down** (*"21 live refusals that reach a clerk
    as silence"*): a key resolved where the helper is in the same file, and
    nothing asked about the branches that had none. Here there is one builder, so
    a missing key is a missing MAP ENTRY and the map is one screenful.

    `code` is the shape a caller switches on; `reason` is the detail. An outcome
    that CREATED or ATTACHED something is not an `owner_account_not_created`, and
    saying otherwise on a receipt is a lie about a money object.
    """
    code = (
        reason
        if reason in (OWNER_ACCOUNT_CREATED, OWNER_ACCOUNT_ATTACHED, OWNER_ACCOUNT_ALREADY_LINKED)
        else OWNER_ACCOUNT_NOT_CREATED
    )
    out: dict[str, Any] = {"code": code}
    if code == OWNER_ACCOUNT_NOT_CREATED:
        out["reason"] = reason
    # The split key where the verdict has one, the plain key otherwise. Read in
    # this order because `identity_mismatch` is one verdict asking two different
    # things of a person — see `OWNER_ACCOUNT_MESSAGE_KEYS`.
    out["message_key"] = OWNER_ACCOUNT_MESSAGE_KEYS.get(
        identity_reason or "", OWNER_ACCOUNT_MESSAGE_KEYS.get(reason)
    )
    if identity_reason:
        out["identity_reason"] = identity_reason
    if borrowed:
        out["borrowed"] = borrowed
    if account_id:
        out["account_id"] = str(account_id)
        # B14 rule 31 again: the id is for the link, the number is for the human.
        out["account_no"] = _master_account_no(account_id)
    return out


def _attach_named_master_account(
    actor: Any,
    row: Any,
    account_id: str,
    held_before: Any,
    warnings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """`BR-MET-1181` — a clerk NAMES an account that already exists.

    ⛔ **THIS IS THE HALF OF THE REPORTER'S BUG THE CREATE PATH DOES NOT COVER.**
    PO, verbatim: *"we are unabel to find and map master account to premises
    later"*. `BR-MET-400` has said since 2026-08-27 that the account *"can be
    existing master account also"*, and until today no door accepted one.

    **WHAT IT REFUSES, BY NAME AND WITHOUT GUESSING:**
      * an id this tenant does not hold — 404-never-403, like every cross-tenant
        read in this product;
      * an account that is not `kind='master'`. An ordinary account at an address
        is a TENANT's account, and naming one as the owner would bill the tenant
        for the landlord's charges. **This is precedence 3 refused at the door**:
        `accounts.premises_id` says which premises an account covers and never
        who owns it.

    ⚠ **NOTHING IS CREATED AND NO CUSTOMER IS RESOLVED**, so it is reported as
    `owner_account_attached`. Calling it *created* would be the lie
    `OWNER_ACCOUNT_ALREADY_LINKED` was minted to prevent, one case over.
    """
    from apps.metering import premises_owners, seams

    if str(held_before or "") == str(account_id):
        warnings.append(
            _owner_account_warning(OWNER_ACCOUNT_ALREADY_LINKED, account_id=account_id)
        )
        return {"created": False, "account_id": str(account_id), "reason": "already_declared",
                "account_no": _master_account_no(account_id)}
    summary = seams.owner_master_account_summary(account_id)
    if summary is None or summary.get("kind") != "master":
        warnings.append(
            {
                "code": OWNER_ACCOUNT_NOT_CREATED,
                "reason": OWNER_ACCOUNT_REFUSED,
                # The refusal's own sentence, raised where the fact lives rather
                # than re-worded: this door knows an id was named and knows what
                # came back, and nothing else in the product does. It is NOT in
                # `OWNER_ACCOUNT_MESSAGE_KEYS` for the same reason no other
                # `refused` is — that map holds this door's own outcomes.
                "message_key": "metering.premises.master_account_unknown",
                "br_ref": "BR-MET-1181",
                "named_account_id": str(account_id),
            }
        )
        return None
    premises_owners.declare_premises_master_account(actor, row.pk, account_id)
    warnings.append(_owner_account_warning(OWNER_ACCOUNT_ATTACHED, account_id=account_id))
    return {
        "created": False,
        "account_id": str(account_id),
        "account_no": summary.get("account_no"),
        "reason": "attached_an_existing_master_account",
    }


def create_premises(
    actor: Any, payload: Any, *, custom_fields_screen: str | None = None
) -> dict[str, Any]:
    """S16 guided add (US-MET-003 TC-1): one premise, optionally its first unit
    (`auto_create_unit`) with the wizard's meter grid + default-plan panel.
    ONE transaction; every row audited (BR-MET-048).

    ⚠ **`custom_fields_screen` IS THE DOOR'S FORM (`CR-161-BRC10` W2,
    `DEF-MET-9226`).** `"S16"` from Add Premises (both its own `POST /premises`
    and the City's), `"NEW_CONNECTION_PREMISE"` from New Connection Step 2,
    `None` from an import, the sample seed and every other caller — of which
    no custom field is required (PO Rules table 2026-10-02: *"A required field
    never blocks a screen that doesn't show it"*). The FIRST unit in `units`
    carries the same screen for the unit's and its service points' fields (the
    Add Premises slots are *first unit* and *services*); any further unit is
    created with `None`, because the form drew no box for it.

    ⛔ **AND SINCE `DEF-MET-5844` IT OPENS THE OWNER'S MASTER ACCOUNT** —
    `BR-MET-1010`, through `premises_owners.ensure_owner_master_account`, the
    same door New Connect walks through. See `_ensure_owner_master_account` for
    the two gates, the savepoint and the one gate this form cannot yet satisfy.
    """
    data = _payload_dict(payload)
    # ── `CR-177-BRC10` task 10b · `BR-MET-1195` — ADD A PREMISE OPENS NO ACCOUNT
    # PO 2026-10-09 on the redesign: *"you should not have these field - Account
    # type … Person or company … Managed by - it will come as part of account
    # seach"*. The screen now LINKS an existing master account and nothing
    # else, so the keys that opened a new one (`BR-MET-1176`, `OQ-MET-12472`)
    # are refused BY NAME from this door rather than quietly ignored — a stale
    # client posting them would otherwise open an account the screen no longer
    # shows it is opening. Every other door (New Connection, the import) still
    # passes them and still opens accounts exactly as before.
    if custom_fields_screen == "S16":
        _refuse_fields(
            [
                _field_error(key, errors.VAL_FORMAT, "metering.unknown_field")
                for key in S16_REFUSED_OWNER_KEYS
                if key in data
            ]
        )
    cleaned = _validate_premises(
        data, partial=False, person_form=custom_fields_screen is not None
    )
    cleaned["custom_data"] = seams.validate_custom_data(
        "premises", data.get("custom_data"), screen=custom_fields_screen
    )
    # ── `CR-177-BRC10` · `DEF-MET-10034` — NO STRAY COMMA IS STORED ──────────
    # The browser walk typed `3721 S Village Dr,` and the review read right
    # (`compose_address` trims), but the ROW kept the comma — so every other
    # screen joining the parts with ", " would print `Dr,, Avenel` again, the
    # exact defect this door was fixed for. Add a premise stores each part
    # trimmed of edge commas and spaces, as `compose_address` reads it.
    if custom_fields_screen == "S16":
        for part in ("address_line", "city", "state", "postal_code"):
            if isinstance(cleaned.get(part), str):
                cleaned[part] = cleaned[part].strip().strip(",").strip()
    warnings: list[dict[str, Any]] = []
    from apps.metering import selectors

    # ── `CR-177-BRC10` task 1 · `BR-MET-1190` — THE SAME ADDRESS, REFUSED ────
    # PO 2026-10-09: *"exact same address if existing in system then you
    # should promp user"*. The screen asks as the clerk completes the address;
    # this asks AGAIN at the moment of the write, because the screen's answer
    # is a courtesy and two clerks can type one address in the same minute.
    # ⚠ **A PERSON'S FORM ONLY.** `custom_fields_screen` is `"S16"` from Add a
    # premise (its own `POST /premises` AND the City's door, which delegates
    # here with the same screen). An import, the sample seed and New Connection
    # pass something else and are not refused here — the import has its own
    # duplicate handling and New Connection is refused at Approve
    # (`DEF-CUS-6350`). ⚠ `add_anyway: true` is the clerk's *Add it anyway*,
    # and it is the ONLY way past (`is True`, so the string `"false"` is no yes).
    if custom_fields_screen == "S16" and data.get("add_anyway") is not True:
        from apps.metering import address_match

        same = address_match.premises_with_same_address(
            cleaned.get("address_line"),
            cleaned.get("city"),
            cleaned.get("state"),
            cleaned.get("postal_code"),
        )
        if same is not None:
            raise same_address_refusal(same)

    with transaction.atomic():
        premise_no = _allocate_unused_number(
            actor, PREMISES_SERIES, warnings, model=models.Premises, field="premise_no"
        )
        # ── `DEF-MET-9847` · THE INDEX'S REFUSAL IS THE SAME SENTENCE ─────────
        # The check in `_validate_premises` answers the ordinary case; this
        # answers the RACE — two clerks, or a double press, both passing the
        # check before either writes — which reached the clerk as our 500
        # (`IntegrityError … uq_premises_tenant_external_ref_ci`), measured on
        # PostgreSQL 16 on 2026-10-07. ⚠ **THE NESTED `atomic()` IS A SAVEPOINT
        # AND IT IS THE ONLY OPTION, NOT THE TIDY ONE (hard-won law 14).** The
        # refusal must READ the other property's address after the failed
        # INSERT; on PostgreSQL that read raises `InFailedSqlTransaction` unless
        # the failure was rolled back to a savepoint first. SQLite has no
        # aborted state, so a version without it passes the default suite.
        status = cleaned.pop("status", "active")
        try:
            with transaction.atomic():
                row = models.Premises.objects.create(
                    tenant_id=_tenant_id(),
                    premise_no=premise_no,
                    status=status,
                    **{k: v for k, v in cleaned.items() if k != "status"},
                    # CR-089 wave A `PUJ-04` — the **Mark checked** control on
                    # the create form. An empty dict when the caller said
                    # nothing about it.
                    **_gis_check_stamp(data, actor),
                )
        except IntegrityError as exc:
            if not _is_parcel_collision(exc):
                raise
            raise _parcel_taken("external_ref", str(cleaned.get("external_ref") or "")) from exc
        _audit(
            actor,
            "premises.created",
            "premises",
            row.id,
            after=selectors.premises_detail_dict(row),
        )
        created_units: list[dict[str, Any]] = []
        unit_payloads = data.get("units")
        if unit_payloads is None and data.get("auto_create_unit"):
            unit_payloads = [data.get("unit") or {}]
        for index, unit_payload in enumerate(unit_payloads or []):
            created_units.append(
                _create_unit_inner(
                    actor,
                    {**dict(unit_payload or {}), "premises_id": str(row.id)},
                    warnings,
                    custom_fields_screen=custom_fields_screen if index == 0 else None,
                )
            )
        # BR-MET-083(a), and it runs AFTER the units so the first unit is
        # included: a premises created straight into an area joins that area's
        # active routes without anyone re-opening the route wizard.
        routes_joined = cascade_area_to_routes(actor, row)
        # ── CR-089 wave B `B6` · `DEF-MET-4715` — THE ROUTE THE CLERK CHOSE ──
        #
        # PO 2026-09-08, verbatim: *"In header we are not shouding Route and
        # Cycle information … you should add that at the time of creation also
        # - **it should be optional**"*.
        #
        # ⚠ **`route` WAS ALREADY ON THIS PAYLOAD'S TOLERATED-KEY LIST AND
        # NOTHING READ IT (`DEF-MET-4715`).** Every other unknown key on a
        # premises create is refused by name with `metering.unknown_field`;
        # this one sat beside `units`/`unit`/`auto_create_unit` with no
        # consumer, so `POST /premises {"route": "COMPLETE NONSENSE, NOT A
        # ROUTE"}` answered **201** and dropped it. Proved live on brazosbend
        # 2026-09-09: `P-00081`, `routes_joined []`. That is hard-won law 2 on a
        # server payload rather than a React prop, and no gate reads it.
        #
        # ⚠ **IT RUNS AFTER THE AREA CASCADE AND ADDS RATHER THAN REPLACES.**
        # `_join_units_to_route` never takes a unit off another route
        # (BR-MET-083 boundary 2: moving one is BR-MET-074's move and *"a move
        # triggered by a form field on a different screen is a move nobody
        # agreed to"*). So choosing a route here fills the gap the area did not,
        # and a clerk who chooses the route the area would have picked anyway
        # gets one membership, not two.
        if (chosen := _resolve_create_route(data)) is not None:
            routes_joined.extend(_join_premises_to_route(actor, row, chosen))
        # ── `DEF-MET-5844` · `BR-MET-1010` — THE OWNER'S MASTER ACCOUNT ──────
        # LAST, and inside this transaction rather than after it: the account
        # and the address are one act, so a rollback of the premises takes the
        # account with it. The reverse is NOT true and is the whole design —
        # the door has its own savepoint, so a refused account leaves the
        # address standing. Everything above it must already be written: the
        # door reads `premises.owner_id` back and `BR-CUS-1011` asks the
        # database whether this address already holds an owner account.
        # ⚠ `CR-177-BRC10` · `BR-MET-1195`: from Add a premise the door runs
        # only when the clerk LINKED an account. Without one there is nothing
        # to attach and nothing may be opened, so the old *no owner named*
        # warning would be a sentence about an act this screen no longer does.
        owner_master_account = (
            _ensure_owner_master_account(actor, row, data, warnings)
            if custom_fields_screen != "S16" or "master_account_id" in data
            else None
        )
    return {
        **selectors.premises_detail_dict(models.Premises.objects.get(pk=row.pk)),
        "units": created_units,
        "routes_joined": routes_joined,
        # ⚠ **SERVED EVEN WHEN IT IS `None`, AND THAT IS THE POINT.** A key that
        # appears only on success is a key a screen cannot ask about; the
        # matching `warnings` row says WHY it is null.
        "owner_master_account": owner_master_account,
        "warnings": warnings,
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def update_premises(
    actor: Any,
    premises_id: Any,
    changes: Any,
    *,
    custom_fields_screen: str | None = None,
) -> dict[str, Any]:
    """S14 edit (US-MET-001). ONE transaction, audited (BR-MET-048).

    `custom_fields_screen` — `"PREMISE_EDIT"` from the Edit premise form; `None`
    from every other caller (the GIS run, an import upsert). `custom_data` is
    validated only when the payload carries it, MERGED into the stored answers,
    and a required field placed Input on that screen counts a stored answer
    (`CR-161-BRC10` W2, `DEF-MET-9226`).

    ⚠ **CHANGING `inside_city_limits` CHANGES WHAT THIS ADDRESS IS CHARGED, AND
    THIS FUNCTION APPLIES THAT FORWARD ONLY — A STATED ASSUMPTION, NOT A RULING
    (`OQ-423`, CR-039 wave C task 10).**

    BR-RAT-102's factor multiplies every base line and every usage line of a
    bill, and BR-RAT-107's `city_limits` tax scope narrows on the same flag. So
    correcting a premises from *inside* to *outside* changes money — and no
    signed document says whether that reaches anything ALREADY BILLED.

    **What this code does, and why:** nothing. It writes the column and stops.
    The next bill run reads the new value through
    `gather._jurisdiction_factor_for` and prices accordingly; every issued
    invoice, invoice line, payment and journal entry is left exactly as it was.
    That follows CLAUDE.md hard rule 4 — *no UPDATE/DELETE on issued invoices;
    corrections are new rows* — so the safe reading is the only one this
    function can take without inventing an adjustment nobody signed.

    **What is NOT decided and is on the PO's agenda as `OQ-423`:** whether a
    corrected flag owes the customer (or the utility) an adjustment on bills
    already issued at the wrong jurisdiction, and if so who raises it and on
    what date it lands. A DRAFT bill in an open run is the same question one
    step earlier. Neither is stubbed with `NotImplementedError`, because
    *forward-only* is not a gap in the code — it is the behaviour, written down
    here so the next agent reads a decision and not an absence.
    """
    data = _payload_dict(changes)
    # `except_premises_id` is what lets the taken-parcel guard run here at all:
    # without it this row would be refused for colliding with itself.
    cleaned = _validate_premises(
        data,
        partial=True,
        except_premises_id=premises_id,
        person_form=custom_fields_screen is not None,
    )
    from apps.metering import selectors

    routes_joined: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    with transaction.atomic():
        row = _premises_row(premises_id, locked=True)
        before = selectors.premises_detail_dict(row)
        if "custom_data" in data:
            cleaned["custom_data"] = seams.validate_custom_data(
                "premises",
                data["custom_data"],
                screen=custom_fields_screen,
                existing=row.custom_data or {},
            )
        fields: list[str] = []
        # CR-089 wave A `PUJ-10` — *Checked against GIS · <who> · <when>*. The
        # stamp rides in with the ordinary change so ONE audit row carries the
        # flag and the person who moved it (BR-MET-048).
        for field, value in {**cleaned, **_gis_check_stamp(data, actor)}.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                fields.append(field)
        if fields:
            # `DEF-MET-9847` — the same savepoint and the same sentence as
            # `create_premises`, for the same race on the Edit premise form.
            try:
                with transaction.atomic():
                    row.save(update_fields=[*fields, "updated_at"])
            except IntegrityError as exc:
                if not _is_parcel_collision(exc):
                    raise
                raise _parcel_taken(
                    "external_ref", str(cleaned.get("external_ref") or ""), except_id=premises_id
                ) from exc
            _audit(
                actor,
                "premises.updated",
                "premises",
                row.id,
                before=before,
                after=selectors.premises_detail_dict(row),
            )
        if "area" in fields:
            # BR-MET-083(a). Only on a CHANGE — re-saving the same area must not
            # re-run the cascade, and boundary 4 is why this is one-directional:
            # a tag change never takes the premises OFF the routes it is on.
            routes_joined = cascade_area_to_routes(actor, row)
        # ── `BR-MET-1181` · `DEF-MET-6139` — THE OWNER'S ACCOUNT, ON EDIT TOO ──
        # ⛔ **THIS IS THE HALF OF THE REPORTER'S SENTENCE THE CREATE PATH DOES
        # NOT COVER:** *"we are unabel to find and map master account to premises
        # LATER"*. Until today `update_premises` touched the owner's account not
        # at all, so an address saved before the form asked for an identifier
        # could never acquire one, and an existing master account could never be
        # attached from any screen.
        #
        # ⚠ **IT RUNS ONLY WHEN THE PAYLOAD SAYS SOMETHING ABOUT IT.** Absent is
        # this API's documented *leave it alone*; a clerk correcting a postal
        # code must not be handed a warning about an owner they did not mention,
        # and an unconditional call would append one to every edit in the
        # product. See `_payload_touches_owner_account`.
        owner_master_account = (
            _ensure_owner_master_account(actor, row, data, warnings)
            if _payload_touches_owner_account(data)
            else None
        )
    return {
        **selectors.premises_detail_dict(_premises_row(premises_id)),
        "routes_joined": routes_joined,
        # ⚠ **SERVED EVEN WHEN IT IS `None`, AND THAT IS THE POINT.** A key that
        # appears only on success is a key a screen cannot ask about; the
        # matching `warnings` row says WHY it is null. `create_premises` serves
        # the identical pair, so one renderer draws both receipts.
        "owner_master_account": owner_master_account,
        "warnings": warnings,
    }


# ── CR-089 wave D · a place can be taken out of service, and put back ───────
# PO 2026-09-08, verbatim: *"Allow user to cahnge Unit and Premsies status"*.
#
# ⚠ **THE REFUSAL SENTENCES ARE WRITTEN OUT, NEVER BUILT FROM A KIND.**
# `f"metering.premises.status.hold.{kind}"` would be a catalogue key no grep can
# find and no gate can resolve — G32's exact blind spot, where a refusal that
# reaches a clerk as SILENCE is indistinguishable from one that resolves. Every
# key below is a literal string in this file and in all eleven catalogues.
PREMISES_HOLD_KEYS: dict[str, str] = {
    "open_accounts": "metering.premises.status.holdAccounts",
    "unpaid_balances": "metering.premises.status.holdBalances",
    "attached_assets": "metering.premises.status.holdAssets",
    "active_units": "metering.premises.status.holdUnits",
}
UNIT_HOLD_KEYS: dict[str, str] = {
    "open_accounts": "metering.units.status.holdAccount",
    "unpaid_balances": "metering.units.status.holdBalance",
}
STATUS_VALUES = ("active", "inactive")

#: The field-error keys, WRITTEN OUT for the same reason the hold keys above
#: are: a key assembled from the entity name at run time is a catalogue string
#: no grep finds and no gate can resolve.
PREMISES_STATUS_FIELD_KEYS: dict[str, str] = {
    "status_required": "metering.premises.status_required",
    "status_unknown": "metering.premises.status_unknown",
    "reason_required": "metering.premises.status_reason_required",
    "date_required": "metering.premises.status_date_required",
    "date_format": "metering.premises.status_date_format",
    "date_future": "metering.premises.status_date_future",
}
UNIT_STATUS_FIELD_KEYS: dict[str, str] = {
    "status_required": "metering.unit.status_required",
    "status_unknown": "metering.unit.status_unknown",
    "reason_required": "metering.unit.status_reason_required",
    "date_required": "metering.unit.status_date_required",
    "date_format": "metering.unit.status_date_format",
    "date_future": "metering.unit.status_date_future",
}


def _status_hold_params(preview: dict[str, Any]) -> dict[str, Any]:
    """What the refused screen needs to draw the SAME list it was already
    showing — the counts, and which one is holding the commit."""
    return {
        "held_by": preview["held_by"],
        "counts": {row["kind"]: row["count"] for row in preview["dependencies"]},
        "dependencies": preview["dependencies"],
    }


def _refuse_if_held(preview: dict[str, Any], keys: dict[str, str], br_ref: str) -> None:
    """BR-MET-1164 (and BR-MET-047's money term), enforced in ONE place.

    ⚠ **BOTH DOORS COME THROUGH HERE, AND THAT IS THE POINT.** The list row's
    `POST /premises/{id}/deactivate` predates this wave and is still live; if it
    kept its own narrower blocker set, a signed rule would be breachable by
    pressing the other button. One computation, two callers.
    """
    if not preview["blocked"]:
        return
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref=br_ref,
        message_key=keys[preview["held_by"]],
        params=_status_hold_params(preview),
    )


def _validate_status_change(payload: Any, *, keys: dict[str, str]) -> dict[str, Any]:
    """`status`, `effective_date` and `reason` — all three REQUIRED, both ways.

    CR-089 §6 D1/D2: *"a date and a reason are required"*, and the reactivation
    *"with the same date and reason"*. **They live in `audit_log` and in no
    column**, exactly as `move_unit`'s do, so neither can be queried back today —
    stated here rather than implied (hard-won law 1).

    ⚠ **A FUTURE DATE IS REFUSED.** Neither `premises.status` nor `units.deleted_at`
    holds a pending change, so an accepted future date would be applied at once
    and then read as scheduled — `move_unit`'s reasoning, one screen over, and
    the same refusal.
    """
    data = _payload_dict(payload)
    known = {"status", "effective_date", "reason"}
    fe: list[dict[str, Any]] = []
    for field in data:
        if field not in known:
            fe.append(_field_error(field, errors.VAL_FORMAT, "metering.unknown_field"))
    _refuse_fields(fe)

    status = _text(data.get("status"), 20)
    if not status:
        _refuse_fields(
            [_field_error("status", errors.VAL_REQUIRED, keys["status_required"])]
        )
    if status not in STATUS_VALUES:
        _refuse_fields(
            [
                _field_error(
                    "status",
                    errors.VAL_UNKNOWN_LOOKUP,
                    keys["status_unknown"],
                    allowed=list(STATUS_VALUES),
                )
            ]
        )
    reason = _text(data.get("reason"), 500)
    if not reason:
        _refuse_fields(
            [_field_error("reason", errors.VAL_REQUIRED, keys["reason_required"])]
        )
    raw_date = data.get("effective_date")
    if not raw_date:
        _refuse_fields(
            [
                _field_error(
                    "effective_date", errors.VAL_REQUIRED, keys["date_required"]
                )
            ]
        )
    try:
        effective_date = date.fromisoformat(str(raw_date))
    except ValueError:
        _refuse_fields(
            [
                _field_error(
                    "effective_date", errors.VAL_FORMAT, keys["date_format"]
                )
            ]
        )
        raise  # unreachable — _refuse_fields always raises when handed a row
    if effective_date > seams.tenant_today():
        _refuse_fields(
            [
                _field_error(
                    "effective_date", errors.VAL_RANGE, keys["date_future"]
                )
            ]
        )
    return {"status": status, "effective_date": effective_date, "reason": reason}


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035")
def change_premises_status(actor: Any, premises_id: Any, payload: Any) -> dict[str, Any]:
    """`POST /premises/{id}/status` — take a property out of service, or put it back.

    BR-MET-1164, PO 2026-09-08 verbatim: *"if you ahve units - active, assets or
    active accounts, you cannot shut down building pr premises."*

    ⚠ **REACTIVATION IS BLOCKED BY NOTHING, DELIBERATELY.** Every dependency this
    rule names is a reason not to STOP serving an address; none of them is a
    reason not to start again. CR-089 §8 names reactivation as the one half of
    this wave a rollback must keep, because reverting without it strands
    everything already deactivated with no screen that can bring it back.
    """
    from apps.metering import selectors

    fields = _validate_status_change(payload, keys=PREMISES_STATUS_FIELD_KEYS)
    with transaction.atomic():
        row = _premises_row(premises_id, locked=True)
        if row.status == fields["status"]:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-1164",
                message_key="metering.premises.status_unchanged",
                params={"status": row.status},
            )
        if fields["status"] == "inactive":
            _refuse_if_held(
                selectors.status_change_dict(
                    entity="premises",
                    entity_id=str(row.id),
                    status=row.status,
                    dependencies=selectors.premises_status_dependencies(row),
                ),
                PREMISES_HOLD_KEYS,
                "BR-MET-1164",
            )
        before = {"status": row.status}
        row.status = fields["status"]
        row.save(update_fields=["status", "updated_at"])
        _audit(
            actor,
            "premises.deactivated" if fields["status"] == "inactive" else "premises.reactivated",
            "premises",
            row.id,
            before=before,
            after={
                "status": row.status,
                # The dated EVENT, in the only place that holds it (hard rule 7).
                "effective_date": fields["effective_date"].isoformat(),
                "reason": fields["reason"],
                "br_ref": "BR-MET-1164",
            },
        )
    return selectors.premises_detail_dict(_premises_row(premises_id))


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035")
def change_unit_status(actor: Any, unit_id: Any, payload: Any) -> dict[str, Any]:
    """`POST /units/{id}/status` — the same, one level down (BR-MET-1164, `PUJ-48`).

    A unit has no stored status column (US-MET-002 §5), so *inactive* is
    `deleted_at` set and *active* is it cleared — the same one column
    `deactivate_unit` has always written, read back by `_unit_status`.

    ⚠ **A UNIT MAY NOT BE REACTIVATED ONTO AN INACTIVE PROPERTY, AND THAT IS
    DERIVED FROM BR-MET-1164 RATHER THAN INVENTED.** The rule says a property
    cannot be inactive while a unit on it is active. Allowing the reverse move
    would breach that invariant through the back door one press later, leaving a
    live flat in a building the utility has stopped serving. Recorded as a build
    judgment in the decision log of 2026-09-08 (law 13), not put back to the PO.
    """
    from apps.metering import selectors

    fields = _validate_status_change(payload, keys=UNIT_STATUS_FIELD_KEYS)
    with transaction.atomic():
        row = _unit_row(unit_id, locked=True)
        current = "inactive" if row.deleted_at is not None else "active"
        if current == fields["status"]:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-1164",
                message_key="metering.unit.status_unchanged",
                params={"status": current},
            )
        if fields["status"] == "inactive":
            _refuse_if_held(
                selectors.status_change_dict(
                    entity="unit",
                    entity_id=str(row.id),
                    status=current,
                    dependencies=selectors.unit_status_dependencies(row),
                ),
                UNIT_HOLD_KEYS,
                "BR-MET-1164",
            )
        elif row.premises.status == "inactive":
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-1164",
                message_key="metering.units.status.holdPremises",
                params={"premise": row.premises.premise_no or ""},
            )
        before = {"status": current}
        row.deleted_at = None if fields["status"] == "active" else timezone.now()
        row.save(update_fields=["deleted_at", "updated_at"])
        _audit(
            actor,
            "unit.deactivated" if fields["status"] == "inactive" else "unit.reactivated",
            "unit",
            row.id,
            before=before,
            after={
                "status": fields["status"],
                "effective_date": fields["effective_date"].isoformat(),
                "reason": fields["reason"],
                "br_ref": "BR-MET-1164",
            },
        )
    return selectors.unit_detail_dict(_unit_row(unit_id))


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035")
def deactivate_premises(actor: Any, premises_id: Any, payload: Any = None) -> dict[str, Any]:
    """IS-1 deactivate-first — the LIST row's door, now recording what the dialog does.

    ⚠ **IT USED TO RECORD NO DATE AND NO REASON, AND THAT WAS THE DEFECT
    (`DEF-4743`, PO ruling 2026-09-10, option (b): _keep it, make it demand a
    date and reason_).** Two doors led out of service. Both enforced the same
    blockers — `BR-MET-1164`, off the same counts — so nothing unsafe ever got
    through either. What differed is what was WRITTEN DOWN: `change_premises_status`
    put the effective date and the reason into `audit_log`, and this one put
    neither. A clerk who went out of service from the LIST row left no record of
    WHEN it took effect or WHY, and nothing on any screen said so.

    ⚠ **THE FIX IS DELEGATION RATHER THAN A SECOND COPY, and that is the whole
    point.** This function now validates the same three fields and calls the
    dialog's own service. A rule enforced at one door and re-implemented at the
    other is a rule that will diverge at the next amendment — which is exactly
    how these two doors came to differ in the first place. There is one path
    through the blockers, one audit shape, and one place to change either.

    ⚠ **BEHAVIOUR CHANGE, STATED RATHER THAN DISCOVERED: THE PAYLOAD IS NOW
    REQUIRED.** `POST /premises/{id}/deactivate` keeps its address, and a caller
    that sends nothing now gets a field error naming `effective_date` and
    `reason` instead of a silent success that loses the audit facts. The product
    itself no longer calls this route at all — the list row was re-pointed at the
    dialog in the same CR — so the callers this can affect are outside it.
    """
    fields = dict(_payload_dict(payload))
    # The only status this door has ever set. Forced rather than accepted, so a
    # caller cannot reactivate through an endpoint named `deactivate`.
    fields["status"] = "inactive"
    return change_premises_status(actor, premises_id, fields)


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035")
def delete_premises(actor: Any, premises_id: Any) -> None:
    """BR-MET-037/BR-MET-001: hard delete ONLY with zero units; otherwise the
    IS-1 audit-lock refuses and offers Deactivate."""
    from apps.metering import selectors

    with transaction.atomic():
        row = _premises_row(premises_id, locked=True)
        unit_count = models.Unit.objects.filter(tenant_id=row.tenant_id, premises=row).count()
        if unit_count:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-MET-037",
                message_key="metering.premises.delete_blocked_has_units",
                params={"units": unit_count, "alternative": "deactivate"},
            )
        before = selectors.premises_detail_dict(row)
        row.delete()
        _audit(actor, "premises.deleted", "premises", premises_id, before=before)


# ── units (US-MET-002 / US-MET-003 · BR-MET-002/006/007/036/037/046/047) ────
def _unit_row(unit_id: Any, *, locked: bool = False) -> models.Unit:
    if not _is_uuid(unit_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    qs = models.Unit.objects.filter(tenant_id=_tenant_id(), pk=unit_id)
    if locked:
        qs = qs.select_for_update()
    row = qs.select_related("premises").first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _validate_unit(payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}
    known = {
        "label",
        "unit_type",
        "floor_label",
        "square_feet",
        "unit_no",
        "is_common_area",
        # ── CR-089 wave A · `BR-MET-1162` (PO ruling 2026-09-08) ────────────
        # A unit's OWN map point. ⚠ **AND NOTHING ELSE FROM AN ADDRESS** — the
        # ruling narrows `BR-MET-1161`'s coordinate clause and its address half
        # stands, so `address_line`, `city`, `postal_code` and `state` are still
        # refused here as `metering.unknown_field`, exactly as they always were.
        # A unit refines a premises by LABEL.
        "lat",
        "lng",
        # ── 2026-09-17 · `DEF-INT-5600` / `DEF-INT-5602` — THE CITY'S KEYS ───
        # ⚠ **THE COLUMNS EXISTED AND NOTHING COULD WRITE THEM.** `CR-112` added
        # `units.gis_point_id` and `units.gis_status` in `metering/0057` and
        # gave them a selector and a screen; the only writer anyone built was
        # `gis_match`, which is reachable only from `gis_parcels`, which had no
        # caller at all (`DEF-INT-5601`). So the live path — the create form —
        # met `metering.unknown_field` and the column was NULL on every unit.
        # The premises' two equivalents have been on `_validate_premises`'s own
        # list since `CR-112`; these two are the same fact one level down.
        "gis_point_id",
        "gis_status",
        # ── 2026-09-17 · `DEF-INT-5629` — AND THE FOUR THE *RUN* WRITES ──────
        # ⚠ **THE TWO ABOVE ARE WHAT A CREATE FORM SENDS; THESE FOUR ARE WHAT
        # THE RECONCILIATION RUN SENDS, AND WITHOUT THEM IT COULD NOT WRITE ONE
        # ROW.** `gis_parcels._persist` patches the replaced-key pair and the
        # verified stamp (`BR-MET-1173`) on every unit whose point the City
        # confirmed; this set carried none of them, so the first apply answered
        # `metering.unknown_field` and — because `ValidationError` is not the
        # `DatabaseError` the savepoint catches — took the whole run down on row
        # one rather than skipping one unit. It could survive only because
        # `DEF-INT-5601` meant nothing had ever called the run.
        #
        # ⚠ **AND THIS IS NOT THE ADDRESS HALF OF `BR-MET-1161` REOPENING.**
        # `address_line`, `city`, `state` and `postal_code` are still refused
        # here as `metering.unknown_field`, exactly as the note above says: a
        # unit refines a premises by LABEL. What arrives here is the City's own
        # key for an address POINT inside that building, which is the same
        # narrowing `BR-MET-1162` already made for `lat`/`lng`.
        "gis_point_id_was",
        "gis_key_changed_at",
        "gis_verified",
        "gis_verified_at",
    }
    # `custom_data` / `service_point_custom_data` — `CR-161-BRC10` W2
    # (`DEF-MET-9227`, `DEF-MET-9173`): validated by the CALLER through
    # `seams.validate_custom_data`, which knows the door's screen.
    ignored = {
        "premises_id",
        "meters",
        "plan",
        "services",
        "sub_meter",
        "custom_data",
        "service_point_custom_data",
    }
    for field in payload:
        if field not in known and field not in ignored:
            if field == "occupancy":
                # BR-MET-036: occupancy is DERIVED — the wizard captures no
                # occupancy input anywhere, and the API refuses one.
                fe.append(
                    _field_error(
                        "occupancy", errors.VAL_FORMAT, "metering.unit.occupancy_is_derived"
                    )
                )
            else:
                fe.append(_field_error(field, errors.VAL_FORMAT, "metering.unknown_field"))
    _refuse_fields(fe)

    if "label" in payload or not partial:
        label = _text(payload.get("label"), 120)
        if not label:
            fe.append(_field_error("label", errors.VAL_REQUIRED, "metering.unit.label_required"))
        out["label"] = label
    # `DEF-INT-5629` — the replaced-key pair and the verified stamp. ⚠ The
    # point key and the status are copied lower down by `DEF-INT-5600`'s own
    # block, which landed on the branch while this was being written; a second
    # copy here would be the same field written twice from one payload.
    _gis_run_fields(payload, out, fe)
    if "unit_type" in payload:
        unit_type = _text(payload["unit_type"], 60)
        if unit_type is None:
            out["unit_type"] = None
        else:
            # BR-MET-084 (CR-010 A-4): the tenant's own `unit_types` rows are
            # the allowed set; the legacy tuple only backstops a tenant with
            # no rows. The stored value is the row's canonical code.
            resolved = _resolve_unit_type(unit_type)
            if resolved is None:
                fe.append(
                    _field_error(
                        "unit_type",
                        errors.VAL_UNKNOWN_LOOKUP,
                        "metering.unit.type_unknown",
                        allowed=_allowed_unit_types(),
                    )
                )
            else:
                out["unit_type"] = resolved
    if "floor_label" in payload:
        out["floor_label"] = _text(payload["floor_label"], 60)
    if "unit_no" in payload:
        out["unit_no"] = _text(payload["unit_no"], 60)
    # ── `DEF-INT-5600` / `DEF-INT-5602` — TRIMMED ONLY, NEVER NORMALISED ─────
    # `_validate_premises`'s own posture for `gis_parcel_id`/`gis_status`, and
    # the reasoning is the same one: a key is the City's string and we are not
    # the ones who decide what a valid one looks like. Comparison is
    # case-insensitive (`BR-INT-073`); STORAGE is as given.
    for field, limit in (("gis_point_id", 120), ("gis_status", 60)):
        if field in payload:
            out[field] = _text(payload[field], limit)
    if "is_common_area" in payload:
        # BR-MET-101: a common area is a unit with a FLAG — a strict boolean,
        # because "truthy" would let "false" (a non-empty string) flag a unit
        # somebody lives in as shared space and bill it to the owner.
        raw = payload["is_common_area"]
        if not isinstance(raw, bool):
            fe.append(
                _field_error(
                    "is_common_area", errors.VAL_FORMAT, "metering.unit.common_area_boolean"
                )
            )
        else:
            out["is_common_area"] = raw
    if "square_feet" in payload:
        raw = payload["square_feet"]
        if raw in (None, ""):
            out["square_feet"] = None
        else:
            try:
                square_feet = int(raw)
            except (TypeError, ValueError):
                square_feet = -1
            if square_feet < 0:
                fe.append(
                    _field_error("square_feet", errors.VAL_RANGE, "metering.unit.square_feet_range")
                )
            else:
                out["square_feet"] = square_feet
    # ── CR-089 wave A · `BR-MET-1162` — the unit's own point ────────────────
    # ⚠ **BOTH OR NEITHER, AND THE PAIR IS REFUSED AS A PAIR.** Half a point is
    # not a place: a unit holding a latitude and no longitude cannot be drawn,
    # and the fallback (*read the building's*) is keyed on the pair being
    # absent — so one of the two would leave the unit neither placed nor fallen
    # back, which is a third state the rule does not have.
    # ⚠ **CLEARING IS A REAL ANSWER**, not a missing one: `{"lat": null,
    # "lng": null}` is a clerk saying *this unit has no point of its own after
    # all*, and the unit goes back to reading its building's. Absent from the
    # payload leaves whatever is stored alone.
    lat_present = "lat" in payload
    lng_present = "lng" in payload
    if lat_present != lng_present:
        fe.append(
            _field_error(
                "lat" if lng_present else "lng",
                errors.VAL_REQUIRED,
                "metering.unit.point_needs_both",
            )
        )
    elif lat_present:
        blank = [field for field in ("lat", "lng") if payload[field] in (None, "")]
        if len(blank) == 1:
            fe.append(
                _field_error(
                    blank[0], errors.VAL_REQUIRED, "metering.unit.point_needs_both"
                )
            )
        elif blank:
            out["lat"] = None
            out["lng"] = None
        else:
            for field, limit in (("lat", Decimal("90")), ("lng", Decimal("180"))):
                try:
                    value = Decimal(str(payload[field])).quantize(Decimal("0.000001"))
                except (ArithmeticError, TypeError, ValueError):
                    fe.append(
                        _field_error(
                            field, errors.VAL_FORMAT, "metering.unit.coordinate_format"
                        )
                    )
                    continue
                # The same fence `_validate_premises` puts on a typed pin, for
                # the same reason: a latitude of -98 is a typo, not a place.
                if value < -limit or value > limit:
                    fe.append(
                        _field_error(
                            field, errors.VAL_FORMAT, "metering.unit.coordinate_range"
                        )
                    )
                    continue
                out[field] = value
    _refuse_fields(fe)
    return out


def _check_unit_label_unique(
    premises: models.Premises, label: str, *, exclude_pk: Any = None
) -> None:
    """BR-MET-002: label unique within (tenant, premise) — US-MET-003 TC-5."""
    qs = models.Unit.objects.filter(
        tenant_id=premises.tenant_id, premises=premises, label__iexact=label
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        _refuse_fields(
            [
                _field_error(
                    "label",
                    errors.VAL_FORMAT,
                    "metering.unit.label_duplicate",
                    premise=premises.premise_no or str(premises.pk),
                    label=label,
                )
            ]
        )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def create_unit(
    actor: Any, payload: Any, *, custom_fields_screen: str | None = None
) -> dict[str, Any]:
    """S16 unit wizard (US-MET-003 TC-2): unit + service_points + the meter
    grid (≤1 meter per enabled service — BR-MET-006) + the default-plan panel
    (BR-MET-007/BR-CUS-014). Nothing is priced here.

    `custom_fields_screen` — the door's form for the unit's and its service
    points' custom fields (`"UNIT_ADD"` from Add units); `None` from an import
    or any other caller, of which no custom field is required."""
    data = _payload_dict(payload)
    warnings: list[dict[str, Any]] = []
    with transaction.atomic():
        result = _create_unit_inner(
            actor, data, warnings, custom_fields_screen=custom_fields_screen
        )
    return {**result, "warnings": warnings + result.get("warnings", [])}


def _service_point_custom_data(
    data: dict[str, Any], codes: list[str], screen: str | None
) -> dict[str, dict[str, Any]]:
    """`CR-161-BRC10` W2 · `DEF-MET-9173` — each new service point's answers.

    `service_point_custom_data` is keyed by SERVICE CODE, because a service
    point is one service at one unit and the form draws one block per service
    the unit takes (a water valve is not the gas one). Every service point the
    create makes is validated — including one the payload names no answers
    for — so a required field placed Input on this screen is refused for the
    service that left it blank. A key naming a service the unit does NOT take
    is refused by name rather than dropped: an answer typed against nothing is
    the silent loss `DEF-836` records.
    """
    raw = data.get("service_point_custom_data")
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        _refuse_fields(
            [
                _field_error(
                    "service_point_custom_data",
                    errors.VAL_FORMAT,
                    "settings.customFields.values_not_object",
                )
            ]
        )
    stray = sorted(str(code) for code in raw if code not in codes)
    if stray:
        _refuse_fields(
            [
                _field_error(
                    f"service_point_custom_data.{code}",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.unit.service_not_taken",
                    service=code,
                )
                for code in stray
            ]
        )
    return {
        code: seams.validate_custom_data("service_points", raw.get(code), screen=screen)
        for code in codes
    }


def _create_unit_inner(
    actor: Any,
    data: dict[str, Any],
    warnings: list[dict[str, Any]],
    *,
    custom_fields_screen: str | None = None,
) -> dict[str, Any]:
    from apps.metering import selectors

    premises_id = data.get("premises_id")
    if not premises_id:
        _refuse_fields(
            [_field_error("premises_id", errors.VAL_REQUIRED, "metering.unit.premises_required")]
        )
    premises = _premises_row(premises_id)
    cleaned = _validate_unit(data, partial=False)
    cleaned["custom_data"] = seams.validate_custom_data(
        "units", data.get("custom_data"), screen=custom_fields_screen
    )
    _check_unit_label_unique(premises, cleaned["label"])
    unit_no = cleaned.pop("unit_no", None) or _allocate_unused_number(
        actor, UNIT_SERIES, warnings, model=models.Unit, field="unit_no"
    )
    unit = models.Unit.objects.create(
        tenant_id=premises.tenant_id, premises=premises, unit_no=unit_no, **cleaned
    )
    # BR-MET-083(b) — DEF-225's symptom. This runs BEFORE the service points and
    # the meter grid below, so everything they create inherits route and cycle
    # through `ensure_service_point`'s membership lookup instead of needing a
    # second stamp. Order is load-bearing; do not move it after the grid.
    routes_joined = cascade_premises_routes_to_unit(actor, unit)
    service_codes = _services_for_a_new_unit(data, premises, warnings)
    point_answers = _service_point_custom_data(data, service_codes, custom_fields_screen)
    for code in service_codes:
        point_id = ensure_service_point(unit.id, code)
        if point_answers.get(code):
            models.ServicePoint.objects.filter(tenant_id=unit.tenant_id, pk=point_id).update(
                custom_data=point_answers[code]
            )
    meters = _apply_meter_grid(actor, unit, data.get("meters") or [], warnings)
    plan = data.get("plan")
    plan_result = None
    if plan:
        plan_result = _apply_unit_plan(actor, unit, dict(plan), source="new_connection")
    _audit(actor, "unit.created", "unit", unit.id, after=selectors.unit_detail_dict(unit))
    return {
        **selectors.unit_detail_dict(models.Unit.objects.get(pk=unit.pk)),
        "meters": meters,
        "plan_assignment": plan_result,
        "routes_joined": routes_joined,
        "warnings": warnings,
    }


def _services_for_a_new_unit(
    data: dict[str, Any], premises: Any, warnings: list[dict[str, Any]]
) -> list[str]:
    """**`BR-MET-119` AS AMENDED 2026-09-25 — WHAT A NEW UNIT STARTS WITH.**

    PO ruling 2026-09-25, verbatim: *"the premises' list is what a unit takes,
    the tick-list stays, and a clerk may untick"*. So a unit's set is **within**
    the premises' set rather than equal to it, and the default is the whole of
    it.

    ⚠ **THE DEFAULT IS HERE, IN THE SERVICE LAYER, AND NOT ON THE FORM.** Every
    door reaches this function — the units wizard, `POST /units`, the premises
    create's inline first unit, the importer — and a default written into a
    React form is a default three of those four doors do not have. That is the
    whole of `DEF-MET-6796`: the tick-list was the only thing that ever wrote
    `services`, so **every unit the Add units wizard has ever made carries no
    service points at all** while its address offers several, and
    `BR-BIL-300` makes service points decide what a bill charges.

    **ABSENT IS NOT EMPTY, AND THAT DISTINCTION IS THE WHOLE RULE** (`DEF-762`'s
    shape one layer up):

      * **no `services` key** — nobody was asked, so the address answers:
        the unit inherits the premises' offer.
      * **`services: []`** — a clerk was asked and unticked everything. It is
        honoured, and the unit is created with no service points. Lawful.
      * **`services: ["water"]`** — a clerk unticked the rest. Honoured.

    ⚠ **IT IS A SUBSET OF THE OFFER AND NEVER A SUPERSET.**
    `_refuse_service_not_at_premises` is the guard on the other side and it
    stays exactly as it was: this function may only ever narrow. The
    intersection with the tenant's ENABLED services (`BR-MET-003`, the outer
    bound) is what keeps that true through time — an address that offered gas
    before the utility stopped selling it would otherwise make every new unit
    at that address refuse, on a create that had nothing to do with gas. The
    dropped codes are **named in a warning rather than dropped in silence**
    (hard-won law 1), because a create that quietly gives a unit fewer services
    than its address advertises is the defect this function exists to close.

    ⚠ **A PREMISES HOLDING `NULL` INHERITS NOTHING, AND THAT IS NOT A BUG.**
    `NULL` means nobody has ever been asked what this address offers
    (`DEF-756`/`DEF-762`), and an address nobody has been asked about has
    provisioned nothing — `BR-MET-119`'s own words. Defaulting from it would be
    this layer answering on the utility's behalf; `_refuse_service_not_at_premises`
    would refuse each one anyway, so the create would die on a service nobody
    typed.
    """
    asked = _clean_services(data.get("services"), "services")
    if asked is not None:
        return asked
    offered = premises.services_available
    if not offered:
        return []
    enabled = seams.enabled_service_codes()
    inherited = [code for code in offered if code in enabled]
    if skipped := [code for code in offered if code not in enabled]:
        warnings.append(
            {
                "code": "premises_services_not_enabled",
                "services": skipped,
                "premises": _premises_ref(premises),
            }
        )
    return inherited


def _premises_ref(premises: Any) -> str:
    """What a clerk CALLS this address — its premise number if it has one, its
    address line otherwise.

    Never the id. BR-MET-119's third clause makes the refusal sentence the
    feature: it must name the address the clerk has to go and change, and
    nobody searches a premises list by uuid.
    """
    for value in (premises.premise_no, premises.address_line):
        text = str(value or "").strip()
        if text:
            return text
    return "this address"  # pragma: no cover — address_line is NOT NULL


def _refuse_service_not_at_premises(tenant_id: Any, unit: Any, service_code: str) -> None:
    """BR-MET-119 · THE THIRD LINK OF THE CHAIN (PO 2026-08-26, CR-036).

    **PREMISES → UNITS → METERS.** A premises DECLARES what services are
    available at the address; a unit INHERITS that list **BY DEFAULT** and has
    none of its own (CR-037 withdrawn); a meter may only be fitted into one of
    those slots. PO
    verbatim: *"Refuse it ; if they want that servcie then they ahve to
    provision it on that unit or premise first"*.

    ⚠ **THIS IS THE INNER BOUND, NOT A REPLACEMENT.** `BR-MET-003` — *"does
    this utility sell it"* — is asked first, is still right, and is simply the
    wrong SCOPE for this question. That is the whole of DEF-772: the check that
    existed passed a gas meter onto a unit at a water/sewer/trash address
    because the utility sold gas somewhere.

    ⚠ **TENANT-SCOPED ON PURPOSE (CLAUDE.md hard rule 1).** `unit.premises`
    follows an FK that carries no tenant of its own, so without the filter
    another tenant's service list could decide what this tenant's meter may
    attach to. A premises not visible in this tenant gets the same 404 the unit
    itself would (HR-1: existence must not leak).

    ⚠ **`NULL` IS NOT AN EMPTY LIST (DEF-756/762).** `NULL` means nobody has
    been asked which services this address offers — the state of EVERY premises
    built through the product before 2026-08-26, because no screen could write
    the field. `[]` means somebody was asked and said none. Both REFUSE, per
    the ruling: an address nobody has been asked about has provisioned nothing.
    They refuse with different sentences because *"add it here"* and *"tell us
    what this address offers"* are different jobs for the clerk, and a refusal
    that describes the wrong one sends them nowhere.
    """
    premises = models.Premises.objects.filter(tenant_id=tenant_id, pk=unit.premises_id).first()
    if premises is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    offered = premises.services_available
    if offered is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.premises_services_unknown",
            params={"service": service_code, "premises": _premises_ref(premises)},
            field_errors=[
                _field_error(
                    "service",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.premises_services_unknown",
                    service=service_code,
                    premises=_premises_ref(premises),
                )
            ],
        )
    if service_code not in offered:
        # An ANSWERED empty list is still an answer, and it reads as one:
        # "…offers nothing, not electric" rather than a sentence with a hole.
        offered_text = ", ".join(str(code) for code in offered) or "nothing"
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.service_not_at_premises",
            params={
                "service": service_code,
                "premises": _premises_ref(premises),
                "offered": offered_text,
            },
            field_errors=[
                _field_error(
                    "service",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.service_not_at_premises",
                    service=service_code,
                    premises=_premises_ref(premises),
                    offered=offered_text,
                )
            ],
        )


def ensure_service_point(unit_id: Any, service_code: str) -> Any:
    """Get-or-create the unit's service point for a service the utility SELLS
    (BR-MET-003) **and the address OFFERS** (BR-MET-119, the inner bound added
    2026-08-26 — see `_refuse_service_not_at_premises`). The assets lane calls
    this through its seam — service_points is metering-owned, so the asset
    module never writes it directly (B1)."""
    tenant_id = _tenant_id()
    unit = models.Unit.objects.filter(tenant_id=tenant_id, pk=unit_id).first()
    if unit is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if service_code not in seams.enabled_service_codes():
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.service_not_enabled",
            params={"service": service_code},
            field_errors=[
                _field_error(
                    "service",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.service_not_enabled",
                    service=service_code,
                )
            ],
        )
    _refuse_service_not_at_premises(tenant_id, unit, service_code)
    service_id = seams.service_row_id(service_code)
    if service_id is None:  # pragma: no cover - catalog is seeded in migration 0001
        raise errors.SysError(errors.SYS_INTERNAL, message_key="metering.service_catalog_missing")
    # DEF-227 — THE UNIT'S MEMBERSHIP FOR **THIS** SERVICE, not whichever row
    # came back first. BR-MET-074 made a unit able to hold several memberships
    # (one per service) and this lookup was written when it could hold at most
    # one, so a house on water and electric could have its new gas meter read by
    # the water crew. A NULL-service membership is a legacy all-services route
    # and is the fallback, never the preference.
    #
    # ── CR-029 RC-W4-T3 · THE DRAFT LEAK (B17 §5 gap G4) ───────────────────
    # ⚠ **A DRAFT ROUTE STAMPS NOTHING, AND THIS IS THE THIRD PATH THAT HAS TO
    # SAY SO.** BR-MET-076: *"a draft route stamps no service point"* —
    # `_stamp_service_points` returns early for a draft and
    # `_stamp_added_service_points` does too, and this lookup did not, so the
    # membership row a draft route wrote in step 2 of the wizard became a LIVE
    # stamp the moment a meter arrived. `selectors.units_in_cycle` reads that
    # stamp, so a draft reached the bill run — which is exactly the consequence
    # DEF-219 ruled must not exist: *"a draft is a thing that has not happened
    # yet and must not have consequences a person can see"*.
    #
    # The draft CYCLE gets the same guard for the same reason: both other
    # stampers write `cycle = route.cycle if route.cycle.status != "draft"`, and
    # this one wrote the cycle whatever its status.
    live = models.RouteMembership.objects.filter(tenant_id=tenant_id, unit=unit).exclude(
        route__status="draft"
    )
    membership = (
        live.filter(service_id=service_id).first() or live.filter(service_id__isnull=True).first()
    )
    route = membership.route if membership else None
    cycle = route.cycle if route and route.cycle_id and route.cycle.status != "draft" else None
    row, _created = models.ServicePoint.objects.get_or_create(
        tenant_id=tenant_id,
        unit=unit,
        service_id=service_id,
        defaults={"route": route, "cycle": cycle},
    )
    return row.id


def _apply_meter_grid(
    actor: Any, unit: models.Unit, rows: Any, warnings: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """BR-MET-006 / BR-AST-028: one row per enabled service; modes
    auto-generate | assign-existing | leave-blank. Asset rows are created or
    linked in the ONE registry through the assets seam — never here."""
    results: list[dict[str, Any]] = []
    if not isinstance(rows, (list, tuple)):
        _refuse_fields([_field_error("meters", errors.VAL_FORMAT, "metering.meters_not_a_list")])
    enabled = seams.enabled_service_codes()
    seen_services: set[str] = set()
    for index, raw in enumerate(rows):
        row = dict(raw or {})
        service = str(row.get("service") or "").strip()
        field = f"meters[{index}]"
        if service not in enabled:
            # BR-MET-003 / US-MET-003 TC-4: a disabled service renders disabled;
            # a submitted row for one is refused server-side.
            _refuse_fields(
                [
                    _field_error(
                        field,
                        errors.VAL_UNKNOWN_LOOKUP,
                        "metering.service_not_enabled",
                        service=service,
                    )
                ]
            )
        if service in seen_services:
            _refuse_fields(
                [
                    _field_error(
                        field, errors.VAL_FORMAT, "metering.meter.one_per_service", service=service
                    )
                ]
            )
        seen_services.add(service)
        mode = str(row.get("mode") or "leave_blank").strip()
        if mode == "leave_blank":
            results.append({"service": service, "mode": mode, "asset": None})
            continue
        if mode not in ("auto_generate", "assign_existing"):
            _refuse_fields(
                [_field_error(field, errors.VAL_UNKNOWN_LOOKUP, "metering.meter.mode_unknown")]
            )
        service_point_id = ensure_service_point(unit.id, service)
        if mode == "assign_existing":
            asset = seams.attach_existing_asset(
                actor=actor,
                asset_no=row.get("asset_no") or row.get("meter_no"),
                unit_id=str(unit.id),
                service_point_id=str(service_point_id),
                install_date=row.get("install_date"),
            )
        else:
            asset = seams.create_asset_for_unit(
                actor=actor,
                unit_id=str(unit.id),
                service_point_id=str(service_point_id),
                payload={
                    "type": row.get("type") or "meter",
                    "asset_no": row.get("asset_no") or row.get("meter_no"),
                    "serial_no": row.get("serial_no"),
                    "read_method": row.get("read_method"),
                    "multiplier": row.get("multiplier", 1),
                    "unit": row.get("unit") or seams.service_default_uom(service),
                    "parent_asset_no": row.get("master") or row.get("parent_asset_no"),
                    "install_date": row.get("install_date"),
                    "allocation_rule": row.get("allocation_rule"),
                    "loss_tolerance_pct": row.get("loss_tolerance_pct"),
                },
            )
        if asset is None:  # pragma: no cover - assets lane ships in this packet
            warnings.append({"code": "assets_lane_unwired", "service": service})
        results.append({"service": service, "mode": mode, "asset": asset})
    return results


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def update_unit(
    actor: Any,
    unit_id: Any,
    changes: Any,
    *,
    custom_fields_screen: str | None = None,
) -> dict[str, Any]:
    """BR-MET-046: a unit NEVER moves between premises — a premises change is
    refused outright (deactivate + recreate is the only path).

    `custom_fields_screen` — `"UNIT_EDIT"` from Edit unit, `None` otherwise.
    `custom_data` is validated only when sent and MERGED into the stored
    answers (`CR-161-BRC10` W2, `DEF-MET-9227`). A service point's answers are
    typed only where it is created (Part 2 row 8), so a PATCH naming
    `service_point_custom_data` is refused by name rather than dropped.

    ── CR-089 wave F `F6` (`PUJ-44`/`PUJ-45`) · THE PLAN MOVES WITH THE EDIT ──
    PO 2026-09-08, verbatim: *"youa re not allowing to add plan here from drop
    down - we shuld attached plans and it should be options, when I edit it
    later you should allow to change the plan ot apply the plan"*. A unit had
    no edit SCREEN of its own at all — the pencil lived on the units list — and
    the plan was a separate modal on a separate tab, so *change the label and
    put it on the right plan* was three screens.

    ⚠ **`plan` WAS ALREADY ACCEPTED HERE AND WAS SILENTLY DROPPED.**
    `_validate_unit`'s `ignored` set has carried `"plan"` since S16 so that the
    CREATE payload could be handed to it whole; on a PATCH nothing then read
    it. So `PATCH /units/{id}` with a plan block answered **200**, changed the
    label, left the plan exactly as it was and said nothing — the silent-drop
    shape `DEF-836` records on a list filter, on a money path. It is applied
    now, and it is applied through **`_apply_unit_plan`, the same function the
    create and the plan modal call**: `BR-MET-042`'s occupied-unit override
    warning, `BR-MET-040`'s lock guard, `BR-RAT-030`'s unpublished-plan refusal
    and the `unit.plan_assigned` audit row are that function's and are not
    restated here. A second implementation of *put this unit on this plan* is
    the one outcome this wave must not produce.

    ⚠ **ONE TRANSACTION, so a refused plan takes the label change back with
    it.** The alternative — two calls behind one Save button — leaves a clerk
    who mistyped a plan with a renamed unit and no way to tell which half
    landed.
    """
    data = _payload_dict(changes)
    from apps.metering import selectors

    if "premises_id" in data or "premises" in data:
        raise errors.BizError(
            errors.BIZ_IMMUTABLE,
            br_ref="BR-MET-046",
            message_key="metering.unit.premises_immutable",
            params={"alternative": "deactivate_and_recreate"},
        )
    if "service_point_custom_data" in data:
        _refuse_fields(
            [
                _field_error(
                    "service_point_custom_data", errors.VAL_FORMAT, "metering.unknown_field"
                )
            ]
        )
    cleaned = _validate_unit(data, partial=True)
    plan = data.get("plan")
    plan_result: dict[str, Any] | None = None
    with transaction.atomic():
        row = _unit_row(unit_id, locked=True)
        if "label" in cleaned and cleaned["label"].lower() != (row.label or "").lower():
            _check_unit_label_unique(row.premises, cleaned["label"], exclude_pk=row.pk)
        before = selectors.unit_detail_dict(row)
        if "custom_data" in data:
            cleaned["custom_data"] = seams.validate_custom_data(
                "units",
                data["custom_data"],
                screen=custom_fields_screen,
                existing=row.custom_data or {},
            )
        fields: list[str] = []
        for field, value in cleaned.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                fields.append(field)
        if fields:
            row.save(update_fields=[*fields, "updated_at"])
            _audit(
                actor,
                "unit.updated",
                "unit",
                row.id,
                before=before,
                after=selectors.unit_detail_dict(row),
            )
        if plan:
            # ⚠ **`change_plan`, WHICH IS AN EXISTING WORD AND NOT A NEW ONE.**
            # `rating.models.UnitPlanAssignment.source` documents its own
            # vocabulary in the column — `new_connection|move_in|change_plan|
            # bulk_update|import` — and a plan changed from the unit's edit
            # form IS a change of plan. Minting a sixth value (`unit_edit`)
            # would put a word nobody ruled into a signed history table, where
            # every later reader would have to guess whether it meant something
            # the other five do not. The same default `assign_unit_plan` takes.
            plan_result = _apply_unit_plan(actor, row, dict(plan), source="change_plan")
    return {
        **selectors.unit_detail_dict(_unit_row(unit_id)),
        # ⚠ **ABSENT WHEN NO PLAN WAS SENT, `null` WHEN ONE WAS AND THE HELPER
        # HAD NOTHING TO SAY.** A caller must be able to tell *I did not ask*
        # from *I asked and nothing came back*; collapsing them is how a screen
        # comes to report an override warning it never received.
        **({"plan_assignment": plan_result} if plan else {}),
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def move_unit(actor: Any, unit_id: Any, payload: Any) -> dict[str, Any]:
    """BR-MET-095 (CR-024, PO 2026-08-21): move a unit to another premise.

    ── WHY THIS EXISTS AT ALL, WHEN BR-MET-046 FORBADE IT ────────────────────
    PO verbatim: *"please ensure move units works in Units; we have that
    functionalities - you can have a modal for that; bascially user has put a
    unit in wrong premises they want to move it to correct premises."*

    BR-MET-046 refused the move to protect *"by-premises money traceability"*.
    **That property is guaranteed by the LEDGER STAMP and not by this refusal**,
    and it was checked rather than assumed: `apps/ledger/posting.py` writes
    `journal_lines.premises_id` at POSTING time (US-LED-002), and
    `ledger.reporting.by_premises_summary` groups on that stamp with no
    read-time account -> unit -> premises join — US-LED-010 TC-5 is a structural
    test on that function's source asserting exactly that, for exactly this
    reason. So money already posted stays against the premise it was posted
    under, and a move changes what the unit's NEXT bill is attributed to.
    BR-MET-046 is stamped SUPERSEDED-REFINED, not deleted: the guarantee it
    names still holds — it is simply not this refusal that holds it.

    ── WHAT THIS REFUSES, AND WHY EACH REFUSAL IS NOT A PREFERENCE ───────────
    * **A move with no reason** — the audit row is the only place the move is
      recorded, so a move with no reason is a move nobody can explain later.
    * **A move with no effective date** — CR-024's shape is a dated EVENT.
    * **A FUTURE effective date.** Nothing in this product can hold a pending
      move: `units` has one `premises_id` and no dated move history, so a
      future date would be accepted, applied immediately, and then MISREAD as
      scheduled. Refused by name rather than silently applied — the honest
      shape until a dated move history is a story somebody owns.
    * **A move onto the premise the unit is already on** — that is not an event,
      and writing one would put a no-op in the audit trail.
    * **A move that would collide with a label already used on the
      destination** (BR-MET-002 / `uq_units_tenant_premises_label`): refused
      before the write, naming the destination's own premise number.
    * **A move of a unit that has EVER had an account, without an explicit
      acknowledgement.** This is the case BR-MET-046 was written for. It is not
      blocked — BR-MET-042's precedent is the PO's own: *"allow the override to
      handle human or user errors"* — but the caller must say it means it, and
      the count travels in the refusal so the screen can state it.

    ⛔ **THE COUNT IN THAT REFUSAL IS ACCOUNTS, NOT BILLS — DEF-511.** CR-024
    asks the warning to state *"how many bills"*; nothing in this product
    answers issued-invoices-by-unit (`seams` declares no such contract), so this
    reports `accounts`, which it CAN count, and never a bill figure it would
    have to invent.

    The effective date and the reason live in `audit_log` and in no column, so
    neither can be read back by a query today. Stated here rather than implied.
    """
    data = _payload_dict(payload)
    known = {"premises_id", "effective_date", "reason", "acknowledge_accounts"}
    fe: list[dict[str, Any]] = []
    for field in data:
        if field not in known:
            fe.append(_field_error(field, errors.VAL_FORMAT, "metering.unknown_field"))
    _refuse_fields(fe)

    target_id = data.get("premises_id")
    if not target_id:
        _refuse_fields(
            [_field_error("premises_id", errors.VAL_REQUIRED, "metering.unit.premises_required")]
        )
    reason = _text(data.get("reason"), 500)
    if not reason:
        _refuse_fields(
            [_field_error("reason", errors.VAL_REQUIRED, "metering.unit.move_reason_required")]
        )
    raw_date = data.get("effective_date")
    if not raw_date:
        _refuse_fields(
            [
                _field_error(
                    "effective_date", errors.VAL_REQUIRED, "metering.unit.move_date_required"
                )
            ]
        )
    try:
        effective_date = date.fromisoformat(str(raw_date))
    except ValueError:
        _refuse_fields(
            [_field_error("effective_date", errors.VAL_FORMAT, "metering.unit.move_date_format")]
        )
        raise  # unreachable — _refuse_fields always raises when handed a row
    if effective_date > seams.tenant_today():
        _refuse_fields(
            [_field_error("effective_date", errors.VAL_RANGE, "metering.unit.move_date_future")]
        )

    from apps.metering import selectors

    with transaction.atomic():
        row = _unit_row(unit_id, locked=True)
        target = _premises_row(target_id, locked=True)
        if row.premises_id == target.pk:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-095",
                message_key="metering.unit.move_same_premises",
                params={"premise": target.premise_no or str(target.pk)},
            )
        if row.label:
            _check_unit_label_unique(target, row.label, exclude_pk=row.pk)
        accounts = seams.account_reference_count(row.id)
        if accounts > 0 and not bool(data.get("acknowledge_accounts")):
            raise errors.BizError(
                errors.BIZ_APPROVAL,
                br_ref="BR-MET-095",
                message_key="metering.unit.move_needs_override",
                # ⚠ `count` IS NOT A DUPLICATE OF `accounts` — IT IS WHAT MAKES
                # THE SENTENCE GRAMMATICAL (`DEF-MET-4694`, CR-089 `PUJ-47`).
                # The refusal used to read *"2 account(s)"*: a machine's plural
                # on the one sentence asking a person to accept an irreversible
                # consequence. The catalogue answers it with `_one`/`_other` in
                # all eleven languages now, and i18next selects the form from a
                # parameter it insists is called `count`. `accounts` stays
                # beside it because that is the name the envelope has carried
                # since CR-024 and a screen reading it must not break.
                params={"accounts": accounts, "count": accounts},
            )
        before = selectors.unit_detail_dict(row)
        row.premises = target
        row.save(update_fields=["premises", "updated_at"])
        after = dict(selectors.unit_detail_dict(_unit_row(unit_id)))
        # The dated EVENT, in the only place that holds it (hard rule 7).
        after["move"] = {
            "from_premises_id": str(before.get("premises_id") or ""),
            "from_premise_no": before.get("premise_no"),
            "to_premises_id": str(target.pk),
            "to_premise_no": target.premise_no,
            "effective_date": effective_date.isoformat(),
            "reason": reason,
            "accounts_ever_attached": accounts,
            "acknowledged": bool(data.get("acknowledge_accounts")),
            "br_ref": "BR-MET-095",
        }
        _audit(actor, "unit.moved", "unit", row.id, before=before, after=after)
    return selectors.unit_detail_dict(_unit_row(unit_id))


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035")
def deactivate_unit(actor: Any, unit_id: Any, payload: Any = None) -> dict[str, Any]:
    """IS-1 deactivate-first — the LIST row's door, now recording what the dialog does.

    ⚠ **IT RECORDED NO DATE AND NO REASON, AND THAT IS `DEF-MET-4761` — THE
    TWIN OF `DEF-4743` ONE LEVEL DOWN.** The PO ruled that one on 2026-09-10,
    option (b): *keep the door, make it demand a date and a reason*. This is the
    same door on the same rule for a unit instead of a property, so the ruling
    is applied rather than put back to them (hard-won law 13).

    Both doors always enforced the same blockers — `BR-MET-1164`, off the same
    counts through `_refuse_if_held` — so nothing unsafe ever got through
    either. What differed is what was WRITTEN DOWN: `change_unit_status` puts
    the effective date and the reason into `audit_log`, and this one put
    neither. A clerk who took a flat out of service from the units LIST left no
    record of WHEN it took effect or WHY, and no screen said so.

    ⚠ **THE FIX IS DELEGATION RATHER THAN A SECOND COPY.** One path through the
    blockers, one audit shape, one place to change either. A rule enforced at
    one door and re-implemented at the other is a rule that will diverge at the
    next amendment — which is exactly how these two came to differ.

    ⚠ **TWO BEHAVIOUR CHANGES, STATED RATHER THAN DISCOVERED.**
      · The payload is now REQUIRED: a caller sending nothing gets a field
        error naming `reason` or `effective_date` instead of a silent success
        that loses both facts.
      · It is no longer IDEMPOTENT. This function used to answer 200 on a unit
        that was already inactive; `change_unit_status` refuses that with
        `metering.unit.status_unchanged`, because *deactivate something already
        deactivated* is a mistake worth naming rather than a no-op worth
        hiding. `deactivate_premises` made the same move on the same ruling.
    The product itself no longer calls this route at all — the units-list row
    was re-pointed at the status dialog in the same commit — so the callers this
    can affect are outside it.
    """
    fields = dict(_payload_dict(payload))
    # The only status this door has ever set. Forced rather than accepted, so a
    # caller cannot reactivate through an endpoint named `deactivate`.
    fields["status"] = "inactive"
    return change_unit_status(actor, unit_id, fields)


def unit_reference_counts(unit: models.Unit) -> dict[str, int]:
    """BR-MET-037 probe set: account · asset · read references."""
    return {
        "accounts": seams.account_reference_count(unit.id),
        "assets": seams.asset_reference_count(unit.id),
        "reads": seams.read_reference_count(unit.id),
    }


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035")
def delete_unit(actor: Any, unit_id: Any) -> None:
    """BR-MET-037: hard delete only when NEVER referenced by an account, asset
    or read; otherwise the audit-lock refuses and offers Deactivate."""
    from apps.metering import selectors

    with transaction.atomic():
        row = _unit_row(unit_id, locked=True)
        counts = {k: v for k, v in unit_reference_counts(row).items() if v}
        if counts:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-MET-037",
                message_key="metering.unit.delete_blocked_referenced",
                params={"referenced_by": counts, "alternative": "deactivate"},
            )
        before = selectors.unit_detail_dict(row)
        models.RouteMembership.objects.filter(tenant_id=row.tenant_id, unit=row).delete()
        models.ServicePoint.objects.filter(tenant_id=row.tenant_id, unit=row).delete()
        row.delete()
        _audit(actor, "unit.deleted", "unit", unit_id, before=before)


# ── unit plan assignment (BR-MET-007/040/041/042/044 · BR-CUS-014) ──────────
def _guard_plan_lock(actor: Any, unit: models.Unit) -> None:
    """BR-MET-007: "plan lock gates changes by permission".

    Until 2026-08-11 `units.plan_locked` was WRITTEN by the wizard, READ back by
    the selector, asserted by a test — and consulted by nothing. A locked plan
    could be changed by anyone the endpoint already admitted, which is every
    caller that reaches here. The flag was decoration (hard-won law 2 — built is
    not wired; the PO named it as gap 3 on 2026-08-11 and ruled "fix it").

    WHAT "BY PERMISSION" RESOLVES TO, and why this is derivation not invention:
    the roles are platform-defined and closed (System Admin · Billing Clerk ·
    Executive, A4 CONFIRMED). This surface already admits exactly System Admin
    and Billing Clerk, and Executive cannot reach it at all. A lock that "gates
    by permission" inside that pair therefore has one reading — Admin passes,
    Clerk does not — because any other reading gates nobody. Recorded in the
    review-ledger row so the PO ratifies the reading, not just the code.

    Applies to the WHOLE plan panel, not only the plan id. Letting a Clerk clear
    `plan_locked` in the same payload that changes the plan would make the lock
    self-defeating: unlock and edit in one call, gate satisfied, nothing gated.
    """
    if not unit.plan_locked:
        return
    if getattr(actor, "role", None) == SYSTEM_ADMIN:
        return
    raise errors.BizError(
        errors.BIZ_LOCKED,
        br_ref="BR-MET-007",
        message_key="metering.plan.locked",
        params={"unit_id": str(unit.id), "required_role": SYSTEM_ADMIN},
    )


def _apply_unit_plan(
    actor: Any, unit: models.Unit, payload: dict[str, Any], *, source: str
) -> dict[str, Any]:
    _guard_plan_lock(actor, unit)
    fe: list[dict[str, Any]] = []
    # `tariff_id` is still accepted as an INPUT NAME because S16 and the wizard
    # payloads use it; what it now names is a PLAN (PO ruling 2026-08-11). The
    # field name is the screen's, the target is rating's `rate_plans`.
    plan_id = payload.get("plan_id") or payload.get("tariff_id")
    if not plan_id:
        fe.append(_field_error("tariff_id", errors.VAL_REQUIRED, "metering.plan.tariff_required"))
    _refuse_fields(fe)
    plan = seams.plan_ref(plan_id)
    if plan is None:
        # BR-RAT-030: an unpublished plan resolves to None as well as an unknown
        # one. Both are "you cannot put a unit on this", and separating them
        # would leak which ids exist.
        _refuse_fields(
            [_field_error("tariff_id", errors.VAL_UNKNOWN_LOOKUP, "metering.plan.tariff_unknown")]
        )
    effective_from = payload.get("effective_from")
    if effective_from:
        try:
            effective_from = date.fromisoformat(str(effective_from))
        except ValueError:
            _refuse_fields(
                [_field_error("effective_from", errors.VAL_FORMAT, "metering.plan.bad_date")]
            )
    else:
        effective_from = seams.tenant_today()

    warning: dict[str, Any] | None = None
    account = seams.active_account_for_unit(unit.id)
    if account is not None and unit.rate_plan_id is not None:
        # BR-MET-042 (PO PU-12): a direct unit-level plan edit on an OCCUPIED
        # unit is allowed as an error-correction OVERRIDE — with warning +
        # audit. Normal changes go through the account Change-plan flow.
        warning = {
            "code": "unit_plan_override_on_occupied_unit",
            "br_ref": "BR-MET-042",
            "account": account,
        }
    before = {
        "rate_plan_id": str(unit.rate_plan_id) if unit.rate_plan_id else None,
        "plan_effective_from": (
            unit.plan_effective_from.isoformat() if unit.plan_effective_from else None
        ),
        "plan_locked": unit.plan_locked,
        "vacant_standby_auto": unit.vacant_standby_auto,
    }
    unit.rate_plan_id = plan["id"]
    unit.plan_effective_from = effective_from
    if "plan_locked" in payload:
        unit.plan_locked = bool(payload["plan_locked"])
    if "vacant_standby_auto" in payload:
        unit.vacant_standby_auto = bool(payload["vacant_standby_auto"])
    unit.save(
        update_fields=[
            "rate_plan",
            "plan_effective_from",
            "plan_locked",
            "vacant_standby_auto",
            "updated_at",
        ]
    )
    # BR-CUS-013 / BR-MET-041: the append-only dated history row, RATING-owned.
    #
    # This is no longer allowed to come back empty. From W1 until 2026-08-11 it
    # always did — rating had never authored the writer — and the response said
    # so honestly with `history_recorded: false`. Honest, and still a unit whose
    # mid-cycle plan change could not be priced. Now that the row is writable,
    # a missing one is a fault, not a status: the plan column and the history
    # must move together or the unit's coverage develops a hole that only shows
    # up months later, inside a bill.
    history = seams.record_unit_plan_assignment(
        unit_id=str(unit.id),
        rate_plan_id=plan["id"],
        assigned_from=effective_from.isoformat(),
        source=source,
        # ⚠ `str(x) or None` DOES NOT SURVIVE `x is None`: `str(None)` is the
        # four-character string "None", which is truthy, so the `or None` never
        # fires and a uuid column is handed the word None. Measured 2026-08-16
        # on the sample-data load, whose actor legitimately carries no user id
        # when identity cannot attribute the run: every premises/unit block died
        # on `ValidationError: '"None" is not a valid UUID'` and the whole
        # metering block reported FAILED. Absence is tested for, once, here.
        actor_user_id=(None if getattr(actor, "id", None) is None else str(actor.id)),
        reason=payload.get("reason"),
    )
    if history is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-CUS-013",
            message_key="metering.plan.history_unavailable",
            params={"unit_id": str(unit.id)},
        )
    after = {
        "rate_plan_id": plan["id"],
        "plan_name": plan["name"],
        "plan_version": plan["version"],
        "plan_effective_from": effective_from.isoformat(),
        "plan_locked": unit.plan_locked,
        "vacant_standby_auto": unit.vacant_standby_auto,
    }
    _audit(actor, "unit.plan_assigned", "unit", unit.id, before=before, after=after)
    # BR-MET-042's occupied-unit override and rating's backdating warning (PO
    # ruling 2026-08-11, option B) are two different things that can BOTH be
    # true of one assignment, so they travel as a LIST. `warning` stays exactly
    # as it was — S16 and the existing tests read it — and `warnings` is what a
    # caller should read from now on. A warning buried inside `history` is a
    # warning the screen never shows (hard-won law 2).
    warnings = [entry for entry in (warning, history.get("warning")) if entry]
    return {
        "unit_id": str(unit.id),
        **after,
        # No longer a status field that can read false: a None history raises
        # above. Kept in the response because callers and tests read it, and
        # because "the history row exists" is worth stating rather than
        # inferring from the absence of an error.
        "history_recorded": True,
        "history": history,
        "warning": warning,
        "warnings": warnings,
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def assign_unit_plan(actor: Any, unit_id: Any, payload: Any) -> dict[str, Any]:
    data = _payload_dict(payload)
    with transaction.atomic():
        unit = _unit_row(unit_id, locked=True)
        return _apply_unit_plan(actor, unit, data, source=str(data.get("source") or "change_plan"))


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def bulk_assign_unit_plans(actor: Any, payload: Any) -> dict[str, Any]:
    """BR-MET-041: multi-select units + plan + effective date; per-unit history
    rows + one audited batch."""
    data = _payload_dict(payload)
    unit_ids = data.get("unit_ids")
    if not isinstance(unit_ids, (list, tuple)) or not unit_ids:
        _refuse_fields(
            [_field_error("unit_ids", errors.VAL_REQUIRED, "metering.plan.units_required")]
        )
    assigned: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    with transaction.atomic():
        for unit_id in unit_ids:
            try:
                # PER-UNIT SAVEPOINT, and it is load-bearing. `_apply_unit_plan`
                # moves `units.rate_plan_id` BEFORE it writes the history row,
                # so a refusal raised after that point — the PO's 2026-08-11
                # backdating refusal, or a missing history writer — used to be
                # caught here with the unit's plan column ALREADY MOVED and no
                # history row behind it. That is precisely the hole the gap-1
                # lane closed for the single-unit path (which rolls back
                # because its exception propagates out of its atomic block):
                # the plan column and the coverage history move together or
                # neither does. A per-unit savepoint gives bulk the same
                # property while keeping BR-MET-041's per-row error report.
                with transaction.atomic():
                    unit = _unit_row(unit_id, locked=True)
                    assigned.append(_apply_unit_plan(actor, unit, dict(data), source="bulk_update"))
            except (errors.ApiError, errors.NotFoundError) as exc:
                failed.append({"unit_id": str(unit_id), "reason": type(exc).__name__})
        _audit(
            actor,
            "unit.plan_bulk_assigned",
            "unit",
            None,
            after={"assigned": len(assigned), "failed": len(failed)},
        )
    return {"assigned": len(assigned), "failed": len(failed), "units": assigned, "errors": failed}


# ── bulk create (US-MET-004 · BR-MET-004/005/031/038/039) ───────────────────
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def stage_import(actor: Any, payload: Any) -> dict[str, Any]:
    """S16 bulk step: parse + validate EVERY row before anything is written
    (BR-MET-004). Nothing is persisted — US-MET-004 §5 states the preview
    counts are "computed over staged rows (no persistence in v1)", so the
    staged set travels in the response (E2 vs 11b §2.5's id-bearing 3-step
    contract — reported, not resolved here)."""
    from apps.metering import importers

    data = _payload_dict(payload)
    return importers.stage(data)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def commit_import(actor: Any, payload: Any) -> dict[str, Any]:
    """BR-MET-038: skip-errors ON by default (per-row errors, never a partial
    surprise) and the result summary "N created · N failed" is ALWAYS returned
    with reasons. One batch audit row (BR-MET-048)."""
    from apps.metering import importers

    data = _payload_dict(payload)
    staged = importers.stage(data)
    return importers.commit(actor, data, staged)


# ── routes & cycles (US-MET-006 · BR-MET-008/009/010/033) ───────────────────
def _route_row(route_id: Any, *, locked: bool = False) -> models.Route:
    if not _is_uuid(route_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    qs = models.Route.objects.filter(tenant_id=_tenant_id(), pk=route_id)
    if locked:
        qs = qs.select_for_update()
    row = qs.first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _cycle_row(cycle_id: Any, *, locked: bool = False) -> models.Cycle:
    if not _is_uuid(cycle_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    qs = models.Cycle.objects.filter(tenant_id=_tenant_id(), pk=cycle_id)
    if locked:
        qs = qs.select_for_update()
    row = qs.first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


#: BR-MET-076 — the three lifecycle values a route or a cycle may hold.
#: DRAFT means "has never run" and stamps nothing; INACTIVE means "used to run"
#: and keeps every stamp it made. Collapsing them would either resurrect retired
#: routes or erase history.
LIFECYCLE_STATUSES = ("draft", "active", "inactive")

#: BR-MET-077, **amended by CR-029 (PO 2026-08-23)** — r10 SET-07.1's three
#: became the EIGHT one-word business names the PO asked for: *"give business
#: names to frequence - 1 word."* The vocabulary itself lives in
#: `apps/metering/schedule.py` (B17 §2's table, in its order) so the migration,
#: the service layer and the tests read ONE list. The CR-006 values
#: (`monthly` · `bi_monthly` · `quarterly`) are still ACCEPTED on write and
#: mapped by `schedule.business_frequency` — migration 0019 moved the rows, and
#: refusing a client that has not moved would break a screen for a vocabulary
#: change it cannot see.
CYCLE_FREQUENCIES = schedule.FREQUENCIES

#: BR-MET-078 — the field names this CR must NEVER accept, refused BY NAME.
#:
#: PO verbatim, 2026-08-16: *"you dont need late fees in this. so dont have
#: anything related to money when you create route and cycles."* r10 SET-07.3
#: draws a `Late / penalty date` select, so a later lane reading the design
#: WILL try to post one — and an unknown-field error saying "unknown field" is
#: the wrong answer, because it reads as an oversight to be fixed. These names
#: get their own refusal that says the field was REMOVED BY A RULING and where
#: grace actually lives (BR-BIL-002/008, Billing defaults). That is the
#: difference between a gap and a decision.
MONEY_FIELDS_REMOVED = (
    "late_day",
    "late_date",
    "late_fee_date",
    "late_fee_day",
    "penalty_date",
    "penalty_day",
    "grace_days",
    "late_grace_days",
    "late_fee",
    "late_fee_pct",
    "late_fee_amount",
    "penalty_amount",
)


def _refuse_money_fields(payload: dict[str, Any], fe: list[dict[str, Any]]) -> None:
    """BR-MET-078: a fee field on these screens is refused by name."""
    for field in payload:
        if field in MONEY_FIELDS_REMOVED:
            fe.append(
                _field_error(
                    field,
                    errors.VAL_FORMAT,
                    "metering.cycle.money_field_removed",
                    lives_on="billing_defaults",
                )
            )


def _validate_route(payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}
    known = {
        "code",
        "name",
        "route_type",
        "feeder_ref",
        "cycle_id",
        "assigned_to",
        # CR-006 / BR-MET-073
        "notes",
        "status",
    }
    _refuse_money_fields(payload, fe)
    _refuse_fields(fe)
    for field in payload:
        if field not in known and field not in (
            "members",
            "walk_order",
            "premises_ids",
            "unit_ids",
            # CR-006: resolved against tenancy below, not set directly.
            "service_code",
            "service_id",
            # CR-029 D10 — the service SET (*"yes it will be multi service"*),
            # resolved by `_resolve_service_set` and stored in `route_services`.
            "service_codes",
            "service_ids",
            "area_code",
            "area_id",
            "excluded_asset_ids",
            # CR-029 (B17 §6) — {asset_id: "two words"}, written onto the
            # exclusion row so SET-06D.assets can explain itself in place.
            "exclusion_reasons",
            # CR-161-BRC10 W4 — the utility's own fields, validated by
            # tenancy's one validator in `_route_custom_answers`, not here.
            "custom_data",
        ):
            if field in ("sequence_from", "sequence_to", "sequence_range", "capacity"):
                # BR-MET-033 (OQ-041 CLOSED): no numeric sequence/capacity range
                # exists anywhere in a route's config or validation.
                fe.append(
                    _field_error(field, errors.VAL_FORMAT, "metering.route.sequence_range_removed")
                )
            else:
                fe.append(_field_error(field, errors.VAL_FORMAT, "metering.unknown_field"))
    _refuse_fields(fe)

    if "code" in payload or not partial:
        code = _text(payload.get("code"), 60)
        if not code:
            fe.append(_field_error("code", errors.VAL_REQUIRED, "metering.route.code_required"))
        out["code"] = code
    if "name" in payload:
        out["name"] = _text(payload["name"], 200)
    if "route_type" in payload:
        route_type = _text(payload["route_type"], 20)
        if route_type is not None and route_type not in ROUTE_TYPES:
            fe.append(
                _field_error(
                    "route_type",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.route.type_unknown",
                    allowed=list(ROUTE_TYPES),
                )
            )
        else:
            out["route_type"] = route_type
    if "feeder_ref" in payload:
        out["feeder_ref"] = _text(payload["feeder_ref"], 60)
    if "notes" in payload:  # BR-MET-073 — r10 "Gate codes, dogs, parking…"
        out["notes"] = _text(payload["notes"], 2000)
    if "status" in payload:  # BR-MET-076
        status = _text(payload["status"], 20)
        if status is not None and status not in LIFECYCLE_STATUSES:
            fe.append(
                _field_error(
                    "status",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.route.status_unknown",
                    allowed=list(LIFECYCLE_STATUSES),
                )
            )
        elif status is not None:
            out["status"] = status
    _refuse_fields(fe)
    return out


def _resolve_service(data: dict[str, Any], field_prefix: str = "service") -> tuple[bool, Any]:
    """BR-MET-073 — resolve `service_code` or `service_id` against tenancy.

    Returns `(present, service_or_None)` so the caller can tell "not supplied"
    (leave the column alone) from "supplied as empty" (an ALL-SERVICES route,
    which is a legitimate answer and the one every shipped route holds).
    """
    code_field, id_field = f"{field_prefix}_code", f"{field_prefix}_id"
    if code_field not in data and id_field not in data:
        return False, None
    raw = data.get(code_field, data.get(id_field))
    if raw in (None, ""):
        return True, None
    from apps.tenancy import models as tenancy_models

    qs = tenancy_models.Service.objects.all()
    row = qs.filter(code__iexact=str(raw)).first()
    if row is None and _is_uuid(raw):
        row = qs.filter(pk=raw).first()
    if row is None:
        _refuse_fields(
            [_field_error(code_field, errors.VAL_UNKNOWN_LOOKUP, "metering.route.service_unknown")]
        )
    return True, row


def _resolve_service_set(data: dict[str, Any]) -> tuple[bool, list[Any]]:
    """CR-029 D10 — resolve `service_codes` / `service_ids` into the route's SET.

    PO, verbatim 2026-08-23: *"yes it will be multi service"*. The upgraded
    prototype draws RT-001 as **"Water + Electric"**, and until `route_services`
    there was no field that sentence could be true of.

    Returns `(present, services)` with the same presence/emptiness distinction
    `_resolve_service` above draws: `(False, [])` is *"the caller sent no set
    field, leave the stored set alone"* — what a PATCH renaming a route must do
    — and `(True, [])` is *"the caller sent an empty set"*, which is the legacy
    ALL-SERVICES route and a legitimate answer.

    ORDER IS PRESERVED and it matters: the FIRST member becomes the transitional
    head `routes.service_id`, which `route_memberships.service` denormalizes
    from and BR-MET-074's two partial uniques key on (migration 0020 argues the
    choice and reports the hole it leaves for RC-W4's D4).

    An unknown service raises the SAME refusal the single-service path raises —
    one unknown service is one fact, and a second message key would be a second
    sentence for it.
    """
    field = "service_codes" if "service_codes" in data else "service_ids"
    if field not in data:
        return False, []
    raw_values = data.get(field) or []
    if isinstance(raw_values, (str, bytes)) or not isinstance(raw_values, (list, tuple, set)):
        _refuse_fields([_field_error(field, errors.VAL_FORMAT, "metering.route.service_unknown")])
    from apps.tenancy import models as tenancy_models

    qs = tenancy_models.Service.objects.all()
    resolved: list[Any] = []
    seen: set[Any] = set()
    for raw in raw_values:
        if str(raw or "").strip() == "":
            continue
        row = qs.filter(code__iexact=str(raw)).first()
        if row is None and _is_uuid(raw):
            row = qs.filter(pk=raw).first()
        if row is None:
            _refuse_fields(
                [_field_error(field, errors.VAL_UNKNOWN_LOOKUP, "metering.route.service_unknown")]
            )
        if row.pk not in seen:  # a set, so a repeated code is not two members
            seen.add(row.pk)
            resolved.append(row)
    return True, resolved


def _set_route_services(route: models.Route, services: list[Any]) -> None:
    """CR-029 D10 — the route's service SET, replaced wholesale.

    WHOLESALE AND NOT ADDITIVE, for `_set_meter_exclusions`' reason: the wizard
    posts the set it wants and a route that dropped electric must actually stop
    reading electric. An additive write would make un-ticking a service silently
    impossible.
    """
    wanted = [row.pk for row in services]
    models.RouteService.objects.filter(tenant_id=route.tenant_id, route=route).exclude(
        service_id__in=wanted
    ).delete()
    for service_id in wanted:
        models.RouteService.objects.get_or_create(
            tenant_id=route.tenant_id, route=route, service_id=service_id
        )


def _sync_route_service_head(route: models.Route, services: list[Any]) -> None:
    """Keep `routes.service_id` — the TRANSITIONAL HEAD — equal to the set's
    first member (migration 0020's stated choice).

    The head is not decoration: `route_memberships.service` is denormalized from
    it and BR-MET-074's two partial uniques are the only thing stopping one unit
    joining two routes for one service. RC-W4 moves membership to D4's run-time
    resolution and RC-W5 removes this column; until then the two must agree, and
    one function is what makes that true.
    """
    head = services[0].pk if services else None
    if route.service_id != head:
        route.service_id = head
        route.save(update_fields=["service", "updated_at"])


def _resolve_area(
    data: dict[str, Any], *, message_key: str = "metering.route.area_unknown"
) -> tuple[bool, Any]:
    """BR-MET-071/073 — resolve `area_code` or `area_id` against tenancy.

    ⚠ Tenant-scoped explicitly: `areas` is a per-tenant table, unlike
    `services` above which is the platform catalog. Reading it without the
    tenant filter would be CLAUDE.md rule 1's exact failure.

    ONE resolver for the route's area and the premises' area (BR-MET-083), so
    the two can never disagree about what an area code means. Only the refusal
    text differs, because "that route's area is unknown" and "that premises'
    area is unknown" are read on different screens.

    The first element of the pair is PRESENCE, not truth: `(False, None)` means
    the caller sent no area field at all and the stored value must be left
    alone; `(True, None)` means it explicitly sent an empty one, which clears.
    """
    if "area_code" not in data and "area_id" not in data:
        return False, None
    raw = data.get("area_code", data.get("area_id"))
    if raw in (None, ""):
        return True, None
    from apps.tenancy import models as tenancy_models

    qs = tenancy_models.Area.objects.filter(tenant_id=_tenant_id())
    row = qs.filter(code__iexact=str(raw)).first()
    if row is None and _is_uuid(raw):
        row = qs.filter(pk=raw).first()
    if row is None:
        _refuse_fields([_field_error("area_code", errors.VAL_UNKNOWN_LOOKUP, message_key)])
    return True, row


ROUTE_SERIES = "route"  # core.numbering.ROUTE — CR-006 SET-06 step 1
CYCLE_SERIES = "cycle"  # core.numbering.CYCLE — CR-006 SET-07 step 1


def next_route_code() -> dict[str, Any]:
    """BR-MET-073 — the route code SET-06 step 1 pre-fills, EDITABLE.

    CR verbatim: *"route ID (from Numbering format, editable)"*. Served as its
    own read so the wizard can show the code before anything is written; the
    number is only CONSUMED when create_route allocates it, so opening the
    wizard and cancelling does not burn a number.

    ⚠ That means the previewed code and the allocated code can differ if two
    admins open the wizard at once. Stated rather than hidden: the alternative
    is reserving a number on a screen the user may abandon, which leaves holes
    in a sequence a utility reconciles against.
    """
    warnings: list[dict[str, Any]] = []
    return {"code": _allocate_number_preview(ROUTE_SERIES, warnings), "warnings": warnings}


def next_cycle_code() -> dict[str, Any]:
    """BR-MET-077 — the cycle code SET-07 step 1 pre-fills, editable. See
    `next_route_code` for why a preview is not a reservation."""
    warnings: list[dict[str, Any]] = []
    return {"code": _allocate_number_preview(CYCLE_SERIES, warnings), "warnings": warnings}


def _allocate_number_preview(series: str, warnings: list[dict[str, Any]]) -> str | None:
    """The series' `preview` — renders, allocates NOTHING, advances NOTHING.

    Reads the tenant's stored row through the tenancy seam and renders it with
    `core.numbering.preview`, which is the same call the S8 Numbering tab's own
    live preview makes (`_series_dict`). One renderer, so the code the wizard
    shows and the code SET-08 shows can never disagree.

    A MISSING SERIES ROW IS REPORTED, NEVER FAKED — CR-005 found `JE-` had no
    row on any tenant and every manual journal entry shipped unnumbered
    because nothing said so out loud.
    """
    from apps.tenancy import selectors as tenancy_selectors

    try:
        row = tenancy_selectors.number_series_row(series)
    except errors.NotFoundError:
        warnings.append({"code": "numbering_series_missing", "series": series})
        return None
    return row.get("preview")


#: CR-161-BRC10 W4 — the route wizard (SET-06.1, create AND edit) is the ONE
#: screen that types a route's own fields (`custom_fields.SLOTS`,
#: `ROUTE_FORM`). It always sends `custom_data` (`{}` when the utility has
#: none); the seeder, the sample data and every other caller never do — so the
#: key's presence says the answers were typed there, and a required field binds
#: only on that screen (BR-TEN-052 as amended).
ROUTE_CUSTOM_SCREEN = "ROUTE_FORM"


def _route_custom_answers(data: dict[str, Any], existing: Any) -> dict[str, Any] | None:
    """The cleaned answers, or None when this door sent none — checked by
    tenancy's ONE validator through `seams.validate_custom_data` BEFORE the
    transaction opens, so a refusal writes nothing and burns no route number."""
    if "custom_data" not in data:
        return None
    return seams.validate_custom_data(
        "routes", data.get("custom_data") or {}, screen=ROUTE_CUSTOM_SCREEN, existing=existing
    )


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035b")
def create_route(actor: Any, payload: Any) -> dict[str, Any]:
    """US-MET-006 TC-1 + CR-006 SET-06: name, type, service, area, notes,
    MEMBERSHIP by premises (BR-MET-074), meter exclusions (BR-MET-075), draft
    or active (BR-MET-076), one cycle (BR-MET-010).

    The code comes from the `route` numbering series when the caller sends
    none (BR-MET-073) — the wizard pre-fills it and the admin may overtype it,
    so an absent code is "use the series" and never an error.

    ⚠ **THE ALLOCATION IS INSIDE `atomic()` AND MUST STAY THERE (DEF-234).**
    It sat immediately above this block until 2026-08-17, and every route
    created without a typed code answered HTTP 500: `allocate_series_number`
    takes a `select_for_update` row lock, and Django refuses that outside a
    transaction. No unit test could see it — `django_db` wraps each test in a
    transaction, so the guard never fires there — and `ATOMIC_REQUESTS` is set
    nowhere in `config/`, so it failed in every environment. Inside the block
    it is also the only placement that makes the number and the row atomic: a
    successful allocation followed by a refused create used to burn a number.
    """
    data = _payload_dict(payload)
    warnings: list[dict[str, Any]] = []
    from apps.metering import selectors

    custom = _route_custom_answers(data, None)
    with transaction.atomic():
        if not str(data.get("code") or "").strip():
            # ⛔ **DEF-2870 — `_allocate_number` HANDS OUT A CODE THAT ALREADY
            # EXISTS, AND THE NEXT STATEMENT REFUSES IT.** `seed_demo` writes
            # `CY-001`..`CY-006` and `RT-001`..`RT-006` with EXPLICIT codes, and
            # a caller-supplied code consumes nothing from the series — so on a
            # freshly seeded database both counters stand at 1 with six rows on
            # file. Measured on a fresh PostgreSQL 16 database, 2026-09-01:
            # `cycle` next_number = 1, `route` next_number = 1, `CY-001`..
            # `CY-006` and `RT-001`..`RT-006` all present, and
            # `manage.py load_sample_data --tenant brazosbend` died on
            # `core.errors.ValidationError: VAL-002
            # (metering.cycle.code_duplicate)` — taking TEN blocks down with it
            # and leaving the tenant with 0 accounts and 0 customers.
            #
            # This is DEF-577's invariant, one table over: *a series must never
            # hand out a number that already exists.* That defect's fix,
            # `_allocate_unused_number`, was applied to `premises` and `unit`
            # and to nothing else, so cycles and routes kept the bug. They ask
            # case-INSENSITIVELY because the duplicate guard three lines below
            # refuses on `code__iexact`.
            allocated = _allocate_unused_number(
                actor,
                ROUTE_SERIES,
                warnings,
                model=models.Route,
                field="code",
                case_insensitive=True,
            )
            if allocated:
                data = {**data, "code": allocated}
        cleaned = _validate_route(data, partial=False)
        if models.Route.objects.filter(
            tenant_id=_tenant_id(), code__iexact=cleaned["code"]
        ).exists():
            _refuse_fields(
                [_field_error("code", errors.VAL_FORMAT, "metering.route.code_duplicate")]
            )
        cycle = _resolve_cycle(data.get("cycle_id"))
        service_present, service = _resolve_service(data)
        # CR-029 D10 — the SET wins over the single field when both arrive, and
        # its first member becomes the transitional head (migration 0020).
        set_present, service_set = _resolve_service_set(data)
        if set_present:
            service_present, service = True, (service_set[0] if service_set else None)
        elif service_present and service is not None:
            service_set = [service]
        area_present, area = _resolve_area(data)
        row = models.Route.objects.create(
            tenant_id=_tenant_id(),
            cycle=cycle,
            service=service if service_present else None,
            area=area if area_present else None,
            custom_data=custom or {},
            **cleaned,
        )
        _set_route_services(row, service_set)
        members, moved_from = _set_route_membership(row, data)
        _audit(
            actor,
            "route.created",
            "route",
            row.id,
            # CR-006: *"All CRUD audit-logged (who, when, before/after member
            # counts)"* — and BR-MET-074's moves, because a member that
            # arrived by being taken off another route is the change a
            # utility most needs to be able to explain later.
            after={
                **selectors.route_dict(row),
                "members": members,
                "moved_from": moved_from,
                "warnings": warnings,
            },
        )
    return {**selectors.route_dict(_route_row(row.pk)), "warnings": warnings}


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _resolve_cycle(cycle_id: Any) -> models.Cycle | None:
    if cycle_id in (None, ""):
        return None
    row = None
    if _is_uuid(cycle_id):
        row = models.Cycle.objects.filter(tenant_id=_tenant_id(), pk=cycle_id).first()
    if row is None:
        row = models.Cycle.objects.filter(
            tenant_id=_tenant_id(), code__iexact=str(cycle_id)
        ).first()
    if row is None:
        _refuse_fields(
            [_field_error("cycle_id", errors.VAL_UNKNOWN_LOOKUP, "metering.cycle.unknown")]
        )
    return row


def _route_service_ids(route: models.Route) -> set[Any]:
    """CR-029 D10 — the services a route READS, as ids.

    The SET (`route_services`) is the truth; `routes.service_id` is the
    transitional head and is the whole set only for a route created before D10
    or one whose set was never written. An EMPTY set is the legacy ALL-SERVICES
    route and is a legitimate answer, not a missing one.
    """
    ids = set(
        models.RouteService.objects.filter(tenant_id=route.tenant_id, route=route).values_list(
            "service_id", flat=True
        )
    )
    if ids:
        return ids
    return {route.service_id} if route.service_id else set()


def _service_sets_collide(mine: set[Any], theirs: set[Any]) -> bool:
    """W4-T6 — do two routes read any service in common?

    ⚠ **AN EMPTY SET COLLIDES WITH EVERYTHING.** A route with no service is the
    legacy ALL-SERVICES route (`_resolve_service`: *"a legitimate answer and the
    one every shipped route holds"*), so it reads whatever the unit takes and
    therefore competes with every other route for that unit. That is the same
    precedence `ensure_service_point` and `_stampable_points` already read with,
    stated once more where the MOVE is decided.
    """
    if not mine or not theirs:
        return True
    return bool(mine & theirs)


def _first_unit_id_of(tenant_id: Any, premises_id: Any) -> str | None:
    """A stable representative unit for an audit row that used to name one.

    ⚠ It is a REPRESENTATIVE and not *"the unit that moved"* — the whole
    building moved. Ordered by id so two runs name the same one, and `None`
    for a building with no units, which is a real state (`W4-T4`'s meterless
    routed premises) and not an error.
    """
    value = (
        models.Unit.objects.filter(
            tenant_id=tenant_id, premises_id=premises_id, deleted_at__isnull=True
        )
        .order_by("id")
        .values_list("id", flat=True)
        .first()
    )
    return str(value) if value else None


def _colliding_premises(
    route: models.Route, premises_ids: Any
) -> list[models.RoutePremisesMembership]:
    """`CR-131-BRC07` step 4 — `BR-MET-074`'s conflict-is-a-MOVE, at the grain
    the route now stores.

    ⚠ **THIS IS THE RULE THE CR NAMES AS THE ONE MOST LIKELY TO BREAK QUIETLY,
    AND THE REASON IS WORTH STATING.** `BR-MET-074` says a premises already on
    another route FOR THE SAME SERVICE **moves**, it is not refused — because
    the CR's own requirement is *"Premises already on another route for the
    same service show a badge… selecting moves them, with confirm"*, and a
    server that refuses first makes the confirm unreachable. Break it and
    nothing goes red: the clerk simply gets an error where they expected a
    badge, or — far worse — the premises silently sits on TWO routes and is
    read twice, which no test in this repository asks about unless it is
    written to.

    It is a straight transposition of `_colliding_memberships` one grain up,
    deliberately keeping its two queries and its service-SET comparison:

      * the other routes' rows for these buildings — ONE query;
      * those routes' service sets — ONE query.

    **Per service SET and not per head (`CR-029` RC-W4-T6).** A premises on a
    "Water + Electric" route is taken off it by an electric-only route exactly
    as by a water-only one; reading `service_id = route.service_id` enforced the
    rule for the head service alone, so the same building could be read, and
    billed, twice.
    """
    mine = _route_service_ids(route)
    rows = list(
        models.RoutePremisesMembership.objects.filter(
            tenant_id=route.tenant_id, premises_id__in=premises_ids
        )
        .exclude(route=route)
        .select_related("route", "premises")
    )
    if not rows:
        return []
    other_ids = {row.route_id for row in rows}
    sets: dict[Any, set[Any]] = {route_id: set() for route_id in other_ids}
    for route_id, service_id in models.RouteService.objects.filter(
        tenant_id=route.tenant_id, route_id__in=list(other_ids)
    ).values_list("route_id", "service_id"):
        sets[route_id].add(service_id)
    collisions: list[models.RoutePremisesMembership] = []
    for row in rows:
        theirs = sets.get(row.route_id) or (
            {row.route.service_id} if row.route.service_id else set()
        )
        if _service_sets_collide(mine, theirs):
            collisions.append(row)
    return collisions


def _colliding_memberships(route: models.Route, unit_ids: Any) -> list[models.RouteMembership]:
    """Every membership on ANOTHER route that reads one of `route`'s services.

    ── CR-029 RC-W4-T6 · THE MULTI-SERVICE MEMBERSHIP HOLE ──────────────────
    B17 §7 W4-T6, verbatim: *"D10 gave a route a service SET, but
    `routes.service_id` was kept as a transitional head because
    `route_memberships.service` denormalizes from it and BR-MET-074's two
    partial unique indexes key on it. The consequence, stated plainly: a "Water
    + Electric" route enforces per-service membership uniqueness for WATER ONLY
    — so the same unit can also join an electric route, and be read twice."*

    This function is the close. The conflict is asked of the SERVICE SET on both
    sides instead of `service_id = route.service_id`, so a unit on RT-001
    ("Water + Electric") is taken off it by an electric-only route exactly as it
    is by a water-only one. **Two queries whatever the size of the selection** —
    the memberships, then the sets of the routes they name — because this runs
    inside the wizard's save.

    ⚠ **The DATABASE's guarantee is still head-keyed and that is REPORTED, not
    hidden** (hard-won law 1): `uq_route_memberships_unit_service` keys on the
    denormalized `route_memberships.service_id`, which is still the head. The
    per-service uniqueness a utility can rely on is this function plus D4's
    resolution, which answers at most one route per (unit, service) whatever the
    stored rows say. Closing it in the schema needs one membership row per
    service in the set, which collides with `uq_route_memberships_walk_order`
    (two rows for one unit would carry one stop number) — a migration with its
    own blast radius, and no ruling asks for it.
    """
    mine = _route_service_ids(route)
    rows = list(
        models.RouteMembership.objects.filter(tenant_id=route.tenant_id, unit_id__in=unit_ids)
        .exclude(route=route)
        .select_related("route", "unit")
    )
    if not rows:
        return []
    other_ids = {row.route_id for row in rows}
    sets: dict[Any, set[Any]] = {route_id: set() for route_id in other_ids}
    for route_id, service_id in models.RouteService.objects.filter(
        tenant_id=route.tenant_id, route_id__in=list(other_ids)
    ).values_list("route_id", "service_id"):
        sets[route_id].add(service_id)
    collisions: list[models.RouteMembership] = []
    for row in rows:
        theirs = sets.get(row.route_id) or (
            {row.route.service_id} if row.route.service_id else set()
        )
        if _service_sets_collide(mine, theirs):
            collisions.append(row)
    return collisions


def _set_route_membership(
    route: models.Route, data: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """BR-MET-033/074: selecting a PREMISES includes its units; walk order is
    OPTIONAL and, when set, unique within the route. A unit is on ≤1 route
    PER SERVICE. Membership drives service_points.route_id.

    Returns `(members, moved_from)`. The second half is the audit's evidence
    for BR-MET-074's move: which units came off which route. It is returned
    rather than logged here because the audit row belongs to the CALLER's
    before/after pair, and two audit writers for one write is how a trail
    stops being a trail.
    """
    if "members" not in data and "premises_ids" not in data and "unit_ids" not in data:
        _set_meter_exclusions(route, data)
        return selector_membership(route), []
    tenant_id = route.tenant_id

    # ── `CR-131-BRC07` step 3 · WHAT IS COLLECTED IS PREMISES ────────────────
    #
    # PO ruling 2026-09-22, verbatim: *"route should not be status - it is
    # dynamicallyderive the details of units, assets meter acocount swithin
    # it"*. So the SET this function builds is a set of BUILDINGS. Six premises
    # carrying 726 units used to become 726 `update_or_create` statements in
    # one transaction holding the route row locked, which is the *"Working…"*
    # for ever the PO reported; it is now six rows.
    #
    # ⚠ **A `unit_id` STILL ARRIVES AND IS PROMOTED TO ITS BUILDING RATHER THAN
    # REFUSED.** Three payload shapes reach here — `premises_ids`, `unit_ids`
    # and the older `members` list — and the last two name units. Refusing them
    # would break callers over a distinction the DERIVATION has not made since
    # `CR-029` RC-W4: `BR-MET-082` clause 2, *"grouping a premises groups every
    # unit in it"*, already resolved every sibling of a picked unit onto the
    # same route. So a unit pick was ALREADY a building pick in every answer
    # the product gave; only the stored rows pretended otherwise, and this is
    # where they stop.
    #
    # ⚠ **THE WALK ORDER IS NOT READ FROM `members` ANY MORE, AND THAT IS THE
    # 2026-09-22 RULING (*"a is okay"*), NOT AN OMISSION.** The order is per
    # PREMISES in `route_premises_orders`, written by `walk_order`'s own audited
    # door. `route_memberships.walk_order` is superseded, has never had a
    # writer and holds 0 rows; `_ordered_members` already overrides it with the
    # stop number on every read. A value accepted here would be written to a
    # column nothing reads — which is worse than refusing it, because the clerk
    # would see it accepted.
    wanted_premises: dict[str, None] = {}
    for premises_id in data.get("premises_ids") or []:
        wanted_premises.setdefault(str(_premises_row(premises_id).id), None)
    for unit_id in data.get("unit_ids") or []:
        wanted_premises.setdefault(str(_unit_row(unit_id).premises_id), None)
    for entry in data.get("members") or []:
        member = dict(entry or {})
        if member.get("premises_id"):
            wanted_premises.setdefault(str(_premises_row(member["premises_id"]).id), None)
            continue
        wanted_premises.setdefault(str(_unit_row(member.get("unit_id")).premises_id), None)

    # The units of those buildings, in ONE query rather than one per premises.
    # They are still needed here for exactly two jobs — the service-point stamp
    # and the legacy `route_memberships` rows step 8 retires — and for nothing
    # a reader consumes. Every READ derives them (`derivation.members_of_route`).
    wanted: dict[str, int | None] = {
        str(unit_id): None
        for unit_id in models.Unit.objects.filter(
            tenant_id=tenant_id, premises_id__in=list(wanted_premises), deleted_at__isnull=True
        ).values_list("id", flat=True)
    }

    # ── BR-MET-074: A CONFLICT IS A **MOVE**, NOT A REFUSAL ─────────────────
    # This block used to raise `metering.route.unit_on_another_route`. That
    # made the CR's own requirement unbuildable — *"Premises already on
    # another route for the same service show a badge… selecting moves them,
    # with confirm"* — because the server refused before any confirm could be
    # offered, so the badge could only ever be followed by an error.
    #
    # The confirmation is the UI's job and the move is the server's, exactly
    # as BR-MET-010 already splits them for cycles. The moved-from rows are
    # returned so the caller can AUDIT what moved and the screen can say
    # *"SCW-R2 drops to 376 members"* (r10 SET-06.4).
    #
    # Scoped PER SERVICE: a unit on the water route and the electric route is
    # correct, and only a second route reading the SAME service is a conflict.
    #
    # ⚠ **PER SERVICE SET, NOT PER HEAD (CR-029 RC-W4-T6).** This read
    # `service_id=route.service_id` until D4, which enforced the rule for the
    # head service only — so a unit on a "Water + Electric" route could also
    # join an electric-only route and be read, and billed, twice. See
    # `_colliding_memberships`.
    # ⚠ **ASKED OF THE BUILDINGS NOW, NOT OF THEIR UNITS (`CR-131-BRC07`).**
    # The answer is the same set of routes either way — a building's units are
    # all on the route the building is on — and asking at this grain is what
    # makes it 1 query over 6 ids instead of 1 over 726.
    conflicts = _colliding_premises(route, list(wanted_premises))
    moved_from: list[dict[str, Any]] = []
    for conflict in conflicts:
        moved_from.append(
            {
                # ⚠ **`premises_id` IS ADDED AND `unit_id` IS KEPT.** The audit
                # row is the evidence for `BR-MET-074`'s move and a reader of
                # last month's trail must still find the key it was written
                # with, so the new fact travels BESIDE the old one rather than
                # replacing it. `unit_id` is now the FIRST unit of the building
                # in id order — a stable representative, named as one here so
                # nobody later reads it as "the only unit that moved".
                "premises_id": str(conflict.premises_id),
                "premise_no": conflict.premises.premise_no,
                "unit_id": _first_unit_id_of(route.tenant_id, conflict.premises_id),
                "from_route": conflict.route.code,
                "from_route_id": str(conflict.route_id),
            }
        )

    # ── DEF-219 · a DRAFT may not take a premises off an ACTIVE route ────────
    #
    # PO ruling 2026-08-17, option (i) of three: *"A draft may not take a
    # premises off an active route — refuse, name the route"*.
    #
    # ⚠ THIS SETTLES WHAT A DRAFT MEANS, and the bug was that the product
    # answered it differently at two layers. *"A draft affects nothing"* was
    # PROVED about service points — `_stamp_service_points` returns early for a
    # draft, so Reads and Billing genuinely cannot see it — and ASSERTED about
    # everything else. But the loop below writes `route_memberships` whatever
    # the status, and the **Members and Meters columns a utility reads on SET-05
    # count MEMBERSHIPS**. So a draft emptied a live route on the only screen
    # anybody looks at: `Route 2 · Mason Rd` went from 1 premises / 2 units /
    # 3 meters to 0 / 0 / 0 while still Active and still inside its cycle.
    #
    # The rule is now true at BOTH layers. An ACTIVE route may still take a
    # premises from another active route — that is BR-MET-074's move and it is
    # deliberate, confirmed on screen and audited. Only a DRAFT is refused,
    # because a draft is a thing that has not happened yet and must not have
    # consequences a person can see.
    #
    # The refusal NAMES THE ROUTE. "That premises is taken" leaves an admin with
    # nowhere to go; naming it tells them where to look and what to change.
    if route.status == "draft" and moved_from:
        blocking = [conflict for conflict in conflicts if conflict.route.status == "active"]
        if blocking:
            names = sorted({f"{c.route.code} · {c.route.name}" for c in blocking})
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-MET-074",
                message_key="metering.route.draft_cannot_take_from_active",
                params={
                    "routes": ", ".join(names),
                    "count": len(blocking),
                    "detail": (
                        f"{len(blocking)} of the selected premises "
                        f"{'is' if len(blocking) == 1 else 'are'} already on "
                        f"{', '.join(names)}, which "
                        f"{'is' if len(names) == 1 else 'are'} active. A draft "
                        "route cannot take them. Activate this route to move "
                        "them, or remove them from the selection."
                    ),
                },
            )

    if conflicts:
        # The MOVE: the building comes off the other route. Its per-unit rows
        # go with it, because until step 8 retires them they are the legacy
        # projection of these and a stale one would keep the old route claiming
        # the building through `derivation`'s own membership read.
        losing = [conflict.premises_id for conflict in conflicts]
        models.RoutePremisesMembership.objects.filter(
            tenant_id=tenant_id, pk__in=[conflict.pk for conflict in conflicts]
        ).delete()
        models.RouteMembership.objects.filter(
            tenant_id=tenant_id,
            route_id__in=[conflict.route_id for conflict in conflicts],
            unit__premises_id__in=losing,
        ).delete()

    # ── THE WRITE — SIX ROWS, NOT 726 ───────────────────────────────────────
    # ⚠ **`bulk_create` WITH ONE STATEMENT, NOT `update_or_create` PER ROW.**
    # The per-row loop is what held the route locked for 726 round trips; at
    # premises grain it would be 6, which is survivable — and it is still
    # written as one statement, because `NFR-5` forbids a code path that has a
    # size it stops working at, and 6 is only today's number. A building whose
    # row already exists is left exactly as it is (`ignore_conflicts`), so the
    # two uniqueness constraints stay the authority rather than this loop.
    models.RoutePremisesMembership.objects.filter(tenant_id=tenant_id, route=route).exclude(
        premises_id__in=list(wanted_premises)
    ).delete()
    models.RoutePremisesMembership.objects.bulk_create(
        [
            models.RoutePremisesMembership(
                tenant_id=tenant_id,
                route=route,
                premises_id=premises_id,
                # BR-MET-074: the denormalized stamp, written HERE and nowhere
                # else — a copy is only safe while exactly one place writes it.
                service_id=route.service_id,
            )
            for premises_id in wanted_premises
        ],
        ignore_conflicts=True,
    )

    # ⚠ **THE LEGACY PER-UNIT ROWS ARE STILL WRITTEN, ON PURPOSE.** A table is
    # retired after its readers move, never in the change that supersedes it —
    # `CR-131-BRC07` step 8 owns that. Until then this keeps the two accounts
    # in step so a half-deployed branch cannot answer two different things.
    models.RouteMembership.objects.filter(tenant_id=tenant_id, route=route).exclude(
        unit_id__in=wanted
    ).delete()
    existing = set(
        str(value)
        for value in models.RouteMembership.objects.filter(
            tenant_id=tenant_id, route=route
        ).values_list("unit_id", flat=True)
    )
    models.RouteMembership.objects.bulk_create(
        [
            models.RouteMembership(
                tenant_id=tenant_id, route=route, unit_id=unit_id, service_id=route.service_id
            )
            for unit_id in wanted
            if unit_id not in existing
        ],
        ignore_conflicts=True,
    )
    _stamp_service_points(route, list(wanted))
    _set_meter_exclusions(route, data)
    return selector_membership(route), moved_from


def _stamp_service_points(route: models.Route, unit_ids: list[str]) -> None:
    """BR-MET-033 + BR-MET-076: membership drives `service_points.route_id` —
    **unless the route is a DRAFT, which stamps nothing.**

    CR verbatim: *"drafts don't affect Reads/Billing"*. A service point is
    exactly how Reads and Billing find a route, so a draft that stamped one
    would be a draft that affects both — the rule would be a comment (hard-won
    law 1). Activating the route later re-runs this with the same membership.
    """
    tenant_id = route.tenant_id
    models.ServicePoint.objects.filter(tenant_id=tenant_id, route=route).exclude(
        unit_id__in=unit_ids
    ).update(route=None, cycle=None)
    if route.status == "draft":
        # Also unstamp anything a previous ACTIVE state left behind, so
        # demoting a route to draft actually removes it from Reads.
        models.ServicePoint.objects.filter(tenant_id=tenant_id, route=route).update(
            route=None, cycle=None
        )
        return
    qs = _stampable_points(route, unit_ids)
    cycle = route.cycle if route.cycle and route.cycle.status != "draft" else None
    qs.update(route=route, cycle=cycle)


def _stampable_points(route: models.Route, unit_ids: list[str]) -> Any:
    """The service points `route` may stamp — DEF-227's WRITE half.

    ⚠ **A ROUTE WITH NO SERVICE MUST NOT TAKE A POINT THAT HAS ONE.** DEF-227
    was filed against the READER (`ensure_service_point` asked for `.first()`
    membership and got whichever row came back) and fixed there on 2026-08-17.
    The two stampers carried the identical bug in the other direction and were
    not touched: the service filter below is inside an `if`, so a route with
    `service_id` NULL — the legacy ALL-SERVICES route, which `_resolve_service`
    calls *"a legitimate answer and the one every shipped route holds"* —
    updated EVERY service point the unit had, water route stamp and all.

    **The cost is not only the wrong crew.** `route` and `cycle` are written in
    one statement, so an all-services route with no cycle set
    `service_points.cycle_id = NULL`, and that column is what
    `selectors.units_in_cycle` — billing's scope seam — reads. The unit dropped
    out of the bill run and nothing said so.

    So: a service-specific route stamps its own service (unchanged), and an
    all-services route stamps only points that are unrouted or already on
    another all-services route. Most specific wins, the same precedence
    `ensure_service_point` reads with.

    Written as a positive `filter(... | ...)` rather than an `exclude()`
    deliberately: `exclude(route__service_id__isnull=False)` compiles to a NOT
    IN over a nullable join and drops the unrouted rows this exists to catch.

    ⚠ **THE SET, NOT THE HEAD (CR-029 D10 + RC-W4-T6).** This filtered on
    `route.service_id` alone, so a "Water + Electric" route stamped its water
    points and left its electric ones unrouted — a route that says it reads
    electric and a stamp that says nobody does.
    """
    qs = models.ServicePoint.objects.filter(tenant_id=route.tenant_id, unit_id__in=unit_ids)
    service_ids = _route_service_ids(route)
    if service_ids:
        # A water route stamps water service points and leaves electric alone.
        return qs.filter(service_id__in=list(service_ids))
    return qs.filter(Q(route__isnull=True) | Q(route__service_id__isnull=True))


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-083 — THE CASCADE. Two write paths that keep route membership true.
#
# BR-MET-082 (PO, 2026-08-17): *"any change any movement make the changes to
# downstream"*. `routes.area_id` shipped with CR-006 and never paid out: a route
# drawn for NORTH and a premises tagged NORTH were two facts that never met.
# These three functions are where they meet.
#
# ⚠ WHAT THIS IS NOT. BR-MET-082 Amendment 1 asks for membership to be DERIVED
# at run time; this is not that. Membership is still a STORED answer and
# `units_in_cycle` still resolves off the `service_points.cycle_id` stamp — what
# changes is that two more write paths keep the stamp correct. DEF-225 stays
# open for the derivation, and BR-MET-083's closing section lists exactly what
# still holds a stale answer.
# ═══════════════════════════════════════════════════════════════════════════


def _routes_for_area(area: Any) -> list[models.Route]:
    """BR-MET-083(a) boundary 3 — the ACTIVE routes a premises in `area` joins.

    A PARENT'S ROUTE COVERS ITS SUB-AREAS: a premises tagged `SOUTH-SE` joins a
    route drawn for `SOUTH`. That is the same direction `selectors._area_ids_for`
    reads for the SET-06 filter (a parent matches its sub-areas), applied to one
    row instead of a chip list — one statement of the rule, read two ways.
    """
    if area is None:
        return []
    area_ids = [area.id] if area.parent_id is None else [area.id, area.parent_id]
    return list(
        models.Route.objects.filter(tenant_id=_tenant_id(), area_id__in=area_ids, status="active")
        .select_related("cycle", "service")
        .order_by("code", "id")
    )


def _stamp_added_service_points(route: models.Route, unit_ids: list[str]) -> None:
    """The ADD-ONLY half of `_stamp_service_points` (BR-MET-033/076).

    ⚠ `_stamp_service_points` takes the route's FULL membership and unstamps
    everything not in it — calling it with the handful of units a cascade just
    added would silently empty the route of everyone else. So a cascade needs
    its own stamper, and this is it: it touches the named units and nothing
    else.

    A DRAFT stamps nothing, for the same reason it does there: a service point
    is exactly how Reads and Billing find a route, and *"drafts don't affect
    Reads/Billing"*.
    """
    if route.status == "draft":
        return
    cycle = route.cycle if route.cycle and route.cycle.status != "draft" else None
    # DEF-227's write half — see `_stampable_points`. An all-services route
    # never takes a point that already belongs to a route drawn for its
    # service, and the cascade is the path that made this ordinary: tagging a
    # premises touches EVERY active route the area has, not just the one a
    # human opened.
    _stampable_points(route, unit_ids).update(route=route, cycle=cycle)


def _add_buildings_to_route_set(route: models.Route, premises_ids: list[str]) -> list[str]:
    """⊕ **`DEF-MET-9250` — a building a cascade puts on a route goes into the
    route's SET, which is the only thing the bill run reads.**

    Since `CR-131-BRC07` the derivation (`derivation._candidate_unit_ids`)
    scopes a route by its premises set and its AREA, and **ignores the per-unit
    `route_memberships` rows**. A route that holds any live pick is defined by
    its picks alone — *"the area fills an empty route, it does not overrule a
    picked one"* — so a building a cascade joined to a PICKED route by writing
    unit rows only was on the route for every screen that counts unit rows and
    on NO billing cycle: 21 of 71 routed Brazos Bend properties, every
    one-time bill on them refused *"No billing cycle"*.

    ADD-ONLY, and deliberately not through `_set_route_membership`: that writer
    REPLACES the set and deletes the unit rows and service-point stamps of
    every building outside it, which on a route already holding cascaded
    buildings would unstamp the very units this exists to keep. Two cases it
    leaves alone, each for the derivation's own reason:

      * **an AREA route with no pick yet** — the area already reaches a building
        it covers, and one pick would make the route pick-defined and drop
        every other building in the area out of the run;
      * **a building already on another route for this service** — `BR-MET-083`
        boundary 2, a cascade never moves one (`_colliding_premises`), and the
        two unique constraints refuse a second home regardless
        (`ignore_conflicts`).

    Returns the premises ids added.
    """
    from apps.metering import derivation

    wanted = {str(value) for value in premises_ids if value}
    if not wanted:
        return []
    current = {
        str(value)
        for value in models.RoutePremisesMembership.objects.filter(
            tenant_id=route.tenant_id, route=route
        ).values_list("premises_id", flat=True)
    }
    wanted -= current
    if not wanted:
        return []
    if not current and route.area_id is not None:
        parents = derivation._area_parents()
        areas = {
            str(premises_id): (str(area_id) if area_id else None)
            for premises_id, area_id in models.Premises.objects.filter(
                tenant_id=route.tenant_id, pk__in=list(wanted)
            ).values_list("id", "area_id")
        }
        wanted = {
            premises_id
            for premises_id in wanted
            if str(route.area_id) not in derivation._covering_areas(areas.get(premises_id), parents)
        }
    taken = {str(row.premises_id) for row in _colliding_premises(route, list(wanted))}
    wanted -= taken
    if not wanted:
        return []
    models.RoutePremisesMembership.objects.bulk_create(
        [
            models.RoutePremisesMembership(
                tenant_id=route.tenant_id,
                route=route,
                premises_id=premises_id,
                # BR-MET-074's denormalised stamp, the value `_set_route_membership`
                # writes: `route.service_id` and nothing else.
                service_id=route.service_id,
            )
            for premises_id in sorted(wanted)
        ],
        ignore_conflicts=True,
    )
    return sorted(wanted)


def _join_units_to_route(route: models.Route, unit_ids: list[str]) -> list[str]:
    """Add the units that are NOT already on a route for this route's service.

    **BR-MET-083 boundary 2 — A CASCADE NEVER TAKES A UNIT OFF ANOTHER ROUTE.**
    Moving a unit between routes is BR-MET-074's move, and the CR requires it be
    confirmed on screen (*"selecting moves them, with confirm"*). A move
    triggered by a form field on a different screen is a move nobody agreed to.
    So a cascade only ever fills a gap; a unit already routed for that service
    is left exactly where it is.

    Returns the unit ids actually joined — empty means the cascade was a no-op,
    which is the common case and must not be reported as a change.
    """
    if not unit_ids:
        return []
    tenant_id = route.tenant_id
    # ⚠ **"ALREADY ROUTED FOR THIS SERVICE" IS ASKED OF THE SERVICE SET**
    # (CR-029 RC-W4-T6). It used to be `service_id = route.service_id`, so a
    # cascade for a "Water + Electric" route happily added a unit that was
    # already on an electric route — a second membership for a service both
    # routes read, which is the hole W4-T6 closes.
    taken = {
        str(row.unit_id)
        for row in _colliding_memberships(route, list(unit_ids))
        if row.route_id != route.id
    } | {
        str(value)
        for value in models.RouteMembership.objects.filter(
            tenant_id=tenant_id, route=route, unit_id__in=unit_ids
        ).values_list("unit_id", flat=True)
    }
    wanted = [unit_id for unit_id in unit_ids if unit_id not in taken]
    if not wanted:
        return []
    for unit_id in wanted:
        models.RouteMembership.objects.create(
            tenant_id=tenant_id,
            route=route,
            unit_id=unit_id,
            walk_order=None,  # a cascaded member has no walk position until a human gives it one
            # BR-MET-074's denormalized stamp. `_set_route_membership` is no
            # longer the ONLY writer of it, so the invariant is restated here:
            # it is copied from `route.service_id` and from nowhere else.
            service_id=route.service_id,
        )
    _stamp_added_service_points(route, wanted)
    # ⊕ `DEF-MET-9250` — and their BUILDINGS into the set the bill run reads.
    _add_buildings_to_route_set(
        route,
        [
            str(value)
            for value in models.Unit.objects.filter(
                tenant_id=tenant_id, pk__in=wanted
            ).values_list("premises_id", flat=True)
        ],
    )
    return wanted


def cascade_area_to_routes(actor: Any, premises: models.Premises) -> list[dict[str, Any]]:
    """BR-MET-083(a) — a premises tagged into an area joins that area's routes.

    Called after a premises is created with an area and after its area changes.
    Audited PER ROUTE rather than folded into the premises audit row: the thing
    that changed is a route's membership, and CR-006 requires *"All CRUD
    audit-logged (who, when, before/after member counts)"* — a utility asking
    "why did SCW-R2 grow by 4 units" must find the answer on the route.
    """
    from apps.metering import selectors

    if premises.area_id is None:
        return []
    routes = _routes_for_area(premises.area)
    if not routes:
        return []
    unit_ids = [
        str(value)
        for value in models.Unit.objects.filter(
            tenant_id=premises.tenant_id, premises=premises, deleted_at__isnull=True
        ).values_list("id", flat=True)
    ]
    joined: list[dict[str, Any]] = []
    for route in routes:
        # STORED, not derived (D4): this row exists to say the cascade added
        # members, and the derived count is the same before and after it.
        before = len(selectors.stored_route_members(route.id))
        added = _join_units_to_route(route, unit_ids)
        if not added:
            continue
        after = len(selectors.stored_route_members(route.id))
        _audit(
            actor,
            "route.members_cascaded",
            "route",
            route.id,
            before={"members": before},
            after={
                "members": after,
                "br_ref": "BR-MET-083",
                "reason": "premises_area_tagged",
                "premises_id": str(premises.id),
                "area_code": premises.area.code,
                "units_added": len(added),
            },
        )
        joined.append({"route_id": str(route.id), "route_code": route.code, "units": len(added)})
    return joined


def _resolve_create_route(payload: dict[str, Any]) -> models.Route | None:
    """**CR-089 wave B `B6` — the route named on a create, or a refusal.**

    Accepts the route's **CODE** or its id, because the wizard's picker sends
    whichever it holds and a shared URL carries the code (the same reasoning
    `PremisesListPage`'s type filter records: *"the server accepts either code
    or name, and the code is what a shared URL must carry"*).

    ⚠ **AN UNKNOWN ROUTE IS REFUSED BY NAME AND NOT IGNORED — THAT IS THE WHOLE
    OF `DEF-MET-4715`.** Silently dropping it is what this key did for its
    entire life, and a create that answers `201` for a route it did not honour
    is the worst of the three possible behaviours: worse than refusing, and
    worse than joining the wrong route, because nothing anywhere says a thing
    happened that did not.

    ⚠ **A DRAFT ROUTE IS REFUSED TOO** (`BR-MET-076`, `DEF-219`): *"a draft is a
    thing that has not happened yet and must not have consequences a person can
    see"*, and a membership on a draft route reaches the bill run through
    `selectors.units_in_cycle`. The refusal names the field either way, so the
    wizard can put the clerk back on the control that caused it (`B8`).
    """
    raw = payload.get("route")
    if raw in (None, ""):
        return None
    term = str(raw).strip()
    if not term:
        return None
    qs = models.Route.objects.filter(tenant_id=_tenant_id())
    route = qs.filter(code__iexact=term).first()
    if route is None:
        # An id, only if it looks like one — `filter(pk=<a code>)` raises
        # ValidationError on PostgreSQL rather than answering "no match", which
        # would reach a clerk as a 500 for a typo.
        try:
            route = qs.filter(pk=term).first()
        except (DjangoValidationError, ValueError, TypeError):
            route = None
    if route is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.premises.route_unknown",
            field_errors=[
                {
                    "field": "route",
                    "code": errors.VAL_UNKNOWN_LOOKUP,
                    "message_key": "metering.premises.route_unknown",
                    "params": {"value": term},
                }
            ],
        )
    if route.status != "active":
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.premises.route_not_active",
            field_errors=[
                {
                    "field": "route",
                    "code": errors.VAL_UNKNOWN_LOOKUP,
                    "message_key": "metering.premises.route_not_active",
                    "params": {"value": route.code, "status": route.status},
                }
            ],
        )
    return route


def _join_premises_to_route(
    actor: Any, premises: models.Premises, route: models.Route
) -> list[dict[str, Any]]:
    """Put this building's units on the route a clerk chose, and audit it.

    The same shape `cascade_area_to_routes` uses one function down, and for the
    same reason: CR-006 requires *"All CRUD audit-logged (who, when, before/
    after member counts)"*, and a utility asking *"why did SCW-R2 grow by 4
    units"* must find the answer on the ROUTE rather than on the property.

    ⚠ **A BUILDING WITH NO UNITS YET JOINS NOTHING, AND THAT IS CORRECT RATHER
    THAN A GAP.** Membership is per unit (`RouteMembership`), so there is
    nothing to write until a unit exists — and `cascade_premises_routes_to_unit`
    (`BR-MET-083(b)`, `DEF-225`) puts every later unit on the routes its
    siblings are already on. A clerk who creates a property with no unit and
    picks a route gets the route the moment the first unit lands.
    """
    from apps.metering import selectors

    unit_ids = [
        str(value)
        for value in models.Unit.objects.filter(
            tenant_id=premises.tenant_id, premises=premises, deleted_at__isnull=True
        ).values_list("id", flat=True)
    ]
    before = len(selectors.stored_route_members(route.id))
    # ⊕ **`DEF-MET-9230` — THE BUILDING JOINS THE ROUTE, THROUGH THE ONE WRITER
    # OF THAT FACT.** Since `CR-131-BRC07` a route is a set of BUILDINGS
    # (`route_premises_memberships`) and the derivation billing asks
    # (`derivation._candidate_unit_ids`) reads that set and NOT the per-unit
    # `route_memberships` rows this function wrote — so a route picked on a
    # premises create was recorded where nothing looks, and a New Connection's
    # units (created after the premises) were in no cycle at all. The building
    # is added to the route's set through `_set_route_membership`, which owns
    # the denormalised service stamp, the legacy per-unit rows and the service
    # point stamps; it replaces the set, so the route's current buildings are
    # passed with this one added and nothing already on it moves.
    #
    # ⊕ **`DEF-MET-9250` — ADD-ONLY NOW, through `_add_buildings_to_route_set`.**
    # This called `_set_route_membership` with the route's current set plus
    # this building, and that writer REPLACES: on a route already holding
    # buildings a cascade had joined by unit rows only, it deleted their rows
    # and unstamped their service points. It also made an AREA route with no
    # pick pick-defined, dropping the rest of the area out of the run. The
    # helper keeps both boundaries (another route's building stays put; an
    # area route reaches a covered building without a pick).
    joined_building = bool(_add_buildings_to_route_set(route, [str(premises.id)]))
    added = _join_units_to_route(route, unit_ids)
    if not added and not joined_building:
        return []
    _audit(
        actor,
        "route.members_cascaded",
        "route",
        route.id,
        before={"members": before},
        after={
            "members": len(selectors.stored_route_members(route.id)),
            "br_ref": "BR-MET-083",
            "reason": "premises_created_on_route",
            "premises_id": str(premises.id),
            "units_added": len(added),
        },
    )
    return [{"route_id": str(route.id), "route_code": route.code, "units": len(added)}]


def _routes_a_premises_is_on(premises: models.Premises) -> list[models.Route]:
    """The ACTIVE routes a premises sits on, from BOTH directions — because
    there are two, and reading only one leaves a hole a whole building falls
    through.

    1. **Where its SIBLING UNITS actually are.** This is what a utility sees on
       SET-05 and what DEF-225 is literally about.
    2. **The routes drawn for its AREA.** Needed because a premises created
       straight into an area has NO units yet when the tag lands — the area
       cascade runs, finds nothing to add, and correctly does nothing. Every
       unit added afterwards would then be the "first" unit with no sibling to
       inherit from, so a sibling-only rule would silently never route the
       building at all.

    Siblings come FIRST and win ties per service: where a human has put unit A
    on a route, unit B joins unit A, not whatever the area says it should be.
    """
    tenant_id = premises.tenant_id
    ordered: list[models.Route] = []
    seen: set[str] = set()
    sibling_ids = list(
        models.Unit.objects.filter(
            tenant_id=tenant_id, premises=premises, deleted_at__isnull=True
        ).values_list("id", flat=True)
    )
    if sibling_ids:
        for membership in (
            models.RouteMembership.objects.filter(tenant_id=tenant_id, unit_id__in=sibling_ids)
            .select_related("route", "route__cycle", "route__service")
            .order_by("route__code", "id")
        ):
            if membership.route.status != "active":  # boundary 1
                continue
            if str(membership.route_id) in seen:
                continue
            seen.add(str(membership.route_id))
            ordered.append(membership.route)
    for route in _routes_for_area(premises.area if premises.area_id else None):
        if str(route.id) not in seen:
            seen.add(str(route.id))
            ordered.append(route)
    return ordered


def cascade_premises_routes_to_unit(actor: Any, unit: models.Unit) -> list[dict[str, Any]]:
    """BR-MET-083(b) — a unit added to a premises already on a route joins it.

    **This is DEF-225's named symptom.** A utility adds Unit B to a serviced
    building; before this, `RouteMembership` was written ONLY when a route was
    created or edited, so Unit B had no membership, its service points were
    stamped NULL, and `selectors.units_in_cycle` — which is BILLING's scope seam
    as well as Reads' — never saw it. Unit B was never read and never invoiced,
    and nothing warned anybody.

    Called BEFORE the meter grid runs, so the service points the grid creates
    inherit route and cycle through `ensure_service_point`'s existing lookup
    rather than needing a second stamp.
    """
    premises = models.Premises.objects.select_related("area").get(pk=unit.premises_id)
    joined: list[dict[str, Any]] = []
    seen_services: set[str] = set()
    for route in _routes_a_premises_is_on(premises):
        # ONE route per service (BR-MET-074). A premises split across two routes
        # of the SAME service is a state the wizard can produce; the first in
        # `_routes_a_premises_is_on`'s order wins, deterministically, rather
        # than the last write.
        key = str(route.service_id)
        if key in seen_services:
            continue
        seen_services.add(key)
        if not _join_units_to_route(route, [str(unit.id)]):
            continue
        _audit(
            actor,
            "route.members_cascaded",
            "route",
            route.id,
            after={
                "br_ref": "BR-MET-083",
                "reason": "unit_added_to_routed_premises",
                "unit_id": str(unit.id),
                "premises_id": str(unit.premises_id),
                "units_added": 1,
            },
        )
        joined.append({"route_id": str(route.id), "route_code": route.code, "units": 1})
    return joined


def cascade_route_area_members(actor: Any, route: models.Route) -> list[dict[str, Any]]:
    """BR-MET-083(c) — a route that BECOMES ACTIVE collects the premises tagged
    into its area while it was a draft.

    **This is DEF-225's mechanism arriving from the other side, and it is a hole
    two correct rules opened between them.** BR-MET-083(a) says a premises
    tagged into an area joins that area's routes. DEF-219 says a DRAFT route
    must gain nothing from that tag, because *"a draft affects nothing"* and the
    Members column on SET-05 counts memberships. Both hold. But
    `_routes_for_area` filters `status="active"`, so the draft is skipped and
    **nothing ever came back for it** — activation re-stamped the membership the
    wizard had set and never re-asked the area question. The ordinary
    onboarding order therefore lost buildings silently:

        1. draft the new water route for the North district
        2. tag the district's premises into North   ← correctly skipped, draft
        3. activate the route                       ← never re-asked

    and every premises tagged at step 2 was on no route, never read and never
    billed. A deferral with no payback is a deletion.

    The area question is asked DOWNWARD here — a route drawn for South covers
    South and South · SE — which is the same sentence `_routes_for_area` reads
    upward for one premises, through the same `selectors._area_ids_for`. One
    rule, two directions, and they must not be able to disagree.

    ⚠ **WHAT THIS DELIBERATELY DOES NOT DO.** DEF-225 also stays open for a
    route whose `area_id` is CHANGED on an already-active route, and for
    membership becoming a run-time DERIVATION rather than a stored answer. Both
    are left exactly where they are. The first is a real question — a route
    whose step-2 selection was a deliberate subset of its area would be
    overruled by re-deriving on every area edit — and answering it by choosing
    a value is what the prime directive forbids. The scope here is only the
    deferral the draft boundary created, paid back at the moment it ends.

    Membership is filled, never taken: `_join_units_to_route` leaves a unit
    already routed for this service exactly where it is (BR-MET-083 boundary 2 /
    BR-MET-074 — a move is confirmed on screen, and activating a route on
    another screen is not that confirmation).
    """
    from apps.metering import selectors

    if route.area_id is None or route.status != "active":
        return []
    area_ids = selectors._area_ids_for(str(route.area_id))
    if not area_ids:  # pragma: no cover - the row was resolved to get here
        return []
    unit_ids = [
        str(value)
        for value in models.Unit.objects.filter(
            tenant_id=route.tenant_id,
            premises__area_id__in=area_ids,
            premises__deleted_at__isnull=True,
            deleted_at__isnull=True,
        )
        .order_by("id")
        .values_list("id", flat=True)
    ]
    if not unit_ids:
        return []
    before = len(selectors.stored_route_members(route.id))
    added = _join_units_to_route(route, unit_ids)
    if not added:
        return []
    after = len(selectors.stored_route_members(route.id))
    _audit(
        actor,
        "route.members_cascaded",
        "route",
        route.id,
        before={"members": before},
        after={
            "members": after,
            "br_ref": "BR-MET-083",
            "reason": "route_activated_over_its_area",
            "area_code": route.area.code,
            "units_added": len(added),
        },
    )
    return [{"route_id": str(route.id), "route_code": route.code, "units": len(added)}]


def _set_meter_exclusions(route: models.Route, data: dict[str, Any]) -> None:
    """BR-MET-075 — `excluded_asset_ids` is the FULL exclusion set for this
    route, replacing whatever was stored. Absent = leave the stored set alone,
    which is what a PATCH that only renames a route must do.

    Nothing here touches the asset. An exclusion is a row saying "not read on
    this route"; the meter keeps its premises, its unit and its service point,
    so an excluded fire line is still metered, still billed and still visible
    everywhere it was before.

    ── CR-029 · THE REASON (B17 §6) ──────────────────────────────────────────
    *"`route_meter_exclusions.reason` — two words, shown in place"*. SET-06D's
    Assets tab renders the exclusions explaining themselves where they sit
    (*"MTR-W2262 excluded · premise demolished"*), so `exclusion_reasons` is a
    `{asset_id: "two words"}` map alongside the id list.

    ⚠ **THE WORD COUNT IS NOT ENFORCED, DELIBERATELY.** "Two words" is the
    design's description of the SHAPE — what fits the row without wrapping —
    and no ruling makes it a validation rule. Refusing *"gate permanently
    locked"* would lose the reason entirely, which is strictly worse than the
    column existing to prevent. The length is capped; the wording is the staff
    member's.
    """
    if "excluded_asset_ids" not in data:
        return
    tenant_id = route.tenant_id
    wanted = {str(value) for value in (data.get("excluded_asset_ids") or []) if str(value).strip()}
    reasons = {str(key): value for key, value in (data.get("exclusion_reasons") or {}).items()}
    models.RouteMeterExclusion.objects.filter(tenant_id=tenant_id, route=route).exclude(
        asset_id__in=wanted
    ).delete()
    for asset_id in wanted:
        if not _is_uuid(asset_id):
            _refuse_fields(
                [
                    _field_error(
                        "excluded_asset_ids", errors.VAL_FORMAT, "metering.route.asset_unknown"
                    )
                ]
            )
        row, _created = models.RouteMeterExclusion.objects.get_or_create(
            tenant_id=tenant_id, route=route, asset_id=asset_id
        )
        if asset_id in reasons:
            reason = _text(reasons[asset_id], 60)
            if row.reason != reason:
                row.reason = reason
                row.save(update_fields=["reason"])


def selector_membership(route: models.Route) -> list[dict[str, Any]]:
    """The STORED rows, for the AUDIT — not `route_members`, which derives.

    ⚠ **CR-029 D4 SPLIT THESE TWO AND THE AUDIT KEEPS THE STORED HALF.** The
    before/after pair on a route write has to say what the WRITE changed; the
    derived set answers *"who is on this route right now"*, which a write may
    leave completely alone (a rename) or change without touching a row (a
    re-drawn area). An audit row whose before and after were both derived would
    show N → N for the one act that actually moved a membership.
    """
    from apps.metering import selectors

    return selectors.stored_route_members(route.id)


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035b")
def update_route(actor: Any, route_id: Any, changes: Any) -> dict[str, Any]:
    """US-MET-006 TC-3 + CR-006: membership + walk-order edits in place,
    before/after audited (BR-MET-033/074). Reassigning a route MOVES it to the
    new cycle — one cycle per route at a time, never duplicated (BR-MET-010).

    **BR-MET-081 — an edit to an ACTIVE route takes effect at the next read
    window.** Nothing already issued changes (hard rule 4), no committed read
    is re-pointed and no in-flight batch is re-scoped: this function writes
    the route row, the membership rows and the CURRENT service-point stamps,
    and touches no `meter_reads` row at all. The wizard states that inline;
    this docstring is why the statement is true.
    """
    data = _payload_dict(changes)
    cleaned = _validate_route(data, partial=True)
    from apps.metering import selectors

    with transaction.atomic():
        row = _route_row(route_id, locked=True)
        before = {**selectors.route_dict(row), "members": selectors.stored_route_members(row.id)}
        if "code" in cleaned and cleaned["code"].lower() != row.code.lower():
            if (
                models.Route.objects.filter(tenant_id=row.tenant_id, code__iexact=cleaned["code"])
                .exclude(pk=row.pk)
                .exists()
            ):
                _refuse_fields(
                    [_field_error("code", errors.VAL_FORMAT, "metering.route.code_duplicate")]
                )
        fields: list[str] = []
        for field, value in cleaned.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                fields.append(field)
        if "cycle_id" in data:
            cycle = _resolve_cycle(data["cycle_id"])
            if row.cycle_id != (cycle.id if cycle else None):
                row.cycle = cycle
                fields.append("cycle")
        service_present, service = _resolve_service(data)
        # CR-029 D10 — the SET wins over the single field when both arrive, and
        # its first member is the transitional head (migration 0020's choice).
        set_present, service_set = _resolve_service_set(data)
        if set_present:
            service_present, service = True, (service_set[0] if service_set else None)
        if service_present and row.service_id != (service.id if service else None):
            row.service = service
            fields.append("service")
        area_present, area = _resolve_area(data)
        if area_present and row.area_id != (area.id if area else None):
            row.area = area
            fields.append("area")
        # CR-161-BRC10 W4 — an EDIT merges: the stored answers are kept, the
        # submitted ones applied, a submitted blank clears its key. Audited in
        # the before/after below because `route_dict` carries `custom_data`.
        custom = _route_custom_answers(data, dict(row.custom_data or {}))
        if custom is not None and custom != dict(row.custom_data or {}):
            row.custom_data = custom
            fields.append("custom_data")
        if fields:
            row.save(update_fields=[*fields, "updated_at"])
        if set_present:
            _set_route_services(row, service_set)
        elif "service" in fields:
            # The single-service path still maintains the SET, or a route edited
            # through the shipped field would read water and have an empty set —
            # two answers to "what does this route read", which is the whole
            # failure D2 is fixing one table over.
            _set_route_services(row, [service] if service is not None else [])
        if "service" in fields:
            # BR-MET-074: the denormalized stamp on every membership row
            # follows the route's service. Written here as well as in
            # `_set_route_membership` because a route may change service
            # WITHOUT its membership being re-sent, and a stale stamp would
            # silently relax the per-service uniqueness it exists to enforce.
            models.RouteMembership.objects.filter(tenant_id=row.tenant_id, route=row).update(
                service_id=row.service_id
            )
        members, moved_from = _set_route_membership(row, data)
        if "status" in fields or "service" in fields:
            # A route promoted out of draft (or moved between services) must
            # re-stamp its service points; membership may not have changed, so
            # `_set_route_membership` above will have returned early.
            _stamp_service_points(
                row, [member["unit_id"] for member in selectors.stored_route_members(row.id)]
            )
        sent_membership = any(key in data for key in ("members", "premises_ids", "unit_ids"))
        if "status" in fields and row.status == "active" and not sent_membership:
            # BR-MET-083(c) / DEF-225 — the draft boundary DEFERS the area
            # cascade (`_routes_for_area` skips a draft) and nothing used to
            # pay it back. Every premises tagged into this route's area while
            # it sat in draft was on no route, never read and never billed.
            # Runs AFTER the re-stamp above so the units it adds are stamped
            # by `_join_units_to_route`'s own stamper and not twice.
            #
            # ⚠ `not sent_membership` IS THE POINT, NOT AN OPTIMISATION. SET-06
            # step 2 lets an admin pick a DELIBERATE SUBSET of an area's
            # premises, and a request that activates the route AND states its
            # member list is that admin saying so in the same breath. Adding
            # the rest of the area on top would overrule a human decision made
            # one field away. The cascade repays a tag made SEPARATELY and
            # dropped by the draft rule; it never argues with the list in front
            # of it. An activation-only PATCH later still cascades.
            cascade_route_area_members(actor, row)
            members = selectors.stored_route_members(row.id)
        _audit(
            actor,
            "route.updated",
            "route",
            row.id,
            before=before,
            after={**selectors.route_dict(row), "members": members, "moved_from": moved_from},
        )
    return selectors.route_dict(_route_row(route_id))


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035b")
def deactivate_route(actor: Any, route_id: Any) -> dict[str, Any]:
    """IS-1: inactive routes drop out of assignment pickers; historical reads
    keep their route reference (US-MET-006 TC-4)."""
    from apps.metering import selectors

    with transaction.atomic():
        row = _route_row(route_id, locked=True)
        before = {"status": row.status}
        row.status = "inactive"
        row.save(update_fields=["status", "updated_at"])
        _audit(
            actor, "route.deactivated", "route", row.id, before=before, after={"status": "inactive"}
        )
    return selectors.route_dict(_route_row(route_id))


def collection_route_id(asset: Any) -> Any | None:
    """BR-MET-079 / DEF-233 — the route a read taken on `asset` belongs to.

    Resolved ONCE, at collection, and stamped onto the read. Two hops, in
    priority order, because an asset reaches a route two different ways and
    only one of them is always populated:

      1. `assets.service_point_id` → that point's `route_id` — set when a meter
         is attached to a service;
      2. the asset's CURRENT unit assignment → any service point on that unit
         carrying a route — for a meter recorded against a unit rather than a
         point.

    Returns None when neither resolves, and None is honest: it means "no route
    could be determined", never "no route". The guard treats it that way.

    ⚠ **HOP 2 GOES THROUGH `AssetAssignment` AND NOT `asset.unit` (DEF-243).**
    `assets.unit` is a TEXT column holding the explicit UoM (CLAUDE.md rule 3),
    NOT a foreign key to `metering.units` — `Asset` has no such key. Filtering
    it against Unit UUIDs compares a UoM string to a uuid, matches nothing, and
    reports zero without erroring. That is exactly what the previous version of
    the guard below did.
    """
    # Local import: metering→assets is the reviewed cross-module direction
    # (B2 §2, the same one `meter_reads.asset_id` already takes), but a
    # module-level import here would close a cycle — assets imports metering.
    from apps.assets import models as assets_models

    tenant_id = _tenant_id()
    point_id = getattr(asset, "service_point_id", None)
    if point_id:
        # DEF-MET-8107 — the batch post loads each asset WITH its service point
        # (`select_related`), so hop 1 is already in memory; asking the
        # database again was one statement per reading for a column we held.
        descriptor = getattr(type(asset), "service_point", None)
        if descriptor is not None and getattr(descriptor, "is_cached", None) and (
            descriptor.is_cached(asset)
        ):
            route_id = getattr(asset.service_point, "route_id", None)
        else:
            route_id = (
                models.ServicePoint.objects.filter(tenant_id=tenant_id, id=point_id)
                .values_list("route_id", flat=True)
                .first()
            )
        if route_id:
            return route_id
    unit_ids = list(
        assets_models.AssetAssignment.objects.filter(
            tenant_id=tenant_id, asset_id=getattr(asset, "id", asset)
        ).values_list("unit_id", flat=True)
    )
    if not unit_ids:
        return None
    route_id = (
        models.ServicePoint.objects.filter(
            tenant_id=tenant_id, unit_id__in=unit_ids, route_id__isnull=False
        )
        .order_by("id")
        .values_list("route_id", flat=True)
        .first()
    )
    if route_id:
        return route_id

    # ── HOP 3 · ASK THE DERIVATION (`CR-131-BRC07`, THE GATE'S OWN HAZARD) ──
    #
    # ⚠ **THIS IS THE ONE THING `CR-131-BRC07` STEP 1 SAID MUST NOT BE LEFT
    # UNDONE, AND IT IS WRITTEN OUT HERE BECAUSE NOTHING WOULD GO RED WITHOUT
    # IT.** Hops 1 and 2 both read `service_points.route_id`, which is a STORED
    # PROJECTION of route membership. The gate proved, by emptying that column
    # and calling this function, that a derivation design which stops
    # maintaining it stops stamping new reads:
    #
    #     collection_route_id WITH the point stamped    : …8913  (RT-009)
    #     collection_route_id WITHOUT any point stamp   : None
    #
    # `meter_reads.route_id` is NULLABLE and its own docstring calls NULL
    # *"honest"*, so **the read history would simply stop being recorded, from
    # the day it shipped, with every test and every gate green.** A guarantee
    # that rests on a projection nobody promised to keep is hard-won law 1.
    #
    # So the last hop asks the question directly — *which route reads this unit
    # for this service, right now?* — of `apps.metering.derivation`, which
    # answers from the premises a human picked and the areas a route is drawn
    # for, and needs no stored projection at all. The projection stays as the
    # FAST PATH, because it is one indexed read and this is several; it is no
    # longer the only path.
    from apps.metering import derivation

    for unit_id in unit_ids:
        answers = derivation.routes_for_unit(unit_id)
        if not answers:
            continue
        # Ordered by service code so two collections of the same read resolve
        # the same way; a meter takes one service in practice, and a unit that
        # somehow reaches two routes must not answer differently per call.
        for _code, found in sorted(answers.items()):
            if found.route_id:
                return found.route_id
    return None


def collection_account_id(asset: Any, *, lookups: Any = None) -> Any | None:
    """The account a read taken on `asset` belongs to — resolved at COLLECTION.

    ⚠ ADDED 2026-08-24 (DEF-658), AND WHAT IT FIXES IS AN ABSENCE, NOT A BUG.
    `meter_reads.account_id` is a reviewed cross-module FK (B2 §2) that has
    existed since the table did, and **nothing ever wrote it**. Every read in
    every seeded database carried NULL. `monthly_usage_service._read_facts`
    filters on exactly that column, so BR-MET-106's Usage tab — ruled by the PO
    on the morning of 2026-08-24 and built the same day — could never populate
    for any account, seeded or real.

    It is hard-won law 2 in its purest form: *"a component with an optional prop
    that nothing passes is dead UI: it renders nothing, every test passes, and
    the feature does not exist."* The column is nullable, so no constraint
    complained; the chart simply had no rows and drew its empty state, which is
    indistinguishable from an account with no reads.

    ⚠ AND THE TESTS COULD NOT SEE IT, WHICH IS THE PART WORTH REMEMBERING.
    `tests/test_br_met_106_monthly_usage._read` writes `account_id=` DIRECTLY,
    with a docstring that reasonably explains why (*"building each row through
    the five-step import wizard would make the fixture, not the behaviour, the
    thing under test"*). That is a fair call for testing the GROUPING. It also
    means every test of BR-MET-106 supplied by hand the one value production
    never supplied at all — so a green suite proved the arithmetic and said
    nothing about whether the input existed. The new case below drives a read
    through the real commit path and asserts the stamp.

    THE SAME SHAPE AS `collection_route_id`, deliberately: resolved ONCE, at
    collection, and never rewritten. That is not a convenience — it is the
    correct semantic. A read belongs to whoever was on supply on the day it was
    taken, so a later move-out must not retroactively reassign a year of
    history to nobody, and a new tenant moving in must not inherit the previous
    occupant's consumption. The `ix_meter_reads_acct_period` index over
    `(tenant, account, read_at)` is built for exactly this reading.

    Two hops, through the REVIEWED SEAMS and never through customers' tables
    directly (B1 module map — metering may not query `accounts`):

      1. the asset's current unit — `seams.current_unit_for_asset`;
      2. that unit's active account — `seams.active_account_for_unit`.

    Returns None when either hop does not resolve, and **None is honest and
    lawful**: an asset on a vacant unit, or on a unit nobody has taken service
    at, genuinely has no account, and the column is nullable for that reason.
    A read still commits — refusing one because the unit is empty would stop a
    utility recording a vacancy read, which BR-MET-036 depends on.
    """
    unit_id = seams.current_unit_for_asset(getattr(asset, "id", asset))
    if not unit_id:
        return None
    # DEF-MET-8107 — a batch post asks every unit's occupant in one read up
    # front (`_BatchLookups.prime_occupants`); the answer is the same seam's.
    account = (
        lookups.occupant(unit_id) if lookups is not None else seams.active_account_for_unit(unit_id)
    )
    return (account or {}).get("id")


def route_read_history_count(route_id: Any) -> int:
    """BR-MET-079 — how many committed reads point at this route.

    ⚠ **THE DURABLE LINK IS THE READ'S OWN STAMP. EVERYTHING ELSE HERE IS A
    FALLBACK, AND THE PREVIOUS VERSION OF THIS DOCSTRING WAS WRONG (DEF-233).**

    It said `read_import_batches.route_id` was "written when a batch is staged
    and is never cleared by a membership edit". True as far as it goes, and it
    could never fire: on the shipped fixture every one of the 135 `meter_reads`
    rows has `import_batch_id` NULL and `read_import_batches` holds ZERO rows.
    The only source that DID fire was the service points currently stamped with
    the route — and a membership move UNSTAMPS those. So the guard dropped to
    zero and the seeded Route 1, which had refused deletion naming 135 reads an
    hour earlier, was deleted after its premises were moved away.

    Hard-won law 1: a comment claiming a guarantee is not the guarantee.

    **FOUR sources are UNIONED over distinct read ids**, never summed — summing
    was the old shape and it needed an `.exclude()` to avoid double-counting,
    which is a bug waiting for a fifth source:

      1. `meter_reads.route_id`, the collection stamp (0012). Nothing a
         membership edit does can reach it. This is the one that fixes it.
      2. the read's import batch, where one exists.
      3. service points CURRENTLY stamped with the route — mutable, kept
         because it still catches reads whose stamp predates 0012.
      4. the asset's unit assignment → a service point on this route. **This
         hop was DEAD CODE and is fixed here (DEF-243)**: it filtered
         `asset__unit__in=<Unit uuids>`, and `assets.unit` is the explicit-UoM
         TEXT column, not a key to `metering.units`. A uuid never equals
         'kgal', so it matched nothing and reported zero without erroring.

    The union can only ever count MORE than the old sum, which is the safe
    direction: an under-counted history DELETES a route that has one; an
    over-counted one refuses a delete that `deactivate` still serves.
    """
    from apps.assets import models as assets_models  # see collection_route_id

    tenant_id = _tenant_id()
    point_ids = list(
        models.ServicePoint.objects.filter(tenant_id=tenant_id, route_id=route_id).values_list(
            "id", flat=True
        )
    )
    unit_ids = list(
        models.ServicePoint.objects.filter(tenant_id=tenant_id, route_id=route_id).values_list(
            "unit_id", flat=True
        )
    )
    asset_ids = (
        list(
            assets_models.AssetAssignment.objects.filter(
                tenant_id=tenant_id, unit_id__in=unit_ids
            ).values_list("asset_id", flat=True)
        )
        if unit_ids
        else []
    )
    predicate = Q(route_id=route_id) | Q(import_batch__route_id=route_id)
    if point_ids:
        predicate |= Q(asset__service_point_id__in=point_ids)
    if asset_ids:
        predicate |= Q(asset_id__in=asset_ids)
    return models.MeterRead.objects.filter(tenant_id=tenant_id).filter(predicate).distinct().count()


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035b")
def delete_route(actor: Any, route_id: Any) -> None:
    """BR-MET-008 + **BR-MET-079**: deletion refuses while ANY unit/service
    point is a member (US-MET-006 TC-5) **AND once the route has READS
    HISTORY** — deactivate only. The refusal names which guard fired.

    ⚠ **WHY THE SECOND GUARD WAS NEEDED.** BR-MET-008 locks on MEMBERSHIP, so
    a route whose members were all removed became deletable even though a year
    of reads pointed at it — and deleting it would orphan the only record of
    who read those meters. CR-006 verbatim: *"deleting is not allowed once a
    route has reads history — deactivate only"*.
    """
    from apps.metering import selectors

    with transaction.atomic():
        row = _route_row(route_id, locked=True)
        members = models.RouteMembership.objects.filter(tenant_id=row.tenant_id, route=row).count()
        points = models.ServicePoint.objects.filter(tenant_id=row.tenant_id, route=row).count()
        reads = route_read_history_count(row.id)
        if reads:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-MET-079",
                message_key="metering.route.delete_blocked_read_history",
                params={"reads": reads, "alternative": "deactivate"},
            )
        if members or points:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-MET-008",
                message_key="metering.route.delete_blocked_referenced",
                params={"members": members, "service_points": points, "alternative": "deactivate"},
            )
        before = selectors.route_dict(row)
        # ⚠ **CONFIGURATION IS CLEARED HERE; HISTORY IS NOT** (CR-029 W1-T4).
        # Every table CR-029 adds takes a PROTECT FK to `routes`, and the two
        # below are things a human CONFIGURED about a route that is going away:
        # which services it reads (D10) and the order its stops are walked
        # (D11). Leaving them would make `DELETE /routes/{id}` raise
        # `ProtectedError` — a 500 on a path that has two tested refusals — and
        # that is exactly what it did until `tests/test_def233_route_read_stamp
        # .py` deleted a route it had never read and quoted the error.
        #
        # `read_windows` is DELIBERATELY ABSENT from this list. A closed window
        # is what a crew DID, and its PROTECT is the same guard BR-MET-079 above
        # gives collected reads: a route with read history is deactivated, never
        # deleted. RC-W2 writes those rows; the guard is here first.
        models.RouteMeterExclusion.objects.filter(tenant_id=row.tenant_id, route=row).delete()
        models.RouteService.objects.filter(tenant_id=row.tenant_id, route=row).delete()
        models.RoutePremisesOrder.objects.filter(tenant_id=row.tenant_id, route=row).delete()
        row.delete()
        _audit(actor, "route.deleted", "route", route_id, before=before)


#: BR-MET-077 — the DAY-OF-MONTH default SET-07 step 3 writes, **now one and
#: not four (D2 + D9, W5-T2)**. `bill_day` is an integer 1–31, not a date: it
#: says *"this cycle normally bills on the 5th"*, and D9 keeps it as the CYCLE's
#: default which the RUN may override.
#:
#: ⚠ **`read_day_from` / `read_day_to` / `due_day` WERE HERE AND ARE DROPPED**
#: (metering 0021). The read window is `start_day` + `days_to_complete` and is
#: derived, never stored; the due fact billing actually reads is `due_days`, a
#: COUNT added to the bill date, not a day-of-month that could wrap.
CYCLE_DAY_FIELDS = ("bill_day",)

#: Field names a client may still SEND and this module no longer STORES — the
#: five columns metering 0021 dropped. `read_day_from`/`read_day_to` are used
#: (they derive the ruled pair for a caller that has not moved); the two dates
#: are read and discarded, because ONE PARTICULAR period's dates were never what
#: a cycle definition holds. Refusing them would break a caller over a field it
#: is entitled to think exists, for no gain — so they are accepted, ignored, and
#: named here rather than silently swallowed by `metering.unknown_field`.
_ACCEPTED_LEGACY_SCHEDULE_FIELDS = (
    "window_start",
    "window_end",
    "read_day_from",
    "read_day_to",
    "due_day",
)
#: Where `_validate_cycle` parks them so they never reach `models.Cycle(**…)`.
_LEGACY_SCHEDULE_KEY = "_legacy_schedule"


def _cycle_window_for(cycle: Any, read_at: Any) -> tuple[date, date] | None:
    """The cycle's read window, in the month the READ belongs to (W5-T2).

    Replaces two dropped columns (`cycles.window_start` / `window_end`) at the
    two places a READ is checked against its cycle's window: BR-MET-016's second
    duplicate clause and the staging context `_build_context` builds.

    ⚠ **THE MONTH IS NOT CHOSEN HERE — IT ARRIVES WITH THE READ**, which is what
    makes this `derive_read_window`'s documented use (*"placed in `anchor`'s
    month … a RENDERING choice for a month already picked"*) and NOT the
    generate-occurrences path OQ-339 blocks. A cycle that has not been given
    both facts answers `None`, and every caller treats that as *no window to
    check against* — the same silence the null columns produced.

    ⚠ **THE START DAY IS THE EFFECTIVE ONE (`DEF-MET-10588`, 2026-10-24).** This
    read the STORED `start_day` while Settings printed the effective one
    (OQ-340: the first run anchors), so one cycle had two windows — Brookfield
    `CY-001` read 10/10–10/14 here and 14–18 in Settings. It now asks
    `period_engine.cycle_read_window`, the one derivation.
    """
    if cycle is None or read_at is None:
        return None
    anchor = read_at.date() if hasattr(read_at, "date") else read_at
    if not isinstance(anchor, date):
        return None
    return period_engine.cycle_read_window(cycle, anchor)


def _sync_cycle_schedule(row: models.Cycle, legacy: dict[str, Any] | None = None) -> None:
    """CR-029 D2 — one generation, and since W5-T2 there is only one to write.

    ⚠ **THIS FUNCTION USED TO KEEP TWO GENERATIONS IN STEP** and that was gap
    G2's containment, not its cure: `cycles` grew a second set of schedule
    columns, each half of the product read a different one, and a cycle created
    through the wizard showed **no read window** in the bill-run picker or on
    S27 — two half-read generations, nothing broken, no error. W1 made
    `start_day` + `days_to_complete` the SOURCE and kept the legacy day pair as
    a maintained copy; W5-T2 dropped the copy.

    What survives is the other direction, and it still earns its place: a client
    that has not moved may still send only the legacy pair, and this derives the
    ruled fields from it so the row is stored in the one generation that exists.
    `_validate_cycle` accepts those two names for exactly this purpose and
    stores neither.

    Called after the payload is applied and BEFORE `_check_cycle_days`, so what
    it derives is validated by the same rule a hand-typed value would be.
    """
    if row.start_day is not None and row.days_to_complete is not None:
        return
    start_day, days = schedule.backfill_schedule(
        read_day_from=(legacy or {}).get("read_day_from"),
        read_day_to=(legacy or {}).get("read_day_to"),
    )
    if row.start_day is None:
        row.start_day = start_day
    if row.days_to_complete is None:
        row.days_to_complete = days


def _validate_cycle(payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}
    known = {
        "code",
        # ⚠ **`bill_date` IS ACCEPTED AND NOT STORED (RC-W6, metering 0023).**
        # The column is gone: OQ-344 ruled what replaces it — *"I'd say B -
        # these are defualt - user can override"*, the bill DAY in the month
        # after the period ends — so billing derives the fallback and nothing
        # reads a stored date. The NAME stays accepted for the same reason
        # `window_start`/`window_end` do: a client that has not moved is
        # entitled to think the field exists, and refusing it would break that
        # caller for no gain. The value is validated and discarded.
        "bill_date",
        "due_days",
        # CR-006 / BR-MET-077
        "name",
        "frequency",
        "status",
        "first_run_date",
        # CR-029 / B17 §2 — the three fields about time (frequency is above).
        "start_day",
        "days_to_complete",
        *CYCLE_DAY_FIELDS,
        # ⚠ ACCEPTED, NOT STORED (W5-T2). `window_start`/`window_end` and the
        # legacy day pair were columns until metering 0021. A client that has
        # not moved may still send them; `_sync_cycle_schedule` derives the
        # ruled fields from the day pair and the dates are ignored, because ONE
        # PARTICULAR period's dates were never what a cycle definition holds.
        # Refusing them instead would break a caller over a field it is entitled
        # to think exists, for no gain.
        *_ACCEPTED_LEGACY_SCHEDULE_FIELDS,
    }
    # BR-MET-078 FIRST, so a late-fee field gets the ruling's own refusal and
    # not the generic "unknown field" that reads as an oversight.
    _refuse_money_fields(payload, fe)
    _refuse_fields(fe)
    for field in payload:
        if field not in known and field != "route_ids":
            fe.append(_field_error(field, errors.VAL_FORMAT, "metering.unknown_field"))
    _refuse_fields(fe)

    if "name" in payload:
        out["name"] = _text(payload["name"], 200)
    if "frequency" in payload:
        # CR-029: the CR-006 vocabulary (and the PO's own spellings) map onto
        # the business word BEFORE the check, so a client that has not moved is
        # understood rather than refused; an unknown word maps to itself and is
        # then refused by name below.
        frequency = schedule.business_frequency(_text(payload["frequency"], 20))
        if frequency is not None and frequency not in CYCLE_FREQUENCIES:
            fe.append(
                _field_error(
                    "frequency",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.cycle.frequency_unknown",
                    allowed=list(CYCLE_FREQUENCIES),
                )
            )
        else:
            out["frequency"] = frequency
    if "status" in payload:  # BR-MET-076
        status = _text(payload["status"], 20)
        if status is not None and status not in LIFECYCLE_STATUSES:
            fe.append(
                _field_error(
                    "status",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.cycle.status_unknown",
                    allowed=list(LIFECYCLE_STATUSES),
                )
            )
        elif status is not None:
            out["status"] = status
    if "first_run_date" in payload:
        raw = payload["first_run_date"]
        if raw in (None, ""):
            out["first_run_date"] = None
        else:
            try:
                out["first_run_date"] = date.fromisoformat(str(raw))
            except ValueError:
                fe.append(
                    _field_error("first_run_date", errors.VAL_FORMAT, "metering.cycle.bad_date")
                )
    for field in (*CYCLE_DAY_FIELDS, "start_day"):
        if field not in payload:
            continue
        raw = payload[field]
        if raw in (None, ""):
            out[field] = None
            continue
        try:
            day = int(raw)
        except (TypeError, ValueError):
            day = 0
        if not 1 <= day <= 31:
            fe.append(_field_error(field, errors.VAL_RANGE, "metering.cycle.day_of_month_range"))
        else:
            out[field] = day
    # CR-029 — *"days to complete it"*. A window of ZERO days is not a short
    # window, it is no window at all: the crew would have no day to read on and
    # `derive_read_window` would have to invent an end date. Refused with its
    # own key rather than silently clamped.
    if "days_to_complete" in payload:
        raw = payload["days_to_complete"]
        if raw in (None, ""):
            out["days_to_complete"] = None
        else:
            try:
                days = int(raw)
            except (TypeError, ValueError):
                days = 0
            if days < 1:
                fe.append(
                    _field_error(
                        "days_to_complete",
                        errors.VAL_RANGE,
                        "metering.cycle.days_to_complete_range",
                    )
                )
            else:
                out["days_to_complete"] = days
    _refuse_fields(fe)

    if "code" in payload or not partial:
        code = _text(payload.get("code"), 40)
        if not code:
            fe.append(_field_error("code", errors.VAL_REQUIRED, "metering.cycle.code_required"))
        out["code"] = code
    if "bill_date" in payload:
        # ⚠ **VALIDATED AND DISCARDED (RC-W6).** The column is gone (metering
        # 0023, OQ-344) so there is nothing to store, but a malformed value is
        # still refused by name rather than silently swallowed: a client sending
        # `"bill_date": "not-a-date"` has a bug and answering 201 would hide it.
        # Accepting the field and dropping a WELL-FORMED value is the
        # `window_start`/`window_end` posture — the field is legacy, not wrong.
        raw = payload["bill_date"]
        if raw not in (None, ""):
            try:
                date.fromisoformat(str(raw))
            except ValueError:
                fe.append(_field_error("bill_date", errors.VAL_FORMAT, "metering.cycle.bad_date"))
    # The dropped names, parked rather than stored (W5-T2). The day pair is what
    # `_sync_cycle_schedule` derives the ruled fields from; the two dates are
    # read and discarded.
    #
    # ⚠ **THEY ARE VALIDATED BY THE SAME RULES THEY ALWAYS WERE**, and that is
    # not politeness — it is CR-006's TC set. A caller sending `read_day_from =
    # 32` or a backwards pair is telling us something wrong about the schedule,
    # and accepting it silently would turn a refusal a client already handles
    # into a cycle with a start day nobody chose. `read_day_from`/`due_day` are
    # DAYS OF THE MONTH (1–31); `read_day_to` must not precede `read_day_from`.
    legacy: dict[str, Any] = {}
    for field in ("read_day_from", "read_day_to", "due_day"):
        if field not in payload or payload[field] in (None, ""):
            continue
        try:
            day = int(payload[field])
        except (TypeError, ValueError):
            day = 0
        if not 1 <= day <= 31:
            fe.append(_field_error(field, errors.VAL_RANGE, "metering.cycle.day_of_month_range"))
        else:
            legacy[field] = day
    if (
        legacy.get("read_day_from") is not None
        and legacy.get("read_day_to") is not None
        and legacy["read_day_from"] > legacy["read_day_to"]
    ):
        fe.append(_field_error("read_day_to", errors.VAL_RANGE, "metering.cycle.read_window_order"))
    if legacy:
        out[_LEGACY_SCHEDULE_KEY] = legacy
    if "due_days" in payload:
        raw = payload["due_days"]
        if raw in (None, ""):
            out["due_days"] = None
        else:
            try:
                due_days = int(raw)
            except (TypeError, ValueError):
                due_days = -1
            if due_days < 0:  # BR-MET-009: due_days ≥ 0
                fe.append(
                    _field_error("due_days", errors.VAL_RANGE, "metering.cycle.due_days_range")
                )
            else:
                out["due_days"] = due_days
    _refuse_fields(fe)
    return out


def _check_cycle_days(row: models.Cycle) -> None:
    """BR-MET-077: read-from ≤ read-to ≤ bill day.

    ⚠ **THE DUE DAY IS DELIBERATELY NOT IN THAT CHAIN.** r10's own hint reads
    *"Dates must land in order: read → bill → due → late"* and its example is
    *read 1–3 · bill 5th · due 26th*, which satisfies it — but a cycle that
    bills on the 26th and is due on the 5th is a perfectly normal Net-10
    arrangement that WRAPS into the following month. Enforcing due ≥ bill as a
    day-of-month comparison would refuse it, and refusing a real cycle to
    satisfy a hint written about one example is the wrong trade. The wrap is
    visible in the preview strip instead, which says "of the following month".

    The late clause of r10's hint is not enforced and not stored — BR-MET-078.
    """
    fe: list[dict[str, Any]] = []
    # ⚠ THE COMPARISON MOVED WITH THE COLUMNS (W5-T2). It read `bill_day <
    # read_day_to`, and `read_day_to` is gone; the day the read window CLOSES is
    # now derived — `start_day + days_to_complete - 1` — which is the same fact
    # the dropped column held and is true for every cycle rather than only the
    # ones that carried the legacy pair. It clamps at 31 for the same reason
    # `schedule.legacy_day_pair` used to: a window that runs into the next month
    # cannot be compared as a day-of-month, and refusing a real cycle to satisfy
    # that arithmetic is the wrong trade.
    close_day = (
        min(row.start_day + row.days_to_complete - 1, 31)
        if row.start_day and row.days_to_complete
        else None
    )
    if row.bill_day and close_day and row.bill_day < close_day:
        fe.append(_field_error("bill_day", errors.VAL_RANGE, "metering.cycle.bill_day_before_read"))
    _refuse_fields(fe)


# ⚠ **`_check_cycle_window` IS GONE — W5-T2, 2026-08-23.** It enforced
# BR-MET-009's *window start ≤ end ≤ bill date* over `window_start` /
# `window_end` / `bill_date`, and metering 0021 dropped the first two: the read
# window is DERIVED now (B17 §2), and a derived window cannot be out of order —
# `start_day + days_to_complete` is a start and a LENGTH, so US-MET-006 TC-6's
# failure mode no longer has a way to occur. What is left of the rule is the
# bill date's ordering against the window end, and there is no stored window end
# to order it against; `_check_cycle_days` holds the surviving comparison
# (`bill_day` against the derived close day) and states it in day-of-month terms,
# which is the generation D9 kept.
#
# The check is DELETED rather than left as a no-op, because a validator that
# cannot fail is a guarantee a reader will believe (hard-won law 1).


def _warn_if_windows_overlap(row: models.Cycle, warnings: list[dict[str, Any]]) -> None:
    """OQ-341 — *"you give warning and if user override; let them do it"*.

    PO ruling 2026-08-23, verbatim: *"B: refuse it (Daily accepts 1, Weekly ≤7,
    Monthly ≤28) - you give warning and if user override; let them do it"*.
    **The option was AMENDED inside the ruling**: what was written as a refusal
    was ruled as a warning the operator may override.

    So this appends to `warnings` and **NEVER calls `_refuse_fields`**. A cycle
    whose days-to-complete is longer than its own repeat SAVES, and
    `period_engine` generates its overlapping windows — a crew really can be
    working two rounds at once. Turning this into a field error would build
    option B as it was written rather than as it was ruled.

    Worked, on the figure the PO was shown: a **Daily** cycle with **3 days** to
    complete warns that the most it can hold is **1**, and window 1 (1–3 Sep)
    and window 2 (2–4 Sep) are both created.

    ⚠ The warning also reaches every READ of the cycle, as
    `cycle_dict()["schedule_warning"]` — because a collision configured last
    month is still a collision, and a warning only the save response carried
    would be invisible the moment the wizard closed.
    """
    warning = period_engine.overlap_warning(
        frequency=row.frequency, days_to_complete=row.days_to_complete
    )
    if warning is not None:
        warnings.append(warning)


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035b")
def create_cycle(actor: Any, payload: Any) -> dict[str, Any]:
    """CR-006 SET-07 — a cycle DEFINITION: code, name, frequency, its routes
    and its day-of-month defaults (BR-MET-077). Draft or active (BR-MET-076).

    The code comes from the `cycle` numbering series when the caller sends
    none, exactly as `create_route` does. **No money field is accepted here
    at any point** (BR-MET-078) — `_validate_cycle` refuses each one by name.

    ⚠ **THE ALLOCATION IS INSIDE `atomic()` AND MUST STAY THERE (DEF-234)** —
    identical shape, identical break, identical reasoning as `create_route`
    above, which is where the full note lives. "Exactly as `create_route` does"
    was true of the bug as well as of the feature.
    """
    data = _payload_dict(payload)
    warnings: list[dict[str, Any]] = []
    from apps.metering import selectors

    with transaction.atomic():
        if not str(data.get("code") or "").strip():
            # ⛔ **DEF-2870 — `_allocate_number` HANDS OUT A CODE THAT ALREADY
            # EXISTS, AND THE NEXT STATEMENT REFUSES IT.** `seed_demo` writes
            # `CY-001`..`CY-006` and `RT-001`..`RT-006` with EXPLICIT codes, and
            # a caller-supplied code consumes nothing from the series — so on a
            # freshly seeded database both counters stand at 1 with six rows on
            # file. Measured on a fresh PostgreSQL 16 database, 2026-09-01:
            # `cycle` next_number = 1, `route` next_number = 1, `CY-001`..
            # `CY-006` and `RT-001`..`RT-006` all present, and
            # `manage.py load_sample_data --tenant brazosbend` died on
            # `core.errors.ValidationError: VAL-002
            # (metering.cycle.code_duplicate)` — taking TEN blocks down with it
            # and leaving the tenant with 0 accounts and 0 customers.
            #
            # This is DEF-577's invariant, one table over: *a series must never
            # hand out a number that already exists.* That defect's fix,
            # `_allocate_unused_number`, was applied to `premises` and `unit`
            # and to nothing else, so cycles and routes kept the bug. They ask
            # case-INSENSITIVELY because the duplicate guard three lines below
            # refuses on `code__iexact`.
            allocated = _allocate_unused_number(
                actor,
                CYCLE_SERIES,
                warnings,
                model=models.Cycle,
                field="code",
                case_insensitive=True,
            )
            if allocated:
                data = {**data, "code": allocated}
        cleaned = _validate_cycle(data, partial=False)
        if models.Cycle.objects.filter(
            tenant_id=_tenant_id(), code__iexact=cleaned["code"]
        ).exists():
            _refuse_fields(
                [_field_error("code", errors.VAL_FORMAT, "metering.cycle.code_duplicate")]
            )
        legacy_schedule = cleaned.pop(_LEGACY_SCHEDULE_KEY, None)
        row = models.Cycle(tenant_id=_tenant_id(), **cleaned)
        # CR-029 D2 — ONE generation. `legacy_schedule` is what a client that
        # has not moved sent; nothing here stores it.
        _sync_cycle_schedule(row, legacy_schedule)
        _check_cycle_days(row)
        _warn_if_windows_overlap(row, warnings)
        row.save()
        moved = _assign_routes_to_cycle(row, data.get("route_ids"))
        _audit(
            actor,
            "cycle.created",
            "cycle",
            row.id,
            after={**selectors.cycle_dict(row), **moved, "warnings": warnings},
        )
    return {**selectors.cycle_dict(_cycle_row(row.pk)), "warnings": warnings}


def _assign_routes_to_cycle(cycle: models.Cycle, route_ids: Any) -> dict[str, Any]:
    """BR-MET-010: assigning a route to a new cycle MOVES it (the caller's
    confirmation is a UI affordance); it is never double-listed.

    **ONE CYCLE PER ROUTE PER SERVICE (CR-006) NEEDS NO SECOND CONSTRAINT**,
    and that is worth stating so nobody adds one. A route holds exactly one
    `cycle_id` and exactly one `service_id`, so "one cycle per route per
    service" is already true by construction — the per-service qualifier
    describes what the single FK MEANS now that a route carries a service, not
    an extra rule to enforce.

    A DRAFT cycle stamps no service point (BR-MET-076): the route is recorded
    as belonging to it, and Reads and Billing cannot see it until it is
    activated.
    """
    if not route_ids:
        return {"routes_moved": []}
    moved = []
    for route_id in route_ids:
        route = _route_row(route_id, locked=True)
        if route.cycle_id != cycle.id:
            moved.append({"route": route.code, "from_cycle_id": str(route.cycle_id or "") or None})
            route.cycle = cycle
            route.save(update_fields=["cycle", "updated_at"])
            stamp = cycle if cycle.status != "draft" and route.status != "draft" else None
            models.ServicePoint.objects.filter(tenant_id=cycle.tenant_id, route=route).update(
                cycle=stamp
            )
    return {"routes_moved": moved}


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035b")
def update_cycle(actor: Any, cycle_id: Any, changes: Any) -> dict[str, Any]:
    data = _payload_dict(changes)
    warnings: list[dict[str, Any]] = []
    cleaned = _validate_cycle(data, partial=True)
    from apps.metering import selectors

    with transaction.atomic():
        row = _cycle_row(cycle_id, locked=True)
        before = selectors.cycle_dict(row)
        if "code" in cleaned and cleaned["code"].lower() != row.code.lower():
            if (
                models.Cycle.objects.filter(tenant_id=row.tenant_id, code__iexact=cleaned["code"])
                .exclude(pk=row.pk)
                .exists()
            ):
                _refuse_fields(
                    [_field_error("code", errors.VAL_FORMAT, "metering.cycle.code_duplicate")]
                )
        legacy_schedule = cleaned.pop(_LEGACY_SCHEDULE_KEY, None)
        for field, value in cleaned.items():
            setattr(row, field, value)
        # CR-029 D2 + W5-T2: there is no second generation to keep in step any
        # more. A PATCH used to have to blank the legacy day pair so S27's export
        # and the countdown would stop answering from the window the cycle used
        # to have; the columns those readers used are gone, and the derived
        # window follows `start_day`/`days_to_complete` by construction.
        _sync_cycle_schedule(row, legacy_schedule)
        _check_cycle_days(row)
        # OQ-341 — the same warning on an EDIT, because the collision is most
        # often created by editing days-to-complete on a cycle that was fine.
        _warn_if_windows_overlap(row, warnings)
        row.save()
        if "status" in cleaned:
            # BR-MET-076: activating a draft cycle stamps its routes' service
            # points; demoting one to draft unstamps them. Without this, a
            # cycle could be "active" on screen and invisible to every bill
            # run — built-is-not-wired at the level that decides who is billed.
            for route in models.Route.objects.filter(tenant_id=row.tenant_id, cycle=row):
                stamp = row if row.status != "draft" and route.status != "draft" else None
                models.ServicePoint.objects.filter(tenant_id=row.tenant_id, route=route).update(
                    cycle=stamp
                )
        moved = _assign_routes_to_cycle(row, data.get("route_ids"))
        _audit(
            actor,
            "cycle.updated",
            "cycle",
            row.id,
            before=before,
            after={**selectors.cycle_dict(row), **moved},
        )
    return {**selectors.cycle_dict(_cycle_row(cycle_id)), "warnings": warnings}


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035b")
def delete_cycle(actor: Any, cycle_id: Any) -> None:
    """BR-MET-009: audit-locked once a read batch or bill run references the
    cycle (US-MET-006 TC-9); assigned routes block too — the cycle's route
    list IS the set of routes pointing at it (BR-MET-010)."""
    from apps.metering import selectors

    with transaction.atomic():
        row = _cycle_row(cycle_id, locked=True)
        routes = models.Route.objects.filter(tenant_id=row.tenant_id, cycle=row).count()
        referenced = seams.cycle_is_referenced(row.id)
        if routes or referenced:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-MET-009",
                message_key="metering.cycle.delete_blocked_referenced",
                params={"routes": routes, "referenced": referenced},
            )
        before = selectors.cycle_dict(row)
        models.ReadSchedule.objects.filter(tenant_id=row.tenant_id, cycle=row).delete()
        row.delete()
        _audit(actor, "cycle.deleted", "cycle", cycle_id, before=before)


# ═══════════════════════════════════════════════════════════════════════════
# W2 READS LANE — US-MET-007..011 · US-MET-014/015 (2026-08-10)
#
# Rules:   BR-MET-012 (staged import) · BR-MET-013/014/032 (template mapping +
#          tag inheritance) · BR-MET-015 (severity model: errors resolved,
#          warnings accepted with a reason) · BR-MET-016/024/053 (supersede,
#          never edit) · BR-MET-017 (compliance stamp) · BR-MET-018 🔒
#          (file+tags idempotency) · BR-MET-019 (consumption + explicit unit) ·
#          BR-MET-020/021/022/052 (config-driven flags) · BR-MET-026..030/058/
#          062 (estimation + true-up) · BR-MET-054 (delete = staged/rejected
#          only) · CLAUDE.md rules 1, 2, 3, 4, 7
#
# Sole-writer law (LAW 0 / B8) holds here exactly as it does above: every read
# row, every batch row and the ONE permitted UPDATE on a committed read
# (superseded_by_id + superseded_at, B2 r8) happen in this module and nowhere
# else. `validation.py` and `estimation.py` DECIDE; this layer gathers their
# inputs and persists their verdicts.
#
# Money boundary: nothing below reads a rate, computes an amount or rounds.
# Reads stop at validated, flagged, stored CONSUMPTION with its explicit unit.
# ═══════════════════════════════════════════════════════════════════════════

READ_BATCH_SERIES = "read_batch"  # EP-TEN-08-style series; absent → NULL + warning

# NUMERIC(18,6) is the column's DECLARED scale (B2 §2 / DB-3's discipline
# applied to quantities). Postgres quantizes to it on INSERT; sqlite does not,
# so the same arithmetic would persist different digits on the two vendors and
# a golden-style assertion would pass on one and fail on the other. Applying it
# HERE, at persist time only, makes them agree. This is NOT the B4.4 rounding
# rule — that one rounds MONEY at invoice-line finalization and is untouched:
# nothing in this module produces a currency figure at all.
_NUMERIC_18_6 = Decimal("0.000001")


def _num6(value: Any) -> Any:
    return value.quantize(_NUMERIC_18_6) if isinstance(value, Decimal) else value


def _read_config() -> Any:
    """The tenant's `read_validation_settings` row, or None.

    BR-MET-020 / US-MET-011 TC-9: None is a legitimate, REPORTED state — the
    engine skips threshold rules rather than falling back to code constants.

    Since CR-038 A1 this row is the ESTIMATION home plus the electric/water
    THRESHOLD FALLBACK; paths that judge reads assemble `_config_set()` so the
    engine can resolve per service. Estimation keeps reading this row directly
    (est_method/est_max_consecutive stayed tenant-wide by the ruling's own
    scope — "the service-shaped values" moved, nothing else).
    """
    return models.ReadValidationSettings.objects.filter(tenant_id=_tenant_id()).first()


def _service_settings_map() -> dict[str, Any]:
    """`{service code: ReadValidationServiceSettings row}` for this tenant —
    the per-service half of CR-038 A1, loaded once per operation."""
    return {
        row.service.code: row
        for row in models.ReadValidationServiceSettings.objects.filter(
            tenant_id=_tenant_id()
        ).select_related("service")
    }


def _config_set() -> validation.ConfigSet:
    """The tenant's WHOLE validation config for the engine to resolve per
    service (CR-038 A1). One query pair per batch/read operation."""
    return validation.ConfigSet(tenant_row=_read_config(), service_rows=_service_settings_map())


# ── CR-038 A1: the RATIFIED per-service seed ────────────────────────────────
# EXACTLY the figures the PO has already signed and NOT ONE MORE: the OQ-002
# closure (high 200% AND floor 50 kWh electric / 1 kgal water · low 25% ·
# days 25–35 flag / 20–45 hard), BR-MET-025's 3% mismatch sample and
# BR-MET-052's confirmed ±1% TOU tolerance, restated per service. These are
# SEEDED defaults in BR-MET-020's sense — written when a row is CREATED, never
# read by the engine when it is absent.
#
# ⚠ AMENDED 2026-08-26, SAME DAY: BR-MET-120 RATIFIED THE REST (CR-038, the
# Blueprint's Open 5 — PO verbatim: "I agree with all your recomendation -
# please mark them as rule"). The table below now carries the ratified floors
# for gas (20 ccf), thermal_heat (10 therm), sewer (1 kgal, only meaningful
# where a sewer meter exists), solar (50 kWh — the export register's service)
# and battery (50 kWh). THREE services stay absent ON PURPOSE, each for its
# own ratified reason: trash and storm_water are never read (no rule row can
# exist for an unread service), and broadband is DEFERRED with Open 7 (no
# register exists to read). Their threshold rules keep the TC-9 fail-safe
# skip-and-report. tests/test_cr038_s64_service_settings.py asserts every
# figure below so drift goes RED (sign-off rule 2026-08-11, part 2).
RATIFIED_SERVICE_SEED: dict[str, dict[str, Any]] = {
    "electric": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("50"),
        "high_abs_unit": "kWh",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "water": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("1"),
        "high_abs_unit": "kgal",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "gas": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("20"),
        "high_abs_unit": "ccf",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "sewer": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("1"),
        "high_abs_unit": "kgal",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "solar": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("50"),
        "high_abs_unit": "kWh",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "thermal_heat": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("10"),
        "high_abs_unit": "therm",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
    "battery": {
        "high_pct": Decimal("200"),
        "high_abs_value": Decimal("50"),
        "high_abs_unit": "kWh",
        "low_pct": Decimal("25"),
        "zero_scope": "active_non_vacant",
        "days_flag_min": 25,
        "days_flag_max": 35,
        "days_hard_min": 20,
        "days_hard_max": 45,
        "mismatch_pct": Decimal("3"),
        "tou_sum_tolerance_pct": Decimal("1"),
    },
}


def ensure_read_validation_settings() -> Any:
    """Provisioning entry point: seed the tenant's config row with the
    PO-RATIFIED defaults of B2 r5 #15 (the column defaults ARE those values —
    OQ-002 + OQ-003 closures). Idempotent; safe to call at every provisioning
    run. Tenancy owns provisioning, so it calls this — metering never reaches
    into another module to seed itself.

    CR-038 A1 ("we will provide default value to start with on all these
    rules"): ALSO seeds the per-service rows — for the services in
    `RATIFIED_SERVICE_SEED` that this tenant has ENABLED, and no others (see
    the constant's own warning about the eight unratified services). Never
    overwrites: a tenant that has tuned a row keeps it (get_or_create)."""
    row, _created = models.ReadValidationSettings.objects.get_or_create(tenant_id=_tenant_id())
    ensure_read_validation_service_rows()
    return row


def service_seed_figures(legacy_row: Any, code: str) -> dict[str, Any]:
    """The figures a NEW electric/water per-service row is seeded with: the
    tenant's OWN legacy tenant-wide row where one exists (so a tenant whose
    figures were ever tuned keeps judging reads by exactly the numbers that
    governed yesterday — behavior preserved to the digit), else the ratified
    constants (a fresh tenant, where the two are the same values). The floor
    column is the service's own legacy column (high_abs_kwh → kWh electric,
    high_abs_kgal → kgal water) — the same mapping `selectors._legacy_figures`
    draws and `validation._FLOOR_COLUMN_BY_UNIT` reads."""
    if legacy_row is None:
        return dict(RATIFIED_SERVICE_SEED[code])
    # ⚠ **THE LEGACY ROW HAS A FLOOR COLUMN FOR TWO SERVICES ONLY, AND
    # `RATIFIED_SERVICE_SEED` NOW CARRIES SEVEN (DEF-796).** BR-MET-120 (PO
    # 2026-08-26) ratified floors for gas, sewer, solar, thermal_heat and
    # battery; `read_validation_settings` has no column for any of them —
    # `high_abs_kwh` and `high_abs_kgal` are the only two that ever existed.
    # Indexing this map with a code outside it raised `KeyError: 'sewer'` and
    # took TENANT SEEDING DOWN with it (22 errors) for every tenant that HAS a
    # legacy row, which is every tenant provisioned before the per-service
    # table. The migration helper `_0031_helpers.backfill_tenant` already had
    # this branch; the runtime path did not, and nothing compared the two.
    # A service with no legacy column has nothing to preserve — its ratified
    # constants ARE its figures, which is the same answer the backfill gives.
    floor_by_service = {"electric": ("high_abs_kwh", "kWh"), "water": ("high_abs_kgal", "kgal")}
    if code not in floor_by_service:
        return dict(RATIFIED_SERVICE_SEED[code])
    column, unit = floor_by_service[code]
    return {
        "high_pct": legacy_row.high_pct,
        "high_abs_value": getattr(legacy_row, column),
        "high_abs_unit": unit,
        "low_pct": legacy_row.low_pct,
        "zero_scope": legacy_row.zero_scope,
        "days_flag_min": legacy_row.days_flag_min,
        "days_flag_max": legacy_row.days_flag_max,
        "days_hard_min": legacy_row.days_hard_min,
        "days_hard_max": legacy_row.days_hard_max,
        "mismatch_pct": legacy_row.mismatch_default_pct,
        "tou_sum_tolerance_pct": legacy_row.tou_sum_tolerance_pct,
    }


def ensure_read_validation_service_rows() -> int:
    """Seed the missing PO-ratified per-service rows for this tenant's ENABLED
    services (CR-038 A1). Returns how many rows were CREATED — 0 on a tenant
    already seeded, which is what lets the repair door say "already present"
    instead of claiming work it did not do (the DEF-153/7.2 failure shape)."""
    enabled = seams.enabled_service_codes()
    legacy_row = _read_config()
    created = 0
    for code in RATIFIED_SERVICE_SEED:
        if code not in enabled:
            continue
        service_id = seams.service_id_by_code(code)
        if service_id is None:
            continue  # catalog missing the code — nothing honest to seed
        _row, was_created = models.ReadValidationServiceSettings.objects.get_or_create(
            tenant_id=_tenant_id(),
            service_id=service_id,
            defaults=service_seed_figures(legacy_row, code),
        )
        created += 1 if was_created else 0
    return created


def seed_read_validation_settings(actor: Any = None) -> dict[str, Any]:
    """THE PROVISIONING SEAM tenancy resolves by name — **DEF-251**.

    `ensure_read_validation_settings` above has said *"Tenancy owns
    provisioning, so it calls this"* since it was written, and **nothing
    called it**: grepping the whole repository found two test files and no
    product caller, and the live database confirmed it with **zero rows for
    the only tenant on the system**. Hard-won law 1 exactly — *a comment
    claiming a guarantee is not the guarantee.*

    What the absence cost, and why no gate saw it: nothing crashes. Every
    threshold rule the read checker owns (high-usage, zero-usage,
    meter-mismatch) reports `not_evaluated: validation config missing` instead
    of running, estimation refuses by name, the bulk-import wizard draws a
    banner — and the single-read correction and supersede paths compute the
    same `not_evaluated` outcomes with **no summary line naming the missing
    configuration**. A clerk correcting one read saw no errors and no
    explanation that no rule had run.

    Two things this adds over the function it wraps, and both are why it is a
    separate entry point rather than a rename:

      1. it reports **whether it created anything**, so the repair door
         (`seed_demo --tenant <sub>`) can print *"already present"* instead of
         claiming work it did not do — the DEF-153/7.2 failure shape;
      2. it takes an `actor`, matching every other seam in
         `apps/tenancy/seams.py`, so the wiring is uniform. Nothing is audited
         here: the row carries the model's own ratified column defaults (B2 r5
         #15, closing OQ-002/OQ-003) and no money, no rate and no consumption
         moves.

    Idempotent, and it never overwrites: a tenant that has tuned its thresholds
    keeps them, because `get_or_create` only ever writes when the row is absent.

    CR-038 A1: the report now carries the per-service half too —
    `service_rows_created` counts the PO-ratified (electric/water) rows this
    call seeded for the tenant's enabled services; 0 means "already present".
    """
    existed = _read_config() is not None
    # Service rows FIRST so the created count is captured here — `ensure_…`
    # below repeats the call and finds nothing left to create (idempotent).
    service_rows_created = ensure_read_validation_service_rows()
    ensure_read_validation_settings()
    return {"created": not existed, "service_rows_created": service_rows_created}


# ── S64 writes (CR-038 A1: GET/PUT /settings/read-validation[/{service}]) ───

#: US-MET-011 §5's closed scope vocabulary — the ONE list the model comment,
#: the engine's `_zero_outcome` and the S64 select all mean.
ZERO_SCOPES: tuple[str, ...] = ("active_non_vacant", "all", "off")
#: CR-079 (PO 2026-09-07) — the SEVEN methods the settings screen offers, and
#: the subset the engine can run. Both come from `estimation`, which owns the
#: arithmetic: a list spelled here would disagree with the engine the first
#: time a method is added, and disagree silently.
#: ⚠ A PUT may store only a RUNNABLE method. `route_peer_average` and
#: `plan_average` are offered on screen (the PO ruled them in) and refused
#: here, because storing one would stop every estimate on the tenant —
#: `estimate()` returns `estimation_method_not_implemented` for both.
EST_METHODS: tuple[str, ...] = estimation.RUNNABLE_EST_METHODS
EST_METHODS_OFFERED: tuple[str, ...] = estimation.EST_METHODS

#: The per-service threshold fields a PUT may carry, in payload order.
_SERVICE_DECIMAL_FIELDS = (
    "high_pct",
    "high_abs_value",
    "low_pct",
    "mismatch_pct",
    "tou_sum_tolerance_pct",
)
_SERVICE_INT_FIELDS = ("days_flag_min", "days_flag_max", "days_hard_min", "days_hard_max")
#: BR-MET-136 (PO 2026-08-26): the per-rule ENABLED switch. **Deliberately NOT
#: in `_SERVICE_FIELDS`** — that tuple is the set a CREATE must supply in full,
#: because no ratified default exists for a threshold. The opposite is true
#: here: the default IS ratified ("you ahve to keep default - all enabled") and
#: it is the empty map, so requiring it on create would be requiring a client
#: to restate a default the column already holds — and a client that got it
#: wrong would be the "existing tenant silently acquires a disabled rule" state
#: clause 2 forbids.
_SERVICE_SWITCH_FIELD = "rule_enabled"
_SERVICE_FIELDS = (
    "high_pct",
    "high_abs_value",
    "high_abs_unit",
    "low_pct",
    "zero_scope",
    *_SERVICE_INT_FIELDS,
    "mismatch_pct",
    "tou_sum_tolerance_pct",
)


def _parse_setting_decimal(field: str, value: Any, fe: list[dict[str, Any]]) -> Any:
    """A canonical decimal from a client STRING (CLAUDE.md rule 2 — the client
    never sends a binary float; a JSON number that arrives anyway converts
    through its repr, exactly the settings-family posture). Quantized to the
    column's own 6dp at the DOOR (`_num6`), so sqlite and Postgres store and
    echo the same digits (the `_NUMERIC_18_6` discipline)."""
    try:
        return _num6(Decimal(repr(value) if isinstance(value, float) else str(value)))
    except (InvalidOperation, ValueError, TypeError):
        fe.append(_field_error(field, errors.VAL_FORMAT, "metering.read_validation.bad_number"))
        return None


def _parse_setting_int(field: str, value: Any, fe: list[dict[str, Any]]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        fe.append(_field_error(field, errors.VAL_FORMAT, "metering.read_validation.bad_number"))
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        fe.append(_field_error(field, errors.VAL_FORMAT, "metering.read_validation.bad_number"))
        return None


def _validate_service_figures(merged: dict[str, Any]) -> list[dict[str, Any]]:
    """The nonsense-refusal law for one service's WHOLE figure set — run on the
    merged document so a partial PUT cannot sneak an inconsistent window past
    the check. Mirrored (not copied — the server is the authority) by the S64
    form's own three structural checks."""
    fe: list[dict[str, Any]] = []
    if merged["high_pct"] is not None and merged["high_pct"] <= 0:
        fe.append(
            _field_error("high_pct", errors.VAL_RANGE, "metering.read_validation.pct_positive")
        )
    if merged["tou_sum_tolerance_pct"] is not None and merged["tou_sum_tolerance_pct"] <= 0:
        fe.append(
            _field_error(
                "tou_sum_tolerance_pct",
                errors.VAL_RANGE,
                "metering.read_validation.pct_positive",
            )
        )
    if merged["high_abs_value"] is not None and merged["high_abs_value"] < 0:
        fe.append(
            _field_error(
                "high_abs_value", errors.VAL_RANGE, "metering.read_validation.floor_negative"
            )
        )
    if merged["mismatch_pct"] is not None and merged["mismatch_pct"] < 0:
        fe.append(
            _field_error(
                "mismatch_pct", errors.VAL_RANGE, "metering.read_validation.floor_negative"
            )
        )
    if merged["low_pct"] is not None and not (0 < merged["low_pct"] <= 100):
        fe.append(
            _field_error("low_pct", errors.VAL_RANGE, "metering.read_validation.low_pct_range")
        )
    if merged["zero_scope"] not in ZERO_SCOPES:
        fe.append(
            _field_error(
                "zero_scope",
                errors.VAL_UNKNOWN_LOOKUP,
                "metering.read_validation.zero_scope_choice",
            )
        )
    if not merged["high_abs_unit"]:
        fe.append(
            _field_error(
                "high_abs_unit", errors.VAL_REQUIRED, "metering.read_validation.unit_required"
            )
        )
    days = {name: merged[name] for name in _SERVICE_INT_FIELDS}
    if any(v is not None and v < 1 for v in days.values()):
        first_bad = next(n for n, v in days.items() if v is not None and v < 1)
        fe.append(
            _field_error(first_bad, errors.VAL_RANGE, "metering.read_validation.days_min_one")
        )
        return fe  # window arithmetic over a nonsense bound would double-report
    if None in days.values():
        return fe
    flag_min, flag_max = days["days_flag_min"], days["days_flag_max"]
    hard_min, hard_max = days["days_hard_min"], days["days_hard_max"]
    if flag_min >= flag_max:
        fe.append(
            _field_error(
                "days_flag_max",
                errors.VAL_RANGE,
                "settings.read_validation.day_window_inverted",
                br="BR-MET-020",
                min=flag_min,
                max=flag_max,
            )
        )
    if hard_min >= hard_max:
        fe.append(
            _field_error(
                "days_hard_max",
                errors.VAL_RANGE,
                "settings.read_validation.day_window_inverted",
                br="BR-MET-020",
                min=hard_min,
                max=hard_max,
            )
        )
    # The HARD window must CONTAIN the flag window (US-MET-011 §5 "soft within
    # hard" — CR-038 A1 keeps the same law per service).
    if hard_min > flag_min or hard_max < flag_max:
        fe.append(
            _field_error(
                "days_flag_min",
                errors.VAL_RANGE,
                "settings.read_validation.soft_outside_hard",
                br="BR-MET-020",
                soft=[flag_min, flag_max],
                hard=[hard_min, hard_max],
            )
        )
    return fe


def _clean_rule_switches(raw: Any, fe: list[dict[str, Any]]) -> dict[str, bool] | None:
    """The BR-MET-136 switch map, validated at the DOOR — clause 4's refusal.

    Clause 4, verbatim: *"The INTEGRITY rules (unknown_meter, retired_meter,
    unit_missing, negative_usage, rollover, duplicate, export_not_net) are NOT
    switchable — they stay locked on S64."*

    **The refusal names the rule.** Silently dropping `{"duplicate": false}`
    from the payload would leave a System Admin looking at a screen that says
    the check is on, having just been told the save succeeded, believing they
    turned it off. That is the "built is not wired" shape (hard-won law 2)
    pointed at a setting: every check passes and the utility's intent
    evaporated. So the write is REFUSED, 422, with `duplicate` in the field
    error's params.

    An UNKNOWN rule name is refused for the same reason and it is the likelier
    slip: `{"hihg": false}` accepted-and-ignored is a tenant who believes the
    high-usage check is off for the next six months of billing.

    Only the keys the client SENDS are cleaned; the stored map is merged over
    in the caller, so a partial change set stays partial (the same posture the
    threshold fields take).
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        fe.append(
            _field_error(
                _SERVICE_SWITCH_FIELD,
                errors.VAL_FORMAT,
                "metering.read_validation.rule_switch_not_object",
            )
        )
        return None
    cleaned: dict[str, bool] = {}
    for rule, enabled in raw.items():
        if rule in validation.INTEGRITY_RULES:
            fe.append(
                _field_error(
                    _SERVICE_SWITCH_FIELD,
                    errors.VAL_RANGE,
                    "metering.read_validation.integrity_rule_locked",
                    br="BR-MET-136",
                    rule=rule,
                )
            )
            continue
        if rule not in validation.JUDGMENT_RULES:
            fe.append(
                _field_error(
                    _SERVICE_SWITCH_FIELD,
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.read_validation.unknown_rule",
                    br="BR-MET-136",
                    rule=rule,
                )
            )
            continue
        if not isinstance(enabled, bool):
            fe.append(
                _field_error(
                    _SERVICE_SWITCH_FIELD,
                    errors.VAL_FORMAT,
                    "metering.read_validation.rule_switch_not_boolean",
                    rule=rule,
                )
            )
            continue
        cleaned[rule] = enabled
    return cleaned


def _audit_rule_switches(
    actor: Any,
    row: Any,
    service_code: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    """ONE audit row for a rule switch — BR-MET-136's "and its audit row".

    A SEPARATE action from `settings.read_validation.service_updated`, and
    deliberately: *"who turned the vacant-unit check off, when, and for which
    service"* is the question this row exists to answer, and folding it into
    the thresholds row would make it a `grep` through every figure edit the
    tenant has ever made. Hard rule 7's spirit — every consequential act names
    itself.

    The blob states BOTH sides as `on`/`off` for **only the rules that moved**,
    expanded (`_switch_audit_state`), so a reader never has to know the
    absent-means-enabled convention to read the trail.
    """
    moved = sorted(set(before) | set(after))
    moved = [r for r in moved if before.get(r, True) != after.get(r, True)]
    _audit(
        actor,
        "settings.read_validation.rule_switched",
        "read_validation_service_settings",
        row.id,
        before={"service": service_code, **_switch_audit_state(before, moved)},
        after={"service": service_code, **_switch_audit_state(after, moved)},
    )


def _switch_audit_state(stored: dict[str, Any], rules: Iterable[str]) -> dict[str, str]:
    """`{rule: "on"|"off"}` for an audit blob — the map EXPANDED, so a reader
    of `audit_log` never has to know that an absent key means enabled."""
    return {rule: ("on" if stored.get(rule, True) else "off") for rule in rules}


@require_role(SYSTEM_ADMIN)
def save_read_validation_service(actor: Any, service_code: str, payload: Any) -> dict[str, Any]:
    """`PUT /settings/read-validation/{service}` — one enabled service's VEE
    thresholds, atomically, with ONE audit row naming field/old/new/actor
    (CR-038 A1; write role copied from `save_settings_family`: System Admin
    writes, the Executive's PUT dies here with 403 AUTH-002 — BR-SHL-025
    defense in depth behind the view's own class).

    UPDATE merges a partial change set over the stored row; CREATE (a service
    the seed never covered — the eight unratified ones) requires EVERY field,
    because there is no ratified figure to merge with and inventing one is the
    guess BR-MET-020 forbids. Event-time forward (BR-TEN-043): the new figures
    judge reads validated AFTER the save; every stored read keeps the
    `rule_outcomes` it was judged by (BR-MET-022/056 — asserted by test, not
    assumed)."""
    changes = _payload_dict(payload)
    fe: list[dict[str, Any]] = []
    for field in changes:
        if field not in _SERVICE_FIELDS and field != _SERVICE_SWITCH_FIELD:
            fe.append(_field_error(field, errors.VAL_FORMAT, "settings.unknown_field"))
    _refuse_fields(fe)
    if service_code not in seams.enabled_service_codes():
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.service_not_enabled",
            field_errors=[
                _field_error("service", errors.VAL_UNKNOWN_LOOKUP, "metering.service_not_enabled")
            ],
        )

    cleaned: dict[str, Any] = {}
    for field in _SERVICE_DECIMAL_FIELDS:
        if field in changes:
            cleaned[field] = _parse_setting_decimal(field, changes[field], fe)
    for field in _SERVICE_INT_FIELDS:
        if field in changes:
            cleaned[field] = _parse_setting_int(field, changes[field], fe)
    if "zero_scope" in changes:
        cleaned["zero_scope"] = _text(changes["zero_scope"], 40)
    if "high_abs_unit" in changes:
        cleaned["high_abs_unit"] = _text(changes["high_abs_unit"], 20)
    # BR-MET-136: the switch map is cleaned in the SAME pass as the figures, so
    # one save either lands whole or refuses whole — a partial write that took
    # the thresholds and dropped an integrity-rule refusal would leave the row
    # and the audit trail disagreeing about what the admin asked for.
    switch_changes = (
        _clean_rule_switches(changes[_SERVICE_SWITCH_FIELD], fe)
        if _SERVICE_SWITCH_FIELD in changes
        else None
    )
    _refuse_fields(fe)

    with transaction.atomic():
        row = (
            models.ReadValidationServiceSettings.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), service__code=service_code)
            .select_related("service")
            .first()
        )
        if row is None:
            missing = [f for f in _SERVICE_FIELDS if f not in cleaned]
            if missing:
                _refuse_fields(
                    [
                        _field_error(
                            f, errors.VAL_REQUIRED, "metering.read_validation.create_incomplete"
                        )
                        for f in missing
                    ]
                )
            merged = dict(cleaned)
            _refuse_fields(_validate_service_figures(merged))
            service_id = seams.service_id_by_code(service_code)
            # BR-MET-136 clause 2 at PROVISIONING: a brand-new row starts from
            # the empty map — ALL ENABLED — and only what the admin explicitly
            # switched off is written over it.
            switches_after = dict(switch_changes or {})
            row = models.ReadValidationServiceSettings.objects.create(
                tenant_id=_tenant_id(),
                service_id=service_id,
                **{_SERVICE_SWITCH_FIELD: switches_after},
                **merged,
            )
            _audit(
                actor,
                "settings.read_validation.service_updated",
                "read_validation_service_settings",
                row.id,
                before={"service": service_code, "configured": False},
                after={
                    "service": service_code,
                    **{f: _figure_str(merged[f]) for f in _SERVICE_FIELDS},
                },
            )
            if switch_changes:
                _audit_rule_switches(actor, row, service_code, {}, switches_after)
        else:
            before = {f: getattr(row, f) for f in _SERVICE_FIELDS}
            merged = {**before, **cleaned}
            _refuse_fields(_validate_service_figures(merged))
            changed = sorted(f for f in _SERVICE_FIELDS if merged[f] != before[f])
            # BR-MET-136: the switch map is MERGED, never replaced — a save
            # that names one rule must not silently re-enable the other twelve.
            switches_before = dict(getattr(row, _SERVICE_SWITCH_FIELD, None) or {})
            switches_after = {**switches_before, **(switch_changes or {})}
            switches_moved = switches_after != switches_before
            if not changed and not switches_moved:
                return selectors.read_validation_service_dict(row)  # no-op: no write, no audit
            for f in changed:
                setattr(row, f, merged[f])
            if switches_moved:
                setattr(row, _SERVICE_SWITCH_FIELD, switches_after)
            row.save(
                update_fields=[
                    *changed,
                    *([_SERVICE_SWITCH_FIELD] if switches_moved else []),
                    "updated_at",
                ]
            )
            if changed:
                _audit(
                    actor,
                    "settings.read_validation.service_updated",
                    "read_validation_service_settings",
                    row.id,
                    before={
                        "service": service_code,
                        **{f: _figure_str(before[f]) for f in changed},
                    },
                    after={
                        "service": service_code,
                        **{f: _figure_str(merged[f]) for f in changed},
                    },
                )
            if switches_moved:
                _audit_rule_switches(actor, row, service_code, switches_before, switches_after)
    return selectors.read_validation_service_dict(row)


_GENERAL_FIELDS = ("est_method", "est_max_consecutive")


@require_role(SYSTEM_ADMIN)
def save_read_validation_general(actor: Any, payload: Any) -> dict[str, Any]:
    """`PUT /settings/read-validation` — the TENANT-WIDE estimation panel
    (est_method/est_max_consecutive stayed on the legacy row by CR-038 A1's own
    scope). Same write law as the per-service save: System Admin, atomic, one
    audit row naming field/old/new/actor, no-op saves write nothing."""
    changes = _payload_dict(payload)
    fe: list[dict[str, Any]] = []
    for field in changes:
        if field not in _GENERAL_FIELDS:
            fe.append(_field_error(field, errors.VAL_FORMAT, "settings.unknown_field"))
    _refuse_fields(fe)
    cleaned: dict[str, Any] = {}
    if "est_method" in changes:
        method = _text(changes["est_method"], 60)
        if method not in EST_METHODS:
            fe.append(
                _field_error(
                    "est_method",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.read_validation.est_method_choice",
                )
            )
        cleaned["est_method"] = method
    if "est_max_consecutive" in changes:
        cap = _parse_setting_int("est_max_consecutive", changes["est_max_consecutive"], fe)
        if cap is not None and cap < 1:
            fe.append(
                _field_error(
                    "est_max_consecutive",
                    errors.VAL_RANGE,
                    "metering.read_validation.est_max_min_one",
                )
            )
        cleaned["est_max_consecutive"] = cap
    _refuse_fields(fe)

    with transaction.atomic():
        row = (
            models.ReadValidationSettings.objects.select_for_update()
            .filter(tenant_id=_tenant_id())
            .first()
        )
        if row is None:
            # A tenant provisioned before DEF-251's fix may lack the row; the
            # save materialises it with its ratified column defaults first.
            row = models.ReadValidationSettings.objects.create(tenant_id=_tenant_id())
        before = {f: getattr(row, f) for f in _GENERAL_FIELDS}
        merged = {**before, **cleaned}
        changed = sorted(f for f in _GENERAL_FIELDS if merged[f] != before[f])
        if changed:
            for f in changed:
                setattr(row, f, merged[f])
            row.save(update_fields=[*changed, "updated_at"])
            _audit(
                actor,
                "settings.read_validation.updated",
                "read_validation_settings",
                row.id,
                before={f: before[f] for f in changed},
                after={f: merged[f] for f in changed},
            )
    return {f: getattr(row, f) for f in _GENERAL_FIELDS}


def _figure_str(value: Any) -> Any:
    """Decimals into canonical 6dp strings for audit blobs and payloads — the
    settings-family posture (never a binary float; STORED scale on the wire,
    the 2dp of CLAUDE.md rule 2 is DISPLAY and belongs to the screen)."""
    return str(_num6(value)) if isinstance(value, Decimal) else value


# ── context assembly (the ORM half of validation.ReadContext) ───────────────


def _head_qs():
    """Committed LINEAGE HEADS only. Every consumer — S25, billing pickup,
    completeness, estimation history — resolves the head (BR-MET-016/053), so
    a superseded chain counts exactly once.

    ⚠ **AND ONLY THE READING THAT COUNTS — BR-MET-1189 (PO 2026-10-04,
    DEF-WRK-9642).** Where one register holds two readings on one date, the
    prior a new reading is measured from, the estimation history and the
    true-up's standing estimates all see the highest approved and validated
    one (`counted_reading.only_counted`) — so 5 November's 3,500 kWh on
    E-5000 is measured from the technician's 3,412, never the office's 3,400.
    """
    return counted_reading.only_counted(
        models.MeterRead.objects.filter(tenant_id=_tenant_id(), superseded_by_id__isnull=True)
    )


def _prior_actual_head(asset_id: Any, channel: str, before: Any) -> Any:
    """The latest ACTUAL head on this (meter, channel) lineage before `before`.

    Actual = carries a register value. An estimate deliberately has no
    `current_value` (BR-MET-028), so it can never become the register baseline
    a delta is measured from — which is precisely what makes BR-MET-029's
    true-up arithmetic work.

    🔒 HUMAN-REVIEW-PENDING — FB-022 (PO 2026-10-31, R1): a reading AWAITING
    A CLERK (`selectors.AWAITING_REVIEW_READ_STATUSES` — lower than the last,
    stored with its flag) is not a baseline either, until a clerk corrects it:
    4,812 → 4,790 (flagged) → 4,900 measures 88 kWh from 4,812, never 110 from
    4,790. Before 2026-10-31 such a reading was refused and never stored, so
    nothing measured from one.
    """
    return (
        _head_qs()
        .filter(
            asset_id=asset_id,
            channel=channel,
            read_at__lt=before,
            current_value__isnull=False,
        )
        .exclude(status__in=sorted(selectors.AWAITING_REVIEW_READ_STATUSES))
        .order_by("-read_at")
        .first()
    )


def _same_key_heads(asset_id: Any, read_at: Any, channel: str, value: Any) -> tuple[Any, Any]:
    """`(counted head, head with this same value)` at one (meter, date,
    register) — BR-MET-1189. The first is the reading that counts there (None
    when the key is empty); the second is any head, counted or not, already
    holding exactly `value` (None when none does), which is the SAME reading
    arriving again rather than a second one."""
    head = _head_qs().filter(asset_id=asset_id, read_at=read_at, channel=channel).first()
    if head is None:
        return None, None
    same_value = None
    if value is not None:
        same_value = (
            models.MeterRead.objects.filter(
                tenant_id=_tenant_id(),
                asset_id=asset_id,
                read_at=read_at,
                channel=channel,
                superseded_by_id__isnull=True,
                current_value=value,
            )
            .order_by("-id")
            .first()
        )
    return head, same_value


#: "The caller did not say" — distinct from `None`, which is a real answer for a
#: prior head ("this meter has never been read"). DEF-MET-8107.
_NOT_GIVEN: Any = object()


def _standing_estimates(
    asset_id: Any, channel: str, before: Any, *, last_actual: Any = _NOT_GIVEN
) -> list[Any]:
    """Estimated heads on this lineage since the last actual — the set
    BR-MET-029 subtracts and BR-MET-027 counts. Oldest first.

    `last_actual` lets a caller that has ALREADY looked up the prior actual
    head pass it in rather than ask the same question twice (DEF-MET-8107:
    the post asked it three times per reading)."""
    if last_actual is _NOT_GIVEN:
        last_actual = _prior_actual_head(asset_id, channel, before)
    qs = _head_qs().filter(
        asset_id=asset_id, channel=channel, read_at__lt=before, status="estimated"
    )
    if last_actual is not None:
        qs = qs.filter(read_at__gt=last_actual.read_at)
    return list(qs.order_by("read_at"))


def _trailing_actuals(asset_id: Any, channel: str, before: Any, limit: int = 12) -> list:
    """`[(consumption, days), …]` newest first, ACTUAL reads only.

    OQ-002's flag basis is the trailing-12-month average (trailing-3 when
    history is short) and BR-MET-026's estimation basis is the trailing 3 —
    both read the same actual-only history, so it is gathered once here and
    each caller takes the window its rule names.
    """
    rows = (
        _head_qs()
        .filter(
            asset_id=asset_id,
            channel=channel,
            read_at__lt=before,
            current_value__isnull=False,
            consumption__isnull=False,
        )
        .order_by("-read_at")[:limit]
    )
    return [(row.consumption, row.days_since_prior or 0) for row in rows]


def _asset_is_retired(asset: Any, on_day: date | None) -> date | None:
    """The retirement date when this read lands on a retired meter, else None
    (BR-MET-052 error). Retirement is either the explicit `retire_date` or the
    lifecycle stage's terminal behaviour class (BR-AST-031)."""
    retire_date = getattr(asset, "retire_date", None)
    if retire_date is not None and (on_day is None or retire_date <= on_day):
        return retire_date
    status = getattr(asset, "status", None)
    if status is not None and getattr(status, "behavior_class", None) == "terminal":
        return retire_date or getattr(asset, "updated_at", None) and asset.updated_at.date()
    return None


def _unit_occupied(asset: Any) -> bool | None:
    """BR-MET-036 derived occupancy for the read's unit, or None when the
    customers seam cannot answer. None is REPORTED by the engine — declaring
    every unit vacant because a neighbour lane is quiet would flag every read
    in the system."""
    service_point = getattr(asset, "service_point", None)
    unit_id = getattr(service_point, "unit_id", None)
    if unit_id is None:
        return None
    return seams.unit_is_occupied(unit_id)


def _uom_conversion(service_code: str | None) -> tuple[str | None, Any]:
    """`(billed_uom, conversion_factor)` for the service (OQ-004 closure). Both
    None means the absolute floor cannot be expressed in the register's unit,
    and the high rule reports instead of half-firing."""
    if not service_code:
        return None, None
    return seams.service_billed_uom(service_code)


def _service_of_asset(asset: Any) -> str | None:
    service_point = getattr(asset, "service_point", None)
    service = getattr(service_point, "service", None)
    return getattr(service, "code", None)


def _meter_cycle_code(meter_cycle_id: Any, cycle: Any, cycle_codes: dict[Any, str | None]) -> Any:
    """The CODE of the meter's own cycle, for BR-MET-122's named message
    ("M-4021 belongs to CY-002"). One lookup per DISTINCT off-cycle cycle per
    batch — `cycle_codes` is a memo the caller shares across rows (the DEF-324
    one-read-per-thing discipline), and the batch's own tagged cycle never
    queries at all."""
    if meter_cycle_id is None:
        return None
    if cycle is not None and meter_cycle_id == cycle.id:
        return cycle.code
    if meter_cycle_id not in cycle_codes:
        cycle_codes[meter_cycle_id] = (
            models.Cycle.objects.filter(tenant_id=_tenant_id(), pk=meter_cycle_id)
            .values_list("code", flat=True)
            .first()
        )
    return cycle_codes[meter_cycle_id]


class _BatchLookups:
    """The answers a read batch asks for OVER AND OVER, asked once — DEF-MET-8107.

    Posting 480 readings issued about 52 SQL statements per reading, and most of
    them were the SAME question asked again: the service's billed unit (three
    statements, identical for every electric row), the unit's plan and pricing
    unit (five, identical for every unit on one plan), who occupies the unit
    (two, and asked twice per reading — once for the vacant-unit rule and once
    to stamp the account). The PO's fix (B), ruled 2026-09-30: *"cut the ~52
    database calls per reading by doing validation work once per batch"*.

    ⚠ **A CACHE OF ANSWERS THAT CANNOT CHANGE DURING THE BATCH, AND NOTHING
    ELSE.** A service's billed unit, a plan's registers and pricing unit, and a
    unit's occupying account are not written by a read post; the rows are
    judged inside one transaction, so a value fetched for row 1 is the value
    row 480 would have fetched. What is deliberately NOT cached is anything the
    batch itself changes as it goes — a meter's prior reading and its lineage
    head — because a file carrying two readings for one meter must see the
    first one when it judges the second.

    One instance per batch pass (validate, or post), never shared between them
    and never kept past the call: a cache outliving its transaction would be a
    stale answer with no one to notice.
    """

    def __init__(self) -> None:
        # BR-MET-049 + BR-MET-1160: one resolver for the whole batch (DEF-324).
        self.pricing_resolver = completeness.PlanRegisterResolver()
        self._uom: dict[str | None, tuple[str | None, Any]] = {}
        self._occupant: dict[str, dict[str, Any] | None] = {}

    def uom_conversion(self, service_code: str | None) -> tuple[str | None, Any]:
        if service_code not in self._uom:
            self._uom[service_code] = _uom_conversion(service_code)
        return self._uom[service_code]

    def prime_occupants(self, unit_ids: Any) -> None:
        """One read for every unit in the batch — `seams.accounts_for_units`
        answers the identical question `active_account_for_unit` does, for a
        list (its own docstring: *"it answers the identical question"*).
        Skipped when customers publishes no batched read, so the single-unit
        path below still answers exactly as it did."""
        wanted = [str(u) for u in unit_ids if u and str(u) not in self._occupant]
        if not wanted:
            return
        if seams.resolve("customers", "accounts_for_units", kind="selectors") is None:
            return
        found = seams.accounts_for_units(wanted)
        for unit_id in wanted:
            self._occupant[unit_id] = found.get(unit_id)

    def occupant(self, unit_id: Any) -> dict[str, Any] | None:
        key = str(unit_id)
        if key not in self._occupant:
            self._occupant[key] = seams.active_account_for_unit(unit_id)
        return self._occupant[key]

    def unit_occupied(self, asset: Any) -> bool | None:
        """`_unit_occupied`, answered from the batch's occupant map. None when
        customers cannot answer — the same three-valued answer the seam gives."""
        unit_id = getattr(getattr(asset, "service_point", None), "unit_id", None)
        if unit_id is None:
            return None
        if seams.resolve("customers", "active_account_for_unit") is None:
            return None
        return self.occupant(unit_id) is not None


def _build_context(
    *,
    asset: Any,
    read_at: Any,
    channel: str,
    value: Any,
    config: Any,
    cycle: Any = None,
    duplicate_of_read_id: str | None = None,
    duplicate_of_row_no: int | None = None,
    same_cycle_unchanged_read_id: str | None = None,
    same_day_sibling_read_id: str | None = None,
    stated_service: str | None = None,
    enabled_services: tuple[str, ...] | None = None,
    cycle_codes: dict[Any, str | None] | None = None,
    # CR-054 W1 task 7 — the row's own two facts, from the staged row.
    row_key: str | None = None,
    row_no: int | None = None,
    meter_no_raw: str | None = None,
    # BR-MET-1160 (PO 2026-09-02) — a SHARED `PlanRegisterResolver` so a
    # 500-row batch asks rating once per (plan, service, date) rather than
    # once per row (the DEF-324 discipline). A single-read caller passes none
    # and gets a private one, which costs exactly one hop.
    pricing_resolver: Any = None,
    # DEF-MET-8107 — the batch's shared answers (`_BatchLookups`), and the
    # prior actual head when the caller already holds it. Both optional: a
    # single-read caller passes neither and behaves exactly as before.
    lookups: _BatchLookups | None = None,
    prior: Any = _NOT_GIVEN,
) -> validation.ReadContext:
    """Gather one row's whole world. Every input is fetched explicitly — there
    is no lazy branch here that could silently supply a default.

    CR-038 W2 (2026-08-26): also resolves the mixed-cycle facts — the meter's
    own cycle via the BR-MET-033 stamp (`service_points.cycle_id`, the chain
    `completeness._expected_meters` walks) for BR-MET-122, and the row's
    BR-MET-014 effective service for the service-coherence rule."""
    if asset is None:
        return validation.ReadContext(
            value=value,
            read_at=read_at,
            channel=channel,
            asset_known=False,
            duplicate_of_read_id=duplicate_of_read_id,
            duplicate_of_row_no=duplicate_of_row_no,
            stated_service=stated_service,
            enabled_services=enabled_services,
            # CR-054 W1 task 7. `meter_no` used to be left None here because
            # only BR-MET-122 read it and that rule never runs on this path.
            # The row-key rule DOES run here, and this is the path where it is
            # most useful: `unknown_meter` can say "M-4099 is not a meter", and
            # only the key can add "…and this row was written for M-4021".
            meter_no=meter_no_raw,
            row_key=row_key,
            row_no=row_no,
        )
    if prior is _NOT_GIVEN:
        prior = _prior_actual_head(asset.id, channel, read_at) if read_at is not None else None
    service_code = _service_of_asset(asset)
    billed_uom, factor = (
        lookups.uom_conversion(service_code)
        if lookups is not None
        else _uom_conversion(service_code)
    )
    if lookups is not None and pricing_resolver is None:
        pricing_resolver = lookups.pricing_resolver
    # ── BR-MET-1160 (PO 2026-09-02) — WHAT UNIT WILL PRICE THIS READING ─────
    # PO verbatim: *"refula at the time of billing - it will be too late to act
    # , we have to ensure wehn we upload reading at that time it is check and
    # corrected"*. The answer is the RATE SCHEDULE's own `uom`, resolved on the
    # READ's date (BR-RAT-007 — the version in force, with no fallback to
    # today's prices), and it is resolved HERE rather than in the rule because
    # `validation` touches no ORM and no seam by design.
    #
    # A read with no date cannot ask "which version was in force" honestly, so
    # the absence is REPORTED rather than resolved against today — the rule
    # reports `no_version_in_force` shaped as a stated gap, never a match.
    pricing = None
    if read_at is not None:
        resolver = pricing_resolver or completeness.PlanRegisterResolver()
        pricing = resolver.pricing_unit_for_asset(asset, service_date=read_at.date())
    # BR-MET-122: membership is the service point's cycle stamp (BR-MET-033).
    meter_cycle_id = getattr(getattr(asset, "service_point", None), "cycle_id", None)
    return validation.ReadContext(
        value=value,
        read_at=read_at,
        channel=channel,
        # ── BR-MET-143 (PO 2026-08-27, closing OQ-391): THE UNIT IS THE
        # REGISTER'S, NOT THE METER'S ────────────────────────────────────────
        # PO verbatim: *"A demand reading carries kW - we have to match utility
        # service unit and meter reading unit"*. This line read `asset.unit` for
        # every channel until 2026-08-27, so a peak on an electric meter was
        # stored **kWh** while `rate_schedules.demand_rate_per_kw` priced it per
        # **kW** — the label half of DEF-797, printed on an issued document.
        # One meter now holds kWh on its energy register and kW on its demand
        # register, which is OQ-391 option (a) in one call.
        #
        # `register_unit` returns None where no demand unit is DECLARED for the
        # meter's own UoM (a tenant metering in kVA, say). That None is not a
        # gap to paper over: it falls straight into `_identity_outcomes`'
        # `unit_missing` ERROR, which refuses the row by name and sends the
        # clerk to the meter's UoM. CLAUDE.md rule 3 has no assume branch, and
        # a plausible unit on an issued bill is worse than a refused row.
        unit=register_units.register_unit(asset.unit, channel),
        multiplier=asset.multiplier,
        register_digits=asset.register_digits,
        asset_known=True,
        asset_retired_on=_asset_is_retired(asset, read_at.date() if read_at else None),
        prior_value=prior.current_value if prior else None,
        prior_read_at=prior.read_at if prior else None,
        trailing_actuals=(
            _trailing_actuals(asset.id, channel, read_at) if read_at is not None else []
        ),
        duplicate_of_read_id=duplicate_of_read_id,
        duplicate_of_row_no=duplicate_of_row_no,
        same_cycle_unchanged_read_id=same_cycle_unchanged_read_id,
        same_day_sibling_read_id=same_day_sibling_read_id,
        unit_occupied=(
            lookups.unit_occupied(asset) if lookups is not None else _unit_occupied(asset)
        ),
        # BR-AST-029: the flag that decides whether an export record is lawful.
        asset_net_metering=bool(getattr(asset, "net_metering", False)),
        # CR-038 W6 (BR-MET-124/135): meter or DEVICE. `asset_types.category`
        # (BR-AST-004's tab key) is the one fact that separates them, and it
        # decides which half of the catalog can honestly judge this row.
        asset_category=seams.asset_type_category(asset),
        # W5-T2 — the cycle's window is DERIVED in the READ's own month, not
        # read off two dropped columns. `derive_read_window` is documented for
        # exactly this ("placed in `anchor`'s month … a RENDERING choice for a
        # month already picked"); it is NOT the generate-occurrences path OQ-339
        # blocks, because no month is being chosen here — it arrives with the
        # read.
        cycle_window_start=(_cycle_window_for(cycle, read_at) or (None, None))[0],
        cycle_window_end=(_cycle_window_for(cycle, read_at) or (None, None))[1],
        billed_unit=billed_uom,
        conversion_factor=factor,
        # BR-MET-1160: the schedule's own unit, and WHY it is absent when it is.
        pricing_unit=getattr(pricing, "unit", None),
        pricing_unit_absent_reason=(
            getattr(pricing, "absent_reason", None)
            if pricing is not None
            else completeness.REGISTERS_ABSENT_NO_VERSION
        ),
        pricing_plan_id=getattr(pricing, "plan_id", None),
        # ⚠ **STILL None, AND NOW HONESTLY SO — DEF-791.** This line used to
        # carry the comment *"BR-MET-025 runs on the committed group, below"*
        # and there WAS no group loop, below or anywhere: the mismatch rule, its
        # config column and its unit tests all existed while no live input ever
        # reached it. Σ subs is a fact about OTHER assets' reads and a row's
        # context is assembled from ONE asset's world, so it cannot be resolved
        # here — the group loop at the end of `validate_read_batch` resolves it
        # (CR-038 W6, `submeter_reconciliation.resolve_submeter_sum`), and
        # `validation._mismatch_outcome` documents the adapter.
        submeter_consumption_sum=None,
        loss_tolerance_pct=getattr(asset, "loss_tolerance_pct", None),
        # CR-038 A1: the service whose thresholds judge this read.
        service_code=service_code,
        # CR-038 W2 (2026-08-26): the mixed-cycle facts.
        meter_no=getattr(asset, "asset_no", None),
        batch_cycle_id=str(cycle.id) if cycle is not None else None,
        batch_cycle_code=getattr(cycle, "code", None),
        meter_cycle_id=str(meter_cycle_id) if meter_cycle_id is not None else None,
        meter_cycle_code=_meter_cycle_code(meter_cycle_id, cycle, cycle_codes or {}),
        stated_service=stated_service,
        enabled_services=enabled_services,
        # CR-054 W1 task 7 — the reading sheet's row key and the row's number,
        # for the named message ("row 412 was M-4021, now M-4099").
        row_key=row_key,
        row_no=row_no,
    )


# ── US-MET-007: stage a batch (steps 1–2) ───────────────────────────────────


def read_method_index() -> dict[str, str]:
    """The tenant's `read_methods` vocabulary, folded name/code -> code.

    BR-MET-123 (PO 2026-08-26) makes the read SOURCE a TAG chosen at upload,
    and BR-AST-043 already owns the words it is chosen from - AMI, AMR,
    walk-by, Manual, Mobile, and since BR-MET-142 (2026-08-27) Drive-by,
    Self-read and Field visit - as a TENANT-EXTENSIBLE reference list on the
    meter side. So this lane mints no vocabulary of its own: it asks assets,
    through the documented seam, for the list the tenant is already editing on
    the S8 reference-data card.

    ONE index per call site, never one lookup per row (the DEF-324 posture the
    assets importer already keeps).

    An UNWIRED assets module answers {} and every named method then reports
    unknown. That is the honest failure and it is deliberate: a fallback tuple
    here would be the hardcoded copy BR-AST-043 deleted, and it would silently
    accept a word the tenant had retired.
    """
    return seams.assets_lookup_index(models.READ_METHOD_LIST_CODE)


def _resolve_read_method(raw: Any, index: dict[str, str]) -> tuple[str | None, bool]:
    """`(value, known)` for one written method.

    Returns the value FOLDED but never CORRECTED (BR-MET-032 validate-then-
    accept): an unrecognised word comes back with `known=False` and its own
    spelling intact, so the row can be flagged by name instead of quietly
    becoming something else.
    """
    folded = read_import.normalize_read_method(raw)
    if folded is None:
        return None, True  # stating no method is lawful - the tag is optional
    resolved = index.get(folded) or index.get(str(raw).strip().lower())
    if resolved is not None:
        return resolved, True
    return folded, False


def _validate_batch_tags(data: dict[str, Any]) -> dict[str, Any]:
    """Step-1 tags (BR-MET-014). Cycle/route must exist in THIS tenant; the
    service tag must be one the tenant has enabled (BR-MET-003); the read
    method must be one of the tenant's own `read_methods` (BR-MET-123)."""
    fe: list[dict[str, Any]] = []
    cleaned: dict[str, Any] = {}

    source_kind = _text(data.get("source_kind"), 40) or "csv"
    if source_kind not in models.SOURCE_KINDS:
        fe.append(_field_error("source_kind", errors.VAL_FORMAT, "metering.read_batch.source_kind"))
    if source_kind == "ami_replay":
        # US-MET-007 §5: the card renders DISABLED until the B7 head-end seam
        # exists. Accepting it here would promise a replay nothing can perform.
        fe.append(
            _field_error(
                "source_kind", errors.VAL_FORMAT, "metering.read_batch.ami_replay_disabled"
            )
        )
    cleaned["source_kind"] = source_kind

    detail = _text(data.get("source_detail"), 40)
    if detail is not None and detail not in models.SOURCE_DETAILS:
        fe.append(
            _field_error("source_detail", errors.VAL_FORMAT, "metering.read_batch.source_detail")
        )
    cleaned["source_detail"] = detail

    # BR-MET-123 - THE SOURCE TAG. Verbatim (PO 2026-08-26): *"there is no
    # integration yet; but it should not stop us from tagging the soruce and
    # accepting the CSV or excel file"*. So this tag is judged INDEPENDENTLY of
    # `source_kind` above: a file collected by AMI is tagged `ami` and uploaded
    # as a file, and the refusal a line up (`ami_replay`) is about the
    # TRANSPORT and must never reach across to the tag.
    method_index = read_method_index()
    method, method_known = _resolve_read_method(data.get("read_method"), method_index)
    if not method_known:
        # Named back with the tenant's OWN active set, exactly as the meter
        # side refuses an unknown read method - the allowed values are data.
        fe.append(
            _field_error(
                "read_method",
                errors.VAL_UNKNOWN_LOOKUP,
                "metering.read_batch.read_method_unknown",
                value=method,
                allowed=sorted(set(method_index.values())),
            )
        )
    cleaned["read_method"] = method if method_known else None
    cleaned["read_method_index"] = method_index

    # ── CR-038 W7 task 3 / R2 — THE WRITE MODE, THE STAGE-1 PREMISE ─────────
    # PO 2026-08-26, verbatim: *"we need insert, insert update, repalce option
    # in step 1 of wirzard"*. Refused BY NAME with the three allowed values
    # rather than silently defaulted: a payload that said `upserts` meant to
    # correct readings already on file, and quietly giving it `insert` would
    # turn every one of those rows into an error the clerk never asked for.
    mode = write_modes.normalize(data.get("write_mode"))
    if mode is None:
        fe.append(
            _field_error(
                "write_mode",
                errors.VAL_FORMAT,
                "metering.read_batch.write_mode_unknown",
                value=_text(data.get("write_mode"), 40),
                allowed=list(write_modes.READ_WRITE_MODES),
            )
        )
    cleaned["write_mode"] = mode or write_modes.DEFAULT_READ_WRITE_MODE

    period_month = data.get("period_month")
    if not period_month:
        fe.append(_field_error("period_month", errors.VAL_REQUIRED, "metering.read_batch.period"))
        cleaned["period_month"] = None
    else:
        parsed = read_import._parse_date(str(period_month))
        if parsed is None:
            fe.append(_field_error("period_month", errors.VAL_FORMAT, "metering.read_batch.period"))
            cleaned["period_month"] = None
        else:
            cleaned["period_month"] = parsed.date().replace(day=1)

    cycle = None
    if data.get("cycle_id"):
        cycle = models.Cycle.objects.filter(
            tenant_id=_tenant_id(), pk=data["cycle_id"], deleted_at__isnull=True
        ).first()
        if cycle is None:
            fe.append(_field_error("cycle_id", errors.VAL_UNKNOWN_LOOKUP, "metering.cycle.unknown"))
    cleaned["cycle"] = cycle

    route = None
    if data.get("route_id"):
        route = models.Route.objects.filter(
            tenant_id=_tenant_id(), pk=data["route_id"], deleted_at__isnull=True
        ).first()
        if route is None:
            fe.append(_field_error("route_id", errors.VAL_UNKNOWN_LOOKUP, "metering.route.unknown"))
    cleaned["route"] = route

    service = _text(data.get("service"), 40)
    if service is not None and service not in seams.enabled_service_codes():
        fe.append(
            _field_error("service", errors.VAL_UNKNOWN_LOOKUP, "metering.service_not_enabled")
        )
    cleaned["service"] = service

    _refuse_fields(fe)
    return cleaned


def _file_bytes(data: dict[str, Any]) -> bytes | None:
    """The uploaded file as bytes. Accepts raw text or base64 — the hash is
    computed from the DECODED bytes either way, so the same file always
    produces the same idempotency key regardless of transport."""
    if data.get("file_base64"):
        import base64

        try:
            return base64.b64decode(str(data["file_base64"]), validate=True)
        except Exception:
            _refuse_fields(
                [_field_error("file_base64", errors.VAL_FORMAT, "metering.read_batch.file_base64")]
            )
    if data.get("file_content") is not None:
        return str(data["file_content"]).encode("utf-8")
    return None


#: CR-161-BRC10 W4 — the record type and the one screen that types a
#: reading's own fields (`apps/tenancy/custom_fields.SLOTS`). The S28 upload is
#: a door that is NOT a screen: nothing is required of a file (W1's rule), and
#: a refused cell is a row error rather than a refused file.
READ_CUSTOM_ENTITY = "meter_reads"
READ_ENTRY_SCREEN = "READ_ENTRY"
ERR_CUSTOM_FIELD = "custom_field_invalid"


def _read_custom_answers(
    parsed_rows: list[Any], *, from_file: bool
) -> dict[int, tuple[dict[str, Any], list[dict[str, Any]]]]:
    """row_no → (the cleaned answers to stage, the parse errors they raise).

    The ONE validator is tenancy's, reached through `seams.validate_custom_data`.
    A MANUAL entry that sent `custom_data` is the quick-read form (`READ_ENTRY`),
    so a required field binds and a refusal raises keyed `custom_data.<key>`
    exactly as every other form's does (BR-SHL-037). A FILE row is judged with
    `screen=None` and a refusal becomes that row's error, naming the field.
    """
    out: dict[int, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    for parsed in parsed_rows:
        if not parsed.custom and not parsed.custom_sent:
            out[parsed.row_no] = ({}, [])
            continue
        if not from_file:
            out[parsed.row_no] = (
                seams.validate_custom_data(
                    READ_CUSTOM_ENTITY,
                    parsed.custom,
                    screen=READ_ENTRY_SCREEN if parsed.custom_sent else None,
                ),
                [],
            )
            continue
        try:
            cleaned = seams.validate_custom_data(READ_CUSTOM_ENTITY, parsed.custom, screen=None)
        except errors.ValidationError as exc:
            fields = [
                str(item.get("field", "")).removeprefix("custom_data.")
                for item in (getattr(exc, "field_errors", None) or [])
            ]
            out[parsed.row_no] = (
                {},
                [{"code": ERR_CUSTOM_FIELD, "field": "custom_data", "value": ", ".join(fields)}],
            )
            continue
        out[parsed.row_no] = (cleaned, [])
    return out


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def stage_read_batch(actor: Any, payload: Any) -> dict[str, Any]:
    """S28 steps 1–2 — create the STAGED batch and its rows. Nothing posts here
    (BR-MET-012): no `meter_reads` row exists until commit, and an abandoned
    batch never appears in Reads.

    Every parsed row is staged, including the ones that failed to parse — their
    errors ride along as rule outcomes (BR-MET-032 validate-then-accept). A row
    that entered the file always appears in the outcome report.
    """
    data = _payload_dict(payload)
    tags = _validate_batch_tags(data)
    payload_bytes = _file_bytes(data)
    manual_entries = data.get("rows")

    mapping: dict[str, Any] = {}
    # CR-161-BRC10 W4 — the utility's own reading fields, read ONCE per batch.
    custom_fields = seams.custom_field_import_columns(READ_CUSTOM_ENTITY)
    if payload_bytes is not None:
        try:
            mapping, _headers, parsed_rows = read_import.parse_csv(payload_bytes, custom_fields)
        except read_import.ImportFileError as exc:
            # US-MET-007 TC-5/TC-6: the step BLOCKS with a specific reason and
            # NOTHING is staged — not a partial batch, not an empty one.
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key=f"metering.read_import.{exc.code}",
                params=exc.detail,
            ) from None
    elif isinstance(manual_entries, list) and manual_entries:
        parsed_rows = read_import.parse_manual_rows(manual_entries)
    else:
        _refuse_fields([_field_error("file", errors.VAL_REQUIRED, "metering.read_batch.no_input")])

    # CR-161-BRC10 W4 — checked BEFORE the transaction: a manual entry whose
    # answers are refused stages nothing and burns no batch number, and a file
    # row whose answers are refused is staged WITH the reason (validate-then-
    # accept, BR-MET-032). Neither statement is a database write, so there is
    # no aborted-transaction state to manage here (hard-won law 14).
    custom_by_row = _read_custom_answers(parsed_rows, from_file=payload_bytes is not None)
    warnings: list[dict[str, Any]] = []
    with transaction.atomic():
        batch = models.ReadImportBatch(
            tenant_id=_tenant_id(),
            batch_no=_allocate_number(READ_BATCH_SERIES, warnings),
            source_kind=tags["source_kind"],
            source_detail=tags["source_detail"],
            read_method=tags["read_method"],  # BR-MET-123 - the stage-1 TAG
            # CR-038 W7 R2 — the stage-1 PREMISE. Recorded on the BATCH and not
            # re-asked at commit: `commit_read_batch` reads it off this row, so
            # a mode chosen at stage 1 is the mode that runs, and the batch's
            # own record says afterwards which premise posted its readings.
            write_mode=tags["write_mode"],
            period_month=tags["period_month"],
            cycle=tags["cycle"],
            route=tags["route"],
            service=tags["service"],
            file_name=_text(data.get("file_name"), 255),
            file_hash=read_import.file_sha256(payload_bytes) if payload_bytes else None,
            tag_fingerprint=read_import.read_batch_idempotency_key(
                {
                    "period_month": tags["period_month"],
                    "cycle_id": tags["cycle"].id if tags["cycle"] else None,
                    "route_id": tags["route"].id if tags["route"] else None,
                    "service": tags["service"],
                    "source_kind": tags["source_kind"],
                    "source_detail": tags["source_detail"],
                }
            ),
            uploaded_by_id=getattr(actor, "id", None),
            uploaded_at=timezone.now(),
            session_ref=_text(data.get("session_ref"), 120),
            ip=data.get("ip") or None,
            status="staged",
        )
        batch.save()
        method_index = tags["read_method_index"]
        for parsed in parsed_rows:
            # BR-MET-014's override half, VERBATIM: *"Batch tags (month/cycle/
            # route/service/source) inherit to every row unless a row-level
            # column overrides"*. A row that states nothing inherits; a row
            # that states its own wins; a row that states an UNKNOWN word keeps
            # that word and carries an error, because coercing it to the batch
            # tag would file a reading against a collector who never touched it.
            row_method, row_method_known = _resolve_read_method(parsed.read_method, method_index)
            effective_method = row_method if parsed.read_method else tags["read_method"]
            method_errors = (
                []
                if row_method_known
                else [
                    {
                        "code": read_import.ERR_READ_METHOD_UNKNOWN,
                        "field": "read_method",
                        "value": row_method,
                    }
                ]
            )
            models.ReadImportRow.objects.create(
                tenant_id=_tenant_id(),
                batch=batch,
                row_no=parsed.row_no,
                # CR-054 W1 task 7 — the generated sheet's key, VERBATIM. It is
                # never corrected, folded or re-derived here: the whole point is
                # that it says what the row was written FOR, so the moment we
                # start tidying it, it stops being evidence.
                row_key=parsed.row_key,
                meter_no_raw=parsed.meter_no_raw,
                read_at=parsed.read_at,
                read_at_raw=parsed.read_at_raw,
                channel=parsed.channel,
                value=parsed.value,
                raw_value=parsed.value,
                service=parsed.service or tags["service"],  # BR-MET-014 row override
                read_method=effective_method,  # BR-MET-014 row override
                note=parsed.note,
                # BR-MET-051 (CR-038 W4) — the column the staged row has always
                # carried and nothing ever set. `_post_row` already copies it
                # onto `meter_reads`; this is the source it was missing.
                demand_reset_noted=parsed.demand_reset,
                custom_data=custom_by_row[parsed.row_no][0],
                rule_outcomes=[
                    {"rule": "parse", "severity": validation.ERROR, "detail": err}
                    for err in (parsed.errors + method_errors + custom_by_row[parsed.row_no][1])
                ],
                severity=(
                    validation.ERROR
                    if (parsed.errors or method_errors or custom_by_row[parsed.row_no][1])
                    else validation.OK
                ),
            )
        _audit(
            actor,
            "read_batch.staged",
            "read_import_batch",
            batch.id,
            after={"rows": len(parsed_rows), "file_name": batch.file_name, "status": "staged"},
        )
    result = selectors.read_batch_dict(batch)
    result["mapping"] = mapping
    # CR-161-BRC10 W4 — each own field's LABEL beside its mapping target, so the
    # mapping step names `custom_data.seal_number` as *Seal number*.
    result["mapping_labels"] = {
        f"{read_import.CUSTOM_TARGET_PREFIX}{field['key']}": field["label"]
        for field in custom_fields
    }
    result["warnings"] = warnings
    return result


# ── US-MET-008/009/011: validate the staged batch (step 3) ──────────────────


def _batch_row(batch_id: Any, *, locked: bool = False) -> Any:
    qs = models.ReadImportBatch.objects.filter(tenant_id=_tenant_id(), pk=batch_id)
    if locked:
        qs = qs.select_for_update()
    row = qs.first()
    if row is None:
        raise errors.NotFoundError()
    return row


def _attach_group_outcome(batch: Any, asset_id: Any, read_at: Any, outcome: Any) -> None:
    """Store one GROUP rule's verdict on every row of a (meter, date) group.

    The shape the sum-sanity and plan-registers loops each write inline; named
    once here because CR-038 W6's master/sub loop is the THIRD copy, and three
    copies of "append the outcome then recompute the row's worst severity" is
    where one of them starts forgetting the second half.
    """
    for row in models.ReadImportRow.objects.filter(
        tenant_id=_tenant_id(), batch=batch, asset_id=asset_id, read_at=read_at
    ):
        row.rule_outcomes = (row.rule_outcomes or []) + [outcome.as_dict()]
        row.severity = validation.worst_severity(
            [
                validation.Outcome(o["rule"], o["severity"], o.get("detail") or {})
                for o in row.rule_outcomes
            ]
        )
        row.save(update_fields=["rule_outcomes", "severity", "updated_at"])


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def validate_read_batch(actor: Any, batch_id: Any) -> dict[str, Any]:
    """Run the EP-MET-04 engine over every staged row and store the outcomes.

    The rules are validation.py's; this function's job is to hand each row its
    world and write back what came out — including, on the batch summary, the
    rules that could NOT be evaluated (BR-MET-020 fail-safe, CLAUDE.md law 1).
    """
    batch = _batch_row(batch_id)
    if batch.status == "posted":
        raise errors.BizError(
            errors.BIZ_IMMUTABLE,
            br_ref="BR-MET-017",
            message_key="metering.read_batch.already_posted",
        )
    # CR-038 A1: the WHOLE config set — the engine resolves per service.
    config = _config_set()
    rows = list(
        models.ReadImportRow.objects.filter(tenant_id=_tenant_id(), batch=batch).order_by("row_no")
    )

    seen_keys: dict[tuple[Any, Any, str], int] = {}
    unevaluated: dict[str, str] = {}
    # BR-MET-136: rules this tenant switched OFF for the service(s) in this
    # file. A SEPARATE accumulator from `unevaluated` above, for the reason
    # `validation.DISABLED` argues at length: a gap a clerk should chase and a
    # check the utility deliberately retired are different facts, and mixing
    # them makes the chase list useless.
    disabled: dict[str, str] = {}
    tou_groups: dict[tuple[Any, Any], dict[str, Any]] = {}
    # BR-MET-049 (US-MET-018, CR-038 W1): EVERY channel a meter received in
    # the batch, per (asset, read date) — the received half the plan-registers
    # group rule compares against the plan-derived expected set. Unlike
    # `tou_groups` above (TOU windows + total only), this holds the whole
    # channel vocabulary, because demand and export registers are part of the
    # required set too.
    register_groups: dict[tuple[Any, Any], dict[str, Any]] = {}
    # BR-MET-125 / DEF-791 (CR-038 W6): every row's computed consumption, keyed
    # (asset, read_at, channel) — the live input the master-vs-subs rule never
    # had. `tou_groups` above cannot serve it: it holds only the TOU windows and
    # `total` of ONE meter, and Σ subs is a fact about OTHER assets' rows in the
    # same file.
    consumption_by_key: dict[tuple[Any, Any, str], Decimal | None] = {}
    # The TOU group rule resolves config by the METER's service too, so each
    # group remembers it (one meter = one service; last write is idempotent).
    tou_group_service: dict[tuple[Any, Any], str | None] = {}
    # CR-038 W2: resolved ONCE per batch, shared across every row's context —
    # the enabled-service vocabulary for the coherence rule and the memo of
    # off-cycle cycle codes for BR-MET-122's named message.
    enabled_services = tuple(seams.enabled_service_codes())
    cycle_codes: dict[Any, str | None] = {}
    # BR-MET-049 + BR-MET-1160 share ONE resolver for the whole batch. It caches
    # `plan_register_inputs` per (plan, service, date) and the unit's plan per
    # unit, so a 500-row file makes one rating hop per distinct plan rather than
    # one per row (DEF-324), and the expected register set and the pricing unit
    # can never be derived from two different plans for one meter.
    # DEF-MET-8107 — and the rest of the answers every row asks the same way
    # (the service's billed unit, the unit's occupant), through one holder.
    lookups = _BatchLookups()
    register_resolver = lookups.pricing_resolver

    with transaction.atomic():
        for row in rows:
            parse_outcomes = [o for o in (row.rule_outcomes or []) if o.get("rule") == "parse"]
            if parse_outcomes:
                # A row that never parsed cannot be judged against thresholds —
                # its errors stand and it stays visible in the report.
                row.severity = validation.ERROR
                row.save(update_fields=["severity", "updated_at"])
                continue

            asset = seams.meter_by_no(row.meter_no_raw) if row.meter_no_raw else None
            key = (getattr(asset, "id", None), row.read_at, row.channel)
            duplicate_row_no = seen_keys.get(key) if asset is not None else None
            if asset is not None and duplicate_row_no is None:
                seen_keys[key] = row.row_no

            committed_dup = None
            unchanged_dup = None
            same_day_sibling = None
            # CR-038 W7: the HEAD ITSELF, not only its id — the write-mode pass
            # below needs its lifecycle (BR-MET-127 turns on `billed`) and the
            # words that name it in a refusal.
            head_row: Any = None
            if asset is not None and row.read_at is not None:
                head, same_value = _same_key_heads(asset.id, row.read_at, row.channel, row.value)
                head_row = same_value or head
                # BR-MET-1189 (PO 2026-10-04): the SAME value again is the same
                # reading (BR-MET-016 stands); a DIFFERENT value is a second
                # reading of that register that day, and it is kept.
                committed_dup = str(same_value.id) if same_value is not None else None
                if same_value is None and head is not None:
                    same_day_sibling = str(head.id)
                if head is None and batch.cycle is not None:
                    # BR-MET-016 second clause: a second read for the same
                    # meter+channel inside the cycle window with an UNCHANGED
                    # value is a duplicate too.
                    # W5-T2 — the window is DERIVED in the read's own month.
                    # ⚠ **AND THIS CLAUSE NOW FIRES FOR EVERY CYCLE, WHERE IT
                    # FIRED FOR ALMOST NONE.** It scoped itself with
                    # `cycle.window_start`/`window_end`, which are null on every
                    # cycle the wizard has created since CR-029 landed — so the
                    # rule was silently dead for all of them and alive only for
                    # CR-006-era rows. Deriving it is what the rule always said.
                    cycle_window = _cycle_window_for(batch.cycle, row.read_at)
                    same_cycle = (
                        _head_qs()
                        .filter(
                            asset_id=asset.id,
                            channel=row.channel,
                            current_value=row.value,
                            read_at__date__gte=cycle_window[0],
                            read_at__date__lte=cycle_window[1],
                        )
                        .first()
                        if cycle_window is not None
                        else None
                    )
                    unchanged_dup = str(same_cycle.id) if same_cycle is not None else None
                    if same_cycle is not None:
                        head_row = same_cycle

            ctx = _build_context(
                asset=asset,
                read_at=row.read_at,
                channel=row.channel,
                value=row.value,
                config=config,
                cycle=batch.cycle,
                duplicate_of_read_id=committed_dup,
                duplicate_of_row_no=duplicate_row_no,
                same_cycle_unchanged_read_id=unchanged_dup,
                same_day_sibling_read_id=same_day_sibling,
                # CR-038 W2: the row's BR-MET-014 effective service (row column
                # else the batch tag — exactly what staging stored) and the
                # batch-shared lookups the mixed-cycle rules read.
                stated_service=row.service,
                enabled_services=enabled_services,
                cycle_codes=cycle_codes,
                # CR-054 W1 task 7 — resolved from the STAGED ROW, which is the
                # only place the key still exists by the time the engine runs.
                row_key=row.row_key,
                row_no=row.row_no,
                meter_no_raw=row.meter_no_raw,
                # BR-MET-1160 — the batch-shared plan/pricing resolver.
                pricing_resolver=register_resolver,
                lookups=lookups,
            )
            consumption, outcomes = validation.evaluate_row(ctx, config)
            # ── CR-038 W7 R2 — RE-JUDGE THE DUPLICATE AGAINST THE PREMISE ────
            # CR-036 (g)'s finding, in the PO's own screenshots: stage 3 was
            # already reporting against an assumption about the write mode that
            # *"the operator was never asked to make"*. So the engine judges
            # (`validation.evaluate_row` above, untouched — a rule's verdict
            # must not depend on what the clerk meant to do with the file), and
            # the premise is applied HERE, as its own outcome beside the
            # engine's. A reader of `rule_outcomes` sees both facts: a duplicate
            # was found, and this is what the chosen mode does about it.
            outcomes = write_modes.apply(
                outcomes,
                write_modes.plan(
                    write_mode=batch.write_mode,
                    head_id=(committed_dup or unchanged_dup or same_day_sibling),
                    head_is_billed=getattr(head_row, "lifecycle", None) == "billed",
                    # BR-MET-1189 — a DIFFERENT value on the same (meter, date,
                    # register) is a second reading of that day, kept under
                    # `insert`; `insert & update` still supersedes it.
                    same_day=same_day_sibling is not None,
                    head_label=write_modes.read_label(
                        meter_no=row.meter_no_raw,
                        read_at=row.read_at,
                        channel=row.channel,
                    ),
                ),
            )
            for gap in validation.unevaluated(outcomes):
                unevaluated.setdefault(gap["rule"], gap["reason"] or "")
            for off in validation.disabled_rules(outcomes):
                disabled.setdefault(off["rule"], off["reason"] or "")

            if asset is not None and row.channel in (
                models.TOU_WINDOW_CHANNELS + (models.CHANNEL_TOTAL,)
            ):
                group = tou_groups.setdefault((asset.id, row.read_at), {})
                group[row.channel] = consumption
                tou_group_service[(asset.id, row.read_at)] = ctx.service_code

            if asset is not None and row.read_at is not None:
                registers = register_groups.setdefault(
                    (asset.id, row.read_at), {"asset": asset, "channels": set()}
                )
                registers["channels"].add(row.channel)
                # CR-038 W6: the master/sub group rule's live input.
                consumption_by_key[(asset.id, row.read_at, row.channel)] = consumption

            row.rule_outcomes = validation.as_json(outcomes)
            row.severity = validation.worst_severity(outcomes)
            row.asset = asset
            row.save(update_fields=["rule_outcomes", "severity", "asset", "updated_at"])

        # US-MET-017: sum-sanity is a GROUP rule — it can only run once every
        # channel of a meter+date has been evaluated.
        for (asset_id, read_at), group in tou_groups.items():
            if not any(channel in group for channel in models.TOU_WINDOW_CHANNELS):
                continue
            group_service = tou_group_service.get((asset_id, read_at))
            outcome = validation.switch_group_outcome(
                validation.tou_sum_sanity(
                    {c: group.get(c) for c in models.TOU_WINDOW_CHANNELS},
                    group.get(models.CHANNEL_TOTAL),
                    config,
                    service_code=group_service,
                ),
                config,
                group_service,
            )
            if outcome.severity == validation.DISABLED:
                # BR-MET-136's trailing clause: a disabled rule STATES itself on
                # the read. A group rule's statement lands the same way its
                # verdict would — on every row of the (meter, date) group — so
                # a clerk reading one row sees "off", not silence.
                disabled.setdefault(outcome.rule, outcome.detail.get("reason") or "")
                _attach_group_outcome(batch, asset_id, read_at, outcome)
                continue
            if outcome.severity == validation.NOT_EVALUATED:
                unevaluated.setdefault(outcome.rule, outcome.detail.get("reason") or "")
                continue
            for row in models.ReadImportRow.objects.filter(
                tenant_id=_tenant_id(), batch=batch, asset_id=asset_id, read_at=read_at
            ):
                row.rule_outcomes = (row.rule_outcomes or []) + [outcome.as_dict()]
                row.severity = validation.worst_severity(
                    [
                        validation.Outcome(o["rule"], o["severity"], o.get("detail") or {})
                        for o in row.rule_outcomes
                    ]
                )
                row.save(update_fields=["rule_outcomes", "severity", "updated_at"])

        # BR-MET-049 (US-MET-018): the plan-registers GROUP rule — the channels
        # this meter actually received vs the set its unit's plan expects,
        # shortfall NAMED. Same posture as the sum-sanity loop above: an
        # actionable verdict lands on every row of the (meter, date) group; an
        # unresolvable set is reported once on the batch summary (a unit with
        # no plan contributes no required set — TC-5 — and "rating cannot
        # answer" is never read as "expects nothing"). Severity on a shortfall
        # is WARNING by design: posting an incomplete meter is Open 2 and
        # unruled, so acceptance stays a human's explicit, reasoned call
        # (BR-MET-015), never a hard stop invented here.
        # ⚠ The SAME resolver the row loop used — its caches are already warm
        # for every (plan, service, date) in this batch, so this loop makes no
        # further rating hops at all.
        for (asset_id, read_at), registers in register_groups.items():
            expected = register_resolver.for_asset(registers["asset"], service_date=read_at.date())
            outcome = validation.switch_group_outcome(
                validation.plan_register_completeness(
                    registers["channels"],
                    expected.channels,
                    absent_reason=expected.absent_reason,
                    plan_detail=expected.detail(),
                ),
                config,
                _service_of_asset(registers["asset"]),
            )
            if outcome.severity == validation.DISABLED:
                disabled.setdefault(outcome.rule, outcome.detail.get("reason") or "")
                _attach_group_outcome(batch, asset_id, read_at, outcome)
                continue
            if outcome.severity == validation.NOT_EVALUATED:
                unevaluated.setdefault(outcome.rule, outcome.detail.get("reason") or "")
                continue
            for row in models.ReadImportRow.objects.filter(
                tenant_id=_tenant_id(), batch=batch, asset_id=asset_id, read_at=read_at
            ):
                row.rule_outcomes = (row.rule_outcomes or []) + [outcome.as_dict()]
                row.severity = validation.worst_severity(
                    [
                        validation.Outcome(o["rule"], o["severity"], o.get("detail") or {})
                        for o in row.rule_outcomes
                    ]
                )
                row.save(update_fields=["rule_outcomes", "severity", "updated_at"])

        # ── BR-MET-125 / DEF-791: THE MASTER-VS-SUB-METERS GROUP RULE ───────
        # The third group loop, and the one that finally gives BR-MET-025 a
        # live input. DEF-791, verbatim: *"_build_context hardcodes
        # submeter_consumption_sum=None with the comment 'runs on the committed
        # group, below', and NOTHING anywhere passes a sum"*. This is that
        # missing loop.
        #
        # Same posture as the two above: an actionable verdict lands on every
        # row of the (master, date) group, an unresolvable one is reported once
        # on the batch summary. It runs at VALIDATE so the clerk sees the 460
        # kWh before they post; the figure is STORED at COMMIT, from committed
        # reads — see `commit_read_batch`.
        for (asset_id, read_at), registers in register_groups.items():
            asset = registers["asset"]
            subs = submeter_reconciliation.live_submeters(
                asset, submeter_reconciliation.period_month_of(read_at)
            )
            if not subs:
                continue  # not a master — the ordinary meter, nothing to reconcile
            for channel in submeter_reconciliation.RECONCILED_CHANNELS:
                if channel not in registers["channels"]:
                    continue
                resolution = submeter_reconciliation.resolve_submeter_sum(
                    master=asset,
                    period_month=submeter_reconciliation.period_month_of(read_at),
                    channel=channel,
                    staged=consumption_by_key,
                    subs=subs,
                )
                master_service = _service_of_asset(asset)
                outcome = validation.switch_group_outcome(
                    submeter_reconciliation.mismatch_outcome(
                        master=asset,
                        resolution=resolution,
                        master_consumption=consumption_by_key.get((asset_id, read_at, channel)),
                        config=config,
                        service_code=master_service,
                    ),
                    config,
                    master_service,
                )
                if outcome.severity == validation.DISABLED:
                    disabled.setdefault(outcome.rule, outcome.detail.get("reason") or "")
                    _attach_group_outcome(batch, asset_id, read_at, outcome)
                    continue
                if outcome.severity == validation.NOT_EVALUATED:
                    unevaluated.setdefault(outcome.rule, outcome.detail.get("reason") or "")
                    continue
                _attach_group_outcome(batch, asset_id, read_at, outcome)

        batch.status = "validated" if batch.status == "staged" else batch.status
        batch.counts = selectors.read_batch_counts(batch)
        batch.save(update_fields=["status", "counts", "updated_at"])
        _audit(
            actor,
            "read_batch.validated",
            "read_import_batch",
            batch.id,
            # A ConfigSet is never None, so `config is not None` would report
            # config over a tenant that has NO row anywhere — `any_config` is
            # the honest answer (CR-038 A1).
            after={"counts": batch.counts, "config_present": config.any_config},
        )

    summary = selectors.read_batch_dict(batch)
    summary["unevaluated_rules"] = [
        {"rule": rule, "reason": reason} for rule, reason in sorted(unevaluated.items())
    ]
    # BR-MET-136: the checks this tenant switched off, stated on the batch the
    # same way the gaps are. Kept apart from `unevaluated_rules` on purpose —
    # "no figures for gas, go and set them" and "your utility turned the
    # vacant-unit check off" ask a clerk for different things.
    summary["disabled_rules"] = [
        {"rule": rule, "reason": reason} for rule, reason in sorted(disabled.items())
    ]
    # CR-038 A1: a ConfigSet is never None — `any_config` is the honest bit.
    summary["validation_config_present"] = config.any_config
    # BR-MET-057 (US-MET-018, CR-038 W1): the review step's cycle coverage —
    # which of the cycle's meters this batch (plus already-committed heads in
    # the window) still leaves missing. None WITH its reason for a batch not
    # tagged with a cycle: coverage is a cycle computation and a cycle-less
    # batch has no expectation to compare against (stated, never a silent 0).
    summary["cycle_coverage"] = completeness.batch_cycle_coverage(batch)
    if summary["cycle_coverage"] is None:
        summary["cycle_coverage_absent_reason"] = "batch_not_tagged_with_cycle"
    # CR-038 W2 aspect 5 (2026-08-26): the per-service review counts — the
    # "412 electric · 380 water · 388 gas" data for a mixed-cycle file. Keyed
    # by the meter's REAL service (its service point's — what the row will be
    # judged and posted as); a row whose meter cannot answer falls back to its
    # stated BR-MET-014 service, else "unknown". Computed AFTER the group
    # rules, so the severities counted are the FINAL ones; derived on every
    # validate, never stored (BR-MET-011 posture — batch.counts stays the
    # persisted shape it was).
    summary["per_service"] = _per_service_counts(batch)
    return summary


def _per_service_counts(batch: Any) -> dict[str, dict[str, int]]:
    """`{service: {rows, ok, warnings, errors}}` over the batch's rows."""
    per_service: dict[str, dict[str, int]] = {}
    counted = models.ReadImportRow.objects.filter(tenant_id=_tenant_id(), batch=batch).values_list(
        "severity", "service", "asset__service_point__service__code"
    )
    for severity, stated, real in counted:
        bucket = per_service.setdefault(
            real or stated or "unknown", {"rows": 0, "ok": 0, "warnings": 0, "errors": 0}
        )
        bucket["rows"] += 1
        if severity == validation.ERROR:
            bucket["errors"] += 1
        elif severity == validation.WARNING:
            bucket["warnings"] += 1
        else:
            bucket["ok"] += 1
    return {code: per_service[code] for code in sorted(per_service)}


# ── US-MET-008 step 4: per-row dispositions ─────────────────────────────────

_REASON_REQUIRED = frozenset({"accept_with_flag", "override", "reject", "skip", "field_visit"})


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def set_row_disposition(actor: Any, batch_id: Any, row_no: Any, payload: Any) -> dict[str, Any]:
    """BR-MET-015: record a row's disposition + reason + actor.

    Errors may NOT be plainly accepted — the resolutions are override (with a
    new value and a reason), reject, or a field visit. Warnings are postable
    only through an explicit accept that records who and why. A negative-usage
    row is offered no auto-fix here or anywhere (BR-MET-052).
    """
    data = _payload_dict(payload)
    batch = _batch_row(batch_id)
    if batch.status == "posted":
        raise errors.BizError(
            errors.BIZ_IMMUTABLE,
            br_ref="BR-MET-017",
            message_key="metering.read_batch.already_posted",
        )
    row = models.ReadImportRow.objects.filter(
        tenant_id=_tenant_id(), batch=batch, row_no=row_no
    ).first()
    if row is None:
        raise errors.NotFoundError()

    disposition = _text(data.get("disposition"), 40)
    fe: list[dict[str, Any]] = []
    if disposition not in models.DISPOSITIONS:
        fe.append(_field_error("disposition", errors.VAL_FORMAT, "metering.read_row.disposition"))
    reason = _text(data.get("reason"), 500)
    if disposition in _REASON_REQUIRED and not reason:
        fe.append(_field_error("reason", errors.VAL_REQUIRED, "metering.read_row.reason_required"))
    if disposition == "accept" and row.severity == validation.ERROR:
        # BR-MET-015: an error is never plainly accepted.
        fe.append(
            _field_error(
                "disposition", errors.VAL_RANGE, "metering.read_row.error_needs_resolution"
            )
        )
    new_value = None
    if disposition == "override":
        new_value = read_import._parse_decimal(str(data.get("value", "")))
        # DEF-MET-8109 — the same two values the file parser now refuses:
        # `NaN`/`Infinity` read as no value at all, and a figure with more
        # whole digits than NUMERIC(18,6) holds is refused by name, before
        # PostgreSQL can refuse it with a 500.
        if new_value is not None and not new_value.is_finite():
            new_value = None
        if new_value is None:
            fe.append(
                _field_error("value", errors.VAL_REQUIRED, "metering.read_row.override_value")
            )
        elif not read_import.fits_register_column(new_value):
            fe.append(
                _field_error("value", errors.VAL_RANGE, "metering.read_import.reading_too_large")
            )
        elif new_value < 0:
            fe.append(_field_error("value", errors.VAL_RANGE, "metering.read_row.value_negative"))
    _refuse_fields(fe)

    before = {"disposition": row.disposition, "value": str(row.value) if row.value else None}
    with transaction.atomic():
        if new_value is not None:
            row.value = new_value  # `raw_value` keeps the file's original
        row.disposition = disposition
        row.disposition_reason = reason
        row.disposed_by_id = getattr(actor, "id", None)
        row.save(
            update_fields=[
                "value",
                "disposition",
                "disposition_reason",
                "disposed_by",
                "updated_at",
            ]
        )
        _audit(
            actor,
            "read_row.dispositioned",
            "read_import_row",
            row.id,
            before=before,
            after={
                "disposition": disposition,
                "reason": reason,
                "value": str(row.value) if row.value else None,
            },
        )
    if new_value is not None:
        # BR-MET-022: a changed value re-runs the engine — the old outcomes
        # described a number that is no longer there.
        validate_read_batch(actor, batch.id)
        row.refresh_from_db()
    return selectors.read_row_dict(row)


# ── BR-MET-051: the demand reset, noted at the review step (CR-038 W4) ──────
#
# BR-MET-051, verbatim: *"Demand: manual demand-register value at cycle read +
# reset noted; ratchet off (BR-RAT proposal stands)"* (PO RD-4, CONFIRMED).
#
# The file column (`read_import.TEMPLATE_COLUMNS["demand_reset"]`) covers the
# clerk who KNEW at upload time. This covers the one who learns at the review
# step — which is the common case, because a technician who resets a fleet of
# demand registers on one visit says so once, about the visit, not once per
# meter. So the reset is recorded here per ROW, and the bulk form loops the
# same per-row write rather than issuing one blanket UPDATE: BR-MET-051 is a
# statement about a REGISTER, and a bulk write that left no per-row trail
# would be the rule with its evidence removed (the `accept_all_warnings`
# precedent one step above, and CLAUDE.md rule 7).

DEMAND_RESET_SKIP_NOT_DEMAND = "not_demand_channel"


def _demand_reset_flag(value: Any) -> bool:
    """The payload's `noted`, through the SAME vocabulary the file column uses
    (`read_import.DEMAND_RESET_TRUE/FALSE`) — one spelling table, not two.

    An ABSENT key means `True`: the control exists to note a reset, so a body
    that says nothing is asking for the thing the control does. An unreadable
    VALUE is refused rather than read as False, for the reason the parser
    refuses one — the harm is all in the direction of an unnoticed reset.
    """
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    noted = read_import._parse_demand_reset(str(value))
    if noted is None:
        _refuse_fields(
            [
                _field_error(
                    "noted",
                    errors.VAL_FORMAT,
                    "metering.read_row.demand_reset_unrecognised",
                    value=str(value),
                )
            ]
        )
    return bool(noted)


def _demand_reset_batch(batch_id: Any) -> Any:
    """The batch, refusing once it has posted (BR-MET-017 / hard rule 4)."""
    batch = _batch_row(batch_id)
    if batch.status == "posted":
        raise errors.BizError(
            errors.BIZ_IMMUTABLE,
            br_ref="BR-MET-017",
            message_key="metering.read_batch.already_posted",
        )
    return batch


def _note_demand_reset(actor: Any, row: Any, noted: bool) -> None:
    """One row's reset + who recorded it. Audited per row, always."""
    before = {"demand_reset_noted": row.demand_reset_noted}
    row.demand_reset_noted = noted
    row.save(update_fields=["demand_reset_noted", "updated_at"])
    _audit(
        actor,
        "read_row.demand_reset",
        "read_import_row",
        row.id,
        before=before,
        after={"demand_reset_noted": noted, "channel": row.channel},
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def set_row_demand_reset(actor: Any, batch_id: Any, row_no: Any, payload: Any) -> dict[str, Any]:
    """BR-MET-051: note (or un-note) the demand reset on ONE staged row.

    Refuses a row that is not the DEMAND register. That scope is BR-MET-051's
    own — the rule is about the demand register's reset, and both
    `demand_reset_noted` columns have carried the comment "demand channel
    only" since they were declared — and it is enforced here as well as in the
    parser so the server refuses regardless of what a screen offers.

    NO REASON IS ASKED FOR, and that is deliberate rather than an omission: a
    reset is an OBSERVATION a reader made in the field, not a judgment a clerk
    is making about a flagged row (which is what `_REASON_REQUIRED` exists
    for). What the write records instead is WHO said so and WHEN — the
    `audit_log` row, per CLAUDE.md rule 7.
    """
    data = _payload_dict(payload)
    batch = _demand_reset_batch(batch_id)
    row = models.ReadImportRow.objects.filter(
        tenant_id=_tenant_id(), batch=batch, row_no=row_no
    ).first()
    if row is None:
        raise errors.NotFoundError()
    if row.channel != models.CHANNEL_DEMAND:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-051",
            message_key="metering.read_row.demand_reset_not_demand",
        )
    _note_demand_reset(actor, row, _demand_reset_flag(data.get("noted")))
    return selectors.read_row_dict(row)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def bulk_demand_reset(actor: Any, batch_id: Any, payload: Any) -> dict[str, Any]:
    """The step-4 BULK reset — one visit, one click, every demand row.

    Returns WHAT IT DID PER ROW: `noted` lists the row numbers it wrote and
    `skipped` names every row it did not touch with the reason, so the screen
    can report "2 demand rows noted · 1 row skipped (not a demand register)"
    rather than a bare count. A bulk action whose answer is only a number
    cannot be checked by the person who clicked it.
    """
    data = _payload_dict(payload)
    noted_value = _demand_reset_flag(data.get("noted"))
    batch = _demand_reset_batch(batch_id)
    rows = list(
        models.ReadImportRow.objects.filter(tenant_id=_tenant_id(), batch=batch).order_by("row_no")
    )
    noted: list[int] = []
    skipped: list[dict[str, Any]] = []
    with transaction.atomic():
        for row in rows:
            if row.channel != models.CHANNEL_DEMAND:
                skipped.append({"row_no": row.row_no, "reason": DEMAND_RESET_SKIP_NOT_DEMAND})
                continue
            _note_demand_reset(actor, row, noted_value)
            noted.append(row.row_no)
    return {
        "batch_id": str(batch.id),
        "noted": noted,
        "skipped": skipped,
        "counts": {"noted": len(noted), "skipped": len(skipped), "rows": len(rows)},
    }


# ── US-MET-010: compliance stamp & atomic commit (step 5) ───────────────────


def _unresolved_errors(batch: Any) -> list[int]:
    """Rows still blocking the post (BR-MET-015). An error is resolved by
    override / reject / field visit / skip — never by ignoring it."""
    resolved = {"override", "reject", "field_visit", "skip"}
    return [
        row.row_no
        for row in models.ReadImportRow.objects.filter(
            tenant_id=_tenant_id(), batch=batch, severity=validation.ERROR
        ).order_by("row_no")
        if row.disposition not in resolved
    ]


def _idempotency_block(batch: Any) -> None:
    """BR-MET-018 / OQ-044 closure option b 🔒 — an identical re-submission
    (same file hash + same tag set) BLOCKS with who posted the original, when,
    and which batch. There is no double-post path, and no silent no-op either:
    the clerk is told the work is already done."""
    if not batch.file_hash:
        return
    original = (
        models.ReadImportBatch.objects.filter(
            tenant_id=_tenant_id(),
            file_hash=batch.file_hash,
            tag_fingerprint=batch.tag_fingerprint,
            status="posted",
        )
        .exclude(pk=batch.pk)
        .order_by("posted_at")
        .first()
    )
    if original is None:
        return
    raise errors.BizError(
        errors.BIZ_IDEMPOTENT,
        br_ref="BR-MET-018",
        message_key="metering.read_batch.already_posted_identical",
        params={
            "batch_id": str(original.id),
            "batch_no": original.batch_no,
            "posted_at": original.posted_at.isoformat() if original.posted_at else None,
            "posted_by": str(original.uploaded_by_id) if original.uploaded_by_id else None,
        },
    )


# BR-MET-129: the GROUP rules evaluated once per (meter, date) during batch
# validation and stored on the staged row. `_post_row` re-runs only the
# PER-ROW catalog (a single row's context cannot re-derive a group), so these
# flags are CARRIED from the staged row onto the committed read — "rule_outcomes
# carry every flag onto the committed read" (BR-MET-129 clause 1). Before this,
# a TOU sum-sanity or plan-registers warning silently vanished at commit.
_GROUP_RULES_CARRIED: tuple[str, ...] = (
    validation.RULE_TOU_SUM_SANITY,
    validation.RULE_PLAN_REGISTERS,
)


def _post_row(
    actor: Any,
    batch: Any,
    row: Any,
    config: Any,
    *,
    enabled_services: tuple[str, ...] | None = None,
    cycle_codes: dict[Any, str | None] | None = None,
    supersede_head: bool = False,
    lookups: _BatchLookups | None = None,
) -> Any:
    """One staged row → one committed `meter_reads` row, inside the caller's
    transaction. Recomputes consumption from the FINAL value (an override
    changed it) and applies the BR-MET-029 true-up when estimates stand on this
    lineage.

    BR-MET-129 (PO 2026-08-26), verbatim: *"**A WARNED READING POSTS —
    WARNINGS NEVER HOLD A COLLECTED READING OUT** … (1) At post, WARNED rows
    commit with their warnings attached (`rule_outcomes` carry every flag onto
    the committed read); no pre-post disposition is required for a warning."*
    The per-row flags are re-derived here (an override may have changed the
    number they describe); the GROUP flags are carried from the staged row —
    see `_GROUP_RULES_CARRIED`. The committed read's `disposition` stays the
    row's REAL one (None when nobody dispositioned — never a synthesized
    accept).

    ⚠ **DEF-MET-8107 — THE PRIOR ACTUAL HEAD IS ASKED FOR ONCE.** It was asked
    three times per reading (the context, the period below, the true-up's
    standing estimates), identically, inside one transaction. It is looked up
    here, AFTER any earlier row of this same batch has been written, so a file
    carrying two readings for one meter still judges the second against the
    first — which is why it is not among the `_BatchLookups` answers.
    """
    asset = row.asset
    prior = _prior_actual_head(asset.id, row.channel, row.read_at)
    ctx = _build_context(
        asset=asset,
        read_at=row.read_at,
        channel=row.channel,
        value=row.value,
        config=config,
        cycle=batch.cycle,
        stated_service=row.service,
        enabled_services=enabled_services,
        cycle_codes=cycle_codes,
        lookups=lookups,
        prior=prior,
    )
    consumption, outcomes = validation.evaluate_row(ctx, config)
    carried_group = [
        outcome
        for outcome in (row.rule_outcomes or [])
        if outcome.get("rule") in _GROUP_RULES_CARRIED
    ]
    if carried_group:
        # Into the judged set too, so the read's ONE primary status
        # (BR-MET-021) is picked from the FULL flag set it carries.
        outcomes = outcomes + [
            validation.Outcome(o["rule"], o["severity"], o.get("detail") or {})
            for o in carried_group
        ]
    days = (row.read_at.date() - prior.read_at.date()).days if prior is not None else None

    # BR-MET-029 true-up — runs automatically at commit when the lineage's
    # latest reads are estimates (US-MET-015 §1). Quantity only.
    standing = _standing_estimates(asset.id, row.channel, row.read_at, last_actual=prior)
    trued = estimation.true_up(
        estimation.TrueUpInput(
            channel=row.channel,
            # BR-MET-143 — the REGISTER's unit, the same one `ctx` was built
            # with and the same one the read is stamped with below. A true-up
            # that travelled in the meter's unit while the read travelled in the
            # register's would put two units on one lineage.
            unit=ctx.unit,
            actual_register=row.value,
            last_actual_register=prior.current_value if prior else None,
            multiplier=asset.multiplier,
            estimated_consumptions=[e.consumption for e in standing if e.consumption is not None],
            estimated_read_ids=[str(e.id) for e in standing],
        )
    )
    outcome_json = validation.as_json(outcomes)
    trues_up_ids = None
    if trued.applies:
        consumption = trued.quantity
        trues_up_ids = trued.corrects_read_ids
        outcome_json = outcome_json + [
            {"rule": "true_up", "severity": validation.OK, "detail": trued.as_dict()}
        ]

    # US-MET-009 "Replace existing": an override on a duplicate SUPERSEDES the
    # committed head — a new row, never an edit (BR-MET-016/053). The id is
    # reserved first so the old head can be closed before this one is inserted.
    #
    # ⚠ **TWO DOORS REACH THIS, AND THEY ARE DIFFERENT FACTS (CR-038 W7).**
    # `disposition == "override"` is a PERSON deciding, row by row, at the
    # review step. `supersede_head` is the batch's WRITE MODE — a premise stated
    # once at stage 1 for the whole file (CR-038 R2: *"insert & update
    # SUPERSEDES a committed duplicate as a correction, reason stamped"*). They
    # are recorded separately because a reader of the audit trail is entitled to
    # know which one closed a reading: a clerk who looked at it, or a mode that
    # applied to 1,180 rows. The MECHANISM is identical and must be — a new row
    # with the old head pointed at it (hard rule 4 / B2 DB-6). Neither ever
    # UPDATEs a committed reading's measurement.
    supersede_reason = row.disposition_reason or (
        write_modes.SUPERSEDE_REASON if supersede_head else None
    )
    new_id = core_dbfields.uuid7()
    previous = (
        _close_head(actor, asset.id, row.read_at, row.channel, new_id, supersede_reason)
        if (row.disposition == "override" or supersede_head)
        else None
    )
    read = models.MeterRead.objects.create(
        id=new_id,
        tenant_id=_tenant_id(),
        asset=asset,
        # BR-MET-079 / DEF-233 — resolved at COLLECTION and never rewritten.
        route_id=collection_route_id(asset),
        # DEF-658 — the same posture, and the column nothing used to write.
        # DEF-MET-8107: the occupant comes from the batch's one read of every
        # unit's occupying account when the post supplies it.
        account_id=collection_account_id(asset, lookups=lookups),
        read_at=row.read_at,
        channel=row.channel,
        period_start=prior.read_at.date() if prior is not None else None,
        period_end=row.read_at.date(),
        prior_value=prior.current_value if prior is not None else None,
        current_value=row.value,
        multiplier=asset.multiplier,
        consumption=_num6(consumption),
        # EXPLICIT — CLAUDE.md rule 3 — and it is the REGISTER's unit, never
        # the meter's (BR-MET-143, PO 2026-08-27, closing OQ-391). `ctx.unit`
        # is the unit every rule in this row's judgement was run against, so
        # the stored unit and the judged unit can never be two strings. On a
        # demand register it is `kW`; on the energy register of the SAME meter,
        # `kWh`. This line read `asset.unit` until 2026-08-27 and that is
        # DEF-797's label half — a peak stamped kWh on an issued document.
        unit=ctx.unit,
        # BR-CWP-074 (2) — the PROVENANCE flag: a batch re-stamped by
        # `customer_reads.record_customer_read` (the one writer) posts the
        # fourth source, `customer`, AT INSERT. Never `manual` — manual is a
        # person the utility SENT. Every other batch is unchanged.
        source=(
            "import"
            if batch.source_kind == "csv"
            else "customer" if batch.source_kind == "customer" else "manual"
        ),
        source_detail=batch.source_detail,
        # BR-MET-123 - the METHOD travels with the reading, and it is the ROW's
        # (inherited or overridden at stage time), never re-read off the batch.
        # That is the whole point of BR-MET-014's override: a batch tagged `ami`
        # whose row said `walk_by` posts a read that says `walk_by`.
        read_method=row.read_method,
        status=validation.primary_status(outcomes),
        lifecycle="committed",
        days_since_prior=days,
        rule_outcomes=outcome_json,
        import_batch=batch,
        imported_by_id=batch.uploaded_by_id,
        # BR-MET-128 (W9 task 1): the EVENT rides the batch and lands on the
        # read AT INSERT — never by a later UPDATE (append-only, B2 r8). NULL
        # for every ordinary import/manual batch. The USER half is
        # `imported_by` above: an event batch's uploader IS the acting user.
        event_context=getattr(batch, "event_context", None),
        disposition=row.disposition,
        disposition_reason=row.disposition_reason,
        # CR-038 R2 — *"reason stamped"*. Set only when this row actually closed
        # a head; a first reading on a meter supersedes nothing and a stamped
        # reason on it would claim a correction that never happened.
        supersede_reason=supersede_reason if previous is not None else None,
        trues_up_read_ids=trues_up_ids,
        demand_reset_noted=row.demand_reset_noted,
        # CR-161-BRC10 W4 — the answers the staged row carried, checked at stage
        # time. AT INSERT, never by a later UPDATE; nothing below reads them.
        custom_data=dict(row.custom_data or {}),
    )
    # DEF-MET-8107: set here, SAVED by the caller in the same UPDATE as the
    # row's posted record — one statement per reading where there were two.
    row.meter_read_id = read.id
    if previous is not None:
        _audit_supersede(actor, previous, read, supersede_reason)
    # CR-182-BRC10 (PO A5) — a reading flagged HIGH tells the customer NOW,
    # before any clerk decides. Soft, own savepoint, never raises.
    high_consumption.notify_if_flagged(read, replaced=previous, actor=actor)
    return read


def _store_submeter_reconciliations(batch: Any, posted: list[Any]) -> list[Any]:
    """**BR-MET-125 — write the unaccounted gap for every master this batch
    posted a read for**, one row per (premises, master, register, period).

    Runs over COMMITTED reads only, so the stored figure can never describe a
    reading that was never posted. A master with no premises (a meter still in
    inventory) stores nothing rather than inventing one — the read is a
    configuration problem the completeness surfaces already name.

    ⚠ **STORING A DERIVED FIGURE IS THE RULING, NOT THIS LANE'S CHOICE.** See
    `models.PremisesSubmeterReconciliation` — the PO chose option (a) *"store +
    report"* over report-only on 2026-08-26 so a future common-area ruling has
    a history to price from.
    """
    stored: list[Any] = []
    seen: set[tuple[Any, str, Any]] = set()
    for read in posted:
        if read.channel not in submeter_reconciliation.RECONCILED_CHANNELS:
            continue
        asset = read.asset
        period_month = submeter_reconciliation.period_month_of(read.read_at)
        key = (asset.id, read.channel, period_month)
        if key in seen:
            continue
        subs = submeter_reconciliation.live_submeters(asset, period_month)
        if not subs:
            continue
        seen.add(key)
        premises_id = submeter_reconciliation.premises_of(asset)
        if premises_id is None:
            continue
        resolution = submeter_reconciliation.resolve_submeter_sum(
            master=asset, period_month=period_month, channel=read.channel, subs=subs
        )
        outcome = submeter_reconciliation.mismatch_outcome(
            master=asset,
            resolution=resolution,
            master_consumption=read.consumption,
            config=_config_set(),
            service_code=_service_of_asset(asset),
        )
        stored.append(
            submeter_reconciliation.store_reconciliation(
                master=asset,
                premises_id=premises_id,
                period_month=period_month,
                channel=read.channel,
                outcome=outcome,
                resolution=resolution,
                master_consumption=read.consumption,
                master_read_id=read.id,
                service_id=getattr(getattr(asset, "service_point", None), "service_id", None),
                is_sample=bool(getattr(read, "is_sample", False)),
            )
        )
    return stored


def _ensure_export_records(actor: Any, batch: Any, posted: list[Any]) -> list[Any]:
    """One 0-value, review-flagged export record per net-meter cycle that has
    none (BR-AST-029).

    Deliberately NOT a guess at what was exported: the quantity is 0 and the
    status says the record is missing, so a clerk sees a gap rather than a
    number nobody measured. The unit is still EXPLICIT (CLAUDE.md rule 3) — a
    zero without its unit is as unusable as any other bare quantity.

    Only `total` records trigger it. A TOU net meter's windows are all
    consumption; its single export register pairs with the cycle, not with each
    window.
    """
    created: list[Any] = []
    for read in posted:
        asset = read.asset
        if not getattr(asset, "net_metering", False) or read.channel != models.CHANNEL_TOTAL:
            continue
        exists = models.MeterRead.objects.filter(
            tenant_id=_tenant_id(),
            asset_id=read.asset_id,
            read_at=read.read_at,
            channel=models.CHANNEL_EXPORT,
            superseded_by_id__isnull=True,
        ).exists()
        if exists:
            continue
        export = models.MeterRead.objects.create(
            tenant_id=_tenant_id(),
            asset=asset,
            # DEF-233 — the export channel is DERIVED from the read above and
            # inherits its stamp, so both channels of one collection agree even
            # if the meter moves route before the next read.
            route_id=read.route_id,
            account_id=read.account_id,
            read_at=read.read_at,
            channel=models.CHANNEL_EXPORT,
            period_start=read.period_start,
            period_end=read.period_end,
            current_value=None,  # no export register was supplied — none is invented
            multiplier=asset.multiplier,
            consumption=_num6(Decimal("0")),
            unit=asset.unit,  # EXPLICIT — rule 3
            source=read.source,
            # The export record is the SAME collection as the total record it
            # is derived from (BR-AST-029), so it inherits the method rather
            # than reporting none.
            source_detail=read.source_detail,
            read_method=read.read_method,
            status="missing",  # the review flag BR-AST-029 asks for
            lifecycle="committed",
            rule_outcomes=[
                {
                    "rule": "missing_export_record",
                    "severity": validation.WARNING,
                    "detail": {
                        "reason": "net_metering_cycle_without_export_record",
                        "br_ref": "BR-AST-029",
                        "paired_read_id": str(read.id),
                    },
                }
            ],
            import_batch=batch,
            imported_by_id=batch.uploaded_by_id,
            # BR-MET-128: the export half of an event read's cycle is DERIVED
            # from the read above and inherits its stamp, exactly as it
            # inherits the route — the two records describe one collection.
            event_context=getattr(read, "event_context", None),
        )
        _audit(
            actor,
            "read.export_record_missing",
            "meter_read",
            export.id,
            after={
                "meter": asset.asset_no,
                "read_at": read.read_at.isoformat(),
                "consumption": "0",
                "unit": export.unit,
                "paired_read_id": str(read.id),
                "br_ref": "BR-AST-029",
            },
        )
        created.append(export)
    return created


def _close_head(
    actor: Any,
    asset_id: Any,
    read_at: Any,
    channel: str,
    new_read_id: Any,
    reason: str | None,
) -> Any | None:
    """Close the current head with `superseded_by_id` + `superseded_at` — the
    ONLY UPDATE B2 r8 permits on a committed row, written as an explicit
    two-column queryset update so no other field can ride along.

    Called BEFORE the replacement row is inserted, and it must be: exactly one
    lineage head may exist per (asset, read_at, channel) (`uq_meter_reads_head`),
    so the old head has to be closed while the new id is still only reserved.
    That ordering is why the caller generates the replacement's uuid up front.
    """
    previous = (
        models.MeterRead.objects.filter(
            tenant_id=_tenant_id(),
            asset_id=asset_id,
            read_at=read_at,
            channel=channel,
            superseded_by_id__isnull=True,
        )
        .exclude(id=new_read_id)
        # BR-MET-1189: a register may now hold two readings on one date. A
        # correction replaces the one that COUNTS — the one the bill read —
        # and the sibling stays as it was.
        .order_by(*counted_reading.RANK)
        .first()
    )
    if previous is None:
        return None
    models.MeterRead.objects.filter(
        tenant_id=_tenant_id(), id=previous.id, read_at=previous.read_at
    ).update(superseded_by_id=new_read_id, superseded_at=timezone.now())
    return previous


def _audit_supersede(actor: Any, previous: Any, new_read: Any, reason: str | None) -> None:
    _audit(
        actor,
        "read.superseded",
        "meter_read",
        previous.id,
        before={
            "current_value": str(previous.current_value),
            "consumption": str(previous.consumption),
        },
        after={
            "superseded_by": str(new_read.id),
            "current_value": str(new_read.current_value),
            "consumption": str(new_read.consumption),
            "reason": reason,
        },
    )


# ── DEF-871 / OQ-690 — THE MONTHLY-USAGE RESTATEMENT, AND WHERE IT RUNS ─────
def _refresh_monthly_usage(
    actor: Any,
    account_ids: Sequence[Any],
    *,
    trigger: str,
    entity_id: Any = None,
    holders_added: bool = False,
) -> dict[str, Any]:
    """Restate the stored monthly usage for the accounts a write touched.

    `holders_added=True` says `account_ids` already carries the accounts
    `monthly_usage_service.with_estimate_holders` adds (DEF-MET-10163) — the
    queued rebuild's payload was expanded when it was queued, and expanding
    each chunk again would restate an account twice.

    ── WHY THIS EXISTS AT ALL (`DEF-871`, open 2026-08-27 → 2026-09-05) ──────
    `monthly_usage_service.recompute_account` is documented as *"the writer,
    called by the lane that changes reads"* and for nine days **no lane called
    it**: its only non-test caller was the sample-data seeder. So the stored
    table was empty on every real tenant, and three screens drew nothing from
    it — the staff `S21` Usage tab, and, from `CR-068` wave H on 2026-09-04,
    the customer portal's home usage tile and its Usage screen. The figure was
    correct wherever it existed; it never came to exist. Hard-won law 2.

    ── WHY IT RUNS OUTSIDE THE CALLER'S TRANSACTION, WHICH IS THE WHOLE POINT ─
    `OQ-690` asked: when the restatement hits `OQ-358` (a month whose reads for
    one account and one service disagree about the unit), does the COMMIT fail
    or does the month stay un-restated and get reported? The one-line fix was
    written and **withdrawn** in August precisely because, called from inside
    `commit_read_batch`'s transaction, an unanswered question about a CHART
    could refuse a lawful READ COMMIT — a clerk's twenty readings lost to a
    500 because one unrelated account's July held two units.

    **The rules settle it and a lane did not choose it.** `BR-MET-129` (PO
    2026-08-26): *"we can give the warning, but we cannot reject the reading"*.
    `BR-MET-940` (PO, carried into `CR-054`, 2026-08-30): *"all or nothing will
    not work - we accept what is correct and rejct what i not correct"*, with
    the held item carrying a reason back to a human.

    **But the placement is stronger than either rule, and that is deliberate.**
    Every caller runs this AFTER its own transaction has committed. Nothing
    here can therefore un-post a reading — not a refusal, not a bug, not a
    dropped connection — so the failure mode is *the usage is stale and
    reported*, structurally, rather than by everybody remembering to catch the
    right exceptions forever. `ATOMIC_REQUESTS` is unset, so a service's outer
    `atomic` block really is the outermost transaction in production.

    ── WHAT IS CAUGHT, AND WHY THE TWO CATCHES ARE DIFFERENT ────────────────
    **1 · `MixedUnitMonth` is collected per (service, month), by name.** That
    is the ruled case: the month keeps its previous statement, every other
    month of that account states, and it comes back in `months_not_restated`
    carrying `OQ-358` so a person can see WHY. This is `GatherProblem`'s
    posture, which `BR-BIL-015` already uses one module over — catch exactly
    the named condition, record it, and let a genuine bug propagate.

    **2 · Any other exception is held PER ACCOUNT and reported LOUDLY.** ⚠ This
    is a broad catch and it is defended rather than accidental, because
    `BR-MET-940` clause (5) says *"a bug — anything else — propagates"*. That
    clause is about holding ROWS OF A FILE, where swallowing means a customer's
    reading never exists. **Nothing is held here.** Every reading is already
    durable; the only casualty is a DERIVED CACHE that `BR-MET-141` clause (6)
    says nothing bills off (*"no rate, no invoice line and no charge reads this
    table"*) and that is fully re-derivable from `meter_reads` by
    `manage.py backfill_monthly_usage`. Letting it propagate would turn a
    successful post into a 500 the clerk reads as *"my readings were refused"* —
    which is the exact outcome `BR-MET-129` forbids, arriving one step later.
    **So it is swallowed, and it is never silent**: it lands in the result, it
    writes its own audit row, and `refresh_incomplete` is True.

    ── LAW 14 ───────────────────────────────────────────────────────────────
    Each `recompute_account` call is its own `@transaction.atomic`. When one
    raises, Django rolls back to that block (a real transaction at top level, a
    SAVEPOINT when nested) and the connection is healthy for the next account —
    which is what makes this loop safe on PostgreSQL, where a failed statement
    otherwise poisons everything after it. **That decorator is load-bearing for
    this loop; do not remove it.** `MixedUnitMonth` itself needs no savepoint
    and gets none: it is raised by pure Python before any statement runs (see
    `monthly_usage_service._hold_month`).
    """
    problems: list[monthly_usage_service.UnrestatedMonth] = []
    faults: list[dict[str, Any]] = []
    restated = 0
    # 🔒 DEF-MET-10163 — an actual posted here may cover another account's
    # estimate on the same meter; that account's month is restated too.
    if not holders_added:
        account_ids = monthly_usage_service.with_estimate_holders(account_ids)
    for account_id in account_ids:
        try:
            monthly_usage_service.recompute_account(
                account_id, actor=actor, problems=problems
            )
            restated += 1
        except Exception as exc:  # noqa: BLE001 — see "2 ·" above; never silent
            faults.append({"account_id": str(account_id), "reason": exc.__class__.__name__})

    months = [
        {
            "account_id": u.account_id,
            "service_id": u.service_id,
            "asset_id": u.asset_id,
            "register": u.channel,
            "grain": u.grain,
            "month": u.period_month.isoformat(),
            "question": u.question,
        }
        for u in problems
    ]
    report: dict[str, Any] = {
        "accounts_restated": restated,
        "accounts_seen": len(account_ids),
        "months_not_restated": len(months),
        "months_not_restated_rows": months[:50],
        "refresh_incomplete": bool(faults),
        "refresh_incomplete_accounts": faults[:50],
    }
    # Hard-won law 1: a comment claiming the gap is reported is not the report.
    # An audit row is written only when there is something to say — a clean
    # refresh already audits each row it writes (`monthly_usage.stated` and its
    # siblings), and a second row per batch saying "nothing was wrong" would
    # bury those.
    if months or faults:
        _audit(
            actor,
            "monthly_usage.refresh_incomplete",
            "read_import_batch" if entity_id is not None else "account",
            entity_id if entity_id is not None else (account_ids[0] if account_ids else None),
            after={"trigger": trigger, **report},
        )
    return report


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def commit_read_batch(
    actor: Any, batch_id: Any, payload: Any, *, defer: bool = True
) -> dict[str, Any]:
    """S28 step 5 — the commit. **PARTIAL SINCE BR-MET-940 (CR-054 task 14).**

    ⛔ **THE RULING, VERBATIM (PO, carried into CR-054):** *"COMMITTING All or
    nothing... - all or nothing will not work - we accept what is correct and
    rejct what i not correct - then create csv file at loading stage itself so
    that suer can see all cases thata re rejcted"*. CR-047 shipped exactly this
    for the account importer on 2026-08-29 under the PO's *"if it is success
    then you read next record, if it is fail - you display on screen shich
    record failed and why (dont write to dB) and continue to uplaod next
    record"*; CR-054 says tasks 13–16 *"apply that existing ruling to reads;
    they do not make a new decision"*.

    **WHAT CHANGED, IN ONE SENTENCE.** A file of 1,180 readings carrying 2
    unknown meters used to post **0** readings and refuse the batch; it now
    posts **1,178** and hands the 2 back with a reason
    (`GET /read-batches/{id}/results.csv?kind=failures`).

    ⚠ **THIS SUPERSEDES BR-MET-015's ERROR HALF AT THIS GATE AND NOWHERE
    ELSE.** BR-MET-015 reads *"errors must be resolved (reject/override/
    investigate) before post"* and its warning half was already superseded by
    BR-MET-129. Its error half still governs the ROW: an unresolved error still
    means that row does not post, it still needs a human, and a disposition
    given is still honoured. What is superseded is the BATCH consequence — an
    unresolved error no longer holds back readings that have nothing wrong with
    them.

    ⚠ **AND HARD RULE 6 IS UNTOUCHED, WHICH IS THE MOST IMPORTANT LINE HERE.**
    The batch still reaches `posted` and is still immutable (BR-MET-017), so
    the two guards a few lines down — `status == "posted"` and
    `_idempotency_block` — refuse a second commit exactly as before. **Partial
    posting therefore CANNOT double-post: the held rows are held ON A CLOSED
    BATCH, and the way back in is a corrected file, which is a new batch with
    its own hash.** That is CR-047's answer too, and it is the reason the batch
    is not left open for a second attempt.

    Two preconditions remain, each a stated refusal: certification present, and
    no identical batch already posted.

    ⚠ **EVERY WRITE IS ITS OWN SAVEPOINT** — see the `IntegrityError` import at
    the top of this file. One outer transaction still wraps the batch, so a
    killed worker still leaves nothing; inside it each `_post_row` runs in a
    nested `transaction.atomic()` so a row PostgreSQL turns down rolls back to
    its savepoint, writes nothing (the PO's *"dont write to dB"*), and leaves
    the transaction healthy for row 401.

    ⛔ **BR-MET-055 — A LARGE BATCH POSTS AS A BACKGROUND JOB (`DEF-MET-8106`).**
    This docstring said the post *"runs SYNCHRONOUSLY today — this deployment
    registers no BE-07 job store"*, and the store has existed since 2026-08-10
    (`apps.tenancy` registers it); the sentence outlived its reason by seven
    weeks (hard-won law 1). What it cost, reproduced before the PO ruled on
    2026-09-30: **480 readings took ~42 s locally and ~60 s on a
    production-like server; gunicorn kills the worker at 60 s AFTER the
    readings are saved; the clerk saw *Internal Server Error* and a re-post
    said *already posted*.** So a batch of more than `READ_POST_ASYNC_ROW_BAR`
    staged rows is now handed to a worker and this call answers at once with
    the job to poll (`deferred: true` → the API's 202); at or below the bar
    nothing changes. The worker runs `_commit_read_batch_body` — the SAME
    function, unguarded, because the role was checked HERE, on the request, and
    a job's actor carries no role by design (`DEF-AST-8102`; `G140` fails a
    job body that reaches a `@require_role` function).

    ⚠ **`defer=False` IS FOR IN-PROCESS CALLERS THAT BUILD ON THE READINGS
    NEXT** — the sample-data plant and `seed_demo`, which post a batch and then
    read it back in the same run. A deferred post would leave them building on
    readings that do not exist yet. The API never passes it.

    The preconditions a clerk can act on — posted already, discarded, an
    identical file already posted, certification missing — are asked HERE,
    before anything is queued, so a refusal still reaches the person who
    clicked. The body asks them again under the batch lock, because a queued
    job runs later and the world may have moved.
    """
    data = _payload_dict(payload)
    batch = _batch_row(batch_id)
    _refuse_post_now(batch, data)
    staged_rows = models.ReadImportRow.objects.filter(tenant_id=_tenant_id(), batch=batch).count()
    if defer and staged_rows > READ_POST_ASYNC_ROW_BAR:
        return _defer_read_batch_post(actor, batch, data, staged_rows)
    return _commit_read_batch_body(actor, batch_id, data)


def _refuse_post_now(batch: Any, data: dict[str, Any]) -> None:
    """The four refusals a post can meet before it writes anything, in the
    order the ruling fixed (BR-MET-018 before certification — see the body).
    Asked on the request AND again inside the body under the batch lock."""
    if batch.status == "posted":
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-MET-018",
            message_key="metering.read_batch.already_posted",
            params={"batch_id": str(batch.id)},
        )
    if batch.status == "discarded":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-012",
            message_key="metering.read_batch.discarded",
        )
    _idempotency_block(batch)
    if not (data.get("certified") or batch.certified_by_uploader):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="metering.read_batch.certification_required",
            field_errors=[
                _field_error(
                    "certified",
                    errors.VAL_REQUIRED,
                    "metering.read_batch.certification_required",
                )
            ],
        )


# ── DEF-MET-8106 · BR-MET-055 — THE POST AS A BACKGROUND JOB ────────────────
#
#: The job kind a deferred post runs under (registered in `apps.py`).
READ_POST_JOB = "metering.read_batch_post"
#: The job kind the monthly-usage rebuild runs under (`DEF-MET-8108`).
USAGE_REFRESH_JOB = "metering.monthly_usage_refresh"

#: Staged rows above which a post goes to a worker. ⛔ **SET FROM A MEASUREMENT**
#: (`DEF-MET-8106`, the asset lane's `DEF-AST-8103` method): PostgreSQL 16, a
#: migrated and `seed_demo`'d database plus 1,000 occupied electric meters, every
#: reading confirmed POSTED, the whole pass rolled back —
#: `10-scripts/def_met_8106_read_post_cost.py --rows 100 480 1000`:
#:
#:     rows | post request s | stmt/reading | usage rebuild        (branch base)
#:      100 |          11.82 |    35.1 + 10 | 2.28 s IN the request
#:      480 |          59.33 |    35.0 + 10 | 14.06 s IN the request
#:     1000 |         119.66 |    35.0 + 10 | 21.06 s IN the request
#:     rows | post (inline) s| stmt/reading | usage rebuild        (this change)
#:      100 |           5.00 |         17.3 | 2.46 s, its own job
#:      480 |          23.93 |         17.1 | 11.41 s, its own job
#:     1000 |          42.58 |         17.0 | 20.39 s, its own job
#:
#: ⚠ **CONTENDED FIGURES, AND SAID SO** — the box ran at a load average of ~10
#: on 4 cores from other lanes' suites, so the SECONDS are pessimistic and the
#: STATEMENTS are the stable figure (the premises entry in
#: `import_runs.ASYNC_ROW_BAR_BY_TARGET` states the rule: a contended figure is
#: not a per-row cost). The base's 480 at 59.3 s is the reproduction's *"~60 s
#: on a production-like server"* to within a second.
#:
#: **200 HOLDS THE POST INSIDE A THIRD OF THE 60 s WALL WITH MARGIN** — the rule
#: every bar in this product is held to: ~48 ms a reading here puts 200 at
#: ~9.6 s, and the reproduction's production-like server ran ~1.4x slower than
#: its local box, ~13.5 s. It is also the stage default the loads use
#: (`import_runs.ASYNC_ROW_BAR_BY_STAGE`), and it FAILS CLOSED: a smaller batch
#: loses nothing, a bigger one gets a progress bar instead of a timeout. Re-run
#: the script on a quiet box before anyone raises it.
READ_POST_ASYNC_ROW_BAR = 200

#: How many accounts the usage rebuild restates between two checkpoints. Small
#: enough that a killed worker re-does little, large enough that the job record
#: is not written after every account.
USAGE_REFRESH_CHUNK = 25


class _PostJobActor:
    """The actor a WORKER carries: an id and NO role — `import_runs._JobActor`'s
    posture, verbatim in intent: the role was checked on the request that
    queued the job, and a worker must not be able to grant anything."""

    __slots__ = ("id",)

    def __init__(self, user_id: Any) -> None:
        self.id = user_id


def _defer_read_batch_post(
    actor: Any, batch: Any, data: dict[str, Any], staged_rows: int
) -> dict[str, Any]:
    """Queue the post and answer at once with the job to poll.

    ⚠ **REFUSES RATHER THAN QUEUE INTO THE VOID** (`DEF-2487`'s posture, the
    same check `import_runs._refuse_no_worker` makes): a queued post on a
    deployment with no worker would say *Posting…* for ever and write nothing.
    ⚠ **THE SCOPE KEY IS THE BATCH**, so a double-clicked *Post* folds into the
    job already running (`core.jobs.enqueue`, NFR-16) rather than starting a
    second post — which hard rule 6 would refuse anyway, but only after the
    clerk had watched a second bar.
    """
    ready, reason = core_jobs.dispatch_is_ready()
    if not ready:
        logger.error(
            "read batch post REFUSED: nothing would run it (%s) — DEF-2487's shape", reason
        )
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-055",
            message_key="metering.import.no_worker",
        )
    record = core_jobs.enqueue(
        READ_POST_JOB,
        payload={
            "batch_id": str(batch.id),
            "certified": bool(data.get("certified")),
            "rows": staged_rows,
            "actor_user_id": (
                str(getattr(actor, "id", None)) if getattr(actor, "id", None) else None
            ),
        },
        scope_key=f"read_batch_post:{batch.id}",
    )
    result = selectors.read_batch_dict(_batch_row(batch.id))
    result["deferred"] = True
    result["async"] = True
    result["rows_to_post"] = staged_rows
    result["receipt_url"] = f"/read-batches/{batch.id}/post-receipt"
    result.update(core_jobs.accepted(record))
    return result


class _PostProgress:
    """The post's gauge: `done of total` readings on the JOB RECORD, written
    where a poller can see it WHILE the post's one transaction is still open.

    ⚠ **A WRITE ON THE POST's OWN CONNECTION WOULD BE INVISIBLE UNTIL THE END**
    — `import_progress`'s whole argument, and this uses its second, autocommit
    connection (`import_progress.write_job_progress`). Throttled to one write
    per 25 readings or per second, whichever is slower. Never raises: a gauge
    does not fail the work it measures.
    """

    EVERY_ROWS = 25
    EVERY_SECONDS = 1.0

    def __init__(self, job_id: Any, total: int) -> None:
        self.job_id = job_id
        self.total = total
        self._last_done = -1
        self._last_at = 0.0

    def step(self, done: int) -> None:
        if self.job_id is None:
            return
        now = time.monotonic()
        if (
            done != self.total
            and done - self._last_done < self.EVERY_ROWS
            and now - self._last_at < self.EVERY_SECONDS
        ):
            return
        import_progress.write_job_progress(
            tenant_id=_tenant_id(), job_id=self.job_id, done=done, total=self.total
        )
        self._last_done = done
        self._last_at = now


def run_read_batch_post_job(record: dict[str, Any]) -> str | None:
    """The deferred post, in a worker. `core.jobs.run_job` has already entered
    the record's tenant context and marked it running.

    ⛔ **NO ROLE-GUARDED FUNCTION MAY BE REACHED FROM HERE (`DEF-AST-8102`,
    `G140`).** This calls `_commit_read_batch_body` directly — never the guarded
    `commit_read_batch` — because this actor has an id and no role, and a
    guard would refuse every job with a false *"not allowed"* after the clerk
    was told the post had started.

    Re-delivery (`CELERY_TASK_ACKS_LATE`) is safe by hard rule 6: the post is
    ONE transaction, so a worker killed half-way leaves nothing, and a second
    delivery of a post that DID commit meets `already_posted` under the lock.
    """
    payload = record["payload"]
    batch_id = payload["batch_id"]
    actor = _PostJobActor(payload.get("actor_user_id"))
    progress = _PostProgress(record["id"], int(payload.get("rows") or 0))
    _commit_read_batch_body(
        actor, batch_id, {"certified": payload.get("certified")}, progress=progress
    )
    return f"/read-batches/{batch_id}/post-receipt"


def _commit_read_batch_body(
    actor: Any,
    batch_id: Any,
    data: dict[str, Any],
    *,
    progress: _PostProgress | None = None,
) -> dict[str, Any]:
    """The post itself — `commit_read_batch`'s docstring is its specification.

    UNGUARDED ON PURPOSE: the request path reaches it through the guarded
    `commit_read_batch`, and the worker path through `run_read_batch_post_job`,
    whose actor has no role (see there). Nothing else may call it.
    """
    config = _config_set()  # CR-038 A1: commit re-judges per service too
    # CR-038 W2: the same batch-shared lookups the validate pass uses.
    enabled_services = tuple(seams.enabled_service_codes())
    cycle_codes: dict[Any, str | None] = {}
    posted: list[Any] = []
    skipped: list[dict[str, Any]] = []
    #: CR-038 W7 — how many of the posted rows CORRECTED a reading already on
    #: file rather than adding one. Counted rather than derived afterwards: the
    #: heads are closed inside this transaction, so after it commits there is no
    #: query that can tell "superseded by this batch" from "superseded earlier".
    superseded: list[dict[str, Any]] = []

    with transaction.atomic():
        batch = _batch_row(batch_id, locked=True)
        # The same four refusals the request asked, asked AGAIN under the lock:
        # a queued post runs later than the click that queued it (DEF-MET-8106).
        # BR-MET-018 first: an identical re-submission hears the OQ-044
        # message (who/when/link), not the wall of duplicate-row errors its
        # own re-upload just generated. Order is part of the ruling's intent.
        _refuse_post_now(batch, data)
        # ── BR-MET-940 — WHERE THE ALL-OR-NOTHING REFUSAL USED TO BE ────────
        # This is the line CR-054 task 14 removes, and it is worth naming what
        # stood here so nobody restores it as a "fix":
        #
        #     blocking = _unresolved_errors(batch)
        #     if blocking:
        #         raise errors.BizError(BIZ_COMPLETENESS, "BR-MET-015",
        #                               "metering.read_batch.errors_need_resolution")
        #
        # Two unknown meters in a file of 1,180 refused the whole post, and the
        # clerk's only route forward was to disposition rows one at a time for
        # a fault that had nothing to do with the other 1,178 customers.
        # `_unresolved_errors` itself is KEPT and still called — the count goes
        # onto the result and into the audit row, because *which* rows were held
        # is the whole of the ruling's second half. What is gone is the raise.
        blocking = _unresolved_errors(batch)

        rows = list(
            models.ReadImportRow.objects.filter(tenant_id=_tenant_id(), batch=batch)
            # DEF-MET-8107 — the meter's status, type and service point were
            # each lazy-loaded once per reading by the rules; one join here is
            # the `seams.meter_by_no` shape the validate pass already uses.
            .select_related(
                "asset",
                "asset__status",
                "asset__type",
                "asset__service_point",
                "asset__service_point__service",
                "asset__service_point__unit",
            )
            .order_by("row_no")
        )
        # DEF-MET-8107 — answers shared by every row of this post, and every
        # unit's occupying account asked for in ONE read rather than twice per
        # reading.
        lookups = _BatchLookups()
        lookups.prime_occupants(
            {
                getattr(getattr(r.asset, "service_point", None), "unit_id", None)
                for r in rows
                if r.asset_id
            }
        )

        # ⛔ **EVERY SKIP IS COUNTED AND NAMED (DEF-659).** These two `continue`s
        # are lawful — a row a clerk REJECTED (or sent to the field, or skipped)
        # does not post, and a row with no asset/date/value cannot post honestly —
        # but until 2026-08-24 they were SILENT: the result carried `posted_reads`
        # and nothing else, so a batch that skipped every row answered
        # `status: posted` and the caller had no reason to look. Reproduced:
        # `{'status': 'posted', …}` with `posted_reads: 0` over a batch whose only
        # row was an undispositioned warning.
        #
        # ⚖️ **BR-MET-129 (PO 2026-08-26) — A WARNED READING POSTS.** Verbatim:
        # *"No if reading are colelcted we have to store the reading, we can give
        # the warning, but we cannot reject the reading, when reading are
        # colelcted then only we will know whether there is usage or not;
        # otherwise, just tagging vacant and customer using utility services -
        # never will be captured - there can be fraud also by people"*. So an
        # UNDISPOSITIONED warning row now posts, its flags carried onto the
        # committed read (`_post_row`), worked AFTER commit from the Reads list
        # (US-MET-012). This supersedes BR-MET-015's warning half — which this
        # loop enforced until 2026-08-26 by skipping such rows. ~~Errors still
        # gate the whole post (`_unresolved_errors` above — BR-MET-015's error
        # half, unchanged)~~ ⚠ **SUPERSEDED 2026-08-30 BY BR-MET-940: an error
        # gates its own ROW and no longer the batch** (CR-054 task 14, PO: *"all
        # or nothing will not work"*) — `_unresolved_errors` still runs and its
        # count still travels, and what is gone is the raise. And a disposition
        # GIVEN is still honored: reject/skip/field_visit/estimate keep the row
        # out, exactly as before.
        #
        # ⚠ **`skipped` NOW RECORDS THE ROW'S REAL `disposition`, NOT THE
        # RESOLVED ONE, AND THAT IS A CORRECTION RATHER THAN A SIDE EFFECT.**
        # Two of the three old branches wrote the DERIVED value, so a row nobody
        # had looked at could be reported as `disposition: "accept"` — the
        # synthesized accept `_post_row`'s own docstring says must never be
        # recorded. `_hold` writes `row.disposition` everywhere: `None` means
        # nobody decided, which is the fact the rejects file has to be able to
        # tell from a decision a person made.
        def _hold(row: Any, reason: str, *, exc: Exception | None = None, **extra: Any) -> None:
            """Record ONE held row — on the result AND on the row itself.

            ⛔ **BOTH, AND THE ROW IS THE HALF THAT MATTERS (BR-MET-940/931).**
            `skipped` is a response payload and is gone the moment the request
            ends; the ruling's second half is *"create csv file ... so that suer
            can see all cases thata re rejcted"*, and a file downloaded an hour
            later can only be built from what is STORED. `read_rejects.
            held_record` writes the reason and its two plain-English sentences
            into `rule_outcomes` — the same list the row already carries its
            flags in, so no column is added and nothing has to be re-derived.

            ⚠ **THE ROW's OWN `severity` IS NOT TOUCHED.** That is stage 3's
            verdict about the READING, and a post result is a different fact
            (`BR-MET-090`'s posture: what was judged stays judged).
            """
            record = read_rejects.held_record(row, reason, exc=exc, **extra)
            skipped.append(
                {
                    "row_no": row.row_no,
                    "reason": reason,
                    "disposition": row.disposition,
                    "severity": row.severity,
                    **{key: value for key, value in extra.items() if value is not None},
                    read_rejects.FAILURE_REASON_COLUMN: record["detail"][
                        read_rejects.FAILURE_REASON_COLUMN
                    ],
                }
            )
            row.rule_outcomes = (row.rule_outcomes or []) + [record]
            row.save(update_fields=["rule_outcomes", "updated_at"])

        for done, row in enumerate(rows):
            # DEF-MET-8106 — the gauge a deferred post's progress bar reads;
            # a synchronous post passes none. Throttled inside.
            if progress is not None:
                progress.step(done)
            disposition = row.disposition or (
                "accept"
                if row.severity in (validation.OK, validation.WARNING)  # BR-MET-129
                else None
            )
            if disposition not in models.POSTING_DISPOSITIONS:
                # ⛔ **TWO FACTS WEARING ONE REASON UNTIL BR-MET-940.** A row a
                # HUMAN rejected and a row carrying an error NOBODY HAS LOOKED
                # AT both land here, and before partial posting the second kind
                # never got this far — it refused the batch. They need different
                # sentences, because the clerk's next act is different: one is
                # *"you decided this"*, the other is *"nobody has decided this
                # yet"*. `not_dispositioned_for_posting` keeps its exact old
                # meaning and its old string, so no existing caller moves.
                _hold(
                    row,
                    (
                        read_rejects.REASON_UNRESOLVED_ERROR
                        if (row.disposition is None and row.severity == validation.ERROR)
                        else read_rejects.REASON_DISPOSITIONED_OUT
                    ),
                )
                continue
            if row.asset is None or row.read_at is None or row.value is None:
                # cannot post honestly; it stays reported on the batch
                _hold(row, read_rejects.REASON_INCOMPLETE_ROW)
                continue
            # ── CR-038 W7 R2 — THE PREMISE, RE-DERIVED AGAINST THE HEAD AS IT
            # IS **NOW** ──────────────────────────────────────────────────────
            # NOT read off the staged row's stored outcome, deliberately. The
            # validate pass is a REHEARSAL: between it and this commit another
            # clerk may have superseded the same reading, or `mark_read_billed`
            # may have moved it to `billed` when a bill run issued. Acting on a
            # stale rehearsal is how a bulk upload mints the money correction
            # BR-MET-127 exists to forbid. This whole block runs inside the
            # commit's `transaction.atomic()` with the batch row locked.
            head, same_value = _same_key_heads(row.asset_id, row.read_at, row.channel, row.value)
            # BR-MET-1189: the same value again is the same reading; a
            # different value is a second reading of the day, kept.
            head = same_value or head
            mode_plan = write_modes.plan(
                write_mode=batch.write_mode,
                head_id=str(head.id) if head is not None else None,
                head_is_billed=getattr(head, "lifecycle", None) == "billed",
                head_label=write_modes.read_label(
                    meter_no=row.meter_no_raw, read_at=row.read_at, channel=row.channel
                ),
                same_day=same_value is None,
            )
            if mode_plan["action"] == write_modes.ACTION_REFUSE_BILLED:
                # ⚖️ BR-MET-127, verbatim: *"A Replace (or Insert & update) row
                # whose existing read is BILLED is refused with the read named
                # and the reason … the refusal is a row outcome, never a batch
                # failure; nothing bulk ever opens a money correction."*
                _hold(
                    row,
                    write_modes.SKIP_REASON_BILLED,
                    existing_read_id=mode_plan.get("existing_read_id"),
                    existing_read=mode_plan.get("existing_read"),
                    br_ref="BR-MET-127",
                    door="correct_billed_read",
                )
                continue
            if mode_plan["action"] == write_modes.ACTION_BLOCKED:
                # `insert` met a reading already on file. Under BR-MET-016 that
                # is an ERROR, so before BR-MET-940 reaching here meant a HUMAN
                # had dispositioned the row for posting (`override` —
                # US-MET-009's "Replace existing", which supersedes) without
                # changing the mode. ⚠ **THAT SENTENCE USED TO SAY "because the
                # gate above has already refused the whole post", AND THE GATE
                # IS GONE (CR-054 task 14).** The conclusion is unchanged and
                # the reason is now stronger rather than weaker: an
                # undispositioned BR-MET-016 error is HELD by the disposition
                # branch at the top of this loop and never reaches this line, so
                # a row that gets here still had a person look at it. The human's
                # disposition wins; the premise does not override a person who
                # looked at the row. Recorded so the batch can say afterwards
                # that it happened.
                mode_plan = {**mode_plan, "action": write_modes.ACTION_SUPERSEDE}
            if mode_plan["action"] == write_modes.ACTION_SUPERSEDE:
                superseded.append(
                    {
                        "row_no": row.row_no,
                        "existing_read_id": mode_plan.get("existing_read_id"),
                        "existing_read": mode_plan.get("existing_read"),
                        "write_mode": batch.write_mode,
                    }
                )
            # ⛔⛔ **ONE SAVEPOINT PER READING — CR-054 TASK 14 (BR-MET-940),
            # AND IT IS THE ONLY SHAPE THAT WORKS ON POSTGRESQL.**
            #
            # ⚠ **A NESTED `atomic()` IS A SAVEPOINT, WHICH IS THE WHOLE
            # POINT.** The refusal is caught OUTSIDE the inner block, so
            # PostgreSQL has already rolled back to the savepoint: this row
            # wrote no `meter_reads` row and closed no head (the PO's *"dont
            # write to dB"*), the OUTER transaction is still healthy, and row
            # 401 is judged as if row 400 had never run. Without it, `except
            # IntegrityError: continue` cannot work at all — the next
            # statement answers `current transaction is aborted, commands
            # ignored until end of transaction block` and the whole batch is
            # lost at COMMIT. **`config/settings/test.py` runs in-memory
            # SQLite, which has no aborted-transaction state, so the broken
            # version is green in this suite on every machine.** Proved on a
            # real PostgreSQL 16 before this shipped (CLAUDE.md hard-won law
            # 14; `tests/test_cr054_w24_backend.py` carries the transcript).
            #
            # ⚠ **THE ALL-OR-NOTHING PROPERTY THE OUTER TRANSACTION CARRIES IS
            # UNTOUCHED** — a killed process still leaves nothing at all,
            # because that property is about the outer transaction and this is
            # inside it. What the savepoint changes is only which ROWS the
            # successful outer commit contains.
            #
            # ⚠ **`_hold` IS CALLED OUTSIDE THE `try`, DELIBERATELY.** It
            # writes `rule_outcomes` on the staged row, and a write inside the
            # rolled-back savepoint would be rolled back with the reading — the
            # row would come out of a failed post carrying no reason at all,
            # which is `DEF-320`'s shape and is exactly what task 16 exists to
            # prevent.
            try:
                with transaction.atomic():
                    read = _post_row(
                        actor,
                        batch,
                        row,
                        config,
                        enabled_services=enabled_services,
                        cycle_codes=cycle_codes,
                        # CR-038 R2: *"the modes NEVER edit a committed row
                        # (hard rule 4)"*. `supersede` here means exactly what
                        # it means everywhere else in this module —
                        # `_close_head` writes the two closure columns on the
                        # old head and a NEW row is inserted. There is no
                        # UPDATE path and there must not be.
                        supersede_head=mode_plan["action"] == write_modes.ACTION_SUPERSEDE,
                        lookups=lookups,
                    )
            except (errors.BizError, errors.ValidationError) as refusal:
                # ⚠ **THESE TWO CLASSES AND NOT `Exception`** — CR-047's own
                # reasoning, which holds here word for word. `BizError` and
                # `ValidationError` are the catalogue's two ways of saying
                # *"this ROW's data is wrong"*, which is the only kind of
                # failure a per-row hold is the right answer to. Everything
                # else is left to propagate and take the batch down, because
                # none of it is about this row:
                #   · `AuthError` — the actor's role. It would refuse every row
                #     identically, and 1,180 "rejected" rows would hide one
                #     permission problem behind a data-quality report.
                #   · `SysError` — the numbering series unusable, a seam
                #     unreachable. The next row fails the same way and the
                #     cycle's readings would land half-filed.
                #   · `NotFoundError` and anything unforeseen — a bug or a
                #     broken invariant. Swallowing those is how a post reports
                #     "43 held" over a fault nobody diagnoses.
                _hold(row, read_rejects.REASON_WRITE_REFUSED, exc=refusal)
                continue
            except (IntegrityError, DataError) as refusal:
                # ⚠ **THE DATABASE ITSELF, AND READS NEEDS THIS ARM WHERE THE
                # ACCOUNTS LOADER DOES NOT.** `create_account_from_import`
                # writes through another module's SERVICE, which refuses a bad
                # row by name; `_post_row` writes `meter_reads` through the ORM,
                # so what turns a row down here is PostgreSQL — the partial
                # unique index over lineage heads when another clerk commits the
                # same (meter, date, register) between the rehearsal and this
                # statement, a NOT NULL column, a foreign key whose target
                # vanished mid-post. That is CR-047's WIDENING arm
                # (`_load_locked`'s task-21 block), not its accounts arm, and
                # both are the same savepoint.
                _hold(row, read_rejects.REASON_DATABASE_REFUSED, exc=refusal)
                continue
            posted.append(read)
            # The mirror of the held record: without it, "no post outcome" would
            # mean both *"this row posted"* and *"this batch never posted"*, and
            # the rejects file has to tell those apart to know whether it is a
            # worklist or a receipt (`read_rejects.posted_record`).
            row.rule_outcomes = (row.rule_outcomes or []) + [read_rejects.posted_record(read.id)]
            # DEF-MET-8107 — `meter_read_id` (set by `_post_row`) rides the same
            # UPDATE: one statement per reading where there used to be two.
            row.save(update_fields=["meter_read_id", "rule_outcomes", "updated_at"])

        if progress is not None:
            progress.step(len(rows))

        # BR-AST-029 (US-AST-011 TC-6): a net meter's cycle is TWO records. A
        # batch that carried only the consumption record leaves the export half
        # as an explicit 0-value record FLAGGED FOR REVIEW — never as silence,
        # which would read downstream as "this net meter exported nothing".
        posted.extend(_ensure_export_records(actor, batch, posted))

        # ── BR-MET-125: THE UNACCOUNTED GAP IS STORED, AND SURVIVES THE POST ──
        # PO 2026-08-26, verbatim: *"(a) store + report — keeps the door open"*.
        # Recomputed here from COMMITTED reads rather than carried over from the
        # validate pass, deliberately: a stored figure derived from staged rows
        # would outlive a discarded batch and state a gap for reads that never
        # landed. The clerk already SAW the flag at step 4; this is what
        # persists. Billing a common area from the figure is NOT built — that is
        # the door the ruling keeps open, and it needs its own ruling.
        _store_submeter_reconciliations(batch, posted)

        # ── DEF-871 · BR-MET-106 / BR-MET-141 — THE MONTHLY USAGE **IS**
        # RESTATED, AND DELIBERATELY **NOT HERE** (`OQ-690`, closed 2026-09-05)
        #
        # The trigger this comment used to say was missing now exists. It runs
        # **after** the `with transaction.atomic()` block below closes, not
        # inside it, and the placement is the whole point rather than a detail:
        # see `_refresh_monthly_usage` for the reasoning and the ruling.
        #
        # In one sentence: by the time the restatement starts, every reading in
        # this batch is already COMMITTED and durable, so nothing the
        # restatement does — a refusal, a bug, a dead connection — can un-post
        # a reading. `OQ-690` asked whether the restatement should be allowed
        # to fail the commit; putting it after the transaction means it CANNOT,
        # which is a stronger answer than a rule that says it must not.

        batch.status = "posted"
        batch.posted_at = timezone.now()
        batch.certified_by_uploader = True
        batch.counts = selectors.read_batch_counts(batch)
        # DEF-MET-8106 — the receipt is KEPT, in the post's own transaction, so
        # a post that ran in a worker can hand it to the screen afterwards
        # (`GET /read-batches/{id}/post-receipt`) and a killed request cannot
        # leave a posted batch with no receipt at all.
        receipt = _post_receipt(batch, posted, skipped, superseded, blocking)
        batch.post_receipt = receipt
        batch.save(
            update_fields=[
                "status",
                "posted_at",
                "certified_by_uploader",
                "counts",
                "post_receipt",
                "updated_at",
            ]
        )
        _audit(
            actor,
            "read_batch.posted",
            "read_import_batch",
            batch.id,
            after={
                "posted_reads": len(posted),
                "skipped_rows": len(skipped),
                # CR-038 W7 — hard rule 7: every money action writes audit_log,
                # and a mode that CORRECTS readings a bill was priced from is
                # one. The premise and the count of readings it closed go into
                # the same row as the post itself, so an auditor reading
                # `read_batch.posted` never has to infer which mode ran.
                "write_mode": batch.write_mode,
                "superseded_reads": len(superseded),
                # ── BR-MET-940 — WHAT A PARTIAL POST LEFT BEHIND, IN THE
                # AUDIT ROW AND NOT ONLY IN THE RESPONSE ────────────────────
                # Before partial posting a batch with unresolved errors wrote
                # NO audit row at all, because it refused before it got here.
                # Now it posts, so the trail has to say how much of the file
                # actually became fact: `held_reads` is the count and
                # `unresolved_errors` is how many of those were rows nobody had
                # judged. An auditor reading `read_batch.posted` must never have
                # to infer that a "posted" batch filed 1,178 of 1,180.
                "held_reads": len(skipped),
                "unresolved_errors": len(blocking),
                "counts": batch.counts,
                "file_hash": batch.file_hash,
                "batch_no": batch.batch_no,
            },
        )
    # ── DEF-871 / OQ-690 — RESTATE THE MONTHS THIS BATCH TOUCHED ────────────
    # **THE TRANSACTION ABOVE HAS COMMITTED.** Every reading in `posted` is
    # durable before this line runs, which is the property that makes the
    # restatement unable to refuse a lawful post no matter what it meets.
    #
    # **ONE CALL PER DISTINCT ACCOUNT — never per row and never per month.**
    # `recompute_account` restates every month that account's reads support
    # from a single `_read_facts` walk, and `BR-MET-141`'s per-METER grain
    # rides inside the same call, which is the one constraint that ruling
    # attaches: *"both grains are written by ONE recompute_account call in ONE
    # transaction, so they can never be stale relative to each other"*. A
    # 1,247-row cycle over 900 accounts is therefore 900 calls, not 1,247.
    #
    # `dict.fromkeys` rather than a `set`: the accounts come out in the order
    # the batch posted them, so a partial refresh interrupted by a restart has
    # processed a PREFIX of the file rather than an arbitrary scatter — which
    # is the difference between "re-run it from row 400" and "re-run the lot".
    usage_accounts = list(dict.fromkeys(r.account_id for r in posted if r.account_id))
    # ── DEF-MET-8108 — THE REBUILD IS ITS OWN JOB, NOT THE TAIL OF THIS CALL ─
    # It ran here, inside the request, after the post had committed. That was
    # right about SAFETY (nothing it meets can un-post a reading) and wrong
    # about TIME: 480 accounts is ~10 statements each, and when the worker was
    # killed at 60 s the rebuild stopped at 267 of 480 with nothing recording
    # which accounts were left stale. It is now queued as `USAGE_REFRESH_JOB`,
    # which restates the accounts in order and writes a CHECKPOINT to its job
    # record every `USAGE_REFRESH_CHUNK` accounts — so a rebuild cut short is a
    # `running`/`failed` record naming where it stopped, and the kernel's own
    # resume (`core.jobs.resume`) carries on from there rather than from row 1.
    # The monthly usage is a summary nothing bills from (`BR-MET-141` clause
    # 6), which is what makes "restated a moment later" lawful.
    receipt.update(
        _enqueue_usage_refresh(
            actor, usage_accounts, trigger="read_batch.posted", entity_id=batch.id
        )
    )
    models.ReadImportBatch.objects.filter(tenant_id=_tenant_id(), pk=batch.id).update(
        post_receipt=receipt
    )
    result = selectors.read_batch_dict(batch)
    result.update(receipt)
    return result


def _post_receipt(
    batch: Any,
    posted: list[Any],
    skipped: list[dict[str, Any]],
    superseded: list[dict[str, Any]],
    blocking: list[int],
) -> dict[str, Any]:
    """What the post did — the figures the receipt prints, and ONLY those.

    Built inside the post's transaction and kept on the batch (`post_receipt`,
    `DEF-MET-8106`), so the synchronous answer and a background post's receipt
    are one dict built by one function. The batch's own fields
    (`read_batch_dict`) are NOT copied in: they are read fresh wherever the
    receipt is served, so a later co-sign is never shown stale.
    """
    receipt: dict[str, Any] = {}
    receipt["posted_reads"] = len(posted)
    # ── CR-038 W7 R2 — WHAT THE PREMISE ACTUALLY DID ────────────────────────
    # DEF-659's lesson applied to a second figure: a commit that CORRECTED 41
    # readings and one that ADDED 41 are different events, and until this line
    # both answered the identical `posted_reads: 41`.
    receipt["write_mode"] = batch.write_mode
    receipt["superseded_reads"] = len(superseded)
    receipt["superseded_rows"] = superseded[:50]
    # ── DEF-659: THE RESULT NEVER SAYS `posted` OVER READS THAT DID NOT LAND ──
    # `batch_status` is the PERSISTED truth and is unchanged — the row really is
    # `posted`, it is immutable (BR-MET-017) and the idempotency block above
    # depends on it. What changes is what this function TELLS ITS CALLER: a
    # commit that posted nothing answers `posted_nothing`, and every commit
    # carries the rows it skipped with the reason each was skipped.
    #
    # ⚠ WHAT THIS DELIBERATELY DOES NOT DO: refuse. Whether a batch whose rows
    # all skip should be REFUSED outright (BR-MET-015's posture for errors) is a
    # ruling, asked in DEF-659's row, and is not a lane's to take. This makes the
    # existing outcome legible; it does not change what the product allows.
    receipt["batch_status"] = batch.status
    receipt["skipped_reads"] = len(skipped)
    receipt["skipped_rows"] = skipped[:50]
    # ── BR-MET-940 — THE TWO NUMBERS THE COMMIT BUTTON HAS TO BE ABLE TO SAY ──
    # CR-054 task 15 asks the button to name its own number — *"Commit 1,178
    # rows"* — and the banner after it to be a statement of what happened rather
    # than a refusal. `held_reads` is the same figure as `skipped_reads` under
    # the name the ruling uses, and it is served ALONGSIDE rather than instead:
    # `skipped_reads` has been the contract since `DEF-659` and moving it would
    # blank a panel that reads it. `unresolved_errors` is the count that used to
    # REFUSE this call, so a screen can say *"2 rows still need a decision"*
    # about a post that has already filed the other 1,178.
    receipt["held_reads"] = len(skipped)
    receipt["held_rows"] = skipped[:50]
    receipt["unresolved_errors"] = len(blocking)
    # Where the held rows can be collected from. Stated rather than assumed by
    # the screen: `DEF-2487`'s finding was that the one moment a person most
    # needs the list of what failed was the moment the product would not give
    # it, because the download hung off a screen a failed commit never reached.
    receipt["rejects_download"] = f"/read-batches/{batch.id}/results.csv?kind=failures"
    if not posted:
        receipt["status"] = "posted_nothing"
    # ── BR-MET-130 — A CLERK MAY POST AN INCOMPLETE CYCLE, AND THE SHORTFALL
    # TRAVELS WITH THE RECEIPT ───────────────────────────────────────────────
    # PO 2026-08-26, verbatim: *"allow it"*. The worked case put to them: CY-001
    # holds 1,240 meters, the file carries 1,180, **60 unread**. Posting is
    # ALLOWED — the rule's own words — *"what is mandatory is the SHOWING"*.
    #
    # ⚠ **NOTHING WAS ADDED TO PERMIT IT, AND THAT IS THE HONEST FINDING.** The
    # lane looked for the gate BR-MET-130 supposedly opens and there was none:
    # no completeness predicate has ever stood between this function and the
    # post. So the rule RATIFIES existing behaviour on its first clause — the
    # same shape BR-MET-121 turned out to have — and what is BUILT here is its
    # second: the showing, carried onto the RECEIPT and not only onto the
    # review step W1 already built. A shortfall a clerk saw at stage 4 and
    # cannot see at stage 5 is a number they have to remember; the chase list
    # is what the 60 land on and the receipt is where it is named. A test pins
    # never-refuses so the absent gate cannot reappear as a "fix".
    receipt["cycle_coverage"] = completeness.batch_cycle_coverage(batch)
    if receipt["cycle_coverage"] is None:
        receipt["cycle_coverage_absent_reason"] = "batch_not_tagged_with_cycle"
    # DEF-MET-8106 — `async` said `False` with *"BR-MET-055 wrapper
    # outstanding"* until the wrapper existed. This dict is the SYNCHRONOUS
    # answer's; a deferred post answers `async: True` from
    # `_defer_read_batch_post` before this runs.
    receipt["async"] = False
    return receipt


def _enqueue_usage_refresh(
    actor: Any, account_ids: list[Any], *, trigger: str, entity_id: Any
) -> dict[str, Any]:
    """Queue the monthly-usage rebuild for these accounts (`DEF-MET-8108`).

    Answers the three facts the receipt carries about it — how many accounts,
    which job, and its state when this call returned (`queued` on a deployment
    with a worker; already `succeeded` or `failed` where `JOBS_EAGER` ran it
    in-process). Never raises into the post: the readings are committed, and a
    rebuild that could not even be queued is logged and reported as such
    rather than turned into a 500 over saved work (`BR-MET-129`).
    """
    # 🔒 DEF-MET-10163 — the accounts holding an estimate one of these readings
    # may now cover are rebuilt with them (`with_estimate_holders`).
    ids = monthly_usage_service.with_estimate_holders(account_ids)
    answer: dict[str, Any] = {
        "usage_refresh_accounts": len(ids),
        "usage_refresh_job_id": None,
        "usage_refresh_status": None,
    }
    if not ids:
        return answer
    try:
        record = core_jobs.enqueue(
            USAGE_REFRESH_JOB,
            payload={
                "account_ids": ids,
                "trigger": trigger,
                "entity_id": str(entity_id) if entity_id is not None else None,
                "actor_user_id": (
                    str(getattr(actor, "id", None)) if getattr(actor, "id", None) else None
                ),
            },
        )
    except core_jobs.JobsError:
        logger.exception(
            "monthly usage rebuild for %s account(s) could not be queued (%s %s) — "
            "run `manage.py backfill_monthly_usage` for them (DEF-MET-8108)",
            len(ids),
            trigger,
            entity_id,
        )
        answer["usage_refresh_status"] = "not_queued"
        return answer
    answer["usage_refresh_job_id"] = record["id"]
    answer["usage_refresh_status"] = core_jobs.current(record["id"])["status"]
    return answer


def run_usage_refresh_job(record: dict[str, Any]) -> str | None:
    """The monthly-usage rebuild, in a worker — RESUMABLE (`DEF-MET-8108`).

    Restates the payload's accounts in their posted order, `USAGE_REFRESH_CHUNK`
    at a time, through the same `_refresh_monthly_usage` the request used to
    call (its docstring holds the rules: one call per account, `OQ-358` months
    held and reported, any other fault held per account and audited). After
    each chunk the job record's checkpoint says how far it got, so:

      * a worker killed mid-way leaves a record whose checkpoint names the next
        account, and `core.jobs.resume` — what a redelivery calls — reclaims it
        and carries on from there, re-doing at most one chunk (each account's
        restatement is idempotent: it REPLACES that account's months);
      * a finished rebuild's checkpoint carries its totals, including the
        months it could not restate, which is the report `OQ-690` asks for.

    ⛔ Reaches no `@require_role` function (`G140`): this actor has no role.
    """
    payload = record["payload"]
    ids = list(payload.get("account_ids") or [])
    checkpoint = record.get("checkpoint") or {}
    start = int(checkpoint.get("next") or 0)
    totals = {
        "accounts_restated": int(checkpoint.get("accounts_restated") or 0),
        "months_not_restated": int(checkpoint.get("months_not_restated") or 0),
        "accounts_failed": int(checkpoint.get("accounts_failed") or 0),
    }
    actor = _PostJobActor(payload.get("actor_user_id"))
    for first in range(start, len(ids), USAGE_REFRESH_CHUNK):
        chunk = ids[first : first + USAGE_REFRESH_CHUNK]
        report = _refresh_monthly_usage(
            actor, chunk, trigger=payload.get("trigger") or USAGE_REFRESH_JOB,
            entity_id=payload.get("entity_id"), holders_added=True,
        )
        totals["accounts_restated"] += report["accounts_restated"]
        totals["months_not_restated"] += report["months_not_restated"]
        totals["accounts_failed"] += len(report["refresh_incomplete_accounts"])
        done = first + len(chunk)
        core_jobs.record_progress(
            record["id"], done=done, total=len(ids), checkpoint={"next": done, **totals}
        )
    return None


# ── CR-038 W7 task 5 — THE CO-SIGN, WHICH HAS BEEN SERVED AND UNWRITTEN ─────
#
# ⛔ **hard-won law 2, "built is not wired", at its longest running.**
# `read_import_batches.cosigned_by` shipped with migration 0003 on 2026-08-10,
# `selectors.read_batch_dict` has served it on every batch since, and **no code
# path in this product has ever written it**. S28's own docstring names the gap
# (*"no supervisor co-sign toggle … drawing the checkbox would offer a control
# that changes nothing"*) and CR-038's coverage map lists it as a W7 row. This
# function is the writer that column never had.
#
# **THE RULE IT IMPLEMENTS IS THE OQ-042 CLOSURE, QUOTED NOT SUMMARISED:**
# *"CLOSED — optional toggle default ON; supervisor = SysAdmin/Executive;
# blocks when enabled (PO R6)"*.
#
# Three clauses. This builds the two that need no surface another lane owns:
#   1. **who qualifies** — SysAdmin or Executive, and nobody else. Enforced by
#      `@require_role`, the same door every other role rule in this module uses.
#   2. **when it may be given** — while the batch is still STAGED or VALIDATED.
#      A posted batch is immutable (BR-MET-017); a co-sign added after the
#      readings landed would be a signature on a decision already taken, which
#      is the opposite of what a co-sign is for.
#   3. ⛔ **THE CO-SIGN IS RULED OUT. DO NOT FINISH THIS — 2026-09-14.**
#      PO, verbatim: *"we do not need confirmation or sign off from another
#      person"*. That REVERSES `OQ-042`'s own closure (*"optional toggle default
#      ON … blocks when enabled"*), which is why this comment is rewritten rather
#      than left with a note bolted on: a body that still describes the open world
#      is what sent three lanes wrong on 2026-09-05 (`DEF-WRK-4030`).
#      **`MR-17` is WITHDRAWN, not deferred**, and `DEF-815`'s `wontfix` is now
#      correct BY RULING rather than by default. The reasoning is the ICP's own —
#      this product is run by 10-20 staff and at the bottom tier by one or two,
#      and `OQ-WRK-1492` was ruled on that same ground: *"a two-person utility has
#      no supervisor sitting by the screen"*. A co-sign nobody present can give is
#      a commit that does not happen.
#      ⚠ **THIS FUNCTION HAS NEVER HAD A CALLER AND BY THIS RULING NEVER GETS
#      ONE.** It is left in place, unwired, because deleting it would also mean a
#      migration dropping `cosigned_by`/`cosigned_at` from a live table, which is
#      a different act needing its own ruling. They stay as lawful empty
#      containers. `commit_read_batch` does NOT block on a co-sign and must not
#      be made to.
@require_role(SYSTEM_ADMIN, EXECUTIVE, br_ref="BR-MET-055")
def cosign_read_batch(actor: Any, batch_id: Any) -> dict[str, Any]:
    """OQ-042's supervisor co-sign, recorded on the batch before it posts."""
    with transaction.atomic():
        batch = _batch_row(batch_id, locked=True)
        if batch.status == "posted":
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-MET-017",
                message_key="metering.read_batch.already_posted",
            )
        if batch.status == "discarded":
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-012",
                message_key="metering.read_batch.discarded",
            )
        batch.cosigned_by_id = getattr(actor, "id", None)
        batch.cosigned_at = timezone.now()
        batch.save(update_fields=["cosigned_by", "cosigned_at", "updated_at"])
        _audit(
            actor,
            "read_batch.cosigned",
            "read_import_batch",
            batch.id,
            after={
                "cosigned_by": str(batch.cosigned_by_id) if batch.cosigned_by_id else None,
                "cosigned_at": batch.cosigned_at.isoformat(),
                "batch_no": batch.batch_no,
                "rows": (batch.counts or {}).get("rows"),
            },
        )
    return selectors.read_batch_dict(batch)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def discard_read_batch(actor: Any, batch_id: Any) -> dict[str, Any]:
    """BR-MET-012/054: an explicit Cancel marks the batch `discarded`. The
    record is RETAINED for audit and never appears in Reads; staged rows are
    the only rows a delete may ever touch, and nothing committed exists yet."""
    with transaction.atomic():
        batch = _batch_row(batch_id, locked=True)
        if batch.status == "posted":
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-MET-017",
                message_key="metering.read_batch.already_posted",
            )
        batch.status = "discarded"
        batch.save(update_fields=["status", "updated_at"])
        _audit(
            actor,
            "read_batch.discarded",
            "read_import_batch",
            batch.id,
            after={"status": "discarded"},
        )
    return selectors.read_batch_dict(batch)


# ── CR-038 W9 task 1: the EVENT-READS write door (BR-MET-128/129, BR-CUS-021) ─


def _event_read_rows(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split an event payload's `reads` into KEYED rows (a value was read) and
    ESTIMATE rows (the meter could not be read — W9 task 8's disclosed path).

    A row is one dict per meter/register: `meter_no` (required), `read_at`
    (required, ISO date), then EITHER `value`/`reading` OR `estimate: true` —
    never both, never neither. `channel` defaults inside the parser to the flat
    meter's `total`. A meter the wizard left blank simply never reaches this
    payload: nothing is invented for it (CR-038 W9 task 3, verbatim — *"unread
    registers stay visible and nothing is invented"*).
    """
    fe: list[dict[str, Any]] = []
    keyed: list[dict[str, Any]] = []
    estimates: list[dict[str, Any]] = []
    rows = data.get("reads")
    if not isinstance(rows, list) or not rows:
        fe.append(_field_error("reads", errors.VAL_REQUIRED, "metering.event_reads.no_rows"))
        _refuse_fields(fe)
    for index, raw in enumerate(rows, start=1):
        row = raw if isinstance(raw, dict) else {}
        meter_no = _text(row.get("meter_no") or row.get("meter_id"), 80)
        read_at = _text(row.get("read_at") or row.get("read_date"), 40)
        value = row.get("value") if row.get("value") is not None else row.get("reading")
        wants_estimate = bool(row.get("estimate"))
        if not meter_no:
            fe.append(
                _field_error(
                    f"reads[{index}].meter_no", errors.VAL_REQUIRED, "metering.read.unknown_meter"
                )
            )
        if not read_at:
            fe.append(
                _field_error(
                    f"reads[{index}].read_at", errors.VAL_REQUIRED, "metering.read.read_at_required"
                )
            )
        if wants_estimate and value not in (None, ""):
            # Both a keyed value and an estimate request is a contradiction the
            # door refuses rather than picks between (never resolve a question
            # by choosing a value).
            fe.append(
                _field_error(
                    f"reads[{index}].estimate",
                    errors.VAL_FORMAT,
                    "metering.event_reads.value_and_estimate",
                )
            )
        elif wants_estimate:
            estimates.append(
                {
                    "meter_no": meter_no,
                    "read_at": read_at,
                    "channel": _text(row.get("channel"), 40) or models.CHANNEL_TOTAL,
                }
            )
        elif value in (None, ""):
            fe.append(
                _field_error(
                    f"reads[{index}].value", errors.VAL_REQUIRED, "metering.event_reads.no_value"
                )
            )
        else:
            keyed.append(
                {
                    "meter_no": meter_no,
                    "read_at": read_at,
                    "reading": str(value),
                    "channel": _text(row.get("channel"), 40) or "",
                    "note": _text(row.get("note"), 500) or "",
                }
            )
    _refuse_fields(fe)
    return keyed, estimates


def _refuse_unit_not_the_registers(data: dict[str, Any]) -> None:
    """**`DEF-WRK-4072` — the door READS `unit` when a caller sends one.**

    Until this check a row's `unit` was neither refused nor honoured: it was
    ignored, so a technician who read a demand register in kWh posted a figure
    that would be priced per kW (hard rule 3: a consumption never travels
    bare, and a WRONG unit is worse than a bare one). The unit that lands on
    the read is still the REGISTER's own (`register_units.register_unit`,
    `BR-MET-143`) — this is the CHECK beside it, for every caller.

    A row with no `unit` is not checked: the four account wizards send none
    and nothing about them changes. A meter this tenant does not hold is left
    to the pipeline, which already refuses it by name (`unknown_meter`). A
    register with no declared unit is left to the pipeline too — it refuses
    that rather than stamping a plausible one.
    """
    fe: list[dict[str, Any]] = []
    for index, raw in enumerate(data.get("reads") or [], start=1):
        row = raw if isinstance(raw, dict) else {}
        claimed = _text(row.get("unit"), 40)
        if not claimed:
            continue
        asset = seams.meter_by_no(_text(row.get("meter_no") or row.get("meter_id"), 80))
        if asset is None:
            continue
        channel = _text(row.get("channel"), 40) or models.CHANNEL_TOTAL
        stamped = register_units.register_unit(asset.unit, channel)
        if stamped and register_units.fold(stamped) != register_units.fold(claimed):
            fe.append(
                _field_error(
                    f"reads[{index}].unit",
                    errors.VAL_FORMAT,
                    "metering.event_reads.unit_not_the_registers",
                    register_unit=stamped,
                    measured_unit=claimed,
                    meter=getattr(asset, "asset_no", None),
                )
            )
    _refuse_fields(fe)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def commit_event_reads(actor: Any, payload: Any) -> dict[str, Any]:
    """**THE metering write door for EVENT READS — CR-038 W9 task 1.**

    BR-MET-128 (PO 2026-08-26), verbatim: *"it will be as per event - bascially
    we will ahve to create an record in reading that such reading ahs been
    colelcted - and it is generated due to that event; + plus the user"*. And
    BR-CUS-021 (PO closure batch 2026-08-08): *"Initial reads at
    new-account/move-in: per active meter, source AMI/manual/estimate,
    prior-final prefill, committed via the metering service (append-only
    BR-MET-017)"* — the metering half that never existed, which is why every
    wizard refused `initial_reads`/`final_reads` payloads until today.

    **AN EVENT READ IS AN ORDINARY COMMITTED READ.** Same pipeline, same 16
    rules: stage → validate → commit is `stage_read_batch` →
    `validate_read_batch` → `commit_read_batch`, in ONE transaction and one
    call path. The batch is MANUAL-shaped (`source_kind="manual"`, so the read
    lands `source="manual"` exactly like a typed S28 row) and additionally
    stamped with the EVENT — one of `models.EVENT_CONTEXTS`' values (five;
    eight since 2026-10-17, DEF-WRK-10184), on the staged batch, copied onto every committed read by `_post_row` AT
    INSERT (append-only, B2 r8 — a committed row is never updated to add it).
    The USER is the batch's `uploaded_by` — the acting user — landing on the
    read as `imported_by`; both render on the read detail (`read_dict`).

    **BR-MET-129 SEMANTICS (PO 2026-08-26, supersedes BR-MET-015's warning
    half):**

      (1) **WARNED rows POST, flagged.** PO verbatim: *"No if reading are
          colelcted we have to store the reading, we can give the warning, but
          we cannot reject the reading … otherwise, just tagging vacant and
          customer using utility services - never will be captured - there can
          be fraud also by people"*. No human pre-post disposition is required;
          this door records a MECHANICAL `accept_with_flag` whose reason names
          the rule, purely so the shared commit path posts the row — the flags
          themselves travel intact in `rule_outcomes` onto the committed read
          and are worked AFTER commit from the Reads list (clause 3). The
          vacant-unit warning is the expected case here: a move-in's opening
          read on a still-vacant unit warns and POSTS.
      (2) **ERRORS refuse, with named rows.** BR-MET-015's error half stands.
          The refusal names every failing row — row number, meter, value and
          the rules that failed — and, because everything runs in ONE
          transaction, NOTHING persists: not the batch, not the rows, not the
          estimates. The wizard shows the named rows with everything typed
          still on screen.

    **ESTIMATES (W9 task 8):** a row carrying `estimate: true` instead of a
    value routes through `estimate_missing_read` — the existing US-MET-014
    engine: disclosed method, consecutive-estimate cap, per register, that
    channel's OWN history — with the event context stamped. A refusal
    ("no history — field visit") comes back AS DATA beside the row, never as a
    silent zero and never as an invented value.

    **CERTIFICATION:** US-MET-010's uploader certification is given by this
    call — the acting user committing the wizard IS the person certifying the
    entry, one human act. **IDEMPOTENCY:** an event batch has no file, so
    BR-MET-018's file-hash block does not apply; the committed-duplicate rule
    is what refuses a re-submission — the same (meter, date, channel) again is
    an ERROR naming the existing read.

    **PUBLISHED FOR `apps.customers.seams.commit_event_reads`** — customers
    resolves it by name at call time (the `reads_for_unit` pattern, W9 task 2)
    and NEVER writes `meter_reads` itself (B1/B8). ⚠ **B2 §2 INTERFACE ROW
    OWED** — this lane may not edit `04-docs/`; flagged in the lane report.

    Payload::

        {"event": "move_in" | "move_out" | "transfer" | "disconnect"
                  | "new_connect" | "reconnect" | "meter_read"
                  | "exchange",         # BR-MET-128 (+3, DEF-WRK-10184)
         "reads": [{"meter_no", "read_at",
                    "value" | "estimate": true,
                    "channel"?, "note"?}, ...],
         "context"?: {...}}   # free audit context (unit/account ids), stored
                              # on the door's own audit row only

    Returns `{"event", "batch_id", "posted": [read_dict...], "posted_reads",
    "estimates": [...], "warnings": [{row_no, meter, rules}...]}`.
    """
    data = _payload_dict(payload)
    fe: list[dict[str, Any]] = []
    event = _text(data.get("event"), 40)
    if event not in models.EVENT_CONTEXTS:
        fe.append(_field_error("event", errors.VAL_FORMAT, "metering.event_reads.unknown_event"))
    _refuse_fields(fe)
    keyed, estimate_rows = _event_read_rows(data)
    _refuse_unit_not_the_registers(data)  # DEF-WRK-4072

    posted: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    estimates: list[dict[str, Any]] = []
    already_recorded: list[dict[str, Any]] = []
    batch = None
    with transaction.atomic():
        if keyed:
            first_day = min(row["read_at"] for row in keyed)
            staged = stage_read_batch(
                actor,
                {
                    "source_kind": "manual",
                    "period_month": first_day,
                    "rows": keyed,
                },
            )
            batch = _batch_row(staged["id"])
            # The event lands on the STAGED batch — mutable by BR-MET-012/017 —
            # so `_post_row` can stamp every read AT INSERT. This is the only
            # writer of `read_import_batches.event_context`.
            batch.event_context = event
            batch.save(update_fields=["event_context", "updated_at"])

            validate_read_batch(actor, batch.id)
            rows = list(
                models.ReadImportRow.objects.filter(tenant_id=_tenant_id(), batch=batch).order_by(
                    "row_no"
                )
            )
            # BR-MET-1189 (4) — the SAME reading arriving again (same meter,
            # date, register AND value) is not refused and not stored twice: it
            # is already in the register, and the door says so. A DIFFERENT
            # value that day is not an error at all any more; it posts.
            already = [row for row in rows if _is_already_recorded(row)]
            already_nos = {row.row_no for row in already}
            failing = [
                {
                    "row_no": row.row_no,
                    "meter_no": row.meter_no_raw,
                    "value": str(row.value) if row.value is not None else None,
                    "rules": [
                        {"rule": o.get("rule"), "detail": o.get("detail")}
                        for o in (row.rule_outcomes or [])
                        if o.get("severity") == validation.ERROR
                    ],
                }
                for row in rows
                if row.severity == validation.ERROR and row.row_no not in already_nos
            ]
            if failing:
                # BR-MET-129 (2): only errors refuse — and the refusal NAMES
                # the rows. The enclosing transaction rolls the staged batch
                # back, so a refused event commit leaves no debris.
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="BR-MET-129",
                    message_key="metering.event_reads.errors_refuse",
                    params={"event": event, "rows": failing[:50], "count": len(failing)},
                )
            for row in already:
                set_row_disposition(
                    actor,
                    batch.id,
                    row.row_no,
                    {
                        "disposition": "reject",
                        "reason": (
                            "BR-MET-1189: the same reading is already in the "
                            "register; nothing is added"
                        ),
                    },
                )
                already_recorded.append(
                    {
                        "row_no": row.row_no,
                        "meter_no": row.meter_no_raw,
                        "value": str(row.value) if row.value is not None else None,
                        "existing_read_id": _already_recorded_id(row),
                    }
                )
            for row in rows:
                if row.severity == validation.WARNING:
                    # BR-MET-129 (1): a warned reading POSTS. The disposition
                    # written here is MECHANICAL — the law's own clause, not a
                    # human judgment — recorded so the shared commit path posts
                    # the row while every flag travels onto the committed read.
                    set_row_disposition(
                        actor,
                        batch.id,
                        row.row_no,
                        {
                            "disposition": "accept_with_flag",
                            "reason": (
                                f"BR-MET-129: warned reading collected by event "
                                f"'{event}' posts with its flags; worked post-commit"
                            ),
                        },
                    )
                    warnings.append(
                        {
                            "row_no": row.row_no,
                            "meter_no": row.meter_no_raw,
                            "rules": [
                                {"rule": o.get("rule"), "detail": o.get("detail")}
                                for o in (row.rule_outcomes or [])
                                if o.get("severity") == validation.WARNING
                            ],
                        }
                    )
            result = commit_read_batch(actor, batch.id, {"certified": True})
            if result["skipped_reads"] > len(already_recorded):
                # DEF-659's lesson applied forward: this door NEVER answers
                # success over reads that did not land. With errors refused and
                # warnings dispositioned above, a skip here is a logic drift —
                # refuse loudly rather than report a partial post.
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-MET-129",
                    message_key="metering.event_reads.rows_skipped",
                    params={"event": event, "rows": result["skipped_rows"]},
                )
            committed = (
                models.MeterRead.objects.filter(tenant_id=_tenant_id(), import_batch=batch)
                .select_related("asset")
                .order_by("created_at")
            )
            posted = [selectors.read_dict(read) for read in committed]

        for spec in estimate_rows:
            # W9 task 8 — the DISCLOSED estimate path. `estimated: False` is a
            # refusal-as-data ("no history — field visit") the wizard shows
            # beside the meter; nothing is invented and no zero is silent.
            estimates.append(
                {
                    "meter_no": spec["meter_no"],
                    "channel": spec["channel"],
                    **estimate_missing_read(
                        actor,
                        {
                            "meter_no": spec["meter_no"],
                            "channel": spec["channel"],
                            "read_at": spec["read_at"],
                            "event_context": event,
                        },
                    ),
                }
            )

        if batch is not None:
            # The door-level trail row. An estimates-only call writes no batch,
            # and each estimate already audited itself (`read.estimated`, with
            # `event_context` in its payload) — a row against no entity would
            # be an orphaned write (BR-AUD-003's entity requirement).
            _audit(
                actor,
                "event_reads.committed",
                "read_import_batch",
                batch.id,
                after={
                    "event": event,
                    "context": data.get("context") or {},
                    "posted_reads": len(posted),
                    "estimates": [
                        {"meter_no": e["meter_no"], "estimated": e.get("estimated")}
                        for e in estimates
                    ],
                    "warnings": len(warnings),
                    "br_ref": "BR-MET-128",
                },
            )
    return {
        "event": event,
        "batch_id": str(batch.id) if batch is not None else None,
        "posted": posted,
        "posted_reads": len(posted),
        "estimates": estimates,
        "warnings": warnings,
        # BR-MET-1189 (4): readings that were already in the register with the
        # same value — not refused, not stored twice.
        "already_recorded": already_recorded,
    }


def _committed_same_value_errors(row: Any) -> list[dict[str, Any]]:
    return [
        o
        for o in (row.rule_outcomes or [])
        if o.get("severity") == validation.ERROR
        and o.get("rule") == validation.RULE_DUPLICATE
        and (o.get("detail") or {}).get("scope") == "committed"
        and (o.get("detail") or {}).get("same_value")
    ]


def _is_already_recorded(row: Any) -> bool:
    """BR-MET-1189 (4): the row's ONLY errors say this exact reading — same
    meter, date, register and value — is already in the register."""
    if row.severity != validation.ERROR:
        return False
    errors_on_row = [o for o in (row.rule_outcomes or []) if o.get("severity") == validation.ERROR]
    return bool(errors_on_row) and len(errors_on_row) == len(_committed_same_value_errors(row))


def _already_recorded_id(row: Any) -> str | None:
    found = _committed_same_value_errors(row)
    return (found[0].get("detail") or {}).get("existing_read_id") if found else None


# ── US-MET-013/016: supersede a committed read ──────────────────────────────


def _read_row(read_id: Any) -> Any:
    # `select_related` carries the asset and the DEF-045 linkage (CR-038 W5):
    # every caller renders the row through `selectors.read_dict`, which serves
    # cycle/route/service/premise — joined here so the detail read costs one
    # query instead of five lazy loads.
    row = (
        models.MeterRead.objects.filter(tenant_id=_tenant_id(), id=read_id)
        .select_related("asset", *selectors.READ_LINKAGE_RELATED)
        .first()
    )
    if row is None:
        raise errors.NotFoundError()
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def supersede_read(actor: Any, read_id: Any, payload: Any) -> dict[str, Any]:
    """BR-MET-024/053 — a correction is a NEW ROW. The original stays fully
    readable; only its two closure columns change.

    A BILLED read is refused HERE and routed (BR-MET-053 service-layer lock;
    US-MET-016 TC-4): the correction must travel with the money fix through the
    J6 path, which is `correct_billed_read` — the ONLY door, with no bypass.
    Silently superseding a billed read would leave an invoice priced from a
    value nothing points at any more.
    """
    data = _payload_dict(payload)
    reason = _text(data.get("reason"), 500)
    fe: list[dict[str, Any]] = []
    if not reason:
        fe.append(_field_error("reason", errors.VAL_REQUIRED, "metering.read.reason_required"))
    new_value = read_import._parse_decimal(str(data.get("value", "")))
    if new_value is None:
        fe.append(_field_error("value", errors.VAL_REQUIRED, "metering.read.value_required"))
    elif new_value < 0:
        fe.append(_field_error("value", errors.VAL_RANGE, "metering.read.value_negative"))
    _refuse_fields(fe)

    config = _config_set()  # CR-038 A1: a correction is judged per service
    with transaction.atomic():
        original = _read_row(read_id)
        if original.lifecycle == "billed":
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-MET-053",
                message_key="metering.read.billed_correction_required",
                params={"read_id": str(original.id)},
            )
        if original.superseded_by_id is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-053",
                message_key="metering.read.not_lineage_head",
                params={"superseded_by": str(original.superseded_by_id)},
            )
        replacement = _supersede_row(actor, original, new_value, reason, config)
        # BR-MET-126 (CR-038 W1b): the reading AFTER the corrected one is found
        # and handled in this same transaction — recomputed when unbilled,
        # recommended through the billed door when billed. See the cascade
        # section below `_supersede_row`.
        cascade = _cascade_after_correction(actor, original, replacement, config)
    # ── DEF-871 / OQ-690 — THE CORRECTION PATH RESTATES TOO ─────────────────
    # The withdrawn-fix comment named BOTH doors, and it was right to: a
    # correction changes what a month is worth just as surely as a new reading
    # does, and BR-MET-106 is explicit that *"corrections RESTATE, they never
    # edit"*. Leaving this door unwired would have fixed the chart for readings
    # posted from now on and left it wrong for every reading anybody FIXED.
    #
    # Outside the transaction, for the reason `_refresh_monthly_usage` sets out
    # in full: the replacement read is durable before the restatement starts,
    # so a month this account cannot summarise can never undo the correction a
    # clerk just made.
    #
    # The whole ACCOUNT rather than `recompute_month`, deliberately: a
    # correction can move a read's `read_at` into a different month, which
    # leaves TWO months wrong — the one it left and the one it joined — and the
    # narrow call only knows about one of them.
    usage_report = _refresh_monthly_usage(
        actor,
        [replacement.account_id] if replacement.account_id else [],
        trigger="read.superseded",
        entity_id=replacement.id,
    )
    result = selectors.read_dict(replacement)
    result["cascade"] = cascade
    result["usage_months_not_restated"] = usage_report["months_not_restated"]
    result["usage_months_not_restated_rows"] = usage_report["months_not_restated_rows"]
    result["usage_refresh_incomplete"] = usage_report["refresh_incomplete"]
    return result


# ── US-MET-013: the DISPUTE marker (BR-MET-024 · OQ-043 closure) ────────────
#
# DEF-046, the first of its three findings, verbatim: *"meter_reads carries
# disputed_at/dispute_reason/disputed_by, needs_attention_counts COUNTS
# disputes, and NO service or route ever sets one -- the chip can only ever read
# zero."* The columns shipped with migration 0003, the S25 chip has counted them
# since, the S29 footer drew a Dispute button DISABLED with that reason, and a
# customer could not raise one. The sample-data seeder refused to write the
# demo tenant's one disputed read straight to the table for exactly this reason
# (`sample_data._flag_disputed_read` looks this function up by name and logs its
# absence rather than faking the flag).
#
# THE RULE THIS IMPLEMENTS IS SIGNED AND IS QUOTED RATHER THAN SUMMARISED.
# BR-MET-024: *"**Dispute** records a dispute marker + reason on the read (feeds
# the S25 "disputes" count); v1 dispute flow per the OQ-043 closure (PO R6):
# record + flag, and the account is **HELD from the bill run until a System
# Admin clears** the dispute."* OQ-043's own closure row says the same in the
# register: *"CLOSED — v1: record+flag, hold account from run until SysAdmin
# clears (PO R6)"*.
#
# So there are exactly three acts, and this module builds all three:
#   1. RECORD   — marker + reason + actor, on the read. No value changes.
#   2. HOLD     — `dispute_holds_for_unit` (selectors) is what billing reads;
#                 `apps/billing/runs.prepare_run` blocks the account on it.
#   3. CLEAR    — System Admin only. The closure names the role and this is the
#                 one place in the module gated to it alone.
#
# ✅ **AND WHAT THE ALREADY-ISSUED BILL DOES IS RULED NOW — BR-MET-133, PO
# 2026-08-26, CLOSING OQ-245.** Every word of BR-MET-024 is forward-looking: it
# says what the NEXT run does and nothing about the invoice a disputed read
# ALREADY priced, which is the ordinary case, because a customer disputes a
# reading BECAUSE they got the bill. OQ-245 asked what happens there. PO
# verbatim: *"Bill stands, resolution through the billed-correction door, and
# the disputed amount doesn't age into late fees while open"*. Four clauses:
#   1. the issued invoice is NOT voided and NOT held — issued money stays
#      (hard rule 4), and nothing here touches it;
#   2. the marker holds the account out of the NEXT run (unchanged);
#   3. resolution goes through the billed-correction door — right → supersede
#      plus the money correction it opens; wrong → clear the marker, the bill
#      was always correct;
#   4. while the dispute is open the DISPUTED AMOUNT does not age and attracts
#      no late fee, and the undisputed remainder ages normally
#      (`apps/billing/late_fee.ageable_portion` + `apps/billing/dispute_ageing`).
# `billed_bill_effect` on the response says all of that in a clerk's words.
# ⚠ Clause 4 is built for a bill whose disputed AMOUNT is known, and nothing in
# this product records one — **OQ-420**, refused rather than defaulted.
#
# NOTHING HERE WEAKENS THE BILLED LOCK. `supersede_read` still refuses a billed
# read and `correct_billed_read` is still the only door (BR-MET-053). A dispute
# is an ORTHOGONAL marker in that same rule's own words — "disputed→cleared" —
# and metering migration 0007's trigger deliberately leaves the marker columns
# free to move while freezing the MEASUREMENT (asset · read_at · channel ·
# prior/current value · multiplier · consumption · unit). That narrowing of B2
# r8 is reported and unresolved as **OQ-209**, and this function relies on it
# rather than restating it.

#: The sentence every surface repeats when the disputed read is already BILLED.
#: A CODE, never prose alone: the screen renders its own copy from it and a grep
#: for the value finds every place that says it.
#:
#: ⚠ **RENAMED AND RE-VALUED 2026-08-26 — it used to be
#: `DISPUTE_BILLED_UNRULED = "issued_bill_untouched_oq_245"`, and both halves
#: were wrong the moment BR-MET-133 was confirmed.** The name said the case was
#: unruled and the value named a question that is now CLOSED, so every surface
#: rendering it was telling a clerk that nobody had decided what a dispute does
#: to a bill already sent. It has been decided. The old value is deliberately
#: NOT kept as an alias: a code that means "unruled" surviving the ruling is
#: exactly the shape of hard-won law 1.
DISPUTE_BILLED_STANDS = "issued_bill_stands_br_met_133"


def _dispute_state(read: Any) -> dict[str, Any]:
    """The marker as every consumer sees it — one shape, one place.

    `active` is the exact condition `needs_attention_counts` counts and
    `dispute_holds_for_unit` holds on: a marker that is set and not cleared.
    """
    active = read.disputed_at is not None and read.dispute_cleared_at is None
    return {
        "disputed": active,
        "disputed_at": read.disputed_at.isoformat() if read.disputed_at else None,
        "dispute_reason": read.dispute_reason,
        "disputed_by": str(read.disputed_by_id) if read.disputed_by_id else None,
        "dispute_cleared_at": (
            read.dispute_cleared_at.isoformat() if read.dispute_cleared_at else None
        ),
        "dispute_cleared_by": (
            str(read.dispute_cleared_by_id) if read.dispute_cleared_by_id else None
        ),
        # BR-MET-024/OQ-043: the hold is the whole consequence in v1, and it is
        # stated on the response so a clerk learns it at the moment they raise
        # the dispute rather than when a bill run mysteriously skips them.
        "holds_bill_run": active,
        # BR-MET-133. Present only when it applies, so a surface cannot render
        # the sentence about an unbilled read.
        "billed_bill_effect": (
            DISPUTE_BILLED_STANDS if active and read.lifecycle == "billed" else None
        ),
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def dispute_read(actor: Any, read_id: Any, payload: Any) -> dict[str, Any]:
    """BR-MET-024 — record the dispute marker + reason. NOTHING ELSE CHANGES.

    US-MET-013 TC-3, verbatim: *"Dispute marker + reason stored; S25 header
    dispute count and the Disputed KPI chip (US-MET-019) increment; audit row;
    no value change; the account is held from the bill run until a System Admin
    clears the dispute (OQ-043 closure)"*.

    "No value change" is enforced by what this function writes: three marker
    columns and nothing else. The register reading, the consumption, the unit
    and the status are untouched, so a disputed read still reads exactly as the
    meter said — which is the point. A dispute is a claim ABOUT a number, not a
    correction OF one; correcting it is `supersede_read` (unbilled) or
    `correct_billed_read` (billed), each with its own reason and its own row.

    Refuses, each rather than half-doing the job:
      · no reason — TC-3 stores one and BR-MET-024 requires it; a marker with no
        reason tells the System Admin who must clear it nothing at all;
      · a read that is not the lineage head — dispute the CURRENT version, not a
        superseded one, or the hold would hang off a row no consumer resolves
        (BR-MET-016);
      · a read already carrying an UNCLEARED marker — the second dispute would
        silently overwrite the first one's reason and actor, and the account is
        already held, so there is nothing to gain and a trail to lose.
    """
    data = _payload_dict(payload)
    reason = _text(data.get("reason"), 500)
    if not reason:
        _refuse_fields(
            [_field_error("reason", errors.VAL_REQUIRED, "metering.read.dispute_reason_required")]
        )

    with transaction.atomic():
        read = _read_row(read_id)
        if read.superseded_by_id is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-016",
                message_key="metering.read.dispute_not_head",
                params={"superseded_by": str(read.superseded_by_id)},
            )
        if read.disputed_at is not None and read.dispute_cleared_at is None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-024",
                message_key="metering.read.already_disputed",
                params={"disputed_at": read.disputed_at.isoformat()},
            )
        before = _dispute_state(read)
        read.disputed_at = timezone.now()
        read.dispute_reason = reason
        read.disputed_by_id = getattr(actor, "id", None)
        # A RE-dispute after a clearance starts a fresh marker: the closure
        # columns are reset so `active` is true again and the S25 chip counts
        # it. The previous cycle survives in the audit trail, which is where a
        # history of markers belongs — `meter_reads` holds ONE marker by B2 r8's
        # column set, and inventing a dispute-history table is a story, not a
        # choice a service function makes.
        read.dispute_cleared_at = None
        read.dispute_cleared_by_id = None
        read.save(
            update_fields=[
                "disputed_at",
                "dispute_reason",
                "disputed_by",
                "dispute_cleared_at",
                "dispute_cleared_by",
                "updated_at",
            ]
        )
        _audit(
            actor,
            "read.disputed",
            "meter_read",
            read.id,
            before=before,
            after={
                **_dispute_state(read),
                # The number under dispute, so the trail says WHAT was disputed
                # and not merely that something was. Rule 3: never the bare
                # figure — `usage_display` carries its unit.
                "usage_display": (quantity_display.quantity_with_unit(read.consumption, read.unit)),
                "lifecycle": read.lifecycle,
                # ⚠ WAS `"open_question": "OQ-245"`. That question is CLOSED
                # (BR-MET-133, PO 2026-08-26) and the trail now records the
                # RULE the bill is standing under, not a question about it.
                # ⚠ AND THE KEY IS `br_ref` SINCE DEF-2377, for the reason its
                # sibling in `clear_dispute` carries: a MACHINE field the S61
                # presenter drops, so a clerk is never shown a rule id. THIS
                # SITE WAS MISSED BY THE FIRST PASS AND THE TEST CAUGHT IT —
                # `g71_audit_payload_prose` reads string CONSTANTS and this
                # value is a conditional expression, which is the gate's stated
                # "a value composed at run time still passes here" in the flesh.
                "br_ref": "BR-MET-133" if read.lifecycle == "billed" else None,
            },
        )
    result = selectors.read_dict(read)
    result["dispute"] = _dispute_state(read)
    return result


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-024")
def clear_read_dispute(actor: Any, read_id: Any, payload: Any = None) -> dict[str, Any]:
    """OQ-043's closure, second half: *"until a System Admin clears"*.

    THE ROLE GATE IS THE RULE, not a convenience. `@require_role(SYSTEM_ADMIN)`
    with no clerk in the list is the only such gate in this module's read
    surface, and it is there because the closure names that role and because
    clearing is what releases the account back into the bill run. The endpoint
    carries `SystemAdminOnly` as well — defence in depth, BR-SHL-025.

    A `resolution` note is ACCEPTED AND OPTIONAL, and it lands in the audit row
    rather than on the read. B2 r8 gives `meter_reads` `dispute_cleared_at` and
    `dispute_cleared_by` and NO cleared-reason column; adding one is a schema
    change a story signs, so the note goes where an append-only trail already
    takes free text.

    ✅ **"CLEARED" IS ONE OF THE TWO OUTCOMES, AND BR-MET-133 CLAUSE 3 SAYS
    WHICH ONE (PO 2026-08-26, closing OQ-245).** Verbatim: *"resolution through
    the billed-correction door"* — *"she is right → supersede + the money
    correction it opens; she is wrong → clear the marker, the bill was always
    correct"*. So a dispute ends two ways and they take two different doors:

      * **the customer is right** → `correct_billed_read` (BR-MET-053 /
        US-MET-016), which supersedes the reading and opens the money
        correction. NOT this verb.
      * **the customer is wrong** → THIS verb. Clearing records that the
        reading stands and the bill was always correct, and it deliberately
        opens no correction.

    This docstring said the two outcomes were unruled and that clearing
    recorded no verdict; the second half is still literally true of the SCHEMA
    (B2 r8 gives no outcome column, and adding one is a story's schema change),
    but the AMBIGUITY is gone — clearing now has exactly one meaning, and the
    S29 modal says it in the clerk's words before they press the button.
    """
    data = _payload_dict(payload) if payload is not None else {}
    resolution = _text(data.get("resolution"), 500)

    with transaction.atomic():
        read = _read_row(read_id)
        if read.disputed_at is None or read.dispute_cleared_at is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-024",
                message_key="metering.read.no_active_dispute",
                params={"read_id": str(read.id)},
            )
        before = _dispute_state(read)
        read.dispute_cleared_at = timezone.now()
        read.dispute_cleared_by_id = getattr(actor, "id", None)
        read.save(update_fields=["dispute_cleared_at", "dispute_cleared_by", "updated_at"])
        _audit(
            actor,
            "read.dispute_cleared",
            "meter_read",
            read.id,
            before=before,
            after={
                **_dispute_state(read),
                "resolution": resolution,
                # BR-MET-133 clause 3 (PO 2026-08-26, closing OQ-245): clearing
                # IS the "the reading stands, the bill was always correct"
                # outcome. The other outcome takes `correct_billed_read`, not
                # this verb. Recorded as a VALUE rather than left null: the
                # trail used to say `"outcome": None, "open_question": "OQ-245"`
                # — a verdict withheld because none was signed. One is now.
                "outcome": "reading_stands",
                # `br_ref` and not `billed_bill_rule`: a MACHINE field the S61
                # presenter drops, so a clerk reading the audit log is not shown
                # a rule id (DEF-2377, the DEF-322 `data-br-ref` precedent).
                "br_ref": "BR-MET-133",
            },
        )
    result = selectors.read_dict(read)
    result["dispute"] = _dispute_state(read)
    return result


# ── US-MET-016: the BILLED read's correction flow (J6 linkage) ──────────────


#: `source_detail` of an estimate a BILL made (DEF-BIL-8280): the clerk's
#: estimate from a bill run's Check decision, saved into the register at issue.
BILLED_ESTIMATE_SOURCE = "billing_estimate"
BILLED_ESTIMATE_METHOD = "clerk_decision"


def record_billed_estimate(
    *,
    unit_id: Any,
    service_code: str,
    read_on: date,
    consumption: Any,
    unit: str,
    invoice_id: Any,
    bill_run_id: Any = None,
    decided_by_id: Any = None,
    asset_id: Any = None,
    actor: Any = None,
) -> dict[str, Any]:
    """Save a clerk's BILLED estimate into this meter's reading history.

    🔒 HUMAN-REVIEW-PENDING (money path — ledger section *"DEF-BIL-8280"*).
    PO direction 2026-09-30 (`07-billing/16-check-decisions-next-bill.md`):
    *at ISSUE, write each clerk estimate from a Check decision into Meter Reads
    THROUGH METERING'S OWN SERVICE as an ESTIMATED reading on that meter and
    date, tagged with run, bill and clerk — so it appears in reading history,
    usage and disputes and Meter Reads' existing true-up (BR-MET-029) subtracts
    it at the next real reading.* Worked: Aug 1,000 · Sep estimate 5 billed ·
    Oct reads 1,012 → the October read trues up to **7**, not 12.

    **Called by billing, never written by it** (B1): billing's seam calls this
    from inside the issue transaction. The row is the estimate row
    `estimate_missing_read` writes — no register value (BR-MET-028), the
    consumption and its EXPLICIT unit — and it is locked BILLED against the
    invoice at once, so it is corrected through the billed-read path like any
    read a bill priced.

    **No role check, on purpose:** issue runs in a background job whose actor
    carries no role (G140); the role was checked when the run was released.

    Idempotent on (meter, date, invoice): a re-issue finds its own row.
    Answers `{"recorded": bool, "read_id"?, "problem"?}` and never raises for a
    missing meter — a bill must not break on it (BR-BIL-055); it is reported.
    """
    service_point = (
        models.ServicePoint.objects.filter(
            tenant_id=_tenant_id(), unit_id=unit_id, service__code=service_code
        )
        .order_by("id")
        .first()
    )
    if asset_id is None:
        if service_point is None:
            return {"recorded": False, "problem": "no_service_point"}
        in_service = seams.in_service_asset_ids_for_service_point(service_point.id)
        candidates = list(in_service if in_service is not None else ())
        if len(candidates) != 1:
            return {"recorded": False, "problem": "meter_not_single"}
        asset_id = candidates[0]
    asset = seams.meter_by_id(asset_id)
    if asset is None:
        return {"recorded": False, "problem": "no_meter"}
    channel = models.CHANNEL_TOTAL
    register_unit = register_units.register_unit(asset.unit, channel)
    if not unit or (register_unit and unit != register_unit):
        # CLAUDE.md rule 3 — the estimate's unit IS the unit of the lineage it
        # joins, or the true-up would subtract kWh from therms.
        return {"recorded": False, "problem": "unit_mismatch"}
    read_at = read_import._parse_date(read_on.isoformat())
    tag = f"{BILLED_ESTIMATE_SOURCE}:{invoice_id}"
    existing = (
        _head_qs()
        .filter(asset_id=asset.id, channel=channel, read_at=read_at, source_detail=tag)
        .first()
    )
    if existing is not None:
        return {"recorded": False, "read_id": str(existing.id), "problem": None}
    prior = _prior_actual_head(asset.id, channel, read_at)
    with transaction.atomic():
        read = models.MeterRead.objects.create(
            tenant_id=_tenant_id(),
            asset=asset,
            route_id=collection_route_id(asset),
            account_id=collection_account_id(asset),
            read_at=read_at,
            channel=channel,
            period_start=prior.read_at.date() if prior is not None else None,
            period_end=read_on,
            prior_value=None,
            current_value=None,  # BR-MET-028: an estimate carries NO register value
            multiplier=asset.multiplier,
            consumption=_num6(Decimal(str(consumption))),
            unit=unit,
            source="estimated",
            source_detail=tag,
            status="estimated",
            lifecycle="committed",
            days_since_prior=(read_on - prior.read_at.date()).days if prior is not None else None,
            rule_outcomes=[
                {
                    "rule": "estimate",
                    "severity": validation.OK,
                    "detail": {
                        "method": BILLED_ESTIMATE_METHOD,
                        "bill_run_id": None if bill_run_id is None else str(bill_run_id),
                        "invoice_id": str(invoice_id),
                        "decided_by_id": None if decided_by_id is None else str(decided_by_id),
                    },
                }
            ],
            estimation_method=BILLED_ESTIMATE_METHOD,
        )
        mark_read_billed(read.id, invoice_id)
        _audit(
            actor,
            "read.estimated",
            "meter_read",
            read.id,
            after={
                "meter": asset.asset_no,
                "channel": channel,
                "consumption": str(consumption),
                "unit": unit,
                "method": BILLED_ESTIMATE_METHOD,
                "bill_run_id": None if bill_run_id is None else str(bill_run_id),
                "invoice_id": str(invoice_id),
                "decided_by_id": None if decided_by_id is None else str(decided_by_id),
            },
        )
        # 🔒 DEF-MET-10163 — the estimate's month is restated once the issue
        # transaction commits, like any reading: it joins the month's sum, or —
        # where a later actual already covers its days — is left out of it
        # (`monthly_usage.covered_estimate_ids`). After commit, so a rebuild
        # can never touch the bill (BR-MET-141 clause 6: nothing bills off it).
        if read.account_id is not None:
            transaction.on_commit(
                lambda account_id=read.account_id: _restate_after_estimate(actor, account_id, read.id)
            )
    return {"recorded": True, "read_id": str(read.id), "problem": None}


def _restate_after_estimate(actor: Any, account_id: Any, read_id: Any) -> None:
    """Queue the monthly-usage rebuild for a billed estimate's account.

    Never raises into the caller (an issue that has already committed):
    `_enqueue_usage_refresh` reports a rebuild it could not queue, and anything
    else is logged — the usage is a derived cache `backfill_monthly_usage`
    rebuilds (BR-MET-141 clause 6), the bill is the money."""
    try:
        _enqueue_usage_refresh(
            actor, [account_id], trigger="read.billed_estimate", entity_id=read_id
        )
    except Exception:  # noqa: BLE001 — a committed issue is never failed by a cache
        logger.exception("monthly usage rebuild after billed estimate %s not queued", read_id)


def mark_read_billed(read_id: Any, invoice_id: Any = None) -> bool:
    """Move a committed read to lifecycle BILLED — the lock BR-MET-053 names.

    PUBLISHED FOR BILLING, and the reason it lives here is B1: `meter_reads` is
    metering's table, so billing calls this rather than writing the column. It
    resolves by name through billing's seam pattern, exactly like every other
    cross-module call in this product.

    ⚠ **NOTHING CALLS THIS YET, and that is stated rather than left to be
    discovered** (hard-won law 2 — "built is not wired"). The BILLED lock and
    the whole correction flow below are dead weight until `apps/billing` calls
    it at issue time, for every read its invoice was priced from. That edit is
    in billing's territory and is REPORTED, not made from this lane. Until it
    lands, a read that HAS been billed still reads as `committed`, so a clerk
    correcting it takes the plain supersede path and no J6 linkage is recorded —
    which is precisely the failure US-MET-016 exists to prevent, and precisely
    why the gap is written down here instead of in a comment somewhere.

    Idempotent: marking an already-billed read changes nothing and answers
    False, so a re-issue cannot double-lock or raise. A SUPERSEDED row is not
    markable either — billing prices lineage heads (BR-MET-016/053), so locking
    a closed version would lock the wrong number.
    """
    updated = models.MeterRead.objects.filter(
        tenant_id=_tenant_id(),
        id=read_id,
        lifecycle="committed",
        superseded_by_id__isnull=True,
    ).update(lifecycle="billed")
    return updated > 0


def _read_correction_payload(data: dict[str, Any]) -> tuple[str, Any, Any]:
    """The three things a billed-read correction cannot proceed without."""
    fe: list[dict[str, Any]] = []
    reason = _text(data.get("reason"), 500)
    if not reason:  # TC-7: no reason → no write, no audit row
        fe.append(_field_error("reason", errors.VAL_REQUIRED, "metering.read.reason_required"))
    new_value = read_import._parse_decimal(str(data.get("value", "")))
    if new_value is None:
        fe.append(_field_error("value", errors.VAL_REQUIRED, "metering.read.value_required"))
    elif new_value < 0:
        fe.append(_field_error("value", errors.VAL_RANGE, "metering.read.value_negative"))
    invoice_id = data.get("invoice_id")
    if not invoice_id:
        fe.append(_field_error("invoice_id", errors.VAL_REQUIRED, "metering.read.invoice_required"))
    _refuse_fields(fe)
    return reason, new_value, invoice_id


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def correct_billed_read(actor: Any, read_id: Any, payload: Any) -> dict[str, Any]:
    """BR-MET-053: the ONLY way a BILLED read is ever corrected.

    "Read fix and money fix travel together." Two things happen in ONE
    transaction and neither can happen without the other:

      1. the read is SUPERSEDED — a new lineage head, the original closed with
         `superseded_by_id`/`superseded_at` and still fully visible (rule 4:
         nothing is edited, nothing is deleted);
      2. a `read_corrections` row is written naming the read PAIR and the
         INVOICE — the row J6 step 1 consumes.

    **The invoice is not touched.** Metering records a reference and stops; the
    credit note, the rebill and the class-R/C/D decision are billing's story
    (J6 amended 2026-08-11 → BR-BIL-041). The invoice id is verified through the
    billing seam first, so the linkage cannot name a bill that does not exist or
    belongs to another tenant — but this module never writes to it.

    Refuses (rather than quietly doing half the job) when:
      · the read is NOT billed — use `supersede_read`, the plain path; opening a
        correction against no invoice would fabricate a money event;
      · the read is not the lineage head — correct the head, not history;
      · billing cannot resolve the invoice (seam unpublished, or unknown id).
    """
    data = _payload_dict(payload)
    reason, new_value, invoice_id = _read_correction_payload(data)

    config = _config_set()  # CR-038 A1: a billed correction is judged per service
    with transaction.atomic():
        original = _read_row(read_id)
        if original.lifecycle != "billed":
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-053",
                message_key="metering.read.not_billed",
                params={"read_id": str(original.id), "lifecycle": original.lifecycle},
            )
        if original.superseded_by_id is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-053",
                message_key="metering.read.not_lineage_head",
                params={"superseded_by": str(original.superseded_by_id)},
            )
        invoice = seams.invoice_ref(invoice_id)
        if invoice is None:
            # The seam REPORTS that it cannot answer; it never substitutes one
            # (G20 / DEF-075). A correction whose invoice cannot be verified is
            # not a correction that travels with the money.
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-MET-053",
                message_key="metering.read.invoice_unresolvable",
                params={"invoice_id": str(invoice_id)},
            )

        replacement = _supersede_row(actor, original, new_value, reason, config)
        linkage = models.ReadCorrection.objects.create(
            tenant_id=_tenant_id(),
            superseded_read_id=original.id,
            superseding_read_id=replacement.id,
            invoice_id=invoice_id,
            invoice_no=invoice.get("invoice_no"),
            asset_id=original.asset_id,
            channel=original.channel,
            reason=reason,
            status="open",
            opened_by_id=getattr(actor, "id", None),
        )
        # The pair ↔ invoice link, in the trail (US-MET-016 §5).
        _audit(
            actor,
            "read.billed_correction_opened",
            "read_correction",
            linkage.id,
            before={
                "read_id": str(original.id),
                "current_value": str(original.current_value),
                "consumption": str(original.consumption),
                "unit": original.unit,
            },
            after={
                "superseding_read_id": str(replacement.id),
                "current_value": str(replacement.current_value),
                "consumption": str(replacement.consumption),
                "unit": replacement.unit,
                "invoice_id": str(invoice_id),
                "invoice_no": invoice.get("invoice_no"),
                "reason": reason,
                "status": "open",
            },
        )
        # BR-MET-126 (CR-038 W1b): a billed correction moves the register too,
        # so the SAME cascade runs from this door — including the resume after
        # a cascade earlier stopped at this read's own billed boundary.
        cascade = _cascade_after_correction(actor, original, replacement, config)
    # DEF-871 / OQ-690 — the BILLED-correction door restates the same way the
    # unbilled one does. `BR-MET-141` clause (6) is what makes this safe to do
    # after the money work rather than with it: *"Nothing bills off it — no
    # rate, no invoice line and no charge reads this table"*, so a stale usage
    # month cannot mis-price the credit note or the rebill this call opens.
    usage_report = _refresh_monthly_usage(
        actor,
        [replacement.account_id] if replacement.account_id else [],
        trigger="read.billed_corrected",
        entity_id=replacement.id,
    )
    result = selectors.read_dict(replacement)
    result["correction"] = selectors.read_correction_dict(linkage)
    result["cascade"] = cascade
    result["usage_months_not_restated"] = usage_report["months_not_restated"]
    result["usage_months_not_restated_rows"] = usage_report["months_not_restated_rows"]
    result["usage_refresh_incomplete"] = usage_report["refresh_incomplete"]
    return result


def _supersede_row(actor: Any, original: Any, new_value: Any, reason: str, config: Any) -> Any:
    """Create the replacement head and close the original (BR-MET-024/053).

    Extracted so `supersede_read` and `correct_billed_read` cannot drift: the
    lineage mechanics are identical, and only the ROUTING differs between an
    unbilled correction and a billed one.
    """
    asset = original.asset
    ctx = _build_context(
        asset=asset,
        read_at=original.read_at,
        channel=original.channel,
        value=new_value,
        config=config,
    )
    consumption, outcomes = validation.evaluate_row(ctx, config)  # BR-MET-022 re-run
    new_id = core_dbfields.uuid7()
    previous = _close_head(actor, asset.id, original.read_at, original.channel, new_id, reason)
    replacement = models.MeterRead.objects.create(
        id=new_id,
        tenant_id=_tenant_id(),
        asset=asset,
        # DEF-233 — a correction INHERITS the original's stamp rather than
        # re-resolving it. Re-resolving would silently re-date the provenance:
        # correcting a 2025 read after the meter moved route would move the
        # history onto today's route and off the one that was actually read.
        # Falls back to resolution only for a pre-0012 original with no stamp.
        route_id=original.route_id or collection_route_id(asset),
        account_id=original.account_id,
        read_at=original.read_at,
        channel=original.channel,
        period_start=original.period_start,
        period_end=original.period_end,
        prior_value=ctx.prior_value,
        current_value=new_value,
        multiplier=asset.multiplier,
        consumption=_num6(consumption),
        # BR-MET-143 — the REGISTER's unit (`ctx.unit`), never the meter's. A
        # correction to a demand read stays in kW; before 2026-08-27 it landed
        # back in the meter's kWh and re-created DEF-797's label on the
        # replacement head.
        unit=ctx.unit,
        source=original.source,
        source_detail=original.source_detail,
        # A correction is a NEW ROW for the SAME collection - the method is a
        # fact about who read the meter, which a corrected figure never changes.
        read_method=original.read_method,
        # CR-161-BRC10 W4 — and so are the utility's own answers about it (a
        # seal number does not change because the figure was mistyped).
        custom_data=dict(original.custom_data or {}),
        status=validation.primary_status(outcomes),
        lifecycle="committed",  # the NEW head is not itself billed yet
        days_since_prior=original.days_since_prior,
        rule_outcomes=validation.as_json(outcomes),
        import_batch=original.import_batch,
        imported_by_id=getattr(actor, "id", None),
        supersede_reason=reason,
    )
    if previous is not None:
        _audit_supersede(actor, previous, replacement, reason)
    # CR-182-BRC10 — a correction that is still high is not emailed twice; one
    # that is no longer high simply has no flag, which closes the portal alert.
    high_consumption.notify_if_flagged(replacement, replaced=original, actor=actor)
    return replacement


# ── BR-MET-126 (CR-038 W1b): the correction cascade ─────────────────────────
#
# THE RULE THIS IMPLEMENTS IS SIGNED AND IS QUOTED RATHER THAN SUMMARISED.
# BR-MET-126 (PO 2026-08-26, CONFIRMED — closes the Blueprint's Open 10), PO
# verbatim: *"(b) auto-recompute when the next reading is still unbilled; flag
# it through the billed-correction door when it's billed - but we cant cahnge
# the source data, so we will ahve to accept the trust and make the
# recomendation"*. Three clauses, built here:
#   (1) after a supersede the next reading on the same meter and register is
#       found IN THE SAME TRANSACTION (the walk below runs inside the door's
#       own `transaction.atomic()` block);
#   (2) an UNBILLED stale reading is recomputed automatically — as a
#       SUPERSEDING CORRECTION ROW (hard rule 4; the original stays visible,
#       closed with the two closure columns and nothing else), marked
#       system-generated in `rule_outcomes` and naming the correction that
#       triggered it (the BR-AST-029 missing-export row set this precedent:
#       a self-describing outcome entry, never a new column);
#   (3) a BILLED stale reading is NEVER rewritten — it is FLAGGED as a
#       RECOMMENDATION carrying the worked delta, and `correct_billed_read`
#       (the ONLY billed door, BR-MET-053) is how a human takes it through.
#
# The worked case (the acceptance test, proven red first —
# tests/test_cr038_w1b_cascade.py): Dec 31 reads 4,200; Jan 31 reads 5,000,
# superseded to 5,200; Feb 28 reads 5,800. Without the cascade February kept
# prior 5,000 / consumption 800, so the heads billed 1,000 + 800 = 1,800
# against 1,600 actually used — 200 units charged twice.
#
# WHAT "EVALUATED THE SAME WAY" MEANS HERE (the bounded loop): the walk visits
# every following lineage head in `read_at` order, not just the first, because
# a correction's consumption change reaches further than its register change —
# a later ESTIMATE averages the corrected read's consumption (BR-MET-026) and
# a later TRUE-UP actual subtracts estimates the cascade itself recomputed
# (BR-MET-029). A head is STALE only when the correction actually reached it:
# an actual whose stored `prior_value` no longer matches the register it
# measures from, or whose `trues_up_read_ids` name a row this cascade closed;
# an estimate whose trailing-3 window contains a row this cascade (or the
# triggering correction) replaced. Anything else is left alone — recomputing
# an untouched historical row with today's asset multiplier or today's config
# would rewrite history for reasons that are not this correction's.
#
# WHERE THE CASCADE STOPS, deliberately: at the end of the chain; at a BILLED
# stale reading (clause 3 — everything past it would be recomputed from a
# number a human has not yet confirmed, so the human's `correct_billed_read`
# resumes the cascade from there); at an estimate the estimation service
# REFUSES to recompute (BR-MET-026's own refusal reasons — flag, never raw
# subtraction); or at the chain-limit backstop. Every stop is named in the
# `cascade` summary the door returns.

#: rule name on the system-generated replacement row (grep-able, like OQ ids)
RULE_CASCADE_RECOMPUTED = "cascade_recomputed"
#: rule name of the RECOMMENDATION outcome on a billed stale reading
RULE_CASCADE_STALE = "cascade_stale_billed"
#: BR-MET-126 clause-3 primary status for a billed stale ACTUAL — what puts it
#: into `needs_attention_counts["flagged"]` with no new counting machinery.
#: NEVER applied to an estimate: `_standing_estimates` and the BR-MET-029
#: true-up count standing estimates BY `status="estimated"`.
CASCADE_STATUS_STALE = "stale_prior"
#: bounded-loop backstop — 240 monthly heads is twenty years of one register.
CASCADE_CHAIN_LIMIT = 240
#: the sentence every surface repeats for the billed recommendation — a CODE
#: plus its rule, never prose alone (the DISPUTE_BILLED_STANDS posture).
CASCADE_BILLED_RECOMMENDATION = "metering.read.cascade_billed_recommendation"


def _cascade_reason(trigger_id: Any) -> str:
    return f"BR-MET-126 cascade — system recompute after correction {trigger_id}"


def _cascade_marker(
    stale: Any, trigger_id: Any, new_prior: Any, new_consumption: Any, unit: Any
) -> dict[str, Any]:
    """The system-generated stamp (clause 2: 'marked system-generated and
    naming the correction that triggered it')."""
    return {
        "rule": RULE_CASCADE_RECOMPUTED,
        "severity": validation.OK,
        "detail": {
            "br_ref": "BR-MET-126",
            "system_generated": True,
            "triggered_by_read_id": str(trigger_id),
            "superseded_read_id": str(stale.id),
            "previous_prior_value": _figure_str(stale.prior_value),
            "previous_consumption": _figure_str(stale.consumption),
            "new_prior_value": _figure_str(new_prior),
            "new_consumption": _figure_str(new_consumption),
            "unit": unit,
        },
    }


def _cascade_flag(
    actor: Any,
    stale: Any,
    trigger_id: Any,
    expected_prior: Any,
    new_consumption: Any,
    summary: dict[str, Any],
    *,
    boundary: str,
    refusal: str | None = None,
) -> None:
    """Clause 3 — the RECOMMENDATION. The row's measurement is not touched
    (hard rule 4 + the 0007 trigger); the flag lands in the marker columns the
    trigger deliberately leaves free, exactly as the dispute marker does."""
    delta = None
    if stale.consumption is not None and new_consumption is not None:
        delta = stale.consumption - new_consumption
    detail = {
        "br_ref": "BR-MET-126",
        "system_generated": True,
        "triggered_by_read_id": str(trigger_id),
        "previous_status": stale.status,
        "stale_prior_value": _figure_str(stale.prior_value),
        "expected_prior_value": _figure_str(expected_prior),
        "stored_consumption": _figure_str(stale.consumption),
        "recomputed_consumption": _figure_str(new_consumption),
        "delta": _figure_str(delta),
        "unit": stale.unit,
        # The way through: the billed door for a billed read (BR-MET-053 —
        # "the read fix and the money fix travel together"); an estimate the
        # service refused to recompute goes to a human reviewer instead.
        "door": "correct_billed_read" if stale.lifecycle == "billed" else "manual_review",
        "message_key": CASCADE_BILLED_RECOMMENDATION,
    }
    if refusal:
        detail["estimation_refusal"] = refusal
        detail["message_key"] = "metering.read.cascade_estimate_unrecomputable"
    summary["flagged"].append(str(stale.id))
    summary["stopped"] = boundary

    outcomes = list(stale.rule_outcomes or [])
    previous_flags = [o for o in outcomes if o.get("rule") == RULE_CASCADE_STALE]
    if previous_flags:
        last = previous_flags[-1].get("detail", {})
        if (
            last.get("expected_prior_value") == detail["expected_prior_value"]
            and last.get("recomputed_consumption") == detail["recomputed_consumption"]
        ):
            return  # the same recommendation already stands — nothing new to say
    outcomes.append({"rule": RULE_CASCADE_STALE, "severity": validation.WARNING, "detail": detail})
    updates: dict[str, Any] = {"rule_outcomes": outcomes, "updated_at": timezone.now()}
    # ACTUALS only get the primary-status flag (see CASCADE_STATUS_STALE).
    if stale.current_value is not None:
        updates["status"] = CASCADE_STATUS_STALE
    models.MeterRead.objects.filter(
        tenant_id=_tenant_id(), id=stale.id, read_at=stale.read_at
    ).update(**updates)
    _audit(  # hard rule 7 — a recommendation about money-bearing state is a money action
        actor,
        "read.cascade_recommendation",
        "meter_read",
        stale.id,
        before={
            "status": stale.status,
            "prior_value": _figure_str(stale.prior_value),
            "consumption": _figure_str(stale.consumption),
            "unit": stale.unit,
        },
        after=detail,
    )


def _cascade_evaluate_actual(
    actor: Any,
    stale: Any,
    trigger_id: Any,
    closed_ids: set[str],
    summary: dict[str, Any],
    config: Any,
) -> tuple[str, Any]:
    """One following ACTUAL head. Stale iff the correction reached it: its
    stored prior no longer matches the register it measures from, or its
    true-up names an estimate row this cascade closed. The recompute mirrors
    `_post_row` — BR-MET-022 re-run PLUS the BR-MET-029 true-up, because a
    cascade that dropped a standing true-up would 'fix' one error with
    another."""
    asset = stale.asset
    prior = _prior_actual_head(stale.asset_id, stale.channel, stale.read_at)
    expected_prior = prior.current_value if prior is not None else None
    trues_touched = bool({str(x) for x in (stale.trues_up_read_ids or [])} & closed_ids)
    if expected_prior == stale.prior_value and not trues_touched:
        return "current", None

    ctx = _build_context(
        asset=asset,
        read_at=stale.read_at,
        channel=stale.channel,
        value=stale.current_value,
        config=config,
    )
    consumption, outcomes = validation.evaluate_row(ctx, config)
    standing = _standing_estimates(stale.asset_id, stale.channel, stale.read_at)
    trued = estimation.true_up(
        estimation.TrueUpInput(
            channel=stale.channel,
            # BR-MET-143 — the REGISTER's unit, matching `ctx.unit` above.
            unit=ctx.unit,
            actual_register=stale.current_value,
            last_actual_register=prior.current_value if prior else None,
            multiplier=asset.multiplier,
            estimated_consumptions=[e.consumption for e in standing if e.consumption is not None],
            estimated_read_ids=[str(e.id) for e in standing],
        )
    )
    outcome_json = validation.as_json(outcomes)
    trues_up_ids = None
    if trued.applies:
        consumption = trued.quantity
        trues_up_ids = trued.corrects_read_ids
        outcome_json = outcome_json + [
            {"rule": "true_up", "severity": validation.OK, "detail": trued.as_dict()}
        ]
    new_consumption = _num6(consumption) if consumption is not None else None
    if expected_prior == stale.prior_value and new_consumption == stale.consumption:
        return "current", None  # value-identical correction — nothing to restate

    if stale.lifecycle == "billed":
        _cascade_flag(
            actor,
            stale,
            trigger_id,
            expected_prior,
            new_consumption,
            summary,
            boundary="billed_boundary",
        )
        return "flagged", None

    reason = _cascade_reason(trigger_id)
    new_id = core_dbfields.uuid7()
    previous = _close_head(actor, stale.asset_id, stale.read_at, stale.channel, new_id, reason)
    replacement = models.MeterRead.objects.create(
        id=new_id,
        tenant_id=_tenant_id(),
        asset=asset,
        # DEF-233 — a correction INHERITS the original's stamp (same as
        # `_supersede_row`), so the cascade cannot re-date provenance.
        route_id=stale.route_id or collection_route_id(asset),
        account_id=stale.account_id,
        read_at=stale.read_at,
        channel=stale.channel,
        period_start=stale.period_start,
        period_end=stale.period_end,
        prior_value=ctx.prior_value,
        current_value=stale.current_value,  # the SOURCE register — never changed here
        multiplier=asset.multiplier,
        consumption=new_consumption,
        # BR-MET-143 — the REGISTER's unit, the one this row was judged under.
        unit=ctx.unit,
        source=stale.source,
        source_detail=stale.source_detail,
        read_method=stale.read_method,  # same collection, recomputed figure
        status=validation.primary_status(outcomes),
        lifecycle="committed",  # the new head is not itself billed yet
        days_since_prior=stale.days_since_prior,
        rule_outcomes=outcome_json
        + [_cascade_marker(stale, trigger_id, ctx.prior_value, new_consumption, ctx.unit)],
        import_batch_id=stale.import_batch_id,
        imported_by_id=getattr(actor, "id", None),
        supersede_reason=reason,
        trues_up_read_ids=trues_up_ids,
        demand_reset_noted=stale.demand_reset_noted,
        custom_data=dict(stale.custom_data or {}),  # CR-161-BRC10 W4 — same collection
        is_sample=stale.is_sample,  # BR-TEN-061 deletes on this predicate
    )
    if previous is not None:
        _audit_supersede(actor, previous, replacement, reason)
    _audit(
        actor,
        "read.cascade_recomputed",
        "meter_read",
        replacement.id,
        before={
            "read_id": str(stale.id),
            "prior_value": _figure_str(stale.prior_value),
            "consumption": _figure_str(stale.consumption),
            "unit": stale.unit,
        },
        after={
            "prior_value": _figure_str(ctx.prior_value),
            "consumption": _figure_str(new_consumption),
            "unit": ctx.unit,  # BR-MET-143 — the register's, not the meter's
            "triggered_by_read_id": str(trigger_id),
            "br_ref": "BR-MET-126",
        },
    )
    summary["recomputed"].append(str(replacement.id))
    # CR-182-BRC10 — a recompute can newly flag a reading as high.
    high_consumption.notify_if_flagged(replacement, replaced=stale, actor=actor)
    return "recomputed", replacement


def _cascade_evaluate_estimate(
    actor: Any,
    stale: Any,
    trigger_id: Any,
    replacement_ids: set[str],
    summary: dict[str, Any],
) -> tuple[str, Any]:
    """One following ESTIMATE head — recomputed through the estimation
    service's OWN math (BR-MET-026 trailing-3 daily average), NEVER by raw
    register subtraction: an estimate has no register (BR-MET-028), so there
    is nothing to subtract and pretending otherwise would invent one."""
    asset = stale.asset
    inputs = list(
        _head_qs()
        .filter(
            asset_id=stale.asset_id,
            channel=stale.channel,
            read_at__lt=stale.read_at,
            current_value__isnull=False,
            consumption__isnull=False,
        )
        .order_by("-read_at")[: estimation.TRAILING_WINDOW]
    )
    if not any(str(row.id) in replacement_ids for row in inputs):
        return "current", None  # its trailing window never saw the correction

    result = estimation.estimate(
        estimation.EstimationInput(
            channel=stale.channel,
            # BR-MET-143 — the REGISTER's unit. BR-MET-062 refuses a demand
            # estimate outright, so this never resolves to kW today; it is
            # written correctly anyway, because the next maximum register to
            # join `MAXIMUM_REGISTERS` must not have to find this line.
            unit=register_units.register_unit(asset.unit, stale.channel),
            days_in_period=stale.days_since_prior,
            trailing_actuals=[(row.consumption, row.days_since_prior or 0) for row in inputs],
            consecutive_estimates=len(
                _standing_estimates(stale.asset_id, stale.channel, stale.read_at)
            ),
        ),
        _read_config(),  # estimation params live on the tenant row (CR-038 A1 scope)
    )
    if not result.estimated:
        # The boundary the estimation service itself declares — flag, report,
        # stop. Recomputing around its refusal would author a second method.
        _cascade_flag(
            actor,
            stale,
            trigger_id,
            None,
            None,
            summary,
            boundary="estimation_boundary",
            refusal=result.reason,
        )
        return "flagged", None

    new_consumption = _num6(result.consumption)
    if new_consumption == stale.consumption:
        return "current", None
    if stale.lifecycle == "billed":
        _cascade_flag(
            actor,
            stale,
            trigger_id,
            None,
            new_consumption,
            summary,
            boundary="billed_boundary",
        )
        return "flagged", None

    reason = _cascade_reason(trigger_id)
    new_id = core_dbfields.uuid7()
    previous = _close_head(actor, stale.asset_id, stale.read_at, stale.channel, new_id, reason)
    replacement = models.MeterRead.objects.create(
        id=new_id,
        tenant_id=_tenant_id(),
        asset=asset,
        route_id=stale.route_id or collection_route_id(asset),
        account_id=stale.account_id,
        read_at=stale.read_at,
        channel=stale.channel,
        period_start=stale.period_start,
        period_end=stale.period_end,
        prior_value=None,
        current_value=None,  # BR-MET-028: an estimate carries NO register value
        multiplier=asset.multiplier,
        consumption=new_consumption,
        unit=result.unit or asset.unit,  # explicit, always
        source="estimated",
        source_detail=stale.source_detail,
        status="estimated",
        lifecycle="committed",
        days_since_prior=result.days_in_period,
        rule_outcomes=[
            {"rule": "estimate", "severity": validation.OK, "detail": result.as_dict()},
            _cascade_marker(stale, trigger_id, None, new_consumption, result.unit or asset.unit),
        ],
        import_batch_id=stale.import_batch_id,
        imported_by_id=getattr(actor, "id", None),
        supersede_reason=reason,
        estimation_method=result.method,
        consecutive_estimate_no=result.consecutive_no,
        is_sample=stale.is_sample,
    )
    if previous is not None:
        _audit_supersede(actor, previous, replacement, reason)
    _audit(
        actor,
        "read.cascade_recomputed",
        "meter_read",
        replacement.id,
        before={
            "read_id": str(stale.id),
            "consumption": _figure_str(stale.consumption),
            "unit": stale.unit,
        },
        after={
            "consumption": _figure_str(new_consumption),
            "unit": replacement.unit,
            "method": result.method,
            "triggered_by_read_id": str(trigger_id),
            "br_ref": "BR-MET-126",
        },
    )
    summary["recomputed"].append(str(replacement.id))
    return "recomputed", replacement


def _cascade_after_correction(
    actor: Any, original: Any, replacement: Any, config: Any
) -> dict[str, Any]:
    """BR-MET-126 — walk the chain after a correction, inside the caller's
    transaction. Returns the summary the door attaches as `cascade` so the
    clerk sees what the system did the moment they did it (never silently)."""
    summary: dict[str, Any] = {
        "br_ref": "BR-MET-126",
        "evaluated": 0,
        "recomputed": [],
        "flagged": [],
        "stopped": None,
    }
    closed_ids = {str(original.id)}
    replacement_ids = {str(replacement.id)}
    trigger_id = replacement.id  # the correction row every cascade row names
    current = replacement
    for _step in range(CASCADE_CHAIN_LIMIT):
        nxt = (
            _head_qs()
            .filter(
                asset_id=current.asset_id,
                channel=current.channel,
                read_at__gt=current.read_at,
            )
            .order_by("read_at")
            .select_related("asset")
            .first()
        )
        if nxt is None:
            summary["stopped"] = summary["stopped"] or "end_of_chain"
            break
        summary["evaluated"] += 1
        if nxt.current_value is None and nxt.status == "estimated":
            verdict, new_head = _cascade_evaluate_estimate(
                actor, nxt, trigger_id, replacement_ids, summary
            )
        elif nxt.current_value is None:
            # A registerless non-estimate (the BR-AST-029 zero-export record):
            # it measures from nothing, so it cannot be stale — walk past it.
            verdict, new_head = "current", None
        else:
            verdict, new_head = _cascade_evaluate_actual(
                actor, nxt, trigger_id, closed_ids, summary, config
            )
        if verdict == "flagged":
            break  # boundary named by _cascade_flag; a human resumes from here
        if verdict == "recomputed":
            closed_ids.add(str(nxt.id))
            replacement_ids.add(str(new_head.id))
            current = new_head
        else:
            current = nxt
    else:
        summary["stopped"] = "chain_limit"
    return summary


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def delete_staged_read_row(actor: Any, row_id: Any) -> dict[str, Any]:
    """BR-MET-054 delete scope, and the whole of it: a STAGED or REJECTED row of
    an un-posted batch. Nothing else in this module has a delete path.

    A committed `meter_reads` row has none — not here, not in the API, not in
    the database (metering 0007's trigger refuses DELETE outright). The batch
    keeps its audit trail: the batch record and its compliance stamp survive the
    row (BR-MET-012/017), and the deletion is itself audited.
    """
    with transaction.atomic():
        row = models.ReadImportRow.objects.filter(tenant_id=_tenant_id(), id=row_id).first()
        if row is None:
            raise errors.NotFoundError()
        batch = row.batch
        if batch.status == "posted":
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-MET-054",
                message_key="metering.read_row.batch_posted",
                params={"batch_id": str(batch.id)},
            )
        if row.meter_read_id is not None:
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-MET-054",
                message_key="metering.read_row.committed",
                params={"read_id": str(row.meter_read_id)},
            )
        snapshot = {
            "row_no": row.row_no,
            "meter_no": row.meter_no_raw,
            "channel": row.channel,
            "value": str(row.value) if row.value is not None else None,
            "severity": row.severity,
            "disposition": row.disposition,
        }
        row.delete()
        _audit(actor, "read_row.deleted", "read_import_row", row_id, before=snapshot)
    return {"deleted": True, "batch_id": str(batch.id), **snapshot}


# ── US-MET-014: estimate a missing read (per channel) ───────────────────────


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def estimate_missing_read(actor: Any, payload: Any) -> dict[str, Any]:
    """BR-MET-026/027/058/062 — fill ONE missing (meter, channel) record.

    The arithmetic is estimation.py's; this function supplies that channel's
    OWN actual history (never another channel's — BR-MET-058) and persists the
    result. A refusal is returned as data with its reason, not raised: "no
    history — field visit" is an answer the clerk must see beside the row.

    QUANTITY ONLY. The estimated consumption is priced later by rating at
    current-period rates (GT-9's money side); nothing here reads a rate.
    """
    data = _payload_dict(payload)
    fe: list[dict[str, Any]] = []
    asset = seams.meter_by_no(_text(data.get("meter_no"), 80)) if data.get("meter_no") else None
    if asset is None and data.get("asset_id"):
        asset = seams.meter_by_id(data["asset_id"])
    if asset is None:
        fe.append(
            _field_error("meter_no", errors.VAL_UNKNOWN_LOOKUP, "metering.read.unknown_meter")
        )
    channel = _text(data.get("channel"), 40) or models.CHANNEL_TOTAL
    if channel not in models.CHANNELS:
        fe.append(_field_error("channel", errors.VAL_FORMAT, "metering.read.channel_unknown"))
    read_at = read_import._parse_date(str(data.get("read_at") or ""))
    if read_at is None:
        fe.append(_field_error("read_at", errors.VAL_REQUIRED, "metering.read.read_at_required"))
    # BR-MET-128 (W9 task 8): an estimated EVENT read is generated by its event
    # too — the context is validated against EVENT_CONTEXTS (DEF-WRK-10184) and
    # stamped AT INSERT below, beside the acting user. Absent = an ordinary
    # estimation (unchanged behaviour).
    event_context = _text(data.get("event_context"), 40)
    if event_context is not None and event_context not in models.EVENT_CONTEXTS:
        fe.append(
            _field_error("event_context", errors.VAL_FORMAT, "metering.event_reads.unknown_event")
        )
    _refuse_fields(fe)

    config = _read_config()
    prior = _prior_actual_head(asset.id, channel, read_at)
    standing = _standing_estimates(asset.id, channel, read_at)
    days = data.get("days_in_period")
    if days is None and prior is not None:
        reference = standing[-1].read_at if standing else prior.read_at
        days = (read_at.date() - reference.date()).days
    spec = estimation.EstimationInput(
        channel=channel,
        # BR-MET-143 — the REGISTER's unit (BR-MET-062 refuses demand here).
        unit=register_units.register_unit(asset.unit, channel),
        days_in_period=int(days) if days is not None else None,
        trailing_actuals=_trailing_actuals(asset.id, channel, read_at, limit=3),
        consecutive_estimates=len(standing),
    )
    result = estimation.estimate(spec, config)
    if not result.estimated:
        return {"estimated": False, **result.as_dict()}

    with transaction.atomic():
        read = models.MeterRead.objects.create(
            tenant_id=_tenant_id(),
            asset=asset,
            # DEF-233 — an ESTIMATE is read history too: BR-MET-079 asks whether
            # the route was read, and a route whose meters were all estimated
            # still has a record that deleting it would orphan.
            route_id=collection_route_id(asset),
            account_id=collection_account_id(asset),  # DEF-658
            read_at=read_at,
            channel=channel,
            period_start=prior.read_at.date() if prior is not None else None,
            period_end=read_at.date(),
            prior_value=None,
            current_value=None,  # BR-MET-028: an estimate carries NO register value
            multiplier=asset.multiplier,
            consumption=_num6(result.consumption),
            unit=result.unit or asset.unit,  # explicit, always
            source="estimated",  # BR-MET-028 "distinct from actuals"
            status="estimated",
            lifecycle="committed",
            days_since_prior=result.days_in_period,
            rule_outcomes=[
                {"rule": "estimate", "severity": validation.OK, "detail": result.as_dict()}
            ],
            estimation_method=result.method,
            consecutive_estimate_no=result.consecutive_no,
            # BR-MET-128 — the event and its user, stamped at insert on the
            # EVENT path only. An ordinary estimation keeps its old shape
            # (event_context NULL, imported_by NULL) so nothing already
            # counting estimates changes meaning underneath its reader.
            event_context=event_context,
            imported_by_id=(getattr(actor, "id", None) if event_context is not None else None),
        )
        _audit(
            actor,
            "read.estimated",
            "meter_read",
            read.id,
            after={
                "meter": asset.asset_no,
                "channel": channel,
                "consumption": str(result.consumption),
                "unit": read.unit,
                "method": result.method,
                "consecutive_no": result.consecutive_no,
                "inputs": result.detail,
                "event_context": event_context,
            },
        )
    return {"estimated": True, **selectors.read_dict(read)}


# ── CR-038 W5 task 7 · BULK OPERATIONS ON THE READS LIST ────────────────────
#
# PO verbatim, 2026-08-26: *"We will need bulk operation; also note read are
# for perticualr period and they need to be part of read cycle or bill cycle -
# how we are going to keep the sanity"*.
#
# ⚠ **AND THE PO'S OTHER SENTENCE, THE ONE THAT SHAPES EVERY LINE BELOW**
# (2026-08-26, on speed against accountability, verbatim):
#
#     *"keep the rule — speed comes from the bulk button… an auditor asking
#      'who chose to estimate M-4412?' gets a name"*
#
# So a bulk action here is a LOOP OVER ROWS THAT EACH GET THE FULL TRAIL, never
# one statement that touches many rows anonymously. Each row it touches carries
# `fixed_by` (the acting user) and `fix_reason`, and each writes its own
# `audit_log` row. The speed the PO asked for is the CLERK'S — one click
# instead of forty — and it is not bought with a `bulk_update`.
#
# WHY THIS CLOSES DEF-046's SECOND FINDING, OPEN SINCE 2026-08-11:
# *"fix_disposition/fix_reason/fixed_by exist with no writer and no route, so
# US-MET-012 TC-3..7 have nothing to call"*. Three columns, in the schema and
# in `selectors.read_dict`'s served field list, that nothing ever wrote —
# hard-won law 2 in the data layer. These are their writer.
#
# ⚠ **A FIX DISPOSITION CHANGES NO VALUE, AND THAT IS WHY IT MAY BE WRITTEN IN
# PLACE.** `MeterRead` law 2 says the only UPDATE a committed row accepts is
# the supersede pair — and `dispute_read` already establishes the reading that
# makes both true: a MARKER about a reading is not a correction OF one. The
# register value, the consumption, the unit and the status are untouched here,
# exactly as they are by a dispute. Anything that would change the number goes
# through `supersede_read` (unbilled) or `correct_billed_read` (billed), each
# with its OWN per-row reason — which is precisely why neither is bulk below.

#: The ONE bulk disposition, and the boundary is deliberate.
#:
#: CR-038's ADDITION section names the bulk actions and this lane does not
#: invent others: *"bulk-accept flagged reads WITH ONE REASON (recorded per
#: row), bulk-estimate the missing set …, bulk clear-selection to export"*.
#:
#: BR-MET-023 lists more fix verbs per flag (override · investigate · check ·
#: field-visit · prorate · change-multiplier). **None of them belongs on a bulk
#: button, and the reason is one sentence:** an override is a SUPERSEDE, which
#: needs a new value and its own reason for each individual read, and a bulk
#: control that took one reason for forty different readings would be recording
#: a sentence that is untrue of thirty-nine of them. Accept is the one verb
#: whose meaning survives being said once about a set — *"I have looked at
#: these flags and they are fine"* — which is the same shape the bill run's
#: BR-BIL-060 bulk apply already has.
BULK_FIX_ACCEPT = "accept"
BULK_FIX_DISPOSITIONS: tuple[str, ...] = (BULK_FIX_ACCEPT,)

#: The estimate half writes this disposition on the rows it CREATES, so the
#: trail says a human chose to estimate them in bulk and names who.
BULK_FIX_ESTIMATE = "estimate"

#: One page of the reads list is 100 rows at most (`PAGE_SIZES`), and a
#: select-all across pages is not offered. 500 leaves room for a clerk who
#: filtered hard and selected everything, and refuses the shape nobody meant to
#: submit. A cap is not a performance guard here — it is a blast-radius guard
#: on an action that writes an audit row per read.
BULK_MAX_ROWS = 500


def _bulk_reason(data: dict[str, Any]) -> str:
    """The ONE reason, required. CR-038: *"bulk-accept flagged reads WITH ONE
    REASON (recorded per row)"* — and a disposition with no reason tells the
    next reader of the row nothing at all, which is `dispute_read`'s own
    refusal for the same absence."""
    reason = _text(data.get("reason"), 500)
    if not reason:
        _refuse_fields(
            [_field_error("reason", errors.VAL_REQUIRED, "metering.reads.bulk.reason_required")]
        )
    return reason  # type: ignore[return-value]


def _bulk_ids(data: dict[str, Any], field: str) -> list[Any]:
    raw = data.get(field)
    ids = [v for v in (raw if isinstance(raw, list) else []) if v not in (None, "")]
    if not ids:
        _refuse_fields(
            [_field_error(field, errors.VAL_REQUIRED, "metering.reads.bulk.selection_required")]
        )
    if len(ids) > BULK_MAX_ROWS:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-023",
            message_key="metering.reads.bulk.too_many",
            params={"selected": len(ids), "max": BULK_MAX_ROWS},
        )
    return ids


def _stamp_fix(actor: Any, read: Any, *, disposition: str, reason: str) -> None:
    """Write the three fix columns and the audit row — the PO's NAME, per row.

    `update_fields` names exactly the marker columns, so this statement
    physically cannot carry a value change into a committed read even if a
    caller had mutated one on the instance.
    """
    before = {
        "fix_disposition": read.fix_disposition,
        "fix_reason": read.fix_reason,
        "fixed_by": str(read.fixed_by_id) if read.fixed_by_id else None,
    }
    read.fix_disposition = disposition
    read.fix_reason = reason
    read.fixed_by_id = getattr(actor, "id", None)
    read.save(update_fields=["fix_disposition", "fix_reason", "fixed_by", "updated_at"])
    _audit(
        actor,
        "read.fix_dispositioned",
        "meter_read",
        read.id,
        before=before,
        after={
            "fix_disposition": read.fix_disposition,
            "fix_reason": read.fix_reason,
            "fixed_by": str(read.fixed_by_id) if read.fixed_by_id else None,
            "status": read.status,
            # Rule 3: never the bare figure — what was dispositioned, with its
            # unit, so the trail is readable a year later.
            "usage_display": (quantity_display.quantity_with_unit(read.consumption, read.unit)),
        },
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def bulk_fix_reads(actor: Any, payload: Any) -> dict[str, Any]:
    """Accept a SET of flagged reads with one reason, recorded on every row.

    **BR-MET-129 is why there is anything here to accept** (PO 2026-08-26,
    verbatim): *"No if reading are colelcted we have to store the reading, we
    can give the warning, but we cannot reject the reading, when reading are
    colelcted then only we will know whether there is usage or not; otherwise,
    just tagging vacant and customer using utility services - never will be
    captured - there can be fraud also by people"*. Clause 3 of that rule:
    *"The flags are worked AFTER commit from the Reads list"*. The reading is
    already in the ledger of facts; this is a person saying they have looked.

    **Nothing here can hold a reading out of billing, and nothing here posts
    one.** A warned read was already posted (BR-MET-129 clause 1) and stays
    posted whether or not anyone accepts it. Accepting records a judgment; it
    does not gate money in either direction.

    Every outcome is DATA, per row: a refused row comes back named beside the
    accepted ones rather than 500-ing the whole click, because a clerk who
    selected forty rows of which two were superseded needs the thirty-eight
    done and the two explained.
    """
    data = _payload_dict(payload)
    reason = _bulk_reason(data)
    disposition = _text(data.get("disposition"), 40) or BULK_FIX_ACCEPT
    if disposition not in BULK_FIX_DISPOSITIONS:
        _refuse_fields(
            [
                _field_error(
                    "disposition", errors.VAL_FORMAT, "metering.reads.bulk.disposition_unknown"
                )
            ]
        )
    read_ids = _bulk_ids(data, "read_ids")

    applied: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for read_id in read_ids:
        with transaction.atomic():
            read = (
                models.MeterRead.objects.filter(tenant_id=_tenant_id(), id=read_id)
                .select_related("asset")
                .first()
            )
            if read is None:
                refused.append({"read_id": str(read_id), "reason": "not_found"})
                continue
            if read.superseded_by_id is not None:
                # BR-MET-016: consumers work the lineage HEAD. Dispositioning a
                # superseded row hangs a judgment off a version no screen shows.
                refused.append(
                    {
                        "read_id": str(read_id),
                        "meter": getattr(read.asset, "asset_no", None),
                        "reason": "not_head",
                    }
                )
                continue
            if read.status == "ok":
                # An accept is a statement about a FLAG. Recording one on an
                # unflagged reading files a judgment about nothing and makes
                # `fix_disposition` unreadable as evidence of review.
                refused.append(
                    {
                        "read_id": str(read_id),
                        "meter": getattr(read.asset, "asset_no", None),
                        "reason": "not_flagged",
                    }
                )
                continue
            if read.fix_disposition is not None:
                # Someone already worked this row. Overwriting would erase a
                # name and a reason — `dispute_read`'s refusal, same argument.
                refused.append(
                    {
                        "read_id": str(read_id),
                        "meter": getattr(read.asset, "asset_no", None),
                        "reason": "already_dispositioned",
                        "fixed_by": str(read.fixed_by_id) if read.fixed_by_id else None,
                    }
                )
                continue
            _stamp_fix(actor, read, disposition=disposition, reason=reason)
            applied.append(
                {
                    "read_id": str(read.id),
                    "meter": getattr(read.asset, "asset_no", None),
                    "channel": read.channel,
                    "status": read.status,
                }
            )
    return {
        "disposition": disposition,
        "reason": reason,
        # The acting user, once, beside the per-row trail — the auditor's
        # question answered by the response as well as by the rows.
        "acted_by": str(getattr(actor, "id", "")) or None,
        "selected": len(read_ids),
        "applied": applied,
        "applied_count": len(applied),
        "refused": refused,
        "refused_count": len(refused),
        "rule_ref": "BR-MET-129",
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def bulk_estimate_reads(actor: Any, payload: Any) -> dict[str, Any]:
    """Estimate a SET of missing (meter, channel, date) records — one reason,
    one name, one audit row EACH.

    The arithmetic is not re-implemented: every target goes through
    `estimate_missing_read`, so BR-MET-026's trailing-3-cycle average,
    BR-MET-027's two-consecutive-estimates limit and BR-MET-058's per-channel
    history apply exactly as they do to the single-row door. **A bulk button is
    a different surface, never a different pipeline** — the same sentence the
    quick-entry modal is built on.

    A target the rules refuse (*"no history — field visit"*, BR-MET-027's third
    consecutive miss) comes back REFUSED WITH ITS REASON rather than silently
    skipped. That is BR-MET-026's own posture at scale: a refusal is an answer
    the clerk must see beside the row, and forty of them are forty answers.
    """
    data = _payload_dict(payload)
    reason = _bulk_reason(data)
    raw_targets = data.get("targets")
    targets = [
        t for t in (raw_targets if isinstance(raw_targets, list) else []) if isinstance(t, dict)
    ]
    if not targets:
        _refuse_fields(
            [_field_error("targets", errors.VAL_REQUIRED, "metering.reads.bulk.selection_required")]
        )
    if len(targets) > BULK_MAX_ROWS:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-023",
            message_key="metering.reads.bulk.too_many",
            params={"selected": len(targets), "max": BULK_MAX_ROWS},
        )

    estimated: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for target in targets:
        label = {
            "meter": target.get("meter_no"),
            "asset_id": str(target["asset_id"]) if target.get("asset_id") else None,
            "channel": target.get("channel") or models.CHANNEL_TOTAL,
            "read_at": target.get("read_at"),
        }
        try:
            result = estimate_missing_read(actor, target)
        except errors.ApiError as exc:
            # One bad target does not cost the clerk the other thirty-nine.
            # The catalog code and its message key travel so the row can say
            # WHY in the clerk's own language (G18: no raw key reaches a user).
            refused.append({**label, "reason": exc.code, "message_key": exc.message_key})
            continue
        if not result.get("estimated"):
            refused.append({**label, "reason": result.get("reason") or "not_estimated"})
            continue
        # The PO's name-on-every-row, on the estimate this click created.
        # BR-MET-030 already requires reason + audit for an estimate override;
        # a BULK estimate is the same obligation with forty rows behind it.
        with transaction.atomic():
            read = models.MeterRead.objects.filter(tenant_id=_tenant_id(), id=result["id"]).first()
            if read is not None:
                _stamp_fix(actor, read, disposition=BULK_FIX_ESTIMATE, reason=reason)
        estimated.append(
            {
                **label,
                "read_id": result["id"],
                "usage_display": result.get("usage_display"),
                "method": result.get("estimation_method"),
            }
        )
    return {
        "reason": reason,
        "acted_by": str(getattr(actor, "id", "")) or None,
        "selected": len(targets),
        "estimated": estimated,
        "estimated_count": len(estimated),
        "refused": refused,
        "refused_count": len(refused),
        "rule_ref": "BR-MET-026",
    }


# ── seam implementations the W1 lane declared and left unwired ──────────────
# apps/metering/seams.py documented these three names and fell back to
# 0/None "true by construction — no meter_reads table exists". The table
# exists now, so the fallbacks would be lies: they are implemented here.


def read_reference_count_impl(unit_id: Any) -> int:
    """BR-MET-037 delete guard: committed reads anywhere under this unit."""
    return models.MeterRead.objects.filter(
        tenant_id=_tenant_id(), asset__service_point__unit_id=unit_id
    ).count()


def read_count_for_asset(asset_id: Any) -> int:
    """BR-AST-012/013: how many committed reads name this asset.

    THE SEAM `apps/assets/seams.py` HAS DOCUMENTED SINCE W1 AND NOBODY WROTE
    (DEF-079, G20 register row `apps.metering.services.read_count_for_asset`).
    Its caller fell back to `0` while it was dark, so the assets delete gate saw
    an asset carrying meter reads as UNREFERENCED and offered to delete it —
    DEF-075's shape exactly: a seam that substitutes an answer instead of
    reporting that it cannot give one. The seam docstring's "0 by construction
    until `meter_reads` lands" stopped being true on 2026-08-10 when the table
    landed; this function is what makes it true again by making the count real.

    EVERY version counts, superseded rows included, and that is deliberate: the
    question the delete gate asks is "has this asset ever been read", and a
    corrected read is still a read. Contrast `collected_read_count_impl`, which
    counts lineage HEADS because it is measuring cycle progress. Two questions,
    two counts, both stated.
    """
    return models.MeterRead.objects.filter(tenant_id=_tenant_id(), asset_id=asset_id).count()


def _capture_manual_read(
    *,
    asset_id: Any,
    value: Any,
    read_at: Any,
    actor: Any,
    value_field: str,
    date_field: str,
    source_detail: str,
    exists_key: str,
    failed_key: str,
    audit_action: str,
    disposition_reason: str,
) -> dict[str, Any] | None:
    """ONE manual-read capture, worn by two doors — the FINAL read at the end of
    an asset's life and the OPENING read at the start of it.

    ⚠ **EXTRACTED 2026-09-12 (`CR-092-BRC01` step 2 wave C lane 2, `AST-B-14`),
    AND THE EXTRACTION IS THE POINT RATHER THAN THE TIDINESS.** The opening read
    is the same act as the final read at the other end of the register: one
    committed MANUAL `meter_reads` row, taken atomically inside the caller's
    transaction, judged by the SAME BR-MET-020/022 engine, refusing the caller's
    whole operation on an ERROR outcome. A second implementation would have been
    a second place for "what a typed reading means" to be decided — the shape
    hard-won law 5 calls two copies free to drift, and on a path where being
    wrong makes every bill from that meter wrong.

    **Everything that varies between the two is a STRING**: which field a
    refusal names, which sentence a clerk reads, what the row's
    `source_detail` says and what the audit line is called. Nothing about the
    arithmetic, the lineage law or the validation set varies at all, and that
    is what makes one body correct for both.

    `capture_final_read`'s behaviour is byte-for-byte what it was — same field
    names, same message keys, same `source_detail`, same audit action, same
    disposition sentence — so its callers (reassign and retire) and its tests
    could not tell this refactor happened.
    """
    fe: list[dict[str, Any]] = []
    asset = seams.meter_by_id(asset_id)
    if asset is None:
        fe.append(
            _field_error(
                value_field, errors.VAL_UNKNOWN_LOOKUP, "metering.read.unknown_meter"
            )
        )
    parsed_at = read_import._parse_date(str(read_at or ""))
    if parsed_at is None:
        fe.append(
            _field_error(date_field, errors.VAL_REQUIRED, "metering.read.read_at_required")
        )
    register = None
    try:
        register = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        fe.append(
            _field_error(value_field, errors.VAL_FORMAT, "metering.read.value_not_a_number")
        )
    if register is not None and register < 0:
        fe.append(
            _field_error(value_field, errors.VAL_RANGE, "metering.read.value_negative")
        )
    _refuse_fields(fe)

    if (
        _head_qs()
        .filter(asset_id=asset.id, read_at=parsed_at, channel=models.CHANNEL_TOTAL)
        .exists()
    ):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-016",
            message_key=exists_key,
            params={"asset_no": asset.asset_no, "date": parsed_at.date().isoformat()},
        )

    config = _config_set()  # CR-038 A1: the final read is judged per service
    ctx = _build_context(
        asset=asset,
        read_at=parsed_at,
        channel=models.CHANNEL_TOTAL,
        value=register,
        config=config,
        cycle=None,
    )
    consumption, outcomes = validation.evaluate_row(ctx, config)
    blocking = [o for o in outcomes if o.severity == validation.ERROR]
    if blocking:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-015",
            message_key=failed_key,
            params={
                "asset_no": asset.asset_no,
                "rule": blocking[0].rule,
                "detail": blocking[0].detail,
            },
        )
    warned = any(o.severity == validation.WARNING for o in outcomes)

    prior = _prior_actual_head(asset.id, models.CHANNEL_TOTAL, parsed_at)
    days = (parsed_at.date() - prior.read_at.date()).days if prior is not None else None
    standing = _standing_estimates(asset.id, models.CHANNEL_TOTAL, parsed_at)
    trued = estimation.true_up(
        estimation.TrueUpInput(
            channel=models.CHANNEL_TOTAL,
            unit=asset.unit,
            actual_register=register,
            last_actual_register=prior.current_value if prior else None,
            multiplier=asset.multiplier,
            estimated_consumptions=[e.consumption for e in standing if e.consumption is not None],
            estimated_read_ids=[str(e.id) for e in standing],
        )
    )
    outcome_json = validation.as_json(outcomes)
    trues_up_ids = None
    if trued.applies:
        consumption = trued.quantity
        trues_up_ids = trued.corrects_read_ids
        outcome_json = outcome_json + [
            {"rule": "true_up", "severity": validation.OK, "detail": trued.as_dict()}
        ]

    read = models.MeterRead.objects.create(
        tenant_id=_tenant_id(),
        asset=asset,
        route_id=collection_route_id(asset),  # BR-MET-079 / DEF-233 — stamped at collection
        account_id=collection_account_id(asset),  # DEF-658 — stamped alongside it
        read_at=parsed_at,
        channel=models.CHANNEL_TOTAL,
        period_start=prior.read_at.date() if prior is not None else None,
        period_end=parsed_at.date(),
        prior_value=prior.current_value if prior is not None else None,
        current_value=register,
        multiplier=asset.multiplier,
        consumption=_num6(consumption),
        unit=asset.unit,  # EXPLICIT, from the asset's OWN UoM — rule 3
        source="manual",
        source_detail=source_detail,
        # An operator TYPED this on the AST-06/AST-08 form, which is exactly
        # what the tenant's `manual` method means (BR-AST-043).
        read_method="manual",
        status=validation.primary_status(outcomes),
        lifecycle="committed",
        days_since_prior=days,
        rule_outcomes=outcome_json,
        imported_by_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        disposition="accept" if warned else None,
        disposition_reason=(
            disposition_reason if warned else None
        ),
        trues_up_read_ids=trues_up_ids,
    )
    _audit(
        actor,
        audit_action,
        "meter_read",
        read.id,
        after={
            "meter": asset.asset_no,
            "channel": models.CHANNEL_TOTAL,
            "current_value": str(register),
            "consumption": str(read.consumption) if read.consumption is not None else None,
            "unit": read.unit,
            "read_at": parsed_at.date().isoformat(),
        },
    )
    return selectors.read_dict(read)


def capture_final_read(
    *,
    asset_id: Any,
    value: Any,
    read_at: Any,
    actor: Any = None,
    unit_id: Any = None,
    unit: Any = None,
) -> dict[str, Any] | None:
    """BR-AST-022 — THE SEAM `apps/assets/seams.py` HAS DOCUMENTED SINCE W1
    AND NOBODY WROTE (wired by the CR-028 debt sweep, 2026-08-22 — D5).

    One committed MANUAL `meter_reads` row for the asset's final register
    value, taken atomically with the caller's reassign/retire (this runs
    inside the caller's transaction — the read and the move commit together,
    US-AST-009 TC-6). While this was unwired every reassign/retire that asked
    for a final read refused BIZ-COMPLETENESS; that refusal is now the path
    of a missing METERING module only.

    The committed-lineage rules are metering's own, reused, never re-derived:

    * the register delta runs through `_build_context` + the BR-MET-020/022
      validation engine — the SAME arithmetic and rule set a batch row gets;
    * an ERROR-severity outcome REFUSES the capture (and with it the whole
      move — BR-MET-015 resolves an error only by a human's override/reject/
      field-visit/skip, and this form offers none of those);
    * WARNING outcomes post with `disposition: accept` and a reason naming
      this path — the operator TYPED the value on the AST-06/AST-08 form,
      which is the attestation BR-MET-015 wants recorded, not skipped;
    * lineage law holds: a committed head already standing on (asset, date,
      total) refuses — a correction goes through S29's supersede, never a
      second head (BR-MET-016/053);
    * the unit is stamped from the ASSET's own UoM (rule 3); the `unit`
      kwarg stays accepted for the documented seam shape and is cross-read
      only (the asset row is the same row the caller holds);
    * BR-MET-029 true-up applies exactly as at batch commit when estimates
      stand on this lineage.

    STATED OMISSION: the BR-AST-029 export placeholder for a net meter's
    cycle is the BATCH path's (`_ensure_export_records` is batch-shaped); a
    final read here records the TOTAL register. A net meter's export reading
    still travels through S28, where the placeholder logic lives.

    Returns `selectors.read_dict(read)` — the caller links `final_read_id` to
    the closing assignment row. QUANTITY only; no money (BR-AST-025).
    """
    return _capture_manual_read(
        asset_id=asset_id,
        value=value,
        read_at=read_at,
        actor=actor,
        value_field="final_read_value",
        date_field="final_read_date",
        source_detail="final_read",
        exists_key="metering.read.final_read_already_exists",
        failed_key="metering.read.final_read_failed_validation",
        audit_action="read.final_read_captured",
        disposition_reason=(
            "final read entered by the operator on the move/retire form (BR-AST-022)"
        ),
    )


def capture_opening_read(
    *,
    asset_id: Any,
    value: Any,
    read_at: Any,
    actor: Any = None,
) -> dict[str, Any] | None:
    """`AST-B-14` — the reading on a new meter's dial, taken as the asset is
    created and inside the SAME transaction (PO 2026-09-12, verbatim:
    ***"Build it as drawn - move it to step 2, beside the multiplier, register
    digits and the warning"***).

    **The failure rule is the whole contract and it is the strict one:** if the
    read cannot be written, the ASSET IS NOT CREATED. `create_asset` calls this
    inside its own `transaction.atomic()`, so an ERROR-severity outcome or a
    refused value takes the create down with it - which is what the wizard's
    consequence box promises a clerk before they press the button. The
    alternative (create the meter, drop the reading, tell nobody) is the shape
    that puts a meter into service reading from an unknown baseline.

    WHY IT IS NOT `capture_final_read` WITH A DIFFERENT LABEL. Everything a
    clerk reads is different: a refusal must name `opening_read`, not
    `final_read_value`, or the wizard highlights a field that is not on the
    screen; and *"Nothing was moved"* is false here, because nothing was being
    moved. The ARITHMETIC is identical and is shared - see
    `_capture_manual_read`.

    THERE IS NO PRIOR HEAD, BY CONSTRUCTION. The asset was created microseconds
    ago, so `_prior_actual_head` finds nothing, `_standing_estimates` is empty
    and the true-up cannot apply. The engine is still run rather than
    short-circuited: BR-MET-020/022's range and rollover rules have things to
    say about a first reading too, and deciding here which of them apply to a
    first read would be re-deriving metering's law inside assets' caller.

    Returns metering's own `read_dict`, or None on a deployment with no metering
    module - which `apps/assets/seams.capture_opening_read` turns into a refusal
    rather than a silent skip, exactly as the final-read seam does.
    """
    return _capture_manual_read(
        asset_id=asset_id,
        value=value,
        read_at=read_at,
        actor=actor,
        value_field="opening_read",
        date_field="opening_read_date",
        source_detail="opening_read",
        exists_key="metering.read.opening_read_already_exists",
        failed_key="metering.read.opening_read_failed_validation",
        audit_action="read.opening_read_captured",
        disposition_reason=(
            "opening read entered by the operator on the add-asset form (AST-B-14)"
        ),
    )


def collected_read_count_impl(*, route_id: Any = None, cycle_id: Any = None) -> int:
    """BR-MET-011: progress derives from committed reads — lineage HEADS only,
    so a superseded chain counts once (US-MET-018/TC-7).

    ── `DEF-MET-6143` · THE ROUTE HALF COUNTS WHAT WAS **COLLECTED** ─────────
    PO ruling 2026-09-22 (`CR-131-BRC07`), verbatim **"100"**: a route reports
    the readings collected on it, not the readings on the meters it holds
    today. So the route leg reads `meter_reads.route_id`, the `BR-MET-079`
    collection stamp, and no longer `asset__service_point__route_id` — which is
    the live membership projection and took this count from 100 to 0 the
    instant a route's premises moved.

    ⚠ **THE TWO LEGS ARE NOT SYMMETRICAL, AND THAT IS DELIBERATE RATHER THAN
    AN OVERSIGHT.** There is no cycle stamp on `meter_reads` — `metering/0012`
    landed a route column and nothing else — so the CYCLE leg still resolves
    through the live projection and still answers *"the reads on this cycle's
    meters today"*. Whether a cycle should carry its own stamp was not part of
    the ruling and is not decided here; it is named so the asymmetry reads as a
    boundary rather than as a half-applied fix.

    ⚠ A reading with NO stamp (collected before `metering/0012`) belongs to no
    route and is absent from the route count. 0 of 516 on the seeded fixture,
    not zero on an older tenant — stated on screen, never silently absorbed.
    """
    qs = _head_qs()
    if route_id is not None:
        qs = qs.filter(route_id=route_id)
    if cycle_id is not None:
        qs = qs.filter(asset__service_point__cycle_id=cycle_id)
    return qs.count()


def last_read_completion_impl(route_id: Any) -> Any:
    """The most recent committed read date on the route, or None.

    ── `DEF-MET-6143` · "ON THE ROUTE" MEANS **COLLECTED ON IT** ─────────────
    PO ruling 2026-09-22 (`CR-131-BRC07`), verbatim **"100"**. This read
    `asset__service_point__route_id` until then, so a route whose premises had
    moved reported *"never read"* — a false ABSENCE, which is invisible to
    every check this repository has and is the reason the defect survived a
    green suite. It now reads the `BR-MET-079` collection stamp.

    ⚠ `None` still means *nothing has been collected on this route*, and now
    ALSO means *everything collected on it predates the stamp*. The second is 0
    of 516 readings on the seeded fixture and is not zero on an older tenant.
    """
    row = (
        _head_qs()
        .filter(route_id=route_id)
        .order_by("-read_at")
        .values_list("read_at", flat=True)
        .first()
    )
    return row


def cycle_read_batch_count(cycle_id: Any) -> int:
    """BR-MET-009: a cycle referenced by a POSTED read batch is audit-locked."""
    return models.ReadImportBatch.objects.filter(
        tenant_id=_tenant_id(), cycle_id=cycle_id, status="posted"
    ).count()


# ══════════════════════════════════════════════════════════════════════════
# US-TEN-019 SAMPLE DATA — the seams `apps/tenancy/seams.py` documents
# ══════════════════════════════════════════════════════════════════════════
# Thin forwarders on purpose. The seam contract names
# `apps.metering.services.seed_sample_records`, G20 harvests that exact path, and
# the implementation is large enough to deserve its own file — so the published
# NAME lives here and the CODE lives in `sample_data.py`. The import is inside
# each function because `sample_data` imports this module (it drives the same
# services a clerk's click uses), and a module-level import would be a cycle.
#
# DEF-153: every one of these was DOCUMENTED and UNIMPLEMENTED until
# 2026-08-16, which is why the Sample data panel loaded nothing and a brand-new
# tenant was empty.


def seed_sample_records(actor: Any) -> int:
    """BR-TEN-056/057 — this module's block of the sample set. See sample_data."""
    from apps.metering import sample_data

    return sample_data.seed_sample_records(actor)


def seed_sample_records_note() -> str | None:
    """WHAT THE ESTATE THIS BLOCK BUILT DOES **NOT** SPEAK — DEF-3224.

    The OPTIONAL `<seam>_note` contract `apps/tenancy/seams.py` documents:
    read-only, no writes, resolved after the block SEEDS, and rendered on the
    Sample data panel beside the block's own line.

    ⛔ **THE GAP IT CLOSES IS A SUCCESS, NOT A FAILURE, WHICH IS WHY NOTHING SAW
    IT.** The estate takes ONE metered backbone per unit and names every other
    metered service the utility sells as refused, with a sentence saying why.
    That refusal is CORRECT (`BR-MET-003`: a seeder must not plant a service the
    utility does not sell, and a second register would double the ready-to-run
    billing month the demo exists to let somebody press) — and until now the
    sentence went to `logger.info` and nowhere else. The Product Owner ticked
    Electric, Water and Sewer, water won the backbone, and **electric got no
    service point, no meter, no read and no line on any of the 95 issued bills,
    not even its `$12.00` monthly base — `$576.00` a month across 48 units** —
    with 0 of 17 blocks failing.

    ⚠ **IT ANSWERS THE GENERAL QUESTION AND NOT THE ELECTRIC ONE.** Refusals
    that are entirely correct still need saying: sewer behind a tenant that does
    not sell water is the standing example, and it is a fact about the utility's
    own service mix rather than a fault in the fixture. So this returns whatever
    `estate().refused` holds — every enabled service that gets NOTHING, each with
    its own reason — and `None` when there is nothing to report, which is the
    ordinary case and is byte-for-byte what a block reported before.

    ⚠ **AND IT IS THE `estate().refused` TEXT, THE SAME TEXT `seed_sample_records`
    LOGS.** `unseeded_services()` answers the same question in CODES and has never
    had a consumer; two sentences for one fact is how a screen and a log come to
    disagree.
    """
    from apps.metering import sample_data

    plan = sample_data.estate()
    return plan.refusal_sentence if plan.refused else None


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-061/066 — remove what is free, report the rest BY NAME."""
    from apps.metering import sample_data

    return sample_data.remove_sample_records()


def sample_record_count() -> int:
    """How many sample rows this module holds right now, read live."""
    from apps.metering import sample_data

    return sample_data.sample_record_count()


def seed_sample_reads(actor: Any) -> int:
    """BR-TEN-056/062 — the BILLED months' meter reads, in kgal (rule 3).

    ⚠ This said *"the three months"* until 2026-09-01 and the third month left
    with the PO's own step: `seed_sample_next_cycle_reads` below posts the walk
    for the cycle they run. A docstring that still said three would be a
    comment claiming a guarantee (hard-won law 1) with a seeding panel attached.
    """
    from apps.metering import sample_data

    return sample_data.seed_sample_reads(actor)


def seed_sample_next_cycle_reads(actor: Any) -> int:
    """THE THIRD-CYCLE WALK — PO 2026-09-01, *"Without meter reads for 3rd cycle
    billing cycle will not run - hence you have to add meter reads also."*

    ⚠ **PUBLISHED HERE BECAUSE A BLOCK NOBODY CAN RESOLVE IS A BLOCK THAT DOES
    NOT RUN.** `apps.tenancy.sample_data` reaches every block through
    `seams.resolve(module, seam)`, which looks in `apps.<module>.services` —
    never in `sample_data`. A seam written only in `sample_data.py` resolves to
    None and the orchestrator SKIPS the block as "seam not wired", reporting a
    healthy tenant with no walk in it (the same three lines
    `apps/payments/services.seed_sample_refund` exists for).
    """
    from apps.metering import sample_data

    return sample_data.seed_sample_next_cycle_reads(actor)


def seed_sample_second_cycle_reads(actor: Any) -> int:
    """THE SECOND CYCLE'S WALK — PO 2026-09-01, *"add reading then bill it, then
    add reading data again, then bill it and then again add reading data - you
    can not add reading data once for 3 months"*.

    ⚠ Published here for the same reason as its two siblings: `seams.resolve`
    looks in `apps.<module>.services` and never in `sample_data`, so a seam
    written only there is SKIPPED as "not wired" and the load reports a healthy
    tenant with a month of readings missing.
    """
    from apps.metering import sample_data

    return sample_data.seed_sample_second_cycle_reads(actor)


def next_cycle_read_coverage(service: Any = None) -> dict[str, Any]:
    """How many meters expect a reading for the next cycle and how many have
    one — the figures the block checks itself against, published so a report
    and the check cannot disagree."""
    from apps.metering import sample_data

    return sample_data.next_cycle_read_coverage(service)


def default_import_mapping_entries() -> list[dict[str, Any]]:
    """BR-AST-048 (CR-028 AST-W3-T8) — the three GENERATED default mapping
    templates, published for TENANCY's provisioning seed to resolve
    (`apps/tenancy/services._generated_import_mapping_entries`). A thin
    forwarder on purpose: the content is derived by the runner from the SAME
    declared column sets that derive the CR-025 sample CSV, so the sample and
    the default cannot drift."""
    from apps.metering import import_runs

    return import_runs.default_import_mapping_entries()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-001@d76f5b4 (story+rules snapshot hash — EP-MET-01 lead story; co-packet EP-MET-02@8f2ab3c)
# packet: US-MET-016@c81d5a7 (EP-MET-04 supersede & correction story — correct_billed_read, mark_read_billed, delete_staged_read_row, read_count_for_asset)
# packet: US-AST-011@9d8d058 (EP-AST-05 — the 0-value export record a net cycle without one leaves behind)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane) · AMENDED 2026-08-10 by story-coder (DEF-017 — meter_types/read_methods forwarded to the assets lane like their two twins) · AMENDED 2026-08-11 by story-coder (plan-assignment BACKDATING lane — `_apply_unit_plan` now surfaces rating's backdating warning to the caller as `warnings`, PO ruling 2026-08-11 option B) · AMENDED 2026-08-18 by story-coder (CR-010 silent-seed-gaps lane — DEF-251: `seed_read_validation_settings`, the provisioning seam the module had DOCUMENTED on the callee since it was written and that nothing anywhere called) · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (default_import_mapping_entries forwarder for tenancy's BR-AST-048 seed) · AMENDED 2026-08-22 by the CR-028 debt-sweep lane (D5: capture_final_read published — the BR-AST-022 seam assets/seams.py documented since W1; one committed manual read in the caller's transaction, through _build_context + the validation engine, ERROR outcomes refuse, WARNING outcomes post disposition=accept with the form-attestation reason, lineage law refuses a second head; stated omission: the BR-AST-029 export placeholder stays the batch path's)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ pytest tests/test_us_met_*.py 56 passed/0 skipped · tests/test_us_ast_*.py 73 passed/0 skipped (13 of the 129 are @pytest.mark.isolation, green on sqlite, deselected from the suite run and re-run under -m isolation: 13 passed, 20 postgres-only skipped) · suite `pytest tests -m "not golden and not isolation"` 566 passed, 9 skipped, 44 deselected✔ (shared tree — the concurrent rating lane's tests included; 365 was the pre-lane baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [DEF-016/017 reference-data lane 2026-08-10] ruff✔(--select E4,E7,E9,F on apps/ — the bar the baseline passes; the repo-wide `ruff check .` default-rule run has 194 pre-existing findings under the newer ruff 0.15.8 in this container, none in this lane's files) black✔(--target-version py312 on this lane's files; 8 apps/ files are pre-existing reformat candidates under black 26.3.1, none of them this lane's) · suite `pytest tests -m "not golden and not isolation"` 895 passed / 9 skipped (875 was the baseline in this tree when the lane started) · `-m isolation` 14 passed / 30 skipped (unchanged) · run_gates 13-PASS/0-FAIL/1-SKIP✔ · no migration in this lane (no schema change) · RED-then-GREEN proved for both defects: removing rating's seam turns the DEF-016 guard red naming ['charge_codes','tax_jurisdictions']; removing the six SEED_LIST_OWNERS rows turns the DEF-017 guards red naming all six
# exceptions: [US-MET-016 lane 2026-08-15] `mark_read_billed` is PUBLISHED and NOTHING CALLS IT YET — apps/billing must call it at issue time for every read its invoice priced, and that edit is billing's territory; until it lands a billed read still reads as `committed`, the plain supersede path is taken and no J6 linkage is recorded, which is the exact failure US-MET-016 exists to prevent. REPORTED, loudly, rather than left as a comment (hard-won law 2) · `correct_billed_read` REFUSES when the billing seam cannot resolve the invoice, rather than writing a linkage that names an unverifiable bill · [US-AST-011 lane 2026-08-15] a net meter's cycle read with no export record gets a 0-value EXPORT record flagged `missing` — never silence, which downstream would read as "exported nothing"; the quantity is 0 and carries its unit, and no export register is invented · [W2 reads lane 2026-08-10] commit_read_batch is SYNCHRONOUS — BR-MET-055's async job wrapper is outstanding (no BE-07 job store on this deployment); atomic semantics are identical, REPORTED · the `read_batch` number series has no seeded row either, so batch_no is NULL with an explicit numbering_series_missing warning · `estimate` as a staged-row disposition records on the batch but posts nothing: the estimate path fills MISSING records (estimate_missing_read), and a staged row already carries a register value · true-up sums STANDING estimates where BR-MET-029 says BILLED ones (billing does not exist yet) — named narrowing, documented in estimation.true_up · `_num6` quantizes to the column's declared NUMERIC(18,6) scale at PERSIST time so sqlite and Postgres store the same digits; this is NOT B4.4 money rounding and no money figure is produced anywhere in this module
# exceptions: [2026-08-11 quantity-seam lane] this module now PUBLISHES two names that are unlike everything else in it — `consumption_from_registers` and `true_up_quantity` are PURE (no ORM, no tenant context, no clock, no audit row) and are not write paths. They are here and nowhere else because apps/billing/rating_seam.py resolves metering's seams on `apps.metering.services` by name; they are re-exported from apps/metering/quantities.py rather than redefined, so there is one signature and not a copy that can drift from the frozen fixtures. Both return QUANTITIES — no rate is read and no money figure is produced anywhere in this module.
# exceptions: premises/unit number series have no seeded row (EP-TEN-08 defines neither) → number NULL + explicit numbering_series_missing warning, never invented · unit deactivation recorded on units.deleted_at (US-MET-002 §5 forbids a stored unit status) · unit_plan_assignments history is rating-owned and was UNWIRED here (history_recorded:false per call) — CORRECTED 2026-08-11: rating authors the writer, a None history now RAISES, and as of the backdating lane the response also carries `warnings` (a LIST: BR-MET-042's occupied-unit override and rating's PO-2026-08-11 backdating warning can both be true of one assignment). `warning` is unchanged for existing readers. The same lane gave `bulk_assign_unit_plans` a PER-UNIT SAVEPOINT: bulk catches per-unit failures and carries on, and `_apply_unit_plan` moves `units.rate_plan_id` before the history row is written, so a refused unit used to keep a moved plan column with no coverage row — PROVED RED (removing the savepoint fails tests/test_us_met_003_plan_backdating.py TC-13 with `AssertionError: assert UUID('019fefd8-dbdc-70f2-8dcc-9c554eec0d6d') is None`) · premises CSV/pattern staging is NOT persisted (US-MET-004 §5 "no persistence in v1") — E2 vs 11b §2.5's id-bearing 3-step contract, reported · premises_types cannot register as a /lookups list (tenancy LOOKUP_LISTS has no such key) — reported · [DEF-017 lane 2026-08-10] seed_reference_list no longer short-circuits meter_types to 0 and no longer raises KeyError for read_methods: all four asset catalogs route to apps.assets.services.seed_reference_list, which is the gap apps/assets REPORTED in its own docstring and could not reach into. The old comment citing B2 r4's plain read_method value was superseded by BR-AST-043 (PO 2026-08-09) and by apps/assets/migrations/0003, which built both tables
# exceptions: [US-MET-013 dispute lane 2026-08-16, DEF-046] `dispute_read` /
#         `clear_read_dispute` are the WRITERS the marker columns never had.
#         Three things are stated rather than chosen: (1) `clear_read_dispute`
#         is @require_role(SYSTEM_ADMIN) ALONE — the only such gate in this
#         module — because the OQ-043 closure names that role and clearing is
#         what releases the account back into the bill run; (2) a re-dispute
#         after a clearance RESETS the closure columns rather than appending,
#         because `meter_reads` holds ONE marker by B2 r8's column set and a
#         dispute-history table is a story, not a service function's choice —
#         the previous cycle survives in `audit_log`; (3) the clearing
#         `resolution` note lands in the audit row and NOT on the read, because
#         B2 r8 gives no cleared-reason column. ⚠ **AMENDED 2026-08-26 —
#         OQ-245 IS CLOSED (BR-MET-133) AND THIS LINE SAID IT WAS OPEN.** What a
#         dispute does to a bill the read ALREADY priced is now ruled: the bill
#         STANDS (not voided, not held — hard rule 4), the marker still holds
#         the next run, resolution goes through `correct_billed_read`, and the
#         DISPUTED AMOUNT does not age into late fees while the dispute is open
#         (`apps/billing/late_fee.ageable_portion`). `billed_bill_effect` now
#         carries `issued_bill_stands_br_met_133` and every surface says the
#         rule rather than the question. Still absent by design: a DUNNING pause
#         (BR-MET-133 names late fees and ageing; the collection ladder is
#         OQ-137's untouched half) and an automatic J6 correction (clause 3
#         makes it a staff decision through the door, not a consequence of
#         disputing). And the disputed AMOUNT is recorded nowhere — OQ-420,
#         refused rather than defaulted. The BILLED
#         lock is untouched: `supersede_read` still refuses a billed read and
#         `correct_billed_read` is still the only door (BR-MET-053), asserted by
#         test_us_met_013_tc3f. This lane RELIES ON but does not decide OQ-209 —
#         metering 0007's trigger deliberately leaves the marker columns free to
#         move while freezing the measurement.
# exceptions: [CR-054 W2/W4 lane 2026-08-30] **BR-MET-940 — PARTIAL POSTING.**
#         `commit_read_batch` no longer raises `errors_need_resolution`: it posts
#         the rows it can and HOLDS the rest with a stored reason, under the PO's
#         *"all or nothing will not work - we accept what is correct and rejct
#         what i not correct"*. **Every write is now its own SAVEPOINT** (law 14,
#         proved on real PostgreSQL — without it the same file answers
#         `TransactionManagementError` and files 0 of 3). ⚠ **The W2 clause below
#         says "errors still raise `errors_need_resolution`" and that half is
#         SUPERSEDED**; BR-MET-015's ROW half is untouched, so an unresolved error
#         still keeps its own reading out. Hard rule 6 is untouched too — the
#         batch still closes, so `already_posted` and `already_posted_identical`
#         refuse a second post exactly as before, which is what stops a partly
#         posted file being posted twice. ⚠ **New route with no 11b row**:
#         `GET /read-batches/{id}/results.csv?kind=failures|successes`
#         (`BR-MET-941`), house grammar, REPORTED for the A11 addendum with the
#         eleven reads routes above. ⚠ Its three refusals REUSE
#         `metering.import.*` catalogue keys because G32 is a ratchet at zero and
#         this lane may not write copy into eleven catalogues — two precise
#         sentences are OWED (*run* should read *batch*, *loaded* should read
#         *posted*). ⚠ `openapi/schema.json` regenerated for this one route.
# exceptions: [CR-038 W2 mixed-cycle lane 2026-08-26] Three rulings signed the
#         same day, built here: (1) **BR-MET-129** — `commit_read_batch`'s
#         posting gate now takes an UNDISPOSITIONED warning row (severity ok OR
#         warning posts; errors still raise `errors_need_resolution` — the
#         BR-MET-015 error half, untouched — ⚠ SUPERSEDED 2026-08-30, see the
#         CR-054 entry above). The committed read's `disposition`
#         stays the row's REAL one (None when nobody dispositioned — never a
#         synthesized accept), and `_post_row` now CARRIES the staged row's
#         GROUP-rule flags (`_GROUP_RULES_CARRIED`: tou_sum_sanity,
#         plan_registers) onto the committed read's `rule_outcomes` and into its
#         primary status — before this they silently vanished at commit. The
#         DEF-659 legibility contract (posted_reads/skipped_rows/posted_nothing)
#         is unchanged and still asserted. (2) **BR-MET-122** — `_build_context`
#         resolves the meter's cycle (`service_points.cycle_id`, BR-MET-033) and
#         the batch's tag onto the ReadContext; the engine's new
#         `cycle_membership` rule warns BY NAME, and an untagged batch skips
#         with a stated reason. (3) CR-038 aspect 4/5 — `stated_service` (the
#         row's BR-MET-014 effective tag) + `enabled_services` feed the engine's
#         `service_coherence` rule, and `validate_read_batch`'s summary gains
#         `per_service` counts (`_per_service_counts`, derived on every
#         validate, never stored — batch.counts keeps its persisted shape).
#         Guards proved RED first; runs quoted in tests/test_cr038_w2_mixed_cycle.py.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
