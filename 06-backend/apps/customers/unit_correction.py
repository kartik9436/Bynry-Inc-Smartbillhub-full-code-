# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 — `BR-CUS-1047` BUILT (PO ruling 2026-09-12, option
#           (a) on `OQ-CUS-1769`). The ruling reached four documents and no
#           line of code; this is the line of code.
# Rules:    BR-CUS-1047 · BR-CUS-017 (NARROWED, not replaced) · BR-CUS-020 ·
#           BR-MET-040 · BR-SHL-025 · OQ-042's closure (*"supervisor =
#           SysAdmin/Executive"*) · A4 `adjustment_approval` (BR-IDN-014) ·
#           hard rule 4 (issued bills) · hard rule 7 (audit).
# Question: OQ-CUS-12355 — the REQUEST half. Not built; see §WHO APPROVES.
# Tests:    06-backend/tests/test_br_cus_1047_unit_correction.py
# Impacts:  POST /accounts/{id}/correct-unit · services.REFUSED_FIELDS
#           (`unit_id`'s reason now points HERE instead of saying "never") ·
#           07-frontend account Overview (`ACC-E07`).
# ───────────────────────────────────────────────────────
"""RE-POINT AN ACCOUNT AT ANOTHER UNIT — AS A CORRECTION, AND ONLY AS ONE.

WHAT A CLERK COULD NOT DO UNTIL THIS FILE EXISTED
─────────────────────────────────────────────────────────────────────────────
An account opened against the wrong unit had **no way back**. `BR-CUS-017` made
the unit create-only, so the only fix was to close the account and open another
— losing its whole history, its number, its notes and its payment record, to
correct a typo. The Product Owner raised it in their own words: *"from the edit
perspective, I cannot see the unit edit where I want to change unit a to unit
b."*

⚠ **THIS IS NOT A MOVE, AND THE DISTINCTION IS THE WHOLE RULE.**
`BR-CUS-017` exists because **a move-in takes the OUTGOING account's unit**: the
bills, the meters and the reads belong to the unit and must not follow a person.
A customer who has genuinely moved still leaves by **move-out** and arrives by
**move-in**, and this door will not serve them — every reason in
`CORRECTION_REASONS` describes a RECORD that was wrong, never a PERSON who went
somewhere. The screen says which is which in the product's own words.

THE FOUR CONDITIONS, QUOTED RATHER THAN SUMMARISED
─────────────────────────────────────────────────────────────────────────────
PO 2026-09-12, verbatim: ***"(a) Narrow the rule to allow exactly this
correction: a reason from a fixed list, a supervisor's approval, effective
today, never backdated, issued bills untouched."***

**1 · A REASON FROM A FIXED LIST.** `CORRECTION_REASONS`, three values, CHECK-
constrained in the database. Not a tenant lookup: the ruling says *fixed*, and a
list a tenant may extend is not fixed. The three are DERIVED and not invented —
they are the three doors in this product that write `accounts.unit_id`
(`create_account`, `create_from_import`, `move_in`), which are the three ways a
record can come to name the wrong unit.

**2 · A SUPERVISOR'S APPROVAL.** See §WHO APPROVES below — it is the one clause
that needed a judgment, and the judgment is recorded rather than assumed.

**3 · EFFECTIVE TODAY, NEVER BACKDATED.** `effective_on` is the server's own
date. **A payload naming it is refused BY NAME**, because a date a clerk may
type is a date a clerk may backdate, and a refusal that only the UI enforces is
not enforcement (`_eligible_unit`'s own docstring makes the same point about a
picker that hides a row). The date is real work and not decoration: the old
unit's service agreements END on it and the new unit's BEGIN on it, so the
account's service history has no gap and no overlap.

**4 · ISSUED BILLS UNTOUCHED.** Hard rule 4. **Nothing in this module reaches
`invoices` and nothing here tries to.** A bill issued against Suite 1 stays a
bill issued against Suite 1 — it was posted, it was sent, and a bill that was
wrong is credited and replaced through billing's own correction flow. The
absence is proved rather than asserted: the test reads every invoice row of the
account before and after and compares them field by field.

WHO APPROVES, AND WHY THIS IS A JUDGMENT AND NOT A GUESS
─────────────────────────────────────────────────────────────────────────────
The ruling says *"a supervisor's approval"* and this product has no role called
supervisor. **It has, however, already been asked who counts as one, and the
Product Owner has already answered — twice, in two independent places, with the
same answer.** Law 13 forbids re-asking what is ruled.

  * **`OQ-042`'s closure**, verbatim: *"optional toggle default ON; **supervisor
    = SysAdmin/Executive**; blocks when enabled (PO R6)"*. That is the PO naming
    the qualifying roles inside the three-role model, and
    `metering.services.cosign_read_batch` has been built on it since CR-038 W7:
    `@require_role(SYSTEM_ADMIN, EXECUTIVE)`, with a billing clerk refused.
  * **A4's signed permission grid** (`identity.models.A4_MATRIX`, transcribed
    verbatim under `BR-IDN-014`), row `adjustment_approval` — *"Adjustment /
    write-off approval"*: **System Admin `Approve` · Executive `Approve` ·
    Billing Clerk `Request`**. The product's signed vocabulary for *approval* is
    those two roles, and only those two.

So `@require_role(SYSTEM_ADMIN, EXECUTIVE)` is not a lane's pick; it is the only
reading both sources support. A **billing clerk is refused**, and that refusal
is the ruling working rather than a limitation — a correction a clerk can give
themselves is not an approval, which is the sentence
`test_w7__a_billing_clerk_cannot_cosign` already makes about the co-sign.

⚠ **WHAT IS *NOT* BUILT, AND IT IS A REAL HALF OF A REAL QUESTION —
`OQ-CUS-12355`.** A4 gives a Billing Clerk `Request` on that same row, so the
signed grid does contemplate *clerk raises it, supervisor approves it* as two
acts by two people. **Nothing in this product implements a request that waits
for an approval** — not on adjustments (`ACTION_UNAVAILABLE["adjust"]` says the
write path is absent), not anywhere. Building the pending row, the queue, the
notification and the supervisor's inbox would be resolving an open decision by
picking a value, which the prime directive forbids.

**So the boundary is drawn here rather than stubbed:** a supervisor performs the
correction and their performance IS the approval, recorded on the row. A clerk
gets `AuthError` with `BR-CUS-1047` named, and the screen shows the control
disabled with that reason (`BR-SHL-025`) instead of hiding it. That is a true
product behaviour a clerk can act on — *ask a supervisor* — and not a
`NotImplementedError` standing where a feature should be. `OQ-CUS-12355` asks
the PO whether the clerk should instead be able to raise one.

WHAT MOVES WITH THE ACCOUNT AND WHAT STAYS BEHIND
─────────────────────────────────────────────────────────────────────────────
The ruling's own worked case (`ACC-E07`, blueprint p185) settles all of it:
`A-11812 · Bramble Bakery`, `Suite 1 · U-000417` → `Suite 2 · U-000418`.

  * **The service agreements MOVE** — old ones end today, new ones start today.
    They are the first link of `accounts → service_agreements(service_point) →
    service_points(unit, service, route, cycle) → units(rate_plan)`, so moving
    them is what actually re-points the plan, the meters, the route and the
    cycle. Nothing is copied; every one of those is reached, never stored.
  * **The plan changes because the UNIT's does** — `SCW-RES v1 → SCM-COM v2`,
    base `$20.00 → $63.00` a month, `$43.00` more. There is no plan column on
    an account to write (PO 2026-08-11: *"from unit you will derive the
    plan"*), so this file writes none.
  * **The reading history STAYS with Suite 1.** Reads belong to meters and
    meters belong to the unit. This module does not own them and does not touch
    them.
  * **The five issued bills STAY.** Condition 4.
  * **The ADDRESS does not move** — hard rule 8. Both suites are in the same
    building, and even when they are not, an account walks `unit → premises` for
    where it is. No address is read, written or copied here.

WHAT `BR-CUS-017` STILL ENFORCES, UNCHANGED
─────────────────────────────────────────────────────────────────────────────
Still **one account ↔ one unit**. Still **at most ONE active account per unit** —
the target unit is locked and checked under the lock, exactly as a create is, so
a correction cannot park an account on an occupied unit. Still **never
premises-attached**. The rule is narrowed, not reversed, and this file is the
narrow part.
"""

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.customers import models
from apps.customers.unit_correction_models import CORRECTION_REASONS, AccountUnitCorrection
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.permissions import EXECUTIVE, SYSTEM_ADMIN, require_role

