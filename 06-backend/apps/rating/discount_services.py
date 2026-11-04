# ── Trace ──────────────────────────────────────────────
# Story:    EP-RAT-12 (CR-013 part 3 — DISCOUNTS). No US-ID is cited: the
#           CR-013 epics are not authored yet and G2 refuses an ID that does
#           not resolve.
# Rules:    BR-RAT-068..BR-RAT-079 (the twelve discount rules this CR adds) ·
#           BR-RAT-037 (versioning discipline + reason) · BR-RAT-043
#           (advisory eligibility) · BR-TEN-057/061/063 (sample data) ·
#           BR-AUD-001 (a money action writes audit_log)
# Tests:    06-backend/tests/test_cr013_discounts.py
# Impacts:  apps/rating/discount_pricing.py (the R6 arithmetic it feeds) ·
#           apps/rating/sample_data.py (the five seeded discounts) ·
#           apps/rating/resolution.resolve_discounts (R6 — the integration
#           point; NOT edited by this lane) · apps/tenancy/settings_families
#           (the second-approval threshold Param)
# ───────────────────────────────────────────────────────
"""Writes and reads for the discount object. HUMAN-OWNED 🔒.

HUMAN-REVIEW-PENDING — AI-authored 2026-08-19 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). This file
decides how much subsidy an account is granted and when a discount stops
paying, which is 🔒 rating math and money rounding under CLAUDE.md. Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human
sign-off.

THREE PO RULINGS OF 2026-08-19 ARE IMPLEMENTED HERE, EACH WHERE IT BITES
-------------------------------------------------------------------------
1. **A plan may not override a discount's value** — *"no plan cannot override
   prices."* `attach_discount_to_plan` takes no value and
   `plan_discount_rules` has no column for one, so the forbidden thing is not
   merely refused, it is unstorable.
2. **A submitter MAY approve their own filing** — *"yes allow it"* — and the
   fact is RECORDED (`DiscountVersion.self_approved`, plus an audit row naming
   it), so an auditor sees it rather than inferring it by comparing two ids.
3. **The second-approval threshold is a TENANT SETTING with a default of
   $10,000** — *"okay, but allow user to set it , we can provide default."* It
   measures the discount's OWN BUDGET CAP, and **a discount with no budget cap
   always requires the second approval**, because unbounded is the largest
   commitment there is.

WHAT THIS MODULE DOES NOT DO, NAMED SO IT READS AS A DECISION
---------------------------------------------------------------
* **It does not evaluate eligibility.** `DiscountVersion.eligibility_rule` is
  stored as authored and nothing reads it — the same ADVISORY posture
  BR-RAT-043 gives `rate_plans.eligibility`. Enrolment is a recorded staff act
  with a verification; automatic evaluation of an income test against a
  household-size table is EP-RAT-12's remainder and is named rather than
  half-built, because a half-built income test enrols the wrong households.
* **It does not wire R6 into the bill run.** `apps/rating/resolution.py` and
  `apps/billing/` belong to other lanes working this same CR in this same tree.
  `r6_enrolled_discounts` and `price_account_discounts` are the two doors; see
  INTEGRATION in `discount_pricing`'s docstring for the two-line change.
* **It stores no per-tax discount treatment.** Statutory and per tax (CR-013
  part 4) — `taxes.discount_treatment` is EP-RAT-13's column.
"""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db import IntegrityError as db_IntegrityError
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Now

from apps.rating import discount_lists, discount_pricing
from apps.rating import discounts as discount_models
from apps.rating import models as rating_models
from apps.rating import seams
from apps.rating.services import (
    _actor_user_id,
    _audit,
    _field_error,
    _json_safe,
    _refuse,
    _require_dict,
    _tenant_id,
)
from core import batch_reads
from core import errors
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

ZERO = Decimal("0")

#: The tenant-settings key the PO's 2026-08-19 ruling created. Declared once in
#: `apps.tenancy.settings_families.FINANCE_CONTROLS`; named here so a rename is
#: a two-file grep rather than a silent read of a key nobody sets.
KEY_SECOND_APPROVAL_THRESHOLD = "discount_second_approval_threshold_amount"
SETTINGS_FAMILY_SLUG = "finance-controls"

#: Every field `create_discount` / `update_discount_version` accept. Unknown
#: keys are REFUSED, never ignored — the same posture `_reject_unknown` takes
#: in `services.py`, and here it is what stops a caller sending
#: `plan_value_override` and believing it was stored.
DISCOUNT_FIELDS = (
    "code",
    "name",
    # `CR-166` §9 — the CODE of one of this utility's program owners. The legacy
    # spelling below is still accepted (a code or a label of the same list), so
    # a screen that has not moved yet keeps working; both land in one column.
    "program_owner",
    "programme_owner",
    "funding_source",
    "report_in_assistance_filing",
)
VERSION_FIELDS = (
    "discount_type",
    "value",
    "currency",
    "applies_to",
    "applies_to_service",
    "applies_to_charge_codes",
    # `CR-091-BRC01` — the PLURAL. Named here as well as in the passthrough loop
    # below because `_reject_unknown` reads THIS tuple: `DEF-388` is what it
    # costs when a field is in one and not the other — the gate that requires it
    # refuses `VAL-001` on the very field the caller supplied.
    "applies_to_services",
    "cap_per_bill",
    "cap_per_year",
    "cap_lifetime",
    "bill_floor_amount",
    "stacking_precedence",
    "stacks_with_others",
    "exclusivity_group",
    # `CR-166` §9 — who qualifies, as a CODE of this utility's list. Stored in
    # `eligibility_code`, with the value's label copied into
    # `eligibility_summary` so a version always reads in words.
    "eligibility",
    "eligibility_rule",
    "eligibility_summary",
    "enrolment_mode",
    "verification_method",
    "proof_required",
    "accepted_proof_kinds",
    "proof_before_first_reduction",
    "recertification_months",
    "recertification_notice_days",
    "recertification_grace_days",
    "lapse_behaviour",
    "effective_from",
    "effective_to",
    "budget_cap",
    "budget_period",
    "exhaustion_behaviour",
    "change_reason",
)


class DiscountRuleError(errors.BizError):
    """A refusal that names its rule, per B8. Every one below quotes CR-013."""


# ── tenant setting: the second-approval threshold ───────────────────────────
def second_approval_threshold() -> Decimal | None:
    """The tenant's own *"second approval required above a discount budget of
    $X"* — PO-ruled 2026-08-19, raised to $50,000 on 2026-08-21 (OQ-290), and
    **UNSET BY DEFAULT FROM 2026-09-10**.

    ⚠ **`None` MEANS THE FEATURE IS OFF, AND IT IS THE ORDINARY STATE.** PO
    ruling 2026-09-10, verbatim: *"Keep the plumbing, default it off. The
    threshold setting stays but starts unset, so nothing ever requires a second
    approval unless a utility deliberately turns it on."* A utility that wants
    it types a figure on Settings and the whole mechanism comes back.

    ⚠ **NO DEFAULT IS SUBSTITUTED HERE.** The ratified value lives once, as a
    seeded `Param` in `apps.tenancy.settings_families.FINANCE_CONTROLS`, and is
    merged into every tenant's document by tenancy's own read. A number written
    into this function would be a SECOND copy, free to drift from the one on
    the tenant's own screen — the exact failure `apps.payments.settings_seam`
    documents for the bank-match tolerance.

    ⚠ **AN ABSENT KEY IS STILL A REFUSAL, AND IT IS NOT THE SAME FACT AS AN
    UNSET ONE.** A key missing from the family document means the settings read
    is broken; a key present and null means a utility has chosen not to require
    a second signature. Collapsing the two would turn a broken read into a
    silently disabled money control.
    """
    tenancy_selectors = import_module("apps.tenancy.selectors")
    values = tenancy_selectors.settings_family(SETTINGS_FAMILY_SLUG)
    if KEY_SECOND_APPROVAL_THRESHOLD not in values:
        raise DiscountRuleError(
            errors.BIZ_APPROVAL,
            br_ref="BR-RAT-077",
            message_key="rating.discounts.threshold_unreadable",
        )
    raw = values[KEY_SECOND_APPROVAL_THRESHOLD]
    if raw is None or str(raw).strip() == "":
        return None
    return Decimal(str(raw))


def second_approval_required(budget_cap: Decimal | None) -> tuple[bool, Decimal | None]:
    """(required?, the threshold that decided it).

    ⚠ **WHILE THE THRESHOLD IS UNSET, NOTHING REQUIRES A SECOND APPROVAL — A
    BLANK BUDGET CAP INCLUDED (PO ruling 2026-09-10).** That last clause is not
    a convenience; without it the feature is not actually off. BR-RAT-077's
    *"a discount with no budget cap ALWAYS requires the second approval"* would
    go on firing with no threshold in force, so the one discount a small
    utility is most likely to write — an assistance programme with no cap —
    would demand an approver it has not got. The ruling disables it with the
    rest, and the rule's own reasoning is preserved for the day a utility turns
    the threshold back on: unbounded is the largest commitment a utility can
    make, and the one case where no figure can be compared is the case that
    most needs two people.
    """
    threshold = second_approval_threshold()
    if threshold is None:
        return False, None
    if budget_cap is None:
        return True, threshold
    return Decimal(budget_cap) > threshold, threshold


