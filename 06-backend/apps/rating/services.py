# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-001 (Plans tab row actions — hard-delete audit-lock, S9) ·
#           US-RAT-002 (New Plan wizard commit: plan-as-bundle, S10) ·
#           US-RAT-003 (plan lifecycle, versioning & category targeting) ·
#           US-RAT-004 (schedule archive audit-lock, S9 tab 2) · US-RAT-005
#           (New Rate wizard: basics, flat & pure tiers, S11) · US-RAT-006 (TOU
#           Option B: windows × seasons × day-types) · US-RAT-007 (demand,
#           seasonal, capacity & %-of-water structures) · US-RAT-008 (charge-code
#           catalog + plan attachment, S12) · US-RAT-009 (taxes & fees + tenant
#           jurisdictions, S13) · US-RAT-010 (effective-dated versioning & the
#           single rate update) · US-RAT-011 (bulk rate update — one atomic
#           batch)   Screens: S9 · S10 · S11 · S12 · S13
# Rules:    BR-RAT-012/027 (base per service; plan base DERIVED) · BR-RAT-024
#           (services ⊆ tenant-enabled) · BR-RAT-025 (D1–D9 plan-as-bundle) ·
#           BR-RAT-026 (pure tiers, no allowance) · BR-RAT-030 (plan lifecycle) ·
#           BR-RAT-031 (schedule: one service/one model; SAVE-DRAFT RESUMABLE —
#           a dateless tariff_versions row is the draft; activation needs a
#           complete structure + effective_from; drafts excluded from the
#           plan-builder picker; approval REMOVED) ·
#           BR-RAT-032 (tier contiguity) · BR-RAT-033 (TOU coverage) ·
#           BR-RAT-034 (seasonal coverage) · BR-RAT-035 (charge-code identity +
#           audit-lock) · BR-RAT-036 (tax forms; base = usage/base only) ·
#           BR-RAT-037 (append-only versions + rate_change_log, reason required) ·
#           BR-RAT-038 (UoM gate) · BR-RAT-039 (staff-assignment only) ·
#           BR-RAT-040 (bulk = one atomic all-or-none batch, never re-run) ·
#           BR-RAT-041 (amount rules; Formula disabled) · BR-RAT-042 (marginal
#           per-unit tax threshold) · BR-RAT-043 (discounts = negative charge
#           rules; budget billing = plan flag; eligibility advisory) ·
#           BR-RAT-014/015/018/019/022 (demand · %-of-water · capacity) ·
#           BR-RAT-007/017 (reprice on the service date, 7-year reproducibility) ·
#           BR-TEN-037 (tenant-entered jurisdictions)
# Tests:    06-backend/tests/test_us_rat_plans.py · test_us_rat_schedules.py ·
#           test_us_rat_charges_taxes.py · test_us_rat_versioning.py
#           06-backend/tests/test_def_rat_8001_windows_close.py
# Impacts:  apps/rating/api.py (thin) · apps/tenancy seams (rate_schedule_count) ·
#           the W3 engine (consumes the structures written here) · customers
#           plan-assignment seam (published plans only) · core.jobs (202 batch)
# ───────────────────────────────────────────────────────
"""rating service layer — the ONLY write path into this module's tables (LAW 0:
api thin → services sole writer → selectors read).

🔒 HUMAN-REVIEW-PENDING · HUMAN-OWNED — CR-039 wave C task 11, 2026-08-27,
for `outside_city_factor` in `PLAN_FIELDS` and `outside_city_exempt` in
`PLAN_SERVICE_FIELDS` ONLY. Those two keys are the write path for BR-RAT-102's
outside-city surcharge: what a plan may state, and which of its services escape
it. The marker is HERE and not only in the ledger because a ledger row naming a
file that carries no marker is invisible to G7, and that shape has bitten three
times. Row: `12-governance/09-human-review-ledger.md`, with the worked figure
(`161 Silver Creek Rd`, June 2026 — water usage `$109.00 → $163.50`) and the
two questions the PO still has to answer (`OQ-423`, `OQ-424`).
⚠ It does NOT extend to the rest of this file, which is unchanged and was never
flagged; `apps/rating/services.py` is not on `10-scripts/gates/human_owned.txt`
and this lane did not put it there — adding a path to that list is a process
event and the PO's call, not a lane's (the note the list carries about
`selectors.py` says so in its own words).

What this module is NOT: the rating ENGINE. Tier/TOU/seasonal/demand/capacity
COMPUTATION is the 🔒 W3 kernel in apps/rating/engine.py (B4 money math,
finance-signed). Everything here is CRUD, lifecycle and CONFIG VALIDATION: it
decides whether a structure may be stored, never what it prices.

Cross-module reads go through apps/rating/seams.py exclusively (B1) — this
module never imports another module's models and never writes another module's
tables. Every write lands its audit row through core.audit (BE-03, hard rule 7);
every refusal is a catalog exception (BE-02) carrying its BR-ID.

Eng dispositions recorded here (not silently resolved — reported in the build
report as well):
- RATE-SCHEDULE DRAFTS (schema-gap fix, migration 0004): BR-RAT-031 "save-draft
  resumable" now HAS storage — `tariff_versions.effective_from` is nullable and
  a dateless version IS the draft, one per tariff. A draft may be incomplete;
  `activate` is the completeness + effective_from gate, and drafts are invisible
  to in-force resolution and to the plan-builder picker until then. The B2 §2
  EXCLUDE gist window constraint is still absent from the DB (migration 0001
  never materialized it; btree_gist is not installed) — `_guard_window` remains
  its app-side half, now reading activated versions only. REPORTED, not resolved.
- PLAN ELIGIBILITY (BR-RAT-043 advisory-with-audit; schema-gap fix, migration
  0004): US-RAT-002 §5 says the ticked boxes are "stored on the plan", so they
  live in `rate_plans.eligibility` (jsonb) and ride the plan snapshot into the
  audit before/after. ADVISORY ONLY — nothing on any path reads it as a gate;
  the attestation half still happens at assignment, in customers.
- BULK REPLAY GUARD: core/idempotency.py is a 🔒 stub owned by the Eng Lead, so
  the BR-RAT-040 "batches never re-run" rule is enforced locally by a
  deterministic fingerprint stored in `rate_change_batches.change_spec` (r6.7).
- Prices are stored quantized to NUMERIC(18,6) — a STORAGE precision bound
  (DB-3), not B4 money rounding: no half-up 2dp ever happens on this path
  (BR-RAT-003 rounds at invoice-line finalization only).
"""

import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Now

from apps.rating import discounts as discount_models
from apps.rating import charge_prices, impact, models, plan_versioning, seams, selectors
from apps.rating.constants import ALL_SIZES, KIND_BASE, KINDS, default_kind
from apps.rating.pricing import percent_basis
from core import audit as core_audit
from core import errors
from core import jobs as core_jobs
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

# ── value sets (comment-documented enums per the W0 TextField pattern) ──────
PLAN_DRAFT = "draft"
PLAN_PUBLISHED = "published"
PLAN_ARCHIVED = "archived"
PLAN_STATUSES = (PLAN_DRAFT, PLAN_PUBLISHED, PLAN_ARCHIVED)

# r5 #16 + r6.1 (BR-RAT-019 / BR-RAT-015)
MODEL_FLAT = "flat"
MODEL_TIERED = "tiered"
MODEL_TOU = "time_of_use"
MODEL_DEMAND = "demand"
MODEL_SEASONAL = "seasonal"
MODEL_CAPACITY = "capacity"
MODEL_PERCENT = "percent_of_service"

#: `CR-130-BRC07` · `BR-RAT-1030` — the two percent bases, imported rather than
#: restated. `apps/rating/pricing/percent_basis.py` is the one statement of this
#: vocabulary in the module; the column default, the projection, the selector
#: and the plugin all read it from there.
PERCENT_BASES = percent_basis.PERCENT_BASES
PERCENT_BASIS_USAGE = percent_basis.PERCENT_BASIS_USAGE
PERCENT_BASIS_CHARGE = percent_basis.PERCENT_BASIS_CHARGE
TARIFF_MODELS = (
    MODEL_FLAT,
    MODEL_TIERED,
    MODEL_TOU,
    MODEL_DEMAND,
    MODEL_SEASONAL,
    MODEL_CAPACITY,
    MODEL_PERCENT,
)

DAY_TYPES = ("weekday", "weekend", "holiday")  # r5 #17
# BR-RAT-067 (PO 2026-08-16, OQ-236): the utility STATES which metered register each
# window reads. The vocabulary is METERING's (B2 r8 / BR-MET-059) and is defined once,
# on the column, in apps/rating/models.py — imported rather than retyped so a fourth
# register can never be added in one place and missed in the other.
TOU_CHANNELS = models.TOU_CHANNELS
MAX_TOU_WINDOWS = 3  # BR-RAT-021 Option B: up to 3 windows per season × day-type
MAX_TOU_SEASONS = 2  # BR-RAT-021: two seasons covering the year
MINUTES_PER_DAY = 24 * 60
DAYS_PER_YEAR = 365  # season coverage is checked on a non-leap reference year

#: ── THE FIFTH CHARGE TYPE (PO ruling 2026-08-21, closes OQ-287) ────────────
#: CR-013 part 2 names FIVE types and the product stored FOUR. The PO ruled on
#: both halves of the question and they got opposite answers:
#:
#:   · **THE NAMING: NO CHANGE.** PO verbatim: *"No changes here"*. `refundable`
#:     is NOT renamed to `deposit` and `penalty` is NOT renamed to
#:     `event_driven`. Every existing row keeps its value, the landing filter
#:     keeps its four, and no data migration was needed for the naming half.
#:   · **THE FIFTH TYPE: ADD IT.** PO verbatim: *"add adjustment"*. This is the
#:     one genuinely NEW capability in the five, and its absence had a cost: a
#:     `-$74.60` over-read correction had nowhere to go, so a clerk filed it as
#:     a negative `penalty` (which puts a customer credit in the late-fee bucket
#:     and makes the late-fee report wrong by that amount) or cut a refund
#:     cheque to a customer who was staying.
#:
#: An `adjustment` is a CREDIT OR CORRECTION — the over-read rebill, the
#: goodwill credit after a main break, the misapplied-rate correction. It is
#: the only type whose amount is routinely NEGATIVE, and hard rule 4 still
#: holds: an issued invoice is never edited, so an adjustment is a NEW LINE on
#: the next bill, not a change to the last one.
CHARGE_TYPES = ("recurring", "one_time", "refundable", "penalty", "adjustment")
AMOUNT_RULES = ("flat", "percent", "percent_with_minimum", "per_case")  # BR-RAT-041 v1 set
#: ── `per_case` — THE AMOUNT IS ENTERED WHEN THE FEE IS USED (DEF-RAT-8753) ──
#: CR-010 A2, PO 2026-08-17: TAP, IMPACT, DAMAGE and BULK-WATER are priced at
#: *"actual cost, entered per case"*; the PO-approved charge-code mock-up draws
#: the same pricing as *"Amount is entered when the fee is used"* (images 41,
#: 64, 70). Until this value existed such a code was stored with NO rule and no
#: amount, byte-identical to a code nobody had priced (`DEF-2340`). A `per_case`
#: code states NO price row — `_validate_charge` refuses one — and a fee bill
#: takes the clerk's amount for it and for nothing else (`billing.fee_bill`).
AMOUNT_RULE_PER_CASE = "per_case"
AMOUNT_RULE_FORMULA = "formula"  # visible in the UI, DISABLED in v1 (BR-RAT-041)
RECURRENCES = ("once", "recurring", "event")  # r5 #9

#: BR-RAT-036 as AMENDED 2026-08-21 (PO ruling, option C, DEF-386). The rule
#: ratified three forms and CR-013 part 4 names four; `per_meter` is the
#: fourth. It prices a COUNT OF METERS and takes no UoM — see the column's
#: docstring on `models.Tax` for why it is not `per_unit` with a odd unit.
TAX_KINDS = ("percent", "flat_per_bill", "per_unit", "per_meter")  # BR-RAT-036
FLAT_FREQUENCIES = ("per_bill", "per_fiscal_year")
FILING_FREQUENCIES = ("monthly", "quarterly", "annual")
JURISDICTION_LEVELS = ("federal", "state", "county", "city", "special_district")
#: DEF-273 (PO ruling 2026-08-18) — the PLATFORM consumer categories a tax may
#: be restricted to, and (BR-RAT-108) a base charge code priced for. It is also
#: the vocabulary `migrate_base_to_charge_codes` accepts a plan's class from.
#:
#: ⚠ **DERIVED, NOT TYPED, SINCE 2026-08-30 — THAT IS `DEF-738`.** This line was
#: a hand-typed four-tuple, right when it was written and stale from the day
#: BR-CUS-094 (PO 2026-08-24) expanded the signed vocabulary to seven plus
#: `government` as legacy. It failed CLOSED, so nothing ever broke: a tax
#: restricted to an Agricultural, Institutional, Municipal or Builder-developer
#: customer was simply REFUSED at creation, and the customer the utility wrote
#: it for was charged nothing by a rate that looked configured. The mirror had a
#: guard; the guard had been red for two days and nobody read it. So the fix is
#: not a wider copy — `seams.account_type_codes()` reads the vocabulary from
#: `customers.AccountType`, the module that owns it, and there is no second copy
#: left in rating to drift. See that seam's docstring for the B2 §2 disposition
#: and for why `government` stays in the list.
#:
#: Evaluated ONCE at import: the source is the model's declared constants, not
#: its rows, so there is no query here and no database is touched.
#:
#: ⚠ **THIS IS THE VOCABULARY *AS RULED*, AND SINCE `BR-CUS-094a` IT IS NO
#: LONGER WHAT VALIDATES A WRITE (PO 2026-09-17, "utility can get their own
#: account types").** A tenant may now add a class the platform never seeded, so
#: what may be PICKED is what that tenant's rows say —
#: `seams.selectable_account_type_codes()`, read at call time, is what every
#: validator below uses. This constant stays for the two jobs a query cannot do:
#: it is the RULED half that `test_def273_the_class_vocabulary_mirrors_the_
#: platform_account_types` compares the seeded rows against (derive it from rows
#: and that guard compares the rows with themselves — `DEF-182`), and it is what
#: `endpoints.ts`'s front-end mirror is held equal to. **Do not point it at the
#: table.**
TAX_CUSTOMER_CLASSES = seams.account_type_codes()
#: CR-013 part 4's FIVE scope mechanisms, the PO's own words (2026-08-18,
#: `TAXES-FEES-BUSINESS-SPEC.md`, TAX-02 step 1): *"how the system decides a
#: premise is in scope (city limits, county, state, taxing district, explicit
#: premise list)"*. All five are storable; `selectors.premises_in_scope` can
#: today ANSWER only `city_limits` and `state`, and the other three fail closed
#: — a scope the product cannot evaluate must never become "applies to all".
#: Bounded here AND by `ck_taxes_premises_scope_kind`.
PREMISES_SCOPE_KINDS = (
    "city_limits",
    "county",
    "state",
    "taxing_district",
    "premise_list",
)
#: The subset a bill run can actually resolve today, named so the gap is a fact
#: in the code rather than a paragraph in a report (hard-won law 1).
#:
#: ⚠ RE-EXPORTED, NOT DECLARED. The list is a statement about what
#: `selectors.premises_in_scope` does, so it is declared beside that function
#: and this name is kept so every caller — and the frontend mirror in
#: `endpoints.ts`, which cites this module by path — is unchanged. Two copies of
#: a statement about one function is how the statement stops being true.
PREMISES_SCOPE_KINDS_RESOLVABLE = selectors.PREMISES_SCOPE_KINDS_RESOLVABLE
GRACE_MODES = ("calendar", "business")
MAX_GRACE_DAYS = 30  # BR-BIL-008 bound, validated on the plan override

BULK_CHANGE_KINDS = ("percent", "set")
RATE_CHANGE_JOB = "rating.bulk_rate_update"

SIX_PLACES = Decimal("0.000001")  # DB-3 storage precision, NOT money rounding
#: A stored fraction is a fraction of ONE; a percent is per HUNDRED. Named
#: because `/ 100` in the body reads as a magic number and this is the only
#: thing it can mean. `selectors.PERCENT_SCALE` is the same constant on the READ
#: side; both exist because a module importing the other for one Decimal would
#: be a cycle, and the value is a fact about arithmetic rather than a policy
#: that could drift.
PERCENT_SCALE = Decimal("100")


# ── shared plumbing ─────────────────────────────────────────────────────────
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
    """Hard rule 7 / BR-AUD-001: one audit row per config or money action."""
    core_audit.write_row(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before=before,
        after=after,
    )


def _actor_user_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


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


def _require_dict(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="rating.payload_not_object")
    return payload


def _reject_unknown(
    payload: dict[str, Any], allowed: tuple[str, ...], fe: list[dict[str, Any]], prefix: str = ""
) -> None:
    """Unknown keys are refused, never ignored — the S13 "Fees"/"tax-on-tax"
    boxes are exactly the fields that must not be expressible (BR-RAT-036)."""
    for field in sorted(set(payload) - set(allowed)):
        fe.append(_field_error(f"{prefix}{field}", errors.VAL_FORMAT, "rating.unknown_field"))


def _text(
    payload: dict[str, Any],
    field: str,
    fe: list[dict[str, Any]],
    *,
    required: bool = False,
    max_length: int = 200,
    prefix: str = "",
) -> str | None:
    if field not in payload or payload[field] is None:
        if required:
            fe.append(_field_error(f"{prefix}{field}", errors.VAL_REQUIRED, "rating.required"))
        return None
    value = str(payload[field]).strip()
    if not value:
        if required:
            fe.append(_field_error(f"{prefix}{field}", errors.VAL_REQUIRED, "rating.required"))
        return None
    if len(value) > max_length:
        fe.append(
            _field_error(f"{prefix}{field}", errors.VAL_RANGE, "rating.too_long", max=max_length)
        )
        return None
    return value


def _choice(
    payload: dict[str, Any],
    field: str,
    allowed: tuple[str, ...],
    fe: list[dict[str, Any]],
    *,
    required: bool = False,
    prefix: str = "",
) -> str | None:
    value = _text(payload, field, fe, required=required, prefix=prefix)
    if value is None:
        return None
    value = value.lower()
    if value not in allowed:
        fe.append(
            _field_error(
                f"{prefix}{field}",
                errors.VAL_UNKNOWN_LOOKUP,
                "rating.unknown_value",
                allowed=list(allowed),
            )
        )
        return None
    return value


def _decimal(
    payload: dict[str, Any],
    field: str,
    fe: list[dict[str, Any]],
    *,
    required: bool = False,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
    prefix: str = "",
) -> Decimal | None:
    """Money/quantity coercion. Decimal only — HR-2 forbids float on money.

    ``maximum`` exists for BR-RAT-094 (DEF-411 option B): a plan charge rule's
    ``amount_override`` is a DISCOUNT, so it is bounded ABOVE by zero. The
    symmetry with ``minimum`` is deliberate — one helper, two ends, one shape
    of field error, so no caller invents its own range check.
    """
    if field not in payload or payload[field] is None:
        if required:
            fe.append(_field_error(f"{prefix}{field}", errors.VAL_REQUIRED, "rating.required"))
        return None
    raw = payload[field]
    if isinstance(raw, float):  # HR-2: a float amount never enters the money path
        fe.append(_field_error(f"{prefix}{field}", errors.VAL_FORMAT, "rating.money_not_decimal"))
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        fe.append(_field_error(f"{prefix}{field}", errors.VAL_FORMAT, "rating.not_a_number"))
        return None
    if minimum is not None and value < minimum:
        fe.append(
            _field_error(
                f"{prefix}{field}", errors.VAL_RANGE, "rating.below_minimum", minimum=str(minimum)
            )
        )
        return None
    if maximum is not None and value > maximum:
        fe.append(
            _field_error(
                f"{prefix}{field}", errors.VAL_RANGE, "rating.above_maximum", maximum=str(maximum)
            )
        )
        return None
    return value


def _q6(value: Decimal) -> Decimal:
    """Quantize to the NUMERIC(18,6) storage precision (DB-3)."""
    return value.quantize(SIX_PLACES)


def _date_value(
    payload: dict[str, Any],
    field: str,
    fe: list[dict[str, Any]],
    *,
    required: bool = False,
    prefix: str = "",
) -> date | None:
    if field not in payload or payload[field] in (None, ""):
        if required:
            fe.append(_field_error(f"{prefix}{field}", errors.VAL_REQUIRED, "rating.required"))
        return None
    try:
        return date.fromisoformat(str(payload[field]))
    except ValueError:
        fe.append(_field_error(f"{prefix}{field}", errors.VAL_FORMAT, "rating.bad_date"))
        return None


def _time_value(
    payload: dict[str, Any], field: str, fe: list[dict[str, Any]], *, prefix: str = ""
) -> time | None:
    raw = payload.get(field)
    if raw in (None, ""):
        fe.append(_field_error(f"{prefix}{field}", errors.VAL_REQUIRED, "rating.required"))
        return None
    text = str(raw)
    for pattern in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).time()
        except ValueError:
            continue
    fe.append(_field_error(f"{prefix}{field}", errors.VAL_FORMAT, "rating.bad_time"))
    return None


def _bool(payload: dict[str, Any], field: str, default: bool = False) -> bool:
    return bool(payload.get(field, default))


def _uuid_value(
    payload: dict[str, Any],
    field: str,
    fe: list[dict[str, Any]],
    *,
    required: bool = False,
    prefix: str = "",
) -> UUID | None:
    if field not in payload or payload[field] in (None, ""):
        if required:
            fe.append(_field_error(f"{prefix}{field}", errors.VAL_REQUIRED, "rating.required"))
        return None
    try:
        return UUID(str(payload[field]))
    except (ValueError, AttributeError, TypeError):
        fe.append(_field_error(f"{prefix}{field}", errors.VAL_FORMAT, "rating.bad_uuid"))
        return None


def _validated_gl_account(
    payload: dict[str, Any],
    field: str,
    fe: list[dict[str, Any]],
    *,
    message_key: str,
    prefix: str = "",
) -> UUID | None:
    """A GL pointer that is a uuid AND is this tenant's own live account.

    ── WHY THIS EXISTS (CR-008 second-set ruling 3, PO 2026-08-17) ───────────
    The PO ruled that an account is validated **when it is picked, not only
    when a bill runs**. The measured problem, in their terms: *"a mapping can
    look correct on screen for weeks and fail on the day a bill runs, which is
    when a utility can least afford it."*

    Before this, `charges.gl_account_id` and `plan_services.gl_account_id`
    accepted **any well-formed uuid** — `_uuid_value` and nothing else. A uuid
    belonging to another utility's chart, a uuid of an account this tenant had
    deactivated, or a uuid of nothing at all were all stored without complaint,
    and the first anyone heard of it was `BR-BIL-010` refusing the WHOLE bill
    at issue, atomically, on billing day.

    ── WHAT IT DOES NOT CHANGE ──────────────────────────────────────────────
    The issue-time check STAYS. This is an earlier refusal, not a replacement:
    an account that is live today can be deactivated tomorrow, so the run must
    still ask. Two checks on one fact, on purpose — the same posture
    `post_payment_cleared` takes on debits-equal-credits.

    `null` / `""` CLEARS the mapping and is accepted, because retiring a
    mapping is a real thing a tenant does. Clearing is not silent: an unmapped
    charge shows the GAP banner on Settings → Accounting and refuses at issue
    by name.

    ── WHY THE LEDGER ANSWERS ───────────────────────────────────────────────
    `seams.ledger_account_is_live` — the table is the ledger's (B1), and the
    read answers OWNERSHIP as well as liveness in one call. An FK would prove
    the row exists and never prove it is THIS tenant's, which in a money path
    is the whole question. It REFUSES loudly rather than answering True when
    the ledger publishes no such read, so an unwired ledger stores nothing
    rather than storing anything.

    One refusal covers unknown, another tenant's, and deactivated — telling
    them apart would confirm the existence of another utility's account id.
    """
    account_id = _uuid_value(payload, field, fe, prefix=prefix)
    if account_id is None:
        return None
    if not seams.ledger_account_is_live(account_id):
        fe.append(
            _field_error(
                f"{prefix}{field}",
                errors.VAL_UNKNOWN_LOOKUP,
                message_key,
                account=str(account_id),
            )
        )
        return None
    return account_id


def _enabled_service(
    code: str | None, field: str, fe: list[dict[str, Any]], *, prefix: str = ""
) -> dict[str, Any] | None:
    """BR-RAT-024: the service must be in the platform catalog AND enabled for
    this tenant. A disabled service is refused, never silently accepted."""
    if code is None:
        return None
    row = seams.service_catalog_row(code)
    if row is None:
        fe.append(
            _field_error(f"{prefix}{field}", errors.VAL_UNKNOWN_LOOKUP, "rating.unknown_service")
        )
        return None
    if not seams.service_is_enabled(code):
        fe.append(
            _field_error(
                f"{prefix}{field}",
                errors.VAL_UNKNOWN_LOOKUP,
                "rating.service_not_enabled",
                service=code,
            )
        )
        return None
    return row


def _json_safe(value: Any) -> Any:
    """before/after jsonb payloads are plain JSON (r5 #14)."""
    return json.loads(json.dumps(value, default=str))


# ══════════════════════════════════════════════════════════════════════════
# Plans — US-RAT-001 / US-RAT-002 / US-RAT-003 (EP-RAT-01)
# ══════════════════════════════════════════════════════════════════════════
PLAN_FIELDS: tuple[str, ...] = (
    "name",
    "code",
    "description",
    # DEF-RAT-5768 (PO ruling 2026-09-19) — the class is a LIST now, and the
    # SCALAR key is gone from the accepted set on purpose: a payload still
    # sending `account_type_id` is refused BY NAME by `_reject_unknown` rather
    # than silently ignored, which is how a caller finds out it must migrate.
    "account_type_ids",
    "account_subtype_id",
    "budget_billing",
    "minimum_bill_amount",
    "effective_from",
    "effective_to",
    "eligibility",
    "services",
    "charge_rules",
    "deposit_rules",
    "penalty_rule",
    "tax_rules",
    # BR-RAT-110 (OQ-300 closed by the PO 2026-08-21 on option (A)) — PLN-03
    # step 6 BINDS discounts, which is BR-RAT-096's sentence applied one step
    # along: *"plan all steps are bascailly binding everything together"*. The
    # key was absent until 2026-08-21, so `plan_discount_rules` existed as a
    # table that no payload could name and `_reject_unknown` refused.
    "discounts",
    # ── BR-RAT-102's FACTOR, WRITABLE (CR-039 wave C task 11 · DEF-515) ──────
    # PO verbatim, 2026-08-21: *"We can have it on plan itself - Plan will
    # decide whether to apply and then how much."* Migration 0016 added the
    # column that same day and NO WRITER WAS BUILT WITH IT — no `PLAN_FIELDS`
    # entry, no serializer, no wizard control, no seeder payload — so the read
    # half was proved end to end on injected data and a real utility still
    # could not express *"we surcharge outside the city by 15 percent"*
    # (DEF-515). The seed CR-039 task 11 asks for cannot be written without
    # this key: a seeder reaching past `create_plan` to `.update()` a money
    # column is exactly what a 🔒 sensitive path may not do.
    #
    # ⚠ **NO CEILING IS IMPOSED, BECAUSE NO SIGNED DOCUMENT STATES ONE.** The
    # floor is 0 (a negative multiplier would invert every line of the bill,
    # which is not a surcharge in any reading). r10 draws `1.5` and BR-RAT-102
    # works `1.15`; neither is a maximum, and inventing one here would be this
    # lane choosing a rate — which `04-docs` reserves for the PO.
    "outside_city_factor",
    # ── THE SAME SURCHARGE, ASKED FOR AS A PERCENT (CR-087 D1 · `PRB-16`) ────
    # PO ruling 2026-09-08, in the decision log: *"The outside-city surcharge
    # stopped asking for arithmetic. 'Type 1.15 to charge 15% more' is a
    # multiplier a clerk computes, in a product where a neighbouring field takes
    # a percentage and another takes a fraction — 15 typed into it would have
    # charged fifteen times the bill."*
    #
    # ⚠ **THE COLUMN DOES NOT MOVE, AND THAT IS THE WHOLE DESIGN.**
    # `rate_plans.outside_city_factor` is read by `resolution.py`, `gather.py`,
    # `resolution_catalogue.py` and the audit snapshot, and it is the number
    # every priced line is MULTIPLIED by. This key is a second way IN — the
    # server converts once, `1 + percent/100` at six places — so nothing that
    # has ever been priced changes. The blueprint offered two shapes ("either
    # the API accepts a percent and converts once, or the column changes") and
    # this lane chose the first; the reasoning and the worked figure are in
    # `12-governance/02-decision-log.md`, 2026-09-08, "CR-087 LANE D" item 1.
    #
    # ⚠ **THE CONVERSION MAY NOT LIVE IN THE BROWSER.** A scale conversion
    # written into a screen is the same trap one layer up: two screens would
    # eventually disagree about which scale they were sending, and the one that
    # was wrong would multiply a bill rather than fail.
    "outside_city_percent",
    # ── THE LATE-FEE CHARGE CODE (BR-RAT-1011 · `CR-078`, PO 2026-09-07) ──────
    # PO verbatim: *"you ahve to take late fees form charge code mentione din
    # the plan - if plan doent provide you that charge code then you have to
    # put zero on late payment."* Accepted by id or by CODE, like
    # `charge_rules[].charge` and `discounts[].discount` — a utility typing
    # `LATE` should not have to find a uuid — and NULL is a legal value that
    # means *this plan charges no late fee*, which is why it is writable to
    # None rather than merely settable once.
    "late_fee_charge",
    # ── `CR-167-BRC10` ruling 9 · THE DEPOSIT CODES THE PLAN NAMES ───────────
    # `BR-RAT-023` as amended 2026-10-03: a list of `refundable` charge codes
    # (by id or code), stored as `plan_charge_rules` rows with `role="deposit"`
    # and read by customer class OR meter size — `OQ-RAT-12786` CLOSED
    # 2026-10-03, PO verbatim: *"(a) Class or size: the deposit table gets a
    # size column, like charge codes have."* (`BR-RAT-020` superseded in part).
    "deposits",
)
PLAN_CONTENT_FIELDS = PLAN_FIELDS  # everything except `reason` is plan content
PLAN_SERVICE_FIELDS = (
    "service",
    "base_charge",
    "currency",
    # ⚠ **`minimum_amount` IS NOT HERE ANY MORE, AND ITS ABSENCE IS A REFUSAL.**
    # PO ruling 2026-09-10: *"set it in rates and use it in plans - thats it -
    # this is rule"*. The per-service floor is set on the RATE SCHEDULE
    # (`tariff_versions.minimum_bill`) and a plan SHOWS it. `_reject_unknown`
    # runs over this tuple, so a client still posting the field is told so by
    # name instead of having its figure accepted and dropped — which is the
    # difference between a clerk seeing a refusal and a plan quietly losing its
    # floor. Migrations `rating/0030` (move) + `0031` (remove).
    "gl_account_id",
    "tariff",
    # BR-RAT-102: *"The per-SERVICE exemption R5 reads belongs on the plan's own
    # service line, because the plan is what lists its services."* Design §A4 S2
    # is the worked case and r10 says it in four words — *"sewer is flat
    # everywhere"*: the sewer base stays $8.00 while every other line moves.
    # Landed with migration 0016 and had no writer either (DEF-515).
    "outside_city_exempt",
)
PLAN_CHARGE_RULE_FIELDS = ("charge", "amount_override", "recurrence", "taxable")
PLAN_DEPOSIT_RULE_FIELDS = ("account_type_id", "amount", "currency")


def _customer_class_ids(payload: dict[str, Any], fe: list[dict[str, Any]]) -> list[str]:
    """`rate_plans.account_type_ids` — a list of platform `account_types` ids.

    **DEF-RAT-5768, PO ruling 2026-09-19.** The plan held ONE class and now
    holds a set of them, with **NULL or `[]` meaning EVERY class** — the
    semantics `charges.applies_to_customer_classes` has carried since
    `DEF-273`, so the product answers this question one way rather than two.

    ⚠ **`null` AND `[]` BOTH STORE `[]`.** They are the same fact in this
    vocabulary and keeping them apart would give a screen a distinction it
    cannot draw and a reader a branch that means nothing. (That is the
    opposite disposition from `charge_row`'s served list, which keeps them
    apart because a SERVER may distinguish *unset* from *explicitly every* on
    a row a clerk did not write. Here the clerk always writes the whole set.)

    ⚠ **THE WHOLE SET IS REPLACED, NEVER MERGED** — the posture
    `applies_to_customer_classes` takes and the one the chip control on step 1
    states: the control means *these and no others*, and a merge would leave a
    removed class attached for ever.

    ⚠ **A DUPLICATE IS REFUSED RATHER THAN DEDUPED.** A payload naming one
    class twice is a caller bug, and quietly collapsing it makes what was
    stored differ from what was sent with nothing saying so.
    """
    raw = payload.get("account_type_ids")
    if raw is None:
        return []
    if not isinstance(raw, list):
        fe.append(
            _field_error("account_type_ids", errors.VAL_FORMAT, "rating.plans.classes_not_a_list")
        )
        return []
    out: list[str] = []
    for index, item in enumerate(raw):
        # The field NAME a refusal carries is the indexed path, so a clerk's
        # screen can point at the offending chip rather than the whole field —
        # the same shape `deposit_rules[i].account_type_id` already uses.
        field = f"account_type_ids[{index}]"
        value = _uuid_value({field: item}, field, fe)
        if value is None:
            continue
        if str(value) in out:
            fe.append(
                _field_error(field, errors.VAL_FORMAT, "rating.plans.duplicate_customer_class")
            )
            continue
        out.append(str(value))
    return out
PLAN_PENALTY_FIELDS = ("late_fee_min", "late_fee_pct", "grace_days", "grace_mode")
#: BR-RAT-1011 — the charge code every tenant is seeded with
#: (`apps/tenancy/fixtures/lookup_defaults.json`, `percent 1.5, min_amount 5`).
#: It is a SEED NAME, not a vocabulary: `rate_plans.late_fee_charge_id` is a
#: real foreign key, so a utility that calls theirs `LATEPAY` points the plan at
#: it and nothing here has to know the string. This constant is used in exactly
#: one place — the default a NEW plan starts with.
SEEDED_LATE_FEE_CODE = "LATE"
#: BR-RAT-094 (PO ruling 2026-08-20, DEF-411 option B) — `rate_override` is NOT
#: accepted. A plan may not change what a jurisdiction charges. Part 5:
#: *"may not ... exclude a statutory tax"*, and unlike the charge override
#: nothing was ever signed defending this one. The COLUMN stays until a
#: migration removes it, so no stored figure is destroyed; the door is shut here.
#: `tax` joined the set with BR-RAT-113 (PO 2026-08-21, CR-021: *"staff need to
#: pick up and attach taxes and fees on the plan"*) — a row states EXACTLY ONE
#: of the two: `jurisdiction` binds an authority (BR-RAT-096), `tax` attaches
#: one catalogue tax/fee beyond what the bound authorities bring.
PLAN_TAX_RULE_FIELDS = ("jurisdiction", "tax")
#: BR-RAT-110 — three keys, and the ABSENT fourth is the ruling. r10 draws a
#: per-plan discount VALUE override (`SMARTBillHub.dc.html:10805`) and the PO
#: refused it on 2026-08-19: *"no plan cannot override prices."* So
#: `plan_discount_rules` has no value column, and naming one here would be the
#: first half of making the forbidden thing storable. A plan chooses WHICH
#: discounts it offers and for HOW LONG it offers them; never at what value.
PLAN_DISCOUNT_RULE_FIELDS = ("discount", "available_from", "available_to")


def _validate_plan(payload: dict[str, Any], *, partial: bool, plan: Any = None) -> dict[str, Any]:
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, PLAN_FIELDS + ("reason",), fe)
    cleaned: dict[str, Any] = {}

    name = _text(payload, "name", fe, required=not partial, max_length=120)
    if name is not None:
        duplicate = models.RatePlan.objects.filter(tenant_id=_tenant_id(), name=name)
        if plan is not None:
            duplicate = duplicate.exclude(pk=plan.pk)
        if duplicate.exists():
            # US-RAT-002 TC-7: (tenant, name) uniqueness, named inline.
            fe.append(_field_error("name", errors.VAL_FORMAT, "rating.plans.duplicate_name"))
        cleaned["name"] = name

    code = _text(payload, "code", fe, required=not partial, max_length=40)
    if code is not None:
        duplicate = models.RatePlan.objects.filter(tenant_id=_tenant_id(), code__iexact=code)
        if plan is not None:
            duplicate = duplicate.exclude(pk=plan.pk)
        if duplicate.exists():
            fe.append(_field_error("code", errors.VAL_FORMAT, "rating.plans.duplicate_code"))
        cleaned["code"] = code

    if "description" in payload:
        cleaned["description"] = _text(payload, "description", fe, max_length=2000)
    # ── DEF-RAT-5768 · THE CUSTOMER CLASSES, AS A LIST ────────────────────
    # PO ruling 2026-09-19: *"your understanding is correct - we have all
    # option anyway in drop down list - that is default"*. `[]` is a real and
    # DEFAULT answer — *every class* — so an empty list is accepted and stored
    # rather than folded into None; and an absent key leaves the stored set
    # alone, which is what makes `partial=True` an update of the fields named.
    if "account_type_ids" in payload:
        cleaned["account_type_ids"] = _customer_class_ids(payload, fe)
    if "account_subtype_id" in payload:
        cleaned["account_subtype_id"] = _uuid_value(payload, "account_subtype_id", fe)
    if "budget_billing" in payload:
        cleaned["budget_billing"] = _bool(payload, "budget_billing")  # BR-RAT-043 plan flag
    if "minimum_bill_amount" in payload:
        cleaned["minimum_bill_amount"] = _decimal(
            payload, "minimum_bill_amount", fe, minimum=Decimal("0")
        )
    if "outside_city_factor" in payload and "outside_city_percent" in payload:
        # ⚠ TWO ANSWERS TO ONE QUESTION (CR-087 D1). Reconciling them by
        # precedence would make one of them lose SILENTLY — and the one that
        # loses is a multiplier on every line of a bill. The refusal names the
        # percent, which is the newer key and the one a screen sends.
        fe.append(
            _field_error(
                "outside_city_percent",
                errors.VAL_FORMAT,
                "rating.plans.surcharge_stated_twice",
            )
        )
    elif "outside_city_percent" in payload:
        # CR-087 D1 — THE PERCENT IN, THE MULTIPLIER STORED, converted HERE and
        # nowhere else. `15` becomes `1.150000`, so a $100.00 bill outside the
        # city becomes $115.00. The old field asked for `1.15`, and `15` typed
        # into THAT multiplied every line by fifteen.
        #
        # ⚠ **THE FLOOR IS −100 AND NOT 0.** The factor's floor is zero (a
        # negative multiplier inverts the bill); −100% is exactly what makes the
        # factor zero, so the two floors are the same statement said on two
        # scales. Anything below it produces a negative factor.
        percent = _decimal(
            payload, "outside_city_percent", fe, minimum=Decimal("-100")
        )
        if percent is not None:
            # SIX places (BR-RAT-092 / CLAUDE.md hard rule 2 — percentages to 6).
            cleaned["outside_city_factor"] = _q6(Decimal("1") + percent / PERCENT_SCALE)
        elif payload.get("outside_city_percent", "") is None:
            # An explicit null is *this plan does not surcharge*, which is the
            # column's own NULL. `_decimal` returns None for both that and a bad
            # value, so the two are told apart by looking at the payload.
            cleaned["outside_city_factor"] = None
    elif "outside_city_factor" in payload:
        # BR-RAT-092 puts a RATE at six places, not four: a multiplier is
        # multiplied by something before it becomes money, so truncating it
        # moves the bill while truncating an amount only moves itself. The
        # column is `rate_field` for exactly that reason (migration 0016).
        cleaned["outside_city_factor"] = _decimal(
            payload, "outside_city_factor", fe, minimum=Decimal("0")
        )
    if "late_fee_charge" in payload:
        # BR-RAT-1011 (`CR-078`). `in payload` and not truthiness: `None` is a
        # LEGAL value here meaning *charge no late fee*, and a truthiness test
        # would make clearing the control impossible — the utility could point
        # a plan at a code and never take it off again.
        cleaned["late_fee_charge"] = _validate_late_fee_charge(payload["late_fee_charge"], fe)
    effective_from = (
        _date_value(payload, "effective_from", fe) if "effective_from" in payload else None
    )
    effective_to = _date_value(payload, "effective_to", fe) if "effective_to" in payload else None
    if "effective_from" in payload:
        cleaned["effective_from"] = effective_from
    if "effective_to" in payload:
        cleaned["effective_to"] = effective_to
    if effective_from and effective_to and effective_from >= effective_to:
        fe.append(_field_error("effective_to", errors.VAL_RANGE, "rating.plans.window_inverted"))

    if "eligibility" in payload:
        # BR-RAT-043: ADVISORY ONLY in v1. US-RAT-002 §5 stores it ON THE PLAN
        # (rate_plans.eligibility jsonb) so the ticked boxes survive a reload;
        # it is never read as a gate — assignment cannot be blocked by it, and
        # the staff attestation still happens at assignment time (customers).
        eligibility = payload["eligibility"]
        if eligibility is not None and not isinstance(eligibility, dict):
            fe.append(_field_error("eligibility", errors.VAL_FORMAT, "rating.bad_eligibility"))
        cleaned["eligibility"] = eligibility or {}

    if "services" in payload:
        cleaned["services"] = _validate_plan_services(payload["services"], fe)
    if "charge_rules" in payload:
        cleaned["charge_rules"] = _validate_plan_charge_rules(payload["charge_rules"], fe)
    if "deposit_rules" in payload:
        cleaned["deposit_rules"] = _validate_plan_deposit_rules(payload["deposit_rules"], fe)
    if "penalty_rule" in payload:
        cleaned["penalty_rule"] = _validate_plan_penalty_rule(payload["penalty_rule"], fe)
    if "tax_rules" in payload:
        cleaned["tax_rules"] = _validate_plan_tax_rules(payload["tax_rules"], fe)
    if "discounts" in payload:
        cleaned["discounts"] = _validate_plan_discount_rules(payload["discounts"], fe)
    if "deposits" in payload:
        cleaned["deposits"] = _validate_plan_deposit_codes(payload["deposits"], fe)

    _refuse(fe)
    return cleaned


def _validate_plan_services(raw: Any, fe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Step 2 + 3: one row per ticked service with its own base charge
    (BR-RAT-012/027) and at most one schedule per service (D2)."""
    rows: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        fe.append(_field_error("services", errors.VAL_FORMAT, "rating.plans.services_not_list"))
        return rows
    seen: set[tuple[str, str | None]] = set()
    for index, item in enumerate(raw):
        prefix = f"services[{index}]."
        if not isinstance(item, dict):
            fe.append(
                _field_error(f"{prefix}", errors.VAL_FORMAT, "rating.plans.service_not_object")
            )
            continue
        _reject_unknown(item, PLAN_SERVICE_FIELDS, fe, prefix=prefix)
        code = _text(item, "service", fe, required=True, prefix=prefix)
        service = _enabled_service(code, "service", fe, prefix=prefix)
        if service is None:
            continue
        if service["code"] in seen:
            fe.append(
                _field_error(
                    f"{prefix}service", errors.VAL_FORMAT, "rating.plans.duplicate_service"
                )
            )
            continue
        seen.add(service["code"])
        # ⚠ **OPTIONAL SINCE 2026-08-21 — DEF-477, AND IT IS A MONEY FIX.**
        # This was `required=True`, which predates BR-RAT-088 by weeks: the
        # ruling of 2026-08-20 moved the base amount onto the CHARGE CODE and
        # says *"a plan displays the base rather than defining it"*, so a write
        # path that DEMANDS the figure demands the one thing a plan may not
        # state. The two halves compounded: `PlanWizard.planPayload` sent the
        # literal `"0"` for a blank because this validator refused an omission,
        # so the first ordinary save after BR-RAT-088's migration nulls the
        # column — a rename, a description edit, adding a charge rule — wrote a
        # stored `0.000000` straight back. A stored zero is a PRICE (PO ruling
        # 2026-08-19, *"print $0.00"*), so `gather._base_charge_for` stops
        # letting the schedule's figure answer and every base line on the plan
        # prints `$0.00`. On Silver Creek that is `$8.00` residential water,
        # `$15.00` commercial water and `$18.00` trash going to zero — DEF-154
        # exactly, reintroduced from a screen nobody would associate with money.
        # US-RAT-002 TC-6's `base ≥ 0` still holds for a figure that IS stated;
        # what is dropped is the demand that one be stated at all, so NULL means
        # *"this plan states no base"* and reaches the column intact.
        base_charge = _decimal(item, "base_charge", fe, minimum=Decimal("0"), prefix=prefix)
        tariff = None
        if item.get("tariff"):
            tariff_id = _uuid_value(item, "tariff", fe, prefix=prefix)
            if tariff_id is not None:
                # ⚠ **THE LOOKUP DELIBERATELY DOES NOT FILTER `deleted_at`, AND
                # THE REFUSAL BELOW IS WHY — `DEF-RAT-5693`.** It did, so an
                # ARCHIVED schedule fell into the `None` branch and was refused
                # as *"We don't recognise that rate schedule"* — said to
                # somebody who picked the value off a list the product had just
                # given them. The id resolves perfectly well; the row is
                # retired. Two different facts deserve two different sentences.
                #
                # The TENANT filter is untouched and is the one that matters:
                # another tenant's id is genuinely unknown here and must stay
                # that way (`test_us_rat_002_tc8__cross_tenant_schedule_is_never
                # _selectable`), because telling a caller that an id they cannot
                # see is *archived* would confirm it exists.
                tariff = models.Tariff.objects.filter(
                    tenant_id=_tenant_id(), pk=tariff_id
                ).first()
                if tariff is None:
                    fe.append(
                        _field_error(
                            f"{prefix}tariff",
                            errors.VAL_UNKNOWN_LOOKUP,
                            "rating.plans.unknown_schedule",
                        )
                    )
                    tariff = None
                elif tariff.deleted_at is not None:
                    # PO ruling 2026-09-17: *"so dont allow archive plans to be
                    # selected in plans - only active rates schedule should be
                    # selected"*. The picker no longer offers one
                    # (`selectableSchedules`), and this is the write path saying
                    # the same thing in the same words — a rule, not a UI filter.
                    fe.append(
                        _field_error(
                            f"{prefix}tariff",
                            errors.VAL_FORMAT,
                            "rating.plans.archived_schedule",
                        )
                    )
                    tariff = None
                elif tariff.service_id != service["id"]:
                    fe.append(
                        _field_error(
                            f"{prefix}tariff",
                            errors.VAL_FORMAT,
                            "rating.plans.schedule_service_mismatch",
                        )
                    )
                    tariff = None
                elif not selectors.schedule_is_activated(tariff):
                    # BR-RAT-031: "draft schedules are excluded from plan-builder
                    # pickers until activated" — enforced on the write path too,
                    # so the rule survives a hand-rolled request.
                    fe.append(
                        _field_error(
                            f"{prefix}tariff",
                            errors.VAL_FORMAT,
                            "rating.plans.draft_schedule",
                        )
                    )
                    tariff = None
        rows.append(
            {
                "service_id": service["id"],
                "service_code": service["code"],
                # DEF-277 — the plan's per-service base, absent when the
                # operator stated none. It filled in a zero here until
                # 2026-08-19, which made "this plan does not set a base for
                # water" indistinguishable from "water's base is zero" — and
                # ⚠ **AND WHO READS THAT DIFFERENCE MOVED ON 2026-09-28
                # (`DEF-BIL-7170`).** This said *"`gather._base_charge_for`
                # reads exactly that difference to decide whether the
                # schedule's figure may answer instead"* — it reads neither
                # column now. The DISTINCTION still matters, on the charge
                # code, where a stored zero is a price and a blank is not.
                "base_charge": base_charge,
                "currency": (item.get("currency") or "USD").upper()[:3],
                # CR-008 second-set ruling 3 — the plan's per-service revenue
                # override is validated at the pick, like every other GL
                # pointer. It was `_uuid_value` alone until 2026-08-17.
                "gl_account_id": _validated_gl_account(
                    item,
                    "gl_account_id",
                    fe,
                    message_key="rating.plans.gl_account_unknown",
                    prefix=prefix,
                ),
                "tariff": tariff,
                # BR-RAT-102 — defaults FALSE, and the default is the rule: a
                # service is surcharged unless the plan says otherwise. With no
                # factor anywhere the default reaches nothing (migration 0016).
                "outside_city_exempt": _bool(item, "outside_city_exempt"),
            }
        )
    return rows


def _validate_late_fee_charge(raw: Any, fe: list[dict[str, Any]]) -> Any:
    """The plan's late-fee charge code, by id or by code — or None meaning ZERO.

    BR-RAT-1011 (`CR-078`). Three answers and they are all different:

      * a live charge code of this tenant → the `Charge` row;
      * `None` / `""` → **None, and that is a legal value**, not a missing
        field. It is the PO's own case: *"if plan doent provide you that charge
        code then you have to put zero on late payment"*. A utility clearing
        this control is saying "we do not charge late fees on this plan" and
        the write must be able to express it;
      * anything else → a FIELD error naming the control, never a silent drop.
        A typo'd code that saved as NULL would look identical to the deliberate
        clear above and would stop the fee with nobody told — the whole shape
        this change exists to make visible.

    A RETIRED code is refused rather than stored (IS-1 — a retired charge is
    not chargeable): storing one would put the plan in the zero state by a
    route no screen explains.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    lookup = models.Charge.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
    try:
        charge = lookup.filter(pk=UUID(str(raw))).first()
    except (ValueError, AttributeError, TypeError):
        charge = lookup.filter(code=str(raw)).first()
    if charge is None:
        fe.append(
            _field_error(
                "late_fee_charge", errors.VAL_UNKNOWN_LOOKUP, "rating.plans.unknown_charge"
            )
        )
        return None
    return charge


def default_late_fee_charge() -> Any:
    """The charge code a NEW plan starts pointed at — the tenant's seeded one.

    ⚠ **THIS IS A SEEDED DEFAULT ON THE PLAN, NOT THE FALLBACK THE PO RULED
    AGAINST, AND THE DIFFERENCE IS WHERE THE ANSWER LIVES.** The rejected shape
    was an ENGINE that, finding no code on the plan, went and read the tenant's
    Billing-defaults screen — so a plan silently charged a fee nobody had
    attached to it. This writes the code ONTO THE PLAN at creation, where a
    human can see it on Plans & Rates and clear it. After this runs the plan
    NAMES a code; the engine still reads only what the plan names.

    It is also what stops the ruling from breaking every tenant provisioned
    tomorrow: without it, `CR-078`'s backfill fixes today's plans and every
    plan created afterwards charges $0.00 with nothing raising — the same
    silent failure one day later, which is `CR-068` R3's clock-in-a-rule shape
    (hard-won law 2's mirror).

    `LATE` is the code `apps/tenancy/fixtures/lookup_defaults.json` seeds on
    every tenant. A tenant that renamed or retired theirs gets None — a plan
    that charges no late fee until a human points it at one, which gate `G121`
    and `manage.py cr078_late_fee_codes` both count.
    """
    return (
        models.Charge.objects.filter(
            tenant_id=_tenant_id(), code=SEEDED_LATE_FEE_CODE, deleted_at__isnull=True
        )
        .order_by("created_at")
        .first()
    )


def _validate_plan_charge_rules(raw: Any, fe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """D7 attachments. Discounts are rows with a NEGATIVE amount_override —
    deliberately NOT sign-checked (BR-RAT-043)."""
    rows: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        fe.append(_field_error("charge_rules", errors.VAL_FORMAT, "rating.plans.rules_not_list"))
        return rows
    seen: set[Any] = set()
    nsf_code: str | None = None
    for index, item in enumerate(raw):
        prefix = f"charge_rules[{index}]."
        if not isinstance(item, dict):
            fe.append(_field_error(prefix, errors.VAL_FORMAT, "rating.plans.rule_not_object"))
            continue
        _reject_unknown(item, PLAN_CHARGE_RULE_FIELDS, fe, prefix=prefix)
        reference = item.get("charge")
        charge = None
        if reference:
            lookup = models.Charge.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
            try:
                charge = lookup.filter(pk=UUID(str(reference))).first()
            except (ValueError, AttributeError, TypeError):
                charge = lookup.filter(code=str(reference)).first()
        if charge is None:
            fe.append(
                _field_error(
                    f"{prefix}charge", errors.VAL_UNKNOWN_LOOKUP, "rating.plans.unknown_charge"
                )
            )
            continue
        if charge.id in seen:
            fe.append(
                _field_error(f"{prefix}charge", errors.VAL_FORMAT, "rating.plans.duplicate_charge")
            )
            continue
        if charge.is_nsf_fee and nsf_code is not None:
            # `DEF-RAT-10739` (PO 2026-10-31 P7) — a plan carries ONE NSF fee:
            # the bounce refuses two by name rather than charging by order.
            fe.append(
                _field_error(
                    f"{prefix}charge",
                    errors.VAL_FORMAT,
                    "rating.plans.second_nsf_fee",
                    charge_code=nsf_code,
                )
            )
            continue
        if charge.is_nsf_fee:
            nsf_code = charge.code
        if charge.is_base:
            # ── `DEF-RAT-9337` · A BASE CODE IS NOT A PLAN CHARGE CODE ──────────
            # It reaches the bill through the rate schedule (`BR-RAT-088`) and
            # `billable_charge_codes` already drops it, so a plan listing it as
            # a charge code stored a fact nothing bills — and the screens drew it
            # in one place and hid it in another. Refused by name; `rating/0063`
            # removed the rows already stored.
            fe.append(
                _field_error(
                    f"{prefix}charge",
                    errors.VAL_FORMAT,
                    "rating.plans.base_code_on_charges",
                    item=charge.code,
                )
            )
            continue
        seen.add(charge.id)
        rows.append(
            {
                "charge": charge,
                # BR-RAT-093 (PO ruling 2026-08-20, DEF-411 option B): kept for the
                # purpose BR-RAT-043 actually signed — *"plan discounts = NEGATIVE-
                # amount charge rules on the plan"* — and gated to that purpose.
                #
                # A NEGATIVE value is a discount and is allowed. A POSITIVE value is
                # a plan REPRICING a charge, which part 5 forbids in the sentence the
                # whole CR rests on: *"a plan composes; it does not price."* §A3
                # priced the failure — a clerk editing one line silently moves 842
                # bills with no version, no date and no record of who approved it.
                #
                # `maximum=0` states it where every other numeric bound is stated,
                # so the refusal reads like every other one on this form.
                "amount_override": _decimal(
                    item, "amount_override", fe, maximum=Decimal("0"), prefix=prefix
                ),
                "recurrence": _choice(item, "recurrence", RECURRENCES, fe, prefix=prefix)
                or "event",
                "taxable": _bool(item, "taxable"),
            }
        )
    return rows


def _validate_plan_deposit_codes(raw: Any, fe: list[dict[str, Any]]) -> list[Any]:
    """`CR-167-BRC10` ruling 9 — the Deposits table: `refundable` charge codes
    by id or code, each once, priced by customer class or by meter size
    (`BR-RAT-023` as amended 2026-10-03; `OQ-RAT-12786` CLOSED the same day,
    PO verbatim *"(a) Class or size: the deposit table gets a size column, like
    charge codes have."*). An empty row, a repeat and a code that is not a
    deposit are each refused BY NAME. ⚠ The by-size refusal that stood here
    (`rating.plans.deposit_code_priced_by_size`) is REMOVED by that ruling: a
    sized code is priced at the connection size of the service it names
    (`selectors.plan_deposit_for`)."""
    out: list[Any] = []
    if not isinstance(raw, list):
        fe.append(_field_error("deposits", errors.VAL_FORMAT, "rating.plans.rules_not_list"))
        return out
    seen: set[Any] = set()
    for index, item in enumerate(raw):
        reference = item.get("charge") if isinstance(item, dict) else item
        field = f"deposits[{index}].charge"
        if reference in (None, ""):
            fe.append(
                _field_error(
                    field, errors.VAL_REQUIRED, "rating.plans.row_empty", table="deposits", row=index + 1
                )
            )
            continue
        lookup = models.Charge.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
        try:
            charge = lookup.filter(pk=UUID(str(reference))).first()
        except (ValueError, AttributeError, TypeError):
            charge = lookup.filter(code=str(reference)).first()
        if charge is None:
            fe.append(_field_error(field, errors.VAL_UNKNOWN_LOOKUP, "rating.plans.unknown_charge"))
            continue
        if charge.id in seen:
            fe.append(
                _field_error(field, errors.VAL_FORMAT, "rating.plans.deposit_listed_twice", item=charge.code)
            )
            continue
        if charge.charge_type != "refundable":
            fe.append(
                _field_error(field, errors.VAL_FORMAT, "rating.plans.deposit_code_not_deposit", item=charge.code)
            )
            continue
        seen.add(charge.id)
        out.append(charge)
    return out


def _validate_plan_deposit_rules(raw: Any, fe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """BR-RAT-020/023: fixed $ per consumer category, one row per category."""
    rows: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        fe.append(_field_error("deposit_rules", errors.VAL_FORMAT, "rating.plans.rules_not_list"))
        return rows
    seen: set[UUID] = set()
    for index, item in enumerate(raw):
        prefix = f"deposit_rules[{index}]."
        if not isinstance(item, dict):
            fe.append(_field_error(prefix, errors.VAL_FORMAT, "rating.plans.rule_not_object"))
            continue
        _reject_unknown(item, PLAN_DEPOSIT_RULE_FIELDS, fe, prefix=prefix)
        account_type_id = _uuid_value(item, "account_type_id", fe, required=True, prefix=prefix)
        amount = _decimal(item, "amount", fe, required=True, minimum=Decimal("0"), prefix=prefix)
        if account_type_id is None or amount is None:
            continue
        if account_type_id in seen:
            fe.append(
                _field_error(
                    f"{prefix}account_type_id", errors.VAL_FORMAT, "rating.plans.duplicate_category"
                )
            )
            continue
        seen.add(account_type_id)
        rows.append(
            {
                "account_type_id": account_type_id,
                "amount": amount,
                "currency": (item.get("currency") or "USD").upper()[:3],
            }
        )
    return rows


def _validate_plan_penalty_rule(raw: Any, fe: list[dict[str, Any]]) -> dict[str, Any] | None:
    """r5 #10 / D6: every NULL falls back to the tenant default at billing time
    (US-RAT-002 TC-2 — an untouched panel writes no row)."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        fe.append(_field_error("penalty_rule", errors.VAL_FORMAT, "rating.plans.rule_not_object"))
        return None
    fe_prefix = "penalty_rule."
    _reject_unknown(raw, PLAN_PENALTY_FIELDS, fe, prefix=fe_prefix)
    grace_days = raw.get("grace_days")
    parsed_days: int | None = None
    if grace_days not in (None, ""):
        try:
            parsed_days = int(grace_days)
        except (TypeError, ValueError):
            fe.append(
                _field_error(f"{fe_prefix}grace_days", errors.VAL_FORMAT, "rating.not_a_number")
            )
        else:
            if not 0 <= parsed_days <= MAX_GRACE_DAYS:
                fe.append(
                    _field_error(
                        f"{fe_prefix}grace_days",
                        errors.VAL_RANGE,
                        "rating.plans.grace_days_range",
                        max=MAX_GRACE_DAYS,
                    )
                )
                parsed_days = None
    return {
        "late_fee_min": _decimal(raw, "late_fee_min", fe, minimum=Decimal("0"), prefix=fe_prefix),
        "late_fee_pct": _decimal(raw, "late_fee_pct", fe, minimum=Decimal("0"), prefix=fe_prefix),
        "grace_days": parsed_days,
        "grace_mode": _choice(raw, "grace_mode", GRACE_MODES, fe, prefix=fe_prefix),
    }


def _validate_plan_tax_rules(raw: Any, fe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """D8 + BR-RAT-113: two row shapes, exactly one source per row.

    A row states `jurisdiction` (bind the authority — BR-RAT-096) OR `tax`
    (attach one catalogue tax/fee — BR-RAT-113); plan × jurisdiction UNIQUE and
    plan × tax UNIQUE, mirrored by the DB constraints. A tax that is ALSO
    brought by a bound jurisdiction may still be attached — the two paths
    de-duplicate at pricing (`selectors.plan_tax_rules`), so it bills once —
    because refusing it would make the validator re-derive the jurisdiction's
    tax set, a second copy of pricing's resolution that could drift from it.
    `rate_override` NULL = jurisdiction rate (write path closed, BR-RAT-094).
    """
    rows: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        fe.append(_field_error("tax_rules", errors.VAL_FORMAT, "rating.plans.rules_not_list"))
        return rows
    seen: set[UUID] = set()
    seen_taxes: set[UUID] = set()
    for index, item in enumerate(raw):
        prefix = f"tax_rules[{index}]."
        if not isinstance(item, dict):
            fe.append(_field_error(prefix, errors.VAL_FORMAT, "rating.plans.rule_not_object"))
            continue
        _reject_unknown(item, PLAN_TAX_RULE_FIELDS, fe, prefix=prefix)
        if "tax" in item and "jurisdiction" in item:
            # ck_plan_tax_rules_one_source, refused before the DB says it.
            fe.append(
                _field_error(f"{prefix}tax", errors.VAL_FORMAT, "rating.plans.rule_two_sources")
            )
            continue
        if "tax" in item:
            tax_id = _uuid_value(item, "tax", fe, required=True, prefix=prefix)
            if tax_id is None:
                continue
            tax = models.Tax.objects.filter(tenant_id=_tenant_id(), pk=tax_id).first()
            if tax is None:
                fe.append(
                    _field_error(
                        f"{prefix}tax", errors.VAL_UNKNOWN_LOOKUP, "rating.plans.unknown_tax"
                    )
                )
                continue
            if tax.id in seen_taxes:
                fe.append(
                    _field_error(f"{prefix}tax", errors.VAL_FORMAT, "rating.plans.duplicate_tax")
                )
                continue
            seen_taxes.add(tax.id)
            rows.append({"jurisdiction": None, "tax": tax, "rate_override": None})
            continue
        jurisdiction_id = _uuid_value(item, "jurisdiction", fe, required=True, prefix=prefix)
        if jurisdiction_id is None:
            continue
        jurisdiction = models.TaxJurisdiction.objects.filter(
            tenant_id=_tenant_id(), pk=jurisdiction_id
        ).first()
        if jurisdiction is None:
            fe.append(
                _field_error(
                    f"{prefix}jurisdiction",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "rating.plans.unknown_jurisdiction",
                )
            )
            continue
        if jurisdiction.id in seen:
            # US-RAT-009 TC-6: the same jurisdiction twice on one plan.
            fe.append(
                _field_error(
                    f"{prefix}jurisdiction",
                    errors.VAL_FORMAT,
                    "rating.plans.duplicate_jurisdiction",
                )
            )
            continue
        seen.add(jurisdiction.id)
        rows.append(
            {
                "jurisdiction": jurisdiction,
                "tax": None,
                # BR-RAT-094: refused above by omission from PLAN_TAX_RULE_FIELDS.
                # Served as None so the write path cannot carry one through.
                "rate_override": None,
            }
        )
    return rows


def _validate_plan_discount_rules(raw: Any, fe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PLN-03 step 6 — WHICH discounts this plan OFFERS (BR-RAT-110).

    ⚠ **BINDING A DISCOUNT HERE DISCOUNTS NOBODY, AND THAT IS THE POINT OF THE
    TABLE** (BR-RAT-069, CR-013 part 3: *"plan attachment makes a discount
    available, not granted"*). A bill run reads `discount_enrolments` and never
    `plan_discount_rules`. Read the availability row as the grant instead and
    every account on the plan is discounted — 842 of them on Residential
    Standard, every bill wrong by the discount.

    ⚠ **NO VALUE IS ACCEPTED** (`PLAN_DISCOUNT_RULE_FIELDS`). The dates narrow
    WHEN the plan offers it; nothing here says at what value.

    ⚠ **WHAT IS DELIBERATELY NOT CHECKED, so the absence reads as a decision.**
    `PlanDiscountRule`'s own docstring says the window is *"narrower than, never
    wider than, the discount's own effective window"*, and that is NOT enforced
    here. A discount's window lives on `discount_versions`, one row per version,
    and a discount may hold several with different windows — so "the discount's
    window" is not a single fact to compare against, and a check that picked one
    version would refuse legitimate bindings on the others. The inversion check
    below IS enforced, because `available_from >= available_to` is wrong under
    every reading. Widening is left to the discount's own effective-window
    resolution at pricing time, which already narrows correctly.

    Accepts a discount by **id or by code**, matching `_validate_plan_charge_rules`
    — the two steps sit beside each other in one wizard and a payload that works
    on step 4 must work on step 6.
    """
    rows: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        fe.append(_field_error("discounts", errors.VAL_FORMAT, "rating.plans.rules_not_list"))
        return rows
    seen: set[Any] = set()
    for index, item in enumerate(raw):
        prefix = f"discounts[{index}]."
        if not isinstance(item, dict):
            fe.append(_field_error(prefix, errors.VAL_FORMAT, "rating.plans.rule_not_object"))
            continue
        _reject_unknown(item, PLAN_DISCOUNT_RULE_FIELDS, fe, prefix=prefix)
        reference = item.get("discount")
        discount = None
        if reference:
            lookup = discount_models.Discount.objects.filter(tenant_id=_tenant_id())
            try:
                discount = lookup.filter(pk=UUID(str(reference))).first()
            except (ValueError, AttributeError, TypeError):
                discount = lookup.filter(code=str(reference)).first()
        if discount is None:
            fe.append(
                _field_error(
                    f"{prefix}discount",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "rating.plans.unknown_discount",
                )
            )
            continue
        if discount.id in seen:
            fe.append(
                _field_error(
                    f"{prefix}discount", errors.VAL_FORMAT, "rating.plans.duplicate_discount"
                )
            )
            continue
        seen.add(discount.id)
        available_from = _date_value(item, "available_from", fe, prefix=prefix)
        available_to = _date_value(item, "available_to", fe, prefix=prefix)
        if available_from and available_to and available_from >= available_to:
            fe.append(
                _field_error(
                    f"{prefix}available_to", errors.VAL_RANGE, "rating.plans.window_inverted"
                )
            )
            continue
        rows.append(
            {
                "discount": discount,
                "available_from": available_from,
                "available_to": available_to,
            }
        )
    return rows


def _close_dropped_discounts(
    plan: models.RatePlan,
    cleaned_rows: list[dict[str, Any]],
    actor: Any = None,
    note: str | None = None,
) -> set[Any]:
    """⚖️ TAKING A DISCOUNT OFF A PLAN STOPS IT FROM THE NEXT BILL — PO ruling
    2026-10-03 (2), which ANSWERS `OQ-322` (CLOSED the same day).

    The ruling, as put and accepted: *"Only accounts whose plan carries the
    discount can get it, and taking it off a plan stops it from the next
    bill."* This function used to be `_refuse_unruled_discount_unbind`, which
    raised `NotImplementedError("OQ-322")` whenever anybody, anywhere, was
    enrolled — so a discount could not be taken off a plan at all while it was
    in use (`DEF-RAT-9294`), and unbinding an unused one DELETED the row.

    What it does now, for every binding the save drops (our judgment for the
    mechanics, `CR-166` §7 item 4, decision log 2026-10-03):
      * the binding is ENDED the day before today (`available_to`), never
        deleted — the bill path already honours the window by SERVICE DATE
        (`selectors.billable_discount_rules`, BR-RAT-007), so a bill whose
        service date is before the removal keeps the discount and the next one
        does not;
      * every open enrolment in that discount, for an account on THIS plan, is
        ended on the same date with the reason *"Removed from plan <name>"*;
      * a binding that starts today or later is deleted (its window cannot
        end before it begins) — ⚠ AMENDED 2026-10-03 (`DEF-RAT-9512`): this
        line read *"it priced nothing and nobody could be enrolled through
        it"*, and the second half was false for a binding starting TODAY, which
        the enrolment gate accepts. Its enrollments are ended like any other's
        and its removal is audited on the discount itself.

    **Worked:** SENIOR taken off Residential Standard on 10/15/2026 → binding
    ends 10/14/2026; an October bill with service to 10/14 keeps the 15%; the
    November bill has none.

    A binding already ended stays as it is — it is history, and the wizard no
    longer shows it (`selectors.plan_discount_rules` serves bindings that have
    not ended). Returns the ids of the discounts kept or re-offered, which the
    caller uses to upsert.

    `note` (`DEF-478`, CR-166 follow-up, 2026-10-03) is the reason the PERSON
    gave — on the plan's own edit or on the discount page's × — and it is the
    reason the discount's Audit shows. The enrolment's own end reason stays
    *"Removed from plan <name>"*: that is what an account's history must say,
    whoever typed what.
    """

    today = seams.tenant_today()
    yesterday = today - timedelta(days=1)
    incoming = {row["discount"].id for row in cleaned_rows}
    for rule in discount_models.PlanDiscountRule.objects.filter(
        tenant_id=_tenant_id(), rate_plan=plan
    ).select_related("discount"):
        if rule.discount_id in incoming:
            continue
        if rule.available_to is not None and rule.available_to < today:
            continue  # already ended — history, left alone
        # ⚠ `DEF-RAT-9512` — A BINDING THAT STARTS TODAY HAS STARTED. It is
        # still deleted (its window cannot end before it begins), but it is
        # NOT skipped: the enrolment gate (`discount_ids_carried`) reads today,
        # so an account can be enrolled through it the day it is added, and
        # those enrollments end here like any other. The removal is written on
        # the DISCOUNT's own audit entity, so deleting the binding row does not
        # take the line off the discount's Audit (`discount_audit_filter`
        # reads bindings by the ids that still exist).
        deleted = rule.available_from is not None and rule.available_from > yesterday
        if deleted:
            rule.delete()
        else:
            rule.available_to = yesterday
            rule.save(update_fields=["available_to", "updated_at"])
        units = models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), rate_plan=plan, assigned_from__lte=today
        ).filter(Q(assigned_to__isnull=True) | Q(assigned_to__gte=today))
        on_plan = seams.account_ids_on_units(units.values("unit_id"))
        ended_on = yesterday
        enrolments = discount_models.DiscountEnrolment.objects.filter(
            tenant_id=_tenant_id(),
            discount_id=rule.discount_id,
            ended_on__isnull=True,
            account_id__in=on_plan,
        )
        numbers = seams.account_numbers(list(enrolments.values_list("account_id", flat=True)))
        reason = f"Removed from plan {plan.name}"
        count = 0
        for enrolment in enrolments:
            enrolment.ended_on = max(enrolment.enrolled_on, ended_on)
            enrolment.end_reason = reason
            enrolment.save(update_fields=["ended_on", "end_reason", "updated_at"])
            count += 1
        _audit(
            actor,
            "discount.removed_from_plan",
            "discount" if deleted else "plan_discount_rule",
            rule.discount_id if deleted else rule.id,
            after={
                "discount": rule.discount.code,
                "plan": plan.name,
                "available_to": None if deleted else str(yesterday),
                "enrolments_ended": count,
                "accounts": sorted(numbers.values()),
                "reason": (note or "").strip() or reason,
            },
        )
    return incoming


def _refuse_new_plan_grace(plan: models.RatePlan, rule: dict[str, Any] | None) -> None:
    """🔒 PO ruling 2026-10-06 11 (a) — grace is set on the late-fee CODE.

    OUR JUDGMENT, recorded with the ruling: a plan that already states a grace
    override keeps it (re-sending it, or clearing it, is allowed — no customer's
    late-fee date moves on deploy), but a plan may not state a NEW one or move
    the one it has. The plan form offers none and shows the code's grace.
    """
    stored = (
        models.PlanPenaltyRule.objects.filter(rate_plan=plan, tenant_id=_tenant_id())
        .values("grace_days", "grace_mode")
        .first()
        or {"grace_days": None, "grace_mode": None}
    )
    for field in ("grace_days", "grace_mode"):
        wanted = (rule or {}).get(field)
        if wanted is not None and wanted != stored[field]:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="rating.plans.grace_on_charge_code",
                field_errors=[
                    _field_error(
                        f"penalty_rule.{field}", errors.VAL_FORMAT, "rating.plans.grace_on_charge_code"
                    )
                ],
            )


def _apply_plan_children(
    plan: models.RatePlan,
    cleaned: dict[str, Any],
    actor: Any = None,
    version: Any = None,
    note: str | None = None,
) -> None:
    """Child sets are REPLACED when their key is present (the wizard always
    posts the full step), left untouched when absent.

    ⚠ **`BR-RAT-1066` — THE ROWS OF ONE VERSION.** A plan version owns its
    bindings, so every delete and every create below names the version it acts
    on: `version` when the caller is writing a particular one (a new dated
    version, a correction of a non-head version), else the plan's HEAD — which
    for every plan with one version is the only set it has ever had, so a
    caller that predates versions writes exactly what it always wrote.
    `all_versions` (never the default manager) because a write must not depend
    on which version today's date happens to read."""
    tenant_id = _tenant_id()
    vid = getattr(version, "pk", version) or plan_versioning.ensure_head(plan)
    if "services" in cleaned:
        models.PlanService.all_versions.filter(rate_plan=plan, plan_version_id=vid).delete()
        models.PlanRateSchedule.all_versions.filter(rate_plan=plan, plan_version_id=vid).delete()
        for row in cleaned["services"]:
            models.PlanService.objects.create(
                tenant_id=tenant_id,
                rate_plan=plan,
                plan_version_id=vid,
                service_id=row["service_id"],
                base_charge=row["base_charge"],
                currency=row["currency"],
                gl_account_id=row["gl_account_id"],
                outside_city_exempt=row["outside_city_exempt"],  # BR-RAT-102
            )
            if row["tariff"] is not None:
                models.PlanRateSchedule.objects.create(
                    tenant_id=tenant_id,
                    rate_plan=plan,
                    plan_version_id=vid,
                    service_id=row["service_id"],
                    tariff=row["tariff"],
                )
    if "charge_rules" in cleaned:
        # ONLY the Charges table's rows: a deposit code the plan names
        # (`role="deposit"`, `CR-167-BRC10` ruling 9) is the Deposits table's
        # and is replaced by `deposits` below, never by a Charges save.
        models.PlanChargeRule.all_versions.filter(
            rate_plan=plan, plan_version_id=vid, role="charge"
        ).delete()
        for row in cleaned["charge_rules"]:
            models.PlanChargeRule.objects.create(
                tenant_id=tenant_id,
                rate_plan=plan,
                plan_version_id=vid,
                charge=row["charge"],
                amount_override=row["amount_override"],
                recurrence=row["recurrence"],
                taxable=row["taxable"],
            )
    if "deposits" in cleaned:
        # `BR-RAT-023` as amended 2026-10-03 — the deposit codes the plan names.
        models.PlanChargeRule.all_versions.filter(
            rate_plan=plan, plan_version_id=vid, role="deposit"
        ).delete()
        for charge in cleaned["deposits"]:
            models.PlanChargeRule.objects.create(
                tenant_id=tenant_id,
                rate_plan=plan,
                plan_version_id=vid,
                charge=charge,
                role="deposit",
            )
    if "deposit_rules" in cleaned:
        models.PlanDepositRule.objects.filter(rate_plan=plan).delete()
        for row in cleaned["deposit_rules"]:
            models.PlanDepositRule.objects.create(
                tenant_id=tenant_id,
                rate_plan=plan,
                account_type_id=row["account_type_id"],
                amount=row["amount"],
                currency=row["currency"],
            )
    if "penalty_rule" in cleaned:
        _refuse_new_plan_grace(plan, cleaned["penalty_rule"])
        models.PlanPenaltyRule.objects.filter(rate_plan=plan).delete()
        rule = cleaned["penalty_rule"]
        if rule is not None and any(value is not None for value in rule.values()):
            models.PlanPenaltyRule.objects.create(tenant_id=tenant_id, rate_plan=plan, **rule)
    if "tax_rules" in cleaned:
        models.PlanTaxRule.all_versions.filter(rate_plan=plan, plan_version_id=vid).delete()
        for row in cleaned["tax_rules"]:
            models.PlanTaxRule.objects.create(
                tenant_id=tenant_id,
                rate_plan=plan,
                plan_version_id=vid,
                jurisdiction=row["jurisdiction"],
                # BR-RAT-113 — shape 2, the explicit attachment. Exactly one of
                # the two is non-None (validator + ck_plan_tax_rules_one_source).
                tax=row["tax"],
                rate_override=row["rate_override"],
            )
    if "discounts" in cleaned:
        # BR-RAT-110 — the set the wizard posts is what the plan OFFERS from
        # now on. ⚠ NOT replace-the-set like every sibling above: a dropped
        # binding is ENDED, never deleted (ruling 2 of 2026-10-03, closing
        # `OQ-322` — see `_close_dropped_discounts`), and a kept one is UPDATED
        # in place, because `(plan, discount)` is unique and the row carries the
        # window a past bill was priced through.
        #
        # ⚠ A DATED NEW VERSION (`version` not the head) is written plainly:
        # nothing is "ended" on it, because the DATE already stops a discount
        # the new version does not carry — every binding read is by service
        # date (`plan_versioning`), so a bill priced by the new version simply
        # does not see the old binding (ruling 2's *"stops it from the next
        # bill"*, reached by date rather than by an end date).
        if str(vid) == str(plan_versioning.ensure_head(plan)) and version is None:
            _close_dropped_discounts(plan, cleaned["discounts"], actor, note=note)
        else:
            discount_models.PlanDiscountRule.all_versions.filter(
                tenant_id=tenant_id, rate_plan=plan, plan_version_id=vid
            ).exclude(discount_id__in=[row["discount"].id for row in cleaned["discounts"]]).delete()
        existing = {
            rule.discount_id: rule
            for rule in discount_models.PlanDiscountRule.all_versions.filter(
                tenant_id=tenant_id, rate_plan=plan, plan_version_id=vid
            )
        }
        for row in cleaned["discounts"]:
            rule = existing.get(row["discount"].id)
            if rule is None:
                discount_models.PlanDiscountRule.objects.create(
                    tenant_id=tenant_id,
                    rate_plan=plan,
                    plan_version_id=vid,
                    discount=row["discount"],
                    available_from=row["available_from"],
                    available_to=row["available_to"],
                )
                continue
            # Re-offering a binding that had ENDED reopens it from its old
            # start: the enrolments ended with it (`_close_dropped_discounts`),
            # so the gap re-offers the discount to nobody.
            rule.available_from = row["available_from"]
            rule.available_to = row["available_to"]
            rule.save(update_fields=["available_from", "available_to", "updated_at"])
        # Ruling 3 — an Automatic discount newly on this plan enrols its
        # accounts now, and one taken off ends theirs.
        from apps.rating import discount_enrolment_job

        for discount in {row["discount"] for row in cleaned["discounts"]}:
            discount_enrolment_job.sync_discount(discount, actor=actor)


def _record_plan_version(
    actor: Any,
    plan: models.RatePlan,
    snapshot: dict[str, Any],
    *,
    reason: str | None,
) -> models.PlanVersion:
    """Write ONE row of the plan's filing record — BR-RAT-111.

    Called at exactly two moments, both of which already exist as facts:
    creation (v1) and a BR-RAT-037 version bump. It invents no lifecycle of its
    own — `rate_plans.version` stays the counter and this stays its history, so
    the two can never disagree about which version a plan is on.

    `get_or_create` rather than `create`: `uq_plan_versions_plan_version_no`
    makes a second row for one version impossible, and a re-entrant caller
    should be idempotent rather than raise an IntegrityError a screen cannot
    read. It is the same posture `attach_discount_to_plan` takes one file over.
    """
    version, created = models.PlanVersion.objects.get_or_create(
        tenant_id=_tenant_id(),
        rate_plan=plan,
        version_no=plan.version,
        corrects__isnull=True,
        defaults={
            "change_reason": reason or None,
            "submitted_by_id": _actor_user_id(actor),
            "snapshot": snapshot,
        },
    )
    if not created and version.status == plan_versioning.VERSION_DRAFT:
        # `BR-RAT-1066` — a draft plan has had its v1 row since creation (it owns
        # the draft's bindings); PUBLISH is when its content stops moving, so the
        # filing record is written now, on that same row.
        version.status = plan_versioning.VERSION_PUBLISHED
        version.snapshot = snapshot
        version.submitted_by_id = _actor_user_id(actor)
        version.save(update_fields=["status", "snapshot", "submitted_by"])
    return version


def _mirror_head(plan: models.RatePlan) -> None:
    """`BR-RAT-1066` — keep the head version's copy of the plan's four TERMS
    (and, for a plan with one priceable version, its window) equal to the
    plan's own columns. Called after every write that saves those columns on
    the head, so the two copies can never disagree (`plan_versioning`)."""
    head_id = plan_versioning.ensure_head(plan)
    fields = {name: getattr(plan, name) for name in plan_versioning.TERM_FIELDS}
    others = models.PlanVersion.objects.filter(rate_plan=plan).exclude(pk=head_id).exclude(
        status=plan_versioning.VERSION_HISTORY
    )
    if not others.exists():
        fields["effective_from"] = plan.effective_from
        fields["effective_to"] = plan.effective_to
    models.PlanVersion.objects.filter(pk=head_id).update(**fields)


def _version_terms(version: models.PlanVersion) -> dict[str, Any]:
    """A version's own four terms as JSON — part of what a correction compares,
    because a non-head version's terms live on its row, not on the plan."""
    return _json_safe({name: getattr(version, name) for name in plan_versioning.TERM_FIELDS})


def _has_other_versions(plan: models.RatePlan) -> bool:
    """True when the plan holds a version besides its head that can price or is
    a draft new version — the case a legacy in-place edit cannot express."""
    head_id = plan_versioning.ensure_head(plan)
    return (
        models.PlanVersion.objects.filter(rate_plan=plan, superseded_by__isnull=True)
        .exclude(pk=head_id)
        .exclude(status=plan_versioning.VERSION_HISTORY)
        .exists()
    )


def _plan_snapshot(plan_id: Any) -> dict[str, Any]:
    """before/after jsonb for the compliance log — content only (the version
    counter and the live account count are not plan CONTENT)."""
    snapshot = selectors.plan_detail(plan_id)
    # ⚠ `versions` JOINS THIS LIST AS OF BR-RAT-111 AND IT IS NOT OPTIONAL. The
    # snapshot is STORED IN a version row, so leaving the version list in it
    # would nest v1 inside v2 inside v3 — a blob that doubles every save, and a
    # diff between two versions that reports the history as the thing that
    # changed. Same reasoning as `version` and `accounts`: none of the three is
    # plan CONTENT.
    for key in ("version", "accounts", "versions"):
        snapshot.pop(key, None)
    # ⚠ AND `discounts[].terms` LEAVES TOO — CR-034 §7, 2026-08-26. The
    # discount's CONDITIONS (who qualifies, the proof, the caps, the floor,
    # the stacking) are the DISCOUNT VERSION's content and reach this payload
    # only because a plan happens to offer it. They change when a programme is
    # re-filed and this plan is untouched, so leaving them in would make the
    # NEXT plan edit diff twenty-two leaves that nobody changed and report
    # them as what changed about the plan — `_plan_snapshot_diff` shows eight
    # and counts the rest, so the real edit would be pushed off the row.
    # Same test as `versions` above: is it plan CONTENT? It is not.
    for rule in snapshot.get("discounts") or []:
        rule.pop("terms", None)
    return _json_safe(snapshot)


@require_role(SYSTEM_ADMIN)
def create_plan(actor: Any, payload: Any) -> dict[str, Any]:
    """S10 commit — one atomic write of the whole bundle (US-RAT-002 §6).
    Always lands as a DRAFT; publishing is its own explicit action
    (BR-RAT-030), so nothing is billable until a human says so."""
    payload = _require_dict(payload)
    cleaned = _validate_plan(payload, partial=False)
    with transaction.atomic():
        plan = models.RatePlan.objects.create(
            tenant_id=_tenant_id(),
            code=cleaned["code"],
            name=cleaned["name"],
            description=cleaned.get("description"),
            # DEF-RAT-5768 — a plan naming nothing is for EVERY class, which
            # is the PO's stated default, so the absent key stores `[]`.
            account_type_ids=cleaned.get("account_type_ids", []),
            account_subtype_id=cleaned.get("account_subtype_id"),
            status=PLAN_DRAFT,
            version=1,
            minimum_bill_amount=cleaned.get("minimum_bill_amount"),
            outside_city_factor=cleaned.get("outside_city_factor"),  # BR-RAT-102
            budget_billing=cleaned.get("budget_billing", False),
            eligibility=cleaned.get("eligibility"),  # advisory (BR-RAT-043)
            effective_from=cleaned.get("effective_from"),
            effective_to=cleaned.get("effective_to"),
            # BR-RAT-1011 (`CR-078`) — the plan names the charge code its late
            # fee comes from. A payload that says nothing gets the tenant's
            # seeded code; a payload that says `null` gets NULL and charges
            # $0.00, which is the PO's ruled case and must stay expressible.
            # `"late_fee_charge" in cleaned` is what tells the two apart.
            late_fee_charge=(
                cleaned["late_fee_charge"]
                if "late_fee_charge" in cleaned
                else default_late_fee_charge()
            ),
        )
        # `BR-RAT-1066` — v1 exists from creation as a DRAFT row that OWNS the
        # draft's bindings; it becomes the filing record at publish (below).
        plan_versioning.ensure_head(plan)
        _apply_plan_children(plan, cleaned, actor)
        # `eligibility` is plan content now, so the snapshot carries it into the
        # audit before/after by itself (BR-RAT-043 advisory-WITH-AUDIT).
        after = _plan_snapshot(plan.id)
        # ⚠ AMENDED 2026-10-03 (`BR-RAT-1066`): the v1 ROW now exists from here,
        # status `draft`, because a version owns its bindings and a draft's
        # bindings need an owner. What the paragraph below protects still holds:
        # its SNAPSHOT is written at publish, when its content stops moving.
        # ⚠ **NO VERSION ROW IS WRITTEN HERE, AND THE ABSENCE IS THE RULE —
        # BR-RAT-111.** A plan lands as a DRAFT (BR-RAT-030) and a draft edits
        # freely: `update_plan` neither bumps the counter nor logs a reason for
        # one. So a `v1` row written at creation would go stale on the first
        # draft edit and keep claiming to be what v1 holds, which is worse than
        # having no row — a filing record that is confidently wrong is the thing
        # `version_label` was stored to prevent one table over. v1 is recorded
        # at PUBLISH, which is the moment its content stops moving.
        _audit(actor, "plan.created", "rate_plan", plan.id, after=after)
    return selectors.plan_detail(plan.id)


#: `BR-RAT-1067` — the six fields a live plan may change on the SAME version
#: (PO ruling 1, 2026-10-03, *"Name and details (same version)"*). The snapshot
#: keys they appear under; `account_type_id` is the derived bridge of the list.
PLAN_INFO_SNAPSHOT_KEYS = frozenset(
    {"name", "code", "description", "account_type_ids", "account_type_id", "eligibility"}
)


def _pricing_keys_changed(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """The snapshot keys that changed and are NOT name-and-details, in order."""
    return [
        key
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key) and key not in PLAN_INFO_SNAPSHOT_KEYS
    ]


def _needs_new_version(field: str) -> errors.ValidationError:
    return errors.ValidationError(
        errors.VAL_FORMAT,
        message_key="rating.plans.field_needs_new_version",
        params={"field": field, "br_ref": "BR-RAT-1067"},
        field_errors=[
            _field_error(field, errors.VAL_FORMAT, "rating.plans.field_needs_new_version", what=field)
        ],
    )


def _replace_head_in_place(plan: models.RatePlan, new_head: models.PlanVersion) -> None:
    """The legacy in-place version bump (`BR-RAT-037` before dates), expressed
    in versions: the new number takes the old head's window and terms, the old
    head becomes `history`, and the bindings move to the new head — so the plan
    prices every unbilled day exactly as the in-place edit always did."""
    old_head = plan_versioning.ensure_head(plan)
    if str(old_head) == str(new_head.pk):
        return
    old = models.PlanVersion.objects.get(pk=old_head)
    models.PlanVersion.objects.filter(pk=old_head).update(status=plan_versioning.VERSION_HISTORY)
    models.PlanVersion.objects.filter(pk=new_head.pk).update(
        status=plan_versioning.VERSION_PUBLISHED,
        effective_from=old.effective_from,
        effective_to=old.effective_to,
        **{name: getattr(plan, name) for name in plan_versioning.TERM_FIELDS},
    )
    for model in (
        models.PlanService,
        models.PlanRateSchedule,
        models.PlanChargeRule,
        models.PlanTaxRule,
        discount_models.PlanDiscountRule,
    ):
        model.all_versions.filter(rate_plan=plan, plan_version_id=old_head).update(
            plan_version_id=new_head.pk
        )
    models.RatePlan.objects.filter(pk=plan.pk).update(head_version_id=new_head.pk)
    plan.head_version_id = new_head.pk


@require_role(SYSTEM_ADMIN)
def update_plan(actor: Any, plan_id: Any, payload: Any) -> dict[str, Any]:
    """BR-RAT-037: a published plan is never edited in place — every content
    change bumps `plans.version` and appends a rate_change_log row with a
    REQUIRED reason. Drafts (never billed) edit freely."""
    payload = _require_dict(payload)
    with transaction.atomic():
        plan = selectors.plan_or_404(plan_id)
        if plan.status == PLAN_ARCHIVED:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-030",
                message_key="rating.plans.archived_not_editable",
            )
        reason = str(payload.get("reason") or "").strip()
        # ⚠ AMENDED 2026-10-03 (`BR-RAT-1067`, PO ruling 1 of the plans
        # redesign): the reason is no longer demanded BEFORE the write. A live
        # plan's name and details save on the SAME version with no reason, so
        # whether one is needed depends on WHAT CHANGED, which is only known
        # after the diff below — and the refusal there rolls the whole write
        # back (the atomic block), so nothing is written either way.
        cleaned = _validate_plan(payload, partial=True, plan=plan)
        # ── BR-RAT-890, THE OTHER HALF · A PUBLISHED PLAN KEEPS ITS DATE ─────
        # ⚠ **WITHOUT THIS THE PUBLISH GATE IS DECORATIVE.** `publish_plan`
        # refuses an undated plan, and this path could then set the column back
        # to NULL on the SAME plan one request later — recreating exactly the
        # state the PO ruled out of existence, on a plan that is already
        # billing customers. The refusal is a FIELD error rather than a
        # BizError so the wizard puts it on the control that caused it.
        # Clearing the date on a DRAFT stays lawful: a draft prices nothing,
        # and BR-RAT-031's save-and-come-back is what a draft is for.
        if (
            plan.status == PLAN_PUBLISHED
            and "effective_from" in cleaned
            and cleaned["effective_from"] is None
        ):
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="rating.plans.effective_from_required",
                params={"br_ref": "BR-RAT-890"},
                field_errors=[
                    _field_error(
                        "effective_from",
                        errors.VAL_REQUIRED,
                        "rating.plans.effective_from_required",
                    )
                ],
            )
        before = _plan_snapshot(plan.id)

        fields: list[str] = []
        for field in (
            "code",
            "name",
            "description",
            "account_type_ids",  # DEF-RAT-5768 — the LIST
            "account_subtype_id",
            "minimum_bill_amount",
            "outside_city_factor",  # BR-RAT-102 / DEF-515
            "budget_billing",
            "eligibility",
            "effective_from",
            "effective_to",
            "late_fee_charge",  # BR-RAT-1011 — settable AND clearable
        ):
            if field in cleaned:
                setattr(plan, field, cleaned[field])
                fields.append(field)
        _apply_plan_children(plan, cleaned, actor, note=reason or None)
        if fields:
            # Persist BEFORE snapshotting: `_plan_snapshot` re-reads the row, so
            # an unsaved SCALAR edit (description, eligibility, …) was invisible
            # to the change detector below and silently skipped its BR-RAT-037
            # version bump + log row. Child-set edits were unaffected.
            plan.save(update_fields=[*dict.fromkeys(fields), "updated_at"])
        after = _plan_snapshot(plan.id)

        changed = before != after
        if fields:
            _mirror_head(plan)
        if changed and plan.status == PLAN_PUBLISHED:
            moved = _pricing_keys_changed(before, after)
            if not moved:
                # ── `BR-RAT-1067` · NAME AND DETAILS, SAME VERSION ────────────
                # PO ruling 1 (2026-10-03): *"Name and details (same version)"*.
                # Six fields that price nothing; the version does not move and
                # Audit gets one before → after line.
                _audit(
                    actor,
                    "plan.details_updated",
                    "rate_plan",
                    plan.id,
                    before=before,
                    after={**after, "version": plan.version},
                )
                return selectors.plan_detail(plan.id)
            if not reason:
                # The contract's refusal (`CR-167-BRC10` §7.3): a price is changed
                # from a date (`POST …/versions`) or corrected
                # (`POST …/corrections`), never by a bare PATCH.
                raise _needs_new_version(moved[0])
            if _has_other_versions(plan):
                # A legacy in-place edit (the 8-step form, until task 8 retires
                # it) re-states the ONE version a plan had; it cannot say which
                # of two dated versions it meant.
                raise _needs_new_version(moved[0])
            plan.version += 1  # BR-RAT-037 — assignment snapshots stay untouched
            plan.save(update_fields=["version", "updated_at"])
        if changed:
            if plan.status == PLAN_PUBLISHED:
                # BR-RAT-111 — the filing record, written in the same
                # transaction as the counter bump above and from the SAME
                # `after` blob `rate_change_log` gets, so the two can never
                # describe different content for one version.
                _replace_head_in_place(plan, _record_plan_version(actor, plan, after, reason=reason))
                models.RateChangeLog.objects.create(
                    tenant_id=_tenant_id(),
                    entity_type="plan",
                    entity_id=plan.id,
                    before=before,
                    after=after,
                    reason=reason,
                    actor_id=_actor_user_id(actor),
                )
                _audit(
                    actor,
                    "plan.version_created",
                    "rate_plan",
                    plan.id,
                    before=before,
                    after={**after, "version": plan.version, "reason": reason},
                )
            else:
                _audit(actor, "plan.updated", "rate_plan", plan.id, before=before, after=after)
    return selectors.plan_detail(plan.id)


@require_role(SYSTEM_ADMIN)
def correct_plan_version(actor: Any, plan_id: Any, payload: Any) -> dict[str, Any]:
    """`BR-RAT-1016` VERB 2 FOR THE PLAN — the last of the five priced objects,
    and the one that needed a schema ruling first (`OQ-RAT-12409`, `DEF-RAT-5710`).

    ── THE RULING THIS IMPLEMENTS, VERBATIM ──────────────────────────────────
    **PO, 2026-09-18:** *"The plan correction — A, B or C - option A pls"*, and
    the correction of premise that makes it make sense, the same day: *"plan
    will not do any edits to Rates - all Rates, chargecode, discounts and taxes
    - this is where we make money changes. plan only binds it"* — which is
    `BR-RAT-088` restated.

    ── A CORRECTION IS NOT A CHANGE, AND HERE THE DIFFERENCE IS THE COUNTER ───
    For a tax and for a rate-schedule version the property that makes a
    correction a correction is that the effective WINDOW is copied from the row
    being corrected and never read from the payload (`correct_tax`,
    `correct_rate_schedule_version`). **A plan version has no window** —
    `OQ-324` records that omission as deliberate (⚠ CLOSED (B) 2026-10-03, BR-RAT-1066) — so the equivalent invariant
    is the COUNTER:

      **`version_no` IS COPIED FROM THE ROW BEING CORRECTED AND IS NEVER READ
      FROM THE PAYLOAD, AND `rate_plans.version` DOES NOT MOVE.**

    That single property is what makes this function a correction rather than a
    version bump wearing one's clothes, so a `version` or `version_no` key in
    the payload is refused BY NAME rather than ignored in silence — the posture
    `correct_rate_schedule_version` takes for a date, and for its stated reason:
    a caller that sent one believed it would be used.

    ── WHY THE COUNTER IS THE THING WORTH PROTECTING ON A PLAN ───────────────
    `unit_plan_assignments.plan_version` SNAPSHOTS the counter at assignment
    (`BR-CUS-013`) and those rows outlive the plan. **Measured on the seeded
    estate before this was written** (hard-won law 1 — a docstring claiming a
    figure is not the figure): `Sample — Residential` (`SCW-RES`) is on v1 with
    **75 units, every one of them recorded against `plan_version = 1`**. A clerk
    who points the water service at `Sample — Commercial water (flat)` by
    mistake and puts it back an hour later produced **three versions** —
    reproduced, not reasoned about — two of which are a slip and its undo, and
    any unit assigned in that hour is stamped with a version number that exists
    only because of a mis-click. After this verb the same pair of acts leaves
    ONE correction row at `version_no = 1` and `rate_plans.version` on 1.

    ── WHAT HAPPENS TO THE ROW BEING CORRECTED ───────────────────────────────
    **It is never rewritten and never deleted.** It keeps its snapshot, its
    `change_reason`, its submitter and its timestamp for ever; `superseded_by`
    is set on it and nothing else is. That one column is the single exception
    this shape takes to `BR-RAT-111`'s append-only posture, it is the exception
    `taxes`, `tariff_versions` and `discount_versions` already take, and it is
    what lets a reader tell the current statement of a version from the one it
    replaced without deleting either.

    ── ⚠ WHAT THIS DELIBERATELY DOES NOT DO, AND IT IS THE MONEY HALF ────────
    **It does not touch one bill already issued** (hard rule 4). A correction
    changes what prices FUTURE bills; a bill that has been issued is reproduced
    from what it stored (`BR-RAT-007`, `BR-RAT-017`). So the answer carries
    `issued_bills_unchanged`, because an operator who has just fixed a plan will
    reasonably believe the money is fixed, and the screen says so where they can
    read it.

    ⚠ **AND IT CARRIES NO COUNT, WHICH IS A DIVERGENCE FROM `correct_tax` AND
    `correct_rate_schedule_version` AND IS DELIBERATE.** Those two can count
    precisely: an invoice line stamps `tariff_version_id` (`DEF-276`), so
    `version_issued_bill_count` counts INVOICES for one version exactly. **There
    is no equivalent for a plan.** `BR-BIL-030` locks what a bill priced into the
    bill itself, so nothing on `invoices` or `invoice_lines` points back at a
    plan at all; the only link is `plan → plan_rate_schedules → tariff_versions
    → invoice_lines`, which `billing.selectors.plan_invoice_count` walks — and it
    counts **LINES, not bills**, and **over-counts when two plans share a
    tariff** (its own docstring says so, and `OQ-185` records it). Measured on
    the seeded estate rather than reasoned about: it answers **640** for
    `SCW-RES` where that tenant holds **135 issued invoices**. Printing 640
    beside the word *bills* would overstate the blast radius roughly fivefold on
    a money consequence, which is worse than saying nothing. So the screen states
    the CONSEQUENCE in words and states no figure, and a precise plan-level count
    stays unbuilt rather than approximated.

    ── WHAT IT REFUSES, AND WHY EACH ONE IS A REFUSAL RATHER THAN A SILENCE ──
    * **A DRAFT plan** — a draft has priced nothing, so there is nothing to
      preserve and nothing to explain. `PATCH /plans/{id}` edits it in place,
      and the refusal NAMES that road rather than ending it (`DEF-384`'s shape).
    * **An ARCHIVED plan** — `update_plan` refuses it and so does this; a
      correction is not a way back in.
    * **A version row that is already superseded** — correcting a correction
      would leave two rows claiming to restate one version with nothing saying
      which is current. Refused by name, exactly as `correct_tax` does.
    * **A plan with no filing record at all** — a plan published before
      `BR-RAT-111` has no `plan_versions` row, so there is no recorded statement
      to correct. Refused rather than invented: minting one here would file a
      snapshot for a version nobody recorded.
    * **A correction that changes nothing** — it would supersede a live filing
      for no content, which is a break in the chain with nothing in it.

    🔒 HUMAN-REVIEW-PENDING — the migration behind it changes a unique
    constraint on a filing table (migration ordering is a CLAUDE.md sensitive
    path). Row in `12-governance/09-human-review-ledger.md`.
    """
    payload = _require_dict(payload)
    reason = str(payload.get("reason") or "").strip()
    fe: list[dict[str, Any]] = []
    if len(reason) < MIN_CORRECTION_REASON:
        fe.append(_field_error("reason", errors.VAL_REQUIRED, "rating.plans.correction_reason"))
    # ⚠ THE COUNTER IS NOT AN INPUT. Refused BY NAME rather than overridden in
    # silence: this is the one property that makes the call a correction, and a
    # caller that sent a version number believed it would be honoured.
    # ⚠ AMENDED 2026-10-03 (`CR-167-BRC10` §7.3, `BR-RAT-1066`): `version` now
    # NAMES WHICH VERSION is corrected (a plan has dated versions), and it must
    # be a number the plan already has — a number that is not one is still
    # refused BY NAME, because that caller believed it would SET the number.
    # `version_no` is never accepted. The window, like the number, is copied
    # from the corrected row (`BR-RAT-1016`) — `effective_from`/`effective_to`
    # are refused here too.
    target_no: int | None = None
    if "version" in payload:
        try:
            target_no = int(payload["version"])
        except (TypeError, ValueError):
            target_no = -1
    numbered = sorted(
        (set(payload) & {"version_no", "effective_from", "effective_to"})
        | ({"version"} if target_no is not None and target_no < 1 else set())
    )
    if numbered:
        fe.append(
            _field_error(
                numbered[0],
                errors.VAL_FORMAT,
                "rating.plans.correction_keeps_the_version",
            )
        )
    # The two counter keys are named above, so they are taken OUT before the
    # generic unknown-field sweep — otherwise one mistake produces two errors
    # and the useful one is the second. Every other unknown key still gets the
    # ordinary refusal.
    _reject_unknown(
        {key: value for key, value in payload.items() if key not in {"version", "version_no"}},
        PLAN_FIELDS + ("reason",),
        fe,
    )
    _refuse(fe)

    with transaction.atomic():
        plan = selectors.plan_or_404(plan_id)
        if plan.status == PLAN_ARCHIVED:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-030",
                message_key="rating.plans.archived_not_editable",
            )
        if plan.status != PLAN_PUBLISHED:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1016",
                message_key="rating.plans.correct_draft",
                params={"name": plan.name},
            )
        wanted = target_no if target_no is not None else plan.version
        original = (
            models.PlanVersion.objects.filter(
                tenant_id=_tenant_id(), rate_plan=plan, version_no=wanted, corrects__isnull=True
            )
            .exclude(status=plan_versioning.VERSION_HISTORY)
            .order_by("-created_at")
            .first()
        )
        if original is None and target_no is not None:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="rating.plans.correction_keeps_the_version",
                params={"br_ref": "BR-RAT-1016"},
                field_errors=[
                    _field_error(
                        "version", errors.VAL_FORMAT, "rating.plans.correction_keeps_the_version"
                    )
                ],
            )
        if original is None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-111",
                message_key="rating.plans.no_version_to_correct",
                params={"name": plan.name, "version": plan.version},
            )
        if original.superseded_by_id is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1016",
                message_key="rating.plans.already_corrected",
                params={"name": plan.name, "version": original.version_no},
            )
        cleaned = _validate_plan(
            {key: value for key, value in payload.items() if key != "version"}, partial=True, plan=plan
        )
        # ── `BR-RAT-1066` · THE CORRECTED VERSION'S OWN ROWS ───────────────────
        # Every read below is taken ON A DAY THE CORRECTED VERSION PRICES (its
        # start, or the plan's head for a dateless one), so the snapshot is that
        # version's content and not whichever version today happens to read.
        was_head = str(original.pk) == str(plan_versioning.ensure_head(plan))
        on_day = original.effective_from
        with plan_versioning.pricing_day(on_day):
            before = {**_plan_snapshot(plan.id), "version_terms": _version_terms(original)}
        # The correction row exists FIRST and takes over the corrected row's
        # bindings, window and terms; the edits are then applied to IT. The
        # overlap lock (`rating/0064`) is DEFERRED, so the moment both rows are
        # `published` with one window inside this transaction is lawful — at
        # COMMIT the original is superseded.
        correction = models.PlanVersion.objects.create(
            tenant_id=_tenant_id(),
            rate_plan=plan,
            # ⚠ **THE COUNTER, COPIED FROM THE ROW BEING CORRECTED.** Not
            # `plan.version` — `rate_plans.version` is NOT touched anywhere in
            # this function, which is the half `DEF-RAT-5710` was filed for.
            version_no=original.version_no,
            # `BR-RAT-037`'s authored note belongs to a CHANGE; the corrected
            # row's own filing note travels with the restatement.
            change_reason=original.change_reason,
            submitted_by_id=_actor_user_id(actor),
            snapshot={},
            corrects=original,
            correction_reason=reason,
            corrected_by_id=_actor_user_id(actor),
            status=original.status,
            effective_from=original.effective_from,
            effective_to=original.effective_to,
            **{name: getattr(original, name) for name in plan_versioning.TERM_FIELDS},
        )
        for model in (
            models.PlanService,
            models.PlanRateSchedule,
            models.PlanChargeRule,
            models.PlanTaxRule,
            discount_models.PlanDiscountRule,
        ):
            model.all_versions.filter(rate_plan=plan, plan_version_id=original.pk).update(
                plan_version_id=correction.pk
            )
        original.superseded_by = correction
        original.save(update_fields=["superseded_by"])
        if was_head:
            models.RatePlan.objects.filter(pk=plan.pk).update(head_version_id=correction.pk)
            plan.head_version_id = correction.pk
        fields: list[str] = []
        for field in ("code", "name", "description", "account_type_ids", "account_subtype_id", "eligibility"):
            if field in cleaned:
                setattr(plan, field, cleaned[field])
                fields.append(field)
        term_updates: dict[str, Any] = {}
        for field in ("minimum_bill_amount", "outside_city_factor", "budget_billing", "late_fee_charge"):
            if field in cleaned:
                column = "late_fee_charge_id" if field == "late_fee_charge" else field
                value = cleaned[field]
                term_updates[column] = getattr(value, "pk", value)
                if was_head:
                    setattr(plan, field, value)
                    fields.append(field)
        if term_updates:
            models.PlanVersion.objects.filter(pk=correction.pk).update(**term_updates)
        _apply_plan_children(plan, cleaned, actor, version=correction)
        if fields:
            # Persist BEFORE snapshotting — `_plan_snapshot` re-reads the row,
            # so an unsaved scalar edit would be invisible to the comparison
            # below. `update_plan` records why this ordering matters.
            plan.save(update_fields=[*dict.fromkeys(fields), "updated_at"])
        with plan_versioning.pricing_day(on_day):
            after = {
                **_plan_snapshot(plan.id),
                "version_terms": _version_terms(models.PlanVersion.objects.get(pk=correction.pk)),
            }
        if before == after:
            # A correction that corrects nothing would supersede a live filing
            # for no content — a break in the chain with nothing in it, which is
            # the opposite of what `BR-RAT-104` protects. Raised INSIDE the
            # atomic block so every write above is rolled back with it.
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="rating.plans.correction_empty",
                params={"br_ref": "BR-RAT-1016"},
                field_errors=[
                    _field_error("reason", errors.VAL_REQUIRED, "rating.plans.correction_empty")
                ],
            )
        models.PlanVersion.objects.filter(pk=correction.pk).update(snapshot=after)
        # The compliance trail, the same row `correct_rate_schedule_version`
        # writes for a schedule. `entity_type="plan"` is already one of the four
        # `RateChangeLog` declares and one of S9's History filters, and this is
        # the table `OQ-RAT-12409`'s own analysis names as the place the wrong
        # binding survives in full, before and after, permanently.
        models.RateChangeLog.objects.create(
            tenant_id=_tenant_id(),
            entity_type="plan",
            entity_id=plan.id,
            before=before,
            after=after,
            reason=reason,
            actor_id=_actor_user_id(actor),
        )
        _audit(
            actor,
            "plan.version_corrected",
            "rate_plan",
            plan.id,
            before=before,
            after={
                **after,
                "version": plan.version,
                "version_no": correction.version_no,
                "reason": reason,
            },
        )
    result = selectors.plan_detail(plan.id)
    # ⚠ SAID OUT LOUD IN THE ANSWER, not only in this docstring —
    # `correct_tax`'s own precedent, and for the reason it records: an operator
    # who has just fixed a plan will reasonably believe the money is fixed.
    result["issued_bills_unchanged"] = True
    return result


def _plan_discount_rules_payload(plan: Any) -> list[dict[str, Any]]:
    """The discounts the plan's HEAD offers today or later, restated in the
    write payload's own shape — `_plan_tax_rules_payload`'s reason: the
    discount page's add and remove go through `update_plan` and inherit every
    rule that guards plan content (BR-RAT-037's reason and version bump, the
    filing record, ruling 2's dated removal) instead of a second, weaker write
    path. A binding already ENDED is history and is not restated
    (`_close_dropped_discounts` leaves it alone)."""
    today = seams.tenant_today()
    head = plan_versioning.ensure_head(plan)
    rows: list[dict[str, Any]] = []
    for rule in (
        discount_models.PlanDiscountRule.all_versions.filter(
            tenant_id=_tenant_id(), rate_plan=plan, plan_version_id=head
        )
        .filter(Q(available_to__isnull=True) | Q(available_to__gte=today))
        .order_by("created_at", "id")
    ):
        rows.append(
            {
                "discount": str(rule.discount_id),
                "available_from": rule.available_from.isoformat() if rule.available_from else None,
                "available_to": rule.available_to.isoformat() if rule.available_to else None,
            }
        )
    return rows


def _plan_link_reason(payload: dict[str, Any]) -> str:
    """The reason the discount page asks for — required on BOTH acts, whatever
    the plan's status: adding or removing a discount changes what a customer
    pays, and its Audit row is the only place the why is written (`DEF-478`,
    our judgment, decision log 2026-10-03)."""
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="rating.reason_required",
            params={"br_ref": "BR-RAT-037"},
            field_errors=[_field_error("reason", errors.VAL_REQUIRED, "rating.reason_required")],
        )
    return reason


def _plan_link_refusal(exc: errors.ValidationError) -> errors.ValidationError:
    """`update_plan` names a box of the PLAN's form (`discounts[3].discount`,
    `discounts`). On the discount page the box is *Plan*, so the refusal is
    drawn there — the sentence is unchanged, only where it is drawn."""
    for entry in getattr(exc, "field_errors", None) or []:
        if str(entry.get("field") or "").startswith("discounts"):
            entry["field"] = "plan"
    return exc


@require_role(SYSTEM_ADMIN)
def add_discount_to_plan(actor: Any, discount_id: Any, payload: Any) -> dict[str, Any]:
    """`DEF-478` — *+ Add to a plan* on the discount's own page (image 21):
    `POST /discounts/{id}/plans {plan, reason}`.

    The plan OFFERS it from the utility's TODAY (`available_from`), so a bill
    whose service date is today or later can carry it and no bill already
    priced moves (BR-RAT-007) — the mirror of ruling 2's removal, which stops it
    from the next bill. It grants it to NOBODY (BR-RAT-069): an Automatic
    discount enrols its qualifying accounts through `update_plan`'s own sync
    (ruling 3); every other kind waits for an enrolment.

    **Worked:** SENIOR added to *Residential Standard* on 10/15/2026 with the
    reason *"Seniors on the main tariff"* → one binding from 10/15/2026, the
    plan's next version carries the reason, and the discount's Audit reads
    *Added to plan · Residential Standard · Seniors on the main tariff*.
    """
    payload = _require_dict(payload)
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, ("plan", "reason"), fe)
    if not str(payload.get("plan") or "").strip():
        fe.append(_field_error("plan", errors.VAL_REQUIRED, "rating.required"))
    _refuse(fe)
    reason = _plan_link_reason(payload)
    discount = discount_models.Discount.objects.filter(tenant_id=_tenant_id(), pk=discount_id).first()
    if discount is None:
        raise errors.NotFoundError()
    plan = selectors.plan_or_404(payload["plan"])
    rules = _plan_discount_rules_payload(plan)
    if any(row["discount"] == str(discount.id) for row in rules):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="rating.discounts.already_on_plan",
            field_errors=[
                _field_error("plan", errors.VAL_FORMAT, "rating.discounts.already_on_plan")
            ],
        )
    today = seams.tenant_today()
    rules.append({"discount": str(discount.id), "available_from": today.isoformat(), "available_to": None})
    with transaction.atomic():
        try:
            result = update_plan(actor, plan.id, {"discounts": rules, "reason": reason})
        except errors.ValidationError as exc:
            raise _plan_link_refusal(exc) from None
        # The discount's half of the audit (`update_plan` audits the PLAN): the
        # row the discount's Audit tab reads, naming the plan by name through
        # `discount_reads._audit_view` (B14 rule 31). On the DISCOUNT entity, so
        # a binding later deleted (`DEF-RAT-9512`) cannot take it with it.
        _audit(
            actor,
            "discount.made_available_on_plan",
            "discount",
            discount.id,
            after={
                "rate_plan": str(plan.id),
                "discount": discount.code,
                "available_from": today.isoformat(),
                "reason": reason,
            },
        )
    return result


@require_role(SYSTEM_ADMIN)
def remove_discount_from_plan(
    actor: Any, discount_id: Any, plan_id: Any, payload: Any = None
) -> dict[str, Any]:
    """`DEF-478` — × on a row of the discount's Plans tab:
    `DELETE /discounts/{id}/plans/{plan_id} {reason}`.

    ⚖️ RULING 2 (PO 2026-10-03), through the ONE path that already obeys it:
    the plan is restated without this discount and `update_plan` →
    `_close_dropped_discounts` ENDS the binding the day before today and ends
    every open enrolment of an account on this plan the same day, with
    *"Removed from plan <name>"* — so the next bill has no discount and a bill
    whose service date is before the removal keeps it. The person's reason is
    the discount Audit's reason.

    **Worked:** SENIOR removed from *Residential Standard* on 10/15/2026 →
    binding ends 10/14/2026; Ruth's enrolment ends 10/14/2026; a bill to 10/14
    keeps −$9.00 and the next has none (walk step 5).
    """
    payload = _require_dict(payload) if payload else {}
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, ("reason",), fe)
    _refuse(fe)
    reason = _plan_link_reason(payload)
    discount = discount_models.Discount.objects.filter(tenant_id=_tenant_id(), pk=discount_id).first()
    if discount is None:
        raise errors.NotFoundError()
    plan = selectors.plan_or_404(plan_id)
    rules = _plan_discount_rules_payload(plan)
    kept = [row for row in rules if row["discount"] != str(discount.id)]
    if len(kept) == len(rules):
        raise errors.NotFoundError()  # this plan does not offer it (any more)
    try:
        return update_plan(actor, plan.id, {"discounts": kept, "reason": reason})
    except errors.ValidationError as exc:
        raise _plan_link_refusal(exc) from None


def _plan_tax_rules_payload(plan: Any) -> list[dict[str, str]]:
    """The plan's CURRENT tax set, restated in the write payload's own shape.

    Read for the row-action services below, so `attach_tax_to_plan` /
    `detach_tax_from_plan` can go through `update_plan`'s replace-the-set and
    inherit every rule that guards plan content — BR-RAT-037's reason + version
    bump on a published plan, the BR-RAT-111 filing record, the compliance log
    and the audit row — instead of growing a second, weaker write path that
    could drift from the first.
    """
    rows: list[dict[str, str]] = []
    for rule in models.PlanTaxRule.objects.filter(rate_plan=plan).order_by("created_at"):
        if rule.tax_id is not None:
            rows.append({"tax": str(rule.tax_id)})
        else:
            rows.append({"jurisdiction": str(rule.jurisdiction_id)})
    return rows


@require_role(SYSTEM_ADMIN)
def attach_tax_to_plan(actor: Any, plan_id: Any, payload: Any) -> dict[str, Any]:
    """BR-RAT-113 (PO 2026-08-21, CR-021): *"staff need to pick up and attach
    taxes and fees on the plan."* PLN-03 step 5's `+ Attach` row action.

    Attaching is ADDITIVE — it puts one catalogue tax/fee on this plan BEYOND
    what its bound jurisdictions bring. It cannot change a rate (BR-RAT-094:
    no `rate_override` travels) and it cannot remove anything. A tax the
    plan's jurisdictions already bring may still be attached; pricing
    de-duplicates (`selectors.plan_tax_rules`), so the bill is unchanged.

    Delegates to `update_plan` with the current set plus the new row, so a
    PUBLISHED plan takes the same `reason` requirement and version bump any
    other content change takes (BR-RAT-037) — an attached tax changes money.
    """
    payload = _require_dict(payload)
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, ("tax", "reason"), fe)
    _refuse(fe)
    plan = selectors.plan_or_404(plan_id)
    rules = _plan_tax_rules_payload(plan)
    # Validated (existence, tenant, duplicates) inside `update_plan`'s
    # `_validate_plan_tax_rules` — one validator, not two.
    rules.append({"tax": payload.get("tax")})
    body: dict[str, Any] = {"tax_rules": rules}
    reason = str(payload.get("reason") or "").strip()
    if reason:
        body["reason"] = reason
    result = update_plan(actor, plan.id, body)
    _audit_tax_plan_link(actor, "tax.attached_to_plan", payload.get("tax"), plan, reason)
    return result


def _audit_tax_plan_link(
    actor: Any, action: str, tax_id: Any, plan: Any, reason: str | None
) -> None:
    """CR-165 §9 / web walk 6.2 — attaching a tax to a plan, and detaching it,
    appear on the TAX's own Audit tab. `update_plan` audits the PLAN
    (`rate_plan` entity); this writes the tax's half, naming the plan by name
    (B14 rule 31 — never its id)."""
    try:
        tax = models.Tax.objects.filter(tenant_id=_tenant_id(), pk=tax_id).first()
    except (ValueError, TypeError):
        return
    if tax is None:
        return
    _audit(
        actor,
        action,
        "tax",
        tax.id,
        after={"plan": plan.name, "version": tax.version_no, "reason": reason or None},
    )


@require_role(SYSTEM_ADMIN)
def detach_tax_from_plan(
    actor: Any, plan_id: Any, tax_id: Any, payload: Any = None
) -> dict[str, Any]:
    """Remove ONE explicit attachment — and ONLY an explicit attachment.

    Detaching a row `attach_tax_to_plan` created reverses nothing that was
    ruled: the tax leaves the plan only if no bound jurisdiction also brings
    it, and if one does, the bill is unchanged (the derived path still prices
    it — BR-RAT-113: *"a jurisdiction-mandated tax stays on the bill whether
    or not anyone ticked it"*).

    A detach attempt on a jurisdiction-MANDATED tax — one this plan carries
    through a jurisdiction binding, with no attachment row to remove — is
    ALLOWED since `BR-RAT-115` (PO 2026-08-22, verbatim: *"we ask madetory
    atleast 1 tax shuld be there"*), which superseded-refined the BR-RAT-094
    refusal that stood here. **The floor is the rule:** a detach that would
    leave the plan carrying ZERO taxes refuses by name, whatever kind of tax
    it is.

    **The mechanism for a mandated tax, recorded as a judgment (decision log
    2026-08-22):** there is no row to delete — the tax is DERIVED from the
    authority's binding — so the binding is REPLACED by explicit attachments
    of the authority's other in-force taxes, and only the named tax leaves.
    The cost is stated: the plan stops following that authority wholesale, so
    a tax the authority mints later will not auto-arrive — which is what
    detaching a mandated tax MEANS.
    """
    payload = _require_dict(payload) if payload else {}
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, ("reason",), fe)
    _refuse(fe)
    plan = selectors.plan_or_404(plan_id)
    tax = selectors.tax_or_404(tax_id)
    # CR-165 — an attachment names ONE version; detaching *this tax* from the
    # Plans tab of v2 must find an attachment made when v1 was current.
    attachment = models.PlanTaxRule.objects.filter(
        rate_plan=plan, tax__chain_id=tax.chain_id or tax.id
    ).first()
    if attachment is None:
        mandated = (
            tax.jurisdiction_id is not None
            and models.PlanTaxRule.objects.filter(
                rate_plan=plan, jurisdiction_id=tax.jurisdiction_id
            ).exists()
        )
        if not mandated:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="rating.plans.tax_not_attached",
                params={"tax": tax.name},
            )
        # BR-RAT-115 — the binding is swapped for explicit attachments of the
        # authority's OTHER taxes; only the named tax leaves. `seen` guards the
        # case where one of those taxes was ALSO explicitly attached, which
        # would otherwise trip the validator's duplicate_tax refusal.
        rules = []
        seen: set[str] = set()
        for rule in models.PlanTaxRule.objects.filter(rate_plan=plan).order_by("created_at"):
            if rule.tax_id is not None:
                if rule.tax_id != tax.id and str(rule.tax_id) not in seen:
                    seen.add(str(rule.tax_id))
                    rules.append({"tax": str(rule.tax_id)})
            elif rule.jurisdiction_id == tax.jurisdiction_id:
                for kind in ("percent", "flat"):
                    other = selectors._authority_tax(rule.jurisdiction_id, kind)
                    if other is not None and other.id != tax.id and str(other.id) not in seen:
                        seen.add(str(other.id))
                        rules.append({"tax": str(other.id)})
            else:
                rules.append({"jurisdiction": str(rule.jurisdiction_id)})
    else:
        rules = [
            row
            for row in _plan_tax_rules_payload(plan)
            if row.get("tax") != str(attachment.tax_id)
        ]
    # ── BR-RAT-115's FLOOR — at least ONE tax must be left standing ─────────
    # ⚠ **EVERY DETACH, NOT ONLY THE MANDATED ONE (PO ruling 2026-08-22, the
    # second pass).** The first build scoped this to the mandated path, on the
    # reasoning that detaching an EXPLICIT attachment already shipped under
    # BR-RAT-113 and should not be reversed by inference. The worked case was
    # then put to the PO — a plan whose ONLY tax is an explicit attachment, a
    # $100.00 bill carrying $2.00, and a detach that would leave the plan
    # taxing NOTHING — and the PO ruled the WIDER floor: *"yes lets go with
    # B"*. So the gate is now on the OUTCOME (would this leave zero taxes?)
    # rather than on the ROUTE the departing tax arrived by, which is what
    # *"atleast 1 tax shuld be there"* says when read plainly.
    remaining: set[str] = set()
    for row in rules:
        if "tax" in row:
            remaining.add(row["tax"])
        else:
            for kind in ("percent", "flat"):
                derived = selectors._authority_tax(row["jurisdiction"], kind)
                if derived is not None:
                    remaining.add(str(derived.id))
    # ⚠ **NO `discard` OF THE DEPARTING TAX, AND `tc6` IS WHY.** `rules` is
    # already the post-detach set, so subtracting the tax again asserts it has
    # LEFT THE BILL — which is false for a REDUNDANT attachment: detaching the
    # explicit row for a tax the plan's own jurisdiction still mandates changes
    # no money at all ($6.25 either side, tc6's own figure). Discarding it made
    # the floor refuse a detach that removes nothing. The question this gate
    # asks is "what will this plan tax AFTER the detach", and `rules` is
    # already that answer.
    if not remaining:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-RAT-115",
            message_key="rating.plans.last_tax_not_detachable",
            params={"tax": tax.name},
        )
    body: dict[str, Any] = {"tax_rules": rules}
    reason = str(payload.get("reason") or "").strip()
    if reason:
        body["reason"] = reason
    result = update_plan(actor, plan.id, body)
    _audit_tax_plan_link(actor, "tax.detached_from_plan", tax.id, plan, reason)
    return result


@require_role(SYSTEM_ADMIN)
def publish_plan(actor: Any, plan_id: Any) -> dict[str, Any]:
    """BR-RAT-030 draft → published: publishing makes the plan assignable BY
    STAFF (BR-RAT-039 — v1 has no self-serve offering). D2 completeness is
    checked here: every ticked service needs its schedule (US-RAT-002 TC-5).

    ⚠ **AND SINCE 2026-08-28 A START DATE IS REQUIRED** — BR-RAT-890, the PO
    ruling that closes DEF-494 by removing the state rather than choosing which
    reading of it wins. See the check below for what an undated published plan
    did to the two pricing paths.
    """
    with transaction.atomic():
        plan = selectors.plan_or_404(plan_id)
        if plan.status == PLAN_PUBLISHED:
            # ── `DEF-RAT-9330` · PUBLISHING A PUBLISHED PLAN IS ALREADY DONE ──
            # The 8-step form's commit for a published plan runs PATCH (which
            # files the new version) and THEN this call, and its refusal was
            # shown as the outcome — *"We couldn't publish this plan"* over a
            # version that had been written. Asking for a state the plan is
            # already in is answered, not refused: nothing is written, no audit
            # row, and the answer says so.
            result = selectors.plan_detail(plan.id)
            result["already_published"] = True
            return result
        if plan.status != PLAN_DRAFT:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-030",
                message_key="rating.plans.not_publishable",
                params={"status": plan.status},
            )
        service_ids = set(
            models.PlanService.objects.filter(rate_plan=plan).values_list("service_id", flat=True)
        )
        if not service_ids:
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-RAT-025",
                message_key="rating.plans.no_services",
            )
        scheduled_ids = set(
            models.PlanRateSchedule.objects.filter(rate_plan=plan).values_list(
                "service_id", flat=True
            )
        )
        missing = service_ids - scheduled_ids
        if missing:
            codes = sorted(
                models.PlanService.objects.filter(
                    rate_plan=plan, service_id__in=missing
                ).values_list("service__code", flat=True)
            )
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-RAT-025",
                message_key="rating.plans.service_without_schedule",
                params={"services": codes},
            )
        # ── BR-RAT-890 · A START DATE IS REQUIRED TO PUBLISH (DEF-494) ───────
        # PO ruling 2026-08-28. The question put was *"a rate plan has been
        # published, but nobody ever typed a start date for it — should it be
        # charging customers?"* and the answer was **require a date to
        # publish**, so the state stops existing rather than one reading of it
        # winning.
        #
        # ⚠ **THIS IS THE GATE IN FRONT OF THE R1–R7 CUTOVER, WHICH IS WHY IT
        # IS HERE AND NOT ONLY ON A SCREEN.** `selectors.plan_ref` — what the
        # bill run reads — filters on `status="published"` and consults NO
        # date, so an undated published plan bills FOREVER;
        # `resolution.PlanVersion.in_force_on` requires a stated date, so the
        # SAME plan is in force NEVER and R1 refuses the account outright.
        # Measured on the seeded tenant before this line existed: **47 of 47
        # accounts refused at R1** on each of three bill runs, which is what
        # stopped R2–R7 being compared at all.
        #
        # ⚠ **LAST OF THE THREE CHECKS, ON PURPOSE.** BR-RAT-025's two
        # refusals describe the plan's CONTENT, and a plan with no services is
        # not helped by being told about a date. This one is the single field
        # that says WHEN the content applies, so it is asked last.
        if plan.effective_from is None:
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-RAT-890",
                message_key="rating.plans.no_effective_from",
            )
        plan.status = PLAN_PUBLISHED
        plan.save(update_fields=["status", "updated_at"])
        _mirror_head(plan)
        # BR-RAT-111 — THIS is where v1 is recorded, not at creation. Publishing
        # is the moment a plan's content stops moving: from here `update_plan`
        # refuses a content change without a reason and bumps the counter, so
        # the snapshot taken now is exactly what v1 holds for as long as v1 is
        # the current version. Recording it at creation instead would freeze the
        # first keystrokes of a draft that was then edited nine more times.
        _record_plan_version(actor, plan, _plan_snapshot(plan.id), reason=None)
        _audit(
            actor,
            "plan.published",
            "rate_plan",
            plan.id,
            before={"status": PLAN_DRAFT},
            after={"status": PLAN_PUBLISHED, "version": plan.version},
        )
    return selectors.plan_detail(plan.id)


@require_role(SYSTEM_ADMIN)
def archive_plan(actor: Any, plan_id: Any) -> dict[str, Any]:
    """BR-RAT-030: archiving blocks NEW assignment; history and already-assigned
    accounts are untouched until someone changes them."""
    with transaction.atomic():
        plan = selectors.plan_or_404(plan_id)
        if plan.status == PLAN_ARCHIVED:
            raise errors.BizError(
                errors.BIZ_STATE, br_ref="BR-RAT-030", message_key="rating.plans.already_archived"
            )
        before = {"status": plan.status}
        plan.status = PLAN_ARCHIVED
        plan.save(update_fields=["status", "updated_at"])
        _audit(
            actor,
            "plan.archived",
            "rate_plan",
            plan.id,
            before=before,
            after={"status": PLAN_ARCHIVED, "accounts": selectors.plan_account_count(plan)},
        )
    return selectors.plan_detail(plan.id)


@require_role(SYSTEM_ADMIN)
def delete_plan(actor: Any, plan_id: Any) -> None:
    """US-RAT-001 TC-5 (IS-1): hard delete ONLY at accounts = 0 AND never
    billed — otherwise the 🔒 audit-lock refuses and offers Archive. The counts
    are recomputed INSIDE the transaction, never trusted from the list page."""
    with transaction.atomic():
        plan = selectors.plan_or_404(plan_id)
        accounts = selectors.plan_account_count(plan)
        billed = seams.plan_invoice_references(plan.id)
        # DEF-079 — **None is not zero and must never be treated as one.** It
        # means billing could not answer the "never billed" half, and this
        # delete is permanent: it takes the plan's rate schedules and every
        # charge, deposit, penalty and tax rule with it, and `units.rate_plan_id`
        # protects only a plan that is LIVE on a unit. A retired plan behind
        # real bills has nothing else refusing for it, because invoices
        # deliberately SNAPSHOT rather than reference a plan. So an
        # unanswerable count LOCKS, and the refusal says which half was
        # unanswerable rather than showing a clerk a blank.
        if accounts or billed is None or billed:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-RAT-030",
                message_key="rating.plans.locked_referenced",
                params={
                    "accounts": accounts,
                    "invoices": "unavailable" if billed is None else billed,
                },
            )
        before = _plan_snapshot(plan.id)
        models.PlanService.all_versions.filter(rate_plan=plan).delete()  # BR-RAT-1066: every version
        models.PlanRateSchedule.all_versions.filter(rate_plan=plan).delete()  # BR-RAT-1066: every version
        models.PlanChargeRule.all_versions.filter(rate_plan=plan).delete()  # BR-RAT-1066: every version
        models.PlanDepositRule.objects.filter(rate_plan=plan).delete()
        models.PlanPenaltyRule.objects.filter(rate_plan=plan).delete()
        models.PlanTaxRule.all_versions.filter(rate_plan=plan).delete()  # BR-RAT-1066: every version
        # BR-RAT-110 · BR-RAT-111 — both new children hold `PROTECT` on the
        # plan, so omitting either turns this hard delete into a `ProtectedError`
        # 500 rather than the refusal above. They are cleared here and nowhere
        # else: the gate has already established this plan has **0 accounts and
        # has never been billed**, so there is no regulatory record to preserve
        # and no availability anyone could have acted on. A plan that HAS either
        # never reaches this line.
        discount_models.PlanDiscountRule.all_versions.filter(rate_plan=plan).delete()  # BR-RAT-1066: every version
        models.RatePlan.objects.filter(pk=plan.pk).update(head_version_id=None)
        models.PlanVersion.objects.filter(rate_plan=plan).delete()
        plan_pk = plan.id
        plan.delete()
        _audit(actor, "plan.deleted", "rate_plan", plan_pk, before=before)


# ══════════════════════════════════════════════════════════════════════════
# Rate schedules — US-RAT-004..007 (EP-RAT-02)
# ══════════════════════════════════════════════════════════════════════════
SCHEDULE_FIELDS: tuple[str, ...] = (
    "name",
    "service",
    "account_type_id",
    "model",
    "uom",
    "currency",
    "base_charge",
    # `CR-120-BRC06` · `BR-RAT-1025` — the code the schedule NAMES as its
    # service's base. ⚠ It sits beside `base_charge` above and is its OPPOSITE:
    # that one is the RETIRED decimal (`BR-RAT-088`), this one is a POINTER at
    # `charges`. A payload carrying a figure here, or a code there, has them the
    # wrong way round.
    "base_charge_code",
    "minimum_bill",
    "effective_from",
    "effective_to",
    "regulator_ref",
    # BR-RAT-082 — the regulator's sign-off, captured and kept. Never a gate.
    "filing_authority",
    "filed_on",
    "regulator_approved_on",
    "regulator_approver",
    # DEF-369 · the label a regulator's docket references, stored rather than
    # derived from a row's position in the effective-date order.
    "version_label",
    # DEF-280 · BR-RAT-037's reason, kept on the version it describes.
    "change_reason",
    "notify_customers",
    "publish_public",
    "approved_by",
    "structure",
    # DEF-360 / §A3 — the SCHEDULE's half of the size axis. `base` is absent by
    # BR-RAT-088: the charge code owns it and this payload cannot express it.
    "size_rows",
    "confirm_percent_over_100",
)


def _validate_schedule_identity(
    payload: dict[str, Any], fe: list[dict[str, Any]], *, partial: bool, tariff: Any = None
) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    name = _text(payload, "name", fe, required=not partial, max_length=120)
    service = None
    if "service" in payload or not partial:
        code = _text(payload, "service", fe, required=not partial)
        service = _enabled_service(code, "service", fe)
        if service is not None:
            cleaned["service_id"] = service["id"]
            cleaned["service_code"] = service["code"]
    if name is not None:
        cleaned["name"] = name
        service_id = cleaned.get("service_id") or (tariff.service_id if tariff else None)
        if service_id is not None:
            duplicate = models.Tariff.objects.filter(
                tenant_id=_tenant_id(), name=name, service_id=service_id
            )
            if tariff is not None:
                duplicate = duplicate.exclude(pk=tariff.pk)
            if duplicate.exists():
                fe.append(
                    _field_error("name", errors.VAL_FORMAT, "rating.schedules.duplicate_name")
                )
    if "account_type_id" in payload:
        cleaned["account_type_id"] = _uuid_value(payload, "account_type_id", fe)
    return cleaned


def _validate_version_fields(
    payload: dict[str, Any], fe: list[dict[str, Any]], *, require_effective_from: bool
) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    cleaned["model"] = _choice(payload, "model", TARIFF_MODELS, fe, required=True)
    cleaned["uom"] = _text(payload, "uom", fe, max_length=20)
    cleaned["currency"] = (payload.get("currency") or "USD").upper()[:3]
    # DEF-277 — ABSENT STAYS ABSENT. This read `_decimal(...) or Decimal("0")`
    # until 2026-08-19, which turned three different facts into one stored row:
    # "no base typed", "this size is not served" (CR-013 part 1's meaning of a
    # blank) and "served, and free". The `or` even swallowed an explicit 0,
    # since `Decimal("0")` is falsey — so the deliberate zero was rewritten as
    # the default zero and the distinction never survived the write path at all.
    # `_decimal` already returns None for an absent or null field; letting that
    # None through is the whole fix, and the nullable column is what lets it
    # round-trip.
    cleaned["base_charge"] = _decimal(payload, "base_charge", fe, minimum=Decimal("0"))
    # ⚠ **AN ABSENT MINIMUM IS ZERO, AND IT IS STORED AS AN ABSENCE (PO ruling
    # 2026-09-19, `CR-120-BRC06`).** Verbatim: *"min we can give in rate
    # schedule - if it is not there then you ahve to add it at step 2 - deulta
    # will be zero"*. A minimum tops a bill UP to itself, so a floor of `0.00`
    # and no floor produce the IDENTICAL bill — which is why the default can be
    # zero without a value being written. **It is the exact opposite of
    # `base_charge` one line up**, where `CR-013` part 1 / `DEF-277` make a
    # blank *"size not served"* and a stored `0` *"served, and free"*: there the
    # two readings are a refused bill and `$0.00`. Nothing is coerced here, and
    # a lane that "simplifies" this to `or Decimal("0")` has filled r10's
    # electric matrix — an em-dash on every size — with `0.00`.
    #
    # ⚠⚠ **SUPERSEDED 2026-10-01 — THE VERSION CARRIES NO MINIMUM ANY MORE
    # (`DEF-RAT-8737`, PO option A: *"A · Minimum per size - this is
    # correct"*).** The paragraph above describes a field the ruling removed:
    # *"the step 3 per-version minimum is removed from screen and stops being
    # billed"*. The minimum is the per-SIZE figure on `size_rows`
    # (`_validate_size_rows`), which billing reads (`selectors._size_minimum`).
    # A payload STATING a figure here is refused by name — accepting and
    # dropping it would tell a clerk a floor was set that nothing bills — and a
    # `null` or an absent key is accepted, because both already mean *no
    # version minimum*, which is now the only answer. Nothing is written:
    # `rating/0053` moved every stated figure onto its version's size rows.
    if payload.get("minimum_bill") is not None:
        fe.append(_field_error("minimum_bill", errors.VAL_FORMAT, "rating.unknown_field"))
    cleaned["minimum_bill"] = None
    # `DEF-RAT-6932` — **CLEARED ON PURPOSE AND NOT MENTIONED ARE DIFFERENT
    # INTENTIONS, AND THIS LINE USED TO COLLAPSE THEM.** The key's PRESENCE is
    # what distinguishes them, exactly as it already does for `account_type_id`
    # one screen across, so the key is only written into `cleaned` when the
    # payload actually spoke:
    #
    #   `{"base_charge_code": "<id>"}`  → that code. A person chose it.
    #   `{"base_charge_code": null}`    → NOTHING. A person emptied the picker,
    #                                     and the service's declared base
    #                                     answers (`BR-RAT-1025` arm 2).
    #   the key absent                  → NOT AN ANSWER. `cleaned` carries no
    #                                     `base_charge_code_id` at all, and
    #                                     `_carry_forward_base_charge_code`
    #                                     below fills it from the row this
    #                                     version succeeds.
    #
    # ⚠ `_write_version` still reads this with `.get`, so a brand-new schedule
    # — where there is no row to carry anything forward from — writes NULL, the
    # behaviour every schedule that exists today has.
    if "base_charge_code" in payload:
        cleaned["base_charge_code_id"] = _validate_base_charge_code(payload, fe)
    effective_from = _date_value(payload, "effective_from", fe, required=require_effective_from)
    effective_to = _date_value(payload, "effective_to", fe)
    if effective_from and effective_to and effective_from >= effective_to:
        fe.append(
            _field_error("effective_to", errors.VAL_RANGE, "rating.schedules.window_inverted")
        )
    cleaned["effective_from"] = effective_from
    cleaned["effective_to"] = effective_to
    cleaned["regulator_ref"] = _text(payload, "regulator_ref", fe, max_length=200)
    # BR-RAT-082: *"we can collect the details and keep it"* — captured, stored,
    # and read by NOTHING. No `required=` on any of the four, deliberately: the
    # in-system approval workflow was removed by BR-RAT-031 as-modified and a
    # required regulator field would rebuild it by the back door. A schedule
    # activates with all four blank exactly as it did before they existed.
    cleaned["filing_authority"] = _text(payload, "filing_authority", fe, max_length=200)
    cleaned["filed_on"] = _date_value(payload, "filed_on", fe)
    cleaned["regulator_approved_on"] = _date_value(payload, "regulator_approved_on", fe)
    cleaned["regulator_approver"] = _text(payload, "regulator_approver", fe, max_length=200)
    # DEF-369 — the FILED label, free text and never derived. Same standing as
    # `regulator_ref` beside it: captured because we are the system of record,
    # never required, never unique, never read by anything that prices.
    cleaned["version_label"] = _text(payload, "version_label", fe, max_length=60)
    # DEF-280 — the authored change note. Optional HERE and required by
    # `create_rate_schedule_version`, which is where BR-RAT-037 binds: a first
    # version has no change to describe, and a draft nobody has published yet
    # is not a change to a published object.
    cleaned["change_reason"] = _text(payload, "change_reason", fe, max_length=500)
    cleaned["size_rows"] = _validate_size_rows(payload.get("size_rows"), fe)
    cleaned["notify_customers"] = _bool(payload, "notify_customers")
    cleaned["publish_public"] = _bool(payload, "publish_public")
    # BR-RAT-031 as-modified: approval happens OUTSIDE the system; this is
    # optional metadata and NEVER a gate.
    cleaned["approved_by_id"] = _uuid_value(payload, "approved_by", fe)
    return cleaned


def _validate_base_charge_code(payload: dict[str, Any], fe: list[dict[str, Any]]) -> UUID | None:
    """`CR-120-BRC06` · `BR-RAT-1025` — the charge code this schedule NAMES as
    its service's base, or None.

    PO ruling 2026-09-19, verbatim: *"no this is not correct ; So: plan → rate
    schedule -> charge code → base charges - this is correct"*, and *"we are not
    bindng base charges in rate schedule - you were taking it default; now we
    are making it explicit it is a same rule - change is default ->
    expliciate"*.

    **NONE IS A REAL ANSWER AND IT IS THE COMMON ONE.** A schedule that names
    nothing resolves its base exactly as every schedule does today — the
    `is_base` charge code for the service, narrowed by customer class and
    connection size. There is no `required=` here and there never should be:
    making the binding mandatory would refuse every save by every tenant on the
    day it shipped, which is `_guard_base_charge_code`'s own recorded lesson one
    screen across.

    ── WHAT IS CHECKED HERE, AND WHAT IS DELIBERATELY CHECKED LATER ──────────
    **HERE: the row exists, in this tenant, and is not deleted.** A dangling id
    is never right at any point in the object's life, so it is refused at the
    moment it is typed.

    **AT ACTIVATION: whether the bound code could actually price this
    schedule's service** — `is_base`, the service, and the customer-class scope
    (`_guard_bound_base_charge_code`). Those three are MUTABLE on the charge
    code after the binding is written, so enforcing them here would mean a
    clerk editing a charge code on a different screen gets a refusal naming a
    rate schedule. It is also the wrong moment: a DRAFT is a half-built thing
    by `BR-RAT-031`'s design, and refusing a draft whose code is not ticked yet
    stops somebody setting a service up in the order that suits them.

    That split is `DEF-2923`'s reasoning applied rather than re-invented — the
    refusal belongs on a settings screen with the cure in its own sentence,
    never on the day the money is due.

    ⚠ **NONE HERE MEANS *A PERSON EMPTIED THE PICKER*, AND IT NO LONGER ALSO
    MEANS *NOBODY SAID ANYTHING* (`DEF-RAT-6932`, 2026-09-27).** This function
    used to answer None for a payload with no `base_charge_code` key at all,
    and `_write_version` wrote that None onto the version — so a save that did
    not mention the binding erased it. The PRESENCE of the key is now tested by
    the one caller, `_validate_version_fields`, which does not call this at all
    when the key is absent; `_carry_forward_base_charge_code` then fills the
    field from the row the new version succeeds. **The `not in payload` clause
    below is kept as a defensive guard for any future caller and is no longer
    the path a rate change takes.**
    """
    if "base_charge_code" not in payload or payload["base_charge_code"] in (None, ""):
        return None
    code_id = _uuid_value(payload, "base_charge_code", fe)
    if code_id is None:
        return None
    exists = models.Charge.objects.filter(
        tenant_id=_tenant_id(), pk=code_id, deleted_at__isnull=True
    ).exists()
    if not exists:
        fe.append(
            _field_error(
                "base_charge_code",
                errors.VAL_FORMAT,
                "rating.schedules.base_charge_code_unknown",
            )
        )
        return None
    return code_id


def _carry_forward_base_charge_code(
    cleaned: dict[str, Any], previous: models.TariffVersion | None
) -> None:
    """`DEF-RAT-6932` · `BR-RAT-1025` — **A VERSION THAT DOES NOT MENTION THE
    BINDING KEEPS IT.**

    A schedule NAMES the charge code that owns its service's base. Every other
    fact a version carries is restated by the payload that writes it, so the
    binding was too — and a save that simply did not mention it wrote a version
    with no binding at all. **A "new price, from a date" is exactly such a
    save**: step 1's picker is not what the clerk came to change, and an API
    client filing a rate change has no reason to repeat it.

    Nothing refused and nothing warned. The schedule went on SHOWING a base
    charge code until the page was reloaded, and the next bill resolved its
    base by the `is_base` lookup instead — which on a catalogue with more than
    one base code for the service is `DEF-468`'s refusal, by name, on the day
    the money is due.

    ⚠ **THE TWO INTENTIONS ARE KEPT APART AND THAT IS THE WHOLE CARE HERE.**
    `_validate_version_fields` writes `base_charge_code_id` into `cleaned` ONLY
    when the payload carried the key. So:

      * **the key is in `cleaned`** — the payload SPOKE. It named a code, or it
        said `null`, which is a person emptying the picker and meaning *this
        schedule names nothing*. Either way it is an answer and this function
        does not touch it. That is what the front end posts: `draftPayload`
        sends `base_charge_code` even when it is empty, on purpose, and says so
        in its own comment.
      * **the key is absent** — nobody said anything, so the version inherits
        what the row it succeeds held.

    Collapsing those two is what caused the defect; collapsing them the OTHER
    way would make the picker impossible to clear, which is why
    `test_def_rat_6932__an_explicit_null_still_clears_it` is in the same file
    as the three carry-forward cases and was green before this function existed.

    ⚠ **`previous is None` WRITES NULL, NOT A GUESS.** A brand-new schedule has
    no row to inherit from, and that is every schedule's first version — the
    behaviour `CR-120-BRC06` shipped and measured (*"all 47 ready accounts
    resolve the same base, from the same code, at the same amount"*).

    ⚠ **IT RUNS BEFORE `_guard_bound_base_charge_code`, DELIBERATELY.** A
    carried binding is a binding this version asserts, so it is re-checked at
    activation like any other: the code may have been retired, un-ticked, moved
    to another service or re-scoped since it was first named. A carry-forward
    that skipped the guard would put a figure on step 5 that the bill will not
    use, which is the exact disagreement `BR-RAT-1025` exists to prevent.

    **BR-RAT-037 is untouched.** Nothing here rewrites a version; it fills in a
    field of the NEW row before it is written.
    """
    if "base_charge_code_id" in cleaned:
        return
    cleaned["base_charge_code_id"] = (
        previous.base_charge_code_id if previous is not None else None
    )


def _validate_size_rows(raw: Any, fe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """DEF-360 · the schedule's per-connection-size rows — MINIMUM BILL only.

    §A3's split, quoted: the **base** column is written by the CHARGE CODE and
    the schedule *"shows it read-only, attributed"*; the **minimum bill** and the
    **tier/period rates** are the schedule's own usage math. So `base` is not a
    key this payload accepts, and `_reject_unknown` refuses it by name rather
    than ignoring it — a client that posts a base here is expressing the
    `$24.00` double-charge BR-RAT-088 exists to prevent, and silence would let
    it think the base was stored.

    ⚠ **A MISSING `minimum_bill` IS NOT ZERO.** CR-013 part 1's *"blank base =
    size not served"* (DEF-277) is the same distinction one column across: r10's
    electric matrix draws an em-dash in the minimum column for every size, and
    that is "this size has no minimum bill", not "its minimum bill is $0.00". A
    row with a NULL amount is therefore a real, stored row — it says the size IS
    served and has no floor — and `_decimal`'s None is let through untouched.

    ⚠ **`size_class` IS NOT CHECKED AGAINST `service_size_classes`, DELIBERATELY.**
    The column is TEXT and not an FK for the reason `RateSizeRow` states: *"a
    size Settings RETIRES must not vanish from a schedule that already priced
    it"*. An existence check here would refuse exactly that case, which is
    CR-013's *"tie it correctly"* read backwards. The picker offers the live
    list; the write keeps whatever a version was built with.

    ⚠ **PER-SIZE TIER RATES ARE NOT HERE AND ARE NOT BUILT — DEF-433.**
    `RateTier.size_class` exists and is nullable, and nothing writes or serves
    it, so r10's 2" water row (`3.45 / 5.10 / 7.70` against every other size's
    `3.20 / 4.80 / 7.20`) is still inexpressible through the API. Filed rather
    than half-built: a size axis that silently dropped a tier override would be
    worse than one that says it has none.
    """
    rows: list[dict[str, Any]] = []
    if raw is None:
        return rows
    if not isinstance(raw, list):
        fe.append(_field_error("size_rows", errors.VAL_FORMAT, "rating.size_rows.not_list"))
        return rows
    seen: set[str] = set()
    for index, item in enumerate(raw):
        prefix = f"size_rows[{index}]."
        if not isinstance(item, dict):
            fe.append(_field_error(prefix, errors.VAL_FORMAT, "rating.size_rows.not_object"))
            continue
        _reject_unknown(item, ("size_class", "minimum_bill"), fe, prefix=prefix)
        size_class = _text(item, "size_class", fe, required=True, max_length=60, prefix=prefix)
        minimum_bill = _decimal(item, "minimum_bill", fe, minimum=Decimal("0"), prefix=prefix)
        if size_class is None:
            continue
        if size_class in seen:
            # The DB's uq_rate_size_rows_tenant_version_size would raise a 500
            # here; a field error says which row is the duplicate.
            fe.append(
                _field_error(
                    f"{prefix}size_class",
                    errors.VAL_FORMAT,
                    "rating.size_rows.duplicate_size",
                    size_class=size_class,
                )
            )
            continue
        seen.add(size_class)
        rows.append({"size_class": size_class, "minimum_bill": minimum_bill})
    return rows


# ── structure validation (BR-RAT-032/033/034 + the model-specific rules) ────
def _validate_tiers(
    raw: Any, fe: list[dict[str, Any]], *, prefix: str = "structure."
) -> list[dict[str, Any]]:
    """BR-RAT-032: seq-ordered · contiguous (tier n+1 From = tier n To) ·
    From < To · only the LAST tier open-ended · rates ≥ 0. Pure tiers, no
    allowance field exists anywhere (BR-RAT-026).

    ⚠ **DEF-433 · CONTIGUITY IS VALIDATED PER SIZE GROUP, NOT OVER THE LIST.**
    `RateTier.size_class` shipped nullable with nothing writing it, so r10's 2"
    water row — `3.45 / 5.10 / 7.70` where every other size prices `3.20 / 4.80
    / 7.20` — could not be expressed at all. It is accepted here now, and the
    validation had to change SHAPE rather than gain a field: a payload carrying
    a base ladder `0→10→30→∞` and a 2" ladder `0→10→30→∞` is six rows whose
    `from_qty`s go `0, 10, 30, 0, 10, 30`, and the old single running
    `previous_to` reads that as a gap at row four and refuses a correct rate.
    So the rows are grouped by `size_class` first and BR-RAT-032 is applied
    inside each group, independently.

    **The NULL group is REQUIRED and it is the fallback.** `RateTier`'s own
    docstring is the rule: NULL means *"every size"*, a size-specific group
    OVERRIDES it, and *"a schedule states the exception, not the rule"*. A
    payload of nothing but size-specific ladders would leave every size the
    utility did not name with no price at all — priced as zero, or refused at
    bill time, depending on which read got there first. Refused here instead,
    by name.

    ⚠ **AND THE OVERRIDE DOES NOT YET REACH A BILL — DEF-484, stated on the
    screen and served as a notice.** `selectors.pricing_inputs` takes the size
    now and falls back to the NULL group, but `apps/billing/gather.py` (another
    module) calls it without one, so a 2" connection currently bills the base
    ladder. The write path is real and the read path is honest; the wiring is
    filed, not assumed.
    """
    rows: list[dict[str, Any]] = []
    if not isinstance(raw, list) or not raw:
        fe.append(_field_error(f"{prefix}tiers", errors.VAL_REQUIRED, "rating.tiers.required"))
        return rows
    # Pass 1 — every row's own fields, in payload order, keeping the index so a
    # field error still names the row the client sent.
    parsed: list[tuple[int, dict[str, Any]]] = []
    for index, item in enumerate(raw):
        item_prefix = f"{prefix}tiers[{index}]."
        if not isinstance(item, dict):
            fe.append(_field_error(item_prefix, errors.VAL_FORMAT, "rating.tiers.not_object"))
            continue
        _reject_unknown(
            item,
            ("from_qty", "to_qty", "unit_price", "season", "size_class"),
            fe,
            prefix=item_prefix,
        )
        from_qty = _decimal(
            item, "from_qty", fe, required=True, minimum=Decimal("0"), prefix=item_prefix
        )
        to_qty = _decimal(item, "to_qty", fe, minimum=Decimal("0"), prefix=item_prefix)
        unit_price = _decimal(
            item, "unit_price", fe, required=True, minimum=Decimal("0"), prefix=item_prefix
        )  # US-RAT-005 TC-6: rate ≥ 0
        # DEF-433. TEXT and NOT checked against `service_size_classes`, for the
        # reason `_validate_size_rows` records one screen across: a size that
        # Settings RETIRES must not vanish from a version that already priced
        # it, and an existence check here would refuse exactly that version.
        size_class = _text(item, "size_class", fe, max_length=60, prefix=item_prefix)
        if from_qty is None or unit_price is None:
            continue
        if to_qty is not None and to_qty <= from_qty:
            fe.append(
                _field_error(f"{item_prefix}to_qty", errors.VAL_RANGE, "rating.tiers.inverted")
            )
        parsed.append(
            (
                index,
                {
                    "from_qty": from_qty,
                    "to_qty": to_qty,
                    "unit_price": unit_price,
                    "season": item.get("season"),
                    "size_class": size_class,
                },
            )
        )
    if not parsed:
        return rows
    # Pass 2 — BR-RAT-032 inside each size group. `dict` preserves insertion
    # order, so the groups come out in the order the client sent them and the
    # NULL group keeps its natural place at the front of an ordinary payload.
    groups: dict[str | None, list[tuple[int, dict[str, Any]]]] = {}
    for index, row in parsed:
        groups.setdefault(row["size_class"], []).append((index, row))
    if None not in groups:
        # The exception without the rule. Named on `tiers` rather than on a row
        # because no single row is wrong — the SET is incomplete.
        fe.append(
            _field_error(
                f"{prefix}tiers",
                errors.VAL_REQUIRED,
                "rating.tiers.size_override_without_base",
                sizes=", ".join(sorted(str(size) for size in groups if size is not None)),
            )
        )
    for members in groups.values():
        previous_to: Decimal | None = None
        for position, (index, row) in enumerate(members):
            item_prefix = f"{prefix}tiers[{index}]."
            is_last = position == len(members) - 1
            if row["to_qty"] is None and not is_last:
                # US-RAT-005 TC-5: only the last tier OF ITS GROUP may be open-
                # ended. Over the flat list this used to mean "the last row of
                # the payload", which made every group but the final one
                # unable to have a top block at all.
                fe.append(
                    _field_error(
                        f"{item_prefix}to_qty", errors.VAL_FORMAT, "rating.tiers.open_middle_tier"
                    )
                )
            if previous_to is not None and row["from_qty"] != previous_to:
                # US-RAT-005 TC-4: gaps and overlaps are both non-contiguous.
                # ⚠ DEF-RAT-5717 — **THE PARAMS ARE THE MESSAGE, AND THREE OF
                # THESE FOUR WERE NOT BEING SENT.** `expected` was, and the
                # catalogue sentence had no placeholder for it, so i18next
                # dropped it without a word: a clerk read *"tiers must run on
                # from one another"* and was left to work out WHICH tier and
                # WHICH number. The PO reported exactly that — *"tier 2 should
                # start from 100"* — and the number was already in this call.
                # The sentence now names both tiers and both numbers, which is
                # what the Plans & Rates blueprint p047 rules: *"the message
                # names the two tiers and the two numbers, so the fix is
                # visible without re-reading the table."*
                #
                # `position + 1` and not `index`: the number a clerk reads is
                # the row's place IN ITS GROUP, which is what the screen counts
                # (a per-size ladder restarts at Tier 1). `index` is the
                # position in the flat payload and would name Tier 4 on a
                # six-row two-size ladder.
                fe.append(
                    _field_error(
                        f"{item_prefix}from_qty",
                        errors.VAL_FORMAT,
                        "rating.tiers.not_contiguous",
                        tier=position + 1,
                        starts=str(row["from_qty"]),
                        previous=position,
                        expected=str(previous_to),
                    )
                )
            previous_to = row["to_qty"]
            # `seq` is the row's position WITHIN ITS GROUP, which is what a
            # matrix column header counts (`Tier 1 · Tier 2 · Tier 3` reads the
            # same against 5/8" and against 2"). The STORED seq is not this —
            # `_write_version` renumbers globally because `uq_rate_tiers_version_seq`
            # is kept verbatim — so this number never leaves validation.
            rows.append({"seq": position + 1, **row})
    return rows


def _season_intervals(seasons: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """[start, end] day-of-year ordinals on a non-leap reference year, wrapping
    seasons split into two intervals."""
    reference = 2001  # non-leap: Feb 29 never participates in coverage math
    intervals: list[tuple[int, int]] = []
    for season in seasons:
        start = date(reference, season["start_month"], season["start_day"]).timetuple().tm_yday
        end = date(reference, season["end_month"], season["end_day"]).timetuple().tm_yday
        if start <= end:
            intervals.append((start, end))
        else:  # wraps the year end (e.g. Winter Oct 1 – May 31)
            intervals.append((start, DAYS_PER_YEAR))
            intervals.append((1, end))
    return sorted(intervals)


def _validate_seasons(
    raw: Any, fe: list[dict[str, Any]], *, prefix: str = "structure.", required: bool = True
) -> list[dict[str, Any]]:
    """BR-RAT-033/034: season date ranges cover the full year without overlap."""
    rows: list[dict[str, Any]] = []
    if not isinstance(raw, list) or not raw:
        if required:
            fe.append(
                _field_error(f"{prefix}seasons", errors.VAL_REQUIRED, "rating.seasons.required")
            )
        return rows
    for index, item in enumerate(raw):
        item_prefix = f"{prefix}seasons[{index}]."
        if not isinstance(item, dict):
            fe.append(_field_error(item_prefix, errors.VAL_FORMAT, "rating.seasons.not_object"))
            continue
        _reject_unknown(
            item,
            ("label", "start_month", "start_day", "end_month", "end_day", "unit_price", "tiers"),
            fe,
            prefix=item_prefix,
        )
        label = _text(item, "label", fe, required=True, max_length=40, prefix=item_prefix)
        bounds: dict[str, int] = {}
        for field, ceiling in (
            ("start_month", 12),
            ("start_day", 31),
            ("end_month", 12),
            ("end_day", 31),
        ):
            try:
                value = int(item.get(field))
            except (TypeError, ValueError):
                fe.append(
                    _field_error(f"{item_prefix}{field}", errors.VAL_REQUIRED, "rating.required")
                )
                continue
            if not 1 <= value <= ceiling:
                fe.append(
                    _field_error(f"{item_prefix}{field}", errors.VAL_RANGE, "rating.out_of_range")
                )
                continue
            bounds[field] = value
        if label is None or len(bounds) != 4:
            continue
        try:
            date(2001, bounds["start_month"], bounds["start_day"])
            date(2001, bounds["end_month"], bounds["end_day"])
        except ValueError:
            fe.append(_field_error(f"{item_prefix}start_day", errors.VAL_RANGE, "rating.bad_date"))
            continue
        rows.append(
            {
                "label": label,
                **bounds,
                "unit_price": item.get("unit_price"),
                "tiers": item.get("tiers"),
            }
        )

    if rows and not fe:
        intervals = _season_intervals(rows)
        covered = 0
        cursor = 1
        for start, end in intervals:
            if start != cursor:
                fe.append(
                    _field_error(
                        f"{prefix}seasons",
                        errors.VAL_FORMAT,
                        "rating.seasons.coverage",  # gap or overlap — same refusal
                    )
                )
                return rows
            covered += end - start + 1
            cursor = end + 1
        if covered != DAYS_PER_YEAR:
            fe.append(
                _field_error(f"{prefix}seasons", errors.VAL_FORMAT, "rating.seasons.coverage")
            )
    return rows


def _window_intervals(start: time, end: time) -> list[tuple[int, int]]:
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    if end_minutes == 0:
        end_minutes = MINUTES_PER_DAY  # 00:00 as an end means midnight-of-next-day
    if start_minutes < end_minutes:
        return [(start_minutes, end_minutes)]
    return [(start_minutes, MINUTES_PER_DAY), (0, end_minutes)]  # wraps midnight


#: `CR-157-BRC10` — the three window names the rate-schedule redesign offers,
#: each naming the meter register it is billed from (`models.TOU_CHANNELS`).
#: Matched without regard to case, spaces or hyphens, so "On-peak", "on peak"
#: and "ONPEAK" are one window; anything else is a tenant's own name and
#: carries its register explicitly (BR-RAT-067, unchanged).
TOU_WINDOW_REGISTERS: dict[str, str] = {
    "onpeak": "tou_on",
    "midpeak": "tou_mid",
    "offpeak": "tou_off",
}


def tou_register_for_window(label: Any) -> str | None:
    """The register a window NAME implies, or None for a name outside the three."""
    if not isinstance(label, str):
        return None
    key = "".join(ch for ch in label.lower() if ch.isalnum())
    return TOU_WINDOW_REGISTERS.get(key)


def _validate_tou(raw: Any, fe: list[dict[str, Any]]) -> dict[str, Any]:
    """BR-RAT-021/033 Option B: ≤3 windows per (season × day-type), windows
    cover 00:00–24:00 with no overlap (a window may wrap midnight), ≤2 seasons
    covering the year, prices ≥ 0."""
    structure = raw if isinstance(raw, dict) else {}
    seasons = _validate_seasons(structure.get("seasons"), fe)
    if len(seasons) > MAX_TOU_SEASONS:
        fe.append(
            _field_error(
                "structure.seasons",
                errors.VAL_RANGE,
                "rating.tou.too_many_seasons",
                max=MAX_TOU_SEASONS,
            )
        )
    windows_raw = structure.get("windows")
    windows: list[dict[str, Any]] = []
    if not isinstance(windows_raw, list) or not windows_raw:
        fe.append(_field_error("structure.windows", errors.VAL_REQUIRED, "rating.tou.required"))
        return {"seasons": seasons, "windows": windows}
    season_labels = {season["label"] for season in seasons}
    for index, item in enumerate(windows_raw):
        prefix = f"structure.windows[{index}]."
        if not isinstance(item, dict):
            fe.append(_field_error(prefix, errors.VAL_FORMAT, "rating.tou.not_object"))
            continue
        _reject_unknown(
            item,
            ("label", "season", "day_type", "start_time", "end_time", "unit_price", "channel"),
            fe,
            prefix=prefix,
        )
        label = _text(item, "label", fe, required=True, max_length=40, prefix=prefix)
        season_label = _text(item, "season", fe, prefix=prefix)
        if season_label is not None and season_label not in season_labels:
            fe.append(
                _field_error(
                    f"{prefix}season", errors.VAL_UNKNOWN_LOOKUP, "rating.tou.unknown_season"
                )
            )
        day_type = _choice(item, "day_type", DAY_TYPES, fe, prefix=prefix) or "weekday"
        start_time = _time_value(item, "start_time", fe, prefix=prefix)
        end_time = _time_value(item, "end_time", fe, prefix=prefix)
        unit_price = _decimal(
            item, "unit_price", fe, required=True, minimum=Decimal("0"), prefix=prefix
        )
        # BR-RAT-067: REQUIRED, and required HERE rather than at activation, because a
        # price with no register is the one field combination that produces a plausible
        # bill at the wrong number. `_choice(required=True)` raises the field error the
        # S11 card renders beside the window.
        #
        # `CR-157-BRC10` — **THE WINDOW'S NAME NOW SETS ITS REGISTER** where the
        # name is one of the three the redesign offers (*On-peak · Mid-peak ·
        # Off-peak*, drawn as a picker with the Register column read-only —
        # `05-prototype/rate-schedules-2026-10-01/images/46-add-2-pricing-tou.png`).
        # The register is then DERIVED and need not be sent; one that is sent
        # and disagrees is refused by name rather than silently preferred,
        # because either reading would bill one register at the other's price.
        # A name outside the three (a tenant's own "Punta", "Peak") keeps the
        # rule it always had: the register is REQUIRED and is what was typed.
        derived = tou_register_for_window(label)
        channel = _choice(
            item, "channel", TOU_CHANNELS, fe, required=derived is None, prefix=prefix
        )
        if derived is not None:
            if channel is not None and channel != derived:
                fe.append(
                    _field_error(
                        f"{prefix}channel",
                        errors.VAL_FORMAT,
                        "rating.tou.window_register_mismatch",
                        window=label,
                        expected=derived,
                    )
                )
                continue
            channel = derived
        if None in (label, start_time, end_time, unit_price, channel):
            continue
        windows.append(
            {
                "label": label,
                "season": season_label,
                "day_type": day_type,
                "start_time": start_time,
                "end_time": end_time,
                "unit_price": unit_price,
                "channel": channel,
            }
        )
    if fe:
        return {"seasons": seasons, "windows": windows}

    grouped: dict[tuple[Any, str], list[dict[str, Any]]] = {}
    for window in windows:
        grouped.setdefault((window["season"], window["day_type"]), []).append(window)
    for (season_label, day_type), group in sorted(
        grouped.items(), key=lambda item: (str(item[0][0]), item[0][1])
    ):
        if len(group) > MAX_TOU_WINDOWS:
            # US-RAT-006 TC-4: "Option B supports up to 3 windows".
            fe.append(
                _field_error(
                    "structure.windows",
                    errors.VAL_RANGE,
                    "rating.tou.too_many_windows",
                    max=MAX_TOU_WINDOWS,
                    season=season_label,
                    day_type=day_type,
                )
            )
            continue
        intervals: list[tuple[int, int]] = []
        for window in group:
            intervals.extend(_window_intervals(window["start_time"], window["end_time"]))
        intervals.sort()
        cursor = 0
        for start, end in intervals:
            if start != cursor:
                # US-RAT-006 TC-5: every hour belongs to exactly one window.
                fe.append(
                    _field_error(
                        "structure.windows",
                        errors.VAL_FORMAT,
                        "rating.tou.coverage",
                        season=season_label,
                        day_type=day_type,
                    )
                )
                break
            cursor = end
        else:
            if cursor != MINUTES_PER_DAY:
                fe.append(
                    _field_error(
                        "structure.windows",
                        errors.VAL_FORMAT,
                        "rating.tou.coverage",
                        season=season_label,
                        day_type=day_type,
                    )
                )
    # BR-RAT-067 clause 2: inside one season, window and register must pair one-to-one.
    # Checked PER SEASON and not per (season × day-type), because a register holds ONE
    # number for the whole period — the weekday and weekend rows of "On-peak" are one
    # register between them (the same reasoning that makes disagreeing day-type prices a
    # refusal, OQ-233). Two DIFFERENT windows on one register would price that register
    # once and drop the other window's money without a mark on the bill; one window on
    # two registers cannot be true of a single measured quantity.
    by_season_pairs: dict[Any, dict[str, set[str]]] = {}
    for window in windows:
        pairs = by_season_pairs.setdefault(window["season"], {})
        pairs.setdefault(window["channel"], set()).add(window["label"])
    for season_label, pairs in by_season_pairs.items():
        for channel, labels in sorted(pairs.items()):
            if len(labels) > 1:
                fe.append(
                    _field_error(
                        "structure.windows",
                        errors.VAL_FORMAT,
                        "rating.tou.register_reused",
                        season=season_label,
                        channel=channel,
                        windows=", ".join(sorted(labels)),
                    )
                )
    for season in seasons:
        if not any(window["season"] == season["label"] for window in windows):
            fe.append(
                _field_error(
                    "structure.windows",
                    errors.VAL_REQUIRED,
                    "rating.tou.season_without_window",
                    season=season["label"],
                )
            )
    return {"seasons": seasons, "windows": windows}


def _validate_structure(
    model: str | None,
    payload: dict[str, Any],
    fe: list[dict[str, Any]],
    *,
    service_code: str | None = None,
) -> dict[str, Any]:
    """One structure per model (BR-RAT-031: one service, one model).

    `service_code` is WHICH SERVICE THIS SCHEDULE PRICES, and it is a keyword
    because only one of the five callers can read it off the payload — a
    create carries `service`, and a draft save, an activation, a correction and
    a new version all read it off the tariff row instead (`CR-130-BRC07`).

    ⚠ **IT IS PASSED BY ALL FIVE ON PURPOSE.** Left to `payload.get("service")`
    the self-reference check below would have been a check that cannot fail on
    four paths out of five — green on every edit, and green precisely where an
    existing schedule is the one being repointed at itself. CLAUDE.md hard-won
    law 7: ask what would make this check pass wrongly.
    """
    raw = payload.get("structure")
    structure: dict[str, Any] = {"tiers": [], "seasons": [], "windows": []}
    notices: list[dict[str, Any]] = []
    if model is None:
        return structure
    if (
        model in (MODEL_TOU, MODEL_DEMAND)
        and service_code
        and not seams.service_bills_from_a_register(service_code)
    ):
        # `DEF-RAT-9015`. Time of use prices on-peak and off-peak READS and
        # demand prices a peak-demand READ, so a service this tenant does not
        # read from a meter (`billing_basis` `share` or `capacity`,
        # BR-TEN-1180) can never supply either: billing refuses every bill on
        # such a schedule, correctly. Saying so here, at the save, is the only
        # place a clerk can still act on it. The answer is the tenant's own
        # declaration through the seam, so a utility that reads its trash or
        # solar from a meter (S8) keeps both methods.
        fe.append(
            _field_error(
                "model", errors.VAL_FORMAT, "rating.schedules.model_needs_meter", model=model
            )
        )
        return structure
    if (
        model == MODEL_PERCENT
        and service_code
        and seams.service_bills_from_a_register(service_code)
    ):
        # `DEF-BIL-9014`, PO 2026-10-02 (decision log, "WATER AT 38% OF
        # ELECTRIC ON TWO WATER METERS IS NOT A VALID CASE"). A share of
        # another service is ONE account-level figure, and billing prices a
        # metered service once PER METER (B5, 2026-09-30) — so a share on a
        # service that has meters is charged once per meter: water at 38% of
        # electric on two water meters billed $1,691.64 against $860.82.
        # The PO's verdict on that case: *"this is not valid case"*; the real
        # case is sewer, which has no meter of its own. So a service the
        # tenant reads from its OWN meter (`billing_basis` `metered`,
        # BR-TEN-1180) is priced from its readings and never as a share. The
        # answer is the tenant's declaration through the seam, so a utility
        # that meters its sewer loses the share and one that does not keeps
        # it. The mirror of `DEF-RAT-9015` above; schedules saved before this
        # guard are not touched by it until they are next saved.
        fe.append(_field_error("model", errors.VAL_FORMAT, "rating.schedules.share_needs_no_meter"))
        return structure
    body = raw if isinstance(raw, dict) else {}
    if raw is not None and not isinstance(raw, dict):
        fe.append(_field_error("structure", errors.VAL_FORMAT, "rating.structure.not_object"))
        return structure

    if model == MODEL_FLAT:
        # BR-RAT-032: flat is stored as ONE 0→∞ tier so the engine has a single
        # execution path.
        if "tiers" in body:
            structure["tiers"] = _validate_tiers(body.get("tiers"), fe)
        else:
            price = _decimal(
                body, "unit_price", fe, required=True, minimum=Decimal("0"), prefix="structure."
            )
            if price is not None:
                structure["tiers"] = [
                    {
                        "seq": 1,
                        "from_qty": Decimal("0"),
                        "to_qty": None,
                        "unit_price": price,
                        "season": None,
                    }
                ]
    elif model == MODEL_TIERED:
        structure["tiers"] = _validate_tiers(body.get("tiers"), fe)
    elif model == MODEL_TOU:
        tou = _validate_tou(body, fe)
        structure["seasons"] = tou["seasons"]
        structure["windows"] = tou["windows"]
    elif model == MODEL_SEASONAL:
        seasons = _validate_seasons(body.get("seasons"), fe)
        structure["seasons"] = seasons
        for index, season in enumerate(seasons):
            prefix = f"structure.seasons[{index}]."
            if season.get("tiers"):
                season["tier_rows"] = _validate_tiers(season["tiers"], fe, prefix=prefix)
                for row in season["tier_rows"]:
                    row["season"] = season["label"]  # season-scoped tier set (r6.7)
            else:
                price = _decimal(
                    season, "unit_price", fe, required=True, minimum=Decimal("0"), prefix=prefix
                )
                season["tier_rows"] = (
                    []
                    if price is None
                    else [
                        {
                            "seq": 1,
                            "from_qty": Decimal("0"),
                            "to_qty": None,
                            "unit_price": price,
                            "season": season["label"],
                        }
                    ]
                )
    elif model == MODEL_CAPACITY:
        capacity = body.get("capacity") if isinstance(body.get("capacity"), dict) else body
        _reject_unknown(
            capacity, ("unit_label", "rate_per_unit", "currency"), fe, prefix="structure.capacity."
        )
        unit_label = _text(
            capacity, "unit_label", fe, required=True, max_length=40, prefix="structure.capacity."
        )  # TENANT-DEFINED free text (BR-RAT-022)
        rate = _decimal(
            capacity,
            "rate_per_unit",
            fe,
            required=True,
            minimum=Decimal("0"),
            prefix="structure.capacity.",
        )
        if unit_label is not None and rate is not None:
            structure["capacity"] = {
                "unit_label": unit_label,
                "rate_per_unit": rate,
                "currency": (capacity.get("currency") or "USD").upper()[:3],
            }
    elif model == MODEL_DEMAND:
        demand = body.get("demand") if isinstance(body.get("demand"), dict) else body
        _reject_unknown(
            demand,
            (
                "energy_rate_per_kwh",
                "demand_rate_per_kw",
                "peak_window_label",
                "peak_window_start",
                "peak_window_end",
                "ratchet_enabled",
                "ratchet_pct",
                "pf_penalty_enabled",
                "pf_penalty_rate_per_kw",
            ),
            fe,
            prefix="structure.demand.",
        )
        energy = _decimal(
            demand,
            "energy_rate_per_kwh",
            fe,
            required=True,
            minimum=Decimal("0"),
            prefix="structure.demand.",
        )
        demand_rate = _decimal(
            demand,
            "demand_rate_per_kw",
            fe,
            required=True,
            minimum=Decimal("0"),
            prefix="structure.demand.",
        )
        peak_start = None
        peak_end = None
        if demand.get("peak_window_start"):
            peak_start = _time_value(demand, "peak_window_start", fe, prefix="structure.demand.")
        if demand.get("peak_window_end"):
            peak_end = _time_value(demand, "peak_window_end", fe, prefix="structure.demand.")
        pf_enabled = _bool(demand, "pf_penalty_enabled")
        if energy is not None and demand_rate is not None:
            structure["demand"] = {
                "energy_rate_per_kwh": energy,
                "demand_rate_per_kw": demand_rate,
                "peak_window_label": _text(
                    demand, "peak_window_label", fe, max_length=60, prefix="structure.demand."
                ),
                "peak_window_start": peak_start,
                "peak_window_end": peak_end,
                "ratchet_enabled": _bool(demand, "ratchet_enabled"),  # r6.2 DEFAULT false
                "ratchet_pct": _decimal(
                    demand, "ratchet_pct", fe, minimum=Decimal("0"), prefix="structure.demand."
                ),
                "pf_penalty_enabled": pf_enabled,
                "pf_penalty_rate_per_kw": _decimal(
                    demand,
                    "pf_penalty_rate_per_kw",
                    fe,
                    minimum=Decimal("0"),
                    prefix="structure.demand.",
                ),
            }
        if pf_enabled:
            # US-RAT-007 TC-8: captured, but the engine may not compute it until
            # the B4 demand addendum ratifies — no silent math.
            notices.append(
                {
                    "code": "rating.demand.pf_penalty_pending_ratification",
                    "br_ref": "BR-RAT-014",
                    "params": {},
                }
            )
    elif model == MODEL_PERCENT:
        percent = _decimal(body, "percent", fe, required=True, prefix="structure.")
        basis_code = _text(body, "basis_service", fe, required=True, prefix="structure.")
        basis = _enabled_service(basis_code, "basis_service", fe, prefix="structure.")
        if percent is not None and percent <= Decimal("0"):
            # US-RAT-007 TC-6: hard error at ≤ 0.
            fe.append(
                _field_error("structure.percent", errors.VAL_RANGE, "rating.percent.not_positive")
            )
        elif (
            percent is not None
            and percent > Decimal("100")
            and not _bool(payload, "confirm_percent_over_100")
        ):
            # US-RAT-007 TC-6: warn-and-confirm above 100 %.
            fe.append(
                _field_error(
                    "structure.percent",
                    errors.VAL_RANGE,
                    "rating.percent.confirm_over_100",
                    percent=str(percent),
                )
            )
        # ── CR-130-BRC07 · A PERCENTAGE OF WHAT — BR-RAT-1030, PO 2026-09-22 ──
        # *"we also need to create 2 option 5age of charges or % of usage"*.
        # REQUIRED on a new or edited percent schedule, because there is no
        # safe default: the same digits mean a RETURN-TO-SEWER FACTOR on one
        # basis and a PRICE RATIO on the other, and reading one as the other
        # produces a well-formed bill for the wrong number.
        chosen_basis = _text(body, "percent_basis", fe, required=True, prefix="structure.")
        if chosen_basis is not None and chosen_basis not in PERCENT_BASES:
            fe.append(
                _field_error(
                    "structure.percent_basis", errors.VAL_UNKNOWN_LOOKUP, "rating.unknown_value"
                )
            )
            chosen_basis = None
        # ⚠ **THE BASIS SERVICE MUST BE ABLE TO SUPPLY THE FIGURE, AND WHAT
        # THAT MEANS DEPENDS ON THE BASIS** — derived, never a named pair (PO,
        # same message: *"dont hard code anything - use logic to derive it so
        # that it is flexible and handle any scenario"*). This is the WRITE
        # half of `selectors.percent_basis_options`, which serves the screen
        # the same answer; both read `seams`, neither names a service.
        if basis is not None and service_code and basis["code"] == service_code:
            fe.append(
                _field_error(
                    "structure.basis_service",
                    errors.VAL_RANGE,
                    "rating.percent.basis_is_itself",
                )
            )
        elif (
            basis is not None
            and chosen_basis == PERCENT_BASIS_USAGE
            and not seams.service_bills_from_a_register(basis["code"])
        ):
            # The derived figure is a QUANTITY in that service's own unit, so a
            # service the utility declares it does not meter has no quantity to
            # take a percentage of (CLAUDE.md hard rule 3). The CHARGE basis
            # asks nothing of the kind: the figure is money, and anything that
            # can put a usage charge on a bill can supply it.
            fe.append(
                _field_error(
                    "structure.basis_service",
                    errors.VAL_RANGE,
                    "rating.percent.basis_meters_nothing",
                    service=basis["code"],
                )
            )

        # ── CR-081 · SEWER HAS A RATE OF ITS OWN FROM 2026-09-08 ────────────
        # The PO re-signed the volume basis under HUMAN-GUIDE §6: sewer bills
        # 90% of the water VOLUME at its own price per unit, where it used to
        # bill 40% of the water MONEY and needed no price at all. The rate is
        # stored the way `flat` stores one — a single 0→∞ `rate_tiers` row
        # (BR-RAT-032) — so there is no new column and only one representation
        # of "one price" in the product.
        #
        # It is **required on a NEW percent schedule** and the requirement is
        # the point: a factor with no rate is half a tariff, and half a tariff
        # bills $0.00 for sewer on every account that carries it. Existing
        # versions are backfilled by `rating/0028_cr081_sewer_volume_basis.py`,
        # never by this path — a draft saved before that migration reaches
        # activation through `_missing_structure`, which now names the rate.
        #
        # ⚠ **AND SINCE 2026-09-22 IT IS REQUIRED ON THE `usage` BASIS AND
        # REFUSED BY NAME ON `charge` (CR-130-BRC07 §3).** A percentage of
        # money needs no price per gallon; a rate accepted there would be a
        # number the tenant states, the screen shows and the engine silently
        # drops — which is the `tiers[0]` discard's shape, one layer up.
        #
        # ⚠ **`tiers` IS THE LADDER, AND IT IS THE SAME FIELD `tiered` USES**
        # (BR-RAT-032: one price is ONE 0→∞ block, several is a ladder). So
        # there is no `rate_shape` flag and nothing new to keep in step — the
        # PO's *"80 X { flat rate or tiered rate }"* is one representation with
        # one block or with several.
        if chosen_basis == PERCENT_BASIS_CHARGE:
            for field in ("unit_price", "tiers"):
                if body.get(field) not in (None, "", [], {}):
                    fe.append(
                        _field_error(
                            f"structure.{field}",
                            errors.VAL_RANGE,
                            "rating.percent.rate_not_on_charge_basis",
                        )
                    )
        elif "tiers" in body:
            structure["tiers"] = _validate_tiers(body.get("tiers"), fe)
        else:
            rate = _decimal(
                body, "unit_price", fe, required=True, minimum=Decimal("0"), prefix="structure."
            )
            if rate is not None:
                structure["tiers"] = [
                    {
                        "seq": 1,
                        "from_qty": Decimal("0"),
                        "to_qty": None,
                        "unit_price": rate,
                        "season": None,
                    }
                ]
        if percent is not None and basis is not None:
            structure["percent"] = percent
            structure["basis_service_id"] = basis["id"]
        if chosen_basis is not None:
            structure["percent_basis"] = chosen_basis
    structure["notices"] = notices
    return structure


def _write_version(
    tariff: models.Tariff,
    cleaned: dict[str, Any],
    structure: dict[str, Any],
    *,
    actor: Any = None,
) -> models.TariffVersion:
    """One version row + its structure children. Append-only by law: nothing
    here ever rewrites an existing version (BR-RAT-037).

    `actor` stamps DEF-367's `submitted_by`. It is a keyword with a default so
    that a caller which forgets it writes NULL — *"nobody filed this"* — rather
    than the wrong person; every caller in this module passes it.
    """
    tenant_id = _tenant_id()
    version = models.TariffVersion.objects.create(
        tenant_id=tenant_id,
        tariff=tariff,
        model=cleaned["model"],
        base_charge=cleaned["base_charge"],
        # `CR-120-BRC06` · `BR-RAT-1025` — the NAMED base charge code, carried
        # onto the version like every other version fact. `.get` and not `[]`
        # on purpose: `correct_rate_schedule_version` builds its `cleaned` from
        # the row it is restating, and a KeyError there would turn a correction
        # into a 500 on a money path.
        base_charge_code_id=cleaned.get("base_charge_code_id"),
        minimum_bill=cleaned["minimum_bill"],
        currency=cleaned["currency"],
        uom=cleaned["uom"],
        percent=structure.get("percent"),
        basis_service_id=structure.get("basis_service_id"),
        # `CR-130-BRC07` · `BR-RAT-1030` — A PERCENTAGE OF WHAT. `or` the
        # default rather than a bare `.get`: every non-percent model writes NO
        # structure key at all, and the column is NOT NULL, so a None here
        # would refuse a flat schedule at the database. It is the same value
        # `rating/0043` wrote onto every row that predates the column, and on a
        # percent schedule `_validate_structure` has already REQUIRED the
        # tenant to state one — so this fallback is never the answer to a
        # percent question.
        percent_basis=structure.get("percent_basis") or PERCENT_BASIS_USAGE,
        effective_from=cleaned["effective_from"],
        effective_to=cleaned["effective_to"],
        approved_by_id=cleaned.get("approved_by_id"),
        regulator_ref=cleaned["regulator_ref"],
        # BR-RAT-082 — captured with the VERSION, not with the schedule, because
        # a rate case is filed against one version: *"a rate case becomes a
        # future-dated draft sitting alongside the active version"* (CR-013
        # part 1). Last year's docket stays on last year's version forever.
        filing_authority=cleaned.get("filing_authority"),
        filed_on=cleaned.get("filed_on"),
        regulator_approved_on=cleaned.get("regulator_approved_on"),
        regulator_approver=cleaned.get("regulator_approver"),
        # DEF-369 — the label a docket references, as typed. NULL when the
        # utility did not state one; the screen falls back to a DERIVED ordinal
        # and says so rather than promoting a position to an identifier.
        version_label=cleaned.get("version_label"),
        # DEF-367 — WHO FILED IT, stamped from the acting user rather than
        # typed, so it cannot be wrong. `approved_by` above stays the separate,
        # optional internal fact about a different person (BR-RAT-083).
        submitted_by_id=_actor_user_id(actor),
        # DEF-280 — BR-RAT-037's reason, kept ON the version it describes. The
        # `rate_change_log` row still carries its own copy; this is the one a
        # filings table can read.
        change_reason=cleaned.get("change_reason"),
        notify_customers=cleaned["notify_customers"],
        publish_public=cleaned["publish_public"],
    )
    for size_row in cleaned.get("size_rows") or []:
        # DEF-360. A row with `minimum_bill=None` is written, not skipped: it
        # says this size IS served and has no floor, which is not the same fact
        # as having no row at all.
        models.RateSizeRow.objects.create(
            tenant_id=tenant_id,
            tariff_version=version,
            size_class=size_row["size_class"],
            minimum_bill=size_row["minimum_bill"],
            currency=cleaned["currency"],
        )
    season_rows: dict[str, models.RateSeason] = {}
    for season in structure.get("seasons") or []:
        season_rows[season["label"]] = models.RateSeason.objects.create(
            tenant_id=tenant_id,
            tariff_version=version,
            label=season["label"],
            start_month=season["start_month"],
            start_day=season["start_day"],
            end_month=season["end_month"],
            end_day=season["end_day"],
        )
    seq = 0
    tier_sets = list(structure.get("tiers") or [])
    for season in structure.get("seasons") or []:
        tier_sets.extend(season.get("tier_rows") or [])
    for tier in tier_sets:
        seq += 1
        models.RateTier.objects.create(
            tenant_id=tenant_id,
            tariff_version=version,
            season=season_rows.get(tier.get("season")) if tier.get("season") else None,
            # DEF-433. NULL is "every size" and is the fallback group; a value
            # here is the exception r10's 2" water row needs. Stored as given —
            # see `_validate_tiers` for why it is not checked against Settings.
            size_class=tier.get("size_class"),
            seq=seq,  # the base UNIQUE is (tariff_version, seq) — kept verbatim (r6.7 wrinkle)
            from_qty=tier["from_qty"],
            to_qty=tier["to_qty"],
            unit_price=tier["unit_price"],
        )
    for window in structure.get("windows") or []:
        models.TimeOfUseWindow.objects.create(
            tenant_id=tenant_id,
            tariff_version=version,
            season=season_rows.get(window["season"]) if window.get("season") else None,
            label=window["label"],
            day_type=window["day_type"],
            start_time=window["start_time"],
            end_time=window["end_time"],
            unit_price=window["unit_price"],
            # BR-RAT-067 — stated by the utility on S11, stored with the VERSION so a
            # reprice seven years out reads the mapping in force then (BR-RAT-007).
            channel=window["channel"],
        )
    capacity = structure.get("capacity")
    if capacity:
        models.CapacityRate.objects.create(tenant_id=tenant_id, tariff_version=version, **capacity)
    demand = structure.get("demand")
    if demand:
        models.DemandRateConfig.objects.create(
            tenant_id=tenant_id, tariff_version=version, **demand
        )
    return version


def _discard_draft(draft: models.TariffVersion) -> None:
    """Drop a draft version and its structure children so the replacement can be
    written. NOT a BR-RAT-037 append-only violation: that law binds versions
    that have been IN FORCE; a draft (no effective_from) never priced anything.
    Children go first — tiers/windows PROTECT their season rows."""
    tenant_id = _tenant_id()
    for child in (
        models.RateTier,
        models.TimeOfUseWindow,
        models.CapacityRate,
        models.DemandRateConfig,
        # DEF-360 — a re-saved draft replaces its size rows with the posted set.
        # Omitted from this tuple, the old rows would survive the rewrite and a
        # size the user DELETED would come back at its old minimum bill.
        models.RateSizeRow,
        models.RateSeason,
    ):
        child.objects.filter(tenant_id=tenant_id, tariff_version=draft).delete()
    draft.delete()


def _missing_structure(version: models.TariffVersion) -> str | None:
    """BR-RAT-031 "activation requires a COMPLETE structure": complete means the
    rows `_write_version` writes for this model actually exist on the row being
    activated. Returns the missing part, or None when the draft is complete."""
    tenant_id = _tenant_id()

    def _has(child: Any) -> bool:
        return child.objects.filter(tenant_id=tenant_id, tariff_version=version).exists()

    if version.model in (MODEL_FLAT, MODEL_TIERED):
        return None if _has(models.RateTier) else "tiers"
    if version.model == MODEL_SEASONAL:
        if not _has(models.RateSeason):
            return "seasons"
        return None if _has(models.RateTier) else "tiers"
    if version.model == MODEL_TOU:
        return None if _has(models.TimeOfUseWindow) else "windows"
    if version.model == MODEL_CAPACITY:
        return None if _has(models.CapacityRate) else "capacity"
    if version.model == MODEL_DEMAND:
        return None if _has(models.DemandRateConfig) else "demand"
    if version.model == MODEL_PERCENT:
        if version.percent is None or version.basis_service_id is None:
            return "percent"
        if version.percent_basis == PERCENT_BASIS_CHARGE:
            # `CR-130-BRC07` — a percentage of MONEY is COMPLETE with a factor
            # and a basis service. It has no rate of its own by design, so
            # demanding one here would make every charge-basis schedule
            # permanently unactivatable — a completeness gate asking for
            # something the validator refuses to accept.
            return None
        # CR-081 — and the ORDER matters: a version missing both reports the
        # percent first, because a rate with no basis to apply it to is the less
        # useful half to be told about.
        return None if _has(models.RateTier) else "rate"
    return None


def _require_complete_structure(version: models.TariffVersion) -> None:
    missing = _missing_structure(version)
    if missing is not None:
        # US-RAT-005 §6: a draft with an incomplete structure never activates.
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-RAT-031",
            message_key="rating.schedules.incomplete_structure",
            params={"missing": missing, "model": version.model},
        )


#: `rating/0047`'s exclusion constraint, by name — the one `_check_windows_now`
#: forces to be checked at the point a save can still answer by name.
NO_OVERLAP_CONSTRAINT = "ex_tariff_versions_no_overlap"

#: PostgreSQL's SQLSTATE for an exclusion-constraint violation.
EXCLUSION_VIOLATION = "23P01"


def _lock_schedule(tariff_id: Any) -> models.Tariff:
    """`CR-157-BRC10` wave A · LOCK THE SCHEDULE ROW, THEN ITS VERSIONS — IN
    THAT ORDER, IN EVERY PATH THAT WRITES A SCHEDULE'S VERSIONS.

    🔒 HUMAN-REVIEW-PENDING — this decides which of two simultaneous saves
    lands and which is refused, on the rows that price a bill. Row in
    `12-governance/09-human-review-ledger.md` (`CR-157-BRC10`).

    ⚠ **WHY THIS EXISTS (`DEF-RAT-8750`).** Every save path read the
    schedule and its versions with plain SELECTs. Two clerks saving the same
    schedule at the same moment therefore both read the SAME world, both
    passed `_guard_window`, both wrote, and the second learned it had lost
    only at COMMIT, from `rating/0047`'s DEFERRED exclusion constraint — a
    raw `IntegrityError` and a server error on screen, where `BR-RAT-037`
    promises the named refusal *"Versions may not overlap"*. Worse cases
    sat beside it: two activations of one saved draft both found no live
    version, and the second could DELETE the row the first had just
    activated (`_discard_draft` deletes by primary key).

    **WHAT IT DOES.** `SELECT … FOR UPDATE` on the `tariffs` row, then on
    every `tariff_versions` row of it in id order. The second clerk WAITS on
    the first lock until the first save commits, and only then reads — so
    every guard in the save path (`_guard_window`, *already activated*,
    *already corrected*) sees the first clerk's rows and answers BY NAME.
    Nothing is half-written: the refused save never wrote a row.

    **WHY THIS ORDER, EVERYWHERE.** A deadlock needs two transactions taking
    two locks in opposite orders. Every writer here takes the SCHEDULE first
    and its versions second, and the bulk rate change
    (`apply_rate_change_batch`) takes all its schedules in ascending id
    before any version — so no two writers can each hold what the other
    wants.

    **NOT A READ PATH.** Billing never calls this; a bill run reads through
    `selectors.in_force_version` with plain SELECTs and is never blocked by
    a clerk's save (PostgreSQL readers do not wait on row locks).

    `tariff_or_404` first, so a malformed or foreign id still answers 404 in
    the shape every caller already expects (hard rule 1 — tenant-scoped).
    """
    found = selectors.tariff_or_404(tariff_id)
    tariff = models.Tariff.objects.select_for_update().get(tenant_id=_tenant_id(), pk=found.pk)
    list(
        models.TariffVersion.objects.select_for_update()
        .filter(tenant_id=_tenant_id(), tariff_id=tariff.pk)
        .order_by("id")
        .values_list("id", flat=True)
    )
    return tariff


def _sqlstate(exc: BaseException) -> str | None:
    """The driver's SQLSTATE, walked down the cause chain (hard-won law 14:
    *"`exc.__cause__` on a caught Django `IntegrityError` is ANOTHER Django
    `IntegrityError`; the driver's exception with the real SQLSTATE is two
    or three hops down"*)."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        code = getattr(current, "sqlstate", None) or getattr(current, "pgcode", None)
        if code:
            return str(code)
        current = current.__cause__ or current.__context__
    return None


def _check_windows_now(tariff: models.Tariff, effective_from: date | None) -> None:
    """`CR-157-BRC10` · ASK `rating/0047` NOW, WHILE THE SAVE CAN STILL ANSWER
    BY NAME — NOT AT COMMIT, WHERE IT CAN ONLY ANSWER WITH A RAW ERROR.

    🔒 HUMAN-REVIEW-PENDING (the same ledger row as `_lock_schedule`).

    The constraint is `DEFERRABLE INITIALLY DEFERRED` for
    `correct_rate_schedule_version`'s sake (the correction row is written
    before the original is stamped superseded), so left alone it is checked
    at COMMIT — after this function has returned and nothing can turn the
    failure into `rating.schedules.window_overlap`. `SET CONSTRAINTS …
    IMMEDIATE` checks every pending row at this statement; it is then set
    back to DEFERRED so a later write in the same transaction keeps the
    ordering freedom the correction depends on.

    ⚠ **A SAVEPOINT IS THE ONLY WAY THIS CAN CATCH, NOT THE TIDY ONE**
    (hard-won law 14). On PostgreSQL a failed statement aborts the whole
    transaction; the nested `atomic()` lets us read the failure and raise a
    named refusal, which then rolls the WHOLE save back — nothing of the
    refused save survives.

    With `_lock_schedule` in place this is the BACKSTOP: under the lock the
    second of two saves sees the first's rows and `_guard_window` refuses it
    before writing. It still earns its place, because any writer that
    reaches `tariff_versions` without the lock (an operator's command, a
    future path) would otherwise surface as a 500 again.

    SQLite has no exclusion constraint and no `SET CONSTRAINTS`, so it does
    nothing there — honestly, not vacuously: there is nothing to check.
    """
    from django.db import IntegrityError, connection

    if connection.vendor != "postgresql":
        return
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"SET CONSTRAINTS {NO_OVERLAP_CONSTRAINT} IMMEDIATE")
    except IntegrityError as exc:
        if _sqlstate(exc) != EXCLUSION_VIOLATION:
            raise
        current = selectors.in_force_version(tariff, effective_from) if effective_from else None
        current = current or selectors.latest_version(tariff)
        raise errors.BizError(
            errors.BIZ_WINDOW,
            br_ref="BR-RAT-037",
            message_key="rating.schedules.window_overlap",
            params={
                "effective_from": effective_from.isoformat() if effective_from else "",
                "current_from": (
                    current.effective_from.isoformat()
                    if current is not None and current.effective_from
                    else ""
                ),
            },
        ) from exc
    with connection.cursor() as cursor:
        cursor.execute(f"SET CONSTRAINTS {NO_OVERLAP_CONSTRAINT} DEFERRED")


@require_role(SYSTEM_ADMIN)
def create_rate_schedule(actor: Any, payload: Any) -> dict[str, Any]:
    """S11 commit. A schedule prices exactly ONE service with ONE model and its
    name is internal (BR-RAT-031). With `effective_from` + a complete structure
    the first version is written and the schedule is ACTIVE — a System Admin
    publishes directly; there is no in-system approval hold (BR-RAT-031
    as-modified).

    WITHOUT `effective_from` the wizard's "Save draft & exit" lands a DRAFT
    version (effective_from NULL) carrying whatever structure was entered, so
    reopening reloads it (BR-RAT-031 save-draft resumable). A draft may be
    incomplete — completeness is activation's gate, not the draft's. With no
    `model` either, only the identity row is stored.

    ── `DEF-RAT-8001` · DOES THIS PATH CLOSE AN OPEN WINDOW? **NO, AND IT MUST
    NOT.** ──────────────────────────────────────────────────────────────────
    One of the six writers of `tariff_versions`, audited together when the
    B2 §2 no-overlap constraint was finally built (`rating/0047`). This one
    creates the SCHEDULE and its FIRST version in the same call, so there is no
    earlier version of this tariff in existence — `tariff` is minted three
    lines below `transaction.atomic()`. A close here would have nothing to
    close, and a helper call written "for symmetry" would read as though it
    might.
    """
    payload = _require_dict(payload)
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, SCHEDULE_FIELDS, fe)
    identity = _validate_schedule_identity(payload, fe, partial=False)
    is_draft = payload.get("effective_from") in (None, "")
    wants_version = not is_draft or "structure" in payload or "model" in payload
    version_fields: dict[str, Any] = {}
    structure: dict[str, Any] = {}
    if wants_version:
        version_fields = _validate_version_fields(payload, fe, require_effective_from=not is_draft)
        if not is_draft or "structure" in payload:
            structure = _validate_structure(
                version_fields.get("model"),
                payload,
                fe,
                service_code=identity.get("service_code"),
            )
    _refuse(fe)

    with transaction.atomic():
        tariff = models.Tariff.objects.create(
            tenant_id=_tenant_id(),
            name=identity["name"],
            service_id=identity["service_id"],
            account_type_id=identity.get("account_type_id"),
        )
        version = None
        if wants_version:
            # §A3/BR-RAT-088: refuse BEFORE the version exists, not after — a
            # refusal that fires post-write leaves a row a human must clean up.
            if version_fields.get("effective_from") is not None:
                _guard_base_charge_code(tariff)
                # `CR-120-BRC06` · `BR-RAT-1025` — and the NAMED code has to be
                # one R4 could actually have selected, or step 5 shows a figure
                # the bill will not use. Silent when nothing is bound, which is
                # every schedule that exists today.
                version_fields["base_charge_code_id"] = _guard_bound_base_charge_code(
                    tariff, version_fields.get("base_charge_code_id")
                )
            version = _write_version(tariff, version_fields, structure, actor=actor)
        after = _json_safe(selectors.schedule_card(tariff))
        _audit(actor, "tariff.created", "tariff", tariff.id, after=after)
        if version is not None:
            _audit(
                actor,
                "tariff.draft_saved" if is_draft else "tariff.activated",
                "tariff_version",
                version.id,
                after=_json_safe(selectors.version_row(version)),
            )
    result = selectors.schedule_detail(tariff.id)
    result["notices"] = _schedule_notices(tariff, structure)
    return result


def _guard_base_charge_code(tariff: models.Tariff) -> None:
    """§A3 · BR-RAT-088 — a schedule may not activate for a service whose base
    charge code is missing, ONCE THIS TENANT PRICES BASES THAT WAY.

    §A3 moved this from part 5 step 4's *"flags a bound schedule with no base
    charge for that service"* to a gate, and the reason is arithmetic: with the
    charge code owning the base, a service with no base code bills **no base at
    all**. Every line is individually correct and the total is short by the
    base — the same silent shape as the double-base the ruling forbids, in the
    other direction.

    ⚠ **THE QUALIFIER IS LOAD-BEARING: *"where the plan expects one"*.** A gate
    that fired unconditionally would refuse EVERY activation the day it shipped,
    because `Charge.is_base` defaults False and no tenant has declared one yet.
    So adoption is inferred from the tenant's own data: a tenant with **no**
    `is_base` code anywhere has not moved to this model and is left exactly as
    it was; a tenant with **some** has, and a service missing its own is a
    configuration error a human must see.

    That makes the gate self-activating per tenant and needs no follow-up commit
    to "turn on" — which is the failure mode CLAUDE.md law 1 warns about, where
    a comment promises a guarantee that a later lane never delivers.

    ⚠ **AND THE QUALIFIER IS NOW HALF THE CONDITION, NOT ALL OF IT — `DEF-2923`,
    2026-09-01.** Everything above is still true **while no rule of the ruled
    chain is pricing bases on this deployment**. The day R4 is served the
    reasoning inverts: *"a tenant with no `is_base` code has not moved to this
    model and is left exactly as it was"* stops being available, because with
    R4 on there is no old way left for the chain to price a base from. Such a
    tenant does not carry on as it was — it has **every account of that service
    refused on its next bill run**, by name, with no fallback (`BR-BIL-872`).
    That was measured, not predicted: flipping the switch turned seven cases of
    `test_br_bil_870_resolution_switch.py` red on exactly this.

    So the condition is now *"this tenant has adopted declared base codes **OR**
    the chain states the base"*, and where the chain states it the gate fires
    for **every** tenant. **The refusal moves from billing day to schedule
    activation** — a settings screen, with the cure in its own sentence, instead
    of an exception tab on the day the money is due.

    Both halves are load-bearing and both are proved red in
    `tests/test_def2923_base_code_gate_follows_the_switch.py`: with the pair off
    the gate must stay silent for an unadopted tenant (TC3), and with the pair
    on it must fire (TC1/TC2).
    """
    service_id = tariff.service_id
    if service_id is None:
        return
    live = models.Charge.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), deleted_at__isnull=True
    )
    if not live.filter(is_base=True).exists() and not _the_chain_states_the_base():
        # This tenant has not adopted declared base codes AND no rule of the
        # ruled chain is pricing bases here, so nothing is enforced.
        #
        # ⚠ **THE SECOND HALF OF THAT CONDITION IS NEW AND IT CLOSES `DEF-2923`.**
        # The self-activating qualifier above was right while nothing was
        # switched on: a tenant with no base code anywhere was simply pricing the
        # old way. **The day R4 is served by the chain it stops being right** —
        # the charge code becomes the ONLY source of a base amount, so that same
        # tenant has every account of every service REFUSED on its next bill run,
        # by name, with no fallback (`BR-BIL-872`). Measured: flipping the switch
        # turned seven cases of `test_br_bil_870_resolution_switch.py` red on
        # exactly this, every one of them a real bill that would have stopped.
        #
        # So where the chain states the base, the gate fires for EVERY tenant,
        # and the refusal moves from BILLING DAY to the moment somebody activates
        # a schedule — a settings screen, with the fix in the sentence, instead of
        # an exception tab on the day the money is due.
        return
    if live.filter(is_base=True, service_id=service_id).exists():
        return
    # WHY this refuses rather than warns, kept HERE rather than in the message:
    # a schedule activated with no base charge code bills every usage line
    # correctly and the total short by the whole base — the failure §A3 priced
    # at $23,069.50 a month across 1,247 connections, invisible because both
    # rows are individually right. G33 caps a refusal at two sentences, so the
    # copy says what happened and what to do; the rationale lives here.
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-RAT-088",
        message_key="rating.schedules.no_base_charge_code",
        params={"service": tariff.service.code if tariff.service_id else ""},
    )


#: `DEF-RAT-9797` — set only by a caller that TYPES it (law 3): the sample-data
#: and demo seeders, whose every-class schedules bill a residential and a
#: commercial base code by the account's class and so cannot name ONE without
#: changing what a seeded customer pays. Nothing on a request path sets it.
_UNNAMED_BASE_ALLOWED: ContextVar[bool] = ContextVar("rating_unnamed_base_allowed", default=False)


@contextmanager
def seeding_schedules_without_a_named_base() -> Iterator[None]:
    """Seeders only: activate a schedule naming no base code, as every schedule
    did before PO ruling 2026-10-06 (`DEF-RAT-9797`). Such a schedule is listed
    for a System Admin to choose (`schedule_reads.schedules_to_name_a_base`)."""
    token = _UNNAMED_BASE_ALLOWED.set(True)
    try:
        yield
    finally:
        _UNNAMED_BASE_ALLOWED.reset(token)


def _require_a_named_base_code(tariff: models.Tariff) -> Any:
    """🔒 HUMAN-REVIEW-PENDING — `DEF-RAT-9797`, PO ruling 2026-10-06: a rate
    schedule names EXACTLY ONE base charge code (*"base charges - rate schedule
    -> plan - so base charges will be atatched to rate schedule"*).

    Asked at ACTIVATION (a version with a start date — a draft is half-built by
    `BR-RAT-031`'s design) when the version names no code. The candidates are
    this service's live base codes whose class scope admits the schedule's
    class (`_code_admits_class`, the chain's own test):

      * **none** → None; `_guard_base_charge_code` above decides, unchanged;
      * **exactly one** → THAT code is written onto the version. Nothing is
        guessed: it is the only code the bill could ever have read for this
        schedule, and naming it is what takes the schedule off the pooled
        fallback for good (worked: water with only W-ALL $8.00 → the version
        names W-ALL, and the residential bill is $8.00 either way);
      * **two or more** → REFUSED, *"Choose a base charge code."* — the
        configuration the ruling exists for (W-ALL $8.00 beside W-COM $15.00
        on an every-class schedule: which one the bill reads is a person's
        choice, never the catalogue's order).

    ⚠ **WHAT IS DELIBERATELY NOT DONE: nothing already stored is touched.** A
    live schedule that names none keeps billing exactly as it did — the pooled,
    class-narrowed code (`selectors.base_charge_from_charge_code` with no
    `named_code`) — until somebody saves a version of it; no migration picks one.
    ⚠ **THE DASHED HALF OF THAT SENTENCE IS SUPERSEDED 2026-10-06
    (`DEF-RAT-9832`, PO ruling: *"if it is not provided then you will take it
    zeo ; but you cannot take W-COM because it is availabel in charge
    coede"*).** Nothing stored is touched and nothing is chosen, still — but a
    live schedule naming none now bills a `$0.00` base with the warning, for
    every class, until a System Admin names its code. There is no pool.
    """
    if tariff.service_id is None:
        return None
    candidates = [
        code
        for code in models.Charge.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            deleted_at__isnull=True,
            is_base=True,
            service_id=tariff.service_id,
        ).order_by("code", "id")
        if _code_admits_class(code, tariff.account_type_id)
    ]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0].id
    if _UNNAMED_BASE_ALLOWED.get():
        return None
    raise errors.ValidationError(
        errors.VAL_REQUIRED,
        message_key="rating.schedules.base_charge_code_required",
        br_ref="BR-RAT-1025",
        field_errors=[
            _field_error(
                "base_charge_code", errors.VAL_REQUIRED, "rating.schedules.base_charge_code_required"
            )
        ],
    )


def _guard_bound_base_charge_code(tariff: models.Tariff, code_id: Any) -> Any:
    """`CR-120-BRC06` · `BR-RAT-1025` — a schedule may not ACTIVATE naming a
    base charge code that could not price the service it names.

    ⚠ **THIS IS THE SAFETY NET FOR THE WHOLE RULING, AND WHAT IT CATCHES IS THE
    SCREEN AND THE BILL DISAGREEING.** `BR-RAT-1025` lets the schedule NAME its
    base code. Step 1 shows the code, step 5 shows the code and its figure, and
    `resolution.resolve_base_charge` bills whatever that code is worth. **If the
    named code is not one R4 could ever have selected for this service, the
    screen is showing a figure the bill will not use** — and that is
    `BR-RAT-088`'s own failure shape in the other direction: *"both rows are
    individually correct and only the rule makes the total wrong"*, priced at
    **$23,069.50 a month across 1,247 connections** in §A3.

    **FOUR CONDITIONS, and each names a fact somebody can go and change:**

      1. the code still EXISTS and is not deleted;
      2. it is ticked `is_base` — `charges.is_base` is what DECLARES a base and
         nothing else does (never the `BASE-` prefix, `BR-RAT-088`: matching the
         string *"breaks the moment a tenant names theirs `SERVICE-CHG`, and it
         breaks silently"*);
      3. its service is THIS schedule's service, or it is account-level
         (`service_id IS NULL`), which is the spec's *"Any"* and is exactly what
         `resolution.resolve_charge_codes` already admits;
      4. its customer-class scope admits this schedule's class. A code scoped to
         Residential on a Commercial schedule would resolve for no account the
         schedule prices, so the base it displays is a base nobody is billed.

    ⚠ **CONDITION 4 IS ONE-SIDED ON PURPOSE.** A schedule with NO class prices
    every class (`_validate_schedule_identity` treats blank as an answer, not an
    unfinished form), so a class-scoped code under it is legitimate — some of
    its accounts read that code and the rest read another. Refusing there would
    stop a real configuration. What is refused is the case where the code's
    scope and the schedule's class are BOTH stated and they do not intersect,
    which no account can satisfy.

    ⚠ **IT RUNS AT ACTIVATION AND NOT AT SAVE, AND NOT AT BILLING TIME.** A
    draft is half-built by `BR-RAT-031`'s design, and all four facts above live
    on the CHARGE CODE, where somebody may change them after the binding is
    written. `DEF-2923` settled where this kind of refusal belongs one column
    across: *"the refusal moves from billing day to schedule activation — a
    settings screen, with the cure in its own sentence, instead of an exception
    tab on the day the money is due."*

    ⚠ **IT IS SILENT WHEN NOTHING IS BOUND**, which is every schedule that
    exists today. `_guard_base_charge_code` above is the gate for THAT world and
    is untouched; this one only has an opinion about a binding somebody made.

    ⚠ **AND IT DELIBERATELY DOES NOT ASK WHETHER THE CODE RIDES AN ORDINARY
    PERIODIC BILL, WHICH IS THE FIFTH CONDITION A READER WILL LOOK FOR.**
    `charges.charge_type` and `charges.auto_apply` decide whether a NAMED code
    lands on a bill — naming it never does (`BR-RAT-117`, PO 2026-08-22,
    *"ruccuring and Autom apply land on bill"*) — and that rule is untouched
    here. **It simply does not reach the base**, because `resolution
    .rides_a_periodic_bill` returns True for `is_base` BEFORE it reads either
    flag: `BR-RAT-088` makes `is_base` decisive for the base, and gating it
    would take the seeded tenant's `$8.00` residential water, `$15.00`
    commercial water and `$18.00` trash bases to **`$0.00`** — `DEF-154`'s
    exact shape.

    So adding that condition here would be a check that can never fail, since
    condition 2 above already requires `is_base` and `is_base` short-circuits
    the flags. **A guard whose fifth arm is unreachable is law 7's *incapable
    of failing* shape**, and it would also read as this rule claiming authority
    over a question that belongs to the charge code. It is left out on purpose,
    and this paragraph is here so nobody adds it back as an oversight.
    """
    if code_id is None:
        # `DEF-RAT-9797` — returns the ONE code that can serve this schedule,
        # or refuses when there are several; None when the service has none.
        return _require_a_named_base_code(tariff)
    code = (
        models.Charge.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), pk=code_id, deleted_at__isnull=True
        )
        .select_related("service")
        .first()
    )
    params = {"service": tariff.service.code if tariff.service_id else ""}
    if code is None:
        # Condition 1. `PROTECT` on the FK means this is hard to reach from a
        # delete — which is why it is kept: it is reachable from a code that was
        # SOFT-deleted (`deleted_at`), and a soft delete leaves the row for the
        # FK and takes it away from everything that reads.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-RAT-1025",
            message_key="rating.schedules.bound_base_charge_code_gone",
            params=params,
        )
    params["code"] = code.code
    if not code.is_base:
        # Condition 2.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-RAT-1025",
            message_key="rating.schedules.bound_base_charge_code_not_base",
            params=params,
        )
    if code.service_id is not None and code.service_id != tariff.service_id:
        # Condition 3.
        params["code_service"] = code.service.code
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-RAT-1025",
            message_key="rating.schedules.bound_base_charge_code_other_service",
            params=params,
        )
    if not _code_admits_class(code, tariff.account_type_id):
        # Condition 4.
        params["code_classes"] = ", ".join(
            str(value) for value in (code.applies_to_customer_classes or [])
        )
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-RAT-1025",
            message_key="rating.schedules.bound_base_charge_code_other_class",
            params=params,
        )
    return code_id


def _code_admits_class(code: models.Charge, account_type_id: Any) -> bool:
    """Whether a charge code's customer-class scope admits this schedule's class.

    **IT IS THE CHAIN'S OWN TEST, RE-ASKED, AND NOT A SECOND OPINION ABOUT IT.**
    `resolution.resolve_charge_codes` narrows with `if code.customer_classes and
    account.customer_class not in code.customer_classes: continue`, and
    `PlanWizard.candidateChargeCodes` takes the identical reading on screen. So
    an EMPTY scope admits every class here too. A second reading of an empty
    list is how one signed rule starts being answered two ways, and the whole
    point of this gate is that the screen and the bill agree.

    **TWO ABSENCES, BOTH PERMISSIVE, AND EACH FOR ITS OWN REASON:**

      · the CODE states no classes  -> it reaches every class. The chain's own
        `if code.customer_classes and ...`, verbatim.
      · the SCHEDULE states no class -> it prices every class
        (`_validate_schedule_identity` treats blank as an answer rather than an
        unfinished form, and `RateScheduleWizard` says so on the field). A
        class-scoped code under a class-less schedule is then LEGITIMATE: some
        of its accounts read that code and the rest read another, which is
        exactly what a utility with one schedule and two prices does.

    What is refused is only the case where BOTH are stated and they do not
    intersect — a binding no account the schedule prices could ever satisfy.

    ⚠ **THE HOP THROUGH A CODE STRING IS DELIBERATE.** `tariffs.account_type_id`
    is a uuid and `charges.applies_to_customer_classes` is a JSON list of code
    strings; `seams.account_type_code_by_id` is the one place that hop is made,
    for the reason `ChargeCodeAmount.customer_class` already records — the
    resolver narrows by CODE, so the gate asks in the resolver's vocabulary.
    """
    classes = [str(value) for value in (code.applies_to_customer_classes or [])]
    if not classes:
        return True
    if account_type_id is None:
        return True
    schedule_class = seams.account_type_code_by_id(account_type_id)
    if schedule_class is None:
        # The class row is gone or unreadable. Permissive on purpose: this gate
        # exists to catch a binding that CANNOT bill, and "we could not look the
        # class up" is not evidence of that. Refusing here would block an
        # activation over a fact this function failed to read.
        return True
    return schedule_class in classes


def _the_chain_states_the_base() -> bool:
    """Is the ruled chain's base-charge rule serving real bills on this deployment?

    `DEF-2923`. Asked so `_guard_base_charge_code` can stop being optional at the
    moment it stops being safe to be optional — see the comment at its call site.

    ⚠ **RATING ASKS BILLING A QUESTION ABOUT A DEPLOYMENT SETTING, NOT ABOUT ITS
    DATA.** B1 forbids reaching into another module's TABLES; this reads no table
    and issues no query. `steps_served_by_chain()` parses one Django setting and
    validates it, and it re-reads that setting on every call by design, so the
    answer here is never a stale import-time snapshot — which matters, because a
    deployment turning the pair off must have this gate relax again without a
    release. Imported locally to keep the module import graph unchanged.
    """
    from apps.billing import resolution_switch

    return "R4" in resolution_switch.steps_served_by_chain()


def _schedule_notices(tariff: models.Tariff, structure: dict[str, Any]) -> list[dict[str, Any]]:
    """Non-blocking notices the wizard renders (BR-RAT-038 UoM gate warning,
    BR-RAT-014 PF-penalty pending ratification)."""
    notices = list(structure.get("notices") or [])
    # DEF-433 / DEF-484 — SAY IT AT SAVE TIME, not only in a docstring. A
    # per-size tier ladder is stored and served correctly and does NOT reach a
    # bill yet: `selectors.pricing_inputs` takes a `size_class` and falls back to
    # the "every size" group, and `apps/billing/gather.py` (another module) calls
    # it without one. So a 2" connection bills the base ladder — `3.20 / 4.80 /
    # 7.20` where the utility typed `3.45 / 5.10 / 7.70`, which on 10 / 20 / 5
    # units of usage is $220.00 against $232.00, twelve dollars a month short and
    # every line individually correct. A silent version of that is precisely what
    # CLAUDE.md means by a guess becoming a production error, so the person who
    # typed the override is told the moment they save it.
    if any(tier.get("size_class") for tier in structure.get("tiers") or []):
        notices.append(
            {
                "code": "rating.tiers.size_override_not_billed",
                "br_ref": "BR-RAT-032",
                # NO PARAMS, and specifically no defect id: `params` is
                # interpolated into text a utility clerk reads, and DEF-319 is
                # the 219 strings that once put engineering references on a
                # user's screen. The id belongs in this comment.
                "params": {},
            }
        )
    gate = selectors.uom_gate(tariff)
    if not gate["satisfied"]:
        # US-RAT-005 TC-7: warn now, rating blocked later — never a silent
        # conversion.
        #
        # ⚠ **THE `billed_uom` PARAM IS THE EFFECTIVE UNIT, NOT THE COLUMN
        # (2026-09-02, the PO's schedule-vs-meter ruling).** `tenant_services
        # .billed_uom` is NULL on every provisioned tenant and NULL MEANS *the
        # register's own unit is what is billed*, so passing the raw column here
        # would print a sentence with a blank in it — *"the service is billed in
        # ''"* — for the one case this notice now exists to catch. `uom_gate`
        # resolves the effective unit and names it `priced_against`; that is the
        # unit a clerk has to reconcile against and the one the copy must show.
        notices.append(
            {
                "code": "rating.uom.mismatch_no_factor",
                "br_ref": "BR-RAT-038",
                "params": {
                    "schedule_uom": gate["schedule_uom"],
                    "billed_uom": gate["priced_against"],
                },
            }
        )
    return notices


DRAFT_FIELDS: tuple[str, ...] = tuple(
    field for field in SCHEDULE_FIELDS if field not in ("service", "effective_from", "effective_to")
)


def _save_schedule_draft(
    actor: Any, tariff: models.Tariff, payload: dict[str, Any]
) -> dict[str, Any]:
    """BR-RAT-031 save-draft resumable, the WRITE half: re-save THE one draft
    of a schedule. The draft is replaced whole (structure children included) —
    append-only binds versions that priced something, not a dateless draft.

    ⚠ **THIS SAID *"of a schedule that has never been activated"* UNTIL
    2026-09-17, AND THE RESTRICTION WAS PROSE — IT WAS NEVER IN THE STORAGE
    (DEF-RAT-6447).** `uq_tariff_versions_one_draft` is a PARTIAL unique index
    on `effective_from IS NULL`: its rule is *one draft*, not *no draft once
    live*. `draft_version` reads that same predicate, `in_force_version` and
    `latest_version` exclude it, and `schedule_state` derives the status pill
    from what is in force — so every read path was already built to carry a
    draft alongside an active version, and `schedule_card` has served both
    since DEF-368. The only thing standing in the way was `update_rate_schedule`'s
    guard, and it was asking a question about the SCHEDULE where BR-RAT-037
    asks one about the ROW. A live schedule now parks a draft here and its
    activated version is untouched, which is asserted rather than described:
    `tests/test_def_rat_5680_park_a_draft.py`.

    ── `DEF-RAT-8001` · DOES THIS PATH CLOSE AN OPEN WINDOW? **NO, AND IT MUST
    NOT.** ──────────────────────────────────────────────────────────────────
    A draft is DATELESS — that is what "draft" means here (BR-RAT-031) — so it
    opens no window and supersedes nothing. The sentence above is the whole
    reason: parking a draft on a live schedule must leave the activated version
    exactly as it was. `rating/0047`'s constraint carries
    `WHERE effective_from IS NOT NULL` for the same fact, so a draft is outside
    it too and the two halves agree.
    """
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, DRAFT_FIELDS, fe)
    identity = _validate_schedule_identity(payload, fe, partial=True, tariff=tariff)
    version_fields = _validate_version_fields(payload, fe, require_effective_from=False)
    structure = (
        _validate_structure(
            version_fields.get("model"), payload, fe, service_code=tariff.service.code
        )
        if "structure" in payload
        else {}
    )
    _refuse(fe)
    before = _json_safe(selectors.schedule_card(tariff))
    draft = selectors.draft_version(tariff)
    # `DEF-RAT-6932` — re-saving a draft replaces it WHOLE, so a payload that
    # does not mention the binding would otherwise drop it on every autosave.
    # The draft being replaced is the row to inherit from; where a live
    # schedule is parking its FIRST draft there is no draft yet, so the version
    # in force is, which is the row this draft is being written against.
    _carry_forward_base_charge_code(
        version_fields, draft if draft is not None else selectors.latest_version(tariff)
    )
    if draft is not None:
        _discard_draft(draft)
    fields = [field for field in ("name", "account_type_id") if field in identity]
    for field in fields:
        setattr(tariff, field, identity[field])
    if fields:
        tariff.save(update_fields=[*fields, "updated_at"])
    version = _write_version(tariff, version_fields, structure, actor=actor)
    _audit(
        actor,
        "tariff.draft_saved",
        "tariff_version",
        version.id,
        before=before,
        after=_json_safe(selectors.schedule_card(tariff)),
    )
    result = selectors.schedule_detail(tariff.id)
    result["notices"] = _schedule_notices(tariff, structure)
    return result


@require_role(SYSTEM_ADMIN)
def discard_rate_schedule_draft(actor: Any, tariff_id: Any) -> dict[str, Any]:
    """DEF-RAT-6447 · throw the parked draft away and keep the live rate.

    ⚠ **THIS IS THE OTHER HALF OF LETTING A LIVE SCHEDULE HOLD A DRAFT, NOT A
    CONVENIENCE.** `uq_tariff_versions_one_draft` allows exactly ONE dateless
    row per schedule. Before this endpoint the only way to clear one was to
    overwrite it by saving another draft, which is fine while the draft is
    yours and useless when it is a half-finished rate case from three months
    ago that nobody now wants: the clerk could neither see past it nor be rid
    of it, and the wizard would go on reopening onto it forever.

    It writes nothing to any activated version and cannot: `draft_version`
    reads only `effective_from IS NULL`, and `_discard_draft` deletes that row
    and its structure children. BR-RAT-037 is untouched — a dateless row has
    never been in force, which is the same reading that makes the parked draft
    lawful in the first place.
    """
    with transaction.atomic():
        tariff = _lock_schedule(tariff_id)  # CR-157-BRC10: lock first
        draft = selectors.draft_version(tariff)
        if draft is None:
            raise errors.NotFoundError()
        before = _json_safe(selectors.schedule_card(tariff))
        _discard_draft(draft)
        _audit(
            actor,
            "tariff.draft_discarded",
            "tariff",
            tariff.id,
            before=before,
            after=_json_safe(selectors.schedule_card(tariff)),
        )
        return selectors.schedule_detail(tariff.id)


@require_role(SYSTEM_ADMIN)
def update_rate_schedule(actor: Any, tariff_id: Any, payload: Any) -> dict[str, Any]:
    """Identity edits, plus the resumable DRAFT re-save. Price content is never
    edited in place once a version has been activated: from then on every change
    is a new version (BR-RAT-037, US-RAT-010 TC-7). Before activation the draft
    is rewritten in place (BR-RAT-031) — but the DATES stay activation's job, so
    posting them here is refused rather than silently activating a schedule
    whose structure was never completeness-checked."""
    payload = _require_dict(payload)
    with transaction.atomic():
        tariff = _lock_schedule(tariff_id)  # CR-157-BRC10: lock first
        content_keys = set(payload) & {
            "structure",
            "model",
            "base_charge",
            "minimum_bill",
            # DEF-360 — a per-size minimum bill is MONEY, so it is price content
            # and BR-RAT-037 binds it: posting it to a schedule that has been
            # activated is refused here, and the change goes through a new
            # version instead. The four BR-RAT-082 filing fields are deliberately
            # NOT here, matching their sibling `regulator_ref`: they describe a
            # sign-off, they price nothing, and they ride with whichever version
            # write is already carrying them.
            "size_rows",
            "effective_from",
            "effective_to",
            "uom",
            "currency",
        }
        if content_keys:
            # ⚠ **THE ORDER OF THESE TWO CHECKS IS THE FIX FOR DEF-RAT-6447 AND
            # IT IS A CHANGE OF QUESTION, NOT A LOOSENING.**
            #
            # This block asked `latest_version(tariff) is not None` FIRST, which
            # is a property of the SCHEDULE — has anything here ever gone live —
            # and refused every content write on a schedule that had. BR-RAT-037
            # is not about the schedule. Its words are *"IN-FORCE plan/tariff
            # versions are never edited in place"*, and that is a property of
            # the ROW BEING WRITTEN. A dateless draft has never been in force:
            # `in_force_version` excludes it by name, `latest_version` and
            # `tariff_versions` exclude it, and `schedule_state` derives the
            # status pill from what is in force, so a parked draft cannot even
            # make a live schedule read as a draft.
            #
            # So the guard was refusing a write that touches no activated
            # version at all — and with it the only way a clerk could park an
            # unfinished edit on a rate that is already live. PO, beta, 2026-09-17,
            # verbatim: *"when user want to save draft version you are refusing
            # it - we need to solve this deadlock. - we need to save edits"*.
            #
            # A DATE is what turns a row into a priced window, so posting one is
            # the ONLY content write here that can reach an activated version —
            # which is why the date check moved above and now carries both
            # refusals. Nothing else about BR-RAT-037 moved: changing a live
            # rate is still `POST /rate-schedules/{id}/versions`, still a new
            # row, still with a required reason and a `rate_change_log` entry.
            dated = sorted(set(payload) & {"effective_from", "effective_to"})
            if dated:
                if selectors.latest_version(tariff) is not None:
                    raise errors.BizError(
                        errors.BIZ_IMMUTABLE,
                        br_ref="BR-RAT-037",
                        message_key="rating.schedules.version_immutable",
                        params={"fields": sorted(content_keys)},
                    )
                raise errors.ValidationError(
                    errors.VAL_FORMAT,
                    message_key="rating.schedules.dates_land_at_activation",
                    params={"fields": dated, "br_ref": "BR-RAT-031"},
                )
            return _save_schedule_draft(actor, tariff, payload)
        fe: list[dict[str, Any]] = []
        _reject_unknown(payload, ("name", "account_type_id"), fe)
        identity = _validate_schedule_identity(payload, fe, partial=True, tariff=tariff)
        _refuse(fe)
        before = _json_safe(selectors.schedule_card(tariff))
        fields = []
        for field in ("name", "account_type_id"):
            if field in identity:
                setattr(tariff, field, identity[field])
                fields.append(field)
        if fields:
            tariff.save(update_fields=[*fields, "updated_at"])
            _audit(
                actor,
                "tariff.updated",
                "tariff",
                tariff.id,
                before=before,
                after=_json_safe(selectors.schedule_card(tariff)),
            )
    return selectors.schedule_detail(tariff.id)


@require_role(SYSTEM_ADMIN)
def activate_rate_schedule(actor: Any, tariff_id: Any, payload: Any = None) -> dict[str, Any]:
    """BR-RAT-031: activation requires a COMPLETE structure + effective_from and
    is published directly by a System Admin — no approval hold exists. A
    schedule that already carries an activated version is activated; changing it
    is a new version (BR-RAT-037).

    Two ways in. Posting the structure activates what was posted (a stored draft
    is superseded). Posting only the dates activates the STORED draft in place —
    the dateless row is stamped with its window after the completeness gate,
    which is exactly what "the row leaves draft" means.

    ── `DEF-RAT-8001` · DOES THIS PATH CLOSE AN OPEN WINDOW? **NO, AND THE
    GUARD BELOW IS WHY — IT IS NOT AN OMISSION.** ───────────────────────────
    This is the one audited path that DOES open a dated window without closing
    anything, so it was the obvious suspect. It is safe because the first thing
    inside the transaction refuses outright when
    `selectors.latest_version(tariff) is not None`: a schedule that already
    carries ANY activated version cannot be activated again, it is CHANGED
    through `create_rate_schedule_version` (BR-RAT-037). So there is provably
    no earlier window here to close.
    ⚠ **THE COROLLARY IS THE THING TO KEEP:** if that refusal is ever relaxed —
    to let a second service be activated onto one schedule, say — this path
    gains an un-closed window on the same day, and `rating/0047`'s constraint
    will refuse the COMMIT rather than the request. Call
    `_close_open_windows_before` here at the same moment the guard changes.
    """
    payload = _require_dict(payload or {})
    with transaction.atomic():
        tariff = _lock_schedule(tariff_id)  # CR-157-BRC10: lock first
        if selectors.latest_version(tariff) is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-037",
                message_key="rating.schedules.already_activated",
            )
        draft = selectors.draft_version(tariff)
        structure: dict[str, Any] = {}
        fe: list[dict[str, Any]] = []
        if draft is not None and "model" not in payload:
            _reject_unknown(payload, ("effective_from", "effective_to"), fe)
            effective_from = _date_value(payload, "effective_from", fe, required=True)
            effective_to = _date_value(payload, "effective_to", fe)
            if effective_from and effective_to and effective_from >= effective_to:
                fe.append(
                    _field_error(
                        "effective_to", errors.VAL_RANGE, "rating.schedules.window_inverted"
                    )
                )
            _refuse(fe)
            _require_complete_structure(draft)
            # §A3/BR-RAT-088 — the SAME guard the other branch runs, and it was
            # missing here entirely (DEF-458). Activating a saved draft is an
            # activation: it puts a priced version in force from a date, which
            # is precisely what the base-charge-code gate exists to stop when no
            # base code is declared. It fires BEFORE the draft is mutated, for
            # the reason stated below — a refusal after the write leaves a row a
            # human has to clean up.
            if effective_from is not None:
                _guard_base_charge_code(tariff)
                # `CR-120-BRC06` · `BR-RAT-1025`. ⚠ **THE ID COMES OFF THE DRAFT
                # ROW AND NOT OFF THE PAYLOAD, because this branch has no
                # `version_fields` at all** — that is `DEF-458` exactly, where
                # four lines reading a name only the other branch binds made
                # activating a saved draft answer 500. The draft is the thing
                # being activated, so the draft is what carries the binding.
                named_base = _guard_bound_base_charge_code(tariff, draft.base_charge_code_id)
            before = _json_safe(selectors.version_row(draft))
            if effective_from is not None:
                draft.base_charge_code_id = named_base
            draft.effective_from = effective_from
            draft.effective_to = effective_to
            draft.save(
                update_fields=["effective_from", "effective_to", "base_charge_code", "updated_at"]
            )
            version = draft
        else:
            _reject_unknown(payload, SCHEDULE_FIELDS, fe)
            version_fields = _validate_version_fields(payload, fe, require_effective_from=True)
            structure = _validate_structure(
                version_fields.get("model"), payload, fe, service_code=tariff.service.code
            )
            _refuse(fe)
            before = None
            # `DEF-RAT-6932` — the binding the draft (or the version in force)
            # already holds, unless this payload says otherwise. Before the
            # guard below, so a carried code is re-checked at activation
            # exactly like a freshly named one.
            _carry_forward_base_charge_code(
                version_fields,
                draft if draft is not None else selectors.latest_version(tariff),
            )
            if draft is not None:
                # The wizard posted the final structure — the saved draft is
                # superseded, never left behind as a second dateless row.
                _discard_draft(draft)
            # §A3/BR-RAT-088: refuse before the version exists, not after — a
            # refusal that fires post-write leaves a row a human must clean up.
            #
            # ⚠ THESE FOUR LINES WERE DEDENTED OUT OF THIS BRANCH (DEF-458,
            # CRITICAL). They read `version_fields`, which ONLY this branch
            # binds — so activating a saved draft, which takes the branch above,
            # raised `UnboundLocalError` and answered 500. The comment itself
            # was split across the slip, which is what makes it readable as an
            # indentation accident rather than a decision.
            if version_fields.get("effective_from") is not None:
                _guard_base_charge_code(tariff)
                # `CR-120-BRC06` · `BR-RAT-1025` — and the NAMED code has to be
                # one R4 could actually have selected, or step 5 shows a figure
                # the bill will not use. Silent when nothing is bound, which is
                # every schedule that exists today.
                version_fields["base_charge_code_id"] = _guard_bound_base_charge_code(
                    tariff, version_fields.get("base_charge_code_id")
                )
            version = _write_version(tariff, version_fields, structure, actor=actor)
        # CR-157-BRC10 — the database's overlap rule, asked while a refusal can
        # still be named (the backstop behind `_lock_schedule`).
        _check_windows_now(tariff, version.effective_from)
        # Both branches now produce a `version` and a `before`, so the audit is
        # shared — an activation is an activation however the version arrived.
        _audit(
            actor,
            "tariff.activated",
            "tariff_version",
            version.id,
            before=before,
            after=_json_safe(selectors.version_row(version)),
        )
    result = selectors.schedule_detail(tariff.id)
    result["notices"] = _schedule_notices(tariff, structure)
    return result


@require_role(SYSTEM_ADMIN)
def correct_rate_schedule_version(
    actor: Any, tariff_id: Any, version_id: Any, payload: Any
) -> dict[str, Any]:
    """`BR-RAT-1016` verb 2 for the RATE SCHEDULE — the fifth and last of the
    five priced objects in this module to get it (DEF-RAT-5715).

    ⚠ **THE RULE THAT GOVERNS THIS IS `BR-RAT-1016`, CONFIRMED BY THE PO ON
    2026-09-17** — shown a table of what each of the five priced objects does
    today, verbatim: *"please fix all these"*. **The three verbs are the same
    for every one of them: EDIT while it has priced nothing · CORRECT over the
    SAME window when the figure recorded was wrong · CHANGE over a NEW window
    when prices move.** That generalises `BR-RAT-104`, which came from CR-013
    part 4 under the heading **shared rules** and was built for taxes alone.

    The charge code, the discount and the tax carry it already; the plan is
    deliberately unbuilt and named (`DEF-RAT-5710`, `OQ-RAT-12409`). **This is
    the rate schedule, which was the object the PO was shown REFUSING the save
    outright once live with no correction path at all.**

    ── THE PO'S OWN DISTINCTION, VERBATIM ────────────────────────────────────
    *"if user make an error while creating the rate schedule and they want to
    rectify that error using edit - how are they going to do it; it is not a new
    rate or it is not a change in rate - it is just an error handling"*.

    ── A CORRECTION IS NOT A RATE CHANGE, AND THE DIFFERENCE IS THE WINDOW ───
    A rate CHANGE is a new row with a NEW window: the price moves on a date, and
    every bill before that date was right (BR-RAT-037,
    `create_rate_schedule_version` below). A CORRECTION restates the SAME
    window, because the figure recorded for that period was **wrong**.

    **THAT SINGLE PROPERTY IS WHAT MAKES THIS FUNCTION A CORRECTION**, so the
    window is copied from the row being corrected and this function NEVER reads
    a date from the payload — it refuses one by name rather than ignoring it.
    A "correction" that moved the window would be a rate change wearing a
    correction's clothes, and it would silently rewrite which bills the old
    figure was ever right for.

    ── WHAT HAPPENS TO THE ROW BEING CORRECTED ───────────────────────────────
    **It is never deleted.** It keeps its rate, its start date, its filing
    detail and its audit trail for ever, and it stays in `activated_versions`
    so a regulator asking *"what has this schedule ever said"* still sees it.
    It stops PRICING because `in_force_version` skips a superseded row — one
    line, added in the same commit as DEF-RAT-5715, and the load-bearing half
    of the pair: without it, two rows share one window and the order-by
    decides which prices by a column that is identical on both.

    ⚠ **EXACTLY ONE COLUMN OF IT MOVES, AND IT IS `effective_to`
    (`BR-RAT-1044`, PO ruling 2026-09-29).** An OPEN end is filled with
    `max(the correction date, its own effective_from)` so the register shows
    **when the wrong version stopped being used**; a stated end is never
    moved. The two worked cases the PO was shown, both tested in
    `tests/test_br_rat_1044_correction_closes_the_window.py`:

      | version's window | corrected on | its `effective_to` becomes |
      |------------------|--------------|----------------------------|
      | from 2026-02-01  | 2026-03-01   | **2026-03-01**             |
      | from 2026-02-01  | 2026-01-15   | **2026-02-01** (the `max`) |

    THIS SENTENCE USED TO READ *"it keeps its DATES for ever"*, which was true
    until that ruling and is why it is spelled out here rather than left to
    be inferred from the code.

    ── ⚠ WHAT THIS DELIBERATELY DOES NOT DO, AND IT IS THE MONEY HALF ────────
    **It does not touch one bill already issued.** Hard rule 4 forbids it, and
    BR-RAT-007/017 say a past bill is reproduced from what it stored. So the
    households already billed at the wrong price are still billed at the wrong
    price until somebody corrects those bills, through billing's own correction
    path. This function REPORTS that rather than implying otherwise: the answer
    carries `issued_bills_unchanged` and the COUNT, because an operator who has
    just fixed a price will reasonably believe the money is fixed.

    ⚠ **THE COUNT IS PRECISE AND WAS MEASURED, NOT ASSUMED** — see
    `selectors.version_issued_bill_count`. It reads `DEF-276`'s stamp, which was
    read back off a running tenant before this was written (hard-won law 1):
    456/456 usage lines and 184/184 base lines carry it, 0 orphans. `None` means
    billing could not answer and is shown as that, never as zero.

    ⚠ **THE SHAPE IS THE OTHER FOUR OBJECTS' SHAPE ON PURPOSE**, down to the
    route spelling (`POST …/corrections`, a collection a correction is MINTED
    into) and the four columns. The uniform-verbs lane recorded the reason on
    the discount the same day and it holds here: *"two objects answering the
    same question must not answer it two ways"*.

    ── `DEF-RAT-8001` · DOES THIS PATH CLOSE AN OPEN WINDOW? **NO, AND CLOSING
    ONE HERE WOULD BE THE BUG.** ────────────────────────────────────────────
    A correction restates the SAME window — that single property is what makes
    this function a correction, as the paragraph above says — so it SUPERSEDES
    rather than adding a window. The two rows that then share one window are
    the feature, not an overlap, and the live run tells them apart by
    `superseded_by`.
    ⚠ **`rating/0047`'s constraint is `DEFERRABLE INITIALLY DEFERRED` FOR THIS
    FUNCTION.** It writes the correction row FIRST and stamps `superseded_by`
    on the original SECOND; for the instant between those two statements there
    are two live rows on one window, and an immediate constraint would refuse
    the INSERT. Deferred, it is checked at COMMIT, by which time the stamp is
    on. **Do not reorder these two writes on the assumption that the order is
    what makes them legal — the deferral is.** And because the check lands at
    COMMIT, anything that catches `IntegrityError` around this must use a
    SAVEPOINT (hard-won law 14).

    🔒 HUMAN-REVIEW-PENDING — this decides which stored row prices a service
    date, which is money. Row in `12-governance/09-human-review-ledger.md`.
    """
    payload = _require_dict(payload)
    reason = str(payload.get("reason") or "").strip()
    fe: list[dict[str, Any]] = []
    if len(reason) < MIN_CORRECTION_REASON:
        fe.append(
            _field_error("reason", errors.VAL_REQUIRED, "rating.schedules.correction_reason")
        )
    # A DATE IN THE PAYLOAD IS REFUSED BY NAME rather than overridden in
    # silence. `correct_tax` overrides, which is safe; saying so is safer,
    # because a caller that sent a date believed it would be used and would
    # otherwise never learn it was not.
    dated = sorted(set(payload) & {"effective_from", "effective_to"})
    if dated:
        fe.append(
            _field_error(
                dated[0],
                errors.VAL_FORMAT,
                "rating.schedules.correction_keeps_the_window",
            )
        )
    _reject_unknown(payload, SCHEDULE_FIELDS + ("reason",), fe)
    with transaction.atomic():
        tariff = _lock_schedule(tariff_id)  # CR-157-BRC10: lock first
        original = selectors.version_or_404(tariff, version_id)
        if original.effective_from is None:
            # A DRAFT is not history. It has never priced anything, so there is
            # nothing to preserve and nothing to explain: edit it in place
            # through `PATCH /rate-schedules/{id}`, which is what wave 1 of
            # DEF-RAT-6447 made reachable on a live schedule too.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-104",
                message_key="rating.schedules.correct_draft",
                params={"name": tariff.name},
            )
        if original.superseded_by_id is not None:
            # Correcting a correction would leave two rows claiming to restate
            # one window with nothing saying which is current.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-104",
                message_key="rating.schedules.already_corrected",
                params={"name": tariff.name},
            )
        version_fields = _validate_version_fields(payload, fe, require_effective_from=False)
        structure = _validate_structure(
            version_fields.get("model"), payload, fe, service_code=tariff.service.code
        )
        _refuse(fe)
        # ── THE WINDOW, COPIED FROM THE ROW BEING CORRECTED ──────────────
        # ⚠ **`effective_from` IS COPIED AND THAT IS WHAT MAKES THIS A
        # CORRECTION** (see the docstring). `effective_to` is copied too, so a
        # correction of the CURRENT version — whose end is open — is itself
        # open, and a correction of an already-closed window keeps that close.
        version_fields["effective_from"] = original.effective_from
        version_fields["effective_to"] = original.effective_to
        # ── `BR-RAT-1044` · WHEN THE WRONG ROW STOPPED BEING USED ─────────
        # PO ruling 2026-09-29, verbatim, choosing option (a) of three:
        # *"i will take this and use superseded_by in filter - so that it is
        # always unique and even if we see in audit it is clear"*.
        #
        # The corrected row's END DATE now records the day it was replaced,
        # so the register reads *in use from X to Y* rather than *in use from
        # X, for ever* on a row that has not priced anything since Y.
        #
        #     old.effective_to = max(the correction date, old.effective_from)
        #
        # ⚠ **THE `max` IS THE WHOLE EDGE CASE, AND IT IS NOT "CORRECTED
        # BEFORE ACTIVATION".** A DRAFT has no dates at all and is edited in
        # place — the branch above refuses it by name, no version exists and
        # there is nothing to supersede. This is the OTHER thing: a version
        # ACTIVATED WITH A FUTURE DATE and corrected before that date arrives.
        # Its `effective_from` is still ahead of today, so a bare correction
        # date would write an end BEFORE the start — the inverted window
        # `_validate_version_fields` refuses by name as `window_inverted` —
        # and the correction would fail outright. The `max` makes such a row
        # read *replaced the day it would have started*. Do not widen this to
        # the draft case; they are different rows in different states.
        #
        # ⚠ **A STATED END IS NEVER MOVED, AND THAT CLAUSE IS OURS RATHER
        # THAN THE PO'S** (decision log 2026-09-29). The ruling was put and
        # answered for the ordinary case — the CURRENT version, whose window
        # is open. A version that is already closed stopped being used on the
        # day its successor started, not on the day somebody noticed the
        # figure was wrong, so writing the correction date over it would make
        # the register say the row ran a month longer than it did. It is also
        # `rating/0046`'s own rule, one writer along: *"ONLY A NULL END IS
        # FILLED. AN END DATE THAT ALREADY EXISTS IS NEVER MOVED — somebody
        # typed it, it is what a bill was reproduced against."*
        #
        # ⚠ **THIS MOVES NO PRICING AND CANNOT.** Both readers of this table
        # drop a superseded row before they look at a window at all —
        # `selectors.in_force_version` has since `DEF-RAT-5715` and
        # `resolution_catalogue` since `DEF-RAT-8002` — so the date written
        # here is read by the REGISTER and by nothing that decides money.
        # `rating/0047`'s exclusion constraint carries the same predicate
        # (`superseded_by_version_id IS NULL`), so the pair stays legal
        # whatever this date says.
        #
        # ⚠ **FORWARD-ONLY.** Rows corrected before today keep their open end.
        # Backfilling them is a separate ruling the PO has not taken, and
        # `10-scripts/rat_schedule_overlap_census.py --corrected-open` is the
        # count that has to go to them first.
        #
        # ⚠ **THE CORRECTION DATE IS THE UTILITY'S OWN DAY, NEVER THE
        # SERVER'S** — `seams.tenant_today()`, which is `BR-TEN-081`'s clock
        # and `BR-TEN-043`'s event-time reading of it: the day the correction
        # HAPPENED, on the clock of the utility it happened at. A server-side
        # `date.today()` would put a Houston correction made at 19:00 on the
        # 8th onto the 9th.
        stopped_using = max(seams.tenant_today(), original.effective_from)
        # BR-RAT-037's authored note belongs to a CHANGE. A correction has its
        # own reason, and putting the correction's words in `change_reason`
        # would file a typo as a rate filing. The corrected row's own change
        # note travels with the restatement, because the FILING did not change.
        version_fields["change_reason"] = original.change_reason
        # `DEF-RAT-6932` — and the binding, for the same reason the window and
        # the change note are copied: a CORRECTION restates one window, it does
        # not re-decide which charge code owns the service's base.
        # `_write_version`'s own comment already claimed a correction *"builds
        # its `cleaned` from the row it is restating"*; only the two lines above
        # ever did, which is hard-won law 1 inside the money path it describes.
        _carry_forward_base_charge_code(version_fields, original)
        before = _json_safe(selectors.version_row(original))
        billed = selectors.version_issued_bill_count(original)
        correction = _write_version(tariff, version_fields, structure, actor=actor)
        correction.corrects = original
        correction.correction_reason = reason
        correction.corrected_by_id = _actor_user_id(actor)
        correction.save(
            update_fields=["corrects", "correction_reason", "corrected_by", "updated_at"]
        )
        original.superseded_by = correction
        # `BR-RAT-1044`, above. Written in the SAME save as the stamp, because
        # the two facts are one event: this row stopped being used BECAUSE it
        # was superseded, and a reader that saw one without the other would
        # see a live row with an end date or an ended row still pricing.
        end_was_open = original.effective_to is None
        if end_was_open:
            original.effective_to = stopped_using
        original.save(
            update_fields=["superseded_by", "effective_to", "updated_at"]
            if end_was_open
            else ["superseded_by", "updated_at"]
        )
        # CR-157-BRC10 — AFTER the stamp, never between the two writes: the
        # deferral above is what makes the pair legal, and this is the moment
        # it has to be legal by.
        _check_windows_now(tariff, original.effective_from)
        after = _json_safe(selectors.version_row(correction))
        models.RateChangeLog.objects.create(
            tenant_id=_tenant_id(),
            entity_type="schedule",
            entity_id=tariff.id,
            before={"name": tariff.name, **(before or {})},
            after={"name": tariff.name, **(after or {})},
            reason=reason,
            actor_id=_actor_user_id(actor),
        )
        _audit(
            actor,
            "tariff.version_corrected",
            "tariff_version",
            original.id,
            before=before,
            after=_json_safe(selectors.version_row(original)),
        )
        _audit(
            actor,
            "tariff.correction_created",
            "tariff_version",
            correction.id,
            after={**(after or {}), "reason": reason, "issued_bills": billed},
        )
    result = selectors.schedule_detail(tariff.id)
    result["notices"] = _schedule_notices(tariff, structure)
    # ⚠ SAID OUT LOUD IN THE ANSWER, not only in this docstring — `correct_tax`'s
    # own precedent, and for the reason it records: an operator who has just
    # fixed a wrong price will reasonably believe the money is fixed.
    result["issued_bills_unchanged"] = True
    result["issued_bills"] = billed
    return result


@require_role(SYSTEM_ADMIN)
def create_rate_schedule_version(actor: Any, tariff_id: Any, payload: Any) -> dict[str, Any]:
    """US-RAT-010: the single rate update. The previous window closes the day
    before the new one opens, windows never overlap (B2 EXCLUDE), and the
    change appends a rate_change_log row with a REQUIRED reason (BR-RAT-037)."""
    payload = _require_dict(payload)
    with transaction.atomic():
        tariff = _lock_schedule(tariff_id)  # CR-157-BRC10: lock first
        reason = str(payload.get("reason") or "").strip()
        if not reason:
            # US-RAT-010 TC-6 — nothing is written without a reason (r5 #14).
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="rating.reason_required",
                params={"br_ref": "BR-RAT-037"},
                field_errors=[
                    _field_error("reason", errors.VAL_REQUIRED, "rating.reason_required")
                ],
            )
        fe: list[dict[str, Any]] = []
        _reject_unknown(payload, SCHEDULE_FIELDS + ("reason",), fe)
        version_fields = _validate_version_fields(payload, fe, require_effective_from=True)
        structure = _validate_structure(
            version_fields.get("model"), payload, fe, service_code=tariff.service.code
        )
        _refuse(fe)
        # DEF-280 — the reason BR-RAT-037 already refuses without is written ON
        # the version, not only into `rate_change_log`. It was always authored
        # by the person filing; it was stored where a filings table cannot read
        # it, which is why §10's CHANGE column had nothing to show. An explicit
        # `change_reason` in the payload (a longer note than the audit reason)
        # wins; otherwise the reason is the note.
        version_fields["change_reason"] = version_fields.get("change_reason") or reason
        previous = selectors.latest_version(tariff)
        new_from = version_fields["effective_from"]
        if previous is None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-031",
                message_key="rating.schedules.activate_first",
            )
        _guard_window(previous, new_from)
        # `DEF-RAT-6932` — the binding survives a rate change unless the payload
        # deliberately clears it. Before the guard below, so a carried code is
        # re-checked at activation exactly like a freshly named one.
        _carry_forward_base_charge_code(version_fields, previous)
        before = _json_safe(selectors.version_row(previous))
        # ── `DEF-RAT-8001` · CLOSE EVERY OPEN WINDOW, NOT JUST THE NEWEST ────
        # This read `selectors.latest_version(tariff)` and closed that ONE row.
        # Correct while exactly one window is open; once two are, every later
        # rate change closes the newest and steps over the rest, so the overlap
        # never heals. `_close_open_windows_before` says which rows it takes and
        # which it leaves (a draft, a correction, a future-dated version).
        # `previous` is still the row whose `before` the audit and the
        # `RateChangeLog` quote — that is the version a clerk believes they are
        # superseding, and it is one of the rows this closes.
        _close_open_windows_before(tariff, new_from)
        previous.refresh_from_db(fields=["effective_to", "updated_at"])
        # §A3/BR-RAT-088: refuse before the version exists, not after — a
        # refusal that fires post-write leaves a row a human must clean up.
        if version_fields.get("effective_from") is not None:
            _guard_base_charge_code(tariff)
            # `CR-120-BRC06` · `BR-RAT-1025` — see the sibling call sites.
            version_fields["base_charge_code_id"] = _guard_bound_base_charge_code(
                tariff, version_fields.get("base_charge_code_id")
            )
        version = _write_version(tariff, version_fields, structure, actor=actor)
        # CR-157-BRC10 — the backstop behind `_lock_schedule`: ask `rating/0047`
        # now, so a clash is `window_overlap` and never a raw error at COMMIT.
        _check_windows_now(tariff, new_from)
        # BR-RAT-091 clause 2 — THE GATE, SERVER-SIDE (DEF-435). Inside the
        # atomic block on purpose: the figure cannot be measured until the
        # version's structure rows exist, and a refusal here rolls the whole
        # write back, so nothing a human must clean up is left behind.
        measured = _guard_rate_change_second_approval(tariff, previous, version)
        after = _json_safe(selectors.version_row(version))
        models.RateChangeLog.objects.create(
            tenant_id=_tenant_id(),
            entity_type="schedule",
            entity_id=tariff.id,
            before={"name": tariff.name, **(before or {})},
            after={"name": tariff.name, **(after or {})},
            reason=reason,
            actor_id=_actor_user_id(actor),
        )
        _audit(
            actor,
            "tariff.version_created",
            "tariff_version",
            version.id,
            before=before,
            # BR-RAT-091 clause 2's measurement rides on the audit row rather
            # than on a column, and the reason is that a RATE change has no gap
            # in time to protect. Clause 1 STORES its answer on the discount
            # version because it is computed at SUBMIT and read at APPROVE, and
            # *"a tenant who edits the threshold in between would otherwise move
            # the bar under a signature that had already been given"*. There is
            # no submit→approve gap here: BR-RAT-031 as-modified removed the
            # rate-schedule workflow, so the gate fires in the same instant the
            # version is written and there is nothing to freeze. What must
            # survive is the RECORD — hard rule 7 — and `audit_log` is where a
            # money action's evidence belongs. `worst_case_pct` is null, never
            # 0, when nobody could measure it (DEF-434, OQ-320).
            after={**(after or {}), "reason": reason, "impact": measured},
        )
    result = selectors.schedule_detail(tariff.id)
    result["notices"] = _schedule_notices(tariff, structure)
    result["impact"] = measured
    return result


def _guard_rate_change_second_approval(
    tariff: models.Tariff,
    previous: models.TariffVersion | None,
    version: models.TariffVersion,
) -> dict[str, Any]:
    """BR-RAT-091 clause 2, ENFORCED WHERE IT CANNOT BE BYPASSED (DEF-435).

    The rule, verbatim: **"(2) RATE CHANGE: worst-case bill change above
    `10%`."** Until 2026-08-21 that figure lived exactly once, as
    `RATE_CHANGE_SECOND_APPROVAL_PCT = 10` in a React file — *"a client-side-only
    gate is advice, not a control"* — while clause 1, the `$500` discount
    subsidy, was a tenant Param enforced by `discount_services` at submit. A
    two-figure rule read as done while half of it governed a screen and not a
    write.

    **The measurement is not re-derived here.** `selectors.impact_figures` is
    the same function `GET /rate-schedules/{id}/impact` answers from, so the
    number the filer read on RAT-03 step 4 and the number that judges their
    filing are the same number, produced by the same engine call. A gate with
    its own arithmetic is how a screen and a server start disagreeing about
    whether a rate case is lawful.

    ⚠ **ABOVE THE BAR, THIS REFUSES — AND THAT IS PENDING `OQ-318`, NOT SETTLED.**
    BR-RAT-091 says such a filing *needs a second approval*; BR-RAT-031
    as-modified deleted the rate-schedule approval workflow, so there is nowhere
    for one to land. Both rules are CONFIRMED and they meet head-on. A CONFIRMED
    rule whose precondition cannot be satisfied must not be reported as
    satisfied, so the write fails CLOSED (hard-won law 3) and the refusal names
    the rule, the measured percentage and the bar. The PO's own precedent points
    the other way — BR-RAT-109, 2026-08-21, verbatim *"We will show message and
    not refuse it"* — which is why this is a question and not a decision.

    ⚠ **UNMEASURED IS NOT CLEAR AND IS NOT REFUSED EITHER.**
    `impact.second_approval_required(None)` returns `None`; the version is
    written, the audit records that the figure was never computed, and nothing
    anywhere reports the filing as under the bar. Refusing every unmeasurable
    filing would stop the first rate schedule of every new tenant, which have no
    accounts and no reads by definition (OQ-320).
    """
    service_code = tariff.service.code if tariff.service_id else ""
    figures, _priced, reasons, _by_plan = selectors.impact_figures(
        tariff, service_code, previous, version, version.effective_from
    )
    required, threshold = impact.second_approval_required(figures.worst_case_pct)
    measured = {
        "worst_case_pct": None if figures.worst_case_pct is None else str(figures.worst_case_pct),
        "second_approval_required": required,
        "second_approval_threshold_pct": str(threshold),
        "accounts_affected": figures.accounts_affected,
        "accounts_priced": figures.accounts_priced,
        "accounts_unpriced": figures.accounts_unpriced,
        "unpriced_reasons": reasons,
    }
    if required:
        # G33 caps refusal copy at two sentences, so the figures travel as
        # params and the reasoning stays in this docstring.
        raise errors.BizError(
            errors.BIZ_APPROVAL,
            br_ref="BR-RAT-091",
            message_key="rating.schedules.second_approval_required",
            params={
                "pct": str(impact.quantize_percent(figures.worst_case_pct).normalize()),
                "threshold": str(threshold.normalize()),
            },
        )
    return measured


def _close_open_windows_before(tariff: models.Tariff, new_from: date) -> int:
    """Close EVERY activated, non-superseded window of this schedule that would
    still be in force on `new_from`. Returns how many were closed.

    ⚠ **THIS REPLACED A ONE-ROW CLOSE, AND THE ONE-ROW VERSION IS WHY AN
    OVERLAP NEVER HEALED (`DEF-RAT-8001`).** Both writers used to read
    `selectors.latest_version(tariff)` — which orders by `-effective_from` and
    takes ONE row — and close that. With exactly one open window that is
    correct, and it is how every one of these schedules looked when the code
    was written. **Once two are open it is a trap:** each later activation
    closes the NEWEST and steps straight over the older ones, so the estate can
    never work its way back to one window however many rate changes are filed.
    Ottumwa Water Works reached four versions of one sewer schedule in force on
    2026-10-29 that way, and its one-time and move-out final bills refuse with
    `AmbiguousSchedule`.

    **WHAT IT CLOSES, AND WHAT IT DELIBERATELY DOES NOT.**
    · ACTIVATED only — a dateless DRAFT has no window (BR-RAT-031) and is not
      touched. `activated_versions` already carries that predicate.
    · NON-SUPERSEDED only — a corrected row's window is settled at the moment
      it is corrected and is never moved afterwards (BR-RAT-104 / BR-RAT-1016
      verb 2; `BR-RAT-1044` is what settles it — `correct_rate_schedule_
      version` stamps the end date the row stopped being used on, in the same
      save as `superseded_by`). It has already stopped pricing because
      `in_force_version` skips it, and rewriting its window HERE would falsify
      the filing history a regulator reads.
    · STARTING BEFORE `new_from` only — a FUTURE-dated version is not something
      this change supersedes, and shortening it here would silently cancel a
      scheduled rate change nobody asked to cancel. `_guard_window` /
      `_guard_batch_window` are what refuse a new window that is not strictly
      later than the newest; this function is not a second guard.
    · `.exclude(effective_to__lt=new_from)` keeps a NULL end (SQL `NULL < x` is
      unknown, so a NULL row is never in the excluded set) **and** keeps a
      stated end that runs past the new start, which is the behaviour the
      one-row version already had for the row it could see.

    The end date written is `new_from - 1 day`, which is this codebase's one
    convention: `effective_to` is INCLUSIVE everywhere
    (`selectors.in_force_version` asks `effective_to >= service_date`).

    🔒 This decides which stored row prices a service date, which is money.
    `rating/0047`'s `ex_tariff_versions_no_overlap` is the database half and
    would now refuse a second open window at COMMIT; this is the half that
    keeps a clerk from ever meeting that refusal.
    """
    rows = list(
        selectors.activated_versions(tariff)
        .filter(superseded_by__isnull=True, effective_from__lt=new_from)
        .exclude(effective_to__lt=new_from)
        .order_by("effective_from")
    )
    for row in rows:
        row.effective_to = new_from - timedelta(days=1)
        row.save(update_fields=["effective_to", "updated_at"])
    return len(rows)


def _guard_window(previous: models.TariffVersion, new_from: date) -> None:
    """The app-side half of the B2 EXCLUDE constraint (sqlite has no gist):
    a new window must open strictly AFTER the latest one (US-RAT-010 TC-5)."""
    if new_from <= previous.effective_from:
        raise errors.BizError(
            errors.BIZ_WINDOW,
            br_ref="BR-RAT-037",
            message_key="rating.schedules.window_overlap",
            params={
                "effective_from": new_from.isoformat(),
                "current_from": previous.effective_from.isoformat(),
            },
        )


def _copy_of_version(version: models.TariffVersion) -> tuple[dict[str, Any], dict[str, Any]]:
    """DEF-370 · one stored version read back into the `(cleaned, structure)`
    pair `_write_version` already takes.

    Built this way ON PURPOSE. A duplicate that wrote its own rows would be a
    SECOND write path for a version — hard-won law 5 inside one module — and the
    two would drift the first time a structure gains a column. Reading the rows
    into the writer's own vocabulary means a duplicate is, by construction,
    whatever `_write_version` writes today.

    ⚠ **WHAT IS DELIBERATELY NOT COPIED, and why each one would be a lie.**
    The dates (a copy has never been in force — it lands as the resumable draft,
    BR-RAT-031), the four BR-RAT-082 filing fields and `regulator_ref` (last
    year's docket belongs to last year's version; a copy carrying it would file
    a new rate under an approved case number), `version_label` (DEF-369: the
    label a regulator recognises, and two versions sharing one is exactly the
    confusion that defect exists to end), `change_reason` (DEF-280: a note about
    a change that has not happened yet) and `approved_by`. `submitted_by` is not
    copied either — `_write_version` stamps the person doing the DUPLICATING,
    which is the true answer to "who filed this draft".
    """
    tenant_id = _tenant_id()
    cleaned: dict[str, Any] = {
        "model": version.model,
        "uom": version.uom,
        "currency": version.currency,
        "base_charge": version.base_charge,
        # `CR-120-BRC06` · `BR-RAT-1025` — **COPIED, unlike the filing fields
        # below.** The binding says which charge code owns this service's base;
        # it is a PRICING fact about the schedule, not a record of a rate case,
        # so a duplicate that dropped it would silently put the copy back on the
        # inferred route. Today that resolves the same figure — and the moment a
        # utility has two base codes it does not, which is the whole reason the
        # binding exists.
        "base_charge_code_id": version.base_charge_code_id,
        # `DEF-RAT-8737` (PO 2026-10-01, option A) — not copied: the version
        # carries no minimum any more; `size_rows` below carries it.
        "minimum_bill": None,
        # BR-RAT-031: a copy is a DRAFT. Dateless is what "draft" means here.
        "effective_from": None,
        "effective_to": None,
        "regulator_ref": None,
        "filing_authority": None,
        "filed_on": None,
        "regulator_approved_on": None,
        "regulator_approver": None,
        "version_label": None,
        "change_reason": None,
        "approved_by_id": None,
        "notify_customers": version.notify_customers,
        "publish_public": version.publish_public,
        "size_rows": [
            {"size_class": row.size_class, "minimum_bill": row.minimum_bill}
            for row in models.RateSizeRow.objects.filter(
                tenant_id=tenant_id, tariff_version=version
            ).order_by("size_class", "id")
        ],
    }
    seasons = list(
        models.RateSeason.objects.filter(tenant_id=tenant_id, tariff_version=version).order_by(
            "start_month", "start_day", "id"
        )
    )
    labels = {season.id: season.label for season in seasons}
    structure: dict[str, Any] = {
        "percent": version.percent,
        "basis_service_id": version.basis_service_id,
        # `CR-130-BRC07` — served back so reopening a saved draft reloads the
        # basis the clerk chose. Without it the wizard would redraw the card on
        # its own default and a charge-basis draft would silently reopen as a
        # usage one (CLAUDE.md hard-won law 2's shape: the write lands, the
        # read does not, and every test passes).
        "percent_basis": version.percent_basis,
        "seasons": [
            {
                "label": season.label,
                "start_month": season.start_month,
                "start_day": season.start_day,
                "end_month": season.end_month,
                "end_day": season.end_day,
            }
            for season in seasons
        ],
        # EVERY tier goes in this one list carrying its season LABEL, including a
        # seasonal schedule's. `_write_version` extends its set from
        # `season["tier_rows"]` only when that key is present, so the copied
        # seasons above (which have no such key) contribute none and nothing is
        # written twice.
        "tiers": [
            {
                "seq": tier.seq,
                "from_qty": tier.from_qty,
                "to_qty": tier.to_qty,
                "unit_price": tier.unit_price,
                "season": labels.get(tier.season_id),
                # DEF-433 — the size axis travels with the copy. A 2" override
                # that vanished on duplicate would be the silent-drop the
                # defect's own prevention note warns about.
                "size_class": tier.size_class,
            }
            for tier in models.RateTier.objects.filter(
                tenant_id=tenant_id, tariff_version=version
            ).order_by("seq", "id")
        ],
        "windows": [
            {
                "label": window.label,
                "season": labels.get(window.season_id),
                "day_type": window.day_type,
                "start_time": window.start_time,
                "end_time": window.end_time,
                "unit_price": window.unit_price,
                # BR-RAT-067: NULL is a refusal, so a copy that invented one
                # here would turn a schedule the engine refuses into one it
                # prices, on the wrong register.
                "channel": window.channel,
            }
            for window in models.TimeOfUseWindow.objects.filter(
                tenant_id=tenant_id, tariff_version=version
            ).order_by("start_time", "id")
        ],
    }
    capacity = models.CapacityRate.objects.filter(
        tenant_id=tenant_id, tariff_version=version
    ).first()
    if capacity is not None:
        structure["capacity"] = {
            "unit_label": capacity.unit_label,
            "rate_per_unit": capacity.rate_per_unit,
            "currency": capacity.currency,
        }
    demand = models.DemandRateConfig.objects.filter(
        tenant_id=tenant_id, tariff_version=version
    ).first()
    if demand is not None:
        structure["demand"] = {
            "energy_rate_per_kwh": demand.energy_rate_per_kwh,
            "demand_rate_per_kw": demand.demand_rate_per_kw,
            "peak_window_label": demand.peak_window_label,
            "peak_window_start": demand.peak_window_start,
            "peak_window_end": demand.peak_window_end,
            "ratchet_enabled": demand.ratchet_enabled,
            "ratchet_pct": demand.ratchet_pct,
            "pf_penalty_enabled": demand.pf_penalty_enabled,
            "pf_penalty_rate_per_kw": demand.pf_penalty_rate_per_kw,
        }
    return cleaned, structure


def _copy_name(source_name: str, service_id: Any) -> str:
    """`Residential Water` → `Residential Water (copy)` → `… (copy 2)`.

    `uq_tariffs_tenant_name_service` is per (tenant, name, service) and a
    duplicate lands on the SAME service, so the plain suffix collides the second
    time a utility duplicates one schedule. Counting is not decoration: without
    it the second duplicate answers a 500 from a database constraint instead of
    creating a schedule.
    """
    taken = set(
        models.Tariff.objects.filter(tenant_id=_tenant_id(), service_id=service_id).values_list(
            "name", flat=True
        )
    )
    base = f"{source_name} (copy)"[:120]
    if base not in taken:
        return base
    for counter in range(2, 100):
        candidate = f"{source_name} (copy {counter})"[:120]
        if candidate not in taken:
            return candidate
    # 99 copies of one schedule is not a case worth inventing a name for; the
    # caller passes its own `name` and gets the ordinary duplicate-name error.
    raise errors.ValidationError(
        errors.VAL_FORMAT,
        message_key="rating.schedules.duplicate_name",
        field_errors=[_field_error("name", errors.VAL_FORMAT, "rating.schedules.duplicate_name")],
    )


@require_role(SYSTEM_ADMIN)
def duplicate_rate_schedule(actor: Any, tariff_id: Any, payload: Any = None) -> dict[str, Any]:
    """DEF-370 · CR-013 part 1, verbatim: *"Duplicate (the normal way to start a
    filing)"*. A utility filing a 2027 rate case starts from the 2026 one.

    The copy is a NEW SCHEDULE carrying a DRAFT version, and both halves of that
    are the rule rather than a convenience:

    · **A new schedule**, so BR-RAT-037 cannot be bypassed. The law is that every
      change to a published object is a new version with a required reason;
      `update_rate_schedule` enforces it by refusing price content once a version
      has been activated. A "duplicate" that wrote a second editable structure
      onto the SOURCE schedule would be a second, reason-free door into exactly
      that. Nothing here touches the source: it is read, and not one of its rows
      is written.
    · **A draft**, so `_guard_base_charge_code`, the completeness gate and the
      window guard all still stand between the copy and being in force. A copy
      activates through `POST …/activate` like anything else, with its own
      effective date, its own label and its own docket.

    `version_id` names WHICH version to copy — a 2027 filing usually starts from
    what is in force today, which is the default, but a utility re-filing a
    superseded sheet asks for that one by id. `name` overrides the generated
    `… (copy)`.

    ── `DEF-RAT-8001` · DOES THIS PATH CLOSE AN OPEN WINDOW? **NO, AND IT MUST
    NOT — TWICE OVER.** ─────────────────────────────────────────────────────
    The copy is a DATELESS DRAFT on a BRAND-NEW schedule, so it opens no window
    (BR-RAT-031) and there is no earlier version of the new tariff to close.
    And closing anything on the SOURCE would be worse than useless: the second
    bullet above is that nothing here writes one of the source's rows.
    """
    payload = _require_dict(payload or {})
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, ("name", "version_id"), fe)
    requested_name = _text(payload, "name", fe, max_length=120)
    version_id = _uuid_value(payload, "version_id", fe)
    _refuse(fe)
    with transaction.atomic():
        source = _lock_schedule(tariff_id)  # CR-157-BRC10: lock first
        if version_id is not None:
            version = models.TariffVersion.objects.filter(
                tenant_id=_tenant_id(), tariff=source, pk=version_id
            ).first()
            if version is None:
                raise errors.NotFoundError()
        else:
            version = (
                selectors.in_force_version(source, seams.tenant_today())
                or selectors.latest_version(source)
                or selectors.draft_version(source)
            )
        if version is None:
            # An identity-only schedule has nothing to copy, and copying its
            # NAME alone would produce a second empty schedule the user then has
            # to delete. Refused by name (US-RAT-005 §6's vocabulary).
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-031",
                message_key="rating.schedules.nothing_to_duplicate",
            )
        name = requested_name or _copy_name(source.name, source.service_id)
        if models.Tariff.objects.filter(
            tenant_id=_tenant_id(), name=name, service_id=source.service_id
        ).exists():
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="rating.schedules.duplicate_name",
                field_errors=[
                    _field_error("name", errors.VAL_FORMAT, "rating.schedules.duplicate_name")
                ],
            )
        copy = models.Tariff.objects.create(
            tenant_id=_tenant_id(),
            name=name,
            service_id=source.service_id,
            account_type_id=source.account_type_id,
            # BR-TEN-057: the sample tag is written by the sample path ONLY. A
            # duplicate of a sample schedule is the utility's own record and
            # must not be deleted by BR-TEN-061's sweep.
            is_sample=False,
        )
        cleaned, structure = _copy_of_version(version)
        new_version = _write_version(copy, cleaned, structure, actor=actor)
        _audit(
            actor,
            "tariff.duplicated",
            "tariff",
            copy.id,
            before=_json_safe(selectors.schedule_card(source)),
            after=_json_safe(selectors.schedule_card(copy)),
        )
        _audit(
            actor,
            "tariff.draft_saved",
            "tariff_version",
            new_version.id,
            after=_json_safe(selectors.version_row(new_version)),
        )
    result = selectors.schedule_detail(copy.id)
    result["notices"] = _schedule_notices(copy, structure)
    return result


@require_role(SYSTEM_ADMIN)
def archive_rate_schedule(actor: Any, tariff_id: Any) -> dict[str, Any]:
    """IS-1 audit-lock (US-RAT-004 TC-4): blocked while any plan references it.
    Archiving stamps `deleted_at` — versions and history stay readable for the
    7-year reproducibility rule (BR-RAT-017)."""
    with transaction.atomic():
        tariff = _lock_schedule(tariff_id)  # CR-157-BRC10: lock first
        plans = selectors.schedule_used_by_plans(tariff)
        if plans:
            # DEF-278 — NAME them. A count is not actionable: "referenced by 3
            # plans" leaves the user opening every plan in the tenant to find
            # which three. The names come from the same query the count came
            # from, capped, with the count kept beside them so the sentence is
            # still true when there are sixty.
            names = selectors.schedule_blocking_plan_names(tariff)
            params = {"plans": plans, "names": ", ".join(names)}
            # Two keys, both written as LITERALS so G32's ast walk can see each
            # one. A conditional expression inside the kwarg would hide both
            # from the gate that exists to prove they resolve.
            if plans <= len(names):
                raise errors.BizError(
                    errors.BIZ_LOCKED,
                    br_ref="BR-RAT-031",
                    message_key="rating.schedules.locked_referenced",
                    params=params,
                )
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-RAT-031",
                message_key="rating.schedules.locked_referenced_many",
                params=params,
            )
        if tariff.deleted_at is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-031",
                message_key="rating.schedules.already_archived",
            )
        before = _json_safe(selectors.schedule_card(tariff))
        tariff.deleted_at = Now()  # DB-side stamp: rating never reads a wall clock
        tariff.save(update_fields=["deleted_at", "updated_at"])
        tariff.refresh_from_db(fields=["deleted_at"])
        _audit(
            actor,
            "tariff.archived",
            "tariff",
            tariff.id,
            before=before,
            after={"status": "archived"},
        )
    return selectors.schedule_detail(tariff.id)


def rate_schedule_count(service_code: str | None = None, uom_code: str | None = None) -> int:
    """The apps/tenancy/seams.py contract (BR-TEN-026/027/029). A read exposed
    on the service module because that is where the seam names it; the query
    itself lives in selectors (LAW 0)."""
    return selectors.rate_schedule_count(service_code=service_code, uom_code=uom_code)


def tax_pricing_gap() -> dict[str, int]:
    """The apps/tenancy/seams.py contract for `DEF-254` — how many tax
    authorities this tenant has and how many are PRICED.

    Exposed on the service module because that is where the seam resolves it by
    name; the query itself lives in selectors (LAW 0). Returns counts only: the
    rate-less scaffold is a PO ruling and nothing here may fill it in.
    """
    return selectors.tax_pricing_gap()


# ══════════════════════════════════════════════════════════════════════════
# Reference-data seeding seam — US-TEN-002 (BR-TEN-012/013/031) · DEF-016
# ══════════════════════════════════════════════════════════════════════════
# THIS FUNCTION IS THE DEF-016 FIX. It did not exist, so tenancy's
# `_seed_reference_data` found no `apps.rating.services.seed_reference_list`,
# honestly skipped `charge_codes` and `tax_jurisdictions` per BR-TEN-013
# skip-until-wired, and reported the skip into a summary nobody read — the S8
# Charge-codes card was empty on every tenant provisioned since W0.
#
# Money law observed here, none of it invented:
#   · Every figure comes from the fixture entry itself; nothing is derived from
#     a rate, a plan or an example. A fixture code with NO figure is NOT
#     created (see below) instead of being stored with a guessed one.
#   · `charges.percent` stores a FRACTION, not percent points (models.Charge +
#     US-RAT-008 TC-3: 1.5 % → 0.015), so a fixture "1.5" is divided by 100.
#     That is a representation change, never a new number.
#   · Values arrive as decimal STRINGS and go straight into Decimal —
#     NUMERIC(18,6), never float, never cents (CLAUDE.md rule 2).
#   · `amount_rule` follows MECHANICALLY from which money keys the fixture
#     states, exactly as rating's own `_validate_charge` requires them:
#     amount ⇒ flat · percent+min_amount ⇒ percent_with_minimum · percent
#     alone ⇒ percent. No other combination is inferred.
#   · A charge with no figure at all cannot be stored: `create_charge` REFUSES
#     a charge without `amount_rule` (rating's own law), and `amount_rule`
#     cannot be chosen without a figure. Those codes are REPORTED by
#     `reference_seed_omissions` below and created by nobody.
#   · TAMPER (PO ruling 2026-08-10) now HAS a platform figure — $250.00 from
#     EP-RAT-03 §4, which the PO chose over the billing workbook's $500.00 and
#     made a platform default. It arrives here as the fixture's decimal string
#     like every other amount; nothing in this file knows or restates it.
#   · `charge_type` is not money and is not inferred either: it is copied only
#     when the fixture STATES it, and only if it is one of CHARGE_TYPES.
_PERCENT_POINTS = Decimal("100")  # fixture states percent POINTS; the column is a fraction


def _charge_money_from_fixture(entry: dict[str, Any]) -> dict[str, Any] | None:
    """The fixture entry's OWN figures, in column representation, or None when
    it states none. Pure — no DB, no writes, so the report path can call it."""
    money: dict[str, Any] = {}
    if entry.get("amount") not in (None, ""):
        money["amount_rule"] = "flat"
        money["amount"] = Decimal(str(entry["amount"]))
        return money
    if entry.get("percent") not in (None, ""):
        money["percent"] = Decimal(str(entry["percent"])) / _PERCENT_POINTS
        if entry.get("min_amount") not in (None, ""):
            money["amount_rule"] = "percent_with_minimum"
            money["min_amount"] = Decimal(str(entry["min_amount"]))
        else:
            money["amount_rule"] = "percent"
        return money
    return None


#: Per-CODE register of charge codes the platform fixture carries on purpose
#: WITHOUT an amount, and the ruling that makes each one deliberate. A code that
#: is not in here and still has no figure falls back to the generic "no ratified
#: figure" reason below — the two are different facts and must not read alike:
#: one is a decision, the other is a gap.
CHARGE_CODES_NOT_SEEDED: dict[str, str] = {
    "DEPO-R": (
        "DELIBERATELY UNSEEDED — this is a RULING, not a missing figure. BR-RAT-020 and "
        "BR-RAT-023 (both CONFIRMED, PO Q&A R1 D6 + R3) put deposits in `plan_deposit_rules` "
        "as a fixed $ per consumer category, PLAN-level, and EXPLICITLY SUPERSEDE the "
        "prototype's single DEPO-R checkbox. A platform-wide DEPO-R amount would therefore "
        "encode a model the Product Owner has already replaced, so the fixture ships the CODE "
        "and its `charge_type` (refundable) and no amount. Deposit amounts are read from the "
        "plan's deposit rules by the customers lane (BR-CUS-023), never from this code."
    ),
    # CR-010 A2 (PO 2026-08-17): DEPO-C arrived in the 25-code set and inherits
    # DEPO-R's ruling wholesale — same rule, commercial category.
    "DEPO-C": (
        "DELIBERATELY UNSEEDED — the same RULING as DEPO-R, for the commercial category. "
        "BR-RAT-020/BR-RAT-023 put deposit amounts in `plan_deposit_rules` per consumer "
        "category and supersede any flat deposit charge; the CODE ships (CR-010 A2, "
        "PO 2026-08-17) so the vocabulary is complete, and the amount lives on the plan."
    ),
}


def reference_seed_omissions(list_code: str, entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """OPTIONAL seam (apps/tenancy/seams.py): the entries this module will NOT
    create, and why. Read-only and side-effect free — it exists so the gap is
    printed and asserted, not discovered later on a live tenant."""
    if list_code == "charge_codes":
        return [
            {
                "entry": str(entry.get("code", "?")),
                "reason": CHARGE_CODES_NOT_SEEDED.get(
                    str(entry.get("code", "")),
                    "the fixture carries this charge CODE with no amount and no percent, "
                    "and rating refuses a charge without an amount_rule (_validate_charge); "
                    "choosing one would be a guessed fee — reported, never invented",
                ),
            }
            for entry in entries
            if _charge_money_from_fixture(entry) is None
            # A `pricing: per_case` code SEEDS (unpriced, CR-010 A2) — it is
            # not an omission, so it does not report as one.
            and str(entry.get("pricing") or "") != "per_case"
        ]
    if list_code == "tax_jurisdictions":
        notes = []
        unseedable = [
            f"{entry.get('name', '?')} · {tax.get('name', '?')}"
            for entry in entries
            for tax in (entry.get("taxes") or [])
            if str(tax.get("kind") or "") == "per_unit"
        ]
        if unseedable:
            notes.append(
                {
                    "entry": ", ".join(unseedable),
                    "reason": (
                        "seeded as a `taxes` row carrying its whole condition, and it prices "
                        "NOTHING yet: BR-RAT-036's per-unit form needs the usage the rating "
                        "seam's TaxRule does not carry, so `plan_tax_rules` skips it rather "
                        "than approximating $0.25/kgal as a percent — a wrong number that "
                        "would look right on a real bill"
                    ),
                }
            )
        if any(entry.get("code") not in (None, "") for entry in entries):
            notes.append(
                {
                    "entry": "code",
                    "reason": (
                        "`tax_jurisdictions` has no code column either (BR-TEN-037 tenant-"
                        "entered registry); the framework's code slot is the NAME, which is "
                        "what this seed matches on"
                    ),
                }
            )
        return notes
    return []


#: DEF-273 (PO ruling 2026-08-18) — the fixture keys a `taxes` entry may state.
#: A key outside this set is a typo or an invented qualifier and REFUSES the
#: seed rather than being dropped: a fixture that silently loses
#: `customer_classes` would seed r10's State Utility Tax with no exemption at
#: all, which is the exact over-charge DEF-273 was filed to prevent.
FIXTURE_TAX_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "kind",
        "rate",
        "flat_amount",
        "flat_frequency",
        "per_unit_amount",
        "per_unit_uom",
        "per_meter_amount",
        "applies_above_units",
        "services",
        "customer_classes",
        "premises_scope",
        "premises_scope_value",
        "remit_to",
        "filing_frequency",
        "gl_code",
    }
)


def _seed_fixture_taxes(
    tenant_id: Any, jurisdiction: Any, entry: dict[str, Any], *, price: bool
) -> int:
    """The `taxes` rows this fixture jurisdiction states, WITH their conditions.

    ── WHY THIS EXISTS (DEF-254 → DEF-273, PO ruling 2026-08-18) ─────────────
    Tax JURISDICTIONS were seeded at provisioning and tax RATES were not, so a
    tenant who declined the sample data issued every bill with no tax at all and
    nothing said so (DEF-254). The PO ruled the figures — *"Tax jurisdiction
    rates (5 TX rows) - already answered"*, then *"I ahve already answered it;
    close it"* — and the answer is prototype r10's own tax table.

    THREE OF THE FIVE COULD NOT BE SEEDED UNTIL TODAY, and that is DEF-273:
    `taxes` carried no customer-class exemption and no premises-geography scope,
    so seeding r10's State Utility Tax as written would have charged **6.25 % to
    every residential customer r10 exempts** and the City Franchise Fee **1.50 %
    to the 61 outside-city accounts r10 exempts**. The columns landed first; this
    function is what fills them.

    ── EVERY FIGURE IS THE FIXTURE'S OWN, AND NOTHING IS DERIVED ─────────────
    The same law `_charge_money_from_fixture` obeys one screen along: values
    arrive as decimal STRINGS and go straight into `Decimal` (NUMERIC(18,6),
    never float, never cents — CLAUDE.md rule 2), and percent POINTS become the
    column's FRACTION (6.25 → 0.062500), which is a representation change and
    never a new number. A tax the fixture states without the figure its own kind
    requires is NOT created; nothing here picks one.

    ── WHAT IS DELIBERATELY *NOT* WRITTEN ────────────────────────────────────
    `gl_code` (r10's 2300–2304) is read and IGNORED. Those are r10's chart
    codes, not this tenant's, and `taxes.liability_gl_account_id` is a uuid into
    the tenant's OWN ledger which B5 line 74 ❄️ says tenant authorities mint for
    themselves (PO 2026-08-12, OQ-145/147). Writing a guessed account would
    remit money to the wrong government. The authorities therefore ship UNMAPPED
    and `rating.sample_data.unmapped_tax_authorities()` already names them — the
    same state seed_demo's own two rates have shipped in since DEF-166.

    A service list is INTERSECTED with the services this tenant enabled, and a
    tax whose ruled services this tenant sells NONE of is skipped entirely.
    Storing an empty list instead would be far worse than skipping: [] means
    "every service" here, so a franchise fee for a utility with no electric and
    no gas would silently attach to their water.
    """
    fixture_taxes = entry.get("taxes") or []
    if not price or not fixture_taxes:
        return 0
    created = 0
    # BR-CUS-094a — the TENANT's own class rows, read ONCE for the whole
    # fixture. This is the one site where the vocabulary sat inside a loop, and
    # hoisting it is what keeps the old seam's reason (b) — "no query in a
    # per-row validator" — true after the source moved from constants to rows.
    selectable_classes = seams.selectable_account_type_codes()
    for spec in fixture_taxes:
        unknown = sorted(set(spec) - FIXTURE_TAX_KEYS)
        if unknown:
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="rating.reference_fixture_invalid",
                params={"list": "tax_jurisdictions", "unknown_tax_keys": ",".join(unknown)},
            )
        name = str(spec.get("name") or "").strip()
        kind = str(spec.get("kind") or "").strip()
        if not name or kind not in TAX_KINDS:
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="rating.reference_fixture_invalid",
                params={"list": "tax_jurisdictions", "tax": name or "?", "kind": kind},
            )
        fields: dict[str, Any] = {"name": name, "kind": kind}
        if kind == "percent":
            if spec.get("rate") in (None, ""):
                continue  # no ratified figure ⇒ no row; nothing is guessed
            fields["rate"] = Decimal(str(spec["rate"])) / _PERCENT_POINTS
        elif kind == "flat_per_bill":
            if spec.get("flat_amount") in (None, ""):
                continue
            fields["flat_amount"] = Decimal(str(spec["flat_amount"]))
            frequency = str(spec.get("flat_frequency") or "").strip()
            if frequency in FLAT_FREQUENCIES:
                fields["flat_frequency"] = frequency
        elif kind == "per_meter":
            if spec.get("per_meter_amount") in (None, ""):
                continue  # no ratified figure ⇒ no row; nothing is guessed
            fields["per_meter_amount"] = Decimal(str(spec["per_meter_amount"]))
        else:  # per_unit
            if spec.get("per_unit_amount") in (None, "") or not spec.get("per_unit_uom"):
                continue  # CLAUDE.md rule 3: a quantity price without its unit is not a price
            fields["per_unit_amount"] = Decimal(str(spec["per_unit_amount"]))
            fields["per_unit_uom"] = str(spec["per_unit_uom"]).strip()
        if spec.get("applies_above_units") not in (None, ""):
            fields["applies_above_units"] = Decimal(str(spec["applies_above_units"]))

        ruled_services = [str(code).strip() for code in (spec.get("services") or [])]
        if ruled_services:
            enabled = [code for code in ruled_services if seams.service_is_enabled(code)]
            if not enabled:
                # This utility sells none of the services the rate applies to.
                # Skipped, NOT stored as [] — see the docstring.
                continue
            fields["applies_to_services"] = enabled

        classes = [str(code).strip().lower() for code in (spec.get("customer_classes") or [])]
        unknown_classes = [code for code in classes if code not in selectable_classes]
        if unknown_classes:
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="rating.reference_fixture_invalid",
                params={"list": "tax_jurisdictions", "customer_classes": ",".join(unknown_classes)},
            )
        if classes:
            fields["applies_to_customer_classes"] = classes

        scope = str(spec.get("premises_scope") or "").strip()
        if scope:
            if scope not in PREMISES_SCOPE_KINDS:
                raise errors.SysError(
                    errors.SYS_INTERNAL,
                    message_key="rating.reference_fixture_invalid",
                    params={"list": "tax_jurisdictions", "premises_scope": scope},
                )
            fields["premises_scope_kind"] = scope
            # DELIBERATELY may be blank. r10 says "Inside city limits" and names
            # no city, so the utility types theirs on S13; until then the fee
            # reaches NOBODY (`plan_tax_rules` fails closed) rather than reaching
            # the 61 outside-city accounts r10 exempts.
            value = str(spec.get("premises_scope_value") or "").strip()
            if value:
                fields["premises_scope_value"] = value

        remit_to = str(spec.get("remit_to") or "").strip()
        if remit_to:
            fields["remit_to"] = remit_to
        filing = str(spec.get("filing_frequency") or "").strip()
        if filing in FILING_FREQUENCIES:
            fields["filing_frequency"] = filing

        models.Tax.objects.create(tenant_id=tenant_id, jurisdiction=jurisdiction, **fields)
        created += 1
    return created


def seed_reference_list(list_code: str, entries: list[dict[str, Any]], fixture_version: str) -> int:
    """The tenancy reference-data seeding seam (contract in apps/tenancy/seams.py).

    Rating owns two S8 lists (BR-TEN-031): `charge_codes` (the S12 catalog) and
    `tax_jurisdictions` (BR-TEN-037 tenant-entered authorities). Writes land in
    THIS module's tables through THIS module's service layer under the caller's
    `app.tenant_id` context — never a cross-module write (BR-TEN-013).

    Per-list idempotent by natural key (BR-TEN-012): `charges.code` case-
    insensitively, `tax_jurisdictions.name` case-insensitively (that table has
    no code column). An existing row is LEFT ALONE — a tenant-touched row is
    never overwritten by a fixture, so a replay writes nothing.

    The one audit row for this write is tenancy's `reference.seeded`
    (BR-TEN-016), written by the caller in the same transaction with the list,
    the fixture version and the count — the same posture apps/assets uses for
    its four lists.
    """
    from apps.rating import discount_lists

    if list_code in discount_lists.REFERENCE_LISTS:
        # CR-166-BRC10 — the three discount lists seed from the DRAWING's
        # values, held in rating's own constant (the `bank_rec_difference_
        # reasons` posture), never from the platform fixture: they are rating's
        # vocabulary and one copy of them is enough. `seed_lists` seeds all
        # three insert-missing, so the second and third calls create nothing.
        return discount_lists.seed_lists()
    if list_code not in ("charge_codes", "tax_jurisdictions"):
        raise KeyError(f"rating owns no reference list {list_code!r} (BR-TEN-031)")
    tenant_id = _tenant_id()
    created = 0
    #: DEF-273 / DEF-247 — THE SET-SKIP, EVALUATED ONCE, BEFORE ANYTHING IS
    #: WRITTEN. A tenant that already holds ANY `taxes` row has priced its own
    #: taxes and is given none by a fixture (BR-TEN-012). Computed here rather
    #: than inside the loop for the obvious reason: the first entry this call
    #: creates would otherwise turn the flag off for the second, and the tenant
    #: would receive one of the five rates and not the other four.
    #:
    #: THE RULE IS ABOUT THE SET AND NOT ABOUT NAMES, and that is DEF-166/247
    #: written down twice already: two seeders naming the same rate differently
    #: is the NORMAL case, and it is how a demo tenant came to carry four
    #: percent rules and tax every bill at 16.5% where its own rates say 8.25%.
    seed_rates = (
        list_code == "tax_jurisdictions"
        and not models.Tax.objects.filter(tenant_id=tenant_id).exists()
    )
    for entry in entries:
        name = str(entry.get("name", "")).strip()
        if not name:
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="rating.reference_fixture_invalid",
                params={"list": list_code},
            )
        if list_code == "tax_jurisdictions":
            # BR-TEN-037: the jurisdiction IS its name here; `level`/`authority`
            # stay NULL unless the fixture states them — "Local" gets no guessed
            # county/city split (the same call seed_demo's TAX_RULES makes).
            jurisdiction = models.TaxJurisdiction.objects.filter(
                tenant_id=tenant_id, name__iexact=name
            ).first()
            if jurisdiction is None:
                fields: dict[str, Any] = {"name": name}
                level = str(entry.get("level") or "").strip()
                if level in JURISDICTION_LEVELS:
                    fields["level"] = level
                authority = str(entry.get("authority") or "").strip()
                if authority:
                    fields["authority"] = authority
                jurisdiction = models.TaxJurisdiction.objects.create(tenant_id=tenant_id, **fields)
                created += 1
            created += _seed_fixture_taxes(tenant_id, jurisdiction, entry, price=seed_rates)
            continue

        code = str(entry.get("code", "")).strip()
        if not code:
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="rating.reference_fixture_invalid",
                params={"list": list_code},
            )
        money = _charge_money_from_fixture(entry)
        if money is None and str(entry.get("pricing") or "") != "per_case":
            continue  # no ratified figure ⇒ no row (reported by the seam above)
        if money is None:
            # CR-010 A2 (PO 2026-08-17): a code the fixture marks
            # `pricing: per_case` is RATIFIED AS UNPRICED — "actual cost,
            # entered per case" was on the table the PO confirmed. It seeds as
            # a catalog row with NO amount_rule and NO figure, so nothing here
            # invents a fee (DEF-016's law holds) and the S12 card shows the
            # code a clerk prices at use time. Absence of a figure WITHOUT the
            # marker still means "nobody priced it" and still refuses — the
            # marker is what keeps a ruling and a gap from reading alike.
            #
            # DEF-2340 (PO 2026-10-01, option A, point 3): the row now SAYS so —
            # `amount_rule = per_case`, *entered when used*, with no price row —
            # so a one-time Fee bill takes the clerk's typed amount for it
            # (`billing.fee_bill.charge_code_line`) and R4 names the true
            # reading instead of both. Existing tenants move by `rating/0055`.
            money = {"amount_rule": AMOUNT_RULE_PER_CASE}
        if models.Charge.objects.filter(tenant_id=tenant_id, code__iexact=code).exists():
            continue  # BR-TEN-012: tenant-touched rows are never overwritten
        fields: dict[str, Any] = {"code": code, "name": name, **money}
        # `charge_type` is the S12 four-card classification. It used to be left
        # NULL here because the fixture stated none, so every platform-seeded
        # charge landed unclassified and only the demo seeder filled it in. The
        # fixture now CARRIES the confirmed class per code (PO 2026-08-10), so
        # it is copied like any other stated field — validated against rating's
        # own value set, never widened by a fixture.
        charge_type = str(entry.get("charge_type") or "").strip()
        if charge_type:
            if charge_type not in CHARGE_TYPES:
                raise errors.SysError(
                    errors.SYS_INTERNAL,
                    message_key="rating.reference_fixture_invalid",
                    params={"list": list_code, "charge_type": charge_type},
                )
            fields["charge_type"] = charge_type
        # CR-156-BRC10 — the platform fixture's codes arrive classified by the
        # PO's own list (base · plan · other); `amount` in `fields` is routed by
        # `Charge.amount`'s setter to an *All sizes* row from the epoch.
        fields["kind"] = default_kind(code, fields.get("charge_type"), False)
        # `DEF-PAY-10698` — the fixture DECLARES which code is the NSF fee; the
        # code string is never read for it.
        if entry.get("is_nsf_fee") is True:
            fields["is_nsf_fee"] = True
        models.Charge.objects.create(tenant_id=tenant_id, **fields)
        created += 1
    return created


# ══════════════════════════════════════════════════════════════════════════
# CR-066 — POINT EVERY SEEDED CHARGE CODE AND DISCOUNT AT AN ACCOUNT
# ══════════════════════════════════════════════════════════════════════════
def apply_default_gl_accounts(actor: Any = None) -> dict[str, Any]:
    """Fill the NULL `gl_account_id` of every charge code and discount that has
    a platform default — CR-066 tasks A2, A3 and B2. Idempotent.

    Returns `{"charges_mapped": n, "charges_unmapped": [codes],
    "discounts_mapped": n, "skipped_reason": str | None}`.

    ⚠ **WHY THIS FUNCTION EXISTS AND WHAT IT COSTS WHEN IT DOES NOT: `DEF-2386`.**
    `apps/billing/issue.py` resolves a bill line's GL account by KIND. A USAGE or
    BASE line resolves from the SERVICE's designation and never looks at a charge
    code; a FEE line resolves `charges.gl_account_id` and **refuses the whole
    bill** when it is null. The platform seed had never written that column, so
    every tenant this product has ever provisioned held **28 charge codes
    pointing nowhere** — measured on PostgreSQL 16 on 2026-09-02, beside a
    Settings screen correctly reporting it and a sample estate that issued 95
    invoices anyway, because every line it writes is usage or base. **That
    asymmetry is why nobody saw it.** And two seeded codes (`PAPER`, `HYDRANT`)
    are `recurring`, which `BR-RAT-117` puts on the ordinary bill of every tenant
    that configures one — so one unmapped recurring charge refuses a whole run.

    ⚠ **`BR-TEN-012` — A ROW A TENANT HAS SET IS NEVER TOUCHED.** The filter is
    `gl_account_id__isnull=True` and there is no other branch. A utility that
    files its after-hours calls in its own account has made a decision, and a
    re-run that overwrote it would be a seed quietly undoing a clerk. That is
    also what makes this safe to call from the repair door as often as anyone
    likes.

    ⚠ **A CODE WITH NO PLATFORM DEFAULT KEEPS ITS NULL AND IS REPORTED.** A
    tenant's OWN charge code is theirs to map; inventing an account for it would
    post their money somewhere nobody chose. The returned `charges_unmapped`
    list is what the caller records, and the Accounting screen goes on saying so.
    """
    tenant_id = _tenant_id()
    charges_mapped = 0
    unmapped: list[str] = []
    for charge in models.Charge.objects.filter(
        tenant_id=tenant_id, gl_account_id__isnull=True
    ).select_related("service"):
        account_id = seams.ledger_default_gl_account_id_for_charge(
            charge.code,
            service=getattr(charge.service, "code", None),
            is_base=bool(charge.is_base),
        )
        if not account_id:
            unmapped.append(charge.code)
            continue
        charge.gl_account_id = account_id
        charge.save(update_fields=["gl_account_id", "updated_at"])
        charges_mapped += 1

    discount_account_id = seams.ledger_default_gl_account_id_for_discount()
    discounts_mapped = 0
    if discount_account_id:
        for discount in discount_models.Discount.objects.filter(
            tenant_id=tenant_id, gl_account_id__isnull=True
        ):
            discount.gl_account_id = discount_account_id
            discount.save(update_fields=["gl_account_id", "updated_at"])
            discounts_mapped += 1

    if charges_mapped or discounts_mapped:
        # CLAUDE.md hard rule 7. WHERE a fee's money lands is a money decision
        # even when the account chosen is the one the PO approved on a table —
        # this is the row a finance reviewer reads to see what the seed decided
        # and when, and `_map_tender_clearing_accounts` writes the same shape
        # one module over for the same reason.
        _audit(
            actor,
            "reference.charge_gl_mapped",
            "charge",
            None,
            after={
                "charges_mapped": charges_mapped,
                "charges_unmapped": sorted(unmapped),
                "discounts_mapped": discounts_mapped,
                "discount_account": chart_default_discount_code(),
                # THE RULING, VERBATIM, LIVES HERE AND IN THE DECISION LOG — not
                # in the payload, because S61 renders a payload value to a clerk
                # (DEF-2377). CR-066, PO 2026-09-02: *"Table 1 - the 28 charge
                # codes - these are all correct - you can apply them as part of
                # Seed data"* / *"Please apply these - Table 3 - discounts."* The
                # PO approved the MAPPING; the nine new accounts are not
                # finance-signed (`chart.PENDING_FINANCE_RE_SIGN`).
                "br_ref": "CR-066",
                "decided": (
                    "the charges and discounts were filed to the accounts the utility "
                    "approved; nine of those accounts are not finance-signed yet"
                ),
            },
        )
    return {
        "charges_mapped": charges_mapped,
        "charges_unmapped": sorted(unmapped),
        "discounts_mapped": discounts_mapped,
        "skipped_reason": None,
    }


def set_discount_gl_account(actor: Any, discount_id: Any, payload: Any) -> dict[str, Any]:
    """Point ONE discount at a GL account, or clear the pointer — CR-066 B3.

    `PATCH /discounts/{id}/gl-account` with `{"gl_account_id": "<uuid>" | null}`.

    ⚠ **WHY THIS IS NOT `PATCH /discounts/{id}`, AND THE DISTINCTION IS A RULE
    RATHER THAN A ROUTE STYLE.** There is no `update_discount` anywhere in this
    module and `apps/rating/api.py` says why in its own words: BR-RAT-078 makes
    enrolments survive versioning and CR-013's shared rules make an edit **a NEW
    DATED VERSION**, so a general PATCH would be a route inviting exactly the
    in-place overwrite that rule forbids. **A GL account is not part of the
    priced agreement.** It moves no money, changes no customer's reduction and
    belongs to the same family as `charges.gl_account_id` and
    `taxes.liability_gl_account_id` — a mapping a utility's bookkeeper re-points
    on Settings → Accounting. So it is its own narrow door, and the versioned
    door stays the only way to change what a discount is WORTH.

    The account is validated as THIS tenant's and still live at the moment it is
    picked (`_validated_gl_account`, CR-008 ruling 3) — an FK would prove a row
    exists and never prove whose it is. `null` clears the pointer, which is a
    real thing to do: the `discount_contra_revenue` designation still answers at
    issue, so clearing restores the product's own default rather than breaking
    anything.

    Hard rule 7 — the change is audited with its before and after.
    """
    # ONE lookup, the module's own — `discount_or_404` already answers 404 for
    # a row that is absent AND for one that belongs to another tenant, which
    # HR-1 makes the same answer on purpose.
    discount = selectors.discount_or_404(discount_id)
    body = payload if isinstance(payload, dict) else {}
    if "gl_account_id" not in body:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            field_errors=[
                _field_error(
                    "gl_account_id",
                    errors.VAL_REQUIRED,
                    "rating.discounts.gl_account_required",
                )
            ],
        )
    fe: list[dict[str, Any]] = []
    account_id = _validated_gl_account(
        body, "gl_account_id", fe, message_key="rating.discounts.gl_account_unknown"
    )
    _refuse(fe)
    before_value = str(discount.gl_account_id) if discount.gl_account_id else None
    discount.gl_account_id = account_id
    discount.save(update_fields=["gl_account_id", "updated_at"])
    _audit(
        actor,
        "discount.gl_account_updated",
        "discount",
        str(discount.id),
        before={"gl_account_id": before_value},
        after={"gl_account_id": str(account_id) if account_id else None},
    )
    return selectors.discount_row(discount)


def chart_default_discount_code() -> str:
    """The chart CODE every discount starts at, named once for the audit row.

    Read through the seam rather than imported so this module states no ledger
    number of its own — `4760` lives in `apps/ledger/chart.py` and nowhere else,
    which is what keeps CR-061's renumbering a one-file act.
    """
    return str(seams.ledger_discount_default_account_code() or "")


# ══════════════════════════════════════════════════════════════════════════
# Charge codes — US-RAT-008 (EP-RAT-03)
# ══════════════════════════════════════════════════════════════════════════
CHARGE_FIELDS: tuple[str, ...] = (
    "code",
    "name",
    "charge_type",
    "service",
    "amount_rule",
    "amount",
    "percent",
    "min_amount",
    "max_amount",
    "gl_account_id",
    #: BR-RAT-088 (DEF-372). `Charge.is_base` and `_guard_base_charge_code` both
    #: shipped without a way to SET the flag, so no tenant could ever adopt the
    #: declared-base model and the gate was unreachable by construction. It is a
    #: plain boolean like the four below it — the model's own docstring already
    #: rules that it is DECLARED and never inferred from the code string.
    "is_base",
    "taxable_default",
    "auto_apply",
    "waivable",
    "separate_line",
    #: BR-RAT-108 (PO ruling 2026-08-21) — WHICH customers this code prices.
    #: The third narrowing dimension beside service and meter size, and the one
    #: that lets a tenant state a $8.00 residential base and a $15.00 commercial
    #: one for the SAME service. NULL/[] = every class.
    "applies_to_customer_classes",
    #: BR-RAT-690 (DEF-2190) — the SECOND narrowing dimension, and the one that
    #: had no writer at any layer until today. `charge_code_amounts` shipped
    #: with a model, a migration and four readers, and `CHARGE_FIELDS` carried
    #: no key for it, so BR-RAT-088's own worked example — a 5/8" water base at
    #: $8.00 and a 2" at $34.00 on ONE code — could not be expressed by any
    #: utility. NOT a column on `charges`: it is a list of rows on a child
    #: table, so `create_charge`/`update_charge` pop it before `setattr`.
    "size_amounts",
    #: ── CR-156-BRC10 (PO 2026-10-01) ────────────────────────────────────
    #: `kind` — base | plan | other (*"can we have 3 kinds"*). The two dates
    #: are the PRICE's, not the code's: *"we will need start and effective
    #: date"* — *Effective from* required on Add and on every Edit that moves
    #: a price, *Effective to* optional (blank = no end). Neither is a column
    #: on `charges`; they date the rows `charge_prices.save_prices` writes.
    "kind",
    "effective_from",
    "effective_to",
    #: DEF-RAT-8753 — a penalty's percent and minimum PER CUSTOMER CLASS,
    #: `[{customer_class, percent (a fraction), min_amount}]`. Stored as dated
    #: terms rows in `charge_code_amounts` (`charge_prices.ClassTerms`).
    "class_terms",
    #: 🔒 PO ruling 2026-10-06 11 (a) — a PENALTY code's late-fee grace
    #: (BR-BIL-008 0–30 days, BR-BIL-002 calendar | business). Columns on
    #: `charges`; NULL on any other type.
    "grace_days",
    "grace_mode",
    #: 🔒 PO rulings 2026-10-06 (`DEF-CUS-9819`) — the utility's ONE application
    #: fee code, added automatically to every new service request at its live
    #: price. A behaviour flag, so NOT in `CHARGE_MONEY_FIELDS` below.
    "is_application_fee",
    #: 🔒 `DEF-PAY-10698` (PO 2026-10-30) — this code is a returned-payment
    #: (NSF) fee: a bounce charges the one the account's plan lists. A
    #: behaviour flag; the price is the code's own, so not a money field.
    "is_nsf_fee",
)

#: ── BR-RAT-1016 · WHAT COUNTS AS MONEY ON A CHARGE CODE ─────────────────────
#:
#: The fields that decide what a customer is BILLED, as opposed to how a line
#: behaves or what it is called. `update_charge` requires a written reason
#: before any of these MOVES on a code that is in use, and writes the move into
#: `rate_change_log` — which is `BR-RAT-037`'s discipline, applied to the object
#: `BR-RAT-088` made the owner of the base amount.
#:
#: ⚠ **`size_amounts` IS HERE AND THE BRIEF NAMED ONLY THE FIVE SCALARS.**
#: `BR-RAT-690` makes a per-size table *the flat rule's amount, stated once per
#: size* — `CR-063`'s going-live fire customer bills `$60.00` for one 6" line
#: and `$12.00` for each 2", entirely out of this table — so leaving it out
#: would guard one of two routes to the same money. That is the exact shape of
#: `DEF-RAT-4832` one object over, where a count of one of two routes read `0`
#: over a code pricing every connection on its service.
#:
#: ⚠ **AND THE BEHAVIOUR FLAGS ARE DELIBERATELY ABSENT.** `taxable_default`,
#: `auto_apply`, `waivable` and `separate_line` change how a line behaves, and
#: `code`/`name`/`gl_account_id` change what it is called and where it posts.
#: The tax lane drew this same boundary at `TAX_RATE_HISTORY_FIELDS` and
#: recorded WHY in the decision log: a rule that demanded a filing record to
#: tick a checkbox is the over-application that gets a rule quietly disabled by
#: the next lane that finds it inconvenient.
CHARGE_MONEY_FIELDS: tuple[str, ...] = (
    "amount_rule",
    "amount",
    "percent",
    "min_amount",
    "max_amount",
    "size_amounts",
    "class_terms",
    #: 🔒 2026-10-06 11 (a) — grace decides WHETHER a late fee is billed on a
    #: given day, so moving it on a code in use is a reasoned, logged change.
    "grace_days",
    "grace_mode",
)


def charge_is_in_use(used: dict[str, Any]) -> bool:
    """Has this code ever priced anything — `BR-RAT-1016`'s verb-1 boundary.

    Three routes, and all three count, because all three mean a figure typed
    here reaches a bill:

    * `plans` — a plan NAMES the code through `plan_charge_rules`;
    * `schedules` — `BR-RAT-088`'s second route, which has no join table at
      all: a code that declares itself its service's base is read by every
      schedule on that service, and `charge_used_by` counted zero for exactly
      that case until `_charge_is_base_for_schedules` was written;
    * `invoice_lines` — it is already on issued bills.

    ⚠ **`invoice_lines is None` MEANS *BILLING COULD NOT ANSWER* AND LOCKS —
    `DEF-079`'s reading, kept verbatim.** That defect is what happens when a
    lock reads *I do not know* as *nobody*: the seam answered `0` for a month
    while charge codes were appearing on real bills, and `BR-RAT-035`'s audit
    lock never engaged once. Failing closed costs an operator one typed
    sentence; failing open costs a price move with no record of why.
    """
    return selectors.charge_in_use(used)


def _stored_size_money(charge: Any) -> dict[tuple[str, str | None], Any]:
    """This code's CURRENT price statement, keyed by the pair that identifies
    a row — `(size_class, customer_class)`, `CR-087` A1's key and not the size
    alone. Since `CR-156-BRC10` the flat amount is one of these keys —
    `(ALL_SIZES, None)` — so one comparison covers both routes to the money.
    Read through `charge_prices` (the one place the table is read)."""
    if charge is None:
        return {}
    return charge_prices.live_prices(charge)


def price_target(charge: Any, cleaned: dict[str, Any]) -> dict[tuple[str, str | None], Any]:
    """The price statement this validated payload asks for, PATCH semantics.

    `amount` is the every-class *All sizes* row (`CR-156-BRC10`, option A);
    `size_amounts` is every other row, *All sizes* by class included. A key
    the payload leaves out keeps what is stored — except that a posted
    `size_amounts` REPLACES the stored sized set (the screen posts what it
    shows), as `BR-RAT-690` always did. The stored flat amount is KEPT beside
    a posted size table unless `amount` is posted too, so moving a code from
    flat to sized still has to clear the scalar in the same write — and the
    *flat and sizes* refusal below still fires when it does not.
    """
    live = _stored_size_money(charge)
    if "size_amounts" in cleaned:
        target = {
            (row["size_class"], row.get("customer_class")): row["amount"]
            for row in cleaned["size_amounts"]
        }
        if (ALL_SIZES, None) not in target and (ALL_SIZES, None) in live:
            target[(ALL_SIZES, None)] = live[(ALL_SIZES, None)]
        # DEF-RAT-8753 — the per-class TERMS rows are a different statement
        # from the size table; a posted size table leaves them alone.
        for key, value in live.items():
            if isinstance(value, charge_prices.ClassTerms) and key not in target:
                target[key] = value
    else:
        target = dict(live)
    if "amount" in cleaned:
        if cleaned["amount"] is None:
            target.pop((ALL_SIZES, None), None)
        else:
            target[(ALL_SIZES, None)] = cleaned["amount"]
    if "class_terms" in cleaned:
        # DEF-RAT-8753 — a posted `class_terms` REPLACES the stored terms rows
        # (the screen posts what it shows), exactly as `size_amounts` does.
        target = {
            key: value
            for key, value in target.items()
            if not isinstance(value, charge_prices.ClassTerms)
        }
        for row in cleaned["class_terms"]:
            target[(ALL_SIZES, row["customer_class"])] = charge_prices.ClassTerms(
                percent=row["percent"], minimum=row["min_amount"]
            )
    if cleaned.get("amount_rule") == AMOUNT_RULE_PER_CASE:
        # 🔒 HUMAN-REVIEW-PENDING (DEF-RAT-9807). Moving a code to `per_case`
        # closes (logically kills) every price it
        # stated, from Effective from — EXCEPT the one optional default
        # (`BR-RAT-1054` AMENDED 2026-10-06, PO option (a), `DEF-RAT-9807`): a
        # posted `amount` is kept as the *All sizes* row, which a clerk's
        # screen starts the fee at and the clerk may change. No `amount` key,
        # or `amount: null`, is no default — exactly the old behaviour.
        default = cleaned.get("amount")
        target = {} if default is None else {(ALL_SIZES, None): default}
    return target


def _prices_move(charge: Any, cleaned: dict[str, Any]) -> bool:
    """Does this payload change the code's price rows — an amount, a size, a
    class, or the end date of the statement?"""
    if (
        "amount" not in cleaned
        and "size_amounts" not in cleaned
        and "class_terms" not in cleaned
        and "effective_to" not in cleaned
        and cleaned.get("amount_rule") != AMOUNT_RULE_PER_CASE
    ):
        return False
    live = _stored_size_money(charge)
    target = price_target(charge, cleaned)
    if set(live) != set(target):
        return True
    for key, amount in target.items():
        if not charge_prices._same(live[key], amount):
            return True
    if "effective_to" in cleaned and charge is not None:
        ends = charge_prices.live_effective_to(charge)
        if any(ends.get(key) != cleaned["effective_to"] for key in target):
            return True
    return False


def charge_money_moves(charge: Any, cleaned: dict[str, Any]) -> bool:
    """Does this validated payload change what a customer is BILLED?

    ⚠ **THE TEST IS WHETHER THE FIGURE MOVED, NEVER WHETHER THE KEY WAS SENT**,
    and the two neighbours in this file take the opposite posture for a reason
    that does not apply here. `update_tax` blocks on `set(payload) &
    TAX_RATE_HISTORY_FIELDS` and `update_plan` on `set(payload) &
    PLAN_CONTENT_FIELDS` — both correct, because on those objects a published
    edit of any content IS a version.

    Here, `ChargeCodeWizard` PATCHes the WHOLE draft on every save, so a
    key-based rule would demand a written reason to fix a spelling mistake in a
    charge code's NAME. A rule that fires on work it was not written for is a
    rule the next lane routes around.

    Decimal comparison is NUMERIC, so `Decimal("2.000000")` (what the column
    holds) and `Decimal("2.00")` (what the payload validated to) are the same
    figure and not a move — which is what makes re-saving an unchanged form
    free.
    """
    if _prices_move(charge, cleaned):
        return True
    for field in CHARGE_MONEY_FIELDS:
        if field in ("amount", "size_amounts", "class_terms") or field not in cleaned:
            continue
        if cleaned[field] != getattr(charge, field, None):
            return True
    return False


def _customer_class_list(
    payload: dict[str, Any], field: str, fe: list[dict[str, Any]]
) -> list[str]:
    """An INCLUSION list of platform `account_types` codes; `[]` = every class.

    Extracted 2026-08-21 when BR-RAT-108 gave `charges` the same dimension
    `taxes` already had. It was a 25-line block inside the tax validator; two
    copies of a rule that refuses a typo'd customer class is exactly how the two
    objects end up disagreeing about what a valid class is.

    INCLUSION rather than exclusion, per DEF-273: a class nobody listed is
    simply not in it, where an exclusion list silently WIDENS every time a
    tenant adds a class. And an unknown code is refused rather than dropped — a
    silently-vanished restriction leaves an object the utility believes is
    scoped applying to everybody.
    """
    raw = payload.get(field) or []
    if not isinstance(raw, list):
        fe.append(_field_error(field, errors.VAL_FORMAT, "rating.taxes.classes_not_list"))
        return []
    # BR-CUS-094a — the TENANT's own rows decide, not a constant. Read ONCE for
    # the whole list rather than per element: the query is what reason (b) of
    # the old seam's docstring was protecting, and hoisting it is the answer.
    selectable = seams.selectable_account_type_codes()
    classes: list[str] = []
    for index, code in enumerate(raw):
        value = str(code).strip().lower()
        if value not in selectable:
            fe.append(
                _field_error(
                    f"{field}[{index}]",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "rating.taxes.unknown_customer_class",
                )
            )
            continue
        if value not in classes:
            classes.append(value)
    return classes


def _stored_size_amounts(charge: Any) -> list[dict[str, Any]]:
    """This code's live SIZED rows as stored (the *All sizes* row excluded —
    it is not a size a meter can be). `[]` for a new code."""
    if charge is None:
        return []
    return [
        {"size_class": size_class, "amount": amount}
        for (size_class, _class), amount in sorted(
            _stored_size_money(charge).items(), key=lambda item: (item[0][0], item[0][1] or "")
        )
        if size_class != ALL_SIZES
    ]


def _validate_size_amounts(
    raw: Any, fe: list[dict[str, Any]], *, charge: Any = None
) -> list[dict[str, Any]]:
    """DEF-2190 · BR-RAT-690 — the charge code's PER-SIZE amounts, validated.

    `charge_code_amounts` had a model, a migration and four readers and **no
    writer outside a test**, so BR-RAT-088's own worked example could not be
    expressed by any utility: a **5/8" water base at $8.00 and a 2" at $34.00
    on ONE charge code**. This is the validator that lets a tenant say it.

    THREE STATES, AND KEEPING THEM APART IS THE WHOLE JOB (DEF-277)
    ---------------------------------------------------------------
    `DEF-277` was filed for a base *"coerced to 0.00 using `or` rather than `is
    None`, so an omitted base, an absent size and a deliberately-typed zero are
    indistinguishable"*. All three survive this function unmixed:

      * **no row for a size**  — the size is not in the posted list at all.
        Nobody has priced it. R4 refuses by name (*"states no amount for
        connection size"*), it does not bill $0.00.
      * **a row with a NULL amount** — the size IS listed and IS NOT SERVED.
        `code.amounts[size] is None` in `resolve_charge_codes`, which refuses.
      * **a row with `0.0000`** — a PRICE. The connection is served free, and
        the bill carries a $0.00 line rather than refusing.

    So a blank amount is passed through as `None` and never as `Decimal("0")`,
    and `_decimal` is only asked about a value that is actually there — an
    empty string reaching `_decimal` would be refused as *"Enter a number"*,
    which would make *"this size is not served"* unsayable.

    THE SIZE IS CHOSEN, NEVER TYPED — AND A RETIRED SIZE STILL SAVES
    ----------------------------------------------------------------
    `size_class` is TEXT and not an FK, and `ChargeCodeAmount`'s own docstring
    gives the reason: *"A size Settings RETIRES must not vanish from a schedule
    that already priced it — CR-013's own reading of 'tie it correctly' — and a
    text key is what makes that possible."* A pure existence check against the
    live list would refuse exactly that case.

    ⚠ **AND NO CHECK AT ALL IS THE OTHER HALF OF DEF-2190.** A size typed as
    `W58` where the tenant configured `W-58` stores a row nothing will ever look
    up: the meter resolves `W-58`, R4 finds no amount for it, and the bill
    refuses — for a base the utility believes it priced. Silent, and only
    visible on billing day.

    **So the allowed set is the UNION of the tenant's ACTIVE configured sizes
    and the sizes this code has ALREADY stored.** A new size must be one a meter
    can actually be; a size already priced here keeps saving after Settings
    retires it. `_validate_size_rows` one screen across takes the weaker posture
    (no check at all) and states its reason — this is that reason honoured
    without its cost, and the divergence is deliberate rather than an oversight.
    The codes come from `seams.configured_size_class_codes()`, which reads the
    SAME rows `/lookups/service_size_classes` publishes — the list the
    connection-size control on AST-05 and the rate-schedule size matrix both
    offer — so a size that saves here is a size a meter can be given.
    """
    rows: list[dict[str, Any]] = []
    if raw is None:
        return rows  # an explicit empty set: this code does not vary by size
    if not isinstance(raw, list):
        fe.append(_field_error("size_amounts", errors.VAL_FORMAT, "rating.size_rows.not_list"))
        return rows
    allowed = set(seams.configured_size_class_codes())
    allowed.update(row["size_class"] for row in _stored_size_amounts(charge))
    #: CR-156-BRC10 — the reserved *All sizes* row, for a code priced by
    #: customer class rather than by size (*"these services can be saved either
    #: on customer class or asset class"*). Not a size a meter can be.
    allowed.add(ALL_SIZES)
    #: BR-CUS-094a — the TENANT's own class rows, read ONCE above the loop.
    #:
    #: ⚠ **`customer_class` WAS VALIDATED AGAINST NOTHING AT ALL UNTIL
    #: 2026-09-17, WHICH IS ASYMMETRIC WITH THE TWO COLUMNS EITHER SIDE OF IT.**
    #: `size_class` three lines below is refused unless it is a served size, and
    #: `applies_to_customer_classes` on the same object refuses an unknown code
    #: by name — but the SECOND narrowing dimension took any string up to 60
    #: characters. DEF-273's reasoning applies here exactly and it is a money
    #: one: a typo'd `residental` row is stored, matches no account ever, and
    #: the customer it was written for is silently billed the every-class amount
    #: — a $45.00 connection fee where the utility typed $85.00, with no error
    #: anywhere. It is REFUSED rather than dropped for the same reason.
    selectable_classes = seams.selectable_account_type_codes()
    seen: set[str] = set()
    for index, item in enumerate(raw):
        prefix = f"size_amounts[{index}]."
        if not isinstance(item, dict):
            fe.append(_field_error(prefix, errors.VAL_FORMAT, "rating.size_rows.not_object"))
            continue
        _reject_unknown(item, ("size_class", "amount", "customer_class"), fe, prefix=prefix)
        size_class = _text(item, "size_class", fe, required=True, max_length=60, prefix=prefix)
        #: CR-087 A1 — the SECOND narrowing dimension. Optional, and absent
        #: means EVERY class (`ChargeCodeAmount.customer_class`'s own rule), so
        #: every payload written before this column keeps its meaning.
        customer_class = _text(item, "customer_class", fe, max_length=60, prefix=prefix)
        customer_class = customer_class or None
        if customer_class is not None and customer_class.lower() not in selectable_classes:
            fe.append(
                _field_error(
                    f"{prefix}customer_class",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "rating.taxes.unknown_customer_class",
                )
            )
            continue
        # `_decimal` is asked ONLY when a real value is present. `None` and `""`
        # both mean "not served" and must not be read as a malformed number.
        amount_given = item.get("amount")
        amount = (
            None
            if amount_given is None or (isinstance(amount_given, str) and not amount_given.strip())
            else _decimal(item, "amount", fe, minimum=Decimal("0"), prefix=prefix)
        )
        if size_class is None:
            continue
        if size_class not in allowed:
            fe.append(
                _field_error(
                    f"{prefix}size_class",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "rating.charges.unknown_size_class",
                    size_class=size_class,
                )
            )
            continue
        #: ⚠ THE KEY IS THE PAIR, NOT THE SIZE (CR-087 A1). Before the class
        #: column a repeated size WAS a duplicate; now `W-58` for every class
        #: and `W-58` for Commercial are two legitimate rows, and only the same
        #: PAIR twice is the 500 this refusal exists to turn into a field error.
        key = (size_class, customer_class)
        if key in seen:
            fe.append(
                _field_error(
                    f"{prefix}size_class",
                    errors.VAL_FORMAT,
                    "rating.size_rows.duplicate_size",
                    size_class=size_class,
                )
            )
            continue
        seen.add(key)
        rows.append(
            {"size_class": size_class, "amount": amount, "customer_class": customer_class}
        )
    return rows


def _validate_class_terms(raw: Any, fe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """🔒 `DEF-RAT-8753` — a penalty's percent and minimum per customer class.

    `[{customer_class, percent, min_amount}]`; `percent` is a FRACTION
    (`0.015` = 1.50%) exactly as `charges.percent` is, so the screen's
    conversion is the one it already makes; `min_amount` blank = no floor.
    The class is the tenant's own (`seams.selectable_account_type_codes`) and
    appears once. An empty list clears the terms (the code goes back to its one
    percent). Worked, the mock-up's `LATE`: Residential 0.015 / 5.00,
    Commercial 0.020 / 10.00.
    """
    rows: list[dict[str, Any]] = []
    if raw is None:
        return rows
    if not isinstance(raw, list):
        fe.append(_field_error("class_terms", errors.VAL_FORMAT, "rating.size_rows.not_list"))
        return rows
    selectable = seams.selectable_account_type_codes()
    seen: set[str] = set()
    for index, item in enumerate(raw):
        prefix = f"class_terms[{index}]."
        if not isinstance(item, dict):
            fe.append(
                _field_error(f"class_terms[{index}]", errors.VAL_FORMAT, "rating.size_rows.not_list")
            )
            continue
        cls = str(item.get("customer_class") or "").strip().lower()
        if not cls:
            fe.append(_field_error(f"{prefix}customer_class", errors.VAL_REQUIRED, "rating.required"))
            continue
        if cls not in selectable:
            fe.append(
                _field_error(
                    f"{prefix}customer_class",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "rating.taxes.unknown_customer_class",
                )
            )
            continue
        if cls in seen:
            fe.append(
                _field_error(f"{prefix}customer_class", errors.VAL_FORMAT, "rating.charges.class_twice")
            )
            continue
        seen.add(cls)
        percent = _decimal(item, "percent", fe, required=True, minimum=Decimal("0"), prefix=prefix)
        given = item.get("min_amount")
        minimum = (
            None
            if given is None or (isinstance(given, str) and not given.strip())
            else _decimal(item, "min_amount", fe, minimum=Decimal("0"), prefix=prefix)
        )
        if percent is None:
            continue
        rows.append({"customer_class": cls, "percent": percent, "min_amount": minimum})
    return rows


def _effective_from_or_today(value: date | None) -> date:
    """⚠ INTERIM (CR-156-BRC10 §7, coordinator 2026-10-01): a price save that
    names no Effective from takes the tenant's TODAY — what the pre-dates
    wizard's save always meant (*the price applies now*). A stated date always
    wins. Retire this when every caller sends the date (wave B's screens do)."""
    return value if value is not None else seams.tenant_today()


def _write_prices(
    charge: Any,
    target: dict[tuple[str, str | None], Any],
    *,
    effective_from: date,
    effective_to: date | None,
) -> charge_prices.PriceChange:
    """🔒 `CR-156-BRC10` — the code's prices become `target` from
    `effective_from`, through the one writer (`charge_prices.save_prices`).

    **SUPERSEDES `BR-RAT-690`'s REPLACE-THE-WHOLE-SET STORAGE** (PO 2026-10-01:
    *"why are you detleting it and not killing it"* → *"logical kill"*). This
    function used to DELETE every row of the code and re-insert the posted set,
    so the previous prices survived only as a before/after copy in
    `rate_change_log` and in `audit_log`, which is pruned. Now an unchanged row
    is left untouched, a changed or removed one is closed and marked killed, and
    the new price is a new row — so *"what was CART-64 on 09/01?"* is answered
    from the price table itself.

    Called INSIDE the caller's `transaction.atomic()`, and before `charge_row`
    is read for the audit `after` — `charge_row` serves the full price history,
    so the audit entry carries the change without a second write (CLAUDE.md
    hard rule 7).
    """
    return charge_prices.save_prices(
        charge, target, effective_from=effective_from, effective_to=effective_to
    )


def _validate_charge(
    payload: dict[str, Any], *, partial: bool, charge: Any = None
) -> dict[str, Any]:
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, CHARGE_FIELDS, fe)
    cleaned: dict[str, Any] = {}

    code = _text(payload, "code", fe, required=not partial, max_length=20)
    if code is not None:
        duplicate = models.Charge.objects.filter(tenant_id=_tenant_id(), code=code)
        if charge is not None:
            duplicate = duplicate.exclude(pk=charge.pk)
        if duplicate.exists():
            # US-RAT-008 TC-5: (tenant, code) uniqueness.
            fe.append(_field_error("code", errors.VAL_FORMAT, "rating.charges.duplicate_code"))
        cleaned["code"] = code
    name = _text(payload, "name", fe, required=not partial, max_length=120)
    if name is not None:
        cleaned["name"] = name
    if "charge_type" in payload:
        cleaned["charge_type"] = _choice(payload, "charge_type", CHARGE_TYPES, fe)
    if "service" in payload:
        service_code = _text(payload, "service", fe)
        if service_code is None:
            cleaned["service_id"] = None  # NULL = any service (r6.6)
        else:
            service = _enabled_service(service_code, "service", fe)
            cleaned["service_id"] = service["id"] if service else None

    amount_rule = None
    if "amount_rule" in payload:
        raw_rule = str(payload.get("amount_rule") or "").strip().lower()
        if raw_rule == AMOUNT_RULE_FORMULA:
            # BR-RAT-041: the option renders in S12 but is DISABLED in v1 — the
            # server refuses it so no half-defined formula can be stored.
            fe.append(
                _field_error(
                    "amount_rule",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "rating.charges.formula_disabled",
                    br_ref="BR-RAT-041",
                )
            )
        else:
            amount_rule = _choice(payload, "amount_rule", AMOUNT_RULES, fe, required=True)
            cleaned["amount_rule"] = amount_rule
    elif not partial:
        fe.append(_field_error("amount_rule", errors.VAL_REQUIRED, "rating.required"))

    for field in ("amount", "percent", "min_amount", "max_amount"):
        if field in payload:
            cleaned[field] = _decimal(payload, field, fe, minimum=Decimal("0"))

    # ── BR-RAT-690 (DEF-2190) — the per-size amounts, and the ONE-BASIS rule ──
    # `resolution.resolve_charge_codes` refuses a code that states BOTH a flat
    # amount and a per-size table, in its own words: *"CR-013 part 2 gives a
    # code one basis; this chain refuses rather than choosing which figure the
    # customer is billed."* That refusal is correct and it fires ON BILLING DAY.
    # Refusing it HERE is the same law at the moment a person can still fix it,
    # and it closes a silent preference the adapter carries meanwhile:
    # `resolution_catalogue.charge_code_facts` sets `flat_amount=None if amounts
    # else …`, so a code holding both would quietly bill the TABLE and ignore
    # the $12.00 somebody typed into the single Amount box.
    if "size_amounts" in payload:
        cleaned["size_amounts"] = _validate_size_amounts(
            payload.get("size_amounts"), fe, charge=charge
        )
        flat_in_table = [
            row
            for row in cleaned["size_amounts"]
            if row["size_class"] == ALL_SIZES and row.get("customer_class") is None
        ]
        if flat_in_table and "amount" in cleaned:
            # The every-class *All sizes* row IS `amount`; stating it twice in
            # one payload is two answers to one question.
            fe.append(
                _field_error(
                    "size_amounts",
                    errors.VAL_FORMAT,
                    "rating.size_rows.duplicate_size",
                    size_class=ALL_SIZES,
                )
            )
    # ── DEF-RAT-8753 — A PENALTY'S TERMS PER CUSTOMER CLASS ─────────────────
    if "class_terms" in payload:
        cleaned["class_terms"] = _validate_class_terms(payload.get("class_terms"), fe)
    # ── CR-013 part 2, ON THE STATEMENT THE SAVE WOULD LEAVE (CR-156-BRC10) ──
    # A code states a flat amount OR a size table. The flat amount is the
    # *All sizes* row now, so "both" is an *All sizes* row beside a sized row
    # in the statement this payload asks for — the same refusal as before, read
    # off one place instead of two.
    target = price_target(charge, cleaned)
    has_flat = any(size == ALL_SIZES for size, _class in target)
    has_sizes = any(size != ALL_SIZES for size, _class in target)
    if has_flat and has_sizes:
        fe.append(
            _field_error(
                "size_amounts", errors.VAL_FORMAT, "rating.charges.amount_and_size_table"
            )
        )
    # A per-size table IS the flat rule's amount, stated once per size. Asking
    # for the scalar as well would demand exactly the state the line above
    # refuses.
    if amount_rule == "flat" and not target:
        fe.append(_field_error("amount", errors.VAL_REQUIRED, "rating.required"))
    # ── DEF-RAT-8753 · `per_case` STATES NO PRICE, AND TERMS ARE A PENALTY'S ──
    # A code whose amount is entered when it is used carries no stored PRICE:
    # a size table or a percent beside it would be two answers to one
    # question, and billing would have to choose which one charges.
    # ⚠ AMENDED 2026-10-06 (`BR-RAT-1054`, PO option (a), `DEF-RAT-9807`): ONE
    # flat `amount` IS allowed now — it is the DEFAULT a clerk's screen starts
    # the fee at, never a price the server charges by itself (`charge_by_code`
    # serves it as `default_amount`, and the fee bill still takes the clerk's
    # figure). Everything else beside `per_case` is still refused.
    stated_terms = any(isinstance(value, charge_prices.ClassTerms) for value in target.values())
    if amount_rule == AMOUNT_RULE_PER_CASE:
        posted_price = (
            bool(cleaned.get("size_amounts"))
            or bool(cleaned.get("class_terms"))
            or cleaned.get("percent") is not None
        )
        if posted_price:
            fe.append(
                _field_error("amount", errors.VAL_FORMAT, "rating.charges.per_case_states_no_price")
            )
    if cleaned.get("class_terms"):
        rule_now = amount_rule or getattr(charge, "amount_rule", None)
        if rule_now not in ("percent", "percent_with_minimum"):
            fe.append(
                _field_error(
                    "class_terms", errors.VAL_FORMAT, "rating.charges.class_terms_need_percent"
                )
            )

    # ── THE PRICE'S DATES (CR-156-BRC10, PO 2026-10-01) ─────────────────────
    # *"we will need start and effective date"*. The NEW screens (wave B) always
    # send Effective from and refuse a save without one (*"Pick a date."*).
    # ⚠ **INTERIM RULE (coordinator, 2026-10-01 — recorded in the decision log
    # and CR-156-BRC10 §7): the SERVICE does not refuse a missing Effective
    # from; it takes the tenant's TODAY** (`_effective_from_or_today`). The live
    # charge-code wizard the beta clerks use sends no date, and a price it
    # saves applied immediately before dates existed — today is exactly that.
    # Once a payload sends the date, the date wins. Effective to is optional.
    if "effective_from" in payload:
        cleaned["effective_from"] = _date_value(payload, "effective_from", fe)
    if "effective_to" in payload:
        cleaned["effective_to"] = _date_value(payload, "effective_to", fe)
    start = cleaned.get("effective_from")
    end = cleaned.get("effective_to")
    if start is not None and end is not None and end < start:
        fe.append(_field_error("effective_to", errors.VAL_RANGE, "rating.plans.window_inverted"))

    # ── KIND (CR-156-BRC10) ─────────────────────────────────────────────────
    # *"can we have 3 kinds base charges, plan charges and others"*. `base`
    # and `is_base` are one fact: a payload stating both must agree.
    if "kind" in payload:
        cleaned["kind"] = _choice(payload, "kind", KINDS, fe)
        if "is_base" in payload and cleaned.get("kind") is not None:
            if _bool(payload, "is_base") != (cleaned["kind"] == KIND_BASE):
                fe.append(
                    _field_error("kind", errors.VAL_UNKNOWN_LOOKUP, "rating.unknown_value")
                )
    # DEF-RAT-8753 — a penalty priced BY CLASS carries its percent and minimum
    # on each class row, so the code's single pair is not required beside it.
    if not stated_terms:
        if amount_rule in ("percent", "percent_with_minimum") and cleaned.get("percent") is None:
            fe.append(_field_error("percent", errors.VAL_REQUIRED, "rating.required"))
        if amount_rule == "percent_with_minimum" and cleaned.get("min_amount") is None:
            fe.append(_field_error("min_amount", errors.VAL_REQUIRED, "rating.required"))
        # 🔒 DEF-BIL-10201 (PO 2026-10-17, a late fee is flat OR a percentage
        # with an optional minimum) — a PENALTY priced at 0% with no minimum
        # charges $0.00 on every bill it ever reaches, which is a late fee
        # nobody can have meant: refused, and the clerk is told what to enter.
        type_now = cleaned.get("charge_type", getattr(charge, "charge_type", None))
        if (
            type_now == "penalty"
            and (amount_rule or getattr(charge, "amount_rule", None)) in ("percent", "percent_with_minimum")
            and cleaned.get("percent") is not None
            and Decimal(cleaned["percent"]) == 0
            and not Decimal(cleaned.get("min_amount") or 0) > 0
        ):
            fe.append(
                _field_error(
                    "percent", errors.VAL_RANGE, "rating.charges.penalty_needs_percent_or_minimum"
                )
            )

    if "gl_account_id" in payload:
        # CR-008 second-set ruling 3 — validated WHEN IT IS PICKED, not only
        # when a bill runs. This line was `_uuid_value(...)` alone until
        # 2026-08-17, so any well-formed uuid was stored, including another
        # utility's account id, and BR-BIL-010 was the first thing to notice —
        # by refusing the whole bill, on billing day.
        cleaned["gl_account_id"] = _validated_gl_account(
            payload, "gl_account_id", fe, message_key="rating.charges.gl_account_unknown"
        )
    if "applies_to_customer_classes" in payload:
        # BR-RAT-108 — the third narrowing dimension. Validated EXACTLY as
        # `taxes.applies_to_customer_classes` is, and deliberately so: two
        # objects answering the same question must not answer it two ways, and
        # a lane reading one should be able to predict the other.
        #
        # An unknown code is REFUSED, never dropped. DEF-273's reason applies
        # unchanged: a typo'd "residental" that silently vanished would leave a
        # base charge the utility believes is restricted applying to EVERYBODY —
        # and on a base charge that is every bill, not an edge case.
        cleaned["applies_to_customer_classes"] = _customer_class_list(
            payload, "applies_to_customer_classes", fe
        )
    for flag in ("taxable_default", "auto_apply", "waivable", "separate_line", "is_base"):
        if flag in payload:
            cleaned[flag] = _bool(payload, flag)
    # ── DEF-RAT-9805 · "APPLY AUTOMATICALLY" ON A ONE-TIME CODE DOES NOTHING ──
    # The two readers of `auto_apply` both require `recurring` beside it
    # (`BR-RAT-117`): the bill run's fee reader OMITS a one-time auto code
    # silently (`selectors._rides_a_periodic_bill`) and R4 REFUSES it as a
    # recurrence conflict (`resolution.rides_a_periodic_bill`, `BR-RAT-730`).
    # No one-time door — move-in fees, connection fees, fee bills, service
    # requests — reads the flag at all (measured 2026-10-06). So the setting a
    # clerk saved did nothing, or stopped a resolution; it is refused here, at
    # the card, which is `OQ-RAT-12464`'s option (c) for the one-time type.
    # Only when the payload TOUCHES one of the two columns, so a name fix on a
    # row stored before this check is not blocked by a choice nobody made now.
    _clean_charge_grace(payload, cleaned, fe, charge)
    _clean_application_fee(payload, cleaned, fe, charge)
    _clean_nsf_fee(payload, cleaned, fe, charge)
    if "auto_apply" in cleaned or "charge_type" in cleaned:
        auto_now = cleaned.get("auto_apply", bool(getattr(charge, "auto_apply", False)))
        type_now = cleaned.get("charge_type", getattr(charge, "charge_type", None))
        if auto_now and type_now == "one_time":
            fe.append(
                _field_error("auto_apply", errors.VAL_FORMAT, "rating.charges.auto_apply_one_time")
            )
    _refuse(fe)
    return cleaned


def _clean_nsf_fee(
    payload: dict[str, Any], cleaned: dict[str, Any], fe: list[dict[str, Any]], charge: Any
) -> None:
    """🔒 HUMAN-REVIEW-PENDING — `DEF-PAY-10698`, PO 2026-10-30.

    *NSF fee: Yes* marks this code as a returned-payment fee. A payment
    reversed for *Returned by the bank* charges the marked code its account's
    plan lists (`selectors.plan_nsf_charge`). Only a PENALTY code may carry it
    — BR-PAY-013's fee is a penalty on the customer, and the seeded `NSF` is
    one — so a marked one-time or base code is refused rather than charged.
    """
    if "is_nsf_fee" in payload:
        cleaned["is_nsf_fee"] = _bool(payload, "is_nsf_fee")
    if "is_nsf_fee" not in cleaned and "charge_type" not in cleaned:
        return
    marked = cleaned.get("is_nsf_fee", bool(getattr(charge, "is_nsf_fee", False)))
    if not marked:
        return
    type_now = cleaned.get("charge_type", getattr(charge, "charge_type", None))
    if type_now != "penalty":
        fe.append(_field_error("is_nsf_fee", errors.VAL_FORMAT, "rating.charges.nsf_fee_penalty"))
        return
    # ── `DEF-RAT-10739` · PO 2026-10-31 P7 = A — ONE NSF FEE PER PLAN ────────
    # The bounce reads the plan's ONE marked code and refuses two by name
    # (`selectors.plan_nsf_charge` → `nsf_fee_ambiguous_on_plan`, *"Two NSF fees
    # on this plan. None charged."*). So a tick that would put a SECOND marked
    # code on a plan is refused HERE, naming the code already doing the job,
    # rather than discovered on the day a cheque bounces. Per PLAN, not per
    # utility: two plans may each charge a different code, which is what the
    # walk Account › Unit › Plan › Charge code exists for.
    if charge is None or not cleaned.get("is_nsf_fee", False) or charge.is_nsf_fee:
        return
    plans = models.PlanChargeRule.objects.filter(
        tenant_id=_tenant_id(), charge_id=charge.pk, role="charge"
    ).values_list("rate_plan_id", flat=True)
    other = (
        models.PlanChargeRule.objects.filter(
            tenant_id=_tenant_id(),
            rate_plan_id__in=list(plans),
            role="charge",
            charge__is_nsf_fee=True,
            charge__deleted_at__isnull=True,
        )
        .exclude(charge_id=charge.pk)
        .select_related("charge", "rate_plan")
        .order_by("rate_plan__name", "charge__code")
        .first()
    )
    if other is not None:
        fe.append(
            _field_error(
                "is_nsf_fee",
                errors.VAL_FORMAT,
                "rating.charges.nsf_fee_taken_on_plan",
                charge_code=other.charge.code,
                plan=other.rate_plan.name,
            )
        )


def _clean_application_fee(
    payload: dict[str, Any], cleaned: dict[str, Any], fe: list[dict[str, Any]], charge: Any
) -> None:
    """🔒 HUMAN-REVIEW-PENDING — `DEF-CUS-9819`, PO rulings 2026-10-06.

    *Application fee: Yes* marks this code as the utility's application fee:
    every new service request gets its line automatically at its live price
    (PO: *"Should the application fee be added to every request automatically?
    I recommend (a)."*). Two refusals, each by name, and only when the payload
    TOUCHES the flag or the type, so a name fix on any other code is never
    blocked by a choice nobody made now:

      * **only a ONE-TIME code** — an application fee is taken once against a
        request (`BR-CUS-1092`); a recurring or penalty code is an account's;
      * **only ONE per utility** — a second is refused naming the code that
        already holds it (the partial unique index `ux_charges_one_application_fee`
        is the database's copy of the same rule).

    Worked: `APP-FEE` $10.00 marked → Kyle Mark's portal request arrives with
    *Application fee $10.00* on it. Marking `CC-REQFEE` too → refused,
    *"APP-FEE is already your application fee."*
    """
    if "is_application_fee" in payload:
        cleaned["is_application_fee"] = _bool(payload, "is_application_fee")
    if "is_application_fee" not in cleaned and "charge_type" not in cleaned:
        return
    marked = cleaned.get("is_application_fee", bool(getattr(charge, "is_application_fee", False)))
    if not marked:
        return
    type_now = cleaned.get("charge_type", getattr(charge, "charge_type", None))
    if type_now != "one_time":
        fe.append(
            _field_error(
                "is_application_fee", errors.VAL_FORMAT, "rating.charges.application_fee_one_time"
            )
        )
        return
    holder = models.Charge.objects.filter(
        tenant_id=_tenant_id(), is_application_fee=True, deleted_at__isnull=True
    )
    if charge is not None:
        holder = holder.exclude(pk=charge.pk)
    other = holder.order_by("code").values_list("code", flat=True).first()
    if other is not None:
        fe.append(
            _field_error(
                "is_application_fee",
                errors.VAL_FORMAT,
                "rating.charges.application_fee_taken",
                charge_code=other,
            )
        )


# ── `DEF-RAT-10026` · PO 2026-10-09 — NO CLASS-OVERLAP REFUSAL FOR BASE CODES ──
# `base_codes_clash` and `base_code_clash` stood here (`DEF-RAT-8845`,
# narrowed by `DEF-RAT-9798`) and are REMOVED, with the step-1 probe
# `GET /charges/base-clash` that asked them (`DEF-RAT-9799`). PO, verbatim, on
# being shown BASE-E (Residential) and BASE-E-OUT (Residential, suburban)
# refused with *"BASE-E already covers Residential."*: *"yes please do it"*.
# The guard existed because billing once picked the base by class from a pool
# and refused two (`DEF-468`); since 2026-10-06 a rate schedule names exactly
# one base code and billing reads only that one
# (`selectors.base_charge_from_charge_code`'s `named_code`), and a schedule
# naming none bills `$0.00` with the warning (`DEF-RAT-9832`). So two live
# base codes of one service may share any classes; code STRINGS stay unique.


def _clean_charge_grace(
    payload: dict[str, Any], cleaned: dict[str, Any], fe: list[dict[str, Any]], charge: Any
) -> None:
    """🔒 HUMAN-REVIEW-PENDING — PO ruling 2026-10-06 11 (a), ❄️ B4/B5 late fee.

    *"When Type is Penalty, the form asks Grace days (default 5) and Calendar /
    Business days, and billing uses the code's grace. The Settings default
    stays as the starting value for new codes."*

    Only a PENALTY code carries a grace. A penalty saved with none takes the
    utility's Billing-defaults grace (`seams.late_grace_default`, 5 calendar
    unless the utility changed it); any other type stores NULL, so a code
    re-typed away from Penalty does not keep a grace nothing reads. The
    arithmetic is untouched: 0–30 (`BR-BIL-008`), two modes (`BR-BIL-002`).
    Worked: due 1 Nov, $100.00 unpaid, grace 5 calendar days on `LATE` → a fee
    only once still unpaid after 6 Nov; grace 10 → not before 12 Nov.
    """
    if "grace_days" in payload:
        raw = payload.get("grace_days")
        days: int | None = None
        if raw not in (None, ""):
            try:
                days = int(str(raw).strip())
            except (TypeError, ValueError):
                fe.append(_field_error("grace_days", errors.VAL_FORMAT, "rating.not_a_number"))
            else:
                if not 0 <= days <= MAX_GRACE_DAYS:
                    fe.append(
                        _field_error(
                            "grace_days",
                            errors.VAL_RANGE,
                            "rating.plans.grace_days_range",
                            max=MAX_GRACE_DAYS,
                        )
                    )
                    days = None
        cleaned["grace_days"] = days
    if "grace_mode" in payload:
        cleaned["grace_mode"] = _choice(payload, "grace_mode", GRACE_MODES, fe)
    if not ({"charge_type", "grace_days", "grace_mode"} & set(cleaned)):
        return
    type_now = cleaned.get("charge_type", getattr(charge, "charge_type", None))
    if type_now != "penalty":
        cleaned["grace_days"] = None
        cleaned["grace_mode"] = None
        return
    default_days, default_mode = seams.late_grace_default()
    if cleaned.get("grace_days", getattr(charge, "grace_days", None)) is None:
        cleaned["grace_days"] = default_days
    if not cleaned.get("grace_mode", getattr(charge, "grace_mode", None)):
        cleaned["grace_mode"] = default_mode


def _base_code_rules(charge: Any, *, gl_given: bool) -> bool:
    """The one rule a BASE code meets at every save; returns True when it set the GL.

    ⚠⚠ **THE OVERLAP REFUSAL BELOW IS REMOVED 2026-10-09 (`DEF-RAT-10026`, PO
    ruling *"yes please do it"*).** A service may hold two or more live base
    codes for the same customer class; the rate schedule names which one bills.
    The two overlap paragraphs that follow are kept as HISTORY (hard-won law 1),
    not as a description of this function; the GL paragraph (`DEF-RAT-8847`)
    is the rule that still runs.

    ⚠ **NARROWED 2026-10-06 (`DEF-RAT-9798`, PO ruling A (a)) — AN ALL-CLASSES
    CODE AND A ONE-CLASS CODE MAY NOW COEXIST.** The paragraph below said an
    EMPTY class list meets any other; it now meets only another empty list.
    See `base_codes_clash` (removed 2026-10-09). What refused until then: two
    codes naming a same class, and two all-classes codes.

    **`DEF-RAT-8845` — ONE LIVE BASE PER SERVICE AND CUSTOMER CLASS.** Billing
    already refuses a bill that two base codes reach (*"2 base charge codes for
    water. Scope them on Charge codes."*, `DEF-468`), so a second residential
    water base saved on a Tuesday stopped every residential water bill from then
    on, and nothing said so at the save. Two live base codes overlap when they
    name the same service and their classes meet — an EMPTY class list is every
    class, so it meets any other. The save is refused by name; nothing already
    stored is touched (coordinator 2026-10-01, from the charge-code walk).

    **`DEF-RAT-8847` — A BASE STARTS ON ITS SERVICE'S BASE REVENUE ACCOUNT.** A
    code minted in Settings carries no GL, and the seeded base codes get theirs
    from the ledger's rule (`ledger.selectors.default_gl_account_id_for_charge_code`
    — *"a base charge code posts to its own service's revenue account"*). A base
    configured on the screen now gets the same answer when it has none and the
    save did not post one; the clerk can still change it. The ledger answering
    None leaves the NULL, exactly as before.
    """
    if not charge.is_base or charge.deleted_at is not None or not charge.service_id:
        return False
    if charge.gl_account_id is None and not gl_given:
        default = seams.ledger_default_gl_account_id_for_charge(
            charge.code, service=charge.service.code, is_base=True
        )
        if default:
            charge.gl_account_id = default
            return True
    return False


@require_role(SYSTEM_ADMIN)
def create_charge(actor: Any, payload: Any) -> dict[str, Any]:
    """S12 save. Amounts are SEEDS, never constants (BR-RAT-035/B4 §NSF)."""
    payload = _require_dict(payload)
    cleaned = _validate_charge(payload, partial=False)
    target = price_target(None, cleaned)
    effective_from = _effective_from_or_today(cleaned.pop("effective_from", None))
    effective_to = cleaned.pop("effective_to", None)
    cleaned.pop("size_amounts", None)
    cleaned.pop("class_terms", None)
    cleaned.pop("amount", None)
    # ── KIND (CR-156-BRC10) — the PO's list decides when nobody chose one ──
    if cleaned.get("kind") is None:
        cleaned["kind"] = default_kind(
            cleaned.get("code"), cleaned.get("charge_type"), bool(cleaned.get("is_base"))
        )
    else:
        cleaned["is_base"] = cleaned["kind"] == KIND_BASE
    with transaction.atomic():
        charge = models.Charge(tenant_id=_tenant_id(), **cleaned)
        _base_code_rules(charge, gl_given="gl_account_id" in cleaned)
        charge.save(force_insert=True)
        _write_prices(charge, target, effective_from=effective_from, effective_to=effective_to)
        after = _json_safe(selectors.charge_row(charge))
        # The first price is not a CHANGE: its row in `charge_code_amounts` IS
        # the start of the history (dated, never deleted), and `audit_log`
        # carries the creation. `rate_change_log` starts at the first edit.
        _audit(actor, "charge.created", "charge", charge.id, after=after)
    return selectors.charge_row(charge)


def _log_charge_price(
    actor: Any, charge: Any, *, before: Any, after: Any, reason: str
) -> None:
    """One `rate_change_log` row for a charge code's price move — written for
    EVERY money change since `CR-156-BRC10` (it used to be written only for a
    code in use, `BR-RAT-1016`). `reason` is the clerk's sentence where one was
    required, else empty: a code nobody uses needs no reason (`BR-RAT-1016`'s
    verb-1 boundary, unchanged), and inventing one would be a record nobody
    wrote."""
    models.RateChangeLog.objects.create(
        tenant_id=_tenant_id(),
        entity_type="charge",
        entity_id=charge.id,
        before=before,
        after=after,
        reason=reason,
        actor_id=_actor_user_id(actor),
    )


@require_role(SYSTEM_ADMIN)
def update_charge(actor: Any, charge_id: Any, payload: Any) -> dict[str, Any]:
    """PATCH one charge code — free while it has priced nothing, REASONED once
    it has (`BR-RAT-1016`, `DEF-RAT-5712`).

    ── WHY THIS OBJECT NEEDED A GUARD MORE THAN THE OTHER FOUR ──────────────
    `BR-RAT-088` (PO 2026-08-20) gives the CHARGE CODE the base amount — *"a
    plan displays it, never defines it"* — and the plan screen says so to the
    clerk in its own words: *"This plan shows it and cannot change it."* So the
    charge code is the ONE place an amount can change. Until this function grew
    a guard it was twenty-three lines, validate and write, and it had the LEAST
    protection of the five priced objects in this module: a tax refuses the
    in-place edit outright (`BR-RAT-104`), a published plan bumps a version and
    demands a reason (`BR-RAT-037`), a rate schedule refuses the save, and a
    DISCOUNT — which can only ever REDUCE a bill — needs submit, approve and
    activate.

    **Worked:** `PAPER` at `$2.00` moved to `$5.00` bills `$3.00` more on every
    plan carrying it, next cycle, for ever. The only trace was an `audit_log`
    row, and `audit_log` is pruned on a retention schedule (hard rule 4's
    2026-09-02 narrowing), so the record of a price move could outlive nothing.

    ── THE THREE VERBS, AND WHICH ONE THIS IS ───────────────────────────────
    This is **VERB 1 and its boundary**. A code nobody uses edits in place with
    an audit row and no reason — in `correct_tax`'s own words, *"a draft is not
    history. It has never priced anything, so there is nothing to preserve and
    nothing to explain."* A code in use may still be repriced, because a
    utility's prices really do move, but not silently: a written reason and a
    `rate_change_log` row carrying before, after, the reason and the actor.

    ⚠ **VERBS 2 (CORRECT) AND 3 (CHANGE) CANNOT BE BUILT HERE AND THE ABSENCE
    IS NAMED RATHER THAN HALF-BUILT.** Both turn on a WINDOW — a correction
    restates the same one, a change gets a new one — and `charges` has no
    dates and no version table at all. Its columns are tenant, code, name,
    charge_type, service, amount_rule, amount, percent, min_amount, max_amount,
    gl_account_id and the behaviour flags. So a price typed here takes effect
    IMMEDIATELY, on the open cycle, and there is no way to schedule one or to
    say a figure was a typo rather than a decision. That is `OQ-RAT-12408`,
    which this response NAMES, with the three storage options and the migration
    sub-question written out.

    ⚠ **AND NOTHING ALREADY ISSUED IS TOUCHED** — hard rule 4. A reprice
    changes what prices FUTURE bills. `issued_bills_unchanged` says so in the
    response rather than only in this docstring, for the reason `correct_tax`
    gives one object over: an operator who has just fixed a price will
    otherwise believe the money is fixed.
    """
    payload = _require_dict(payload)
    # `reason` is not a column and `_reject_unknown` refuses every key that is
    # not in `CHARGE_FIELDS`, so it comes out before validation — the same
    # split `correct_tax` makes between its reason and its changes.
    reason = str(payload.get("reason") or "").strip()
    changes = {key: value for key, value in payload.items() if key != "reason"}
    with transaction.atomic():
        charge = selectors.charge_or_404(charge_id)
        cleaned = _validate_charge(changes, partial=True, charge=charge)
        cleaned = _penalty_pair_as_dated_terms(charge, cleaned)
        # ── BR-RAT-1016 — REFUSED BEFORE ANYTHING IS WRITTEN ────────────────
        # `update_plan`'s own posture, and it matters more here: a half-applied
        # reprice is a figure that bills. `charge_used_by` is recomputed inside
        # this transaction rather than read from the row the caller was shown,
        # so a plan that attached the code while the form was open counts.
        used = selectors.charge_used_by(charge)
        repriced = charge_money_moves(charge, cleaned) and charge_is_in_use(used)
        if repriced and len(reason) < MIN_CORRECTION_REASON:
            # The SAME floor `correct_tax` uses, and for the same reason: a
            # filing record where every row says "fix" is a history nobody can
            # read in a year. The refusal NAMES what is in use, because a
            # refusal that does not say why is the road ending — the shape
            # `DEF-384` was filed for.
            # `charge_code` and not `code`: `_field_error`'s SECOND positional
            # parameter is named `code` (the VAL-### error code), so a params
            # key of that name collides with it — `TypeError: got multiple
            # values for argument 'code'`, raised from inside the refusal path
            # and therefore only ever seen by whoever triggers the refusal.
            details = {
                "br_ref": "BR-RAT-1016",
                "charge_code": charge.code,
                "plans": used["plans"],
                "schedules": used["schedules"],
            }
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="rating.charges.reason_required",
                params=details,
                field_errors=[
                    _field_error(
                        "reason", errors.VAL_REQUIRED, "rating.charges.reason_required", **details
                    )
                ],
            )
        # BR-RAT-690. ABSENT is not EMPTY: a payload with no `size_amounts` key
        # leaves the stored rows exactly as they are (the posture
        # `gl_account_id` takes for the same reason), and an empty list is the
        # explicit "this code no longer varies by size".
        prices_move = _prices_move(charge, cleaned)
        target = price_target(charge, cleaned)
        effective_from = _effective_from_or_today(cleaned.pop("effective_from", None))
        effective_to = cleaned.pop(
            "effective_to", None
        )
        cleaned.pop("size_amounts", None)
        cleaned.pop("class_terms", None)
        cleaned.pop("amount", None)
        # ── KIND and `is_base` are one fact (CR-156-BRC10) ─────────────────
        if cleaned.get("kind") is not None:
            cleaned["is_base"] = cleaned["kind"] == KIND_BASE
        elif "is_base" in cleaned and cleaned["is_base"] != charge.is_base:
            cleaned["kind"] = default_kind(
                cleaned.get("code", charge.code),
                cleaned.get("charge_type", charge.charge_type),
                bool(cleaned["is_base"]),
            )
        before = _json_safe(selectors.charge_row(charge))
        for field, value in cleaned.items():
            setattr(charge, field, value)
        # DEF-RAT-8845 / DEF-RAT-8847 — one live base per service and class, and a
        # base's revenue account by default.
        if _base_code_rules(charge, gl_given="gl_account_id" in cleaned):
            cleaned["gl_account_id"] = charge.gl_account_id
        if cleaned:
            charge.save(update_fields=[*cleaned.keys(), "updated_at"])
        change = (
            _write_prices(charge, target, effective_from=effective_from, effective_to=effective_to)
            if prices_move
            else charge_prices.PriceChange()
        )
        after = _json_safe(selectors.charge_row(charge))
        money_moved = change.moved or (
            charge_money_moves_scalar(before, after)
        )
        if before != after:
            if money_moved:
                # CR-156-BRC10 — written for EVERY money change, in use or not;
                # the REASON is still required only for a code in use
                # (`BR-RAT-1016`, today's rule, enforced above).
                _log_charge_price(actor, charge, before=before, after=after, reason=reason)
            if repriced:
                # A REPRICE IS ITS OWN ACTION, so an audit reader can tell a
                # price move from a rename without diffing two blobs.
                _audit(
                    actor,
                    "charge.repriced",
                    "charge",
                    charge.id,
                    before=before,
                    after={**after, "reason": reason},
                )
            else:
                _audit(actor, "charge.updated", "charge", charge.id, before=before, after=after)
    row = selectors.charge_row(charge)
    if repriced:
        # ⚠ SAID OUT LOUD IN THE RESPONSE, not only in a docstring — the same
        # thing `correct_tax` does with `OQ-310`, for the same reason.
        row["issued_bills_unchanged"] = True
    return row


def _penalty_pair_as_dated_terms(charge: Any, cleaned: dict[str, Any]) -> dict[str, Any]:
    """🔒 `DEF-RAT-8827` — a penalty's EVERY-CLASS percent and minimum, edited,
    become a DATED terms row; the code's two columns are never overwritten.

    Before this, *Edit* on `LATE` (one percent and one minimum for every class)
    PATCHed `charges.percent` / `charges.min_amount` in place: 1.50% / $5.00 →
    1.75% / $6.00 typed *"from 11/01/2026"* charged every overdue account the
    new fee THAT DAY, and no version or row was kept. A charge code's price is
    dated and never overwritten (PO 2026-10-01, *"we will need start and
    effective date"*, *"logical kill"*), and wave C already stores a per-CLASS
    penalty that way (`BR-RAT-1053`). The every-class pair is the same statement
    with no class, so it takes the same road: an *All sizes* terms row naming no
    class, from Effective from, through `charge_prices.save_prices`.

    **The columns stay what they were and keep their meaning: the terms BEFORE
    any dated row.** `charge_prices.class_terms_on` picks a class's row, else the
    every-class row, else None — and `selectors.plan_late_fee_terms` answers None
    from the columns. Worked (`LATE`, edited on 10/01 for 11/01): 10/15 reads no
    row → 1.50% / $5.00 from the columns; 11/15 reads the row → 1.75% / $6.00.

    A by-class save (`class_terms` posted non-empty) is wave C's path and is left
    exactly as it was. Re-saving the pair a clerk was shown changes nothing.
    """
    rule = cleaned.get("amount_rule", charge.amount_rule)
    if rule not in ("percent", "percent_with_minimum"):
        return cleaned
    if cleaned.get("class_terms"):
        return cleaned
    if "percent" not in cleaned and "min_amount" not in cleaned:
        return cleaned
    shown = charge_prices.class_terms_on(charge, None) or charge_prices.ClassTerms(
        percent=charge.percent, minimum=charge.min_amount
    )
    wanted = charge_prices.ClassTerms(
        percent=cleaned.get("percent", shown.percent),
        minimum=cleaned.get("min_amount", shown.minimum),
    )
    out = {key: value for key, value in cleaned.items() if key not in ("percent", "min_amount")}
    if wanted.percent is None or (shown.percent is not None and charge_prices._same(shown, wanted)):
        return out
    out["class_terms"] = [
        {"customer_class": None, "percent": wanted.percent, "min_amount": wanted.minimum}
    ]
    return out


def charge_money_moves_scalar(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """Did a money SCALAR on the code move (rule, percent, minimum, maximum)?
    The price rows are answered by `PriceChange.moved`; these four live on
    `charges` itself (`CR-156-BRC10`)."""
    return any(
        before.get(field) != after.get(field)
        for field in ("amount_rule", "percent", "min_amount", "max_amount", "grace_days", "grace_mode")
    )


@require_role(SYSTEM_ADMIN)
def set_charge_active(actor: Any, charge_id: Any, active: bool) -> dict[str, Any]:
    """IS-1 deactivate-first: deactivation is ALWAYS allowed (US-RAT-008 TC-7);
    reactivation is allowed at any time."""
    with transaction.atomic():
        charge = selectors.charge_or_404(charge_id)
        before = _json_safe(selectors.charge_row(charge))
        if active and charge.deleted_at is not None:
            # DEF-RAT-8845 — bringing a base back must not make two live bases.
            charge.deleted_at = None
            _base_code_rules(charge, gl_given=True)
        # DEF-CUS-9819 — bringing back a retired application-fee code while
        # another live code holds the mark must not make two (reactivation is
        # allowed at any time, so the returning code gives up its mark).
        unmark = (
            active
            and charge.is_application_fee
            and models.Charge.objects.filter(
                tenant_id=_tenant_id(), is_application_fee=True, deleted_at__isnull=True
            )
            .exclude(pk=charge.pk)
            .exists()
        )
        if unmark:
            charge.is_application_fee = False
        charge.deleted_at = None if active else Now()
        charge.save(
            update_fields=["deleted_at", "updated_at", *(["is_application_fee"] if unmark else [])]
        )
        charge.refresh_from_db(fields=["deleted_at"])
        action = "charge.reactivated" if active else "charge.deactivated"
        _audit(
            actor,
            action,
            "charge",
            charge.id,
            before=before,
            after=_json_safe(selectors.charge_row(charge)),
        )
    return selectors.charge_row(charge)


@require_role(SYSTEM_ADMIN)
def delete_charge(actor: Any, charge_id: Any) -> None:
    """BR-RAT-035 🔒 audit-lock: hard removal only at zero references, counted
    fresh INSIDE the transaction (US-RAT-008 TC-7)."""
    with transaction.atomic():
        charge = selectors.charge_or_404(charge_id)
        used = selectors.charge_used_by(charge)
        # DEF-079, the same fail-closed reading as `delete_plan`: `None` means
        # billing could not answer, and deleting a code that live invoice lines
        # cite would leave those rows — which hard rule 4 forbids anyone from
        # going back and fixing — pointing at a code that no longer exists.
        # CR-087 — `schedules` joins the lock. A code declared `is_base` for a
        # service is the base for every schedule on it (BR-RAT-088) and holds no
        # `PlanChargeRule` row at all, so it counted as used by nobody and the
        # zero-reference branch let it be deleted out from under every bill on
        # that service. It fails closed with the other two.
        if (
            used["plans"]
            or used["schedules"]
            or used["invoice_lines"] is None
            or used["invoice_lines"]
        ):
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-RAT-035",
                message_key="rating.charges.locked_referenced",
                params={
                    **used,
                    "invoice_lines": (
                        "unavailable" if used["invoice_lines"] is None else used["invoice_lines"]
                    ),
                },
            )
        before = _json_safe(selectors.charge_row(charge))
        charge_pk = charge.id
        # BR-RAT-690 — `ChargeCodeAmount.charge` is `on_delete=PROTECT`, so a
        # code that was priced per size could not be removed at all once the
        # write path above existed: the delete would raise `ProtectedError` and
        # a lawful zero-reference removal would answer HTTP 500. The rows are
        # this code's own and carry no reference of their own; they go with it,
        # inside the same transaction, and `before` already holds them.
        # CR-156-BRC10, decision log 2026-10-01 judgment (b): a code no plan
        # names, no schedule reads and no bill carries never priced anything,
        # so its rows go with it. A used code never reaches this line — it is
        # retired (`set_charge_active`), and its rows are kept.
        charge_prices.remove_all(charge)
        charge.delete()
        _audit(actor, "charge.deleted", "charge", charge_pk, before=before)


# ══════════════════════════════════════════════════════════════════════════
# Taxes & fees — US-RAT-009 (EP-RAT-03)
# ══════════════════════════════════════════════════════════════════════════
TAX_FIELDS: tuple[str, ...] = (
    "name",
    "jurisdiction",
    "kind",
    "rate",
    "base_includes_usage",
    "base_includes_base",
    "flat_amount",
    "flat_frequency",
    "per_unit_amount",
    "per_unit_uom",
    "per_meter_amount",
    "applies_above_units",
    "applies_to_services",
    "applies_to_customer_classes",
    "premises_scope_kind",
    "premises_scope_value",
    "liability_gl_account_id",
    "remit_to",
    "filing_frequency",
    "filing_form",
    "effective_from",
    "effective_to",
    # ── DEF-385 · the fields TAX-02 collects and had no column ──────────────
    # Added to the ACCEPTED set at the same commit as the columns. Until now a
    # wizard that posted `code` got `VAL_UNKNOWN_FIELD` from `_reject_unknown`,
    # which is why TAX-02 rendered each of these as a named absence rather than
    # a control: *"a control that posts a key the server refuses as unknown is
    # worse than no control."*
    "code",
    "bill_label",
    "tax_type",
    "rounding_rule",
    "due_date_rule",
    "remit_method",
    "remit_reference",
    "collection_allowance_percent",
    "collection_allowance_gl_account_id",
    "interest_penalty_percent",
    "interest_penalty_basis",
    "filing_reminder_recipient",
    # DEF-382 — statutory, per authority.
    "discount_treatment",
    # CR-165-BRC10 round 2 (§9) — *Account with the authority*, picked from
    # Settings › Accounting › Authority accounts.
    "authority_account_id",
)
JURISDICTION_FIELDS = ("name", "authority", "level", "reference_no")

#: DEF-385 — the CLASSIFICATION, which is not the computation form. See
#: `models.Tax.tax_type`: a franchise fee and a sales tax are both `percent`.
#: Bounded because an authority's filing rules follow the type, so a free-text
#: type would make the remittance worksheet unable to group anything.
TAX_TYPES = (
    "sales_tax",
    "franchise_fee",
    "regulatory_fee",
    "utility_tax",
    "environmental_fee",
    "other",
)
#: ⚠ STORED, AND THE ENGINE DOES NOT READ IT — `OQ-309`. B4's money rounding is
#: ❄️ FROZEN and finance-signed; a per-authority override would move signed
#: figures without a re-sign, which is a STOP under the change process. So the
#: utility may RECORD what its authority mandates and the arithmetic stays B4's
#: until finance rules. NULL means "B4's rule", which is what every row carries.
TAX_ROUNDING_RULES = ("half_up", "half_even", "up", "down", "truncate")
#: Part 4 step 3's *"method"*. Bounded so the remittance worksheet can group by
#: it; `other` exists because a small authority may still take a cheque in an
#: envelope and the product must not make that unrepresentable.
TAX_REMIT_METHODS = ("ach", "eft", "cheque", "portal", "other")
#: A rate without its period is not a rate. `1.5%` monthly read as annual is
#: twelve times too small — the same class of error CLAUDE.md hard rule 3 exists
#: to prevent for consumption.
TAX_INTEREST_BASES = ("daily", "monthly", "annual")
#: DEF-382 — re-exported from `selectors`, where the reader that consumes it
#: lives (`taxable_subtotal_for`). One declaration per rule.
DISCOUNT_TREATMENTS = selectors.DISCOUNT_TREATMENTS


def _resolve_jurisdiction(
    raw: Any, fe: list[dict[str, Any]], *, required: bool
) -> tuple[models.TaxJurisdiction | None, dict[str, Any] | None]:
    """BR-TEN-037: jurisdictions are TENANT-entered — either an existing id of
    this tenant or a new inline record. There is no global registry to look up."""
    if raw in (None, ""):
        if required:
            fe.append(_field_error("jurisdiction", errors.VAL_REQUIRED, "rating.required"))
        return None, None
    if isinstance(raw, dict):
        _reject_unknown(raw, JURISDICTION_FIELDS, fe, prefix="jurisdiction.")
        name = _text(raw, "name", fe, required=True, max_length=120, prefix="jurisdiction.")
        level = _choice(raw, "level", JURISDICTION_LEVELS, fe, prefix="jurisdiction.")
        if name is None:
            return None, None
        return None, {
            "name": name,
            "authority": _text(raw, "authority", fe, max_length=120, prefix="jurisdiction."),
            "level": level,
            "reference_no": _text(raw, "reference_no", fe, max_length=60, prefix="jurisdiction."),
        }
    try:
        jurisdiction_id = UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        fe.append(_field_error("jurisdiction", errors.VAL_FORMAT, "rating.bad_uuid"))
        return None, None
    row = models.TaxJurisdiction.objects.filter(tenant_id=_tenant_id(), pk=jurisdiction_id).first()
    if row is None:
        fe.append(
            _field_error("jurisdiction", errors.VAL_UNKNOWN_LOOKUP, "rating.unknown_jurisdiction")
        )
    return row, None


def _validated_liability_account(payload: dict[str, Any], fe: list[dict[str, Any]]) -> Any:
    """The tax's 2200-series liability account — the tenant's own, and live.

    ── THE TENANT MANAGES THIS, AND THAT IS THE RULING ───────────────────────
    BR-BIL-069 (PO ruling 2026-08-11 closing OQ-116), verbatim: *"For each
    atheority have separate account and tagging; but also ensure you allow Use
    to manage it since every utility may not have every account."* So this is a
    field a tenant fills in on S13, per authority, and **nothing seeds it**:
    `apps/ledger/chart.py` deliberately carries no 2200-series row, because B5
    line 74 (❄️ finance-signed) says *"tenant authorities mint their own"* and
    seeding one would invent an authority no tenant created (BR-TEN-037). What
    the tenant stores here, no seed and no re-seed ever overwrites — the ledger's
    seed only INSERTS accounts a tenant does not have and never writes this row.

    ── WHY IT IS VALIDATED, AND WHY THE LEDGER VALIDATES IT ──────────────────
    `liability_gl_account_id` is a deferred-FK uuid column (B11 F-3): before
    this, ANY well-formed uuid was accepted, including one belonging to another
    tenant's chart or to an account this tenant had deactivated. Either would be
    stamped onto an invoice line at issue and frozen there. The check is the
    ledger's because the table is the ledger's (B1) — `account_is_live` answers
    ownership AND liveness in one read, and it is the same function tenancy's
    `update_tenant_service` validates a service revenue account through, so the
    two configuration surfaces cannot drift on what "a usable account" means.

    `null` CLEARS the mapping and is accepted: retiring an authority is a real
    thing a tenant does. The consequence is not silent — a tax with no account
    refuses at issue, by name (BR-BIL-010). Whether SETUP should refuse it too
    is **OQ-146**, raised rather than chosen; nothing here blocks the save.

    ── ONE IMPLEMENTATION, THREE POINTERS (CR-008, 2026-08-17) ───────────────
    This function held the only copy of that check until charges and plan
    services needed the same one under second-set ruling 3. Rather than two
    more copies, the branches moved to `_validated_gl_account` and this stays
    as the named entry point carrying the tax-specific ruling above. A change
    to what "a usable account" means now changes all three or none.
    """
    return _validated_gl_account(
        payload,
        "liability_gl_account_id",
        fe,
        message_key="rating.taxes.gl_account_unknown",
    )


def _validated_authority_account(raw: Any, fe: list[dict[str, Any]], *, keep: Any) -> Any:
    """CR-165 §9 — `authority_account_id` names one of THIS tenant's authority
    accounts, and an ACTIVE one unless the tax already pointed at it (a retired
    account stays on the taxes that filed under it; it is only no longer
    offered). Blank clears it."""
    if raw in (None, ""):
        return None
    try:
        account_id = UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        fe.append(_field_error("authority_account_id", errors.VAL_FORMAT, "rating.bad_uuid"))
        return None
    row = models.TaxAuthorityAccount.objects.filter(tenant_id=_tenant_id(), pk=account_id).first()
    if row is None or (not row.active and str(keep or "") != str(account_id)):
        fe.append(
            _field_error(
                "authority_account_id",
                errors.VAL_UNKNOWN_LOOKUP,
                "rating.taxes.unknown_authority_account",
            )
        )
        return None
    return row.id


def _validate_tax(
    payload: dict[str, Any], *, partial: bool, tax: models.Tax | None = None
) -> dict[str, Any]:
    fe: list[dict[str, Any]] = []
    # US-RAT-009 TC-3: "Fees" and "tax-on-tax" are NOT representable — an
    # unknown key is refused here rather than silently dropped (BR-RAT-036).
    _reject_unknown(payload, TAX_FIELDS, fe)
    cleaned: dict[str, Any] = {}
    name = _text(payload, "name", fe, required=not partial, max_length=120)
    if name is not None:
        cleaned["name"] = name

    kind = None
    if "kind" in payload or not partial:
        kind = _choice(payload, "kind", TAX_KINDS, fe, required=not partial)
        if kind is not None:
            cleaned["kind"] = kind
    if "rate" in payload:
        cleaned["rate"] = _decimal(payload, "rate", fe, minimum=Decimal("0"))
    if kind == "percent" and cleaned.get("rate") is None:
        # US-RAT-009 TC-5: a negative or blank percent rate is refused.
        fe.append(_field_error("rate", errors.VAL_REQUIRED, "rating.required"))
    if "flat_amount" in payload:
        cleaned["flat_amount"] = _decimal(payload, "flat_amount", fe, minimum=Decimal("0"))
    if kind == "flat_per_bill" and cleaned.get("flat_amount") is None:
        fe.append(_field_error("flat_amount", errors.VAL_REQUIRED, "rating.required"))
    if "flat_frequency" in payload:
        cleaned["flat_frequency"] = _choice(payload, "flat_frequency", FLAT_FREQUENCIES, fe)
    if "per_unit_amount" in payload:
        cleaned["per_unit_amount"] = _decimal(payload, "per_unit_amount", fe, minimum=Decimal("0"))
    if kind == "per_unit" and cleaned.get("per_unit_amount") is None:
        fe.append(_field_error("per_unit_amount", errors.VAL_REQUIRED, "rating.required"))
    if "per_unit_uom" in payload:
        # CLAUDE.md rule 3: a quantity-priced tax always states its unit.
        cleaned["per_unit_uom"] = _text(payload, "per_unit_uom", fe, max_length=20)
    if kind == "per_unit" and "per_unit_uom" in payload and cleaned.get("per_unit_uom") is None:
        fe.append(_field_error("per_unit_uom", errors.VAL_REQUIRED, "rating.required"))
    if "per_meter_amount" in payload:
        cleaned["per_meter_amount"] = _decimal(
            payload, "per_meter_amount", fe, minimum=Decimal("0")
        )
    # BR-RAT-036 as amended: the amount is REQUIRED and there is deliberately no
    # unit to state — the quantity is a count of meters, not a measure.
    if kind == "per_meter" and cleaned.get("per_meter_amount") is None:
        fe.append(_field_error("per_meter_amount", errors.VAL_REQUIRED, "rating.required"))
    if "applies_above_units" in payload:
        # BR-RAT-042 (CONFIRMED, closes OQ-054): MARGINAL — only the units above
        # the threshold are taxed. Stored here, applied by the engine.
        cleaned["applies_above_units"] = _decimal(
            payload, "applies_above_units", fe, minimum=Decimal("0")
        )
    for flag in ("base_includes_usage", "base_includes_base"):
        if flag in payload:
            cleaned[flag] = _bool(payload, flag, default=True)
    if "applies_to_services" in payload:
        raw_services = payload.get("applies_to_services") or []
        if not isinstance(raw_services, list):
            fe.append(
                _field_error(
                    "applies_to_services", errors.VAL_FORMAT, "rating.taxes.services_not_list"
                )
            )
            raw_services = []
        codes: list[str] = []
        for index, code in enumerate(raw_services):
            service = _enabled_service(str(code), "applies_to_services", fe, prefix=f"[{index}]")
            if service is not None:
                codes.append(service["code"])
        cleaned["applies_to_services"] = codes
    if "applies_to_customer_classes" in payload:
        # DEF-273 — r10's *"Comm, Industrial only · Residential exempt"*. An
        # INCLUSION list of platform `account_types` codes; [] and absent both
        # mean every class. A code outside the platform catalog is REFUSED, not
        # dropped: a typo'd "residental" that silently vanished would leave a
        # tax the utility believes is restricted applying to everybody.
        raw_classes = payload.get("applies_to_customer_classes") or []
        if not isinstance(raw_classes, list):
            fe.append(
                _field_error(
                    "applies_to_customer_classes",
                    errors.VAL_FORMAT,
                    "rating.taxes.classes_not_list",
                )
            )
            raw_classes = []
        # BR-CUS-094a — the TENANT's own rows decide. Hoisted above the loop for
        # the same reason as the charge validator above.
        selectable = seams.selectable_account_type_codes()
        classes: list[str] = []
        for index, code in enumerate(raw_classes):
            value = str(code).strip().lower()
            if value not in selectable:
                fe.append(
                    _field_error(
                        f"applies_to_customer_classes[{index}]",
                        errors.VAL_UNKNOWN_LOOKUP,
                        "rating.taxes.unknown_customer_class",
                    )
                )
                continue
            if value not in classes:
                classes.append(value)
        cleaned["applies_to_customer_classes"] = classes
    if "premises_scope_kind" in payload:
        # DEF-273 / CR-013 part 4 — r10's *"Inside city limits"*. The MECHANISM
        # is a bounded choice; blank clears the scope, which is how a utility
        # says "everywhere". All five are accepted at WRITE time even though a
        # bill run can only resolve two of them: refusing to store a mechanism
        # the PO named would make the wizard lie about what the product supports,
        # and the unresolvable ones fail closed at pricing where it is visible.
        raw_kind = payload.get("premises_scope_kind")
        # CR-165 §9 — `GET /taxes/form-options` offers *Everywhere* as the value
        # `everywhere`; stored as NO scope, which is what everywhere has always
        # meant (a NULL kind applies the tax to every premises).
        if raw_kind in (None, "") or str(raw_kind).strip().lower() == "everywhere":
            cleaned["premises_scope_kind"] = None
        else:
            cleaned["premises_scope_kind"] = _choice(
                payload, "premises_scope_kind", PREMISES_SCOPE_KINDS, fe
            )
    if "premises_scope_value" in payload:
        cleaned["premises_scope_value"] = _text(payload, "premises_scope_value", fe, max_length=120)
    #: A scope FIELD with no VALUE is accepted and stated: it is exactly what a
    #: half-finished S13 wizard looks like, and refusing the save would lose the
    #: work. The consequence is not silent — `plan_tax_rules` treats it as
    #: reaching NOBODY (fail-safe), so an unfinished scope under-charges rather
    #: than over-charges while the utility finishes typing.
    # ── DEF-385 · the fields part 4 asks TAX-02 to collect ──────────────────
    if "code" in payload:
        # r10's first landing column. Uppercased on the way in, like every other
        # tenant code in this product, so `sales-tx` and `SALES-TX` cannot both
        # exist and then disagree about which one the remittance report means.
        code = _text(payload, "code", fe, max_length=32)
        code = code.upper() if code else None
        if code:
            # (tenant, code) case-insensitive, the same rule and the same shape
            # `_validate_charge` uses for charge codes; `uq_taxes_tenant_code_ci`
            # is the DB half. Refused at the field so the wizard can point at
            # the box rather than 500-ing on an IntegrityError.
            duplicate = models.Tax.objects.filter(tenant_id=_tenant_id(), code__iexact=code)
            if tax is not None:
                # ⚠ `DEF-RAT-9276` — EVERY VERSION OF A TAX SHARES ITS CODE
                # (CR-165 §7 item 6). It excluded only `tax.pk`, so a correction
                # — a NEW row restating the same tax — met its own predecessor's
                # code and was refused as a duplicate. The rule is now *one code
                # names one CHAIN*; `ex_taxes_code_one_chain` (`rating/0058`) is
                # the PostgreSQL half.
                duplicate = duplicate.exclude(pk=tax.pk).exclude(
                    chain_id=tax.chain_id or tax.pk
                )
            if duplicate.exists():
                fe.append(_field_error("code", errors.VAL_FORMAT, "rating.taxes.duplicate_code"))
        cleaned["code"] = code
    if "bill_label" in payload:
        cleaned["bill_label"] = _text(payload, "bill_label", fe, max_length=80)
    if "tax_type" in payload:
        cleaned["tax_type"] = _choice(payload, "tax_type", TAX_TYPES, fe)
    if "rounding_rule" in payload:
        # ⚠ ACCEPTED AND STORED, NOT HONOURED — OQ-309. See TAX_ROUNDING_RULES.
        cleaned["rounding_rule"] = _choice(payload, "rounding_rule", TAX_ROUNDING_RULES, fe)
    if "due_date_rule" in payload:
        # CR-165 §7 item 3 — the six drawn choices, stored as CODES with one
        # evaluator (`selectors.next_filing_due`). A legacy free-text value the
        # row already holds is accepted UNCHANGED (a correction or a new rate
        # restates every field), and never rewritten; anything else must be a
        # code.
        raw_rule = payload.get("due_date_rule")
        legacy = tax is not None and raw_rule == tax.due_date_rule
        if raw_rule in (None, ""):
            cleaned["due_date_rule"] = None
        elif legacy:
            cleaned["due_date_rule"] = tax.due_date_rule
        else:
            cleaned["due_date_rule"] = _choice(
                payload, "due_date_rule", tuple(selectors.DUE_DATE_RULES), fe
            )
    if "authority_account_id" in payload:
        cleaned["authority_account_id"] = _validated_authority_account(
            payload.get("authority_account_id"),
            fe,
            keep=tax.authority_account_id if tax is not None else None,
        )
    if "remit_method" in payload:
        cleaned["remit_method"] = _choice(payload, "remit_method", TAX_REMIT_METHODS, fe)
    if "remit_reference" in payload:
        cleaned["remit_reference"] = _text(payload, "remit_reference", fe, max_length=64)
    if "collection_allowance_percent" in payload:
        # A FRACTION, the same convention `rate` uses (0.5% is 0.005000).
        # Bounded 0..1 because an allowance above 100% of what is collected
        # would have the utility keeping more than it billed — the one bound
        # here that is arithmetic rather than policy.
        cleaned["collection_allowance_percent"] = _decimal(
            payload,
            "collection_allowance_percent",
            fe,
            minimum=Decimal("0"),
            maximum=Decimal("1"),
        )
    if "collection_allowance_gl_account_id" in payload:
        # ⚠ ITS OWN ACCOUNT, AND NOT THE LIABILITY ONE. The allowance is the
        # utility's INCOME — money it keeps for filing on time — where the
        # collected tax is somebody else's, which is part 4's sharpest sentence.
        # Posting one to the other would report a liability as revenue.
        # Validated through the SAME ledger check (CR-008 ruling 3: an account
        # is validated when it is picked), so "a usable account" means one thing
        # in all four places rating stores a GL pointer.
        cleaned["collection_allowance_gl_account_id"] = _validated_gl_account(
            payload,
            "collection_allowance_gl_account_id",
            fe,
            message_key="rating.taxes.gl_account_unknown",
        )
    if "interest_penalty_percent" in payload:
        cleaned["interest_penalty_percent"] = _decimal(
            payload, "interest_penalty_percent", fe, minimum=Decimal("0")
        )
    if "interest_penalty_basis" in payload:
        cleaned["interest_penalty_basis"] = _choice(
            payload, "interest_penalty_basis", TAX_INTEREST_BASES, fe
        )
    # A percent with no period is not a rate (see TAX_INTEREST_BASES). Refused
    # rather than defaulted: guessing `monthly` on a figure the authority states
    # annually is a 12x error in the utility's own liability.
    if cleaned.get("interest_penalty_percent") is not None and not (
        cleaned.get("interest_penalty_basis") or payload.get("interest_penalty_basis")
    ):
        fe.append(
            _field_error("interest_penalty_basis", errors.VAL_REQUIRED, "rating.required")
        )
    if "filing_reminder_recipient" in payload:
        cleaned["filing_reminder_recipient"] = _text(
            payload, "filing_reminder_recipient", fe, max_length=254
        )
    if "discount_treatment" in payload:
        # DEF-382 — statutory and per authority. NOT nullable: the column
        # carries a default so every authority states an answer, and a blank
        # would put the product back where it was, with one behaviour nobody
        # could see or contradict.
        #
        # ⚠ THE BLANK FALLBACK IS THE MODEL'S OWN DEFAULT, READ FROM THE FIELD
        # (DEF-652, 2026-08-28). It used to name `before` here as a literal, so
        # when the PO's ruling moved the column default to `after` this line
        # would have gone on writing the OLD answer for anyone posting an empty
        # string — one screen's blank quietly disagreeing with every other path
        # that builds a tax. There is one default and it lives on the column.
        cleaned["discount_treatment"] = (
            _choice(payload, "discount_treatment", DISCOUNT_TREATMENTS, fe)
            or models.Tax._meta.get_field("discount_treatment").default
        )
    if "liability_gl_account_id" in payload:
        cleaned["liability_gl_account_id"] = _validated_liability_account(payload, fe)
    if "remit_to" in payload:
        cleaned["remit_to"] = _text(payload, "remit_to", fe, max_length=120)
    if "filing_frequency" in payload:
        cleaned["filing_frequency"] = _choice(payload, "filing_frequency", FILING_FREQUENCIES, fe)
    if "filing_form" in payload:
        cleaned["filing_form"] = _text(payload, "filing_form", fe, max_length=60)
    effective_from = (
        _date_value(payload, "effective_from", fe) if "effective_from" in payload else None
    )
    effective_to = _date_value(payload, "effective_to", fe) if "effective_to" in payload else None
    if "effective_from" in payload:
        cleaned["effective_from"] = effective_from
    if "effective_to" in payload:
        cleaned["effective_to"] = effective_to
    if effective_from and effective_to and effective_from >= effective_to:
        fe.append(_field_error("effective_to", errors.VAL_RANGE, "rating.taxes.window_inverted"))
    jurisdiction, inline = _resolve_jurisdiction(
        payload.get("jurisdiction"), fe, required=not partial
    )
    _refuse(fe)
    cleaned["_jurisdiction"] = jurisdiction
    cleaned["_jurisdiction_inline"] = inline
    return cleaned


@require_role(SYSTEM_ADMIN)
def create_tax(actor: Any, payload: Any, *, as_draft: bool = False) -> dict[str, Any]:
    """S13 save. Tax rate changes are NEW rows with their own effective window
    (BR-RAT-037 discipline) — this never rewrites a historical rate.

    ── `as_draft` IS PART 4 STEP 4's FIRST OUTCOME (DEF-387) ─────────────────
    *"Draft / Save & schedule / Activate."* A draft is a tax nobody has put into
    force: it reads **Draft** on TAX-01, `tax_in_force` returns False for it and
    it prices nothing at all. `as_draft=False` stays the default so every
    existing caller — the API's POST /taxes, the fixture seeder, every test —
    creates an ACTIVE tax exactly as it always has, and no seeded rate silently
    stops billing.

    *Save & schedule* is not a third path: it is this call with an
    `effective_from` in the future, which reads **Scheduled** and starts pricing
    on the date the statute says. One save plus a date, which is what TAX-02
    already tells the operator on screen.
    """
    payload = _require_dict(payload)
    cleaned = _validate_tax(payload, partial=False)
    if as_draft:
        # DEFAULT IS NOT-A-DRAFT (see `models.Tax.is_draft`): asking for a
        # draft is the thing you type, so no existing caller changes behaviour
        # and no path that forgets this argument mints a rate that never bills.
        cleaned["is_draft"] = True
    jurisdiction = cleaned.pop("_jurisdiction")
    inline = cleaned.pop("_jurisdiction_inline")
    with transaction.atomic():
        if jurisdiction is None and inline is not None:
            jurisdiction = models.TaxJurisdiction.objects.create(tenant_id=_tenant_id(), **inline)
            _audit(
                actor,
                "tax_jurisdiction.created",
                "tax_jurisdiction",
                jurisdiction.id,
                after=_json_safe(selectors.jurisdiction_row(jurisdiction)),
            )
        tax = models.Tax.objects.create(
            tenant_id=_tenant_id(), jurisdiction=jurisdiction, **cleaned
        )
        _audit(actor, "tax.created", "tax", tax.id, after=_json_safe(selectors.tax_row(tax)))
    return selectors.tax_row(tax)


@require_role(SYSTEM_ADMIN)
def update_tax(actor: Any, tax_id: Any, payload: Any) -> dict[str, Any]:
    """PATCH one tax — and REFUSE the half of it part 4 forbids (DEF-384).

    CR-013 part 4, shared rules, verbatim: *"in-place edits of an active version
    are refused outright, even for Owner/Admin, because rate history is an audit
    artefact; a historic typo is fixed by a documented correction version with a
    reason."* TAX-02 has refused this on the CLIENT since it was built. **A
    client-side refusal is not a refusal** — `PATCH /taxes/{id}` accepted a new
    rate on a live tax from anything that could reach the API — so the rule is
    enforced here, where it is true for every caller.

    ── WHAT IS REFUSED IS RATE HISTORY, NOT EVERY FIELD ─────────────────────
    `TAX_RATE_HISTORY_FIELDS` is the list, and its own comment says why the
    boundary is drawn there: part 4's refusal is REASONED (*"because rate
    history is an audit artefact"*), and a bookkeeper's email address is not
    rate history. Filing detail stays editable in place on a live tax; the rate,
    its base, its scope and its window do not. That reading is a judgment
    recorded in the decision log, not a rule quoted from the CR.

    A DRAFT is freely editable in every field — it has never priced anything, so
    there is no history to protect. A SUPERSEDED row is frozen entirely: it is
    the audit artefact.
    """
    payload = _require_dict(payload)
    with transaction.atomic():
        tax = selectors.tax_or_404(tax_id)
        if "liability_gl_account_id" in payload and not tax.is_draft:
            # ⚠ PO 2026-10-03, verbatim (decision log *"THREE PO ANSWERS"*):
            # *"Pick it when you create the tax; change it later only in
            # Settings -a llow it"* — CR-008's *"Settings → Accounting is the
            # only place a GL code is edited"*, with ONE exception at creation.
            # So a live tax's liability account is refused HERE by name and
            # changed through `set_tax_liability_account`, the narrow door
            # Settings › Accounting calls. A DRAFT is still being created, so
            # it may still set it in place.
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="CR-008",
                message_key="rating.taxes.liability_edit_in_settings",
                params={"name": tax.name, "settings_path": f"/taxes/{tax.id}/gl-account"},
            )
        blocked = sorted(set(payload) & set(TAX_RATE_HISTORY_FIELDS))
        if blocked and not tax.is_draft:
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-RAT-104",
                message_key="rating.taxes.in_force_edit_refused",
                params={
                    "name": tax.name,
                    "fields": ",".join(blocked),
                    # NAMED IN THE REFUSAL, because a refusal that does not say
                    # what to do instead is the road ending — which is exactly
                    # the shape DEF-384 was filed for.
                    "correction_path": f"/taxes/{tax.id}/corrections",
                },
            )
        cleaned = _validate_tax(payload, partial=True, tax=tax)
        jurisdiction = cleaned.pop("_jurisdiction")
        inline = cleaned.pop("_jurisdiction_inline")
        before = _json_safe(selectors.tax_row(tax))
        if jurisdiction is None and inline is not None:
            jurisdiction = models.TaxJurisdiction.objects.create(tenant_id=_tenant_id(), **inline)
        if jurisdiction is not None:
            tax.jurisdiction = jurisdiction
            cleaned["jurisdiction"] = jurisdiction
        for field, value in cleaned.items():
            setattr(tax, field, value)
        if cleaned:
            tax.save(update_fields=[*cleaned.keys(), "updated_at"])
        after = _json_safe(selectors.tax_row(tax))
        if before != after:
            _audit(actor, "tax.updated", "tax", tax.id, before=before, after=after)
    return selectors.tax_row(tax)


@require_role(SYSTEM_ADMIN)
def set_tax_active(actor: Any, tax_id: Any, active: bool) -> dict[str, Any]:
    """IS-1 deactivate-first for the Taxes & fees tab."""
    with transaction.atomic():
        tax = selectors.tax_or_404(tax_id)
        before = _json_safe(selectors.tax_row(tax))
        tax.deleted_at = None if active else Now()
        tax.save(update_fields=["deleted_at", "updated_at"])
        tax.refresh_from_db(fields=["deleted_at"])
        _audit(
            actor,
            "tax.reactivated" if active else "tax.deactivated",
            "tax",
            tax.id,
            before=before,
            after=_json_safe(selectors.tax_row(tax)),
        )
    return selectors.tax_row(tax)


# ══════════════════════════════════════════════════════════════════════════
# The tax lifecycle and the correction path — CR-013 part 4 (DEF-387, DEF-384)
# ══════════════════════════════════════════════════════════════════════════
#: The money-and-history fields a CORRECTION may restate, and therefore the ones
#: an in-place edit of an in-force tax may NOT touch.
#:
#: ⚠ THE LIST IS THE RULE, SO READ WHAT IS *NOT* IN IT. `remit_to`,
#: `filing_form`, `filing_reminder_recipient`, `remit_method` and the rest of
#: the filing detail stay editable in place on a live tax, because part 4's
#: refusal is reasoned — *"because rate history is an audit artefact"* — and a
#: bookkeeper's email address is not rate history. Refusing those too would have
#: meant minting a correction version to fix a typo in a contact, which is the
#: kind of over-application that gets a rule quietly disabled later.
#:
#: That reading is a JUDGMENT this lane made where part 4 does not spell the
#: boundary out; it is recorded in the decision log with this list, and the half
#: that genuinely cannot be decided from the rules — whether a correction must
#: also restate bills already issued under the wrong figure — is `OQ-310`.
TAX_RATE_HISTORY_FIELDS: tuple[str, ...] = (
    "kind",
    "rate",
    "flat_amount",
    "flat_frequency",
    "per_unit_amount",
    "per_unit_uom",
    "per_meter_amount",
    "applies_above_units",
    "applies_to_services",
    "applies_to_customer_classes",
    "premises_scope_kind",
    "premises_scope_value",
    "base_includes_usage",
    "base_includes_base",
    "discount_treatment",
    "rounding_rule",
    "effective_from",
    "effective_to",
    "jurisdiction",
)

#: Long enough that "typo" is not a reason. Part 4 asks for *"a documented
#: correction version with a reason"*, and a one-word reason documents nothing
#: an auditor can use twelve months later.
MIN_CORRECTION_REASON = 10


@require_role(SYSTEM_ADMIN)
def activate_tax(actor: Any, tax_id: Any, effective_from: Any = None) -> dict[str, Any]:
    """DEF-387 — put a DRAFT tax into force. Step 4's *Activate* and *Save &
    schedule*, which are the same act with and without a future date.

    CR-013 part 4 step 4 offers *"Draft / Save & schedule (future statutory
    date, shows as Scheduled in the rate calendar) / Activate"*. They are not
    three save buttons: they are ONE save plus a date, which is what TAX-02
    already says on screen. A tax activated with an `effective_from` in the
    future reads **Scheduled** and prices nothing until that date arrives
    (`selectors.tax_in_force`); activated with no date or a past one it reads
    **Active** and prices now.

    Activating an already-activated tax is refused rather than being a silent
    no-op: it is the only signal a caller gets that the row it is looking at is
    not the draft it thought it was.
    """
    with transaction.atomic():
        tax = selectors.tax_or_404(tax_id)
        if not tax.is_draft:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-103",
                message_key="rating.taxes.already_activated",
                params={"name": tax.name, "status": selectors.tax_status(tax)},
            )
        before = _json_safe(selectors.tax_row(tax))
        fields = ["is_draft", "updated_at"]
        if effective_from not in (None, ""):
            cleaned_fe: list[dict[str, Any]] = []
            tax.effective_from = _date_value({"effective_from": effective_from}, "effective_from", cleaned_fe)
            _refuse(cleaned_fe)
            fields.append("effective_from")
        tax.is_draft = False
        tax.save(update_fields=fields)
        tax.refresh_from_db(fields=["is_draft", "effective_from"])
        # Hard rule 7 — putting a rate into force is a money action.
        _audit(
            actor,
            "tax.activated",
            "tax",
            tax.id,
            before=before,
            after=_json_safe(selectors.tax_row(tax)),
        )
    return selectors.tax_row(tax)


@require_role(SYSTEM_ADMIN)
def correct_tax(actor: Any, tax_id: Any, payload: Any) -> dict[str, Any]:
    """DEF-384 — the door part 4 points at and nothing implemented.

    CR-013 part 4, shared rules, verbatim: *"in-place edits of an active version
    are refused outright, even for Owner/Admin, because rate history is an audit
    artefact; a historic typo is fixed by a documented correction version with a
    reason."* TAX-02 has refused that edit since it was built, correctly, and
    had **nowhere to send the operator** — the refusal ended the road.

    ── A CORRECTION IS NOT A RATE CHANGE, AND THE DIFFERENCE IS THE WINDOW ───
    A rate CHANGE is already a new row with a NEW effective window (BR-RAT-037,
    and `create_tax`'s own docstring). A CORRECTION restates the SAME window:
    the figure that was recorded for that period was wrong. So this mints a new
    row carrying the corrected values, copies the corrected row's window
    verbatim, links the two, and marks the original superseded so it stops
    pricing. **The original is never rewritten and never deleted** — it keeps
    its rate, its dates and its audit trail, which is what makes part 4's
    *"every rate with statutory date, citation, and amount collected under
    each"* readable at all.

    **Worked:** an authority's rate typed as `0.625000` (62.5 %) instead of
    `0.062500` (6.25 %) charges **`$122.73`** on a `$196.37` taxable bill where
    it should charge **`$12.27`**. Correcting it mints a second row at
    `0.062500` over the same window; the next run charges `$12.27`, and the
    `62.5 %` row stays visible as the thing that happened.

    ── ⚠ WHAT THIS DELIBERATELY DOES NOT DO, AND IT IS THE MONEY HALF ───────
    **It does not touch a single bill already issued.** Hard rule 4 forbids it,
    and part 4's own downstream sentence — *"Bills store the version id, base
    amount and exemptions applied so any past remittance report recomputes
    identically"* — says a past bill is reproduced from what it stored, not from
    what the tax row says today. So the eleven customers already charged
    `$122.73` are still charged `$122.73` until somebody corrects their bills,
    and **nothing in the rules says whether that must happen automatically**.
    That is `OQ-310`, raised rather than chosen, and this service NAMES it in
    the response so the operator is not left believing the money is fixed.
    """
    payload = _require_dict(payload)
    reason = str(payload.get("reason") or "").strip()
    changes = {key: value for key, value in payload.items() if key != "reason"}
    fe: list[dict[str, Any]] = []
    if len(reason) < MIN_CORRECTION_REASON:
        fe.append(_field_error("reason", errors.VAL_REQUIRED, "rating.taxes.correction_reason"))
    if not changes:
        # A correction that corrects nothing would mint an identical row and
        # supersede a live rate for no reason — a break in rate history with no
        # content, which is the opposite of what the rule is protecting.
        fe.append(_field_error("reason", errors.VAL_REQUIRED, "rating.taxes.correction_empty"))
    _refuse(fe)

    with transaction.atomic():
        original = selectors.tax_or_404(tax_id)
        if original.superseded_by_id is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-104",
                message_key="rating.taxes.already_corrected",
                params={"name": original.name},
            )
        if original.is_draft:
            # A DRAFT is not history. It has never priced anything, so there is
            # nothing to preserve and nothing to explain: edit it in place.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-104",
                message_key="rating.taxes.correct_draft",
                params={"name": original.name},
            )
        # ⚠ `tax=original` (`DEF-RAT-9276`): the correction is a new VERSION of
        # this tax, so its code is its own chain's and not a duplicate.
        cleaned = _validate_tax(
            {**_tax_payload_of(original), **changes}, partial=False, tax=original
        )
        cleaned.pop("_jurisdiction_inline", None)
        jurisdiction = cleaned.pop("_jurisdiction")
        before = _json_safe(selectors.tax_row(original))
        correction = models.Tax.objects.create(
            tenant_id=_tenant_id(),
            jurisdiction=jurisdiction,
            # CR-165 — the same tax, the next version (v1 -> v2).
            chain_id=original.chain_id or original.id,
            version_no=_next_version_no(original),
            # THE SAME WINDOW, copied from the row being corrected and not from
            # the payload: a "correction" that moved the window would be a rate
            # change wearing a correction's clothes, and it would silently
            # rewrite which bills the old figure was ever right for.
            **{
                **cleaned,
                "effective_from": original.effective_from,
                "effective_to": original.effective_to,
            },
            corrects=original,
            correction_reason=reason,
            # ⚠ **THE `BY` COLUMN OF THE TAX'S OWN AUDIT TAB, AND IT IS STAMPED
            # HERE BECAUSE THIS IS THE ONE PATH THAT WRITES A CORRECTION.**
            # Nobody types it, so it cannot be wrong — `TariffVersion`'s
            # `submitted_by` established both the shape and the reason
            # (DEF-367). It is deliberately NOT read back out of the two
            # `audit_log` rows written below: `audit_log` is pruned on a
            # retention schedule (hard rule 4's 2026-09-02 narrowing), so a
            # rate history that sourced its authors from there would lose them
            # on the pruning run with nothing raising.
            corrected_by_id=_actor_user_id(actor),
        )
        original.superseded_by = correction
        original.save(update_fields=["superseded_by", "updated_at"])
        _audit(
            actor,
            "tax.corrected",
            "tax",
            original.id,
            before=before,
            after=_json_safe(selectors.tax_row(original)),
        )
        _audit(
            actor,
            "tax.correction_created",
            "tax",
            correction.id,
            after=_json_safe(selectors.tax_row(correction)),
        )
    row = selectors.tax_row(correction)
    # ⚠ SAID OUT LOUD IN THE RESPONSE, not only in a docstring. An operator who
    # has just corrected a wrong rate will reasonably believe the money is
    # fixed. It is not: bills already issued keep the figure they were issued
    # with (hard rule 4), and whether they must be corrected too is unruled.
    row["issued_bills_unchanged"] = True
    row["open_question"] = "OQ-310"
    return row


def _tax_payload_of(tax: models.Tax) -> dict[str, Any]:
    """The corrected row read back as a WRITE payload, so a correction that
    restates one field keeps every other field identical.

    Reading the row rather than making the caller resend everything is what
    stops a correction from silently blanking the scope or the service list
    because the client did not know to include them. Decimals go out as
    strings, which is the shape `_validate_tax` accepts and the shape that never
    round-trips through a float (hard rule 2).
    """
    payload: dict[str, Any] = {
        "name": tax.name,
        "jurisdiction": str(tax.jurisdiction_id) if tax.jurisdiction_id else None,
        "kind": tax.kind,
        "base_includes_usage": tax.base_includes_usage,
        "base_includes_base": tax.base_includes_base,
        "flat_frequency": tax.flat_frequency,
        "per_unit_uom": tax.per_unit_uom,
        "applies_to_services": list(tax.applies_to_services or []),
        "applies_to_customer_classes": list(tax.applies_to_customer_classes or []),
        "premises_scope_kind": tax.premises_scope_kind,
        "premises_scope_value": tax.premises_scope_value,
        "liability_gl_account_id": (
            str(tax.liability_gl_account_id) if tax.liability_gl_account_id else None
        ),
        "remit_to": tax.remit_to,
        "filing_frequency": tax.filing_frequency,
        "filing_form": tax.filing_form,
        "code": tax.code,
        "bill_label": tax.bill_label,
        "tax_type": tax.tax_type,
        "rounding_rule": tax.rounding_rule,
        "due_date_rule": tax.due_date_rule,
        "remit_method": tax.remit_method,
        "remit_reference": tax.remit_reference,
        "collection_allowance_gl_account_id": (
            str(tax.collection_allowance_gl_account_id)
            if tax.collection_allowance_gl_account_id
            else None
        ),
        "interest_penalty_basis": tax.interest_penalty_basis,
        "filing_reminder_recipient": tax.filing_reminder_recipient,
        "discount_treatment": tax.discount_treatment,
        "authority_account_id": (
            str(tax.authority_account_id) if tax.authority_account_id else None
        ),
        "effective_from": tax.effective_from.isoformat() if tax.effective_from else None,
        "effective_to": tax.effective_to.isoformat() if tax.effective_to else None,
    }
    for field in (
        "rate",
        "flat_amount",
        "per_unit_amount",
        "per_meter_amount",
        "applies_above_units",
        "collection_allowance_percent",
        "interest_penalty_percent",
    ):
        value = getattr(tax, field)
        payload[field] = str(value) if value is not None else None
    return {key: value for key, value in payload.items() if value is not None}


@require_role(SYSTEM_ADMIN)
def set_tax_liability_account(actor: Any, tax_id: Any, payload: Any) -> dict[str, Any]:
    """`PATCH /taxes/{id}/gl-account` — Settings › Accounting's door to a tax's
    liability account, and the ONLY one after creation.

    PO 2026-10-03 (*"Pick it when you create the tax; change it later only in
    Settings -a llow it"*) on top of CR-008 (*"Settings → Accounting is the only
    place a GL code is edited"*): the New tax form sets it on create, and
    `update_tax` refuses it on a live tax by name. The shape is
    `set_discount_gl_account`'s: one field, validated through the ledger's own
    liveness check (`_validated_liability_account`), audited with before and
    after (hard rule 7). `null` clears it — the tax then refuses at issue, by
    name (BR-BIL-010).
    """
    body = _require_dict(payload)
    fe: list[dict[str, Any]] = []
    _reject_unknown(body, ("liability_gl_account_id",), fe)
    if "liability_gl_account_id" not in body:
        fe.append(_field_error("liability_gl_account_id", errors.VAL_REQUIRED, "rating.required"))
    _refuse(fe)
    account_id = _validated_liability_account(body, fe)
    _refuse(fe)
    with transaction.atomic():
        tax = selectors.tax_or_404(tax_id)
        before = _json_safe(selectors.tax_row(tax))
        tax.liability_gl_account_id = account_id
        tax.save(update_fields=["liability_gl_account_id", "updated_at"])
        after = _json_safe(selectors.tax_row(tax))
        if before != after:
            _audit(actor, "tax.updated", "tax", tax.id, before=before, after=after)
    return selectors.tax_row(tax)


# ══════════════════════════════════════════════════════════════════════════
# CR-165-BRC10 round 2 · task 3 — new rate from a date, retire, and the
# authority accounts (CR §9; DEF-RAT-9283 · DEF-RAT-9279)
# ══════════════════════════════════════════════════════════════════════════
def _next_version_no(tax: models.Tax) -> int:
    """The chain's highest version + 1 — v1 -> v2 for a correction and for a
    new rate alike. Read inside the writer's transaction, after its lock."""
    top = (
        models.Tax.objects.filter(tenant_id=_tenant_id(), chain_id=tax.chain_id or tax.id)
        .order_by("-version_no")
        .values_list("version_no", flat=True)
        .first()
    )
    return int(top or tax.version_no or 1) + 1


def _lock_chain(tax: models.Tax) -> list[models.Tax]:
    """Every row of this tax's chain, locked FOR UPDATE, oldest first — so two
    clerks saving a new rate on one tax at the same moment queue rather than
    both ending v1 and both minting a v2."""
    return list(
        models.Tax.objects.select_for_update()
        .filter(tenant_id=_tenant_id(), chain_id=tax.chain_id or tax.id)
        .order_by("created_at", "id")
    )


def _is_live(row: models.Tax) -> bool:
    """Can this row price at all — not superseded, not deactivated, not a draft.
    The predicate `ex_taxes_chain_no_overlap` (`rating/0058`) holds apart."""
    return row.superseded_by_id is None and row.deleted_at is None and not row.is_draft


#: What *New rate from a date* may change: the FIGURE and its form, and — as
#: image 28 of the approved drawing shows them editable — WHAT IS TAXED, how
#: DISCOUNTS are treated and the ROUNDING the new version uses (CR-165-BRC10
#: §16, web walk). Never the reach (services, classes, boundary) and never the
#: authority — a different reach is a different tax, or a correction if the
#: reach was typed wrong. The version being replaced keeps its own values: it
#: is only given an end date, so a bill dated before the new start prices
#: exactly as it did.
NEW_RATE_FIELDS: tuple[str, ...] = (
    "kind",
    "rate",
    "flat_amount",
    "flat_frequency",
    "per_unit_amount",
    "per_unit_uom",
    "per_meter_amount",
    "applies_above_units",
    "base_includes_usage",
    "base_includes_base",
    "discount_treatment",
    "rounding_rule",
)


@require_role(SYSTEM_ADMIN)
def new_tax_rate(actor: Any, tax_id: Any, payload: Any) -> dict[str, Any]:
    """🔒 `POST /taxes/{id}/new-rate` — *New rate from a date* (`DEF-RAT-9283`).

    BR-RAT-037 has said since r6.5 that a rate CHANGE is a new row with its own
    window, and nothing ever implemented it: `create_tax` made an UNLINKED row,
    `correct_tax` copies the old window, and `update_tax` refuses `effective_to`
    on a live tax. So the only way to change a rate left two rows in force on
    the new date and the bill refused (CR §6 g).

    **IN ONE TRANSACTION, UNDER A LOCK ON THE CHAIN:**
      1. find the chain's LATEST live version (the one a new rate replaces);
      2. refuse an `effective_from` on or before that version's own start, by
         name — a new rate must start after the rate it replaces started;
      3. END that version the day before `effective_from` (only where it would
         otherwise still be in force on that day);
      4. insert the next version — every other field copied from the version it
         follows, the figure from the payload, `follows` pointing back,
         `version_no` + 1, the same `chain_id` and code;
      5. audit both rows (hard rule 7).

    The old row is ended BEFORE the new one is inserted, so the two never
    overlap even for one statement and `ex_taxes_chain_no_overlap` never needs
    its deferral here.

    **Worked (the web walk's 4.2):** State sales tax v1 6.25% from 01/01/2026,
    open-ended; new rate 6.5% from **11/01/2026** -> v1 ends **10/31/2026**, v2
    starts 11/01/2026. A $60.00 October bill is **$3.75**, November **$3.90**.
    Bills already issued keep the rate they were issued at (hard rule 4).
    """
    payload = _require_dict(payload)
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, (*NEW_RATE_FIELDS, "effective_from", "effective_to", "reason"), fe)
    effective_from = _date_value(payload, "effective_from", fe, required=True)
    effective_to = _date_value(payload, "effective_to", fe)
    if effective_from and effective_to and effective_to < effective_from:
        fe.append(_field_error("effective_to", errors.VAL_RANGE, "rating.taxes.window_inverted"))
    changes = {key: payload[key] for key in NEW_RATE_FIELDS if key in payload}
    if "kind" in changes:
        # A change of FORM drops the old form's figure, so the new version
        # states exactly one (BR-RAT-036) rather than inheriting the old one.
        for amount in ("rate", "flat_amount", "per_unit_amount", "per_meter_amount"):
            changes.setdefault(amount, None)
    if not changes:
        fe.append(_field_error("rate", errors.VAL_REQUIRED, "rating.required"))
    _refuse(fe)
    reason = str(payload.get("reason") or "").strip() or None

    with transaction.atomic():
        asked = selectors.tax_or_404(tax_id)
        chain = _lock_chain(asked)
        live = [row for row in chain if _is_live(row)]
        if not live:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-037",
                message_key="rating.taxes.correct_draft"
                if asked.is_draft
                else "rating.taxes.already_corrected",
                params={"name": asked.name},
            )
        # The version a new rate replaces is the one that starts LAST.
        current = max(live, key=lambda row: (row.effective_from or date.min, row.created_at))
        if current.effective_from is not None and effective_from <= current.effective_from:
            raise errors.ValidationError(
                errors.VAL_RANGE,
                message_key="rating.taxes.new_rate_too_early",
                params={"name": current.name, "starts": current.effective_from.isoformat()},
                field_errors=[
                    _field_error(
                        "effective_from",
                        errors.VAL_RANGE,
                        "rating.taxes.new_rate_too_early",
                        starts=current.effective_from.isoformat(),
                    )
                ],
            )
        cleaned = _validate_tax(
            {
                **_tax_payload_of(current),
                **changes,
                "effective_from": effective_from.isoformat(),
                "effective_to": effective_to.isoformat() if effective_to else None,
            },
            partial=False,
            tax=current,
        )
        cleaned.pop("_jurisdiction_inline", None)
        jurisdiction = cleaned.pop("_jurisdiction")
        before = _json_safe(selectors.tax_row(current))
        day_before = effective_from - timedelta(days=1)
        if current.effective_to is None or current.effective_to > day_before:
            current.effective_to = day_before
            current.save(update_fields=["effective_to", "updated_at"])
        successor = models.Tax.objects.create(
            tenant_id=_tenant_id(),
            jurisdiction=jurisdiction,
            **{**cleaned, "effective_from": effective_from, "effective_to": effective_to},
            chain_id=current.chain_id or current.id,
            version_no=_next_version_no(current),
            follows=current,
        )
        _audit(
            actor,
            "tax.ended_for_new_rate",
            "tax",
            current.id,
            before=before,
            after={**_json_safe(selectors.tax_row(current)), "reason": reason},
        )
        _audit(
            actor,
            "tax.new_rate_created",
            "tax",
            successor.id,
            after={**_json_safe(selectors.tax_row(successor)), "reason": reason},
        )
    row = selectors.tax_row(successor)
    # CR-165 §9 (added by task 3) — what the old version became, so the Review
    # step can say *v1 ends 10/31/2026* without a second read.
    row["ended_version"] = {
        "id": str(current.id),
        "version": current.version_no,
        "effective_to": current.effective_to.isoformat() if current.effective_to else None,
    }
    row["issued_bills_unchanged"] = True
    return row


@require_role(SYSTEM_ADMIN)
def retire_tax(actor: Any, tax_id: Any, payload: Any) -> dict[str, Any]:
    """🔒 `POST /taxes/{id}/retire` — END THE WINDOW, never `deleted_at`
    (CR-165 §7 item 4, our judgment, decision log 2026-10-03).

    A retired tax prices every bill dated up to and including `effective_to`
    and nothing after it — *Retire the 2% Bexar tax on 12/31/2026* means a
    December bill still carries it and a January bill carries no Bexar line.
    `deleted_at` could not say that (it stopped everything at once, and until
    `DEF-RAT-9279` it stopped nothing at all).

    Refused by name when no version of this tax is in force on that date
    (`rating.taxes.retire_not_in_force`), and when a LATER version is already
    scheduled to start after it (`rating.taxes.retire_scheduled_version`) —
    that version would go on pricing, so a retire that left it would be a
    retire in name only.
    """
    payload = _require_dict(payload)
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, ("effective_to", "reason"), fe)
    effective_to = _date_value(payload, "effective_to", fe, required=True)
    _refuse(fe)
    reason = str(payload.get("reason") or "").strip() or None
    with transaction.atomic():
        asked = selectors.tax_or_404(tax_id)
        chain = _lock_chain(asked)
        live = [row for row in chain if _is_live(row)]
        later = [
            row for row in live if row.effective_from is not None and row.effective_from > effective_to
        ]
        if later:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-103",
                message_key="rating.taxes.retire_scheduled_version",
                params={"name": asked.name, "starts": later[0].effective_from.isoformat()},
            )
        target = next((row for row in live if selectors.tax_in_force(row, effective_to)), None)
        if target is None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-103",
                message_key="rating.taxes.retire_not_in_force",
                params={"name": asked.name, "date": effective_to.isoformat()},
            )
        before = _json_safe(selectors.tax_row(target))
        target.effective_to = effective_to
        target.save(update_fields=["effective_to", "updated_at"])
        _audit(
            actor,
            "tax.retired",
            "tax",
            target.id,
            before=before,
            after={**_json_safe(selectors.tax_row(target)), "reason": reason},
        )
    return selectors.tax_row(target)


# ── Settings › Accounting › Authority accounts (CR-165 §7 item 1) ────────────
AUTHORITY_ACCOUNT_FIELDS: tuple[str, ...] = (
    "authority_name",
    "account_number",
    "jurisdiction_id",
    "active",
)


def _validate_authority_account(
    payload: dict[str, Any], *, partial: bool, row: models.TaxAuthorityAccount | None = None
) -> dict[str, Any]:
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, AUTHORITY_ACCOUNT_FIELDS, fe)
    cleaned: dict[str, Any] = {}
    # DEF-RAT-10027 (PO ruling 2026-10-09, option (a)): the authority is PICKED
    # from `tax_jurisdictions`, the list a tax uses. Where a row names its
    # authority by `jurisdiction_id`, the jurisdiction's name IS the authority
    # name — written here, so a linked row can never carry a typed name that
    # disagrees with the authority it points at. A row with no link (typed
    # before the picker) keeps its typed name and is linked by editing.
    linked: models.TaxJurisdiction | None = None
    picks_authority = payload.get("jurisdiction_id") not in (None, "")
    if "jurisdiction_id" in payload:
        if not picks_authority:
            cleaned["jurisdiction_id"] = None
        else:
            linked, _inline = _resolve_jurisdiction(str(payload["jurisdiction_id"]), fe, required=False)
            if linked is not None:
                cleaned["jurisdiction_id"] = linked.id
    for field, limit in (("authority_name", 120), ("account_number", 64)):
        if field == "authority_name" and picks_authority:
            continue
        if field in payload or not partial:
            value = _text(payload, field, fe, required=True, max_length=limit)
            if value is not None:
                cleaned[field] = value
    if linked is not None:
        cleaned["authority_name"] = linked.name
    if "active" in payload:
        cleaned["active"] = _bool(payload, "active", default=True)
    name = cleaned.get("authority_name", row.authority_name if row else None)
    number = cleaned.get("account_number", row.account_number if row else None)
    if name and number:
        clash = models.TaxAuthorityAccount.objects.filter(
            tenant_id=_tenant_id(), authority_name__iexact=name, account_number__iexact=number
        )
        if row is not None:
            clash = clash.exclude(pk=row.pk)
        if clash.exists():
            fe.append(
                _field_error(
                    "account_number", errors.VAL_FORMAT, "rating.authorityAccounts.duplicate"
                )
            )
    _refuse(fe)
    return cleaned


@require_role(SYSTEM_ADMIN)
def create_authority_account(actor: Any, payload: Any) -> dict[str, Any]:
    """Add one account the utility holds with a tax authority — typed ONCE here
    and picked on every tax (CR-165 §7 item 1)."""
    payload = _require_dict(payload)
    cleaned = _validate_authority_account(payload, partial=False)
    with transaction.atomic():
        row = models.TaxAuthorityAccount.objects.create(tenant_id=_tenant_id(), **cleaned)
        _audit(
            actor,
            "tax_authority_account.created",
            "tax_authority_account",
            row.id,
            after=_json_safe(selectors.authority_account_row(row)),
        )
    return selectors.authority_account_row(row)


@require_role(SYSTEM_ADMIN)
def update_authority_account(actor: Any, account_id: Any, payload: Any) -> dict[str, Any]:
    """Edit or retire (`active: false`) one authority account. A retired account
    stays on every tax that files under it and leaves the picker."""
    payload = _require_dict(payload)
    with transaction.atomic():
        row = selectors.authority_account_or_404(account_id)
        cleaned = _validate_authority_account(payload, partial=True, row=row)
        before = _json_safe(selectors.authority_account_row(row))
        for field, value in cleaned.items():
            setattr(row, field, value)
        if cleaned:
            row.save(update_fields=[*cleaned.keys(), "updated_at"])
        after = _json_safe(selectors.authority_account_row(row))
        if before != after:
            _audit(
                actor,
                "tax_authority_account.updated",
                "tax_authority_account",
                row.id,
                before=before,
                after=after,
            )
    return selectors.authority_account_row(row)


# ══════════════════════════════════════════════════════════════════════════
# Exemption categories & certificates — CR-013 part 4 (DEF-383)
# ══════════════════════════════════════════════════════════════════════════
EXEMPTION_CATEGORY_FIELDS: tuple[str, ...] = (
    "code",
    "name",
    "requires_certificate",
    "certificate_requirement",
)
EXEMPTION_CERTIFICATE_FIELDS: tuple[str, ...] = (
    "account_id",
    "certificate_ref",
    "issued_on",
    "expires_on",
)


@require_role(SYSTEM_ADMIN)
def create_exemption_category(actor: Any, tax_id: Any, payload: Any) -> dict[str, Any]:
    """One of THIS authority's exemption categories (part 4 step 2).

    A category belongs to one tax and not to a shared catalogue, because an
    authority's exemption categories are that authority's statute — Texas'
    religious exemption is not Bexar County's, and a shared list would need
    every authority to agree on which categories exist.
    """
    payload = _require_dict(payload)
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, EXEMPTION_CATEGORY_FIELDS, fe)
    code = _text(payload, "code", fe, required=True, max_length=32)
    name = _text(payload, "name", fe, required=True, max_length=120)
    requirement = _text(payload, "certificate_requirement", fe, max_length=240)
    requires = _bool(payload, "requires_certificate", default=True)
    _refuse(fe)
    with transaction.atomic():
        tax = selectors.tax_or_404(tax_id)
        if (
            models.TaxExemptionCategory.objects.filter(tenant_id=_tenant_id(), tax_id=tax.id)
            .filter(code__iexact=code)
            .exists()
        ):
            _refuse([_field_error("code", errors.VAL_FORMAT, "rating.taxes.duplicate_category")])
        category = models.TaxExemptionCategory.objects.create(
            tenant_id=_tenant_id(),
            tax=tax,
            code=(code or "").upper(),
            name=name,
            requires_certificate=requires,
            certificate_requirement=requirement,
        )
        _audit(
            actor,
            "tax_exemption_category.created",
            "tax_exemption_category",
            category.id,
            after=_json_safe(selectors.exemption_category_row(category)),
        )
    return selectors.exemption_category_row(category)


@require_role(SYSTEM_ADMIN, BILLING_CLERK)
def record_exemption_certificate(actor: Any, category_id: Any, payload: Any) -> dict[str, Any]:
    """ONE ACCOUNT'S claim against one category, with its expiry (part 4).

    ⚖️ **A BILLING CLERK RECORDS IT TOO** — PO ruling 2026-10-05 (decision log
    *"FOUR PO RULINGS IN ONE REPLY"* (2), option (b)), verbatim: *"Let billing
    clerks record it themselves. - we have set the limits so clark can do it -
    its a day to day work"*. Worked: Marcus records a church's certificate
    against a 2.00% city tax at move-in and its $100.00 bill carries $0.00 of
    that tax. The CATEGORY (which tax, whether a certificate is required) stays
    System Admin's, and so does revoking; the Plans & Rates door that also
    reaches this function stays System Admin's too (`api.
    tax_exemption_certificates`, A4: Plans & Rates is View for a clerk), so the
    clerk records from the ACCOUNT side (the move-in), where A4 gives Full.

    ⚠ **A MONEY ACTION.** Recording this stops an authority's tax appearing on
    that customer's bills, so it audits (hard rule 7) — and so does revoking it.
    An exemption granted with no trail is the thing an authority asks about.

    The account id is checked through the CUSTOMERS seam rather than trusted:
    an unrecognised uuid stored here would look like a live exemption for ever
    and match no bill, which is a silent no-op nobody could find.
    """
    payload = _require_dict(payload)
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, EXEMPTION_CERTIFICATE_FIELDS, fe)
    account_id = _text(payload, "account_id", fe, required=True, max_length=64)
    reference = _text(payload, "certificate_ref", fe, max_length=64)
    issued_on = _date_value(payload, "issued_on", fe) if "issued_on" in payload else None
    expires_on = _date_value(payload, "expires_on", fe) if "expires_on" in payload else None
    if issued_on and expires_on and issued_on > expires_on:
        fe.append(_field_error("expires_on", errors.VAL_RANGE, "rating.taxes.window_inverted"))
    _refuse(fe)
    with transaction.atomic():
        category = selectors.exemption_category_or_404(category_id)
        if category.deleted_at is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-105",
                message_key="rating.taxes.category_inactive",
                params={"name": category.name},
            )
        if category.requires_certificate and not reference:
            # The category's own rule, enforced where it is stated. A category
            # that requires a certificate and holds claims with no reference is
            # a list of customers the utility cannot defend to an authority.
            _refuse(
                [
                    _field_error(
                        "certificate_ref", errors.VAL_REQUIRED, "rating.taxes.certificate_required"
                    )
                ]
            )
        if not seams.account_exists(account_id):
            _refuse(
                [
                    _field_error(
                        "account_id", errors.VAL_UNKNOWN_LOOKUP, "rating.taxes.unknown_account"
                    )
                ]
            )
        existing = models.TaxExemptionCertificate.objects.filter(
            tenant_id=_tenant_id(),
            category_id=category.id,
            account_id=account_id,
            revoked_at__isnull=True,
        ).first()
        if existing is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-105",
                message_key="rating.taxes.certificate_exists",
                params={"category": category.name},
            )
        certificate = models.TaxExemptionCertificate.objects.create(
            tenant_id=_tenant_id(),
            category=category,
            account_id=account_id,
            certificate_ref=reference,
            issued_on=issued_on,
            expires_on=expires_on,
            verified_by_id=getattr(actor, "id", None),
        )
        _audit(
            actor,
            "tax_exemption_certificate.recorded",
            "tax_exemption_certificate",
            certificate.id,
            after=_json_safe(selectors.exemption_certificate_row(certificate)),
        )
    return selectors.exemption_certificate_row(certificate)


@require_role(SYSTEM_ADMIN)
def revoke_exemption_certificate(actor: Any, certificate_id: Any) -> dict[str, Any]:
    """Withdraw a claim NOW, without waiting for it to expire.

    Revoked, never deleted: an authority that disallows a claim needs to see
    WHEN the utility stopped honouring it, and a deleted row answers nothing.
    """
    with transaction.atomic():
        certificate = models.TaxExemptionCertificate.objects.filter(
            tenant_id=_tenant_id(), pk=certificate_id
        ).first()
        if certificate is None:
            raise errors.NotFoundError()
        if certificate.revoked_at is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-105",
                message_key="rating.taxes.already_revoked",
            )
        before = _json_safe(selectors.exemption_certificate_row(certificate))
        certificate.revoked_at = Now()
        certificate.save(update_fields=["revoked_at", "updated_at"])
        certificate.refresh_from_db(fields=["revoked_at"])
        _audit(
            actor,
            "tax_exemption_certificate.revoked",
            "tax_exemption_certificate",
            certificate.id,
            before=before,
            after=_json_safe(selectors.exemption_certificate_row(certificate)),
        )
    return selectors.exemption_certificate_row(certificate)


# ══════════════════════════════════════════════════════════════════════════
# Bulk rate update — US-RAT-011 (EP-RAT-04)
# ══════════════════════════════════════════════════════════════════════════
BATCH_FIELDS: tuple[str, ...] = ("entities", "change", "effective_from", "reason", "preview")


def _fingerprint(cleaned: dict[str, Any]) -> str:
    """Deterministic batch identity — the local half of BR-RAT-040 ("batches
    are append-only and never re-run"). core/idempotency.py is a 🔒 Eng-Lead
    stub, so this lane does NOT invent a platform key scheme."""
    material = {
        "entities": sorted(f"{entity['type']}:{entity['id']}" for entity in cleaned["entities"]),
        "change": {"kind": cleaned["change"]["kind"], "value": str(cleaned["change"]["value"])},
        "effective_from": cleaned["effective_from"].isoformat(),
        "reason": cleaned["reason"],
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def _validate_batch(payload: dict[str, Any]) -> dict[str, Any]:
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, BATCH_FIELDS, fe)
    reason = _text(payload, "reason", fe, required=True, max_length=500)  # TC-4: required
    effective_from = _date_value(payload, "effective_from", fe, required=True)

    change_raw = payload.get("change")
    change: dict[str, Any] = {}
    if not isinstance(change_raw, dict):
        fe.append(_field_error("change", errors.VAL_REQUIRED, "rating.required"))
    else:
        _reject_unknown(change_raw, ("kind", "value"), fe, prefix="change.")
        kind = _choice(change_raw, "kind", BULK_CHANGE_KINDS, fe, required=True, prefix="change.")
        value = _decimal(change_raw, "value", fe, required=True, prefix="change.")
        if kind == "percent" and value is not None and value == Decimal("0"):
            fe.append(_field_error("change.value", errors.VAL_RANGE, "rating.bulk.percent_zero"))
        if kind == "set" and value is not None and value < Decimal("0"):
            fe.append(_field_error("change.value", errors.VAL_RANGE, "rating.below_minimum"))
        change = {"kind": kind, "value": value}

    entities_raw = payload.get("entities")
    entities: list[dict[str, Any]] = []
    if not isinstance(entities_raw, list) or not entities_raw:
        fe.append(_field_error("entities", errors.VAL_REQUIRED, "rating.bulk.entities_required"))
    else:
        for index, item in enumerate(entities_raw):
            prefix = f"entities[{index}]."
            entity = item if isinstance(item, dict) else {"type": "schedule", "id": item}
            _reject_unknown(entity, ("type", "id"), fe, prefix=prefix)
            entity_type = _choice(
                entity, "type", ("schedule", "plan"), fe, required=True, prefix=prefix
            )
            entity_id = _uuid_value(entity, "id", fe, required=True, prefix=prefix)
            if entity_type is None or entity_id is None:
                continue
            if entity_type == "schedule":
                row = models.Tariff.objects.filter(tenant_id=_tenant_id(), pk=entity_id).first()
            else:
                row = models.RatePlan.objects.filter(tenant_id=_tenant_id(), pk=entity_id).first()
            if row is None:
                fe.append(
                    _field_error(
                        f"{prefix}id", errors.VAL_UNKNOWN_LOOKUP, "rating.bulk.unknown_entity"
                    )
                )
                continue
            entities.append({"type": entity_type, "id": str(entity_id), "row": row})
    _refuse(fe)
    cleaned = {
        "entities": entities,
        "change": change,
        "effective_from": effective_from,
        "reason": reason,
    }
    cleaned["fingerprint"] = _fingerprint(cleaned)
    return cleaned


def _changed_price(value: Decimal, change: dict[str, Any]) -> Decimal:
    """+N % or set-to. NUMERIC(18,6) throughout — no premature rounding, and
    no B4 money rounding (that happens at invoice-line finalization)."""
    if change["kind"] == "percent":
        multiplier = Decimal("1") + (change["value"] / Decimal("100"))
        return _q6(value * multiplier)
    return _q6(change["value"])


def preview_rate_change(cleaned: dict[str, Any]) -> list[dict[str, Any]]:
    """IS-6: every before → after is shown before the money action commits."""
    rows: list[dict[str, Any]] = []
    for entity in cleaned["entities"]:
        if entity["type"] == "schedule":
            tariff = entity["row"]
            version = selectors.latest_version(tariff)
            if version is None:
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="BR-RAT-040",
                    message_key="rating.bulk.entity_without_version",
                    params={"entity": tariff.name},
                )
            _guard_batch_window(tariff, version, cleaned["effective_from"])
            changes = [
                {
                    "field": f"tier[{tier.seq}].unit_price",
                    "before": str(tier.unit_price),
                    "after": str(_changed_price(tier.unit_price, cleaned["change"])),
                }
                for tier in models.RateTier.objects.filter(
                    tenant_id=_tenant_id(), tariff_version=version
                ).order_by("seq")
            ] + [
                {
                    "field": f"window[{window.label}].unit_price",
                    "before": str(window.unit_price),
                    "after": str(_changed_price(window.unit_price, cleaned["change"])),
                }
                for window in models.TimeOfUseWindow.objects.filter(
                    tenant_id=_tenant_id(), tariff_version=version
                ).order_by("label")
            ]
            rows.append(
                {"type": "schedule", "id": str(tariff.id), "name": tariff.name, "changes": changes}
            )
        else:
            plan = entity["row"]
            changes = [
                {
                    "field": f"base_charge[{row.service.code}]",
                    "before": str(row.base_charge),
                    "after": str(_changed_price(row.base_charge, cleaned["change"])),
                }
                for row in models.PlanService.objects.filter(rate_plan=plan)
                .select_related("service")
                .order_by("service__code")
            ]
            rows.append({"type": "plan", "id": str(plan.id), "name": plan.name, "changes": changes})
    return rows


def _guard_batch_window(
    tariff: models.Tariff, version: models.TariffVersion, effective_from: date
) -> None:
    """US-RAT-011 TC-5: a conflicting pending version aborts the WHOLE batch,
    naming the entity — zero partial writes (BR-RAT-040 atomicity)."""
    if effective_from <= version.effective_from:
        raise errors.BizError(
            errors.BIZ_WINDOW,
            br_ref="BR-RAT-040",
            message_key="rating.bulk.entity_window_conflict",
            params={"entity": tariff.name, "current_from": version.effective_from.isoformat()},
        )


@require_role(SYSTEM_ADMIN)
def request_rate_change_batch(actor: Any, payload: Any) -> dict[str, Any]:
    """A4: Plans & Rates writes are Admin-only (US-RAT-011 TC-7). Validates and
    previews SYNCHRONOUSLY (so a bad batch never becomes a job), then hands the
    apply to the BE-07 async contract: 202 + job_id, poll /jobs/{id}."""
    payload = _require_dict(payload)
    cleaned = _validate_batch(payload)
    existing = selectors.batch_by_fingerprint(cleaned["fingerprint"])
    if existing is not None:
        # US-RAT-011 TC-6: a completed batch is never re-run (BR-RAT-040). This
        # is checked BEFORE the preview so a replay is refused as a replay, not
        # as the window conflict its own first run created.
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-RAT-040",
            message_key="rating.bulk.batch_already_applied",
            params={"batch_id": str(existing.id), "created_at": str(existing.created_at)},
        )
    preview = preview_rate_change(cleaned)
    if payload.get("preview"):
        return {"preview": preview, "fingerprint": cleaned["fingerprint"]}
    record = core_jobs.enqueue(
        RATE_CHANGE_JOB,
        payload={
            "entities": [
                {"type": entity["type"], "id": entity["id"]} for entity in cleaned["entities"]
            ],
            "change": {
                "kind": cleaned["change"]["kind"],
                "value": str(cleaned["change"]["value"]),
            },
            "effective_from": cleaned["effective_from"].isoformat(),
            "reason": cleaned["reason"],
            "fingerprint": cleaned["fingerprint"],
            "actor_user_id": str(_actor_user_id(actor)) if _actor_user_id(actor) else None,
        },
        scope_key=cleaned["fingerprint"],
    )
    return core_jobs.accepted(record)


def apply_rate_change_batch(record: dict[str, Any]) -> str:
    """The job body (BE-07 runner contract). ONE transaction: one batch row +
    one new version per schedule + one rate_change_log row per entity — a
    failed entity aborts everything (BR-RAT-040 all-or-none).

    Role was checked at enqueue (request_rate_change_batch); the worker carries
    the actor id in the record, never a role, so it can grant nothing."""
    payload = record["payload"]
    cleaned = _rehydrate_batch(payload)
    actor_user_id = payload.get("actor_user_id")
    with transaction.atomic():
        existing = selectors.batch_by_fingerprint(cleaned["fingerprint"])
        if existing is not None:
            raise errors.BizError(
                errors.BIZ_IDEMPOTENT,
                br_ref="BR-RAT-040",
                message_key="rating.bulk.batch_already_applied",
                params={"batch_id": str(existing.id)},
            )
        batch = models.RateChangeBatch.objects.create(
            tenant_id=_tenant_id(),
            reason=cleaned["reason"],
            change_spec={
                "kind": cleaned["change"]["kind"],
                "value": str(cleaned["change"]["value"]),
                "effective_from": cleaned["effective_from"].isoformat(),
                "entities": [
                    {"type": entity["type"], "id": entity["id"]} for entity in cleaned["entities"]
                ],
                "fingerprint": cleaned["fingerprint"],
            },
            actor_id=actor_user_id,
        )
        # CR-157-BRC10 · `DEF-RAT-8750` — EVERY schedule of the batch is locked
        # BEFORE any is written, in ascending id, schedule rows before their
        # versions — the one order every single-schedule save path also takes
        # (`_lock_schedule`), so a batch and a clerk's save, or two batches over
        # overlapping schedules, can wait on each other but never deadlock.
        locked: dict[str, models.Tariff] = {}
        for tariff_id in sorted(
            str(entity["row"].pk) for entity in cleaned["entities"] if entity["type"] == "schedule"
        ):
            locked[tariff_id] = _lock_schedule(tariff_id)
        for entity in cleaned["entities"]:
            if entity["type"] == "schedule":
                tariff = locked[str(entity["row"].pk)]
                _apply_batch_to_schedule(batch, tariff, cleaned, actor_user_id)
                _check_windows_now(tariff, cleaned["effective_from"])
            else:
                _apply_batch_to_plan(batch, entity["row"], cleaned, actor_user_id)
        core_audit.write_row(
            action="rating.bulk_rate_update",
            entity_type="rate_change_batch",
            entity_id=batch.id,
            actor_user_id=actor_user_id,
            after={
                "batch_id": str(batch.id),
                "entities": len(cleaned["entities"]),
                "reason": cleaned["reason"],
                "effective_from": cleaned["effective_from"].isoformat(),
            },
        )
    return f"/rate-changes/{batch.id}"


def _rehydrate_batch(payload: dict[str, Any]) -> dict[str, Any]:
    """Re-resolve the job payload against live rows (TD-17: the record, not the
    caller's memory, is the truth a resumed run reads)."""
    entities: list[dict[str, Any]] = []
    for entity in payload["entities"]:
        if entity["type"] == "schedule":
            row = models.Tariff.objects.filter(tenant_id=_tenant_id(), pk=entity["id"]).first()
        else:
            row = models.RatePlan.objects.filter(tenant_id=_tenant_id(), pk=entity["id"]).first()
        if row is None:
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-RAT-040",
                message_key="rating.bulk.unknown_entity",
                params={"id": entity["id"]},
            )
        entities.append({**entity, "row": row})
    return {
        "entities": entities,
        "change": {
            "kind": payload["change"]["kind"],
            "value": Decimal(str(payload["change"]["value"])),
        },
        "effective_from": date.fromisoformat(payload["effective_from"]),
        "reason": payload["reason"],
        "fingerprint": payload["fingerprint"],
    }


def _apply_batch_to_schedule(
    batch: models.RateChangeBatch,
    tariff: models.Tariff,
    cleaned: dict[str, Any],
    actor_user_id: Any,
) -> None:
    tenant_id = _tenant_id()
    version = selectors.latest_version(tariff)
    if version is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-RAT-040",
            message_key="rating.bulk.entity_without_version",
            params={"entity": tariff.name},
        )
    effective_from = cleaned["effective_from"]
    _guard_batch_window(tariff, version, effective_from)
    before = _json_safe(selectors.version_row(version))

    # ── `DEF-RAT-8003` · THIS COMMENT CLAIMED A GUARANTEE THAT DID NOT EXIST
    # (hard-won law 1) ───────────────────────────────────────────────────────
    # It read: *"Close the old window FIRST: two open-ended windows would
    # collide with the B2 EXCLUDE constraint on Postgres"*. **There was no such
    # constraint.** B2 §2 signs one; `rating/0001` never materialised it
    # because `btree_gist` was not installed, and `rating/0004` reported that
    # in its own header and left it *"for the human review of this row"*, which
    # never happened. So the only thing standing between a bulk uplift and two
    # open windows was the line below — and the line below closed ONE row.
    # There IS a constraint now (`rating/0047`,
    # `ex_tariff_versions_no_overlap`, DEFERRABLE INITIALLY DEFERRED), and this
    # comment is worth keeping as the reason the next lane should not delete
    # the close and lean on the database: a constraint refuses the COMMIT with
    # PostgreSQL's own message, where closing the window is the behaviour a
    # clerk asked for.
    #
    # ── `DEF-RAT-8001` · AND IT CLOSED ONE ROW ─────────────────────────────
    # `selectors.latest_version(tariff)` is the NEWEST activated version, so a
    # schedule that already had two open windows kept one for ever, whatever
    # bulk uplifts were run over it.
    _close_open_windows_before(tariff, effective_from)
    version.refresh_from_db(fields=["effective_to", "updated_at"])
    new_version = models.TariffVersion.objects.create(
        tenant_id=tenant_id,
        tariff=tariff,
        model=version.model,
        base_charge=version.base_charge,
        # `DEF-RAT-6932` · `BR-RAT-1025` — **THE NAMED BASE CHARGE CODE, WHICH
        # THIS CLONE SIMPLY DID NOT HAVE.** This is the one writer of
        # `tariff_versions` that does not go through `_write_version` (`DEF-499`
        # named it), so it carries every version fact by hand — including the
        # regulator's filing details below, deliberately — and a column added
        # after it was written reaches it only if somebody comes here. Until
        # this line existed, one clerk's bulk uplift unbound EVERY schedule a
        # utility has, at once, whatever the batch payload said.
        base_charge_code_id=version.base_charge_code_id,
        # `DEF-RAT-8737` (PO 2026-10-01, option A) — the version carries no
        # minimum; the size rows below carry it, and are cloned with it.
        minimum_bill=None,
        currency=version.currency,
        uom=version.uom,
        percent=version.percent,
        basis_service_id=version.basis_service_id,
        effective_from=effective_from,
        effective_to=None,
        regulator_ref=version.regulator_ref,
        # BR-RAT-082 — a bulk uplift carries the filing details of the version it
        # was computed from. They are metadata about a sign-off that happened,
        # so they travel with the numbers rather than being blanked.
        filing_authority=version.filing_authority,
        filed_on=version.filed_on,
        regulator_approved_on=version.regulator_approved_on,
        regulator_approver=version.regulator_approver,
    )
    for size_row in models.RateSizeRow.objects.filter(
        tenant_id=tenant_id, tariff_version=version
    ).order_by("size_class"):
        # DEF-360. Copied VERBATIM — `cleaned["change"]` is an uplift on TIER
        # PRICES, and `base_charge`/`minimum_bill` above are already carried
        # unchanged by this same clone. Applying the uplift here would reprice a
        # floor that BR-RAT-040's batch never asked about.
        models.RateSizeRow.objects.create(
            tenant_id=tenant_id,
            tariff_version=new_version,
            size_class=size_row.size_class,
            minimum_bill=size_row.minimum_bill,
            currency=size_row.currency,
        )
    season_map: dict[Any, models.RateSeason] = {}
    for season in models.RateSeason.objects.filter(
        tenant_id=tenant_id, tariff_version=version
    ).order_by("start_month", "start_day"):
        season_map[season.id] = models.RateSeason.objects.create(
            tenant_id=tenant_id,
            tariff_version=new_version,
            label=season.label,
            start_month=season.start_month,
            start_day=season.start_day,
            end_month=season.end_month,
            end_day=season.end_day,
        )
    for tier in models.RateTier.objects.filter(
        tenant_id=tenant_id, tariff_version=version
    ).order_by("seq"):
        models.RateTier.objects.create(
            tenant_id=tenant_id,
            tariff_version=new_version,
            season=season_map.get(tier.season_id),
            seq=tier.seq,
            from_qty=tier.from_qty,
            to_qty=tier.to_qty,
            unit_price=_changed_price(tier.unit_price, cleaned["change"]),
        )
    for window in models.TimeOfUseWindow.objects.filter(
        tenant_id=tenant_id, tariff_version=version
    ).order_by("start_time"):
        models.TimeOfUseWindow.objects.create(
            tenant_id=tenant_id,
            tariff_version=new_version,
            season=season_map.get(window.season_id),
            label=window.label,
            day_type=window.day_type,
            start_time=window.start_time,
            end_time=window.end_time,
            unit_price=_changed_price(window.unit_price, cleaned["change"]),
            # BR-RAT-067: a bulk price change moves the MONEY and never the meter. The
            # register the utility stated is copied through untouched — re-deriving it
            # from the new prices is the price-rank inference the PO's ruling ended, and
            # an across-the-board rise can reorder two windows that were close together.
            channel=window.channel,
        )
    for capacity in models.CapacityRate.objects.filter(tenant_id=tenant_id, tariff_version=version):
        models.CapacityRate.objects.create(
            tenant_id=tenant_id,
            tariff_version=new_version,
            unit_label=capacity.unit_label,
            rate_per_unit=_changed_price(capacity.rate_per_unit, cleaned["change"]),
            currency=capacity.currency,
        )
    for demand in models.DemandRateConfig.objects.filter(
        tenant_id=tenant_id, tariff_version=version
    ):
        models.DemandRateConfig.objects.create(
            tenant_id=tenant_id,
            tariff_version=new_version,
            energy_rate_per_kwh=_changed_price(demand.energy_rate_per_kwh, cleaned["change"]),
            demand_rate_per_kw=_changed_price(demand.demand_rate_per_kw, cleaned["change"]),
            peak_window_label=demand.peak_window_label,
            peak_window_start=demand.peak_window_start,
            peak_window_end=demand.peak_window_end,
            ratchet_enabled=demand.ratchet_enabled,
            ratchet_pct=demand.ratchet_pct,
            pf_penalty_enabled=demand.pf_penalty_enabled,
            pf_penalty_rate_per_kw=demand.pf_penalty_rate_per_kw,
        )
    # BR-RAT-091 clause 2 — THE SAME GATE THE SINGLE EDIT PATH RUNS (DEF-499).
    #
    # ⚠ THIS FUNCTION IS THE SIXTH WRITER OF `tariff_versions` AND THE ONLY ONE
    # THAT DOES NOT GO THROUGH `_write_version`. It builds the row and its size
    # rows, seasons, tiers, windows, capacity and demand children itself. So a
    # gate added to "the write path" covered five writers and missed this one —
    # and this is the writer that can do the most damage, because ONE bulk
    # uplift moves every schedule a utility has at once. The check must be
    # called explicitly here; nothing about the shape of this code would have
    # made that obvious to the next lane, which is why it is stated.
    #
    # It RAISES, exactly as `rating.bulk.entity_without_version` above does, and
    # BR-RAT-040 makes the consequence the WHOLE BATCH: `apply_rate_change_batch`
    # wraps every entity in one `transaction.atomic()`, so one schedule over the
    # bar refuses the filing for all of them and nothing is written. That is the
    # rule's own posture (*"bulk = one atomic batch"*) and not a choice made
    # here — measured, not assumed: the job re-raises `BIZ-APPROVAL` and the
    # schedule is still on its single version afterwards.
    _guard_rate_change_second_approval(tariff, version, new_version)
    models.RateChangeLog.objects.create(
        tenant_id=tenant_id,
        batch=batch,
        entity_type="schedule",
        entity_id=tariff.id,
        before={"name": tariff.name, **(before or {})},
        after={"name": tariff.name, **(_json_safe(selectors.version_row(new_version)) or {})},
        reason=cleaned["reason"],
        actor_id=actor_user_id,
    )


def _apply_batch_to_plan(
    batch: models.RateChangeBatch,
    plan: models.RatePlan,
    cleaned: dict[str, Any],
    actor_user_id: Any,
) -> None:
    """Plan base charges move the same way (D9 "schedules and/or plan base
    charges"), with the same version bump the single edit path uses."""
    before = _plan_snapshot(plan.id)
    for row in models.PlanService.objects.filter(rate_plan=plan):
        row.base_charge = _changed_price(row.base_charge, cleaned["change"])
        row.save(update_fields=["base_charge", "updated_at"])
    if plan.status == PLAN_PUBLISHED:
        plan.version += 1
        plan.save(update_fields=["version", "updated_at"])
    models.RateChangeLog.objects.create(
        tenant_id=_tenant_id(),
        batch=batch,
        entity_type="plan",
        entity_id=plan.id,
        before=before,
        after=_plan_snapshot(plan.id),
        reason=cleaned["reason"],
        actor_id=actor_user_id,
    )


# ── unit plan assignment history (BR-CUS-010/011/013 · BR-MET-041) ──────────
#: The guard's own vocabulary. Codes, not sentences: the caller renders, and a
#: test that pins a code does not break when the wording improves.
BACKDATED_BEHIND_ISSUED_BILL = "plan_change_backdated_behind_issued_bill"
BACKDATING_NOT_CHECKED = "plan_backdating_not_checked_against_issued_bills"


def _backdating_warning(unit_id: Any, effective: date) -> dict[str, Any] | None:
    """Does `effective` reach back into days an ISSUED bill already priced?

    PO RULING 2026-08-11, on this worked example, verbatim: *"a unit's plan is
    changed effective 1 June; June's bill went out on the 5th at the old rate;
    the records now disagree with the bill."* Three options were put — (A)
    block any backdating behind the last issued bill, (B) warn and allow with a
    reason recorded, (C) allow silently. **The PO answered B.** So this
    function does not refuse anything. It reports.

    THE SHAPE IS BORROWED, NOT INVENTED. `apps/customers/services.py`'s
    `_check_move_out_against_issued_bills` asks the same question about a
    move-out date: seam → "could not be asked" is a WARNING, never silence →
    otherwise compare against the last issued bill. The one difference is the
    verdict, and it is the PO's: a move-out behind an issued bill is REFUSED
    (US-CUS-005 TC-6), a plan change behind one is ALLOWED with a reason. Same
    question, two rulings; sharing the question is what keeps them comparable.

    THE COMPARISON IS `<=`, and the boundary is not a detail. The last billed
    day was priced by the issued bill, so a plan starting ON it changes what an
    already-billed day should have cost. Move-out uses `<` because a move-out
    date is an END boundary — leaving on the last billed day agrees with the
    bill. A start boundary and an end boundary are not the same test even when
    they read alike.
    """
    probe = seams.last_issued_bill_for_unit(str(unit_id))
    if not probe.get("wired"):
        # Hard-won law 1: a check that could not run is not a check that
        # passed. Say so on the response rather than letting silence claim it.
        return {
            "code": BACKDATING_NOT_CHECKED,
            "br_ref": "BR-BIL-004",
            "assigned_from": effective.isoformat(),
            "detail": (
                "billing publishes no last-issued-bill read, so the PO's 2026-08-11 "
                "backdating check could not be evaluated for this assignment"
            ),
        }
    bill = probe.get("bill")
    if bill is None or effective > bill["period_end"]:
        return None
    return {
        "code": BACKDATED_BEHIND_ISSUED_BILL,
        "br_ref": "BR-BIL-004",
        "assigned_from": effective.isoformat(),
        "billed_through": bill["period_end"].isoformat(),
        "invoice_no": bill["invoice_no"],
        "invoice_id": bill["invoice_id"],
        "account_id": bill["account_id"],
        "reason_required": True,
    }


def record_unit_plan_assignment(
    *,
    unit_id: Any,
    rate_plan_id: Any,
    assigned_from: str,
    source: str,
    actor_user_id: Any = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Append the dated plan-history row for a unit, closing the previous one.

    THE GAP THIS CLOSES (PO "gap 1", 2026-08-11). `unit_plan_assignments` has
    existed since W1 and was NEVER WRITTEN: metering resolved this function
    through its seam, rating had never authored it, and every plan assignment
    returned `history_recorded: false`. Honestly reported, and still a hole —
    the unit knew only its CURRENT plan, so a mid-cycle change could not be
    priced. Billing needs "plan A from the 1st to the 14th, plan B from the
    15th"; an audit row carrying before/after values is not something a bill
    run can calculate from.

    It could not be written earlier for a real reason, not an oversight: this
    table stores a `rate_plan_id`, and `units.default_tariff_id` stored a
    TARIFF. Writing one into the other would have failed on the foreign key.
    The PO settled that contradiction on 2026-08-11 — a unit holds a PLAN —
    and this function became possible in the same change that repointed it.

    NOT AN ENTRY POINT. There is no `@require_role` here: metering's
    `assign_unit_plan` is the gated caller (System Admin or Billing Clerk, plus
    the BR-MET-007 plan lock) and this runs inside its transaction. The
    `actor_user_id` is for ATTRIBUTION, not authorisation. Rating owns this
    table (B2 r16 #6), so the write lands here rather than metering reaching
    across a module boundary.

    `plan_version` is SNAPSHOT at assignment (BR-CUS-013). Editing the plan
    next year bumps its version; this row keeps the one that was assigned, so
    a bill reprinted years later resolves the prices the customer actually had.

    BACKDATING BEHIND AN ISSUED BILL — PO ruling 2026-08-11, option B of three.
    The flag this function used to carry ("REPORTED, NOT RESOLVED") is closed.
    An `assigned_from` on or before the last day an ISSUED bill covered is
    ALLOWED, requires a `reason`, and is recorded. Not blocked: the PO was
    shown "a unit's plan is changed effective 1 June; June's bill went out on
    the 5th at the old rate; the records now disagree with the bill" and chose
    warn-and-allow over block. That makes this the same shape as a late-fee
    waiver — the act is permitted and the justification is EVIDENCE.

    WHERE THE EVIDENCE GOES: BOTH the history row and `audit_log`, and the
    duplication is the point.
      * The ROW (`unit_plan_assignments.reason`, BR-CUS-011 "who/when/from→to/
        reason/source") is where a reader of the plan history finds it. Anyone
        asking "why does this unit's history contradict the June bill?" is
        looking at that table, not at the trail.
      * The AUDIT row is the compliance record, and it names the invoice — the
        row cannot, because it has no column for one. It also survives
        independently: `unit_plan_assignments` is append-only by convention,
        `audit_log` by rule (BR-AUD-002).
    HARD RULE 7 SAYS "every money action writes audit_log", and a plan change
    is NOT itself a money action — it moves no balance. This one is audited
    anyway, and the reading is stated rather than implied: the act deliberately
    contradicts a document already sent to a customer, so it is a decision
    ABOUT money that has already moved. The general plan assignment keeps its
    existing `unit.plan_assigned` row in metering; this adds a second, narrower
    one for the override decision itself, the same posture BR-MET-042 takes for
    the occupied-unit override.

    THE REASON IS REQUIRED ONLY IN THAT CASE. A forward-dated assignment
    demands nothing new — see the comment below about the earlier draft that
    refused ordinary flows and was caught by its own tests within a minute.
    Requiring a reason from every caller would be that same mistake, and would
    break every existing call site.
    """
    tenant_id = _tenant_id()
    effective = date.fromisoformat(str(assigned_from))
    plan = selectors.plan_ref(rate_plan_id)
    if plan is None:
        _refuse(
            [
                _field_error(
                    "rate_plan_id",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "rating.plan.unknown_or_unpublished",
                    rate_plan_id=str(rate_plan_id),
                )
            ]
        )

    open_row = models.UnitPlanAssignment.objects.filter(
        tenant_id=tenant_id, unit_id=unit_id, assigned_to__isnull=True
    ).first()

    if open_row is not None:
        # Re-stating the SAME plan from the SAME date is not a second change.
        # Without this, a double-submitted form leaves two rows describing one
        # event and the history reads as a plan change that never happened.
        # Natural-key idempotency, the same shape the seeder uses.
        #
        # Deliberately AHEAD of the backdating guard: a re-submit changes
        # nothing, so demanding a fresh reason for it would turn a harmless
        # double-click into a refusal — and the reason the original carried is
        # already on the row being returned.
        if str(open_row.rate_plan_id) == plan["id"] and open_row.assigned_from == effective:
            return _assignment_dict(open_row, plan)

    # PO ruling 2026-08-11 (option B): warn and allow, reason required. Asked
    # BEFORE anything is written, so a refusal leaves no half-closed history
    # behind — the same posture update_plan takes for BR-RAT-037's reason.
    warning = _backdating_warning(unit_id, effective)
    reason = (reason or "").strip() or None
    if warning is not None and warning["code"] == BACKDATED_BEHIND_ISSUED_BILL and not reason:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="rating.assignment.reason_required_behind_issued_bill",
            params={
                "br_ref": "BR-BIL-004",
                "billed_through": warning["billed_through"],
                "assigned_from": warning["assigned_from"],
            },
            field_errors=[
                _field_error(
                    "reason",
                    errors.VAL_REQUIRED,
                    "rating.assignment.reason_required_behind_issued_bill",
                    billed_through=warning["billed_through"],
                    assigned_from=warning["assigned_from"],
                )
            ],
        )

    if open_row is not None:
        # A NEW ASSIGNMENT ALWAYS SUPERSEDES THE OPEN ONE. Its last covered day
        # is the day before the incoming one starts, so no day is covered twice
        # and no day is left uncovered.
        #
        # This deliberately does NOT refuse an earlier date, and an earlier
        # draft of this function did. That draft was wrong in a way its own
        # tests caught immediately: it rejected two entirely ordinary flows —
        # correcting a plan on the same day it was set, and replacing a
        # future-dated assignment before it ever took effect. Both are staff
        # fixing a mistake, which is the commonest reason to touch this screen.
        #
        # When the outgoing row never covered a day (superseded on or before
        # its own start date), it is still CLOSED rather than deleted: the
        # table is append-only, and the row is the evidence that the assignment
        # was made and withdrawn, with its actor and reason. Such a row has
        # `assigned_to < assigned_from`, which is how a reader tells "never in
        # force" from "in force and ended" — filter with
        # `assigned_to IS NULL OR assigned_to >= assigned_from`.
        #
        # Backdating behind an ALREADY-BILLED period WAS the flag this comment
        # used to carry ("REPORTED, NOT RESOLVED — billing has no `invoices`
        # table to ask"). Billing has one now, so the question is asked above
        # and the PO's 2026-08-11 ruling answers it: warn, require a reason,
        # allow. Not the refusal move-out carries — same question, different
        # verdict, both from the PO.
        open_row.assigned_to = effective - timedelta(days=1)
        open_row.save(update_fields=["assigned_to"])

    row = models.UnitPlanAssignment.objects.create(
        tenant_id=tenant_id,
        unit_id=unit_id,
        rate_plan_id=plan["id"],
        plan_version=plan["version"],  # SNAPSHOT — BR-CUS-013
        assigned_from=effective,
        source=source,
        actor_id=actor_user_id or None,
        reason=reason,
    )
    if warning is not None and warning["code"] == BACKDATED_BEHIND_ISSUED_BILL:
        # The second half of the ruling: the record has to say who decided and
        # why. `reason` is on the row above; this names the BILL the row now
        # disagrees with, which the row has no column for.
        core_audit.write_row(
            action="unit_plan_assignment.backdated",
            entity_type="unit_plan_assignment",
            entity_id=row.id,
            actor_user_id=actor_user_id or None,
            after=_json_safe(
                {
                    "unit_id": str(unit_id),
                    "rate_plan_id": plan["id"],
                    "plan_version": row.plan_version,
                    "source": source,
                    "reason": reason,
                    **warning,
                }
            ),
        )
    return _assignment_dict(row, plan, warning=warning)


def _assignment_dict(
    row: Any, plan: dict[str, Any], *, warning: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "id": str(row.pk),
        "unit_id": str(row.unit_id),
        "rate_plan_id": str(row.rate_plan_id),
        "plan_name": plan["name"],
        "plan_version": row.plan_version,
        "assigned_from": row.assigned_from.isoformat(),
        "assigned_to": row.assigned_to.isoformat() if row.assigned_to else None,
        "source": row.source,
        "reason": row.reason,
        # PO 2026-08-11 option B: the caller is TOLD, every time. A warning the
        # response does not carry is a warning nobody was given (law 2). None on
        # the idempotent re-submit path, where nothing changed.
        "warning": warning,
    }


def run_rate_change_job(job_id: str) -> dict[str, Any]:
    """The BE-07 harness entry point (worker, management command and tests take
    the SAME path — tenant context is re-entered from the record)."""
    return core_jobs.run_job(job_id, apply_rate_change_batch)


# ══════════════════════════════════════════════════════════════════════════
# US-TEN-019 SAMPLE DATA — the seams `apps/tenancy/seams.py` documents
# ══════════════════════════════════════════════════════════════════════════
# Thin forwarders on purpose. The seam contract names
# `apps.rating.services.seed_sample_records`, G20 harvests that exact path, and
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
    from apps.rating import sample_data

    return sample_data.seed_sample_records(actor)


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-061/066 — remove what is free, report the rest BY NAME."""
    from apps.rating import sample_data

    return sample_data.remove_sample_records()


def sample_record_count() -> int:
    """How many sample rows this module holds right now, read live."""
    from apps.rating import sample_data

    return sample_data.sample_record_count()


def sample_plan_id(code: str) -> str | None:
    """The id of a seeded sample plan, BY CODE — published so metering and
    customers never attach a unit to `the first plan in the list`, which is how
    a lane once put a whole fixture onto a water-only Small Commercial plan."""
    from apps.rating import sample_data

    return sample_data.sample_plan_id(code)


# ── CR-062 ADDENDUM J2 · THE ENROLMENT BLOCK ───────────────────────────────
# A SECOND rating block, and it is second because of WHEN it can run rather
# than what it writes. An enrolment needs an ACCOUNT, and rating's own block has
# to run before customers' — a plan must exist before customers can attach an
# agreement to one. So the Municipal grant is its own block, ordered after the
# Accounts block and before the first bill run, which is the only window in
# which the reduction can appear on the June document a person opens.


def seed_sample_enrolments(actor: Any) -> int:
    """`CR-062` addendum J2 — the Municipal discount, granted to the one seeded
    government building. See `discount_sample_data`."""
    from apps.rating import discount_sample_data

    return discount_sample_data.seed_sample_enrolments(actor)


def remove_sample_enrolments() -> dict[str, Any]:
    """BR-TEN-061/066 — the seeded enrolments, removed. A clerk's own enrolment
    carries no `is_sample` tag and is never touched."""
    from apps.rating import discount_sample_data

    return discount_sample_data.remove_sample_enrolments()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-002@6304a38 (story+rules snapshot hash — EP-RAT-01 lead story; co-packets EP-RAT-02@0b56fac · EP-RAT-03@7d1a8ef · EP-RAT-04@f69a661)
# generated: 2026-08-09 by story-coder v1 (W1 rating feature lane — services/selectors/API); amended 2026-08-09 by story-coder v1 (rating SCHEMA-GAP lane — draft save/activate + eligibility writes) · AMENDED 2026-08-10 by story-coder (DEF-016 — seed_reference_list + reference_seed_omissions, the seam that never existed) · AMENDED 2026-08-10 by story-coder (DEF-026 backend-fix lane — the platform charge seed now copies the fixture's confirmed `charge_type`, and DEPO-R's omission carries its RULING) · AMENDED 2026-08-11 by story-coder (plan-assignment BACKDATING lane — PO ruling 2026-08-11 item 7, option B "warn and allow with a reason recorded"; closes flag (c) of this file's human-review-ledger row) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: a tax's liability account is validated as this tenant's and live, through the ledger (`_validated_liability_account`)) · AMENDED 2026-08-16 by the register lane (BR-RAT-067: `_validate_tou` REQUIRES `channel` per window and refuses two windows on one register; `_write_version` and the rate-change batch copy store and carry it)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ pytest tests/test_us_rat_schedules.py+test_us_rat_plans.py: 65 passed / 2 skipped✔ · full suite -m 'not golden and not isolation': 580 passed / 0 failed / 8 skipped✔ (566 baseline + 14 gap tests) · migrate✔ makemigrations --check clean✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [DEF-016/017 reference-data lane 2026-08-10] ruff✔(--select E4,E7,E9,F on apps/ — the bar the baseline passes; the repo-wide `ruff check .` default-rule run has 194 pre-existing findings under the newer ruff 0.15.8 in this container, none in this lane's files) black✔(--target-version py312 on this lane's files; 8 apps/ files are pre-existing reformat candidates under black 26.3.1, none of them this lane's) · suite `pytest tests -m "not golden and not isolation"` 895 passed / 9 skipped (875 was the baseline in this tree when the lane started) · `-m isolation` 14 passed / 30 skipped (unchanged) · run_gates 13-PASS/0-FAIL/1-SKIP✔ · no migration in this lane (no schema change) · RED-then-GREEN proved for both defects: removing rating's seam turns the DEF-016 guard red naming ['charge_codes','tax_jurisdictions']; removing the six SEED_LIST_OWNERS rows turns the DEF-017 guards red naming all six · [DEF-026 backend-fix lane 2026-08-10] ruff check .✔(All checks passed) black --check on this lane's 6 files✔ (the repo-wide run reports 9 reformat candidates, ALL of them the concurrent metering W2-reads lane's files — none of this lane's) · suite `pytest tests -m "not golden and not isolation"` 975 passed / 10 skipped / 4 FAILED — every failure belongs to the concurrent metering+customers W2 lane (test_be11_openapi snapshot · test_be_list_export routes/cycles · test_us_met_005_006 ×2, where `collected` flipped from None to 0 when that lane wired seams.collected_read_count) and each was PROVED pre-existing by re-running it with every file of THIS lane reverted to HEAD: identical 4 failures. The baseline when this lane started was 923 passed / 9 skipped / 0 failed · `-m isolation` sqlite 14 passed / 39 skipped; live Postgres (config.settings.local + DATABASE_URL) 40 passed / 12 skipped / 1 failed (test_us_cus_003_account_race — customers lane) · run_gates 10-PASS/4-FAIL/1-SKIP: G1, G3, G7 and G8 name ONLY apps/metering/** and apps/customers/** files from the concurrent lane (14-PASS/0-FAIL/1-SKIP at lane start) · `manage.py seed_demo --check` exit 0 under config.settings.local AND under config.settings.production · no migration in this lane (no schema change) · the TAMPER figure and the six `charge_type` values are asserted at the DB in tests/test_reference_data_completeness.py (test_us_ten_002_tc1__tamper_is_the_po_ruling_and_the_seeded_class_is_confirmed) and against the constants in tests/test_seed_demo.py · [BACKDATING lane 2026-08-11] **RED PROVED FIRST, quoted verbatim from the run** — `pytest tests/test_us_met_003_plan_backdating.py` against the pre-ruling code: `5 failed in 14.72s`, being TC-8 `E KeyError: 'warning'` · TC-9 `E Failed: DID NOT RAISE ValidationError` · TC-10 `E KeyError: 'warning'` · TC-11 `E Failed: DID NOT RAISE ValidationError` · TC-12 `E AttributeError: <module 'apps.rating.seams' from '/home/user/SMARTBillHub/06-backend/apps/rating/seams.py'> has no attribute 'last_issued_bill_for_unit'`. After the guard landed: `5 passed in 13.42s` (now 6 with TC-13, the bulk-savepoint case metering red-proved separately: `6 passed in 22.68s`). The AUDIT half was red-proved on its own too: disabling the `core_audit.write_row` call fails TC-8 with `E assert 0 == 1 / + where 0 = len([])`, i.e. no `unit_plan_assignment.backdated` row — so the claim that the decision is audited is asserted, not merely written in a docstring. ruff check apps → `All checks passed!` · black --check --line-length 100 on this lane's 5 files → `5 files would be left unchanged` (the repo-wide `black --check apps tests` was RED on 3 files when this lane started — apps/billing/rating_seam.py · apps/payments/allocation.py · tests/test_us_pay_006_allocation.py, all concurrent lanes' — and is `314 files would be left unchanged` now that they landed) · `pytest tests -m golden` 12 passed / 1 xfailed✔ · suite `pytest tests -m "not golden and not isolation"` **1315 passed / 21 skipped / 0 failed**✔ · run_gates **15 PASS / 0 FAIL / 1 SKIP**✔ (a mid-lane run showed G8 and G16 RED naming apps/payments/allocation.py:936 `cites OQ-109 which is not in the registry` and partition_exceptions.txt `cites OQ-108, which is CLOSED` — neither file is this lane's and both cleared when those lanes landed)
# exceptions: `channel` is REQUIRED on every TOU window at WRITE time, not at activation (BR-RAT-067) — a price with no register is the one combination that bills a plausible wrong number · rate-schedule DRAFTS now HAVE storage (migration 0004 — dateless tariff_versions row + one-draft partial unique); B2 §2's EXCLUDE gist window constraint remains unmaterialized in the DB (migration 0001 never created it; btree_gist absent) so `_guard_window` is still the only overlap guard — REPORTED, not resolved · plan eligibility now lands in rate_plans.eligibility (US-RAT-002 §5) and rides the plan snapshot into the audit; the old audit-only `eligibility_advisory` key is retired · DEFECT FOUND+FIXED in update_plan: `after` was snapshotted BEFORE the scalar save, so scalar-only content edits (description, eligibility…) silently skipped the BR-RAT-037 version bump + rate_change_log row — the save now precedes the snapshot · a draft re-save REPLACES the draft row (append-only binds versions that priced something, never a dateless draft) and posting effective_from to PATCH is refused (`rating.schedules.dates_land_at_activation`) so nothing activates without the completeness gate · bulk replay guard is a LOCAL fingerprint in change_spec because core/idempotency.py is a 🔒 Eng-Lead stub · POST /rate-changes needs the /jobs store the job-table lane owns (BE-07 fails loudly without it — reported) · US-RAT-009 TC-7 expects the per-unit threshold BLOCKED pending OQ-054 while BR-RAT-042 (STATUS AUTHORITY, OQ-054 CLOSED) rules it MARGINAL and buildable — implemented per the BR register, contradiction REPORTED · [DEF-016 lane 2026-08-10] seed_reference_list writes rating's OWN tables from the tenancy fixture: every figure is the fixture's own decimal STRING, percent points become the column's fraction (models.Charge / US-RAT-008 TC-3) and amount_rule follows mechanically from which money keys the fixture states — a charge code the fixture carries with NO amount and NO percent (DEPO-R, TAMPER) is NOT created, because _validate_charge requires an amount_rule and one cannot be chosen without a figure; both are named by reference_seed_omissions rather than guessed · charge_type stays NULL on seeded rows (the fixture states none); seed_demo fills it for the demo tenant from its own cited constants · tax_jurisdictions seeds NAME only — that table has no code and no rate column, and the fixture's rates are S13 `taxes` rows, reported not dropped · the seam's audit row is tenancy's `reference.seeded` (BR-TEN-016) written in the same transaction, the same posture apps/assets uses · [DEF-026 lane 2026-08-10] `charge_type` NO LONGER stays NULL on platform-seeded rows: the fixture states the confirmed S12 class per code (PO 2026-08-10) and seed_reference_list copies it, validated against CHARGE_TYPES — a fixture can never widen rating's own value set. TAMPER now carries a figure for the first time: $250.00, the PO's 2026-08-10 ruling between EP-RAT-03 §4 ($250.00) and the billing workbook ($500.00), made a PLATFORM default; this file states no number of its own — the amount arrives as the fixture's decimal string and `amount_rule` follows mechanically · DEPO-R is still not created, but the reason CHANGED KIND and CHARGE_CODES_NOT_SEEDED now says so: BR-RAT-020/023 put deposits in `plan_deposit_rules` per consumer category and explicitly supersede the prototype's single DEPO-R checkbox, so a platform-wide amount would encode a superseded model — a decision, not a gap, and the two must not read alike · REPORTED, NOT FIXED HERE: BR-TEN-012 keys seeding on the FIXTURE VERSION, so a tenant that already carries a `reference_seed_runs` row for 2026.08 receives neither TAMPER nor the new charge_type values; reaching existing tenants needs a version bump (a PO decision) and, for charge_type on rows that already exist, a fill-the-blanks pass this seam deliberately does not do (BR-TEN-012: a tenant-touched row is never overwritten) · [BACKDATING lane 2026-08-11] the guard WARNS, it does not block — PO ruling 2026-08-11 chose option B over "block any backdating behind the last issued bill", so `record_unit_plan_assignment` refuses ONLY the missing reason, never the date · the reason is recorded TWICE on purpose (the history row, where a reader of the plan history looks; and an `audit_log` row `unit_plan_assignment.backdated`, which can name the invoice the row now disagrees with — the table has no column for one) · hard rule 7 covers "money actions" and a plan change is not one; audited anyway because the act contradicts a document already sent, and the reading is stated rather than implied · REPORTED, NOT FIXED HERE: customers' own move-out guard (`_check_move_out_against_issued_bills`) resolves its billing read from `apps.billing.SERVICES`, so it stays unwired and every move-out still returns `move_out_date_not_checked_against_issued_bills` even though `invoices` now exists — one word in customers/seams.py, another lane's territory · NO BUSINESS RULE ID EXISTS for the ruling yet: the code cites BR-BIL-004 (the rule it protects) and the PO's date; the proposed BR-MET-065 text is in the lane report and is a human's to write · **OWED I18N ROW, named not shipped:** the refusal's `message_key` is `rating.assignment.reason_required_behind_issued_bill` and backend message keys are rendered from `07-frontend/src/i18n/locales/*.json`, which this lane may not touch (three concurrent frontend lanes) — until the row lands in all five catalogues the screen renders the raw key, the exact defect G15 was built for. G15 does NOT catch it (it compares catalogues to each other, never code to catalogue). Exact strings for all five locales are in the lane report. The same gap already exists for customers' `customers.account.move_out_behind_issued_bill` — pre-existing, found while checking this one
# AMENDED 2026-09-27 by lane RAT-BIND (`DEF-RAT-6932`, v2.377.7) — the NAMED base charge code now
#   SURVIVES a version that does not mention it. `_validate_version_fields` writes
#   `base_charge_code_id` into `cleaned` only when the payload carried the key, so *cleared on
#   purpose* (`null`) and *not mentioned* (absent) stop being the same answer; the NEW
#   `_carry_forward_base_charge_code` fills the absent case from the row the new version
#   succeeds, at four call sites, and `_apply_batch_to_schedule` clones the FK like every other
#   version fact. Proved red at tip 82f47577 (4 failed, 2 passed) —
#   tests/test_def_rat_6932_binding_survives_a_new_version.py. BR-RAT-037 untouched: no existing
#   version is rewritten.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