#: The only keys this door accepts. `effective_on` is ABSENT on purpose and is
#: refused BY NAME below — condition 3 is *never backdated*, and a date in the
#: body is a second, disagreeing source of truth for a fact the server owns.
CORRECTION_FIELDS: frozenset[str] = frozenset({"unit_id", "reason_code"})

#: Keys a caller might reasonably send that this door refuses WITH ITS REASON
#: rather than as *"unknown field"*. Each names a real concept; telling a caller
#: it does not exist would hide the real answer (`_reject_unknown`'s own rule).
CORRECTION_REFUSED: dict[str, tuple[str, str]] = {
    "effective_on": (
        "BR-CUS-1047",
        "a correction takes effect TODAY and is never backdated — the server "
        "supplies the date and no caller may name one",
    ),
    "effective_date": (
        "BR-CUS-1047",
        "a correction takes effect TODAY and is never backdated — the server "
        "supplies the date and no caller may name one",
    ),
    "reason": (
        "BR-CUS-1047",
        "the reason comes from a FIXED LIST — send `reason_code`, one of "
        "CORRECTION_REASONS; free text is not a reason this path accepts",
    ),
    "approved_by": (
        "BR-CUS-1047",
        "the approver is the signed-in supervisor making the call, never a name "
        "in the body — an approval a caller can address to somebody else is not "
        "an approval",
    ),
}