def _enabled_service_row(
    code: str, index: int | None, fe: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """One service code → its catalog row, or a field error naming its index.

    BR-RAT-024, and the same two refusals `services._enabled_service` makes for
    a tax: unknown to the platform catalog, or known and not enabled for this
    tenant. The INDEX is in the field name (`applies_to_services[2]`) so a
    screen can point at the chip that is wrong rather than at the whole list.

    ⚠ **`index=None` MEANS THE SINGULAR FIELD (`DEF-RAT-5815`).** `one_service`
    has one target and no chips, so there is no index to point at and a field
    error naming `applies_to_services[None]` would land on a control that form
    does not draw — the same fault `GATE 1` records two blocks down. One
    resolver, two field names, because it is one question about one catalogue.
    """
    field = "applies_to_service" if index is None else f"applies_to_services[{index}]"
    row = seams.service_catalog_row(code)
    if row is None:
        fe.append(
            _field_error(
                field,
                errors.VAL_UNKNOWN_LOOKUP,
                "rating.unknown_service",
            )
        )
        return None
    if not seams.service_is_enabled(code):
        fe.append(
            _field_error(
                field,
                errors.VAL_UNKNOWN_LOOKUP,
                "rating.service_not_enabled",
                service=code,
            )
        )
        return None
    return row


# ── cross-module read: does this account exist, on THIS tenant? ─────────────
def _account_or_refuse(account_id: Any) -> Any:
    """The reviewed cross-module READ (B2 §2) behind
    `discount_enrolments.account_id`.

    Rating never writes an `accounts` row; it reads one to refuse an enrolment
    against an account that is not this tenant's. The FK enforces existence,
    but only at COMMIT and without a sentence — and an enrolment quietly bound
    to another utility's customer is a cross-tenant leak wearing a foreign-key
    error, so it is refused here with a message a human can act on.
    """
    account_model = discount_models.DiscountEnrolment._meta.get_field("account").related_model
    account = account_model.objects.filter(tenant_id=_tenant_id(), pk=account_id).first()
    if account is None:
        raise errors.NotFoundError()
    return account


# ── validation ──────────────────────────────────────────────────────────────
def _reject_unknown(payload: dict[str, Any], allowed: tuple[str, ...], fe: list) -> None:
    for field_name in sorted(set(payload) - set(allowed)):
        fe.append(_field_error(field_name, errors.VAL_FORMAT, "rating.unknown_field"))


def _validate_version(
    payload: dict[str, Any], *, partial: bool, keeps_type: str | None = None
) -> dict[str, Any]:
    """The named validation gates CR-013 part 3 asks for, each quoted.

    Part 3's *"validation gates"* clause names two by hand. Both are here, and
    both refuse the COMBINATION rather than resolving it silently — which is
    the whole point of naming them: the product does not decide for the
    operator which half of a contradiction they meant.

    `keeps_type` is the type the version being edited ALREADY holds. It exists
    for one gate (GATE 0 below): sending a draft's own type back with an edit
    is not choosing that type, so it is not refused.
    """
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, VERSION_FIELDS, fe)
    cleaned: dict[str, Any] = {}

    for key, vocabulary, rule in (
        ("discount_type", discount_models.DISCOUNT_TYPES, "BR-RAT-068"),
        ("applies_to", discount_models.DISCOUNT_SCOPES, "BR-RAT-068"),
        ("enrolment_mode", discount_models.ENROLMENT_MODES, "BR-RAT-076"),
        ("verification_method", discount_models.VERIFICATION_METHODS, "BR-RAT-076"),
        ("lapse_behaviour", discount_models.LAPSE_BEHAVIOURS, "BR-RAT-076"),
        ("budget_period", discount_models.BUDGET_PERIODS, "BR-RAT-075"),
        ("exhaustion_behaviour", discount_models.EXHAUSTION_BEHAVIOURS, "BR-RAT-075"),
    ):
        if key in payload:
            value = str(payload[key] or "").strip()
            if value not in vocabulary:
                fe.append(_field_error(key, errors.VAL_UNKNOWN_LOOKUP, f"rating.discounts.{key}"))
            else:
                cleaned[key] = value
        elif not partial and key in ("discount_type",):
            fe.append(_field_error(key, errors.VAL_REQUIRED, "rating.required"))

    # ── GATE 0: A USAGE ALLOWANCE IS NOT OFFERED (PO ruling 2026-10-03) ──────
    #
    # Decision log 2026-10-03, *"A USAGE ALLOWANCE IS NOT OFFERED ON THE NEW
    # DISCOUNT FORM UNTIL 'FREE UNITS BEFORE PRICING' IS BUILT"*, PO verbatim
    # *"recommend (b) - this is correct"*. `BR-RAT-962` keeps the type
    # unpriceable (no step takes free units off the reading before pricing), so
    # a new one could be saved and never go live. Every door that would bring a
    # NEW usage allowance into being refuses here, on the type box: create, a
    # new version, an edit that would TURN a draft into one, a new value and a
    # correction. A draft that already IS one (`keeps_type`) still edits, and
    # reads stay as they were. **Nothing is priced differently.** When the step
    # is built (a money change and a finance re-sign), this gate goes.
    if (
        cleaned.get("discount_type") == discount_models.DISCOUNT_USAGE_ALLOWANCE
        and keeps_type != discount_models.DISCOUNT_USAGE_ALLOWANCE
    ):
        fe.append(
            _field_error(
                "discount_type",
                errors.VAL_RANGE,
                "rating.discounts.usage_allowance_not_offered",
                br_ref="BR-RAT-962",
            )
        )

    if "value" in payload:
        try:
            value = Decimal(str(payload["value"]))
        except (ArithmeticError, TypeError, ValueError):
            fe.append(_field_error("value", errors.VAL_FORMAT, "rating.discounts.value"))
        else:
            if value < ZERO:
                # A discount's value is a MAGNITUDE. A negative one stored here
                # and subtracted by the engine would ADD to the bill.
                fe.append(_field_error("value", errors.VAL_RANGE, "rating.discounts.value_sign"))
            cleaned["value"] = value
    elif not partial:
        fe.append(_field_error("value", errors.VAL_REQUIRED, "rating.required"))

    for money_key in (
        "cap_per_bill",
        "cap_per_year",
        "cap_lifetime",
        "bill_floor_amount",
        "budget_cap",
    ):
        if money_key in payload and payload[money_key] is not None:
            try:
                cleaned[money_key] = Decimal(str(payload[money_key]))
            except (ArithmeticError, TypeError, ValueError):
                fe.append(_field_error(money_key, errors.VAL_FORMAT, "rating.discounts.money"))
        elif money_key in payload:
            cleaned[money_key] = None

    for int_key in (
        "stacking_precedence",
        "recertification_months",
        "recertification_notice_days",
        "recertification_grace_days",
    ):
        if int_key in payload:
            raw = payload[int_key]
            cleaned[int_key] = None if raw is None else int(raw)

    for flag in ("stacks_with_others", "proof_required", "proof_before_first_reduction"):
        if flag in payload:
            cleaned[flag] = bool(payload[flag])

    # ── `CR-166` §9 · THE CURRENCY IS THE UTILITY'S, AND THE SERVER SETS IT ──
    #
    # PO 2026-10-03, verbatim: *"Currency - it is default of utility - user
    # cannot change it"*. This was a PASSTHROUGH and the walk saved CAD on a USD
    # utility (`CR-166` §6 b), which `DiscountCurrencyMismatch` then refused at
    # BILL time — an outage instead of a correction. Now every full write stores
    # the utility's own currency whatever was sent, and a payload naming ANOTHER
    # one is refused by name, so nobody believes a CAD discount was saved.
    utility_currency = seams.tenant_currency() or "USD"
    if "currency" in payload and str(payload.get("currency") or "").strip():
        if str(payload["currency"]).strip().upper() != utility_currency:
            fe.append(
                _field_error(
                    "currency",
                    errors.VAL_RANGE,
                    "rating.discounts.currency_not_utility",
                    currency=utility_currency,
                )
            )
    if not partial or "currency" in payload:
        cleaned["currency"] = utility_currency

    # ── `CR-166` §9 · THE TWO VERSION-BORNE LISTS ARE CODES OF THIS UTILITY'S
    # OWN VALUES (PO 2026-10-03, *"Exclusivity group - can you make this drop
    # down"*, *"Who qualifies * - drop down"*). `none` stores NULL — see
    # `discounts.EXCLUSIVITY_NONE` for why a group named "none" must not exist.
    if "exclusivity_group" in payload:
        group = discount_lists.clean_code(
            discount_models.LIST_EXCLUSIVITY_GROUP,
            "exclusivity_group",
            payload["exclusivity_group"],
            fe,
        )
        if group is not ...:
            cleaned["exclusivity_group"] = group

    for passthrough in (
        "eligibility_rule",
        "eligibility_summary",
        "accepted_proof_kinds",
        # ⚠ **DEF-388 — THIS NAME WAS MISSING AND THE SCOPE IT GATES WAS
        # UNREACHABLE.** `applies_to_charge_codes` was listed in
        # `VERSION_FIELDS`, so `_reject_unknown` ACCEPTED it, and then no loop
        # copied it into `cleaned`. GATE 3 below reads
        # `cleaned.get("applies_to_charge_codes")`, found nothing, and refused
        # `VAL-001` **on the very field the caller had supplied** — so
        # `named_codes`, one of the five scopes CR-013 part 3 names by hand,
        # could not be created at all and a utility could not express *"waive
        # the connection fee"*. For every OTHER scope the list was accepted and
        # discarded in silence, which is the worse half: a caller that set it
        # believed it stored.
        #
        # `discount_pricing._scoped_base` has read the field for
        # `SCOPE_NAMED_CODES` since it was written, so the pricing half was
        # built and waiting for data nothing could write.
        #
        # It is a PASSTHROUGH and not a typed loop deliberately: the value is a
        # JSON list of charge-code strings, the same shape
        # `accepted_proof_kinds` above already passes through untouched.
        "applies_to_charge_codes",
        "effective_from",
        "effective_to",
        "change_reason",
    ):
        if passthrough in payload:
            cleaned[passthrough] = payload[passthrough]

    # `CR-166` §9 — AFTER the passthrough loop on purpose: when a CODE is sent,
    # its label is what `eligibility_summary` says, whatever free text rode
    # along (a correction re-sends the old summary beside a new code).
    if "eligibility" in payload:
        eligibility = discount_lists.clean_code(
            discount_models.LIST_ELIGIBILITY, "eligibility", payload["eligibility"], fe
        )
        if eligibility is not ...:
            cleaned["eligibility_code"] = eligibility
            row = discount_lists.value_row(discount_models.LIST_ELIGIBILITY, eligibility)
            if row is not None:
                cleaned["eligibility_summary"] = row.label

    # ── `DEF-RAT-5815` · THE SINGULAR TAKES A SERVICE **CODE**, LIKE EVERY
    # OTHER SURFACE THAT NAMES A SERVICE ──────────────────────────────────────
    #
    # ⚠ **THIS WAS `cleaned["applies_to_service_id"] = payload[...]`, A
    # PASSTHROUGH OF WHATEVER ARRIVED INTO A UUID FOREIGN KEY, AND THE SCOPE
    # HAS THEREFORE NEVER BEEN SAVEABLE FROM THE WIZARD.** DIS-02 step 2's
    # service picker is built from `props.services.map((row) => ({ value:
    # row.service }))` — `row.service` is the catalogue CODE — so choosing
    # *One service* posted `"electric"` into `applies_to_service_id` and
    # Django answered `ValidationError: ['"electric" is not a valid UUID.']`,
    # which reaches the clerk as *"Something went wrong on our side."*
    #
    # ⚠ **THE CODE IS WHAT THE WHOLE PRODUCT ALREADY SPEAKS, AND THAT IS WHAT
    # SETTLES WHICH TYPE THIS FIELD IS** — it was never a genuine fork:
    #   * the PLURAL sibling `applies_to_services` validates CODES, three
    #     blocks down, against the same catalogue;
    #   * every READ path serves a code — `selectors.discount_terms`,
    #     `selectors.discount_detail` and `discount_rules_for_account` all
    #     write `version.applies_to_service.code`;
    #   * `discount_pricing.DiscountRule.applies_to_service` is typed
    #     `str | None` and is compared against `line.service`, a code;
    #   * and the wizard's EDIT door reads that same code back into the
    #     picker (`DiscountWizard.tsx`, `row.applies_to_service ?? ""`).
    # The UUID existed in exactly one place — this line — because the storage
    # happens to be an FK. `DEF-RAT-5815`'s own words: *"one idea, two types,
    # and the screen sends the same string to both."*
    #
    # ⚠ **IT IS VALIDATED, NOT MERELY RESOLVED.** Same two refusals the plural
    # makes and the tax makes (`BR-RAT-024`): unknown to the platform
    # catalogue, or known and not enabled for this tenant. A discount naming a
    # service the utility does not sell reduces nothing and says nothing about
    # why, and the decision log's sentence applies — *"a refusal a clerk meets
    # while configuring is a correction; the same refusal met during a bill
    # run is an outage."*
    #
    # ⚠ **`None` STILL CLEARS IT**, so a version moved off `one_service` drops
    # its target rather than keeping a stale one GATE 3 would no longer look at.
    if "applies_to_service" in payload:
        raw_service = payload["applies_to_service"]
        if raw_service in (None, ""):
            cleaned["applies_to_service_id"] = None
        else:
            row = _enabled_service_row(str(raw_service), None, fe)
            cleaned["applies_to_service_id"] = None if row is None else row["id"]

    # ── `CR-091-BRC01` · THE PLURAL LIST, VALIDATED THE WAY A TAX'S IS ───────
    #
    # ⚠ **THE TAX'S OWN LOOP, COPIED RATHER THAN RE-INVENTED** (`services.
    # _clean_tax`, the `applies_to_services` branch). Same field name, same
    # shape, same per-index refusal, same `_enabled_service` check — BR-RAT-024:
    # the service must be in the platform catalog AND enabled for this tenant.
    # A disabled service is refused rather than silently accepted, because a
    # discount naming a service the utility does not sell reduces nothing and
    # says nothing about why.
    #
    # ⚠ **IT IS NOT A PASSTHROUGH, AND `applies_to_charge_codes` NEXT DOOR IS.**
    # That is deliberate: a charge code is validated at PRICING time against the
    # tenant's own `charges`, while a service code has a catalog and an enabled
    # flag that can be checked at SAVE — and the decision log's own sentence
    # applies, *"a refusal a clerk meets while configuring is a correction; the
    # same refusal met during a bill run is an outage."*
    if "applies_to_services" in payload:
        raw_services = payload.get("applies_to_services") or []
        if not isinstance(raw_services, list):
            fe.append(
                _field_error(
                    "applies_to_services",
                    errors.VAL_FORMAT,
                    "rating.discounts.services_not_list",
                )
            )
            raw_services = []
        codes: list[str] = []
        for index, code in enumerate(raw_services):
            row = _enabled_service_row(str(code), index, fe)
            if row is not None and row["code"] not in codes:
                codes.append(row["code"])
        cleaned["applies_to_services"] = codes

    # ── GATE 1 (part 3, verbatim): "automatic enrolment with mandatory proof
    # (contradictory)". The product REFUSES the combination rather than
    # resolving it — an automatic programme that also demands a document either
    # enrols nobody or demands nothing, and which of those it does would be
    # decided by whichever code path ran first.
    #
    # ⚠ **IT NAMES BOTH FIELDS FROM CR-087 C1, AND THE REASON IS A SCREEN THAT
    # NO LONGER DRAWS THE CONTROL THIS USED TO POINT AT.** The refusal named
    # `proof_required` alone, which was right while DIS-02 step 3 carried a
    # tick-box for it — the message landed on the box the clerk had just
    # ticked. CR-087 C1 (PO 2026-09-08, *"these should be drop down"*) replaces
    # the enrolment pair with ONE dropdown of the three combinations that mean
    # something, so there is no tick-box left to highlight, and a field error
    # naming a control the form does not draw is a refusal nobody can act on.
    # **Both halves make the contradiction**, so both are named and a screen
    # highlights whichever control it actually has.
    #
    # ⚠ AND THE SCREEN LOSING THE ABILITY TO EXPRESS THIS IS NOT WHAT REFUSES
    # IT — PRB-14, and `DEF-384`'s lesson on a different endpoint: a client that
    # cannot express a state is not a server that refuses it. Every caller
    # arrives here, so the gate stays whatever any one form can draw.
    mode = cleaned.get("enrolment_mode")
    proof = cleaned.get("proof_required")
    if mode == discount_models.ENROLMENT_AUTOMATIC and proof:
        for field in ("enrolment_mode", "proof_required"):
            fe.append(
                _field_error(
                    field,
                    errors.VAL_FORMAT,
                    "rating.discounts.automatic_with_mandatory_proof",
                    br_ref="BR-RAT-076",
                )
            )

    # ── GATE 1b · RULING 3 (PO 2026-10-03): *"A 'customer shows proof' condition
    # cannot be Automatic."* `BR-RAT-076`'s refused combination in the new
    # vocabulary: an Automatic discount is enrolled by a job that can only run
    # one of the four system checks, so a proof condition would enrol nobody and
    # say nothing. Checked here on what THIS payload states; the partial doors
    # re-check on the merged row (`_refuse_automatic_with_proof`).
    _refuse_automatic_with_proof(
        cleaned.get("enrolment_mode"), cleaned.get("eligibility_code"), fe
    )

    # ── GATE 2: a programme that demands proof must say WHICH documents it
    # accepts, or a clerk is refusing enrolments against a list nobody wrote.
    #
    # ⚠ **THIS GATE WAS CORRECT AND UNREADABLE — `DEF-RAT-5816`.** Its
    # `message_key` existed in NONE of the eleven catalogues, so a clerk who
    # chose *Apply and approve, with proof* and ticked nothing was shown the
    # literal string `rating.discounts.proof_kinds_required` (B14 rule 32 — no
    # internal code in clerk-facing copy), at the COMMIT, after walking two
    # more steps past the screen where that choice is made. The sentence is
    # written now and DIS-02 step 3 objects at the control, using THIS key so
    # the two wordings cannot drift apart.
    # ⚖️ `CR-166` §9 (our judgment, decision log 2026-10-03): the approved
    # drawing has NO *documents accepted* box, so a payload that says who
    # qualifies and demands proof gets the documents DERIVED from who
    # qualifies (`discount_lists.proof_kinds_for`) instead of being refused for
    # a field the screen cannot show. A caller that names the kinds still wins.
    if proof and not cleaned.get("accepted_proof_kinds") and cleaned.get("eligibility_code"):
        cleaned["accepted_proof_kinds"] = discount_lists.proof_kinds_for(
            cleaned["eligibility_code"]
        )
    if proof and not cleaned.get("accepted_proof_kinds") and not partial:
        fe.append(
            _field_error(
                "accepted_proof_kinds",
                errors.VAL_REQUIRED,
                "rating.discounts.proof_kinds_required",
                br_ref="BR-RAT-076",
            )
        )

    # ── GATE 3: a scope that names a target must have one.
    scope = cleaned.get("applies_to")
    if scope == discount_models.SCOPE_ONE_SERVICE and not cleaned.get("applies_to_service_id"):
        fe.append(_field_error("applies_to_service", errors.VAL_REQUIRED, "rating.required"))
    if scope == discount_models.SCOPE_NAMED_CODES and not cleaned.get("applies_to_charge_codes"):
        fe.append(_field_error("applies_to_charge_codes", errors.VAL_REQUIRED, "rating.required"))
    # ⚠ **`CR-091-BRC01` — AN EMPTY SPECIFIC LIST IS AN UNFINISHED FORM, NOT A
    # SYNONYM FOR *EVERY SERVICE*.** PO ruling 2026-09-10: *"With `All services`
    # on screen as its own choice, an empty list stops being an expression of
    # intent and becomes an unfinished form: a clerk who meant every service
    # says so."*
    #
    # ⚠ **DO NOT COPY THE TAX'S `NULL or [] = everywhere` READING HERE.** The
    # tax has no such pair on screen, so its empty list carries a meaning it
    # cannot carry once the pair exists — and a screen that kept the old reading
    # would apply a discount to EVERY service on a form the clerk had not
    # finished. The general lesson the PO drew from it: an absence only carries
    # meaning while there is no way to state the thing explicitly.
    if scope == discount_models.SCOPE_SPECIFIC_SERVICES and not cleaned.get(
        "applies_to_services"
    ):
        fe.append(
            _field_error(
                "applies_to_services",
                errors.VAL_REQUIRED,
                "rating.discounts.specific_services_required",
                br_ref="BR-RAT-963",
            )
        )

    # ── GATE 3b: A USAGE ALLOWANCE IS A ONE-SERVICE DISCOUNT — BR-RAT-960,
    # PO ruling 2026-08-31 (`OQ-291` CLOSED), verbatim: *"a) Take the unit from
    # the service it's attached to"*.
    #
    # ⚠ THE RULING DECIDES THIS BY IMPLICATION AND THE IMPLICATION IS THE WHOLE
    # GATE. An allowance is a QUANTITY — `2` — and the ruling says its unit comes
    # from the service it is attached to. A discount attached to the WHOLE BILL
    # names no service, so there is nothing to take a unit from and `2` means
    # nothing. The same is true of `usage_only`, `base_only` and `named_codes`:
    # not one of the four names a single service. The ruling names `whole_bill`
    # because that is the case it was shown; the reason is identical for all four
    # and is written down here rather than re-asked (CLAUDE.md law 13).
    #
    # ⚠ AND IT IS HERE, AT SET-UP, ON PURPOSE — the decision log's own sentence:
    # *"a refusal a clerk meets while configuring is a correction; the same
    # refusal met during a bill run is an outage."* This runs on `create_discount`
    # and on every `create_discount_version`, which is every door a scope can be
    # typed through, and it lands as a FIELD error on `applies_to` so the wizard
    # renders it against the control the clerk just changed rather than as a
    # banner they have to interpret.
    #
    # ⚠ NOT AT ACTIVATION, and that is not an oversight. `activate_discount_
    # version` is the LAST gate before a discount goes live, so a refusal there
    # is met by whoever is releasing rather than whoever is configuring — the
    # very split this ruling asks us to get right.
    #
    # ⚠ AND THE EFFECTIVE SCOPE IS RESOLVED AGAINST THE MODEL DEFAULT, WHICH IS
    # THE DIFFERENCE BETWEEN A GATE AND A GATE-SHAPED COMMENT. `DiscountVersion.
    # applies_to` defaults to `SCOPE_WHOLE_BILL`, so a payload that simply OMITS
    # the scope — the ordinary shape of a wizard save where the clerk never
    # touched the control — stores `whole_bill`, which is the exact state this
    # rule forbids. A gate reading only `cleaned["applies_to"]` would pass that
    # payload and refuse only the one a clerk had explicitly set, i.e. it would
    # be green on the most likely way to break the rule.
    effective_scope = scope
    if effective_scope is None and not partial:
        # The column's own default, named once here rather than re-derived.
        effective_scope = discount_models.SCOPE_WHOLE_BILL
    if (
        cleaned.get("discount_type") == discount_models.DISCOUNT_USAGE_ALLOWANCE
        and effective_scope is not None
        and effective_scope != discount_models.SCOPE_ONE_SERVICE
    ):
        fe.append(
            _field_error(
                "applies_to",
                errors.VAL_RANGE,
                "rating.discounts.allowance_needs_one_service",
                br_ref="BR-RAT-960",
            )
        )

    # ── GATE 4: a percentage over 100 is not a discount, it is a payment TO the
    # customer, and no floor can rescue a bill priced backwards.
    if cleaned.get("discount_type") == discount_models.DISCOUNT_PERCENTAGE:
        value = cleaned.get("value")
        if value is not None and value > Decimal("100"):
            fe.append(_field_error("value", errors.VAL_RANGE, "rating.discounts.percent_over_100"))

    # ── GATE 5: THE WINDOW CANNOT END BEFORE IT STARTS (`DEF-RAT-8050`) ──────
    #
    # ⚠ **THERE WAS NO DATE VALIDATION ON THIS OBJECT AT ALL.** `effective_from`
    # and `effective_to` are PASSTHROUGH fields here — whatever arrives is
    # stored — so `2026-12-01 → 2026-01-31` saved cleanly, and
    # `rating/0049`'s `daterange(effective_from, effective_to + 1)` then
    # refuses it at the DATABASE with PostgreSQL's own `range lower bound must
    # be less than or equal to range upper bound`, which reaches a clerk as
    # *"Something went wrong on our side."* Rate schedules have refused this
    # since `rating.schedules.window_inverted`; this is that gate, one object
    # over, and it exists so the constraint never has to speak to a human.
    lo, hi = cleaned.get("effective_from"), cleaned.get("effective_to")
    lo_d, hi_d = _as_date(lo), _as_date(hi)
    if lo_d is not None and hi_d is not None and hi_d < lo_d:
        fe.append(
            _field_error("effective_to", errors.VAL_RANGE, "rating.discounts.window_inverted")
        )

    _refuse(fe)
    return cleaned


def _refuse_automatic_with_proof(mode: Any, eligibility_code: Any, fe: list) -> None:
    """Ruling 3 — Automatic + a *customer shows proof* value is refused on both
    fields, so a screen highlights whichever control it draws (GATE 1's
    reasoning). A code with no row reads as proof: the product cannot check a
    condition it does not know."""
    if mode != discount_models.ENROLMENT_AUTOMATIC or not eligibility_code:
        return
    if discount_lists.check_key_for(eligibility_code) is not None:
        return
    for field in ("enrolment_mode", "eligibility"):
        fe.append(
            _field_error(
                field,
                errors.VAL_FORMAT,
                "rating.discounts.automatic_needs_system_check",
                br_ref="BR-RAT-076",
            )
        )


def _as_date(value: Any) -> date | None:
    """A payload date as a `date`, or None when it is absent or unparseable.

    ⚠ **UNPARSEABLE READS AS None ON PURPOSE, AND THAT IS NOT SWALLOWING AN
    ERROR.** This helper exists for ONE comparison (gate 5). Django's
    `DateField` is what validates the format, at save, with its own field
    error; a second format check here would report the same fault twice in
    different words. What must not happen is gate 5 raising on a malformed
    string and turning a field error into a 500.
    """
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


# ── the object ──────────────────────────────────────────────────────────────
@require_role(SYSTEM_ADMIN)
def create_discount(actor: Any, payload: Any) -> dict[str, Any]:
    """DIS-02 step 1 + step 2 — the identity and its FIRST DRAFT version.

    One call, because a discount with no version is an object with no value and
    part 3's landing has a `Value` column that would have nothing to render. It
    lands as a **draft** (`Discount.status = draft`, `DiscountVersion.status =
    draft`); nothing bills from a draft, which is already law.
    """
    payload = _require_dict(payload)
    head = {key: payload[key] for key in DISCOUNT_FIELDS if key in payload}
    body = {key: payload[key] for key in payload if key not in DISCOUNT_FIELDS}
    fe: list[dict[str, Any]] = []
    code = str(head.get("code") or "").strip()
    if not code:
        fe.append(_field_error("code", errors.VAL_REQUIRED, "rating.required"))
    name = str(head.get("name") or "").strip()
    if not name:
        fe.append(_field_error("name", errors.VAL_REQUIRED, "rating.required"))
    if (
        code
        and discount_models.Discount.objects.filter(
            tenant_id=_tenant_id(), code__iexact=code
        ).exists()
    ):
        fe.append(_field_error("code", errors.VAL_FORMAT, "rating.discounts.duplicate_code"))
    owner = _clean_program_owner(head, fe)
    _refuse(fe)
    cleaned = _validate_version(body, partial=False)

    with transaction.atomic():
        discount = discount_models.Discount.objects.create(
            tenant_id=_tenant_id(),
            code=code,
            name=name,
            programme_owner=None if owner is ... else owner,
            funding_source=head.get("funding_source"),
            report_in_assistance_filing=bool(head.get("report_in_assistance_filing", False)),
            status=discount_models.DISCOUNT_DRAFT,
        )
        discount_models.DiscountVersion.objects.create(
            tenant_id=_tenant_id(), discount=discount, version_no=1, **cleaned
        )
        row = discount_row(discount)
        _audit(actor, "discount.created", "discount", discount.id, after=_json_safe(row))
    return row


def _duplicate_source_version(discount: Any) -> Any:
    """The version a Duplicate copies: the one IN FORCE today; failing that
    (a draft, one waiting approval, one not started, one ended or retired) the
    newest version that was not set aside — never a `superseded` or `rejected`
    row, which nobody priced from."""
    in_force = active_version(discount)
    if in_force is not None:
        return in_force
    return (
        discount_models.DiscountVersion.objects.filter(tenant_id=_tenant_id(), discount=discount)
        .exclude(
            status__in=(discount_models.VERSION_SUPERSEDED, discount_models.VERSION_REJECTED)
        )
        .order_by("-version_no")
        .first()
    )


@require_role(SYSTEM_ADMIN)
def duplicate_discount(actor: Any, discount_id: Any, payload: Any) -> dict[str, Any]:
    """`DEF-RAT-9310` — More ▾ *Duplicate* (image 23): `POST
    /discounts/{id}/duplicate {code, name}` makes a NEW DRAFT discount.

    WHAT IS COPIED: every value, condition, limit and list of the version in
    force (`_duplicate_source_version`) — type, value, what it applies to (and
    its service, services or charge codes), caps, floor, stacking, exclusivity
    group, who qualifies, enrollment, verification, proof, recertification,
    lapse, budget — and the discount's own program owner, funding source,
    assistance-report flag and GL account. It goes through `create_discount`,
    so every refusal a New discount meets is met here too (a code already used,
    a usage allowance — ruling (b) of 2026-10-03).

    WHAT IS NOT: a new CODE and NAME are REQUIRED (the clerk types both); the
    start and end dates are left EMPTY, because a copy dated in the past would
    go live backwards the day it is approved (ruling 1); and NO enrolment, grant,
    plan binding or version history is copied — a duplicate is offered by no
    plan and received by nobody until somebody puts it there.

    **Worked:** *Senior discount* (SENIOR, 15% off the subtotal before taxes, age
    65 or over, apply and approve, recertify every 12 months, notice 30 · grace
    15, budget $2,383.00 a year; v2 12% scheduled from 01/01/2027, 12 accounts
    receiving it, on *Residential Standard*) duplicated as SENIOR-RURAL *Rural
    senior discount* → a draft v1 at **15%** with the same conditions, no dates,
    on no plan, 0 accounts; its Audit reads *Created* and *Duplicated · SENIOR*.
    """
    payload = _require_dict(payload)
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, ("code", "name"), fe)
    _refuse(fe)
    source = _discount_or_404(discount_id)
    version = _duplicate_source_version(source)
    if version is None:
        raise DiscountRuleError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-RAT-069",
            message_key="rating.discounts.no_active_version",
        )
    body = _version_payload_of(version)
    body["effective_from"] = None
    body["effective_to"] = None
    create_payload: dict[str, Any] = {
        **{key: value for key, value in body.items() if value is not None},
        "code": payload.get("code"),
        "name": payload.get("name"),
        "funding_source": source.funding_source,
        "report_in_assistance_filing": source.report_in_assistance_filing,
    }
    if source.programme_owner:
        create_payload["program_owner"] = source.programme_owner
    with transaction.atomic():
        row = create_discount(actor, create_payload)
        if source.gl_account_id is not None:
            discount_models.Discount.objects.filter(tenant_id=_tenant_id(), pk=row["id"]).update(
                gl_account_id=source.gl_account_id
            )
            row = discount_row(discount_models.Discount.objects.get(pk=row["id"]))
        _audit(
            actor,
            "discount.duplicated",
            "discount",
            row["id"],
            after={"from_code": source.code, "from_version": version.version_no},
        )
    return row


