# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-002 (payment purpose: bill · deposit · plan-down · prepay —
#           money with no open bill)   Screens: S22 · S33 · S35
# Rules:    BR-PAY-012 (every payment carries a purpose; unapplied → account
#           credit; deposit-purpose satisfies the first-bill deposit line at
#           issue; plan-down links to its plan) · BR-PAY-010 (allocation order
#           — a prepay that meets open bills meets them in the ratified order) ·
#           BR-CUS-043 (one LIVE plan per account) · BR-TEN-013 (a module never
#           touches another module's ORM; a cross-module read resolves the
#           owner's published callable) · BR-BIL-012 (the first bill carries the
#           deposit line — this story only SATISFIES it) · CLAUDE.md rule 1
#           (tenant scoping) · rule 2 (money NUMERIC(18,6), never float)
# Tests:    06-backend/tests/test_us_pay_002_purpose.py
# Impacts:  apps/payments/services.record_payment (its only caller — the
#           `_purpose` gate that refused three of the four values) ·
#           apps/payments/ledger_seam.post_payment_cleared (the deposit leg) ·
#           apps/payments/credit.py (a prepay's remainder is US-PAY-007's
#           carried credit) · apps/payments/models.Payment.plan (migration 0009)
# ───────────────────────────────────────────────────────
"""What each of BR-PAY-012's four purposes MEANS for the money.

BR-PAY-012, CONFIRMED 2026-08-08: *"Every payment carries a **purpose**: bill |
deposit | plan-down | prepay; unapplied → account credit; deposit-purpose
satisfies the first-bill deposit line at issue; plan-down links to its plan."*

Until this file existed, `services.record_payment` accepted `bill` and REFUSED
the other three by name, each for a linkage that did not exist. Two of those
three reasons are now stale and the third is half stale, and saying so is the
point of this docstring (hard-won law 1):

  * **plan_down** was refused because *"`payment_plans` is EP-PAY-05's table and
    does not exist"*. It exists (migration 0007) and so does its service. What
    was still missing was the COLUMN — field-map **P-12** — and migration 0009
    adds `payments.plan_id`.
  * **prepay** was refused because *"US-PAY-007 owns the credit's lifecycle and
    the read-model that makes it visible; neither exists"*. Both exist now
    (`selectors.account_credit_position` since the NSF lane, `credit.py` with
    this one).
  * **deposit** was refused because the first-bill satisfaction did not exist.
    **That half is still true** and this file does not pretend otherwise — see
    THE DEPOSIT HALF below.

════════════════════════════════════════════════════════════════════════════
WHAT EACH PURPOSE DOES TO THE MONEY
════════════════════════════════════════════════════════════════════════════
    bill        meets open bills in the ratified order (BR-PAY-010); anything
                no bill can absorb carries as account credit.
    prepay      IDENTICAL TREATMENT, and that is BR-PAY-010 applied rather than
                a decision taken here. US-PAY-002 TC-4 is a prepay on an account
                with ZERO open bills, and oldest-first over an empty list
                carries the whole $200.00 as credit with no special case. What
                a prepay does when bills ARE open is not ruled anywhere, so the
                DEFAULT rule governs it (*"DEFAULT oldest-invoice-first"*)
                rather than an invented "prepay never touches a bill" — and a
                clerk who means the other thing has BR-PAY-001's `carry_credit`
                instruction, which the form already offers.
    plan_down   meets the ARREARS the plan spreads, in the same ratified order,
                AND links to the plan. Both halves matter: PE-13's plan totals
                267.30 with 50.00 down and instalments summing to 217.30, so the
                down payment must reduce the debt by 50.00 or the customer pays
                267.30 in instalments against a 217.30 schedule.
    deposit     meets NO bill and becomes NO credit. US-PAY-002 TC-1 is explicit:
                *"no allocation to any invoice; account credit NOT created — the
                money is held against the deposit line"*. It is a LIABILITY the
                utility owes back, not a payment on account, and the ledger says
                the same thing from its own side (`deposit_liability`, one of the
                twelve ruled designations).

`selectors.account_credit_position` excludes deposit-purpose payments for
exactly that reason, and a test asserts it: a $150.00 deposit that read as
$150.00 of credit would auto-apply to the next bill and the utility would have
spent money it is holding for the customer.

════════════════════════════════════════════════════════════════════════════
THE DEPOSIT HALF — WHAT IS BUILT, AND THE ONE THING THAT IS NOT
════════════════════════════════════════════════════════════════════════════
BUILT: the payment is recorded against the account's deposit position, posts
`DR undeposited funds / CR deposit liability` (the signed contract row *"Cash
deposit taken (payment purpose=deposit) | cash | deposit liability"*, corrected
to undeposited per BR-PAY-039 — see `ledger_seam`), and is published to billing
through `deposit_payments_for_account` so the first bill's deposit line can be
satisfied at issue.

NOT BUILT, and it is billing's: **nothing calls that read.** BR-BIL-012's
first-bill deposit line is US-BIL-010's, `apps/billing` belongs to another lane,
and this module may not reach into its issue path. So US-PAY-002 TC-2 — *"the
deposit-purpose payment satisfies the deposit line at issue"* — is served on
this side and unwired on the other. REPORTED in the lane report with the exact
one-line ask, never implied to be done.

**AND THE REQUIREMENT READ DOES NOT EXIST.** TC-5 wants a deposit-purpose
payment REFUSED on *"an account with no deposit position"*. The only figure any
module publishes is `accounts.deposit_on_file` — what is ALREADY HELD — which is
0.00 on precisely the pre-move-in account TC-1 describes, so testing against it
would refuse the story's own worked case. What decides the question is the rate
plan's deposit RULE (`plan_deposit_rules`, BR-RAT-020/023), and
`apps.rating.selectors` publishes no per-account read of it. This module names
that contract (`DEPOSIT_REQUIREMENT_READ`), resolves it AT CALL TIME, and:

  * when rating publishes it → a zero requirement REFUSES, which is TC-5;
  * while it does not → the payment is recorded and the result carries
    `deposit_requirement_not_checked`.

That is the `refunds.cross_account_arrears_not_checked` posture, and it is the
G20 rule: an unwired seam REPORTS that it cannot answer. It never answers 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from importlib import import_module
from typing import Any

from apps.payments import models
from apps.payments.collections_models import LIVE_PLAN_STATUSES, PaymentPlan
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")

#: The customers read this module needs to see an account's deposit position,
#: named once so the contract is greppable from BOTH sides of the boundary — the
#: posture `refunds.CROSS_ACCOUNT_ARREARS_READ` and
#: `billing/final_bill.DEPOSIT_INTEREST_READ` both take.
#:
#:     apps.customers.selectors.account_detail(account_id) -> dict
#:
#: carrying `deposit_on_file` and `deposit_received_on` (B2 + r9 #5).
DEPOSIT_POSITION_READ = "account_detail"

#: The rating read that would let TC-5's refusal be real. NOT PUBLISHED — see
#: the module docstring.
#:
#:     apps.rating.selectors.deposit_requirement_for_account(account_id) -> Decimal
#:
#: The fixed deposit `plan_deposit_rules` states for this account's rate plan ×
#: account type (BR-RAT-020/023). Zero when the plan requires none.
DEPOSIT_REQUIREMENT_READ = "deposit_requirement_for_account"

#: Carried on the result of every deposit-purpose recording while the read above
#: is unpublished. A code, not a sentence, because the API layer surfaces it and
#: the S22 form renders it (BR-SHL-025).
DEPOSIT_REQUIREMENT_UNCHECKED = "deposit_requirement_not_checked"
#: Carried on every deposit-purpose recording, full stop: the satisfaction half
#: is billing's and nothing calls it yet.
DEPOSIT_LINE_NOT_SATISFIED = "first_bill_deposit_line_not_satisfied"


@dataclass(frozen=True)
class PurposeLinkage:
    """What one purpose resolved to, before a single row is written.

    Frozen and computed BEFORE the payment row exists, so a linkage that cannot
    be made refuses at the door rather than leaving an orphan purpose behind —
    US-PAY-002 TC-5's own requirement (*"no orphan purpose links"*).

    `allocates` is whether this money meets open bills at all. `credits_account`
    is whether an unapplied remainder becomes the carried credit US-PAY-007
    owns. A deposit is the only purpose for which both are False — the money is
    held, and held money is neither applied nor credited.
    """

    purpose: str
    plan: Any = None
    allocates: bool = True
    credits_account: bool = True
    is_deposit: bool = False
    problems: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _as_decimal(value: Any) -> Decimal:
    """A money figure from another module's wire format, never a float.

    Hard rule 2: a `float()` here would put money into binary at the boundary,
    which is the one place nobody looks for it.
    """
    if isinstance(value, Decimal):
        return value
    if value is None:
        return ZERO
    return Decimal(str(value))


# ── the deposit position (customers-owned; payments reads, never computes) ───


def deposit_position(account_id: Any) -> dict[str, Any]:
    """What the utility already HOLDS for this account, as customers reports it.

    REFUSES when customers publishes no `account_detail`: an unreadable deposit
    position is not a zero one, and recording a deposit against a position that
    could not be read would put money in a liability nothing can reconcile.
    """
    read = _resolve("customers", DEPOSIT_POSITION_READ)
    if read is None:
        raise PaymentRuleError(
            f"apps.customers.selectors.{DEPOSIT_POSITION_READ} is not published, so this "
            "account's deposit position cannot be read. A deposit-purpose payment is money the "
            "utility HOLDS FOR the customer (BR-PAY-012), and holding it against a position "
            "nothing can see is worse than refusing it at the counter. Nothing was written.",
            br_ref="BR-PAY-012",
        )
    row = dict(read(account_id))
    return {
        "on_file": _as_decimal(row.get("deposit_on_file")),
        "received_on": row.get("deposit_received_on"),
    }


def deposit_requirement(account_id: Any) -> Decimal | None:
    """What the account's rate plan REQUIRES as a deposit — or None, honestly.

    None means *nobody can answer this today*, and it is not the same fact as
    0.00. See the module docstring: the caller carries
    `deposit_requirement_not_checked` on its result rather than treating the
    absence as "no deposit required", which would refuse TC-1's own $150.00.
    """
    read = _resolve("rating", DEPOSIT_REQUIREMENT_READ)
    if read is None:
        return None
    return _as_decimal(read(account_id))


# ── the plan link (US-PAY-002 TC-3 / BR-PAY-012) ────────────────────────────


def live_plan_or_refuse(account_id: Any, *, plan_id: Any = None) -> PaymentPlan:
    """The plan a down payment attaches to (BR-CUS-043: exactly one is live).

    `plan_id` is optional because the S24 wizard knows which plan it just
    proposed and the S22 counter form does not — and BR-CUS-043's one-live-plan
    invariant means the account is enough to find it. A named plan that is not
    this account's, or not live, REFUSES: US-PAY-002 TC-5 requires a *named
    linkage error*, and TC-6 requires that a Brazos Bend plan id is invisible to
    Lone Star Ridge (the queryset is tenant-scoped and RLS FORCE is the second,
    independent guarantee).
    """
    live = PaymentPlan.objects.filter(account_id=account_id, status__in=LIVE_PLAN_STATUSES)
    if plan_id is not None:
        plan = live.filter(pk=plan_id).first()
        if plan is None:
            raise PaymentRuleError(
                f"plan {plan_id!r} is not a live payment plan on this account, so a down payment "
                "has nothing to attach to (BR-PAY-012: *plan-down links to its plan*). A live "
                f"plan is one in {list(LIVE_PLAN_STATUSES)}. Nothing was written.",
                br_ref="BR-PAY-012",
            )
        return plan
    plan = live.first()
    if plan is None:
        raise PaymentRuleError(
            "this account has no live payment plan, so a payment with purpose 'plan_down' has "
            "nothing to attach to (BR-PAY-012). Record it with purpose 'bill' if it is an "
            "ordinary payment, or propose the plan first (US-PAY-017). Nothing was written.",
            br_ref="BR-PAY-012",
        )
    return plan


# ── the one entry point ─────────────────────────────────────────────────────


def resolve(account_id: Any, purpose: str, *, plan_id: Any = None) -> PurposeLinkage:
    """BR-PAY-012's four values, each resolved to what it does to the money.

    Called by `services.record_payment` BEFORE the payment row is created, so
    every refusal below happens with nothing written — which is what makes
    US-PAY-002 TC-5's *"no orphan purpose links"* true rather than tidy.
    """
    if purpose not in models.PAYMENT_PURPOSES:
        raise PaymentRuleError(
            f"{purpose!r} is not one of the payment purposes BR-PAY-012 defines "
            f"({list(models.PAYMENT_PURPOSES)}). Nothing here invents a fifth.",
            br_ref="BR-PAY-012",
        )

    if purpose == models.PURPOSE_BILL:
        return PurposeLinkage(purpose=purpose)

    if purpose == models.PURPOSE_PREPAY:
        # BR-PAY-010's DEFAULT, applied — see the module docstring. Nothing
        # special happens here and that is the finding, not an omission.
        return PurposeLinkage(purpose=purpose)

    if purpose == models.PURPOSE_PLAN_DOWN:
        plan = live_plan_or_refuse(account_id, plan_id=plan_id)
        return PurposeLinkage(purpose=purpose, plan=plan)

    # ── deposit ─────────────────────────────────────────────────────────────
    position = deposit_position(account_id)
    problems: list[dict[str, Any]] = [
        {
            "code": DEPOSIT_LINE_NOT_SATISFIED,
            "br_ref": "BR-BIL-012",
            "detail": "this deposit is held against the account's deposit position and posts to "
            "the deposit LIABILITY, and `apps.payments.credit.deposit_payments_for_account` "
            "publishes it for billing to draw on. Nothing calls that read: satisfying the first "
            "bill's deposit line at issue is US-BIL-010's write in `apps/billing`, and this "
            "module may not make it. The money is recorded and visible; the line it will settle "
            "is not settled yet.",
        }
    ]
    requirement = deposit_requirement(account_id)
    if requirement is None:
        problems.append(
            {
                "code": DEPOSIT_REQUIREMENT_UNCHECKED,
                "br_ref": "BR-RAT-020",
                "detail": f"apps.rating.selectors.{DEPOSIT_REQUIREMENT_READ} is not published, so "
                "whether this account's rate plan requires a deposit at all could not be checked. "
                f"The account holds {position['on_file']} on file today, which is a different "
                "fact — a pre-move-in account holds nothing and is exactly the case US-PAY-002 "
                "TC-1 describes. The deposit is recorded; the requirement is UNCHECKED, and this "
                "code says so rather than reporting that none exists.",
            }
        )
    elif requirement <= ZERO:
        raise PaymentRuleError(
            "this account's rate plan requires no deposit, so there is no deposit position for "
            "the money to be held against (BR-PAY-012 / BR-RAT-020). Record it with purpose "
            "'prepay' if the customer is paying ahead, or 'bill' if it is a payment. Nothing "
            "was written.",
            br_ref="BR-PAY-012",
        )

    return PurposeLinkage(
        purpose=purpose,
        allocates=False,
        credits_account=False,
        is_deposit=True,
        problems=tuple(problems),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-002@3c9f5a1 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-01-record-payments.md US-PAY-002 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-012/010 · 04-docs/05-modules/08-payments/03-field-map.md §1 + P-12 · 04-docs/05-modules/08-payments/07-pre-session-model.md PE-6/PE-13 · 08-qa/01-e2e/journeys/J2-read-to-cash.md)
# generated: 2026-08-15 by story-coder (payments visible-half lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_002_purpose.py (the plan-link refusal and the deposit's exclusion from the credit position were each driven RED first — verbatim transcripts in the lane report) · pytest tests -m isolation✔
# exceptions: (1) TC-2 IS SERVED ON ONE SIDE ONLY. `credit.deposit_payments_for_account` publishes the figure billing needs to satisfy BR-BIL-012's first-bill deposit line; `apps/billing` belongs to another lane and nothing calls it. REPORTED with the exact ask — not implied to be wired (hard-won law 2)
#         (2) TC-5's deposit half CANNOT REFUSE TODAY. The rate plan's deposit RULE is what decides whether a deposit position exists and `apps.rating.selectors` publishes no per-account read of it; `accounts.deposit_on_file` is what is ALREADY HELD and is 0.00 on TC-1's own pre-move-in account. The contract is named, resolved at call time, and refuses a ZERO requirement the day rating publishes it; until then every deposit recording carries `deposit_requirement_not_checked`. An unwired seam REPORTS — it never answers 0 (G20)
#         (3) PREPAY GETS NO SPECIAL CASE and the docstring says why: TC-4 is a prepay against zero open bills, which BR-PAY-010's default already handles; what a prepay does when bills ARE open is unruled, so the DEFAULT rule governs rather than an invented one. A clerk who means "do not touch the bills" has BR-PAY-001's `carry_credit`
#         (4) `plan_id` is OPTIONAL: BR-CUS-043's one-live-plan invariant makes the account sufficient, and the S22 counter form does not know a plan id
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
