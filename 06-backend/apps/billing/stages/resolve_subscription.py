# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-029 (stage 1 of seven)   Screens: S31.2
#           The S31.2 story that RENDERS this output is named in the
#           docstring, not here — G10 reads a Trace US-ID as a claim to ship
#           that story's test cases, and this slice ships a stage.
# Rules:    BR-BIL-037 (one input contract, one output contract) · BR-BIL-039
#           (PURE — no writes, no external calls, no clock) · BR-CUS-055
#           (status behaviour classes; Vacation-hold / Suspended =
#           billable-base-only) · BR-MET-040 (a plan is REQUIRED — a unit
#           without one blocks) · BR-CUS-014 (the account derives its plan from
#           the unit) · B4.2 (tax exemption is account-level) · B4.3 (calendar-
#           day proration) · CLAUDE.md rule 2 (the tenant's currency)
# Tests:    06-backend/tests/test_us_bil_029_stages.py
# Impacts:  apps/billing/stages/measure_consumption.py (its sole consumer)
# ───────────────────────────────────────────────────────
"""Stage 1 — what is this account subscribed to, before anything is measured.

Its output is what the S31.2 preview's Consumers and Plans tabs render
(US-BIL-002). That story is named here rather than in the Trace block because
G10 reads a Trace US-ID as "this file ships that story's test cases", and this
file ships a stage.

PURE (BR-BIL-039): it reads its argument and returns a value. No database, no
clock, no writes. Everything it needs was gathered before the pipeline started,
which is what makes the S31.2 preview and the real run the same code.

WHAT IT DECIDES, and each of these is a rule rather than a preference:

1. **Is this account billable at all** (BR-CUS-055). Four behaviour classes:
   `billable` bills everything, `billable_base_only` bills base charges and no
   usage, `non_billable` and `terminal` bill nothing. This stage does not guess
   from a status NAME — the class travels on the gathered data, because a
   tenant may add statuses and the name is theirs while the class is the rule.

2. **Does it have a plan** (BR-MET-040, CONFIRMED: "Plan is REQUIRED at account
   activation; a unit without a plan blocks with a message"). No plan is not an
   empty bill — it is a refusal, and one the run surfaces as an exception for a
   human rather than swallowing.

3. **How much of the period does it own** (B4.3). A mid-period move-in owns
   fewer service days than the cycle has. The period travels as BOTH numbers so
   the proration factor is derived ONCE downstream and cannot be computed twice
   from two disagreeing figures.

WHAT IT DELIBERATELY DOES NOT DO: measure anything. A base-only account has a
subscription and no usage, and keeping "what is subscribed" separate from "what
was used" is what lets that case bill correctly instead of being special-cased
in a function that does both.
"""

from __future__ import annotations

from apps.billing import rating_seam
from apps.billing.contracts import AccountBillingData, SubscriptionContext
from apps.billing.exceptions import BillingRuleError

#: BR-CUS-055's seeded classes. A tenant extends the STATUS list; the class set
#: is the rule and is closed.
CLASS_BILLABLE = "billable"
CLASS_BASE_ONLY = "billable_base_only"
CLASS_NON_BILLABLE = "non_billable"
CLASS_TERMINAL = "terminal"
BILLING_CLASSES = (CLASS_BILLABLE, CLASS_BASE_ONLY, CLASS_NON_BILLABLE, CLASS_TERMINAL)
#: The two that produce a bill at all.
CLASSES_THAT_BILL = (CLASS_BILLABLE, CLASS_BASE_ONLY)


def resolve_subscription(data: AccountBillingData) -> SubscriptionContext:
    """`AccountBillingData` -> `SubscriptionContext`. One in, one out."""
    if data.behavior_class not in BILLING_CLASSES:
        # An unknown class is a refusal, not a default. Defaulting to
        # non-billable would silently drop a customer from a run; defaulting to
        # billable would bill someone the rules may not permit billing. Both
        # are wrong quietly, which is the worst way to be wrong about money.
        raise BillingRuleError(
            f"account {data.account_no}: unknown behaviour class "
            f"{data.behavior_class!r}. BR-CUS-055 defines {BILLING_CLASSES}. A "
            "class the code does not implement stops this account rather than "
            "falling through to a guess."
        )

    if data.behavior_class not in CLASSES_THAT_BILL:
        raise BillingRuleError(
            f"account {data.account_no} is {data.behavior_class} and is not "
            "billed. This is a scope decision the run makes BEFORE the "
            "pipeline; reaching stage 1 with it means the gather step let it "
            "through (BR-CUS-055)."
        )

    if not data.rate_plan_id:
        # BR-MET-040 CONFIRMED. Surfaces as an exception the run groups on the
        # S31.2 Plans tab, never as a zero-line bill.
        raise BillingRuleError(
            f"account {data.account_no} has no plan. BR-MET-040: a plan is "
            "REQUIRED — a unit without one blocks with a message. The account "
            "belongs in the run's exception list, not in a bill."
        )

    if not data.currency:
        raise BillingRuleError(
            f"account {data.account_no} has no currency. CLAUDE.md rule 2: "
            "money always travels with its CHAR(3) partner, and the currency "
            "is the TENANT's, never client input or a default."
        )

    base_only = data.behavior_class == CLASS_BASE_ONLY

    return SubscriptionContext(
        account_id=data.account_id,
        account_no=data.account_no,
        currency=data.currency,
        tax_exempt=data.tax_exempt,  # B4.2 — account-level, regardless of service
        period=rating_seam.BillingPeriod(
            cycle_days=data.cycle_days,
            service_days=data.service_days,
        ),
        rate_plan_id=data.rate_plan_id,
        rate_plan_name=data.rate_plan_name,
        rate_plan_version=data.rate_plan_version,
        tariffs=data.tariffs,
        taxes=data.taxes,
        fees=data.fees,
        base_only=base_only,
        snapshot=data.snapshot,
        # DEF-502 — the granted discounts travel with the subscription the way
        # the taxes do: gathered once, carried verbatim, priced by the engine.
        discounts=data.discounts,
        # PO 2026-10-01 — the pricing chain, as values, for stage 6 to write.
        pricing_trace=dict(getattr(data, "pricing_trace", None) or {}),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-029@e9d5a48 (the four billing sources — B2 §2 + r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a pure stage) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_029_stages.py
# exceptions: refuses rather than defaults on an unknown behaviour class, on a
#         missing plan and on a missing currency — each of those has a
#         plausible-looking default that would be wrong SILENTLY, which is the
#         failure mode CLAUDE.md names for billing · does NOT itself decide
#         whether a base-only account is billed THIS run: the PO ruled
#         2026-08-11 that this is a staff opt-in/opt-out at prepare time
#         (`base_only_billing` in DECISION_CASES), so by the time data reaches
#         this stage that choice has already been made and is recorded
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