def _clean_program_owner(head: dict[str, Any], fe: list) -> Any:
    """`program_owner` (or the legacy `programme_owner`) → the stored CODE.

    `...` when nothing was sent, None when it was cleared, a field error naming
    the field the caller used when the value is not one of this utility's."""
    for field in ("program_owner", "programme_owner"):
        if field in head:
            return discount_lists.clean_code(
                discount_models.LIST_PROGRAM_OWNER, field, head[field], fe
            )
    return ...


@require_role(SYSTEM_ADMIN)
def create_discount_version(actor: Any, discount_id: Any, payload: Any) -> dict[str, Any]:
    """Editing an active discount NEVER overwrites it — it drafts a new dated
    version (CR-013's shared rule, BR-RAT-037's discipline).

    A `change_reason` is REQUIRED on every version after the first: r10's own
    version table renders it (*"Raised from −10% to −15%"*), and a version
    history where every row says nothing is a history nobody can use.
    """
    payload = _require_dict(payload)
    cleaned = _validate_version(payload, partial=False)
    with transaction.atomic():
        discount = _discount_or_404(discount_id)
        if not cleaned.get("change_reason"):
            _refuse(
                [
                    _field_error(
                        "change_reason", errors.VAL_REQUIRED, "rating.discounts.reason_required"
                    )
                ]
            )
        # ── `DEF-RAT-5817` · ONE DRAFT AT A TIME, SAID IN WORDS ─────────────
        #
        # ⚠ **THIS WAS A RAW `IntegrityError`, SO A DISCOUNT COULD BE EDITED
        # EXACTLY ONCE.** `uq_discount_versions_one_draft` is a PARTIAL unique
        # index on `(discount_id) WHERE status='draft'`, and nothing here had a
        # handler for it: the first *Save new version* returned 201, the second
        # hit the index and the clerk read *"Something went wrong on our side.
        # Nothing was saved."* The edit door on that discount was then a dead
        # end for ever — no explanation and no way back.
        #
        # ⚠ **THE INDEX IS RIGHT AND IS NOT TOUCHED** (`BR-RAT-031`'s shape,
        # taken from `tariff_versions`). *Resume the half-built one* has to be
        # unambiguous, and two drafts of one discount make it a guess.
        #
        # ⚠ **THE REFUSAL AND THE WAY OUT ARE ONE FIX, NOT TWO, WHICH IS
        # `DEF-RAT-6447`'S LESSON ON THE TARIFF'S IDENTICAL INDEX.** A better
        # sentence alone would name a state the clerk cannot reach: before
        # this commit the draft was invisible — the Audit tab said no endpoint
        # served the versions and the header still read `V1` — and nothing
        # anywhere discarded one. So `GET /discounts/{id}/versions` now serves
        # the chain including the draft, and `…/versions/{id}/discard` throws
        # it away. The sentence points at controls that exist.
        #
        # ⚠ **IT DOES NOT REPLACE THE DRAFT THE WAY `_save_schedule_draft`
        # DOES, AND THE DIFFERENCE IS THE NUMBERING.** A rate schedule's draft
        # is the one DATELESS row and carries no version number, so overwriting
        # it loses nothing a person can cite. A discount version is NUMBERED
        # and append-only (`BR-RAT-037`); silently overwriting `V2` would
        # destroy a half-finished filing somebody may be part-way through and
        # leave the history with a gap nobody could explain.
        existing_draft = (
            discount_models.DiscountVersion.objects.filter(
                discount=discount, status=discount_models.VERSION_DRAFT
            )
            .order_by("version_no")
            .first()
        )
        if existing_draft is not None:
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-031",
                message_key="rating.discounts.draft_already_open",
                params={"version_no": existing_draft.version_no},
            )
        highest = (
            discount_models.DiscountVersion.objects.filter(discount=discount)
            .order_by("-version_no")
            .values_list("version_no", flat=True)
            .first()
            or 0
        )
        # ⚠ **THE SAVEPOINT IS THE ONLY OPTION, NOT THE TIDY ONE** (CLAUDE.md
        # hard-won law 14). The check above answers the reported case and every
        # single-clerk case; this closes the RACE, where two requests both read
        # no draft and both insert. On PostgreSQL the failed INSERT aborts the
        # whole transaction, so without a nested `atomic()` — a SAVEPOINT — the
        # refusal below could not be raised cleanly and the audit write after
        # it would die on `InFailedSqlTransaction`. **The default suite cannot
        # see any of that**: `config/settings/test.py` hardcodes in-memory
        # SQLite, which has no aborted-transaction state, so the version
        # without the savepoint passes green everywhere and fails the first
        # time two clerks click at once. Proved on real PostgreSQL in
        # `tests/test_def_rat_5817_one_draft_pg.py`.
        try:
            with transaction.atomic():
                version = discount_models.DiscountVersion.objects.create(
                    tenant_id=_tenant_id(), discount=discount, version_no=highest + 1, **cleaned
                )
        except db_IntegrityError as exc:
            if "uq_discount_versions_one_draft" not in str(exc):
                raise
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-031",
                message_key="rating.discounts.draft_already_open",
                params={"version_no": highest},
            ) from exc
        after = _json_safe(version_row(version))
        _audit(actor, "discount.version_drafted", "discount_version", version.id, after=after)
    return version_row(version)


#: The floor a correction reason has to clear, taken from `services.py` rather
#: than re-declared: `correct_tax` uses `MIN_CORRECTION_REASON` and two
#: different minimum reason lengths in one module is exactly the drift
#: `BR-RAT-1016` exists to stop.
MIN_CORRECTION_REASON = 10


@require_role(SYSTEM_ADMIN)
def update_discount(actor: Any, discount_id: Any, payload: Any) -> dict[str, Any]:
    """The discount's IDENTITY, editable at any time (`BR-RAT-1016`, verb 1).

    Code, name, programme owner, funding source and whether it is reported in
    the assistance filing. **None of this is priced content** — it is what the
    programme is CALLED and who runs it — so it carries no version, no reason
    and no approval, exactly as `update_tax` leaves a tax's filing detail
    editable on a live tax. That boundary is the tax lane's recorded judgment
    (decision log 2026-08-21) applied to a second object: *"a bookkeeper's email
    address is not rate history"*.

    ⚠ **THERE WAS NO EDIT PATH OF ANY KIND ON THIS OBJECT (`DEF-RAT-5709`).**
    `discount_services` had create, submit, approve, activate, retire and
    suspend and no update, so fixing a misspelt programme NAME — the likeliest
    typo of all — had no route at all.
    """
    payload = _require_dict(payload)
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, DISCOUNT_FIELDS, fe)
    _refuse(fe)
    with transaction.atomic():
        discount = _discount_or_404(discount_id)
        # The snapshot is taken BEFORE any field is assigned. It used to sit
        # after the code and name were set on the object, so a rename was
        # missing from its own audit row and a rename alone wrote none
        # (`DEF-RAT-9338`, CR-166 web walk step 7).
        before = _json_safe(discount_row(discount))
        if "code" in payload:
            code = str(payload.get("code") or "").strip()
            if not code:
                fe.append(_field_error("code", errors.VAL_REQUIRED, "rating.required"))
            elif (
                discount_models.Discount.objects.filter(tenant_id=_tenant_id(), code__iexact=code)
                .exclude(pk=discount.pk)
                .exists()
            ):
                fe.append(
                    _field_error("code", errors.VAL_FORMAT, "rating.discounts.duplicate_code")
                )
            else:
                discount.code = code
        if "name" in payload:
            name = str(payload.get("name") or "").strip()
            if not name:
                fe.append(_field_error("name", errors.VAL_REQUIRED, "rating.required"))
            else:
                discount.name = name
        owner = _clean_program_owner(payload, fe)
        _refuse(fe)
        if owner is not ...:
            discount.programme_owner = owner
        if "funding_source" in payload:
            discount.funding_source = payload["funding_source"]
        if "report_in_assistance_filing" in payload:
            discount.report_in_assistance_filing = bool(payload["report_in_assistance_filing"])
        discount.save(
            update_fields=[
                "code",
                "name",
                "programme_owner",
                "funding_source",
                "report_in_assistance_filing",
                "updated_at",
            ]
        )
        after = _json_safe(discount_row(discount))
        if before != after:
            _audit(actor, "discount.updated", "discount", discount.id, before=before, after=after)
    return discount_row(discount)


@require_role(SYSTEM_ADMIN)
def update_discount_version(actor: Any, version_id: Any, payload: Any) -> dict[str, Any]:
    """VERB 1 — a DRAFT version that has never been submitted edits in place
    (`BR-RAT-1016`, `DEF-RAT-5709`).

    ── WHAT THIS REPLACES, AND WHY IT IS THE BIGGEST OF THE FIVE GAPS ───────
    This file had **no update function of any kind**. So a clerk who typed
    `-15` where they meant `-1.5` on a version that had never been submitted,
    never been approved and had priced nothing had exactly one route out:
    draft a SECOND version carrying a `change_reason` and walk it through
    submit, approve and activate — three acts and, above the tenant's
    threshold, a second person's signature — to fix a typo in something no
    customer had ever seen. The module's own docstring already named the
    missing function: `DISCOUNT_FIELDS`' comment reads *"Every field
    `create_discount` / `update_discount_version` accept"*, and
    `update_discount_version` had never existed. That is hard-won law 1 — a
    comment claiming a guarantee is not the guarantee.

    ── THE RULE, IN `correct_tax`'s OWN WORDS ───────────────────────────────
    *"A draft is not history. It has never priced anything, so there is nothing
    to preserve and nothing to explain."* No reason, no version bump, no
    approval — one audit row, because hard rule 7 counts a money field moving
    even on a draft.

    ⚠ **IT ASKS `submitted_at`, NOT ONLY THE STATUS, AND THE SECOND CHECK IS
    THE LOAD-BEARING ONE.** Today a `DRAFT` always has a null `submitted_at`,
    because nothing returns a version to draft — so the check is redundant
    *today*. It is written because the day somebody adds *send back for
    changes*, a status check alone would silently re-open in-place editing on a
    version an approver has already read, and `BR-RAT-077`'s stored requirement
    would then describe content that has since moved. That is a rule with a
    clock in it (hard-won law 2's mirror), and this is the clock being written
    down rather than left to rot.

    ⚠ **THE SUBMIT / APPROVE / ACTIVATE WORKFLOW IS NOT TOUCHED.**
    `BR-RAT-077` and `BR-RAT-109` govern how a discount goes live and both are
    ratified. This adds an edit path for a draft; it changes nothing about how
    anything becomes the version in force.
    """
    payload = _require_dict(payload)
    # The type the draft already holds (GATE 0): a usage-allowance draft saved
    # before the PO ruling of 2026-10-03 still edits; nothing else becomes one.
    held_type = (
        discount_models.DiscountVersion.objects.filter(tenant_id=_tenant_id(), pk=version_id)
        .values_list("discount_type", flat=True)
        .first()
    )
    cleaned = _validate_version(payload, partial=True, keeps_type=held_type)
    with transaction.atomic():
        version = _version_or_404(version_id)
        if version.status != discount_models.VERSION_DRAFT:
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1016",
                message_key="rating.discounts.edit_not_a_draft",
                params={
                    "status": version.status,
                    # NAMED IN THE REFUSAL: a refusal that does not say what to
                    # do instead is the road ending, which is the shape
                    # `DEF-384` was filed for one object over.
                    "correction_path": f"/discounts/versions/{version.id}/corrections",
                },
            )
        if version.submitted_at is not None:
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1016",
                message_key="rating.discounts.edit_already_submitted",
                params={"version_no": version.version_no},
            )
        before = _json_safe(version_row(version))
        for field, value in cleaned.items():
            setattr(version, field, value)
        if cleaned:
            version.save(update_fields=[*cleaned.keys(), "updated_at"])
        # ⚠ **RE-READ BEFORE SNAPSHOTTING, AND IT IS NOT TIDINESS.** `value` is
        # `NUMERIC(18,6)`, so the column holds `1.500000` while the validated
        # payload held `Decimal("1.5")` — and `version_row` serves
        # `str(version.value)`. Without this the RESPONSE says `1.5` where the
        # next GET says `1.500000` (two screens disagreeing about one figure),
        # and the no-op check below reads that formatting difference as a change
        # and writes an audit row for an edit that changed nothing. Found by
        # `test_an_edit_that_changes_nothing_writes_no_audit_row`, which is why
        # that test exists.
        version.refresh_from_db()
        after = _json_safe(version_row(version))
        if before != after:
            # Hard rule 7 — a draft's VALUE is still a money field, and the one
            # audit row is what makes a draft edited five times readable.
            _audit(
                actor,
                "discount.version_updated",
                "discount_version",
                version.id,
                before=before,
                after=after,
            )
    return version_row(version)


@require_role(SYSTEM_ADMIN)
def correct_discount_version(actor: Any, version_id: Any, payload: Any) -> dict[str, Any]:
    """VERB 2 — a LIVE version is corrected over the SAME window
    (`BR-RAT-1016`, generalising `BR-RAT-104` from `CR-013` part 4's shared
    rules).

    ── A CORRECTION IS NOT A VALUE CHANGE, AND THE DIFFERENCE IS THE WINDOW ──
    A discount whose value CHANGES is already a new version with NEW dates —
    `create_discount_version`, and `BR-RAT-037`'s discipline. A CORRECTION says
    the figure recorded for a period that has already run was **wrong**. So this
    mints a new version carrying the corrected values, **copies the corrected
    row's `effective_from` and `effective_to` VERBATIM rather than taking them
    from the payload**, links the two (`corrects` / `superseded_by`) and marks
    the original superseded so it stops pricing. The original is never rewritten
    and never deleted: it keeps its value, its dates and its approval trail for
    ever.

    **Worked:** a senior discount typed `15.000000` as a PERCENTAGE where the
    programme is `1.500000` reduces a `$196.37` bill by **`$29.46`** instead of
    **`$2.95`** — `$26.51` of subsidy per account per cycle that the utility
    granted and cannot report as intended. Correcting it mints a second version
    at `1.500000` over the same window; the next run reduces by `$2.95`, and the
    15 % row stays visible as the thing that happened.

    ⚠ **THE APPROVAL TRAIL IS NOT FORGED, AND THE ABSENCE OF ONE IS RECORDED.**
    `BR-RAT-077` computes the second-approval requirement AT SUBMIT, and a
    correction does not submit — so the correction row carries **no
    `submitted_by` and no `approved_by`**, because copying the corrected row's
    signatures onto content those people never read would be inventing a
    signature. Instead the requirement is RECOMPUTED from the correction's own
    budget cap and stored beside it, and the audit entry carries
    `corrected_without_submission`. That is `BR-RAT-109`'s ruled posture
    verbatim — PO 2026-08-21, *"We will show message and not refuse it"* — and
    its stated reason applies here unchanged: Silver Creek has 1–2 staff, and a
    refusal that needs a second person is a refusal that stops the business.
    **The warning names what was SKIPPED, never a figure nobody computed.**

    ⚠ **AND IT DOES NOT TOUCH A SINGLE BILL ALREADY ISSUED** — hard rule 4. The
    subsidy already granted at the wrong figure stays granted until somebody
    corrects those bills, and whether that must happen automatically is
    `OQ-310`, unruled since 2026-08-21. The response NAMES it, so an operator
    who has just fixed a value is not left believing the money is fixed.
    """
    payload = _require_dict(payload)
    reason = str(payload.get("reason") or "").strip()
    changes = {key: value for key, value in payload.items() if key != "reason"}
    fe: list[dict[str, Any]] = []
    if len(reason) < MIN_CORRECTION_REASON:
        fe.append(
            _field_error("reason", errors.VAL_REQUIRED, "rating.discounts.correction_reason")
        )
    if not changes:
        # A correction that corrects nothing would mint an identical row and
        # supersede a live version for no reason — a break in the version chain
        # with no content, which is the opposite of what the rule protects.
        fe.append(_field_error("reason", errors.VAL_REQUIRED, "rating.discounts.correction_empty"))
    _refuse(fe)

    with transaction.atomic():
        original = _version_or_404(version_id)
        if original.superseded_by_id is not None:
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1016",
                message_key="rating.discounts.already_corrected",
                params={"version_no": original.version_no},
            )
        if original.status == discount_models.VERSION_DRAFT:
            # A DRAFT is not history — edit it in place (verb 1). Named as the
            # route rather than refused into silence.
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1016",
                message_key="rating.discounts.correct_draft",
                params={"version_no": original.version_no},
            )
        if original.status != discount_models.VERSION_ACTIVE:
            # A version that is not in force has priced nothing, so there is no
            # recorded figure to correct. A pending or scheduled one is
            # withdrawn and re-filed; a superseded one is the audit artefact
            # and is frozen entirely.
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1016",
                message_key="rating.discounts.correct_not_in_force",
                params={"version_no": original.version_no, "status": original.status},
            )
        cleaned = _validate_version({**_version_payload_of(original), **changes}, partial=False)
        before = _json_safe(version_row(original))
        highest = (
            discount_models.DiscountVersion.objects.filter(discount_id=original.discount_id)
            .order_by("-version_no")
            .values_list("version_no", flat=True)
            .first()
            or 0
        )
        required, threshold = second_approval_required(cleaned.get("budget_cap"))
        correction = discount_models.DiscountVersion.objects.create(
            tenant_id=_tenant_id(),
            discount_id=original.discount_id,
            version_no=highest + 1,
            **{
                **cleaned,
                # THE SAME WINDOW, copied from the row being corrected and NOT
                # from the payload: a "correction" that moved the window would
                # be a value change wearing a correction's clothes, and it would
                # silently rewrite which bills the old figure was ever right
                # for. This one line is the whole distinction.
                "effective_from": original.effective_from,
                "effective_to": original.effective_to,
            },
            status=discount_models.VERSION_ACTIVE,
            corrects=original,
            correction_reason=reason,
            corrected_by_id=_actor_user_id(actor),
            # RECOMPUTED, never copied: the flag must describe THIS content, so
            # an auditor reading the correction sees whether the figure now in
            # force would itself have needed a second approval.
            second_approval_required=required,
            second_approval_threshold=threshold,
            # r10's version table renders `change_reason` on every row, and a
            # correction's reason IS why this version exists. One sentence, two
            # columns, so neither table has a blank cell.
            change_reason=reason,
        )
        original.status = discount_models.VERSION_SUPERSEDED
        original.superseded_by = correction
        original.save(update_fields=["status", "superseded_by", "updated_at"])
        after = _json_safe(version_row(original))
        correction_after = _json_safe(version_row(correction))
        # BR-RAT-109's posture — the fact that NO second-approval check ran is
        # written down rather than left to be inferred from a null
        # `submitted_at`. It rides in the AFTER image because `_audit` takes
        # before/after and nothing else.
        correction_after["corrected_without_submission"] = True
        _audit(
            actor,
            "discount.version_corrected",
            "discount_version",
            original.id,
            before=before,
            after=after,
        )
        _audit(
            actor,
            "discount.correction_created",
            "discount_version",
            correction.id,
            after=correction_after,
        )
    row = version_row(correction)
    # ⚠ SAID OUT LOUD IN THE RESPONSE, not only in a docstring — `correct_tax`
    # does the same thing with the same id, for the same reason.
    row["issued_bills_unchanged"] = True
    row["open_question"] = "OQ-310"
    return row


