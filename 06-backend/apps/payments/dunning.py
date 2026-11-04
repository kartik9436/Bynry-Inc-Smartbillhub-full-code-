# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-019 (dunning + disconnect PAUSE while a plan is active and
#           current; resume when it stops being either)   Screens: S21 · S34
# Rules:    BR-CUS-043 (while active AND current, dunning and disconnect pause;
#           late-fee suspension is a per-plan ELECTION) · BR-PAY-016 (⚠ its
#           "2nd miss voids, dunning resumes" clause is SUPERSEDED — PO
#           2026-08-11 "nodrop we chase for payments until write off") ·
#           BR-PAY-017 (the resumed ladder is the tenant-config sequence; no
#           tier is invented here) · BR-PAY-021 (on-time-ness is judged on the
#           POSTING date) · BR-BIL-073 (a plan does NOT suspend the current
#           bill — PO 2026-08-11, OQ-138) · BR-TEN-043 (event time is an
#           argument) · CLAUDE.md rule 7
# Tests:    06-backend/tests/test_us_pay_019_dunning_pause.py
# Impacts:  apps/payments/notices.py (asks this before every send) ·
#           apps/payments/plans.py · apps/customers/payment_plan.py (the
#           `plan_pauses_current_bill` rule, resolved BY NAME and never copied)
# ───────────────────────────────────────────────────────
"""What a payment plan does and does not stop — the two rulings, joined.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this gate decides whether a disconnect
notice goes to a customer. AI-authored 2026-08-11 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
TWO PO RULINGS OF 2026-08-11 MEET HERE, AND THEIR JOIN IS THE WHOLE FILE
════════════════════════════════════════════════════════════════════════════
**(1) A PLAN DOES NOT SUSPEND THE CURRENT BILL** (OQ-138 → BR-BIL-073). Verbatim:
*"no there is monthly charges that thye have to pay nad it is due every month"*.
Worked, on the frozen PE-13 plan: the instalment is $36.22 and October's bill is
$184.20, so the customer owes **$220.42** in October — not $36.22.

**(2) NOBODY IS DROPPED OFF A PLAN** (OQ-141). Verbatim: *"nodrop we chase for
payments until write off"*. There is no void, no `defaulted` state and no miss
counter anywhere in this module.

BR-CUS-043 pauses dunning *"while active AND current"*, and ruling (1) is what
fixes what **current** means. A customer paying only the instalment is **NOT
current on the account** — they are current on the *plan* and behind on the
month. So the pause has a SCOPE and it is not the account:

    PAUSED    the collection ladder over the ARREARS this plan spreads —
              the debt the customer agreed a schedule for.
    NOT PAUSED the CURRENT month's bill, which is chased like anybody else's.

That is the reading `apps/customers/payment_plan.py` already records on the
other side of the seam (*"The pause covers the ARREARS the plan is spreading …
and the current month's bill is chased like anybody else's"*), and it is the
defect DEF-061 closed: treating the plan as satisfying the account let a
customer stop paying current bills for six months with nothing chasing them.

════════════════════════════════════════════════════════════════════════════
A MISSED INSTALMENT LIFTS THE PAUSE. IT DOES NOT END THE PLAN.
════════════════════════════════════════════════════════════════════════════
Those are two different consequences and only the second one was superseded.

BR-CUS-043 is CONFIRMED and untouched: the pause is granted *while active AND
current*. An instalment that came and went unpaid means the plan is not current,
so the condition the pause rests on has stopped being true and the ladder
resumes over the arrears. The plan itself stays **active** — for the tenth miss
as for the first — because "nodrop" superseded the DROP-OFF, not the word
"current".

⚠ **US-PAY-019 TC-3 expects the opposite** (*"One miss (below threshold) → pause
holds"*), and it says why in its own text: *below threshold*. That threshold was
BR-PAY-016's two-miss void, which no longer exists, so the test case is written
against a rule the product no longer has. This build follows BR-CUS-043's own
words and **OQ-170** asks the PO the question the missing threshold leaves open:
does a missed instalment lift the pause at once, or is there a grace period
first? Nothing here invents a grace of N days — a number nobody ruled would be
the difference between a disconnect notice going out and not.

════════════════════════════════════════════════════════════════════════════
WHAT ENDS A PLAN OTHER THAN PAYMENT — A WRITE-OFF (PO 2026-08-12, OQ-171)
════════════════════════════════════════════════════════════════════════════
US-PAY-019's own title says *"resume on void/close"* and there is still no
VOID: the miss-driven one is superseded and nobody is dropped. What ends a plan
other than paying it off is a **write-off**, and the PO's ruling is as much
about who decides as about what happens — *"these are user business decision,
they will make a decision, we have to provide a mechanism and report it"*.

So `close_plan_on_write_off` is a mechanism a person invokes. Nothing calls it
automatically, nothing here counts missed instalments toward it, and that
absence is the rule. Before it existed a plan could never close, and BR-CUS-043
allows one live plan per account — so an account whose arrears the utility had
already given up on was locked out of ever agreeing another plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from importlib import import_module
from typing import Any

from django.db import IntegrityError, transaction

from core import audit
from core import tenancy as core_tenancy

from apps.payments import plans
from apps.payments.collections_models import (
    LIVE_PLAN_STATUSES,
    PLAN_ACTIVE,
    PLAN_AGREEMENT_SENT,
    PLAN_CLOSED,
    PLAN_PROPOSED,
    PaymentPlan,
)
from apps.payments.exceptions import PaymentRuleError

#: The customers-side rule, resolved BY NAME rather than copied — the seam
#: idiom `apps/billing/rating_seam.py` and `apps/notifications/services.py` both
#: use. If that lane's module is ever absent the answer defaults to the SAME
#: value the rule states (False: a plan does not pause the current bill), so the
#: fallback is the ruling rather than a guess in the other direction.
CUSTOMERS_PLAN_RULE_MODULE = "customers"
CUSTOMERS_PLAN_RULE_ATTR = "plan_pauses_current_bill"

PAUSE_NO_PLAN = "no_live_plan"
PAUSE_PLAN_NOT_ACTIVE = "plan_not_yet_active"
PAUSE_PLAN_BEHIND = "plan_not_current"
PAUSE_ACTIVE_AND_CURRENT = "plan_active_and_current"


@dataclass(frozen=True)
class PauseDecision:
    """Whether the ladder runs for this account, and over WHAT.

    `covers` and `not_covered` are on the result rather than in a comment
    because the whole defect this closes was a scope people believed rather than
    read. A caller that renders "Payment plan · Active" beside a paused ladder
    must be able to say, on the same screen, that this month's bill is still
    due.
    """

    paused: bool
    reason: str
    plan_id: str | None
    covers: str
    not_covered: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "paused": self.paused,
            "reason": self.reason,
            "plan_id": self.plan_id,
            "covers": self.covers,
            "not_covered": self.not_covered,
            "detail": self.detail,
        }


def plan_pauses_current_bill() -> bool:
    """**False** — PO 2026-08-11, OQ-138. Resolved from the customers rule."""
    try:
        module = import_module(f"apps.{CUSTOMERS_PLAN_RULE_MODULE}.payment_plan")
    except ImportError:  # pragma: no cover - defensive
        return False
    rule = getattr(module, CUSTOMERS_PLAN_RULE_ATTR, None)
    return bool(rule()) if callable(rule) else False


def plan_is_current(plan: PaymentPlan, *, as_of: date) -> bool:
    """Every instalment due by `as_of` was met by its due date (BR-PAY-021).

    `as_of` is an argument and never a clock (BR-TEN-043): a pause evaluated at
    preview and at send must judge the same plan against the same day, and a
    function that read the system date would answer differently in a test than
    in the batch it is testing.

    ⚠ **NOTHING CALLS THIS ON THE PAUSE PATH ANY MORE, AND THAT IS SAID HERE
    RATHER THAN LEFT TO BE DISCOVERED (`CR-138-BRC07` `P4.2`).**
    `collections_pause_for` used to ask it and then ask
    `outstanding_installments` a SECOND time for the number to put in the
    refusal; it now asks once and reads the length, and the batched form reads
    a `COUNT` in SQL. **It is kept because it is the one-line English statement
    of BR-PAY-021's *current*** — *"every instalment due by `as_of` was met by
    its due date"* — and deleting it would leave that rule stated only as a
    `filter(...).annotate(Count(...))`.

    **It is not dead, because it is WIRED INTO THE GUARD:**
    `tests/test_cr138_p42_ladder_statement_count.py` asserts that this
    predicate and `plans.outstanding_installment_counts` agree on the same
    plan, so the English form and the SQL form cannot drift. A function nobody
    calls and nobody checks is hard-won law 2's dead code; a function nobody
    calls and a test checks is a specification.
    """
    return not plans.outstanding_installments(plan, as_of=as_of)


def _pause_decision(plan: Any, *, missed: int) -> PauseDecision:
    """THE rule, written once — `collections_pause_for` and its plural share it.

    ⚠ **IT IS A PURE FUNCTION OF (plan, missed) AND TAKES NO QUERY**, which is
    what makes a batched form possible at all (`CR-138-BRC07` `P4.2`). Before
    that task the decision and its two reads were one function, so the only way
    to ask it about 40,000 accounts was to ask it 40,000 times. Splitting the
    reads off the rule keeps ONE statement of the rule — a second copy in a
    bulk path is how a preview and a send come to disagree about who is paused.
    """
    current_bill_note = (
        "the CURRENT month's bill — a plan does not suspend it (PO 2026-08-11, "
        "BR-BIL-073), so this month's charges are chased like anybody else's"
    )
    if plan is None:
        return PauseDecision(
            paused=False,
            reason=PAUSE_NO_PLAN,
            plan_id=None,
            covers="nothing",
            not_covered="everything the account owes",
            detail="this account has no live payment plan, so the ladder runs normally.",
        )
    if plan.status != PLAN_ACTIVE:
        return PauseDecision(
            paused=False,
            reason=PAUSE_PLAN_NOT_ACTIVE,
            plan_id=str(plan.pk),
            covers="nothing yet",
            not_covered="everything the account owes",
            detail=f"the plan is {plan.status!r}: it activates on the customer's "
            "signature and pauses nothing before that (BR-CUS-044). A plan that paused "
            "dunning before it was signed would stop chasing a debt nobody agreed to.",
        )
    if missed:
        return PauseDecision(
            paused=False,
            reason=PAUSE_PLAN_BEHIND,
            plan_id=str(plan.pk),
            covers="nothing",
            not_covered="everything the account owes",
            detail=(
                f"the plan is ACTIVE and stays active — nobody is dropped off a plan (PO "
                f"2026-08-11) — but {missed} instalment(s) due by their due date were not "
                "met, so it is not CURRENT and BR-CUS-043's pause does "
                "not apply. The ladder resumes over the arrears; the plan is not ended, "
                "voided or defaulted, and the customer is chased until write-off. "
                "Whether a grace period should come first is OQ-170."
            ),
        )
    return PauseDecision(
        paused=True,
        reason=PAUSE_ACTIVE_AND_CURRENT,
        plan_id=str(plan.pk),
        covers="the arrears this plan spreads",
        not_covered=current_bill_note,
        detail="the plan is active and current, so the collection ladder and disconnect "
        "steps pause over the debt it spreads (BR-CUS-043). This month's bill is not "
        "part of that debt and is chased normally.",
    )


def collections_pause_for(account_id: Any, *, as_of: date) -> PauseDecision:
    """Does the collection ladder run for this account today, and over what?

    Consumed by `notices.py` before every send and by US-PAY-014's engine
    (unbuilt) through the same call. The decision is COMPUTED every time and
    never read from a stored flag: a pause cached on a row is a pause that
    outlives its reason.

    ⚠ **A LIST CALLS `collections_pause_for_many` INSTEAD.** This is the
    singular and it costs one query — two when the account has a plan. The
    collections board called it once per debtor until `CR-138-BRC07` `P4.2`:
    **12,395 statements and 14.503 s at 2,046 debtors, 244,195 statements and
    285.572 s at 40,046**, measured on real PostgreSQL 16.
    """
    plan = plans.live_plan_for(account_id)
    missed = 0 if plan is None else len(plans.outstanding_installments(plan, as_of=as_of))
    return _pause_decision(plan, missed=missed)


def collections_pause_for_many(
    account_ids: Any, *, as_of: date
) -> dict[Any, PauseDecision]:
    """The plural of `collections_pause_for` — **TWO queries for a whole list.**

    ⛔ **THE N+1 `CLAUDE.md` DOES NOT NAME** (`CR-138-BRC07` `P4.2`).
    `collections_read.ladder_board` asked the singular once per debtor, and the
    singular asks twice for an account on a plan. Measured on real PostgreSQL
    16: **2,046 debtors cost 12,395 statements and 14.503 s; 40,046 debtors
    cost 244,195 statements and 285.572 s** — four and three quarter minutes
    to draw one screen, over a worker that is given sixty seconds. The board
    now makes **20 statements at either size.**

    ⚠ **IT IS THE SAME RULE, NOT A SECOND ONE.** Both forms call
    `_pause_decision`, which takes no query and cannot drift; what is batched
    is the two READS. A test asserts the two agree on the same account, which
    is the only thing that stops them separating.

    ⚠ **THE PLAN CHOSEN PER ACCOUNT IS THE SINGULAR'S CHOICE.**
    `live_plan_for` orders `-created_at` and takes the first, so this orders
    the same way and keeps the first per account. A batched read that ordered
    differently would quietly pause a different plan's account, which no
    statement count can see (`primary_contact_names_for`'s own warning, in
    another module, about exactly this).
    """
    ids = list(account_ids or [])
    if not ids:
        return {}
    live: dict[Any, Any] = {}
    for plan in (
        PaymentPlan.objects.filter(
            tenant_id=_tenant_id(), account_id__in=ids, status__in=LIVE_PLAN_STATUSES
        )
        .order_by("-created_at")
    ):
        live.setdefault(plan.account_id, plan)
    missed_by_plan = plans.outstanding_installment_counts(
        [plan.pk for plan in live.values()], as_of=as_of
    )
    return {
        account_id: _pause_decision(
            live.get(account_id),
            missed=missed_by_plan.get(getattr(live.get(account_id), "pk", None), 0),
        )
        for account_id in ids
    }


def disconnect_blocked(account_id: Any, *, as_of: date) -> tuple[bool, str]:
    """US-PAY-019 TC-6 — the server-side gate, whatever the UI shows.

    Two conditions, and they are not the same: BR-CUS-043 blocks disconnect
    while a plan is active AND current, and the plan's own `suspend_disconnect`
    ELECTION can decline the block. The election is per plan, defaulting ON
    (the prototype's S24 default), and a plan whose election is OFF does not
    block — that is the customer choosing a plan without a disconnect hold, not
    a bug.
    """
    decision = collections_pause_for(account_id, as_of=as_of)
    if not decision.paused:
        return False, decision.detail
    plan = plans.live_plan_for(account_id)
    if plan is not None and not plan.suspend_disconnect:
        return False, (
            "this plan was agreed WITHOUT a disconnect hold (`suspend_disconnect` is a "
            "per-plan election, BR-CUS-043), so disconnect steps continue even while the "
            "plan is current."
        )
    return True, (
        "disconnect is blocked while this payment plan is active and current "
        "(BR-CUS-043). The block is server-side: a forced send through the API is "
        "refused whatever the screen offers."
    )


def late_fee_suspended_for(account_id: Any, *, as_of: date) -> bool:
    """BR-CUS-043 — late-fee suspension is a PER-PLAN ELECTION, not a rule.

    US-PAY-019 TC-2: election ON → billing's late-fee candidates exclude the
    account while it is current; election OFF → late fees continue. The fee
    ITSELF is billing's (BR-BIL-001 and its $25.00 balance floor as amended on
    2026-08-11) and is not restated here — this answers only whether the account
    is a candidate.
    """
    decision = collections_pause_for(account_id, as_of=as_of)
    if not decision.paused:
        return False
    plan = plans.live_plan_for(account_id)
    return bool(plan and plan.suspend_late_fees)


def _tenant_id() -> Any:
    """The current tenant, or refuse. Hard rule 1 — no tenant table is touched
    without `app.tenant_id` set, and a missing context is an auth failure rather
    than a silent all-tenant query."""
    from core import errors

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


@transaction.atomic
def close_plan_on_write_off(
    *, actor: Any = None, plan_id: Any, written_off_on: date, reason: str | None = None
) -> dict[str, Any]:
    """**A WRITE-OFF CLOSES THE PLAN** — PO 2026-08-12, OQ-171 CLOSED.

    Verbatim: *"Write-off closes - these are user business decision, they will
    make a decision, we have to provide a mechanism and report it"*.

    **THE PRODUCT NEVER DECIDES TO WRITE ANYTHING OFF.** That is a human's call
    about a real customer's debt, and this function is the mechanism they use
    once they have made it — never a rule that fires on its own. Nothing here
    watches a plan's age, counts missed instalments, or closes anything by
    itself; there is no automatic path into this function and its absence is the
    rule (PO 2026-08-11: *"nodrop we chase for payments until write off"*).

    **WHY IT MATTERS THAT A PLAN CAN CLOSE AT ALL.** BR-CUS-043 allows exactly
    one live plan per account. A plan that could never end therefore blocked
    that customer from ever agreeing another one — so an account whose arrears
    the utility had already given up on was locked out of the very arrangement
    that might have helped it next time. Worked: ACC-1310 agrees a **$267.30**
    plan, pays the **$50.00** down payment and nothing else; eighteen months on
    nobody has dropped them and the utility writes the arrears off. The plan
    closes here, and the account can take a new plan tomorrow.

    The plan closes the SAME WAY a paid-off plan closes — `closed`, with its
    date and an audit row — because the books distinguish the two by the
    write-off entry, not by inventing a fifth plan state (there are four, and
    `defaulted`/`void` are absent on purpose).
    """
    tenant_id = _tenant_id()
    plan = PaymentPlan.objects.select_for_update().filter(tenant_id=tenant_id, pk=plan_id).first()
    if plan is None:
        raise PaymentRuleError(
            f"payment plan {plan_id} was not found for this tenant, so nothing was closed.",
            br_ref="BR-CUS-043",
        )
    if plan.status == PLAN_CLOSED:
        # Idempotent by nature: a second write-off click closes nothing twice.
        return {"id": str(plan.pk), "status": plan.status, "created": False}

    plan.status = PLAN_CLOSED
    plan.closed_on = written_off_on
    plan.save(update_fields=["status", "closed_on", "updated_at"])
    audit.money_action(
        actor,
        "payment_plan.closed_on_write_off",
        "payment_plans",
        str(plan.pk),
        after={
            "status": PLAN_CLOSED,
            "closed_on": written_off_on.isoformat(),
            "closed_because": "arrears_written_off",
            "reason": reason,
            # Recorded on the money action so a year-old trail says WHY this
            # plan ended, which "closed" alone cannot distinguish from paid.
            "decided_by": "a person — the product never writes off on its own",
        },
    )
    return {"id": str(plan.pk), "status": PLAN_CLOSED, "created": True}


def _status_before_the_write_off(plan: PaymentPlan) -> str:
    """Which live status a written-off plan held, from its own date columns.

    **No column records it, and none is added — the three dates already do.**
    BR-CUS-044: *"activation is the CUSTOMER's e-signature ALONE"*, so
    `signed_on` IS the activation fact; `agreement_sent_on` is the step before
    it and `proposed_on` is always set. Reading them back is a reconstruction of
    a fact the row already holds, not a guess.

    ⚠ **THIS IS THE SENTENCE THAT MATTERS.** Reopening every plan to `active`
    would activate a schedule the customer never signed — a proposal the utility
    wrote off before it was agreed would come back as an agreement the customer
    is held to, with its late-fee suspension and its disconnect pause live. That
    is money-visible and it is silent, so the pre-closure status is
    reconstructed rather than assumed.
    """
    if plan.signed_on is not None:
        return PLAN_ACTIVE
    if plan.agreement_sent_on is not None:
        return PLAN_AGREEMENT_SENT
    return PLAN_PROPOSED


@transaction.atomic
def reopen_plan_on_write_off_reversal(
    *, actor: Any = None, plan_id: Any, reversed_on: date, reason: str | None = None
) -> dict[str, Any]:
    """The other half of `close_plan_on_write_off` — CR-059 CS-25.

    CS-25's *"⚠ WATCH FOR"*, verbatim and the reason it is ONE change and not
    two: *"A reversal **must reopen the payment plan the approval closed**, or
    the customer is left with a debt and no schedule."*

    Worked: ACC-1310 agrees a **$267.30** plan (GT-47 — $50.00 down, then
    5 × $36.22 + $36.20), the utility writes the arrears off and the approval
    closes the plan; the write-off is then found to have been raised on the
    wrong account and is reversed. Without this the customer owes **$217.30**
    again with no schedule to pay it on, and BR-CUS-043's one-live-plan index
    means the clerk cannot simply agree the same plan twice — they would have to
    build a second one, on figures that would not match the letter the customer
    signed.

    **It reopens to the status the plan actually held**, reconstructed above —
    never blanket-`active`.

    ════════════════════════════════════════════════════════════════════════
    THE ONE CASE IT REFUSES, AND IT REPORTS RATHER THAN RAISING
    ════════════════════════════════════════════════════════════════════════
    BR-CUS-043 allows **one live plan per account**, held by
    `uq_one_live_plan_per_account` in the database. If the account agreed a NEW
    plan after the write-off closed the old one, reopening would be a second
    live plan for one debt — *"the loser gives one debt two schedules with no
    rule for which the customer signed"*, in that constraint's own words. So the
    newer plan stands and this one does not reopen, and the caller is told BY
    NAME. The customer is not left without a schedule in that case; they are on
    the newer one.

    ⚠ **CLAUDE.md LAW 14 — THE SAVEPOINT IS THE ONLY OPTION, NOT THE TIDY ONE.**
    The `select` above cannot lock a row that does not exist yet, so a plan
    agreed in a parallel transaction can still lose the race to the unique
    index. On PostgreSQL a failed statement ABORTS THE WHOLE TRANSACTION — the
    write-off reversal, its ledger mirror and its audit row would all be lost at
    COMMIT — so the save runs inside a nested `atomic()` (a SAVEPOINT) and the
    refusal is reported. **The developer suite is in-memory SQLite, which has no
    aborted-transaction state, so this shape is not what the suite proves; it is
    what PostgreSQL requires.** Do not "simplify" it away.
    """
    tenant_id = _tenant_id()
    plan = PaymentPlan.objects.select_for_update().filter(tenant_id=tenant_id, pk=plan_id).first()
    if plan is None:
        raise PaymentRuleError(
            f"payment plan {plan_id} was not found for this tenant, so nothing was reopened.",
            br_ref="BR-CUS-043",
        )
    if plan.status != PLAN_CLOSED:
        # Idempotent by nature, and the same posture `close_plan_on_write_off`
        # takes: a second reversal click reopens nothing twice.
        return {"id": str(plan.pk), "status": plan.status, "created": False}

    live = (
        PaymentPlan.objects.filter(
            tenant_id=tenant_id, account_id=plan.account_id, status__in=LIVE_PLAN_STATUSES
        )
        .exclude(pk=plan.pk)
        .first()
    )
    if live is not None:
        return {
            "id": str(plan.pk),
            "status": plan.status,
            "created": False,
            "blocked_by_plan_id": str(live.pk),
        }

    restored = _status_before_the_write_off(plan)
    plan.status = restored
    plan.closed_on = None
    try:
        with transaction.atomic():  # SAVEPOINT — law 14, see the docstring
            plan.save(update_fields=["status", "closed_on", "updated_at"])
    except IntegrityError:
        # `uq_one_live_plan_per_account` — a plan was agreed between the read
        # above and this write. The newer one stands.
        return {
            "id": str(plan.pk),
            "status": PLAN_CLOSED,
            "created": False,
            "blocked_by_plan_id": None,
        }
    audit.money_action(
        actor,
        "payment_plan.reopened_on_write_off_reversal",
        "payment_plans",
        str(plan.pk),
        after={
            "status": restored,
            "reopened_on": reversed_on.isoformat(),
            "reopened_because": "write_off_reversed",
            "reason": reason,
            # The status is RECONSTRUCTED, so the trail says from what. A year
            # later "why is this plan `proposed` again" has an answer on the row.
            "restored_from": (
                "signed_on"
                if plan.signed_on is not None
                else ("agreement_sent_on" if plan.agreement_sent_on is not None else "proposed_on")
            ),
        },
    )
    return {"id": str(plan.pk), "status": restored, "created": True}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-019@7b2ce54 (ships with apps/payments/collections_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S34 column and S21 header are read-models with no endpoint yet) E=deferred(no-frontend-half — S21/S34 are unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report for the verbatim RED transcript — the "a plan
#         notice path may not drop an account" guard was proved RED by
#         reinstating a drop-off, RUN, and the measured failure quoted
# exceptions: (1) THE PAUSE HAS A SCOPE and the scope is the plan's ARREARS, not
#         the account. The current bill is never paused (PO 2026-08-11,
#         BR-BIL-073) and `PauseDecision.not_covered` says so on every result.
#         (2) A MISSED INSTALMENT LIFTS THE PAUSE and does NOT end the plan.
#         US-PAY-019 TC-3 expects the pause to hold "below threshold" and that
#         threshold was the superseded two-miss void — OQ-170 puts the grace
#         question to the PO rather than inventing a number of days.
#         (3) A WRITE-OFF CLOSES A PLAN (PO 2026-08-12, OQ-171) and a person
#         decides it — `close_plan_on_write_off` has no automatic caller and
#         counts nothing toward itself. This line described `void_plan` raising
#         until the ruling landed; rewritten rather than left, because a trailer
#         describing a refusal the code no longer makes is hard-won law 1.
#         (4) NO STORED PAUSE FLAG. The decision is computed on every call; a
#         cached pause is a pause that outlives its reason.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
