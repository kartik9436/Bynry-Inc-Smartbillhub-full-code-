# ── Trace ──────────────────────────────────────────────
# Rules:   BR-RAT-117 (PO 2026-08-22, verbatim: "ruccuring and Autom apply
#          land on bill") · BR-RAT-730 (the trigger is BOTH columns, and R4
#          reads them) · BR-RAT-088 (is_base owns the base — never twice) ·
#          BR-RAT-108 (customer-class INCLUSION list)
# Ruling:  PO 2026-09-19 — "the charge code decides / Naming a charge in a
#          plan makes it available. Whether it bills monthly is the charge
#          code's own setting"; and "plan is only binding - even plan should
#          not talk about rules here"
# Defects: DEF-RAT-5784 — a plan-named code rode every cycle whatever its
#          declared trigger; DEF-561 (the route this corrects, not reverses)
# Questions: OQ-RAT-12463 (a monthly fee on ONE plan) · OQ-RAT-12464 (the
#          auto-apply/non-recurring conflict: R4 refuses, this omits)
# ───────────────────────────────────────────────────────
"""`DEF-RAT-5784` — a plan NAMING a charge code does not put it on a bill.

⚠ **THE DISCRIMINATOR IS WHICH CODES COME BACK, NEVER A QUERY COUNT.** A
sibling lane in this module found the trap by hand: the old path was a single
statement returning everything, so its cost lived in ROWS and never in
STATEMENTS, and a count-based assertion passes on the unfixed code. Every case
here names a CODE.

**WHAT WAS WRONG, MEASURED ON `brazosbend` ON 2026-09-19.** Nine
`plan_charge_rules` attachments, five distinct codes, every one `penalty` or
`one_time`: `TAMPER` `$250.00` and `NSF` `$30.00` on Industrial (1 unit);
`CONN` `$45.00` and `NSF` on Residential Standard (7 units); `DISC` `$45.00`
and `NSF` on Small Commercial (2 units); `LATE` on all three. **`$955.00` a
month and `$11,460.00` a year across ten units**, and a `$250.00` tamper fee
billed twelve times a year without anyone tampering. Route 1 selected NOTHING
on that tenant — it holds no `recurring` + `auto_apply` code at all — so
**every fee line the product could produce was one of those nine.**
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.rating import models as rating_models, selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, tenant_ctx  # noqa: F401
from apps.rating.charge_prices import flat_amount as _flat  # CR-156-BRC10: the amount is a dated row

pytestmark = pytest.mark.django_db

SERVICE_DATE = date(2026, 9, 1)


def _plan(tenant, name):
    """⚠ REUSE THE SEEDED PLAN WHERE THERE IS ONE, FOR THE SAME REASON `_code`
    DOES — and because creating a second `Industrial` violates
    `uq_rate_plans_tenant_code_ci` on PostgreSQL.

    ⚠ **AND `code` MUST BE SET EXPLICITLY.** `RatePlan.code` is a bare
    `TextField` with no default, so two plans created without one both hold
    `""` and the SECOND violates `uq_rate_plans_tenant_code_ci` — which is why
    the single-plan cases passed and the three-plan case did not.

    **The failure is hard-won law 14 in miniature and is worth naming:** it
    arrived as `IntegrityError` and then `TransactionManagementError: An error
    occurred in the current transaction`, the aborted-transaction state SQLite
    does not have. The default suite could not have shown it this way.
    """
    existing = rating_models.RatePlan.objects.filter(tenant_id=tenant.id, name=name).first()
    if existing is not None:
        return existing
    code = "T5784-" + "".join(ch for ch in name.upper() if ch.isalnum())[:12]
    return rating_models.RatePlan.objects.create(
        tenant=tenant, code=code, name=name, status="published"
    )


def _code(tenant, code, *, amount, kind, auto=False, base=False):
    """⚠ UPDATE-OR-CREATE, AND THE REASON IS THE POINT OF THIS FILE.

    `CONN`, `NSF`, `TAMPER`, `DISC` and `LATE` ARE ALREADY IN THE SEEDED
    TENANT — they are the utility's own codes, which is why they are the ones
    that were wrongly riding its bills. Creating them raises
    `UniqueViolation: uq_charges_tenant_code`, so these cases state the shape
    on the REAL rows rather than on look-alikes beside them.
    """
    amount = None if amount is None else Decimal(amount)
    existing = rating_models.Charge.objects.filter(
        tenant_id=tenant.id, code=code, deleted_at__isnull=True
    ).first()
    if existing is not None:
        existing.charge_type = kind
        existing.auto_apply = auto
        existing.amount = amount
        existing.is_base = base
        existing.save(update_fields=["charge_type", "auto_apply", "amount", "is_base"])
        return existing
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=code,
        name=f"{code} charge",
        charge_type=kind,
        auto_apply=auto,
        amount=amount,
        is_base=base,
    )


def _name_on_plan(tenant, plan, code):
    rule, _ = rating_models.PlanChargeRule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, charge=code
    )
    return rule


# ── THE DEFECT ITSELF ───────────────────────────────────────────────────────


def test_the_tamper_fee_is_ABSENT_from_the_bill_and_PRESENT_in_the_catalogue(brazos):
    """⚠ THE PIN. `TAMPER` is a `$250.00` penalty. The Industrial plan names
    it, so before this fix it rode an ordinary bill twelve times a year.

    **Both halves are asserted on purpose.** Absent from the bill proves the
    trigger gate fires; present in the catalogue proves the fix did that by
    honouring the code's trigger and NOT by deleting the attachment or hiding
    the code — which is the false pass this case exists to exclude.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos, "Industrial")
        tamper = _code(brazos, "TAMPER", amount="250.0000", kind="penalty")
        _name_on_plan(brazos, plan, tamper)

        billed = selectors.billable_charge_codes(plan.id, SERVICE_DATE)
        catalogue = list(
            rating_models.Charge.objects.filter(
                tenant_id=brazos.id, deleted_at__isnull=True
            ).values_list("code", flat=True)
        )
        still_named = rating_models.PlanChargeRule.objects.filter(
            tenant_id=brazos.id, rate_plan_id=plan.id, charge_id=tamper.id
        ).count()

    assert "TAMPER" not in [row["code"] for row in billed], (
        f"a $250.00 penalty is still riding an ordinary bill: {billed}"
    )
    assert "TAMPER" in catalogue, "the fix removed the code instead of gating it"
    assert still_named == 1, "the fix removed the plan attachment instead of gating it"