def _version_payload_of(version: Any) -> dict[str, Any]:
    """The corrected version read back as a WRITE payload, so a correction that
    restates ONE field keeps every other field identical.

    Reading the row rather than making the caller resend everything is what
    stops a correction from silently blanking the caps, the scope or the
    verification rules because the client did not know to include them —
    `_tax_payload_of`'s reason, verbatim. Decimals go out as STRINGS, which is
    the shape `_validate_version` accepts and the shape that never round-trips
    through a float (hard rule 2).

    ⚠ `effective_from`/`effective_to` ARE HERE AND ARE THEN OVERWRITTEN BY THE
    CALLER FROM THE ORIGINAL. They are in this payload only so a correction of
    a version with no dates validates identically; the window that is STORED
    comes from `original` and never from here or from the caller.
    """
    payload: dict[str, Any] = {
        "discount_type": version.discount_type,
        "value": str(version.value),
        "currency": version.currency,
        "applies_to": version.applies_to,
        # ⚠ **THE CODE, NOT THE UUID (`DEF-RAT-5815`).** This payload is fed
        # straight back through `_validate_version`, which resolves a CODE
        # since that defect; emitting the uuid here would make every
        # correction of a `one_service` discount refuse *"We don't recognise
        # that service"* on a field the caller never touched. It also matches
        # what every read path already serves.
        "applies_to_service": (
            version.applies_to_service.code if version.applies_to_service_id else None
        ),
        "applies_to_charge_codes": (
            list(version.applies_to_charge_codes) if version.applies_to_charge_codes else None
        ),
        "applies_to_services": (
            list(version.applies_to_services) if version.applies_to_services else None
        ),
        "bill_floor_amount": str(version.bill_floor_amount),
        "stacking_precedence": version.stacking_precedence,
        "stacks_with_others": version.stacks_with_others,
        "exclusivity_group": version.exclusivity_group,
        "eligibility_rule": version.eligibility_rule,
        "eligibility_summary": version.eligibility_summary,
        # `CR-166` §9 — the CODE travels too, so a correction or a new value
        # keeps who qualifies rather than dropping to the free text.
        "eligibility": version.eligibility_code,
        "enrolment_mode": version.enrolment_mode,
        "verification_method": version.verification_method,
        "proof_required": version.proof_required,
        "accepted_proof_kinds": (
            list(version.accepted_proof_kinds) if version.accepted_proof_kinds else None
        ),
        "proof_before_first_reduction": version.proof_before_first_reduction,
        "recertification_months": version.recertification_months,
        "recertification_notice_days": version.recertification_notice_days,
        "recertification_grace_days": version.recertification_grace_days,
        "lapse_behaviour": version.lapse_behaviour,
        "effective_from": str(version.effective_from) if version.effective_from else None,
        "effective_to": str(version.effective_to) if version.effective_to else None,
        "budget_period": version.budget_period,
        "exhaustion_behaviour": version.exhaustion_behaviour,
    }
    for field in ("cap_per_bill", "cap_per_year", "cap_lifetime", "budget_cap"):
        value = getattr(version, field)
        payload[field] = str(value) if value is not None else None
    return payload


@require_role(SYSTEM_ADMIN)
def submit_discount_version(actor: Any, version_id: Any) -> dict[str, Any]:
    """Submit for approval — and **submitting FREEZES the version** (§A7.2).

    The second-approval requirement is computed HERE and STORED, never
    recomputed at approval (§A7.6): an approver must see the requirement the
    submitter saw, and a tenant who edits the threshold in between would
    otherwise move the bar under a signature that had already been given.
    """
    with transaction.atomic():
        version = _version_or_404(version_id)
        if version.status != discount_models.VERSION_DRAFT:
            raise DiscountRuleError(
                errors.BIZ_STATE, br_ref="BR-RAT-077", message_key="rating.discounts.not_a_draft"
            )
        # PO ruling 2026-10-03: a usage allowance is never made live, and
        # approval already refuses it (`_refuse_unpriceable`). Submitting one
        # would only hand an approver a filing nobody can approve, so it is
        # refused here in the same words. `rate_override` is left as it was —
        # the ruling names only the usage allowance.
        if version.discount_type == discount_models.DISCOUNT_USAGE_ALLOWANCE:
            raise DiscountRuleError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-RAT-962",
                message_key="rating.discounts.type_not_priceable",
            )
        required, threshold = second_approval_required(version.budget_cap)
        before = _json_safe(version_row(version))
        version.status = discount_models.VERSION_PENDING_APPROVAL
        version.submitted_by_id = _actor_user_id(actor)
        version.submitted_at = Now()
        version.second_approval_required = required
        version.second_approval_threshold = threshold
        version.save(
            update_fields=[
                "status",
                "submitted_by",
                "submitted_at",
                "second_approval_required",
                "second_approval_threshold",
                "updated_at",
            ]
        )
        version.refresh_from_db(fields=["submitted_at"])
        after = _json_safe(version_row(version))
        _audit(
            actor,
            "discount.version_submitted",
            "discount_version",
            version.id,
            before=before,
            after=after,
        )
    return version_row(version)


@require_role(SYSTEM_ADMIN)
def discard_discount_version_draft(actor: Any, version_id: Any) -> dict[str, Any]:
    """`DEF-RAT-5817` · throw a parked DRAFT away and keep the live discount.

    ⚠ **THIS IS THE OTHER HALF OF REFUSING A SECOND DRAFT, NOT A CONVENIENCE**
    — `discard_rate_schedule_draft`'s reason, verbatim, on the identical index.
    `uq_discount_versions_one_draft` allows exactly ONE draft per discount, and
    before this endpoint there was no way to clear one at all. A refusal saying
    *finish it or discard it* would then name an act nobody could perform, and
    the edit door on that discount would stay shut for ever.

    ⚠ **A DRAFT ONLY, AND THE STATUS IS THE WHOLE GUARD.** Hard rule 4 and
    `BR-RAT-037` make an issued version permanent; a draft has priced nothing,
    is enrolled on by nobody and is not in force, so there is nothing to
    preserve. Any other status is refused by NAME rather than ignored, and it
    names the correction route so the road does not end where a clerk is
    standing — `update_discount_version`'s posture.

    ⚠ **THE NUMBER IS NOT REUSED.** `create_discount_version` takes
    `max(version_no) + 1`, and a discarded `V2` leaves `V1` as the maximum, so
    the next draft is `V2` again. That is deliberate: the discarded row priced
    nothing and was never cited anywhere, so no history acquires a hole — and
    a version_no that skipped would be a gap an auditor would have to be told
    about.
    """
    with transaction.atomic():
        version = _version_or_404(version_id)
        if version.status != discount_models.VERSION_DRAFT:
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-037",
                message_key="rating.discounts.discard_not_a_draft",
            )
        discount = version.discount
        before = _json_safe(version_row(version))
        version.delete()
        _audit(
            actor,
            "discount.version_draft_discarded",
            "discount",
            discount.id,
            before=before,
        )
        return discount_row(discount)


def discount_version_chain(discount: Any) -> list[dict[str, Any]]:
    """`DEF-RAT-5817` · EVERY version of this discount, newest first — the
    read the Audit tab could not make.

    ⚠ **IT EXISTS BECAUSE THE BLOCKING DRAFT WAS INVISIBLE.** DIS-02's detail
    header read `V1` while a `V2` draft sat in the table refusing every further
    edit, and the Audit tab rendered one sentence — *"no endpoint serves those
    versions yet"* — which was true and was the defect. `GET /taxes/{id}/
    versions` is the same read for a tax and landed for the same reason.

    ⚠ **THE OBJECT'S OWN VERSION TABLE, NEVER A FILTERED `audit_log` QUERY.**
    `tax_correction_chain`'s refusal applies unchanged: the two are both
    append-only histories of one object and they answer different questions — a
    version row is a priced state bills still resolve to, an audit row is an
    actor + action + timestamp the engine never reads. And `audit_log` is
    PRUNED on a retention schedule (hard rule 4's 2026-09-02 narrowing), so a
    history sourced from it loses its authors with nothing raising.

    ⚠ **NFR-3 — bounded by the number of times ONE discount has been
    re-filed**, a handful over a programme's life. Never a row per bill and
    never a row per enrolment.
    """
    rows = (
        discount_models.DiscountVersion.objects.filter(
            tenant_id=_tenant_id(), discount=discount
        )
        .select_related("applies_to_service")
        .order_by("-version_no")
    )
    return [version_row(row) for row in rows]


@require_role(SYSTEM_ADMIN)
def approve_discount_version(actor: Any, version_id: Any) -> dict[str, Any]:
    """Approve a pending version — **AND APPROVAL IS THE LAST ACT: THE VERSION
    GOES LIVE BY ITSELF ON ITS START DATE.**

    ⚖️ PO ruling 2026-10-03 (1), verbatim from the decision log row *"GO ON THE
    DISCOUNTS REDESIGN"*: *"an approved discount goes live by itself on its
    start date — approval is the last act; the separate Activate goes."*
    `DEF-RAT-9293` reproduced the old shape: approved with a start date ten days
    past, the discount priced nothing and refused every enrolment until somebody
    pressed Activate.

    ── HOW "BY ITSELF" IS BUILT, AND WHY THERE IS NO JOB ──────────────────────
    Approval writes the version `active` WITH ITS OWN START DATE, and closes the
    open window of every older active version the day before that start, in
    this transaction. Every pricing read already asks *active AND the window
    contains the service date* (`active_version`), so on 12/31/2026 the old
    version answers and on 01/01/2027 the new one does — nothing has to run at
    midnight for the change to happen, and nothing can forget to. `scheduled`
    is no longer written; a future-dated active version is SHOWN as Scheduled by
    the read (`discount_reads.discount_status`), which is a display of a date
    and not a second stored state.

    ⚠ **THE OVERLAP LOCK THEREFORE COVERS EVERY APPROVED VERSION** — they are
    all `active` — and `rating/0061` widens the predicate to `scheduled` as well
    for any legacy row. An approval that would leave two versions in force on
    one date is REFUSED HERE by name (`window_overlaps_version`) before the
    deferred constraint has to speak at COMMIT.

    **A submitter may still approve their own filing** (PO 2026-08-19, *"yes
    allow it"*), recorded on the row and in its own audit action. The checks
    `activate_discount_version` used to make — a type the engine can price, a
    start date — move here, because this is now the act that makes it live.
    """
    with transaction.atomic():
        version = _version_or_404(version_id)
        if version.status != discount_models.VERSION_PENDING_APPROVAL:
            raise DiscountRuleError(
                errors.BIZ_STATE, br_ref="BR-RAT-077", message_key="rating.discounts.not_pending"
            )
        _refuse_unpriceable(version)
        discount = version.discount
        if discount.retire_on is not None and version.effective_from > discount.retire_on:
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-078",
                message_key="rating.discounts.starts_after_retire",
                params={"retire_on": str(discount.retire_on)},
            )
        actor_id = _actor_user_id(actor)
        before = _json_safe(version_row(version))
        closed = _put_in_force(version)
        version.approved_by_id = actor_id
        version.approved_at = Now()
        version.self_approved = bool(actor_id and version.submitted_by_id == actor_id)
        version.status = discount_models.VERSION_ACTIVE
        if discount.retire_on is not None and (
            version.effective_to is None or version.effective_to > discount.retire_on
        ):
            version.effective_to = discount.retire_on
        version.save(
            update_fields=[
                "approved_by",
                "approved_at",
                "self_approved",
                "status",
                "effective_to",
                "updated_at",
            ]
        )
        version.refresh_from_db(fields=["approved_at"])
        if discount.status == discount_models.DISCOUNT_DRAFT:
            discount.status = discount_models.DISCOUNT_ACTIVE
            discount.save(update_fields=["status", "updated_at"])
        after = _json_safe(version_row(version))
        after["goes_live_on"] = str(version.effective_from)
        after["predecessor_windows_closed"] = closed
        _audit(
            actor,
            (
                "discount.version_self_approved"
                if version.self_approved
                else "discount.version_approved"
            ),
            "discount_version",
            version.id,
            before=before,
            after=after,
        )
        # Ruling 3 — an Automatic discount enrols its accounts the moment it is
        # approved, not at the next nightly sweep.
        from apps.rating import discount_enrolment_job

        discount_enrolment_job.sync_discount(discount, actor=actor)
    return version_row(version)


def _refuse_unpriceable(version: Any) -> None:
    """The two refusals that make a version unable to go live, named where an
    operator is looking (formerly at Activate)."""
    if version.discount_type not in discount_models.DISCOUNT_TYPES_PRICEABLE:
        raise DiscountRuleError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-RAT-068",
            message_key="rating.discounts.type_not_priceable",
        )
    if version.effective_from is None:
        raise DiscountRuleError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-RAT-068",
            message_key="rating.discounts.no_effective_date",
        )
    _refuse_named_codes_off_the_tariff(version)


def _refuse_named_codes_off_the_tariff(version: Any) -> None:
    """🔒 HUMAN-REVIEW-PENDING — `DEF-RAT-9327` (2026-10-03).

    A discount scoped to NAMED charge codes is taken over the TARIFF lines
    carrying those codes (BR-RAT-068) — and the only tariff line that carries a
    charge code is the BASE line (`price_usage` stamps it from the code billing
    resolved). A FEE code (a connection charge, a late fee) is never on a tariff
    line, because fees and deposits are never discounted (decision log
    2026-08-22: *"discounting either has no signed rule"*). A waiver naming one
    would take **$0.00** off every bill it reaches while the utility believes it
    granted it — the failure BR-RAT-068's *"subsidy granted is reportable"*
    forbids.

    Until this date the BILL RUN refused instead, stopping every enrolled
    account's whole bill. Refusing at APPROVAL is the same refusal met by the
    person configuring, which is where the decision log puts every refusal of
    this kind (*"a refusal a clerk meets while configuring is a correction; the
    same refusal met during a bill run is an outage"*).

    A code counts as a BASE code when it is ticked `is_base` OR a rate schedule
    names it as its base (`tariff_versions.base_charge_code`, BR-RAT-1025) — the
    two arms by which billing resolves a base. Unknown codes are refused too:
    a code nothing holds is a code no line can carry.
    """
    if version.applies_to != discount_models.SCOPE_NAMED_CODES:
        return
    named = [str(code) for code in (version.applies_to_charge_codes or ())]
    if not named:
        return
    from apps.rating import selectors

    base = selectors.base_charge_codes_among(named)
    off_tariff = [code for code in named if code not in base]
    if off_tariff:
        raise DiscountRuleError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-RAT-068",
            message_key="rating.discounts.named_code_not_priceable",
            params={"codes": ", ".join(off_tariff)},
        )


def _put_in_force(version: Any) -> int:
    """Close every older open window the day before `version` starts, then
    REFUSE if any active version of the discount would still share a date with
    it. Returns how many windows were closed (for the audit row).

    `DEF-RAT-8050`'s close, unchanged (`_close_open_windows_before`), followed
    by the check the database makes at COMMIT — made first, so the clerk reads
    a sentence naming the other version rather than PostgreSQL's.
    """
    closed = _close_open_windows_before(version.discount, version.effective_from)
    far = date.max
    start, end = version.effective_from, version.effective_to or far
    for other in discount_models.DiscountVersion.objects.filter(
        tenant_id=_tenant_id(),
        discount_id=version.discount_id,
        status=discount_models.VERSION_ACTIVE,
        effective_from__isnull=False,
    ).exclude(pk=version.pk):
        if other.effective_from <= end and start <= (other.effective_to or far):
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1016",
                message_key="rating.discounts.window_overlaps_version",
                params={
                    "version_no": other.version_no,
                    "from": str(other.effective_from),
                    "to": str(other.effective_to) if other.effective_to else None,
                },
            )
    return closed


@require_role(SYSTEM_ADMIN)
def activate_discount_version(actor: Any, version_id: Any) -> dict[str, Any]:
    """**RETIRED — there is no Activate (PO ruling 2026-10-03 (1)).**

    Approval is the last act and puts the version in force from its start date
    (`approve_discount_version`). This door is kept ONLY so a screen or a
    script that still posts here is told so in words rather than a 404; it
    changes nothing. With it goes `BR-RAT-109` (*"activating a never-submitted
    discount is allowed, warned and recorded"*): there is no longer any door
    through which a never-submitted draft goes live, so there is nothing left to
    warn about — SUPERSEDED in `02-business-rules.md`, citing the ruling.
    """
    _version_or_404(version_id)
    raise DiscountRuleError(
        errors.BIZ_STATE,
        br_ref="BR-RAT-077",
        message_key="rating.discounts.activate_retired",
    )


@require_role(SYSTEM_ADMIN)
def retire_discount(actor: Any, discount_id: Any, payload: Any = None) -> dict[str, Any]:
    """**Retire ON A DATE: after it nobody gets the discount, enrolled accounts
    included; nothing changes before it.**

    ⚖️ PO ruling 2026-10-03 (4): *"Retire asks for an end date, and after it
    nobody gets the discount, accounts already enrolled included — the same as
    Retire on taxes."* It SUPERSEDES the retire half of `BR-RAT-078` (*"retiring
    blocks new enrolment and leaves existing ones alone"*).

    ⚠ **AND IT FIXES A STOP THAT RAN BACKWARDS (`DEF-RAT-9296`).** The old act
    took no date and set `Discount.status = retired`; `discount_rules_for_account`
    skipped a discount by that CURRENT status, so after retiring MUNICIPAL the
    enrolled government account lost its 20% on 08/15, 09/15 and 12/15/2026
    alike — a re-bill of August lost a discount it was owed. Now nothing reads
    the status to decide a date: the retirement is WRITTEN ONTO THE WINDOWS that
    every pricing read already honours by date.

    **What it writes, in one transaction:**
      * every active version in force on `effective_to` ends on it; one that
        would only START after it never prices and is marked superseded;
      * every open enrolment ends on `effective_to`, reason `discount_retired`
        (the drawing's Accounts tab then reads *ended*, never *receiving*);
      * `Discount.retire_on = effective_to` — what a new enrolment and a screen
        ask (*Retiring 12/31/2026* until then, *Retired* after).

    **Worked (asserted on PostgreSQL):** SENIOR 15% retired on 12/31/2026 — the
    December bill keeps **−$9.00** off **$60.00**; January's has none.

    ⚠ **A DATE BEFORE TODAY IS REFUSED** (`CR-166` §7 item 6, our judgment):
    issued bills are immutable (hard rule 4), and a retirement reaching back
    would make a re-bill of an already-billed period disagree with the bill.
    """
    payload = _require_dict(payload or {})
    fe: list[dict[str, Any]] = []
    _reject_unknown(payload, ("effective_to", "reason"), fe)
    end = _as_date(payload.get("effective_to"))
    if end is None:
        fe.append(_field_error("effective_to", errors.VAL_REQUIRED, "rating.discounts.retire_date"))
    elif end < seams.tenant_today():
        fe.append(
            _field_error("effective_to", errors.VAL_RANGE, "rating.discounts.retire_in_past")
        )
    _refuse(fe)
    with transaction.atomic():
        discount = _discount_or_404(discount_id)
        before = _json_safe(discount_row(discount))
        ended_versions = 0
        for version in discount_models.DiscountVersion.objects.filter(
            tenant_id=_tenant_id(),
            discount=discount,
            status=discount_models.VERSION_ACTIVE,
            effective_from__isnull=False,
        ):
            if version.effective_from > end:
                version.status = discount_models.VERSION_SUPERSEDED
                version.save(update_fields=["status", "updated_at"])
                ended_versions += 1
            elif version.effective_to is None or version.effective_to > end:
                version.effective_to = end
                version.save(update_fields=["effective_to", "updated_at"])
                ended_versions += 1
        enrolments = discount_models.DiscountEnrolment.objects.filter(
            tenant_id=_tenant_id(), discount=discount
        ).filter(Q(ended_on__isnull=True) | Q(ended_on__gt=end))
        ended = enrolments.update(ended_on=end, end_reason="discount_retired")
        discount.retire_on = end
        discount.save(update_fields=["retire_on", "updated_at"])
        after = _json_safe(discount_row(discount))
        after.update(
            {
                "retire_on": str(end),
                "versions_ended": ended_versions,
                "enrolments_ended": ended,
                "reason": payload.get("reason"),
            }
        )
        _audit(actor, "discount.retired", "discount", discount.id, before=before, after=after)
    return discount_row(discount)