def _fe(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _payload(changes: Any) -> dict[str, Any]:
    if changes is None:
        return {}
    if isinstance(changes, dict):
        return dict(changes)
    return dict(getattr(changes, "data", {}) or {})


def _validate(payload: dict[str, Any]) -> tuple[Any, str]:
    """Every key allowed, refused-with-a-reason, or unknown — the same three
    answers `_reject_unknown` gives on every other account door."""
    fe: list[dict[str, Any]] = []
    for field in payload:
        if field in CORRECTION_FIELDS:
            continue
        if field in CORRECTION_REFUSED:
            br_ref, reason = CORRECTION_REFUSED[field]
            fe.append(
                _fe(
                    field,
                    errors.VAL_FORMAT,
                    "customers.account.field_not_writable",
                    br_ref=br_ref,
                    reason=reason,
                )
            )
        else:
            fe.append(_fe(field, errors.VAL_FORMAT, "customers.account.unknown_field"))

    unit_id = payload.get("unit_id")
    if unit_id in (None, ""):
        fe.append(_fe("unit_id", errors.VAL_REQUIRED, "customers.account.unit_required"))

    reason_code = str(payload.get("reason_code") or "").strip()
    if not reason_code:
        fe.append(
            _fe(
                "reason_code",
                errors.VAL_REQUIRED,
                "customers.account.correction_reason_required",
                br_ref="BR-CUS-1047",
            )
        )
    elif reason_code not in CORRECTION_REASONS:
        # ⚠ The allowed values ride in `params` rather than being retyped into a
        # catalogue, for the reason `REFUSED_FIELDS` gives about its own
        # reasons: a second copy of a vocabulary is a second thing to drift.
        fe.append(
            _fe(
                "reason_code",
                errors.VAL_UNKNOWN_LOOKUP,
                "customers.account.correction_reason_unknown",
                br_ref="BR-CUS-1047",
                value=reason_code,
                allowed=list(CORRECTION_REASONS),
            )
        )

    if fe:
        # The same raise shape `services._refuse_fields` uses — the FIRST error
        # is the envelope's code and message, the whole list rides in
        # `field_errors`, so a form can mark every bad field at once.
        raise errors.ValidationError(
            fe[0]["code"],
            message_key=fe[0]["message_key"],
            params=fe[0]["params"],
            field_errors=fe,
        )
    return unit_id, reason_code


@require_role(SYSTEM_ADMIN, EXECUTIVE, br_ref="BR-CUS-1047")
def correct_account_unit(actor: Any, account_id: Any, payload: Any = None) -> dict[str, Any]:
    """POST /accounts/{id}/correct-unit — `BR-CUS-1047`.

    ONE transaction. Audited (hard rule 7). Issued bills are not read, not
    written and not reachable from here (hard rule 4)."""
    from apps.customers import selectors, services

    data = _payload(payload)
    new_unit_id, reason_code = _validate(data)
    warnings: list[dict[str, Any]] = []

    with transaction.atomic():
        account = selectors.account_or_404(account_id, lock=True)
        before = selectors.account_detail_dict(account)
        old_unit_id = account.unit_id

        # ⚠ **A MASTER ACCOUNT IS NOT SERVED HERE AND THE REFUSAL IS BY NAME.**
        # `BR-CUS-1010`/`BR-CUS-1012`: a master account's anchor unit is
        # DERIVED from the premises' common-area units and it may attach many;
        # re-pointing one at a single unit would silently unmake that
        # derivation. `BR-CUS-1047` is about a REGULAR account whose record
        # named the wrong unit, and the worked case is one.
        if account.kind != services.ACCOUNT_KIND_REGULAR:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-1010",
                message_key="customers.account.correction_not_for_master",
                params={"kind": account.kind},
            )

        # An account with no unit has nothing to correct FROM — `BR-CUS-1012`
        # lets an owner account hold none. Refused by name rather than crashing
        # on a NULL foreign key two statements later.
        if old_unit_id is None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-1047",
                message_key="customers.account.correction_has_no_unit",
            )

        new_unit = services._eligible_unit(new_unit_id, [])
        if new_unit is None:  # pragma: no cover — `_validate` already required it
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-020",
                message_key="customers.account.unit_not_eligible",
                params={"unit_id": str(new_unit_id)},
            )
        if str(new_unit.id) == str(old_unit_id):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-1047",
                message_key="customers.account.correction_same_unit",
                params={"unit_id": str(old_unit_id)},
            )

        # ⚠ **BR-CUS-017's SURVIVING HALF, ENFORCED THE WAY A CREATE ENFORCES
        # IT.** Lock the (tenant, unit) scope FIRST, then read under the lock —
        # a check before the lock is the check-then-act race `T5-15` step 4
        # describes, and a correction racing a move-in for the same unit is
        # exactly that race with two different doors.
        services.lock_unit_scope(new_unit.id)
        services._refuse_if_unit_occupied(new_unit.id, exclude_id=account.id)

        # BR-MET-040 — a plan is required where an account is ACTIVE. A draft
        # may sit on a plan-less unit (BR-CUS-018 derives no occupancy), so the
        # guard is asked only of an occupying account, exactly as
        # `_occupancy_guards` asks it.
        occupying = services.is_occupying(account.status)
        if occupying:
            services._require_plan_on_unit(new_unit)

        effective_on = timezone.localdate()
        approved_at = timezone.now()

        # ── the service history: close there, open here, both TODAY ──────────
        # This is what actually re-points the plan, the meters, the route and
        # the cycle — none of which has a column on the account (BR-CUS-029).
        ended = models.ServiceAgreement.objects.filter(
            tenant_id=account.tenant_id, account=account, ended_on__isnull=True
        ).update(ended_on=effective_on, updated_at=approved_at)

        account.unit = new_unit
        account.save(update_fields=["unit", "updated_at"])

        # ⚠ **THE NEW LINKS ARE OPENED ONLY WHERE THERE WERE LINKS TO MOVE, AND
        # THE FIRST DRAFT OF THIS GOT IT WRONG.** `_open_service_agreements` was
        # called unconditionally, which is correct for an account that HAD
        # services and wrong for one that never did: `BR-CUS-018`'s draft
        # derives no occupancy, so `create_account` deliberately writes it NO
        # agreements at all (`_open_account`'s `elif inherit_services:` — only
        # the import door asks for them). A correction that handed a draft the
        # links a draft is not supposed to have would leave it in a state no
        # create can produce, and `activate_account` would then find them
        # already there.
        #
        # So the correction MIRRORS what the account already is. A draft is
        # re-pointed and stays link-less; it inherits from the CORRECT unit when
        # something activates it, which is `_make_occupying`'s job and not this
        # function's. Caught by `TC-6c` asserting `agreements_ended > 0` on an
        # account that had none — the test was written against the ruling's
        # worked case, where five bills exist and services certainly do.
        opened: list[Any] = []
        if ended:
            opened = services._open_service_agreements(account, effective_on)
            if not opened:
                # Honest rather than silent: the new unit has no service points,
                # so the account reaches no service from it and its old links
                # are already closed. The correction still stands — the record
                # is now right — and the caller is TOLD, the same way
                # `_make_occupying` reports what it could not do rather than
                # leaving a clerk to discover it.
                warnings.append(
                    {
                        "code": "no_service_points_on_new_unit",
                        "br_ref": "BR-CUS-029",
                        "unit_id": str(new_unit.id),
                    }
                )

        correction = AccountUnitCorrection.objects.create(
            tenant_id=account.tenant_id,
            account=account,
            from_unit_id=old_unit_id,
            to_unit_id=new_unit.id,
            reason_code=reason_code,
            effective_on=effective_on,
            approved_by_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            approved_at=approved_at,
        )

        after = selectors.account_detail_dict(account)
        core_audit.write_row(
            action="account.unit_corrected",
            entity_type="account",
            entity_id=account.id,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            before=before,
            after={
                **after,
                "correction": {
                    "id": str(correction.id),
                    "from_unit_id": str(old_unit_id),
                    "to_unit_id": str(new_unit.id),
                    "reason_code": reason_code,
                    "effective_on": effective_on.isoformat(),
                    "agreements_ended": ended,
                    "agreements_opened": len(opened),
                },
            },
        )

    return {
        **after,
        "correction": correction_dict(correction),
        "agreements_ended": ended,
        "agreements_opened": len(opened),
        "warnings": warnings,
    }