def test_a_properly_marked_recurring_auto_apply_code_STILL_ARRIVES(brazos):
    """Route 1 must be untouched. `BR-RAT-117`'s own worked figure is a
    `$12.00`/month recurring auto-apply fee, and it still lands."""
    with tenant_ctx(brazos):
        plan = _plan(brazos, "Route 1 intact")
        _code(brazos, "SVC-M", amount="12.0000", kind="recurring", auto=True)
        rows = selectors.billable_charge_codes(plan.id, SERVICE_DATE)

    assert [row["code"] for row in rows] == ["SVC-M"]
    assert rows[0]["amount"] == Decimal("12.0000")


def test_the_whole_brazosbend_shape_bills_955_before_and_0_after(brazos):
    """⚠ THE MONEY. The tenant's own nine attachments, rebuilt exactly, with
    the unit multipliers that make the figure: Industrial 1, Residential
    Standard 7, Small Commercial 2.

    Every one of the five codes is `penalty` or `one_time`, so after the fix
    the fee total is `$0.00` on all three plans. The `$955.00` it replaces is
    asserted as ARITHMETIC over what the old union WOULD have selected — the
    plan-named set, ungated — so the figure in the defect row is checked here
    rather than merely quoted.
    """
    per_plan_units = {"Industrial": 1, "Residential Standard": 7, "Small Commercial": 2}
    with tenant_ctx(brazos):
        codes = {
            "TAMPER": _code(brazos, "TAMPER", amount="250.0000", kind="penalty"),
            "NSF": _code(brazos, "NSF", amount="30.0000", kind="penalty"),
            "LATE": _code(brazos, "LATE", amount=None, kind="penalty"),
            "CONN": _code(brazos, "CONN", amount="45.0000", kind="one_time"),
            "DISC": _code(brazos, "DISC", amount="45.0000", kind="one_time"),
        }
        attach = {
            "Industrial": ("TAMPER", "NSF", "LATE"),
            "Residential Standard": ("CONN", "NSF", "LATE"),
            "Small Commercial": ("DISC", "NSF", "LATE"),
        }
        plans = {}
        for plan_name, wanted in attach.items():
            plan = _plan(brazos, plan_name)
            plans[plan_name] = plan
            for code_name in wanted:
                _name_on_plan(brazos, plan, codes[code_name])

        billed_now = {
            name: selectors.billable_charge_codes(plan.id, SERVICE_DATE)
            for name, plan in plans.items()
        }

    # What the OLD union would have selected: every code the plan names.
    would_have_billed = Decimal("0")
    for plan_name, wanted in attach.items():
        per_bill = sum(
            (Decimal(_flat(codes[c]) or 0) for c in wanted), Decimal("0")
        )
        would_have_billed += per_bill * per_plan_units[plan_name]
    assert would_have_billed == Decimal("955.0000"), would_have_billed

    for plan_name, rows in billed_now.items():
        assert rows == [], f"{plan_name} still bills {rows}"