@require_role(SYSTEM_ADMIN)
def suspend_discount_for_funding(actor: Any, discount_id: Any) -> dict[str, Any]:
    """The one status a BILL RUN sets: `suspended_funding_exhausted`.

    Called by the bill run when `price_discounts` reports a code in
    `DiscountOutcome.exhausted`. It is its own status rather than `retired`
    because a retired programme is a decision and an exhausted one is an
    accident of arithmetic — and the difference decides whether re-funding is a
    one-field edit or a new discount.
    """
    with transaction.atomic():
        discount = _discount_or_404(discount_id)
        before = _json_safe(discount_row(discount))
        discount.status = discount_models.DISCOUNT_SUSPENDED_FUNDING
        discount.funding_exhausted_at = Now()
        discount.save(update_fields=["status", "funding_exhausted_at", "updated_at"])
        discount.refresh_from_db(fields=["funding_exhausted_at"])
        _audit(
            actor,
            "discount.funding_exhausted",
            "discount",
            discount.id,
            before=before,
            after=_json_safe(discount_row(discount)),
        )
    return discount_row(discount)


# ── plan availability — AVAILABLE, NOT GRANTED ──────────────────────────────
@require_role(SYSTEM_ADMIN)
def attach_discount_to_plan(
    actor: Any,
    rate_plan_id: Any,
    discount_id: Any,
    available_from: date | None = None,
    available_to: date | None = None,
) -> dict[str, Any]:
    """PLN-03 step 6 — *"available discounts (available, not granted)"*.

    ⚠ **THIS FUNCTION TAKES NO VALUE, AND THAT IS THE PO'S RULING OF
    2026-08-19** (*"no plan cannot override prices"*). r10 draws a per-plan
    discount-value override; it is not built, and `plan_discount_rules` has no
    column that could hold one.

    ⚠ **AND CALLING IT DISCOUNTS NOBODY.** The bill run reads
    `DiscountEnrolment`. If this attachment ever became what R6 reads, every
    account on the plan would be discounted — 842 of them on Residential
    Standard — and every one of those bills would be wrong.
    """
    with transaction.atomic():
        discount = _discount_or_404(discount_id)
        plan = rating_models.RatePlan.objects.filter(
            tenant_id=_tenant_id(), pk=rate_plan_id
        ).first()
        if plan is None:
            raise errors.NotFoundError()
        rule, created = discount_models.PlanDiscountRule.objects.get_or_create(
            tenant_id=_tenant_id(),
            rate_plan=plan,
            discount=discount,
            defaults={"available_from": available_from, "available_to": available_to},
        )
        if created:
            _audit(
                actor,
                "discount.made_available_on_plan",
                "plan_discount_rule",
                rule.id,
                after={"rate_plan": str(plan.id), "discount": discount.code},
            )
    return {"id": str(rule.id), "rate_plan": str(plan.id), "discount": discount.code}


# ── enrolment — THE GRANT ───────────────────────────────────────────────────
# ⚖️ A BILLING CLERK ENROLS TOO — PO ruling 2026-10-05 (decision log *"FOUR PO
# RULINGS IN ONE REPLY"* (2), option (b)), verbatim: *"Let billing clerks
# record it themselves. - we have set the limits so clark can do it - its a day
# to day work"*. Widened HERE, on the one grant writer, through the same
# `require_role` every door uses — no new limit and no second path. What a
# clerk may enrol is still bounded by the discount itself: only a discount the
# account's plan carries (BR-RAT-110/1062), never a retired one (BR-RAT-078),
# *pending* when its programme asks for proof (BR-RAT-076), at the value the
# approved version states. Creating, approving, verifying and ending a discount
# stay System Admin's. Only `POST /accounts/{id}/discounts` and the move-in
# reach this function (rating serves no enrolment door of its own).
@require_role(SYSTEM_ADMIN, BILLING_CLERK)
def enrol_account(
    actor: Any,
    discount_id: Any,
    account_id: Any,
    enrolled_on: date | None = None,
) -> dict[str, Any]:
    """Enrol ONE account. This — not plan attachment — is what discounts a bill.

    Two refusals, both from part 3:
      * a **retired** discount takes no new enrolment (*"retiring blocks new
        enrolment"*);
      * a discount whose version demands proof enrols as `pending`, not
        `verified`, so `proof_before_first_reduction` can do its job. A caller
        cannot pass a verification status in — verification is its own recorded
        act with its own audit row.
    """
    with transaction.atomic():
        discount = _discount_or_404(discount_id)
        # BR-RAT-078's surviving clause — *"retiring blocks new enrolment"* —
        # now true from the moment a retirement is RECORDED (ruling 4 gives it a
        # date; the legacy stored status still counts for rows retired before).
        if discount.status == discount_models.DISCOUNT_RETIRED or discount.retire_on:
            raise DiscountRuleError(
                errors.BIZ_STATE, br_ref="BR-RAT-078", message_key="rating.discounts.retired"
            )
        account = _account_or_refuse(account_id)
        when = enrolled_on or seams.tenant_today()
        version = active_version(discount, when)
        if version is None:
            raise DiscountRuleError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-RAT-069",
                message_key="rating.discounts.no_active_version",
            )
        existing = discount_models.DiscountEnrolment.objects.filter(
            tenant_id=_tenant_id(), discount=discount, account=account, ended_on__isnull=True
        ).first()
        if existing is not None:
            return enrolment_row(existing)  # idempotent (hard rule 6 posture)
        # ⚖️ RULING 2 (PO 2026-10-03): *"Only accounts whose plan carries the
        # discount can get it."* `DEF-RAT-9294` reproduced the old shape: SENIOR
        # (on no plan) enrolled A-10432, the Enrolled count said 1, the R6 door
        # took $9.00 off a $60.00 bill and the bill run silently dropped it.
        # Refused by NAME here, on the enrolment date, through the ONE resolver
        # every reader uses (`discount_ids_carried`).
        if discount.id not in discount_ids_carried(account.id, when):
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-110",
                message_key="rating.discounts.plan_does_not_carry",
                params={"discount": discount.code, "on_day": str(when)},
            )

        needs_proof = version.proof_required or version.verification_method != (
            discount_models.VERIFY_AUTOMATIC
        )
        enrolment = discount_models.DiscountEnrolment.objects.create(
            tenant_id=_tenant_id(),
            discount=discount,
            account=account,
            enrolled_on=when,
            enrolled_by_id=_actor_user_id(actor),
            verification_status=(
                discount_models.VERIFICATION_PENDING
                if needs_proof
                else discount_models.VERIFICATION_NOT_REQUIRED
            ),
            currency=version.currency,
        )
        _audit(
            actor,
            "discount.account_enrolled",
            "discount_enrolment",
            enrolment.id,
            after=_json_safe(enrolment_row(enrolment)),
        )
    return enrolment_row(enrolment)


@require_role(SYSTEM_ADMIN)
def verify_enrolment(
    actor: Any,
    enrolment_id: Any,
    proof_kind: str | None = None,
    proof_reference: str | None = None,
    verified_on: date | None = None,
) -> dict[str, Any]:
    """Record that the proof is on file, and set the recertification clock.

    `recertification_due_on` is computed from the version's
    `recertification_months` — NULL months means nothing to recertify (a
    one-time proof, or an automatic programme). Part 3's *"expiring in 30
    days"* filter reads that column, so a programme that never expires must
    leave it NULL rather than parking a date far in the future that a report
    would eventually surface.

    ⚠ `DiscountEnrolmentDocument.restricted` is DERIVED from `proof_kind`
    (BR-RAT-079) — income and medical proof are restricted and must not appear
    in the general document lists a clerk browses. A caller cannot pass the
    flag; deriving it is what stops a new restricted kind being filed as an
    ordinary one by an endpoint that forgot.
    """
    with transaction.atomic():
        enrolment = _enrolment_or_404(enrolment_id)
        version = active_version(enrolment.discount)
        when = verified_on or seams.tenant_today()
        before = _json_safe(enrolment_row(enrolment))
        if proof_kind:
            if proof_kind not in discount_models.PROOF_KINDS:
                _refuse(
                    [
                        _field_error(
                            "proof_kind", errors.VAL_UNKNOWN_LOOKUP, "rating.discounts.proof"
                        )
                    ]
                )
            discount_models.DiscountEnrolmentDocument.objects.create(
                tenant_id=_tenant_id(),
                enrolment=enrolment,
                kind=proof_kind,
                reference=proof_reference,
                received_on=when,
                restricted=proof_kind in discount_models.RESTRICTED_PROOF_KINDS,
                uploaded_by_id=_actor_user_id(actor),
            )
        enrolment.verification_status = discount_models.VERIFICATION_VERIFIED
        enrolment.verified_on = when
        enrolment.verified_by_id = _actor_user_id(actor)
        enrolment.recertification_due_on = _recert_due(when, version)
        enrolment.save(
            update_fields=[
                "verification_status",
                "verified_on",
                "verified_by",
                "recertification_due_on",
                "updated_at",
            ]
        )
        _audit(
            actor,
            "discount.enrolment_verified",
            "discount_enrolment",
            enrolment.id,
            before=before,
            after=_json_safe(enrolment_row(enrolment)),
        )
    return enrolment_row(enrolment)


#: DEF-CUS-9780 — the proof kind an *assistance evidence* upload is filed as,
#: when the programme accepts it. B18 §5.3.4's evidence is evidence of being in
#: an assistance PROGRAMME, and the award letter is that document.
ASSISTANCE_EVIDENCE_KIND = "programme_award_letter"


def proof_kind_for_assistance_evidence(version: Any) -> str:
    """Which `PROOF_KINDS` value a move-in's *Assistance evidence* upload is.

    Our judgment (decision log 2026-10-06, `DEF-CUS-9780`; the clerk's checklist
    names no proof kind, and no rule did): the award letter when the programme
    accepts one; otherwise the FIRST kind the programme accepts, which is what
    the clerk was collecting against (`household_income_limit` → an income
    statement, which BR-RAT-079 then restricts); the award letter again when the
    programme lists none. `restricted` is never chosen here — it is derived
    from the kind by the writer below.
    """
    accepted = [kind for kind in (getattr(version, "accepted_proof_kinds", None) or [])]
    if ASSISTANCE_EVIDENCE_KIND in accepted:
        return ASSISTANCE_EVIDENCE_KIND
    for kind in accepted:
        if kind in discount_models.PROOF_KINDS:
            return kind
    return ASSISTANCE_EVIDENCE_KIND


@require_role(SYSTEM_ADMIN, BILLING_CLERK)
def attach_enrolment_proof(
    actor: Any,
    enrolment_id: Any,
    references: list[Any],
    received_on: date | None = None,
) -> list[dict[str, Any]]:
    """🔒 HUMAN-REVIEW-PENDING — `DEF-CUS-9780` (2026-10-06). Put the evidence a
    clerk took at the counter ON the enrolment it supports, WITHOUT verifying.

    `references` are the documents surface's handles — the account document
    (filing card) ids the move-in filed. One `discount_enrolment_documents` row
    each (B18 §5.5.5's `evidence_ref`), kind from
    :func:`proof_kind_for_assistance_evidence`, `restricted` DERIVED from that
    kind (BR-RAT-079), uploaded by the clerk.

    ⚠ **NOTHING ELSE MOVES.** `verification_status`, `verified_on`,
    `verified_by` and the recertification clock are untouched: PO ruling (2) of
    2026-10-05 lets a clerk RECORD a claim and keeps verifying System Admin's,
    and BR-RAT-076's `proof_before_first_reduction` still holds the reduction
    until :func:`verify_enrolment` runs. Only a *pending* enrolment takes proof
    here — one that needs none, or is already verified, is left as it is and
    nothing is written. A reference already on the enrolment is not written
    twice.
    """
    wanted = [str(one) for one in references if one]
    if not wanted:
        return []
    with transaction.atomic():
        enrolment = _enrolment_or_404(enrolment_id)
        if enrolment.verification_status != discount_models.VERIFICATION_PENDING:
            return []
        version = active_version(enrolment.discount, enrolment.enrolled_on)
        kind = proof_kind_for_assistance_evidence(version)
        when = received_on or seams.tenant_today()
        held = set(
            discount_models.DiscountEnrolmentDocument.objects.filter(
                tenant_id=_tenant_id(), enrolment=enrolment
            ).values_list("reference", flat=True)
        )
        written: list[dict[str, Any]] = []
        for reference in wanted:
            if reference in held:
                continue
            held.add(reference)
            document = discount_models.DiscountEnrolmentDocument.objects.create(
                tenant_id=_tenant_id(),
                enrolment=enrolment,
                kind=kind,
                reference=reference,
                received_on=when,
                restricted=kind in discount_models.RESTRICTED_PROOF_KINDS,
                uploaded_by_id=_actor_user_id(actor),
            )
            row = {
                "id": str(document.id),
                "enrolment_id": str(enrolment.id),
                "kind": document.kind,
                "reference": document.reference,
                "received_on": str(document.received_on),
                "restricted": document.restricted,
            }
            _audit(
                actor,
                "discount.enrolment_proof_attached",
                "discount_enrolment",
                enrolment.id,
                after=row,
            )
            written.append(row)
    return written


def enrolment_proof_references(enrolment_ids: list[Any]) -> dict[str, str]:
    """`{enrolment id: the latest proof reference}` for a page of enrolments —
    the Accounts tab's *View proof*, one query for the page (`DEF-CUS-9780`).
    The CALLER decides who may see it (BR-RAT-079: restricted by role)."""
    out: dict[str, str] = {}
    rows = (
        discount_models.DiscountEnrolmentDocument.objects.filter(
            tenant_id=_tenant_id(), enrolment_id__in=list(enrolment_ids)
        )
        .exclude(reference__isnull=True)
        .exclude(reference="")
        .order_by("created_at", "id")
        .values_list("enrolment_id", "reference")
    )
    for enrolment_id, reference in rows:
        out[str(enrolment_id)] = reference
    return out


@require_role(SYSTEM_ADMIN)
def end_enrolment(actor: Any, enrolment_id: Any, reason: str, ended_on: date | None = None) -> dict:
    """End one enrolment. r10's own words: *"Removing a customer from the
    program restores full price with no rate change."*

    The row is kept — part 5's deletion bar is *"once billed **or ever
    enrolled**"* — and the reason is stored, because *"why did my bill go up
    $25?"* is answered from this column.
    """
    with transaction.atomic():
        enrolment = _enrolment_or_404(enrolment_id)
        when = _as_date(ended_on) or seams.tenant_today()
        fe: list[dict[str, Any]] = []
        if not str(reason or "").strip():
            fe.append(_field_error("reason", errors.VAL_REQUIRED, "rating.required"))
        if enrolment.ended_on is not None and enrolment.ended_on < when:
            fe.append(
                _field_error("ended_on", errors.VAL_RANGE, "rating.discounts.enrolment_already_ended")
            )
        if when < enrolment.enrolled_on:
            fe.append(
                _field_error("ended_on", errors.VAL_RANGE, "rating.discounts.end_before_enrolled")
            )
        _refuse(fe)
        before = _json_safe(enrolment_row(enrolment))
        enrolment.ended_on = when
        enrolment.end_reason = str(reason).strip()
        enrolment.save(update_fields=["ended_on", "end_reason", "updated_at"])
        _audit(
            actor,
            "discount.enrolment_ended",
            "discount_enrolment",
            enrolment.id,
            before=before,
            after=_json_safe(enrolment_row(enrolment)),
        )
    return enrolment_row(enrolment)


@require_role(SYSTEM_ADMIN)
def record_grant(
    actor: Any,
    enrolment_id: Any,
    period_start: date,
    period_end: date,
    amount: Decimal,
    invoice_id: Any = None,
) -> dict[str, Any]:
    """Append ONE subsidy actually given — the row that makes it reportable.

    **Append-only** (hard rule 4): an issued bill's reduction is never updated
    or deleted; a correction is a NEW row with a negative `amount`, so the SUM
    over rows is always the net subsidy. The enrolment's
    `lifetime_subsidy_amount` is moved in the SAME transaction, which is what
    keeps the denormalised counter equal to the sum a test asserts.

    Every call writes `audit_log` — CLAUDE.md rule 7, and this is money.
    """
    with transaction.atomic():
        enrolment = _enrolment_or_404(enrolment_id)
        version = active_version(enrolment.discount)
        if version is None:
            raise DiscountRuleError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-RAT-075",
                message_key="rating.discounts.no_active_version",
            )
        grant = discount_models.DiscountGrant.objects.create(
            tenant_id=_tenant_id(),
            enrolment=enrolment,
            discount=enrolment.discount,
            discount_version=version,
            invoice_id=invoice_id,
            period_start=period_start,
            period_end=period_end,
            amount=Decimal(amount),
            currency=enrolment.currency,
        )
        enrolment.lifetime_subsidy_amount = Decimal(enrolment.lifetime_subsidy_amount) + Decimal(
            amount
        )
        enrolment.save(update_fields=["lifetime_subsidy_amount", "updated_at"])
        _audit(
            actor,
            "discount.subsidy_granted",
            "discount_grant",
            grant.id,
            after={
                "discount": enrolment.discount.code,
                "amount": str(grant.amount),
                "currency": grant.currency,
                "period": f"{period_start}..{period_end}",
                "invoice_id": str(invoice_id) if invoice_id else None,
            },
        )
    return {"id": str(grant.id), "amount": str(grant.amount), "currency": grant.currency}


# ── DEF-2430 / DEF-BIL-5341 · the grant, recorded AT ISSUE (PO 2026-10-03) ──
#
# PO ruling 2026-10-03, verbatim: *"A · Yearly caps don't count down - a"*.
# Until these two writes existed `discount_grants` had no writer on the bill
# path, so every cap and budget below — each a SUM over grants (BR-RAT-075) —
# read $0.00 spent forever. Billing calls them through ONE seam
# (`billing.rating_seam.record_discount_grants` / `reverse_discount_grants`)
# and contributes the figures and the document; RATING resolves which
# enrolment and which version each figure spent, because it already owns that
# answer (`discount_rules_for_account`) — the same shape as the ledger posting
# seam. No arithmetic: every amount is the issued bill's own discount line.



#: The bills whose grants a PREVIEW re-price must not count (see
#: `grants_excluded`). Empty everywhere but inside that block.
_EXCLUDED_INVOICES: ContextVar[frozenset[str]] = ContextVar(
    "rating_discount_grants_excluded", default=frozenset()
)


@contextmanager
def grants_excluded(*invoice_ids: Any) -> Iterator[None]:
    """Price AS IF these bills had granted nothing — for a correction PREVIEW.

    A correction gives the original bill's grants back before its rebill is
    priced (`reverse_grants_for_invoice`), so the rebill sees the cap headroom
    the original spent. The preview (`billing.corrections.recompute`) writes
    nothing and so cannot reverse anything; without this its figure would
    disagree with the one the correction then issues — a December preview
    reading $0.00 CAP off because the year includes December's own $25.00,
    and the executed rebill taking $25.00. Read-only: it only narrows the three
    sums below for the duration of the block.
    """
    token = _EXCLUDED_INVOICES.set(
        _EXCLUDED_INVOICES.get() | {str(i) for i in invoice_ids if i is not None}
    )
    try:
        yield
    finally:
        _EXCLUDED_INVOICES.reset(token)