def correction_dict(row: AccountUnitCorrection) -> dict[str, Any]:
    """One correction, as the Overview's history renders it.

    ⚠ **NO DATABASE ID IS THE VISIBLE VALUE OF A FIELD** (B14 rule 31) — the
    ids here address rows, and the screen shows the unit LABELS it resolves
    from them."""
    return {
        "id": str(row.id),
        "from_unit_id": str(row.from_unit_id),
        "to_unit_id": str(row.to_unit_id),
        "reason_code": row.reason_code,
        "effective_on": row.effective_on.isoformat(),
        "approved_by": str(row.approved_by_id),
        "approved_at": row.approved_at.isoformat(),
    }


def corrections_for(account_id: Any) -> list[dict[str, Any]]:
    """Newest first. Tenant-scoped like every read in this product — the RLS
    policy is the enforcement and this filter is the query."""
    rows = AccountUnitCorrection.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), account_id=account_id
    ).order_by("-effective_on", "-created_at", "-id")
    return [correction_dict(row) for row in rows]


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-CUS-1047 (PO ruling 2026-09-12, option (a) on OQ-CUS-1769) ·
#         BR-CUS-017 · OQ-042 closure · A4 / BR-IDN-014
# generated: 2026-09-13 — the ruling's first arrival in code
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