def test_a_one_time_connection_fee_named_by_a_plan_does_not_ride(brazos):
    """`CONN` is `$45.00` and `one_time`. A connection fee belongs on the bill
    that follows a connection, not on all twelve of the year."""
    with tenant_ctx(brazos):
        plan = _plan(brazos, "One-time named")
        conn = _code(brazos, "CONN", amount="45.0000", kind="one_time")
        _name_on_plan(brazos, plan, conn)
        rows = selectors.billable_charge_codes(plan.id, SERVICE_DATE)
    assert rows == []


def test_a_recurring_code_a_plan_names_but_the_tenant_did_not_auto_apply(brazos):
    """⚠ THE ONE CASE THE TWO READINGS DISAGREE ABOUT, PINNED SO THE CHOICE IS
    VISIBLE. `PAPER` is `$2.00` and `recurring`, `auto_apply` is unset, and a
    plan names it.

    **It does NOT ride**, because `BR-RAT-730` makes the trigger BOTH columns
    and `DEF-RAT-5779` derives the plan wizard's *On every bill* column from
    exactly that pair — so billing it here would print *No* on the screen
    where a clerk attaches it and charge the customer anyway.

    Reading it the other way (`recurring` alone for a plan-named code) is
    defensible and is `OQ-RAT-12463`. **Zero rows on `brazosbend` are in this
    state**, so the two readings bill the same `$0.00` today; this case exists
    so that changing the answer has to change a test that says why.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos, "Recurring not auto")
        paper = _code(brazos, "PAPER", amount="2.0000", kind="recurring", auto=False)
        _name_on_plan(brazos, plan, paper)
        rows = selectors.billable_charge_codes(plan.id, SERVICE_DATE)
    assert rows == []


def test_the_union_still_bills_ONCE(brazos):
    """`BR-RAT-088`'s `$24.00`-for-one-`$12.00`-fee. A code that is
    auto-applied AND named by the plan is one entry and one line."""
    with tenant_ctx(brazos):
        plan = _plan(brazos, "Both routes")
        code = _code(brazos, "SVC-BOTH", amount="12.0000", kind="recurring", auto=True)
        _name_on_plan(brazos, plan, code)
        rows = selectors.billable_charge_codes(plan.id, SERVICE_DATE)
    assert len(rows) == 1, f"billed twice: {rows}"
    assert rows[0]["amount"] == Decimal("12.0000")


# ── THE TWO NARROWINGS ARE HELD IN STEP BY THIS, NOT BY A CALL ──────────────


@pytest.mark.parametrize(
    "kind,auto",
    [
        ("recurring", True),
        ("recurring", False),
        ("one_time", False),
        ("penalty", False),
        ("refundable", False),
        ("adjustment", False),
    ],
)
def test_it_AGREES_with_R4_for_every_non_base_code(brazos, kind, auto):
    """⚠ `selectors._rides_a_periodic_bill` RESTATES `resolution.
    rides_a_periodic_bill` and deliberately does not call it — the module's
    own posture, because the pricing shadow compares its two narrowings and
    *"a comparison whose two sides are the same function is a check that
    cannot fail"*. **This is what holds them in step instead.**

    The auto-apply/non-recurring row is excluded from the parameter list: R4
    RAISES there and this omits, which is a stated divergence with its own
    case below.
    """
    from apps.rating import resolution

    with tenant_ctx(brazos):
        plan = _plan(brazos, f"Agree {kind}-{auto}")
        code = _code(brazos, "AGREE", amount="7.0000", kind=kind, auto=auto)
        _name_on_plan(brazos, plan, code)
        selected = bool(selectors.billable_charge_codes(plan.id, SERVICE_DATE))
        r4_says = resolution.rides_a_periodic_bill(
            resolution.ChargeCode(
                code=code.code,
                charge_type=code.charge_type,
                auto_apply=code.auto_apply,
                is_base=code.is_base,
            )
        )
    assert selected == r4_says, (
        f"the two narrowings disagree for {kind}/auto_apply={auto}: "
        f"selector={selected}, R4={r4_says}"
    )


def test_the_is_base_divergence_from_R4_is_DELIBERATE(brazos):
    """⚠ R4 says a base code RIDES; this selector EXCLUDES it. Both are right
    and the pair is pinned so neither reads as drift.

    R4's `resolve_base_charge` reads its output, so gating the base on
    `auto_apply` is a base that does not exist — `DEF-154` took `$8.00`
    residential water to `$0.00` exactly that way. This reader excludes
    `is_base` by name because the base already reaches the bill by its own
    route, and letting it in bills `$12.00` twice (`BR-RAT-088`, the
    `$23,069.50`-a-month failure).
    """
    from apps.rating import resolution

    with tenant_ctx(brazos):
        plan = _plan(brazos, "Base divergence")
        base = _code(brazos, "BASE-W", amount="8.0000", kind="recurring", auto=False, base=True)
        _name_on_plan(brazos, plan, base)
        rows = selectors.billable_charge_codes(plan.id, SERVICE_DATE)
        r4_says = resolution.rides_a_periodic_bill(
            resolution.ChargeCode(
                code=base.code,
                charge_type=base.charge_type,
                auto_apply=base.auto_apply,
                is_base=True,
            )
        )
    assert rows == [], "the base would be billed twice"
    assert r4_says is True, "R4 stopped carrying the base — DEF-154's shape"


def test_the_conflict_divergence_is_OMIT_here_and_REFUSE_at_R4(brazos):
    """⚠ `OQ-RAT-12464`. A code marked `auto_apply` whose type is `penalty`
    is two columns a person filled in that contradict each other — *a $250.00
    tamper fee on one bill or on twelve*.

    R4 raises `ChargeCodeRecurrenceConflict`. This selector omits it. **That
    is pre-existing and `DEF-RAT-5784` does not change it**: route 1 has
    always expressed the conjunction as a queryset filter, and putting a new
    refusal on the LIVE fee path can stop a bill run. Pinned so the asymmetry
    is a recorded choice rather than an accident.
    """
    from apps.rating import resolution

    with tenant_ctx(brazos):
        plan = _plan(brazos, "Conflict")
        code = _code(brazos, "CONFLICT", amount="250.0000", kind="penalty", auto=True)
        _name_on_plan(brazos, plan, code)
        rows = selectors.billable_charge_codes(plan.id, SERVICE_DATE)
        with pytest.raises(resolution.ChargeCodeRecurrenceConflict):
            resolution.rides_a_periodic_bill(
                resolution.ChargeCode(
                    code=code.code,
                    charge_type=code.charge_type,
                    auto_apply=True,
                    is_base=False,
                )
            )
    assert rows == [], "a conflicting code rode an ordinary bill"