def _counted(grants: Any) -> Any:
    excluded = _EXCLUDED_INVOICES.get()
    return grants.exclude(invoice_id__in=list(excluded)) if excluded else grants


def _enrolment_on(account_id: Any, code: str, on_day: date) -> Any:
    """The account's enrolment in programme `code` IN FORCE on `on_day` — the
    same window `discount_rules_for_account` priced the bill on, so the grant
    is recorded against exactly the enrolment that produced the reduction."""
    rows = list(
        discount_models.DiscountEnrolment.objects.filter(
            tenant_id=_tenant_id(),
            account_id=account_id,
            discount__code=code,
            enrolled_on__lte=on_day,
        )
        .filter(Q(ended_on__isnull=True) | Q(ended_on__gte=on_day))
        .select_related("discount")
        .order_by("-enrolled_on")[:1]
    )
    return rows[0] if rows else None


def record_grants_for_invoice(
    actor: Any,
    *,
    account_id: Any,
    invoice_id: Any,
    period_start: date,
    period_end: date,
    service_date: date,
    granted: dict[str, Decimal],
) -> dict[str, Any]:
    """Record what ONE issued bill granted — one `discount_grants` row per
    programme, against the enrolment and the version IN FORCE ON THE BILL'S
    SERVICE DATE (BR-RAT-007's pivot, the day it was priced on).

    `granted` is `{programme code: POSITIVE amount}` read off the bill's own
    discount lines. **Idempotent (hard rule 6):** a second call for the same
    bill finds the row `uq_discount_grants_enrolment_invoice` already holds and
    writes nothing, so replaying an issue cannot count a subsidy twice.

    ⚖️ **IT NEVER REFUSES — A DISCOUNT NEVER STOPS A BILL** (`DEF-RAT-9522`; PO
    2026-10-04, *"We cannot hold the bill; we need to make discount value to 0
    and move on - we cannot stop the billing"*). 2.491.0 refused here when the
    account held no enrolment in the programme on the service date, and the
    bill stayed a draft. Now:
      * the enrolment was ENDED after the bill was priced (back-dated) — the
        grant is recorded against that enrolment, because the bill gives what it
        was priced to give and the cap must count it; audited as
        `discount.grant_after_enrolment_ended`;
      * the account NEVER held the programme — nothing to count against, so no
        grant; audited as `discount.grant_unrecorded` and returned in
        `unrecorded`;
      * no version in force on the day — the programme's latest version stamps
        the grant (the money was given; only the label is approximate).
    Re-pricing the line to $0.00 here is not possible: the bill's taxes were
    computed with the discount in their base (BR-RAT-106), and issue does not
    re-price.

    Moves `lifetime_subsidy_amount` in the same transaction as each row and
    writes one `audit_log` row per grant (hard rule 7).
    """
    written: list[dict[str, Any]] = []
    existing: list[dict[str, Any]] = []
    unrecorded: list[dict[str, Any]] = []
    with transaction.atomic():
        for code in sorted(granted):
            amount = Decimal(granted[code])
            enrolment = _enrolment_on(account_id, code, service_date)
            ended_since = False
            if enrolment is None:
                # DEF-RAT-9522 — never a refusal. The enrolment that priced this
                # bill, ended since; or none at all.
                enrolment = (
                    discount_models.DiscountEnrolment.objects.filter(
                        tenant_id=_tenant_id(), account_id=account_id, discount__code=code
                    )
                    .select_related("discount")
                    .order_by("-enrolled_on", "-created_at")
                    .first()
                )
                if enrolment is None:
                    _audit(
                        actor,
                        "discount.grant_unrecorded",
                        "invoice",
                        invoice_id,
                        after={
                            "discount": code,
                            "amount": str(amount),
                            "reason": "account_never_enrolled",
                            "period": f"{period_start}..{period_end}",
                        },
                    )
                    unrecorded.append({"code": code, "amount": str(amount)})
                    continue
                ended_since = True
            prior = discount_models.DiscountGrant.objects.filter(
                tenant_id=_tenant_id(),
                enrolment=enrolment,
                invoice_id=invoice_id,
                reverses_grant__isnull=True,
            ).first()
            if prior is not None:
                existing.append({"id": str(prior.id), "code": code, "amount": str(prior.amount)})
                continue
            version = (
                active_version(enrolment.discount, service_date)
                or discount_models.DiscountVersion.objects.filter(
                    tenant_id=_tenant_id(), discount=enrolment.discount
                )
                .order_by("-version_no")
                .first()
            )
            if version is None:  # a programme with no version cannot have priced it
                _audit(
                    actor,
                    "discount.grant_unrecorded",
                    "invoice",
                    invoice_id,
                    after={"discount": code, "amount": str(amount), "reason": "no_version"},
                )
                unrecorded.append({"code": code, "amount": str(amount)})
                continue
            grant = discount_models.DiscountGrant.objects.create(
                tenant_id=_tenant_id(),
                enrolment=enrolment,
                discount=enrolment.discount,
                discount_version=version,
                invoice_id=invoice_id,
                period_start=period_start,
                period_end=period_end,
                amount=amount,
                currency=enrolment.currency,
            )
            enrolment.lifetime_subsidy_amount = Decimal(enrolment.lifetime_subsidy_amount) + amount
            enrolment.save(update_fields=["lifetime_subsidy_amount", "updated_at"])
            _audit(
                actor,
                "discount.subsidy_granted",
                "discount_grant",
                grant.id,
                after={
                    "discount": code,
                    "version": version.version_no,
                    "amount": str(grant.amount),
                    "currency": grant.currency,
                    "period": f"{period_start}..{period_end}",
                    "invoice_id": str(invoice_id),
                },
            )
            if ended_since:
                _audit(
                    actor,
                    "discount.grant_after_enrolment_ended",
                    "discount_grant",
                    grant.id,
                    after={
                        "discount": code,
                        "amount": str(grant.amount),
                        "ended_on": str(enrolment.ended_on),
                        "invoice_id": str(invoice_id),
                    },
                )
            written.append({"id": str(grant.id), "code": code, "amount": str(grant.amount)})
    return {"written": written, "already_recorded": existing, "unrecorded": unrecorded}


def reverse_grants_for_invoice(
    actor: Any, *, invoice_id: Any, reason: str, document_id: Any = None
) -> dict[str, Any]:
    """Give back every subsidy ONE corrected bill granted — hard rule 4: a NEW
    row of the opposite sign per grant, naming the grant it reverses, never an
    edit. The reversal keeps the original bill's `invoice_id` and period, so it
    lands in the same cap year as the money it cancels.

    Called by a correction BEFORE the replacement bill is priced, so the
    replacement sees the cap headroom the original spent: Carl's corrected
    December bill gives its $25.00 CAP credit back and the rebill takes $25.00
    again, rather than finding his year already at $300.00.

    **Idempotent (hard rule 6):** `uq_discount_grants_reverses_grant` holds
    one reversal per grant, and a grant already reversed is skipped here, so a
    replayed correction gives nothing back twice. A bill that granted nothing
    reverses nothing and writes nothing.
    """
    reversed_rows: list[dict[str, Any]] = []
    with transaction.atomic():
        originals = list(
            discount_models.DiscountGrant.objects.filter(
                tenant_id=_tenant_id(), invoice_id=invoice_id, reverses_grant__isnull=True
            )
            .select_related("enrolment", "discount")
            .order_by("granted_at", "id")
        )
        done = set(
            discount_models.DiscountGrant.objects.filter(
                tenant_id=_tenant_id(), reverses_grant__in=[g.id for g in originals]
            ).values_list("reverses_grant_id", flat=True)
        )
        for grant in originals:
            if grant.id in done:
                continue
            reversal = discount_models.DiscountGrant.objects.create(
                tenant_id=_tenant_id(),
                enrolment=grant.enrolment,
                discount=grant.discount,
                discount_version_id=grant.discount_version_id,
                invoice_id=grant.invoice_id,
                period_start=grant.period_start,
                period_end=grant.period_end,
                amount=-Decimal(grant.amount),
                currency=grant.currency,
                reverses_grant=grant,
            )
            enrolment = grant.enrolment
            enrolment.lifetime_subsidy_amount = Decimal(
                enrolment.lifetime_subsidy_amount
            ) - Decimal(grant.amount)
            enrolment.save(update_fields=["lifetime_subsidy_amount", "updated_at"])
            _audit(
                actor,
                "discount.subsidy_reversed",
                "discount_grant",
                reversal.id,
                before={"amount": str(grant.amount)},
                after={
                    "discount": grant.discount.code,
                    "amount": str(reversal.amount),
                    "currency": reversal.currency,
                    "period": f"{grant.period_start}..{grant.period_end}",
                    "invoice_id": str(grant.invoice_id),
                    "reason": reason,
                    "document_id": str(document_id) if document_id else None,
                },
            )
            reversed_rows.append(
                {"id": str(reversal.id), "code": grant.discount.code, "amount": str(reversal.amount)}
            )
    return {"reversed": reversed_rows}


# ── CR-166-BRC10 §9 · the discount-level doors the redesigned screens use ───
#
# The drawing's buttons act on THE DISCOUNT (*Submit for approval*, *Approve*,
# *Send back*, *Edit*, *Retire*), never on a version id a clerk cannot see. Each
# door below resolves WHICH version it means and delegates to the version-level
# service that owns the rule, so there is one rulebook and two spellings of the
# address. A payload may name `version_id` to be explicit; without it the door
# acts on the one version in the state the act needs, and refuses by name when
# there is none or more than one.


def _the_version(discount: Any, status: str, version_id: Any = None) -> Any:
    qs = discount_models.DiscountVersion.objects.filter(
        tenant_id=_tenant_id(), discount=discount, status=status
    )
    if version_id:
        row = qs.filter(pk=version_id).first()
        if row is None:
            raise errors.NotFoundError()
        return row
    rows = list(qs.order_by("version_no")[:2])
    if not rows:
        raise DiscountRuleError(
            errors.BIZ_STATE,
            br_ref="BR-RAT-077",
            message_key=f"rating.discounts.no_version_{status}",
        )
    if len(rows) > 1:
        raise DiscountRuleError(
            errors.BIZ_STATE,
            br_ref="BR-RAT-077",
            message_key="rating.discounts.several_versions_name_one",
            params={"status": status, "version_nos": [row.version_no for row in rows]},
        )
    return rows[0]


def submit_discount(actor: Any, discount_id: Any, payload: Any = None) -> dict[str, Any]:
    """`POST /discounts/{id}/submit` — the discount's DRAFT goes for approval."""
    payload = _require_dict(payload or {})
    discount = _discount_or_404(discount_id)
    version = _the_version(discount, discount_models.VERSION_DRAFT, payload.get("version_id"))
    return submit_discount_version(actor, version.id)


def approve_discount(actor: Any, discount_id: Any, payload: Any = None) -> dict[str, Any]:
    """`POST /discounts/{id}/approve` — the LAST act (ruling 1)."""
    payload = _require_dict(payload or {})
    discount = _discount_or_404(discount_id)
    version = _the_version(
        discount, discount_models.VERSION_PENDING_APPROVAL, payload.get("version_id")
    )
    return approve_discount_version(actor, version.id)


@require_role(SYSTEM_ADMIN)
def send_back_discount(actor: Any, discount_id: Any, payload: Any = None) -> dict[str, Any]:
    """`POST /discounts/{id}/send-back {note}` — the approver returns a filing.

    The drawing's *Waiting approval* header carries *Send back · Approve* (image
    26). A version sent back is a DRAFT again and EDITS IN PLACE — which is the
    case `update_discount_version`'s docstring wrote down a clock for (*"the day
    somebody adds send back for changes, a status check alone would silently
    re-open in-place editing on a version an approver has already read"*). So
    the clock is wound here, deliberately and visibly: `submitted_at` is
    cleared, the requirement it froze is cleared with it, the NOTE is kept on
    the row (`rejection_reason`) and the whole before/after is in `audit_log`,
    so the next submit freezes the content again and BR-RAT-077 recomputes the
    second-approval requirement on what is actually submitted.

    Refused when the discount already holds another draft — one draft at a
    time (`uq_discount_versions_one_draft`, `BR-RAT-031`).
    """
    payload = _require_dict(payload or {})
    note = str(payload.get("note") or "").strip()
    if not note:
        _refuse([_field_error("note", errors.VAL_REQUIRED, "rating.discounts.send_back_note")])
    with transaction.atomic():
        discount = _discount_or_404(discount_id)
        version = _the_version(
            discount, discount_models.VERSION_PENDING_APPROVAL, payload.get("version_id")
        )
        other_draft = discount_models.DiscountVersion.objects.filter(
            tenant_id=_tenant_id(), discount=discount, status=discount_models.VERSION_DRAFT
        ).first()
        if other_draft is not None:
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-031",
                message_key="rating.discounts.draft_already_open",
                params={"version_no": other_draft.version_no},
            )
        before = _json_safe(version_row(version))
        version.status = discount_models.VERSION_DRAFT
        version.submitted_by_id = None
        version.submitted_at = None
        version.second_approval_required = False
        version.second_approval_threshold = None
        version.rejection_reason = note
        version.save(
            update_fields=[
                "status",
                "submitted_by",
                "submitted_at",
                "second_approval_required",
                "second_approval_threshold",
                "rejection_reason",
                "updated_at",
            ]
        )
        after = _json_safe(version_row(version))
        after["reason"] = note
        _audit(
            actor,
            "discount.version_sent_back",
            "discount_version",
            version.id,
            before=before,
            after=after,
        )
    return version_row(version)


#: `PATCH /discounts/{id}` on a LIVE discount — the fields the drawing LOCKS
#: (image 27: *"Value and limits · Change with a new value"*; image 28: *"Starts
#: … Change with a new value"*). Each is refused BY NAME with the door that does
#: change it, so the road does not end where the clerk is standing.
LOCKED_ON_LIVE: tuple[str, ...] = (
    "discount_type",
    "value",
    "currency",
    "applies_to",
    "applies_to_service",
    "applies_to_services",
    "applies_to_charge_codes",
    "cap_per_bill",
    "cap_per_year",
    "cap_lifetime",
    "bill_floor_amount",
    "stacking_precedence",
    "stacks_with_others",
    "exclusivity_group",
    "effective_from",
)


@require_role(SYSTEM_ADMIN)
def update_discount_details(actor: Any, discount_id: Any, payload: Any) -> dict[str, Any]:
    """`PATCH /discounts/{id}` — *Name and details*, SAVED ON THIS VERSION.

    The drawing's first Edit choice (images 27–30): *"Name and details · Saved
    on this version"*. Three cases, by the discount's state:
      * **a DRAFT never submitted** — everything edits in place (BR-RAT-1016
        verb 1, `update_discount_version`);
      * **waiting approval** — refused: send it back first, so an approver never
        signs content that moved under them;
      * **LIVE** — the identity (`update_discount`) plus the version's
        non-priced details (who qualifies, enrolment, verification, proof,
        recertification, lapse, the END date, the budget) edit in place on the
        version in force; VALUE, LIMITS and START are refused by name
        (`LOCKED_ON_LIVE`) — those are *New value from a date* or *Fix a
        mistake*.

    ⚠ **THE END DATE IS EDITABLE HERE AND IS CHECKED LIKE A RETIRE**: not before
    today (an issued bill is immutable — hard rule 4), not before the start, and
    not past a later version already approved (two versions on one date). The
    budget edits in place because it is not the discount's VALUE; the
    second-approval requirement stored at submit is left as it was signed.
    """
    payload = _require_dict(payload)
    identity = {key: payload[key] for key in payload if key in DISCOUNT_FIELDS}
    details = {key: payload[key] for key in payload if key not in DISCOUNT_FIELDS}
    sync_needed = "enrolment_mode" in details or "eligibility" in details
    with transaction.atomic():
        discount = _discount_or_404(discount_id)
        today = seams.tenant_today()
        live = (
            discount_models.DiscountVersion.objects.filter(
                tenant_id=_tenant_id(),
                discount=discount,
                status=discount_models.VERSION_ACTIVE,
                effective_from__isnull=False,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
            .order_by("effective_from", "version_no")
            .first()
        )
        if live is None and details:
            pending = discount_models.DiscountVersion.objects.filter(
                tenant_id=_tenant_id(),
                discount=discount,
                status=discount_models.VERSION_PENDING_APPROVAL,
            ).exists()
            if pending:
                raise DiscountRuleError(
                    errors.BIZ_STATE,
                    br_ref="BR-RAT-077",
                    message_key="rating.discounts.waiting_approval_send_back_first",
                )
            draft = _the_version(discount, discount_models.VERSION_DRAFT)
            update_discount_version(actor, draft.id, details)
            details = {}
        if details:
            fe: list[dict[str, Any]] = []
            for field in LOCKED_ON_LIVE:
                if field in details:
                    fe.append(
                        _field_error(
                            field,
                            errors.VAL_FORMAT,
                            "rating.discounts.locked_on_live",
                            new_value_path=f"/discounts/{discount.id}/new-value",
                            correction_path=f"/discounts/{discount.id}/corrections",
                        )
                    )
            _refuse(fe)
            cleaned = _validate_version(details, partial=True)
            cleaned.pop("currency", None)
            cleaned.pop("change_reason", None)
            merged_mode = cleaned.get("enrolment_mode", live.enrolment_mode)
            merged_code = cleaned.get("eligibility_code", live.eligibility_code)
            _refuse_automatic_with_proof(merged_mode, merged_code, fe)
            if "effective_to" in cleaned:
                end = _as_date(cleaned["effective_to"])
                if end is not None:
                    if end < today:
                        fe.append(
                            _field_error(
                                "effective_to", errors.VAL_RANGE, "rating.discounts.retire_in_past"
                            )
                        )
                    if live.effective_from and end < live.effective_from:
                        fe.append(
                            _field_error(
                                "effective_to", errors.VAL_RANGE, "rating.discounts.window_inverted"
                            )
                        )
                later = discount_models.DiscountVersion.objects.filter(
                    tenant_id=_tenant_id(),
                    discount=discount,
                    status=discount_models.VERSION_ACTIVE,
                    effective_from__gt=live.effective_from,
                ).first()
                if later is not None:
                    fe.append(
                        _field_error(
                            "effective_to",
                            errors.VAL_RANGE,
                            "rating.discounts.window_overlaps_version",
                            version_no=later.version_no,
                        )
                    )
            _refuse(fe)
            before = _json_safe(version_row(live))
            for field, value in cleaned.items():
                setattr(live, field, value)
            if cleaned:
                live.save(update_fields=[*cleaned.keys(), "updated_at"])
                live.refresh_from_db()
                after = _json_safe(version_row(live))
                if before != after:
                    _audit(
                        actor,
                        "discount.details_updated",
                        "discount_version",
                        live.id,
                        before=before,
                        after=after,
                    )
        if identity:
            update_discount(actor, discount.id, identity)
        if sync_needed:
            from apps.rating import discount_enrolment_job

            discount_enrolment_job.sync_discount(discount, actor=actor)
    from apps.rating import selectors

    return selectors.discount_detail(discount.id)


@require_role(SYSTEM_ADMIN)
def new_discount_value(actor: Any, discount_id: Any, payload: Any) -> dict[str, Any]:
    """`POST /discounts/{id}/new-value` — *New value from a date* (images 31–33).

    The value moves from `effective_from`; the version in force **ends the day
    before** and keeps every bill before that date (*"Bills before 01/01/2027
    keep 15%."*). One transaction, two rows, the `new_tax_rate` shape
    (`CR-165`).

    **Worked (asserted on PostgreSQL):** SENIOR v1 15% from 08/01/2026, new
    value 12% from 01/01/2027 → v1 ends **12/31/2026** and bills **−$9.00** on a
    **$60.00** bill; v2 bills **−$7.20** from 01/01/2027. Billing gets exactly
    one of them for any date.

    ⚖️ **SAVING IS APPROVING, AND THAT IS OUR JUDGMENT (decision log
    2026-10-03, `CR-166` round 2).** The drawing saves a new value straight to
    *Scheduled* (images 19 and 33 — *"v1 · Gets an end date · v2 · New
    version"*), with no *Waiting approval* in between; ruling 1 makes approval
    the act that puts a version in force. So the person who saves is recorded
    as the submitter AND the approver of v2 (`self_approved`, which the PO
    allowed on 2026-08-19, *"yes allow it"*), and the audit row says so. **The
    one exception keeps BR-RAT-077 whole:** where the utility has switched the
    second-approval threshold ON and v2's budget needs it, v2 lands *Waiting
    approval* instead and v1 is untouched until somebody approves it.

    Refused by name: no version in force today (`new_value_needs_live`); a start
    on or before the live version's own start (image 32,
    `new_value_not_after_start`); a later value already approved
    (`next_value_already_scheduled`); a discount that is retiring before the new
    start (`starts_after_retire`).

    ⚠ **THE NEW VALUE'S OWN END IS THE ONE TYPED (`DEF-RAT-9313`, CR-166 round
    3).** Image 31 draws an *Ends* box for the new value, and until 2026-10-03
    this door stripped `effective_to` from the payload and answered 201 with no
    end stored. Now: a typed end is v2's end — refused when it is before v2's
    start (`window_inverted`) or past a recorded retire date
    (`ends_after_retire`: ruling 4 says nobody gets it after that date). With no
    end typed, v2 keeps the live version's stated end (a retire date) or none.
    *Worked:* 12% from 01/01/2027 to 06/30/2027 → v1 ends 12/31/2026, v2 runs
    01/01/2027–06/30/2027.

    ⚠ **THE LIVE VERSION IS ENDED BEFORE THE OVERLAP CHECK, NOT AFTER IT
    (`DEF-RAT-9314`).** A discount retiring on 12/31/2027 carries that end on its
    live version, so checking v2 (from 01/01/2027) for an overlap before moving
    v1's end refused the save as *"Dates overlap version 1"* — v1 overlapping the
    version that replaces it. Both writes are in this one transaction, so a
    refusal after the trim still writes nothing.
    """
    payload = _require_dict(payload)
    reason = str(payload.get("change_reason") or "").strip()
    changes = {
        key: value
        for key, value in payload.items()
        if key not in ("change_reason", "effective_to")
    }
    fe: list[dict[str, Any]] = []
    start = _as_date(payload.get("effective_from"))
    if start is None:
        fe.append(_field_error("effective_from", errors.VAL_REQUIRED, "rating.required"))
    typed_end = _as_date(payload.get("effective_to")) if payload.get("effective_to") else None
    if typed_end is not None and start is not None and typed_end < start:
        fe.append(
            _field_error("effective_to", errors.VAL_RANGE, "rating.discounts.window_inverted")
        )
    _refuse(fe)
    with transaction.atomic():
        discount = _discount_or_404(discount_id)
        today = seams.tenant_today()
        current = active_version(discount, today)
        if current is None:
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-037",
                message_key="rating.discounts.new_value_needs_live",
            )
        if start <= current.effective_from:
            _refuse(
                [
                    _field_error(
                        "effective_from",
                        errors.VAL_RANGE,
                        "rating.discounts.new_value_not_after_start",
                        current_start=str(current.effective_from),
                    )
                ]
            )
        later = (
            discount_models.DiscountVersion.objects.filter(
                tenant_id=_tenant_id(),
                discount=discount,
                status__in=(
                    discount_models.VERSION_ACTIVE,
                    discount_models.VERSION_PENDING_APPROVAL,
                ),
                effective_from__gt=current.effective_from,
            )
            .exclude(pk=current.pk)
            .first()
        )
        if later is not None:
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1016",
                message_key="rating.discounts.next_value_already_scheduled",
                params={"version_no": later.version_no, "from": str(later.effective_from)},
            )
        if discount.retire_on is not None and start > discount.retire_on:
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-078",
                message_key="rating.discounts.starts_after_retire",
                params={"retire_on": str(discount.retire_on)},
            )
        if (
            typed_end is not None
            and discount.retire_on is not None
            and typed_end > discount.retire_on
        ):
            _refuse(
                [
                    _field_error(
                        "effective_to",
                        errors.VAL_RANGE,
                        "rating.discounts.ends_after_retire",
                        retire_on=str(discount.retire_on),
                    )
                ]
            )
        base = _version_payload_of(current)
        merged = {**base, **changes, "effective_from": str(start)}
        if typed_end is not None:
            merged["effective_to"] = str(typed_end)
        else:
            merged["effective_to"] = (
                str(current.effective_to)
                if current.effective_to is not None and current.effective_to >= start
                else None
            )
        merged["change_reason"] = reason or f"New value from {start:%m/%d/%Y}"
        cleaned = _validate_version(merged, partial=False)
        cleaned["effective_from"] = start
        cleaned["effective_to"] = _as_date(merged["effective_to"])
        required, threshold = second_approval_required(cleaned.get("budget_cap"))
        highest = (
            discount_models.DiscountVersion.objects.filter(discount=discount)
            .order_by("-version_no")
            .values_list("version_no", flat=True)
            .first()
            or 0
        )
        actor_id = _actor_user_id(actor)
        before_current = _json_safe(version_row(current))
        version = discount_models.DiscountVersion.objects.create(
            tenant_id=_tenant_id(),
            discount=discount,
            version_no=highest + 1,
            status=(
                discount_models.VERSION_PENDING_APPROVAL
                if required
                else discount_models.VERSION_ACTIVE
            ),
            submitted_by_id=actor_id,
            submitted_at=Now(),
            approved_by_id=None if required else actor_id,
            approved_at=None if required else Now(),
            self_approved=not required and bool(actor_id),
            second_approval_required=required,
            second_approval_threshold=threshold,
            **cleaned,
        )
        closed = 0
        if not required:
            if current.effective_to is not None and current.effective_to >= start:
                # `_close_open_windows_before` fills NULL ends only; a live
                # version with a stated end past the new start (a retirement
                # recorded later) is ended the day before too, because the two
                # cannot both price that span. ⚠ BEFORE `_put_in_force`, whose
                # overlap check would otherwise see v1 still running to its
                # retire date and refuse the save (`DEF-RAT-9314`).
                current.effective_to = start - timedelta(days=1)
                current.save(update_fields=["effective_to", "updated_at"])
                closed += 1
            closed += _put_in_force(version)
        version.refresh_from_db()
        after = _json_safe(version_row(version))
        after.update(
            {
                "previous_version_no": current.version_no,
                "previous_ends_on": None if required else str(start - timedelta(days=1)),
                "predecessor_windows_closed": closed,
                "saved_as_approved": not required,
            }
        )
        _audit(
            actor,
            "discount.new_value",
            "discount_version",
            version.id,
            before=before_current,
            after=after,
        )
    return version_row(version)


def correct_discount(actor: Any, discount_id: Any, payload: Any) -> dict[str, Any]:
    """`POST /discounts/{id}/corrections {…, reason}` — *Fix a mistake* (images
    34–36): the version in force TODAY (or the one `version_id` names) is
    corrected over the SAME window; the old row is kept, superseded."""
    payload = _require_dict(payload)
    discount = _discount_or_404(discount_id)
    version_id = payload.pop("version_id", None)
    if version_id:
        version = (
            discount_models.DiscountVersion.objects.filter(
                tenant_id=_tenant_id(), discount=discount, pk=version_id
            ).first()
        )
        if version is None:
            raise errors.NotFoundError()
    else:
        version = active_version(discount, seams.tenant_today())
        if version is None:
            raise DiscountRuleError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1016",
                message_key="rating.discounts.correct_not_in_force",
                params={"version_no": None, "status": None},
            )
    return correct_discount_version(actor, version.id, payload)


# ── reads ───────────────────────────────────────────────────────────────────
#: ⚠ EVERY TIMESTAMP BELOW IS THE DATABASE'S CLOCK (`Now()`), NEVER
#: `timezone.now()`. BR-TEN-043 is the event-time law and G6 greps this app for
#: a wall clock by name: an approval, a submission and a funding-exhaustion are
#: all events on a money object, and a Python process clock can disagree with
#: the transaction it is inside — by a leap second, by a container drifting, or
#: by a retry running minutes after the row it stamps. `Now()` is evaluated by
#: Postgres inside the same transaction as the write, so the stamp and the row
#: cannot separate. The cost is one `refresh_from_db` per write, because until
#: it is refreshed the attribute holds the EXPRESSION rather than a datetime —
#: and returning that expression in a row dict is how a serializer explodes.


def _recert_due(from_day: date, version: Any) -> date | None:
    if version is None or not version.recertification_months:
        return None
    months = int(version.recertification_months)
    year = from_day.year + (from_day.month - 1 + months) // 12
    month = (from_day.month - 1 + months) % 12 + 1
    # `monthrange` rather than a hand-written table: an annual recertification
    # verified on 29 Feb must land on 28 Feb, and a table that gets the century
    # leap rule wrong would expire a subsidy a day early once a century.
    return date(year, month, min(from_day.day, monthrange(year, month)[1]))


def _discount_or_404(discount_id: Any) -> Any:
    row = discount_models.Discount.objects.filter(tenant_id=_tenant_id(), pk=discount_id).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def _version_or_404(version_id: Any) -> Any:
    row = (
        discount_models.DiscountVersion.objects.filter(tenant_id=_tenant_id(), pk=version_id)
        .select_related("discount")
        .first()
    )
    if row is None:
        raise errors.NotFoundError()
    return row


def _enrolment_or_404(enrolment_id: Any) -> Any:
    row = (
        discount_models.DiscountEnrolment.objects.filter(tenant_id=_tenant_id(), pk=enrolment_id)
        .select_related("discount")
        .first()
    )
    if row is None:
        raise errors.NotFoundError()
    return row


def active_version(discount: Any, on_day: date | None = None) -> Any:
    """The version in force on `on_day` — exactly one, or None.

    The narrowing R1/R2 perform for plans and schedules, performed for
    discounts: effective window contains the day, status is `active`.

    ⚠ **IT USED TO END `.order_by(…).first()`, AND THAT IS NOT A TIE-BREAK
    (`DEF-RAT-8050`).** The docstring said so in its own words — *"Two rows
    matching would be an ambiguity, and the ORDER BY makes it deterministic
    rather than random while the activation path keeps it from happening"* —
    which is hard-won law 1 twice over: DETERMINISTIC is not CORRECT (the
    order-by picks one of two equally valid rows and reduces a bill by that
    figure), and *"the activation path keeps it from happening"* was a claim
    about `activate_discount_version` that nothing checked and that no writer
    on any other route obeys. `selectors.in_force_version`'s own comment on
    the identical shape one object over: *"That is not a tie-break, it is a
    coin toss on a money path."*

    So it REFUSES, naming both rows. `rating/0049`'s
    `ex_discount_versions_no_overlap` makes the shape unreachable in
    PostgreSQL; this is the same sentence one layer up, and it is the only
    layer that exists on SQLite (hard-won law 14).
    """
    when = on_day or seams.tenant_today()
    in_force = list(
        discount_models.DiscountVersion.objects.filter(
            tenant_id=_tenant_id(),
            discount=discount,
            status=discount_models.VERSION_ACTIVE,
            effective_from__isnull=False,
            effective_from__lte=when,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=when))
        .order_by("-effective_from", "-version_no")[:2]
    )
    if len(in_force) > 1:
        raise DiscountRuleError(
            errors.BIZ_STATE,
            br_ref="BR-RAT-1016",
            message_key="rating.discounts.two_versions_in_force",
            params={
                "on_day": str(when),
                "version_no": in_force[0].version_no,
                "other_version_no": in_force[1].version_no,
            },
        )
    return in_force[0] if in_force else None


def _close_open_windows_before(discount: Any, new_from: date) -> int:
    """Close EVERY older in-force window, not merely the most recent one.

    ⚠ **NOT ONE ROW — THAT IS THE WHOLE POINT, AND IT IS `DEF-RAT-8000`'s
    LESSON CARRIED ACROSS.** `services._close_open_windows_before` replaced a
    one-row close on `tariff_versions` after four versions of one sewer
    schedule ended up in force on one date at a live tenant: a repair that
    closes only the newest predecessor leaves every older open window open for
    ever, so one bad write never heals.

    ⚠ **ON DISCOUNTS THIS CHANGES WHICH ROW PRICES NOTHING AT ALL, AND SAYING
    SO IS THE POINT (hard rule 4).** Supersession on this object is a STATUS
    (`discounts.py`: *"`superseded` is what a later version does to an earlier
    one"*), and `activate_discount_version` already flips every other `active`
    row to `superseded` in the same transaction — so every row this closes was
    about to stop pricing anyway, by status, one statement later. What the
    close adds is that the DATA then says what the status says. Without it a
    superseded row keeps an open `effective_to` for ever, the window model is
    decorative, and `rating/0049`'s constraint would be guarding a column
    nobody maintains.

    ⚠ **IT ONLY EVER FILLS A NULL END, NEVER MOVES A STATED ONE.** Somebody
    typed that date; it is what a grant was reproduced against, and moving it
    changes which version a past service date resolves to. Same rule as
    `rating/0046` pass 1.

    Returns how many rows it closed, so the caller's audit row can say.
    """
    closed = 0
    rows = discount_models.DiscountVersion.objects.filter(
        tenant_id=_tenant_id(),
        discount=discount,
        status=discount_models.VERSION_ACTIVE,
        effective_from__isnull=False,
        effective_from__lt=new_from,
        effective_to__isnull=True,
    )
    for row in rows:
        row.effective_to = new_from - timedelta(days=1)
        row.save(update_fields=["effective_to", "updated_at"])
        closed += 1
    return closed


def discount_ids_carried(account_id: Any, on_day: date) -> set[Any]:
    """The discounts the account's PLAN offers on `on_day` — ruling 2's gate.

    Account → its unit (customers' fact, through the seam) → the unit's plan
    assignment in force that day (rating's own `unit_plan_assignments`) → the
    plan's bindings whose availability window contains the day (BR-RAT-110's
    window, the same one `selectors.billable_discount_rules` reads). An account
    naming no unit, or a unit on no plan that day, is offered nothing.

    ⚠ **THE BINDING WINDOW IS HOW "REMOVED FROM A PLAN" STOPS IT FROM THE NEXT
    BILL** (ruling 2): unbinding now closes the binding the day before instead
    of deleting it (`services._close_dropped_discounts`), so a bill for a
    service date before the removal still finds it and one after does not.
    """
    unit_id = seams.account_unit_id(account_id)
    if unit_id is None:
        return set()
    plan_ids = list(
        rating_models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), unit_id=unit_id, assigned_from__lte=on_day
        )
        .filter(Q(assigned_to__isnull=True) | Q(assigned_to__gte=on_day))
        .values_list("rate_plan_id", flat=True)
    )
    if not plan_ids:
        return set()
    return set(
        discount_models.PlanDiscountRule.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id__in=plan_ids
        )
        .filter(Q(available_from__isnull=True) | Q(available_from__lte=on_day))
        .filter(Q(available_to__isnull=True) | Q(available_to__gte=on_day))
        .values_list("discount_id", flat=True)
    )


def automatic_discount_ids(discount_ids: Iterable[Any], on_day: date) -> set[str]:
    """Of `discount_ids`, the ones whose version in force on `on_day` is
    **Automatic** — granted and ended by `discount_enrolment_job` from the
    account's own facts, never claimed by a person (PO 2026-10-03 ruling (3)).

    `DEF-CUS-9779`: the move-in offered Municipal account, Paperless and Autopay
    as claims; a clerk's pick was enrolled at Complete and the nightly sync
    ended it the next night. The move-in's claim list and its claim refusal
    both read THIS, so the stored `enrolment_mode` decides and no code list
    does. Ids come back as strings; an id with no version in force that day is
    not named (`enrol_account` refuses it on its own terms).

    ⚠ **AMENDED 2026-10-06 (`DEF-RAT-9833`, PO D2 (b) and ruling 4): THE DOORS
    NO LONGER READ THIS ONE.** Autopay and Paperless are Automatic AND
    clerk-addable now, so every person's door reads
    `hand_refused_discount_ids` (this, less `setting_paired_discount_ids`).
    This stays the answer to *"is it Automatic"* — `discount_detail`'s
    `enrolled_automatically` still reads it.
    """
    wanted = [one for one in discount_ids if one]
    if not wanted:
        return set()
    return {
        str(one)
        for one in discount_models.DiscountVersion.objects.filter(
            tenant_id=_tenant_id(),
            discount_id__in=wanted,
            status=discount_models.VERSION_ACTIVE,
            enrolment_mode=discount_models.ENROLMENT_AUTOMATIC,
            effective_from__isnull=False,
            effective_from__lte=on_day,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_day))
        .values_list("discount_id", flat=True)
    }


#: ⚖️ PO rulings D2 (b) and 4, 2026-10-06 (`DEF-RAT-9833`) — the two system
#: checks that MIRROR A SETTING ON THE ACCOUNT. An Automatic discount whose
#: who-qualifies is one of these is still kept by the nightly sync, AND a clerk
#: may add it by hand: the add switches the setting On in the same transaction
#: and switching the setting On enrols at once. *Government or municipal* and
#: *Everyone on the plan* are not here, so Municipal account stays automatic
#: and refused by hand.
SETTING_CHECKS: tuple[str, ...] = (discount_models.CHECK_AUTOPAY, discount_models.CHECK_PAPERLESS)


def setting_paired_discount_ids(discount_ids: Iterable[Any], on_day: date) -> dict[str, str]:
    """Of `discount_ids`, the AUTOMATIC ones whose who-qualifies check mirrors a
    setting on the account — `{discount_id: "autopay" | "paperless"}`.

    ⚖️ PO D2 (b), verbatim: *"Offer Autopay and Paperless at move-in as drawn …
    Clark has to add those discounts. clark can add it later also on account"*;
    ruling 4 (reading (b)): *"when clark make it on or adds it you ahve to set it
    up so that next billing cycle pick it"*. Decided by the STORED check of the
    version in force (`discount_lists.check_key_for`), never by a code, so a
    renamed Paperless still pairs (decision log *"D2 (b) AND RULING 4"* (1)).
    """
    wanted = [one for one in discount_ids if one]
    if not wanted:
        return {}
    rows = (
        discount_models.DiscountVersion.objects.filter(
            tenant_id=_tenant_id(),
            discount_id__in=wanted,
            status=discount_models.VERSION_ACTIVE,
            enrolment_mode=discount_models.ENROLMENT_AUTOMATIC,
            effective_from__isnull=False,
            effective_from__lte=on_day,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_day))
        .values_list("discount_id", "eligibility_code")
    )
    out: dict[str, str] = {}
    for discount_id, code in rows:
        check = discount_lists.check_key_for(code)
        if check in SETTING_CHECKS:
            out[str(discount_id)] = check
    return out


def hand_refused_discount_ids(discount_ids: Iterable[Any], on_day: date) -> set[str]:
    """Of `discount_ids`, the ones NO PERSON may add by hand: Automatic, and not
    paired with a setting (`setting_paired_discount_ids`). Municipal account
    and an *Everyone on the plan* discount are here; Autopay and Paperless are
    not (PO D2 (b), 2026-10-06). The move-in's claim list, the move-in's
    refusal, `claim_assistance` and the Accounts tab's *+ Enroll an account*
    all read THIS."""
    wanted = [one for one in discount_ids if one]
    automatic = automatic_discount_ids(wanted, on_day)
    if not automatic:
        return set()
    return automatic - set(setting_paired_discount_ids(automatic, on_day))


def enrol_for_settings(
    actor: Any, account_id: Any, *, today: date | None = None, source: str = "setting_on"
) -> list[dict[str, Any]]:
    """Enrol ONE account, NOW, in every setting-paired Automatic discount its
    plan carries and whose setting it has On — so the NEXT bill carries it,
    instead of waiting for tonight's sync.

    ⚖️ PO ruling 4, 2026-10-06 (reading (b)), verbatim: *"so when clark make it
    on or adds it you ahve to set it up so that next billing cycle pick it"*.
    Called by customers after it writes `autopay` / `paperless` On (the account
    edit, the portal's email choice, the move-in) and after a clerk's add has
    switched the setting. It ENDS nothing — a setting switched Off ends that
    night, from the next bill (`discount_enrolment_job`, `CR-166` §7 item 7).

    The effective date is the one every door already writes: `enrolled_on` =
    today (`enrol_account`'s default and the sync's `day`). The qualifying test
    is the sync's own (`seams.accounts_meeting`), with an account still
    *pending activation* counted (decision log *"D2 (b) AND RULING 4"* (5)) and
    a closed one not. Idempotent: an account already enrolled is skipped (hard
    rule 6). One audit row per enrolment written (hard rule 7); the actor may be
    None (the portal's customer is not a staff user — `source` names the door).

    HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING — AI-authored 2026-10-06 (lane
    AUTO-PAPERLESS, `DEF-RAT-9833`) under the PO ruling of 2026-08-09; row in
    `12-governance/09-human-review-ledger.md`.
    """
    today = today or seams.tenant_today()
    carried = discount_ids_carried(account_id, today)
    paired = setting_paired_discount_ids(carried, today)
    written: list[dict[str, Any]] = []
    if not paired:
        return written
    from apps.rating import discount_enrolment_job

    for discount in discount_models.Discount.objects.filter(
        tenant_id=_tenant_id(), pk__in=list(paired)
    ).order_by("code"):
        # BR-RAT-078 — a retirement RECORDED blocks new enrolment, as in
        # `enrol_account`; a draft enrols nobody, as in the sync.
        if (
            discount.status in (discount_models.DISCOUNT_RETIRED, discount_models.DISCOUNT_DRAFT)
            or discount.retire_on
        ):
            continue
        version = active_version(discount, today)
        if version is None:
            continue
        units = discount_enrolment_job._units_on_carrying_plans(discount, today)
        meets = seams.accounts_meeting(units, paired[str(discount.id)], include_pending=True)
        if not meets.filter(id=account_id).exists():
            continue
        with transaction.atomic():
            if discount_models.DiscountEnrolment.objects.filter(
                tenant_id=_tenant_id(),
                discount=discount,
                account_id=account_id,
                ended_on__isnull=True,
            ).exists():
                continue
            enrolment = discount_models.DiscountEnrolment.objects.create(
                tenant_id=_tenant_id(),
                discount=discount,
                account_id=account_id,
                enrolled_on=today,
                enrolled_by_id=_actor_user_id(actor) if actor is not None else None,
                verification_status=discount_models.VERIFICATION_NOT_REQUIRED,
                currency=version.currency,
            )
            row = enrolment_row(enrolment)
            _audit(
                actor,
                "discount.account_enrolled",
                "discount_enrolment",
                enrolment.id,
                after=_json_safe({**row, "source": source, "check": paired[str(discount.id)]}),
            )
        written.append(row)
    return written


def budget_remaining(version: Any, on_day: date | None = None) -> Decimal | None:
    """What this programme has LEFT — `budget_cap` minus the grants inside the
    budget period. None when no cap was typed (which part 3 allows and the
    second-approval ruling treats as the largest commitment there is).

    Summed over `discount_grants` rather than decremented from a counter,
    because part 3's Budget-&-usage tab has to say WHICH bills spent the money
    and a counter cannot answer that.
    """
    if version.budget_cap is None:
        return None
    when = on_day or seams.tenant_today()
    grants = discount_models.DiscountGrant.objects.filter(
        tenant_id=_tenant_id(), discount_id=version.discount_id
    )
    # 🔒 DEF-RAT-9366 — each period has an END as well as a start (see
    # `discount_rules_for_account`): a re-priced December must not count
    # January's grants against December's budget.
    if version.budget_period == discount_models.BUDGET_PERIOD_ANNUAL:
        grants = grants.filter(
            period_end__gte=date(when.year, 1, 1), period_end__lt=date(when.year + 1, 1, 1)
        )
    elif version.budget_period == discount_models.BUDGET_PERIOD_MONTHLY:
        first = date(when.year, when.month, 1)
        grants = grants.filter(
            period_end__gte=first, period_end__lte=date(when.year, when.month, monthrange(when.year, when.month)[1])
        )
    spent = _counted(grants).aggregate(total=Sum("amount"))["total"] or ZERO
    return Decimal(version.budget_cap) - Decimal(spent)


#: The batch store key under which `rating.selectors.prime_check_batch` marks
#: an account that holds NO discount enrolment at all (B27).
NO_ENROLMENT = "rating.no_discount_enrolment"


def discount_rules_for_account(
    account_id: Any, on_day: date | None = None
) -> tuple[discount_pricing.DiscountRule, ...]:
    """Every in-force enrolment for one account, as R6's pure arithmetic needs
    it — dates, proof and budget all RESOLVED here so `discount_pricing` has no
    clock and no database.
    """
    when = on_day or seams.tenant_today()
    if batch_reads.get(NO_ENROLMENT, account_id):
        # B27 — the bulk Check batch read every account's enrolments at once and
        # this account has NONE, in any date range: the loop below would find
        # nothing to turn into a rule.
        return ()
    enrolments = (
        discount_models.DiscountEnrolment.objects.filter(
            tenant_id=_tenant_id(), account_id=account_id, enrolled_on__lte=when
        )
        .filter(Q(ended_on__isnull=True) | Q(ended_on__gte=when))
        .select_related("discount")
        .order_by("discount__code")
    )
    rules: list[discount_pricing.DiscountRule] = []
    carried: set[Any] | None = None
    for enrolment in enrolments:
        discount = enrolment.discount
        # ⚖️ RULING 4 / `DEF-RAT-9296` — **A DATE IS DECIDED BY DATES, NEVER BY
        # THE CURRENT STATUS.** This used to skip anything not `active` or
        # `suspended_funding_exhausted`, so retiring a discount TODAY removed it
        # from a re-bill of AUGUST. A dated retire is written onto the version
        # windows (`retire_discount`), which `active_version` below honours by
        # date. Two stored states still exclude, and neither is a date question:
        #   * `draft` — nothing was ever approved, so nothing can price;
        #   * a LEGACY `retired` with no `retire_on` — retired by the old,
        #     dateless act before this commit. Its stop date was never
        #     recorded, so it keeps the old behaviour rather than resuming
        #     discounts nobody has decided to resume (no money moves either way
        #     for those rows; `CR-166` §10 names them).
        if discount.status == discount_models.DISCOUNT_DRAFT:
            continue
        if discount.status == discount_models.DISCOUNT_RETIRED and discount.retire_on is None:
            continue
        # ⚖️ RULING 2 — the plan gate, in the ONE resolver every reader uses,
        # so the enrolled count, the R6 door and the bill agree. Asked once per
        # account, on the service date.
        if carried is None:
            carried = discount_ids_carried(account_id, when)
        if discount.id not in carried:
            continue
        version = active_version(discount, when)
        if version is None:
            continue
        granted = (
            _counted(
                discount_models.DiscountGrant.objects.filter(
                    tenant_id=_tenant_id(), enrolment=enrolment
                )
            ).aggregate(total=Sum("amount"))["total"]
            or ZERO
        )
        # 🔒 DEF-RAT-9366 — THE CAP YEAR IS THE CALENDAR YEAR OF THE SERVICE
        # DATE, and it has an END as well as a start. It read `period_end >=
        # 1 Jan` with no upper bound, which was harmless while nothing wrote a
        # grant (`DEF-2430`) and wrong the day something did: a correction of a
        # December 2026 bill priced in February 2027 would have counted 2027's
        # grants against 2026's cap. A grant counts in the year its bill
        # PERIOD ENDS. Which year a cap means (calendar or the programme's own)
        # is unsigned and is with the PO with this build's worked figures.
        this_year = (
            _counted(
                discount_models.DiscountGrant.objects.filter(
                    tenant_id=_tenant_id(),
                    enrolment=enrolment,
                    period_end__gte=date(when.year, 1, 1),
                    period_end__lt=date(when.year + 1, 1, 1),
                )
            ).aggregate(total=Sum("amount"))["total"]
            or ZERO
        )
        rules.append(
            discount_pricing.DiscountRule(
                code=discount.code,
                discount_type=version.discount_type,
                value=Decimal(version.value),
                currency=version.currency,
                applies_to=version.applies_to,
                verified=(
                    enrolment.verification_status
                    in (
                        discount_models.VERIFICATION_VERIFIED,
                        discount_models.VERIFICATION_NOT_REQUIRED,
                    )
                ),
                proof_before_first_reduction=version.proof_before_first_reduction,
                applies_to_service=(
                    version.applies_to_service.code if version.applies_to_service_id else None
                ),
                # `CR-091-BRC01` — the plural, on its own field. Empty on every
                # scope but `specific_services`.
                applies_to_services=tuple(version.applies_to_services or ()),
                applies_to_charge_codes=tuple(version.applies_to_charge_codes or ()),
                cap_per_bill=version.cap_per_bill,
                cap_year_remaining=(
                    None
                    if version.cap_per_year is None
                    else Decimal(version.cap_per_year) - Decimal(this_year)
                ),
                cap_lifetime_remaining=(
                    None
                    if version.cap_lifetime is None
                    else Decimal(version.cap_lifetime) - Decimal(granted)
                ),
                budget_remaining=budget_remaining(version, when),
                exhaustion_behaviour=version.exhaustion_behaviour,
                bill_floor_amount=Decimal(version.bill_floor_amount),
                stacking_precedence=version.stacking_precedence,
                stacks_with_others=version.stacks_with_others,
                exclusivity_group=version.exclusivity_group,
            )
        )
    return tuple(rules)


def price_account_discounts(
    account_id: Any,
    lines: tuple[discount_pricing.BillLine, ...],
    on_day: date | None = None,
    currency: str = "USD",
) -> discount_pricing.DiscountOutcome:
    """THE DOOR A BILL RUN CALLS. Reads the enrolments, then does the maths.

    Nothing in `apps/billing/` calls it yet — R6 is still an explicitly
    unmodelled step in `apps/rating/resolution.py`, which belongs to the
    EP-RAT-15 lane working this same CR in this same tree. Wiring it is that
    lane's call, and the integration is written out in `discount_pricing`'s
    docstring so it is two lines when they take it.
    """
    return discount_pricing.price_discounts(
        lines=lines, rules=discount_rules_for_account(account_id, on_day), currency=currency
    )


def r6_enrolled_discounts(
    account_id: Any, on_day: date | None = None
) -> tuple[tuple[str, Decimal], ...]:
    """R6's NARROWING answer, in the shape `resolution.DiscountResolution` types.

    ⚠ **THE `Decimal` HERE IS THE DISCOUNT'S CONFIGURED VALUE, NOT A REDUCTION
    IN MONEY**, and the ambiguity is worth stating rather than leaving to a
    reader. `apps/rating/resolution.py` holds *"NO money arithmetic"* by its own
    docstring, and a reduction cannot be computed without the priced bill lines
    that module never sees. So a `('SENIOR', Decimal('15'))` pair here means
    *fifteen percent*, and the money is `price_account_discounts`' answer.
    """
    rules = discount_rules_for_account(account_id, on_day)
    return tuple((rule.code, rule.value) for rule in rules)


def discount_row(discount: Any) -> dict[str, Any]:
    """One DIS-01 landing row. Columns are r10's, in r10's order: Code ·
    Discount · Type · Value · Eligibility · Verification · Plans · Enrolled ·
    Status.

    ⚠ **THIS IS THE SECOND `discount_row` IN THE MODULE AND THE TWO ALREADY
    DISAGREE — `DEF-2803`, filed rather than fixed here.**
    `selectors.discount_row` serves the same DIS-01 row for the READ path and
    carries `value_display`, `version_id`, `version_status` and `version_no`
    that this one does not; this is what a WRITE hands back. Hard-won law 5 is
    *one generated file, committed once*, and two hand-written copies of one
    row shape are the same failure. Reconciling them is a contract change across
    `rating/api.py` and the wizard, which is not this lane's ground.

    **`allowance_unit` IS ADDED TO BOTH IN THE SAME COMMIT** (`BR-RAT-960`),
    precisely because the drift above is what makes a field on one row and not
    the other into a defect nobody sees: the wizard reads this row after a save
    and the landing reads the other, so an allowance would have shown its unit
    on one screen and a bare figure on the next.
    """
    from apps.rating import selectors

    version = (
        discount_models.DiscountVersion.objects.filter(
            tenant_id=_tenant_id(), discount=discount, status=discount_models.VERSION_ACTIVE
        )
        .order_by("-version_no")
        .first()
        or discount_models.DiscountVersion.objects.filter(tenant_id=_tenant_id(), discount=discount)
        .order_by("-version_no")
        .first()
    )
    return {
        "id": str(discount.id),
        "code": discount.code,
        "name": discount.name,
        "status": discount.status,
        "programme_owner": discount.programme_owner,
        "funding_source": discount.funding_source,
        "type": version.discount_type if version else None,
        "value": str(version.value) if version else None,
        # BR-RAT-960 — the unit a usage allowance RESOLVED to, from the service
        # its scope names. `null` for every other type and for a service that
        # states no unit. Served here as well as on the read row so the two
        # screens cannot show the same stored `2` differently.
        "allowance_unit": selectors.discount_allowance_unit(version),
        "value_display": selectors.discount_value_display(
            version.discount_type if version else None,
            version.value if version else None,
            selectors.discount_allowance_unit(version),
            version.currency if version else None,
        ),
        "currency": version.currency if version else None,
        "applies_to": version.applies_to if version else None,
        "eligibility": version.eligibility_summary if version else None,
        "verification": version.verification_method if version else None,
        "plans": discount_models.PlanDiscountRule.objects.filter(
            tenant_id=_tenant_id(), discount=discount
        ).count(),
        "enrolled": discount_models.DiscountEnrolment.objects.filter(
            tenant_id=_tenant_id(), discount=discount, ended_on__isnull=True
        ).count(),
        "effective_from": (
            str(version.effective_from) if version and version.effective_from else None
        ),
    }


def version_row(version: Any) -> dict[str, Any]:
    # ⚠ **IMPORTED HERE, NOT AT MODULE LEVEL, AND THE REASON IS A CYCLE** —
    # `selectors` imports this module. `discount_row` below does the same and
    # says so; both would raise `ImportError` at start-up otherwise.
    from apps.rating import selectors

    return {
        "id": str(version.id),
        "discount": str(version.discount_id),
        "version_no": version.version_no,
        "status": version.status,
        # `BR-RAT-1016` — the correction chain, SERVED, so a screen can draw a
        # superseded row as *corrected* rather than as merely old. Both ends,
        # because the two answer different questions: `corrects` says *this row
        # replaces that one*, `superseded_by` says *stop reading me, read that*.
        "corrects": str(version.corrects_id) if version.corrects_id else None,
        "superseded_by": str(version.superseded_by_id) if version.superseded_by_id else None,
        "correction_reason": version.correction_reason,
        "type": version.discount_type,
        "value": str(version.value),
        # ⚠ **THE STRING A SCREEN PRINTS — `BR-RAT-087` / `DEF-364`, and
        # `DEF-RAT-5817` is why it is on THIS row too.** The Audit tab draws a
        # `Value` column, and `value` above is the stored magnitude at six
        # decimals (hard rule 2). A client that formatted it would be doing
        # money arithmetic the server owns, and would print `15.000000` or a
        # rounded-in-JavaScript `15.00` depending on who wrote the cell. The
        # same resolution the list row and the plan tab already use, so one
        # figure cannot read two ways on two screens — including the
        # allowance's unit (`BR-RAT-960`: `2` is `2.00 kgal` on water and
        # `2.00 kWh` on electric, which is how a clerk NOTICES a discount
        # attached to the wrong service).
        "value_display": selectors.discount_value_display(
            version.discount_type,
            version.value,
            selectors.discount_allowance_unit(version),
            version.currency,
        ),
        "currency": version.currency,
        "applies_to": version.applies_to,
        # `CR-091-BRC01` — served as a LIST, always, the way a tax serves its
        # own (`selectors.py:828`). A null column reads as `[]` rather than as
        # `null`, so a caller never has to handle two shapes of "no services".
        "applies_to_services": list(version.applies_to_services or []),
        "budget_cap": str(version.budget_cap) if version.budget_cap is not None else None,
        "second_approval_required": version.second_approval_required,
        "second_approval_threshold": (
            str(version.second_approval_threshold)
            if version.second_approval_threshold is not None
            else None
        ),
        "self_approved": version.self_approved,
        "effective_from": str(version.effective_from) if version.effective_from else None,
        # `CR-166-BRC10` r3 t6 (§9 "Fields added") — the details page's
        # versions table reads *08/01/2026 – 12/31/2026* (image 19). A READ
        # field only: nothing prices from this row. Null = no end.
        "effective_to": str(version.effective_to) if version.effective_to else None,
        "change_reason": version.change_reason,
    }


def enrolment_row(enrolment: Any) -> dict[str, Any]:
    return {
        "id": str(enrolment.id),
        "discount": enrolment.discount.code,
        "account": str(enrolment.account_id),
        "enrolled_on": str(enrolment.enrolled_on),
        "ended_on": str(enrolment.ended_on) if enrolment.ended_on else None,
        "end_reason": enrolment.end_reason,
        "verification_status": enrolment.verification_status,
        "recertification_due_on": (
            str(enrolment.recertification_due_on) if enrolment.recertification_due_on else None
        ),
        "lifetime_subsidy_amount": str(enrolment.lifetime_subsidy_amount),
        "currency": enrolment.currency,
    }


def discount_count() -> int:
    """Counted out of the DATABASE, for the report that says how many there
    are. CR-010's lesson, and the PO's own instruction of 2026-08-19 about the
    stale `31 priced objects` figure: *"we have increase this number check out
    seed data"*."""
    return discount_models.Discount.objects.filter(tenant_id=_tenant_id()).count()


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 part 3 of 5 VERBATIM (12-governance/11-change-requests.md) + parts 4/5 for the tax base and plan-composition rules + 08-cr013-design.md §A7/§A8/§A9 + 07-r10-plans-rates-readout.md §4 + the PO rulings of 2026-08-19 (decision log — a plan may not override a discount's value; a submitter may approve their own filing; the second-approval threshold is a tenant setting defaulting to $10,000 measured against the discount's own budget cap, no budget always requiring it) + CLAUDE.md hard rules 1/2/4/6/7
# generated: 2026-08-19 by the CR-013 EP-RAT-12 lane (discounts — writes, reads and the R6 door)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — DIS-01/DIS-02 endpoints are a separate story) E=deferred(no-frontend-half — the landing, the detail view and the wizard are explicitly out of this slice) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒, HUMAN-REVIEW-PENDING, ledger row appended)
# gates: ruff✔ black✔ py_compile✔ · pytest tests/test_cr013_discounts.py 47 passed✔ · G6 forbidden PASS — ⚠ this file FAILED G6 first (`discount_services.py:879: wall-clock time in a money path`) and the fix is `Now()` (the database clock, evaluated inside the write's own transaction) with a refresh_from_db, not a suppression · G7 human-owned PASS (HUMAN-OWNED + HUMAN-REVIEW-PENDING markers, ledger row, enrolled in human_owned.txt) · golden-verify 33 PASS/0 FAIL✔
# exceptions: eligibility is ADVISORY — `eligibility_rule` is stored and nothing evaluates it (BR-RAT-043's posture); automatic eligibility evaluation is EP-RAT-12's remainder · R6 is NOT wired into `resolution.resolve_discounts` or into `apps/billing` by this lane — both belong to other lanes working this same CR in this same tree; `price_account_discounts` and `r6_enrolled_discounts` are the doors and the integration is written out in discount_pricing's docstring · the impact figures §A7.6 asks be stored at SUBMIT are NOT stored (EP-RAT-16's approval slice); `second_approval_required` and `second_approval_threshold` ARE, because the PO ruled them · `apps/tenancy/settings_families.py` gains ONE Param for the threshold — declared in the family that owns the S71 page rather than copied into a rating constant
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
