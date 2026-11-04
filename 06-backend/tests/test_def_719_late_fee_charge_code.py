# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-003 (S31.3 — the clerk applies the late fee) · US-BIL-005
#           (issue — the GL stamp) · US-BIL-029 (stage 6 writes the draft)
#           Screens: S31.3 · S31 step 5 · S13 · S30
# Rules:    BR-BIL-075 (PO ruling 2026-08-26, verbatim: "A · The late fee uses a
#           tenant charge code — like NSF and reconnect already do") ·
#           BR-BIL-007 (a fee's account is the TENANT's, never a literal) ·
#           BR-BIL-010 (every line's GL account resolves at issue and freezes) ·
#           BR-BIL-001 + B4 ❄️ (the fee's AMOUNT — max($5.00, 1.5% × overdue
#           portion) — which the charge code does NOT supply) · B4.2 (a fee is
#           never in the tax base) · BR-BIL-055 (a break never blocks the run) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money) · rule 4
#           (immutability) · rule 5 (balanced pairs; only the posting service
#           writes journal lines) · rule 6 (idempotency)
# Golden:   GT-10 ❄️ — usage 82.08 + base 18.50 + fee 8.13 + tax 8.30 = 117.01,
#           re-signed 2026-08-10 under HUMAN-GUIDE §6. GT-8 ❄️ computes the
#           8.13: max(5.00, 0.015 × 542.10) = max(5.00, 8.1315) = 8.13.
# Defects:  DEF-719 (a bill carrying an applied late fee could not be issued at
#           all) · DEF-201 (the same hole, open since 2026-08-17) · DEF-714 (the
#           charge-code half, which closed every fee EXCEPT this one) ·
#           DEF-700 (CC-RECON is in no seed — the reachability trap this file
#           checks it has not repeated)
# ───────────────────────────────────────────────────────
"""A bill CARRYING AN APPLIED LATE FEE is issued — which it could not be.

**THE TEST THREE DEFECTS SAY NOBODY HAD WRITTEN.** DEF-561 tested the selector.
DEF-714 tested a bill with a *charge-code* fee on it. Neither ever issued a bill
carrying the one fee this product computes rather than looks up, so the hole
survived two fixes: a clerk applied a late fee on S31.3, `decisions.py` appended
a fee line whose amount came from B4's own rule and which named **no charge
code**, and `issue._gl_account_for` refused the WHOLE BILL by name —
`a fee line ('Late fee') names no charge code`. No clerk could close it on a
screen, because there was nothing to configure: the line had no code to point
anywhere.

BR-BIL-075 closes it the way the PO chose: *"A · The late fee uses a tenant
charge code — like NSF and reconnect already do"*.

────────────────────────────────────────────────────────────────────────────
⚠⚠ THE HALF THAT SENTENCE DOES NOT SETTLE, AND THIS FILE GUARDS IT
────────────────────────────────────────────────────────────────────────────
NSF and reconnect are **flat** fees and their charge code carries the figure.
A late fee is not flat. Its amount is **❄️ FROZEN B4 math** and `GT-10`'s
**8.13** is a signed golden figure. So the code says **WHERE** the fee books
and B4 keeps saying **WHAT IT IS** — a charge code whose `amount` overrode 8.13
would change a frozen figure, which is a finance re-sign under HUMAN-GUIDE §6
and not an implementation choice.

`tc6` is the case that holds that line: it configures the tenant's `LATE` code
as a **flat $99.00**, issues the bill, and asserts the customer is charged
**8.13** and the bill totals **117.01** — while that same $99.00 code supplies
the account the 8.13 books to.

────────────────────────────────────────────────────────────────────────────
THE WORKED BILL, AND IT IS GT-10's OWN
────────────────────────────────────────────────────────────────────────────
    Electric usage   684 kWh × $0.12    82.08
    Electric base                       18.50   ── taxable base 100.58
    Late fee (B4: max($5.00, 1.5% × $542.10))
                                         8.13   ── a FEE: never in the tax base
    Tax (8.25% of 100.58)                8.30
                                       ------
    Total                              117.01

and it **issues**, with the 8.13 credited to the account the TENANT pointed
their `LATE` code at — `4200 Late-fee revenue` in `tc1`, and **`4210` in `tc3`,
which is the whole point of the ruling**: the PO rejected a twelfth GL
designation precisely because it would have hard-wired every utility's late fee
to 4200.
"""

from decimal import Decimal

import pytest

from apps.billing import decisions, issue, models, runs
from apps.billing import rating_seam
from apps.billing.exceptions import BillingRuleError
from apps.ledger import models as ledger_models
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from core import tenancy as core_tenancy

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    tenant_ctx,
)
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    an_account,
    an_authorised_run,
    electric_gl_accounts,
)
from tests.test_us_bil_029_assemble import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    billing_data,
)
from tests.test_br_bil_069_tax_authority_gl import a_tax_authority

pytestmark = pytest.mark.django_db

#: ❄️ **GT-10, and every figure below is one of its numbers.** The fee is the
#: one this file must not let move: GT-8 computes it as
#: `max(5.00, 0.015 × 542.10)` = `max(5.00, 8.1315)` = **8.13**, half-up at 2dp
#: on finalization (BR-RAT-003), and B5 signed it.
LATE_FEE = Decimal("8.13")
TAXABLE_BASE = Decimal("100.58")  # 82.08 usage + 18.50 base
TAX_TOTAL = Decimal("8.30")  # 8.25% of 100.58 — NOT of 108.71 (B4.2)
BILL_TOTAL = Decimal("117.01")  # 100.58 + 8.13 + 8.30
TAX_RATE = Decimal("0.0825")

#: The overdue portion GT-8 computes 8.13 from. Never used as an input here —
#: this file bills the SIGNED RESULT — but written down so a reader can check
#: the arithmetic without opening B5.
GT8_OVERDUE_PORTION = Decimal("542.10")

#: What a tenant that thinks about nothing lands on: the seeded chart's
#: `4200 Late-fee revenue`. It is a DEFAULT and `tc3` proves it is not a rule.
LATE_GL_CODE = "4200"
#: A second, equally lawful destination the same tenant may choose instead.
OTHER_GL_CODE = "4210"


def _account_by_code(code):
    """One LIVE ledger account of the CURRENT tenant, by its chart code.

    Tenant-scoped explicitly (CLAUDE.md rule 1): the developer database is
    SQLite and has no RLS, so every tenant's `4200` is visible to a bare
    queryset. On Postgres the policy would have done it; a test must not depend
    on which database it happens to be running against.
    """
    return ledger_models.LedgerAccount.objects.get(
        tenant_id=core_tenancy.current_tenant_id(), code=code, deleted_at__isnull=True
    )


def the_tenants_late_fee_code(tenant, code=decisions.DEFAULT_LATE_FEE_CHARGE_CODE):
    """The `LATE` row provisioning already wrote for this tenant.

    ⚠ **NOT `create` — it is ALREADY THERE, and that is the finding worth
    keeping.** Provisioning seeds `LATE` (`percent_with_minimum`, 1.5%, $5.00
    minimum — BR-BIL-001's own figures) on every tenant, so BR-BIL-075's code is
    reachable out of the box and this is not DEF-700 again. What it does NOT
    seed is a **GL account** — `gl_account_id` is NULL on a fresh tenant — which
    is `tc11`'s case (and DEF-733) and the one thing a clerk must do on S13 before a late fee
    can be billed.
    """
    return rating_models.Charge.objects.get(tenant=tenant, code=code, deleted_at__isnull=True)


def a_mapped_late_fee_code(tenant, *, gl_code=LATE_GL_CODE, amount=None, amount_rule=None):
    """The clerk's one S13 edit: point the tenant's `LATE` code at an account.

    `amount`/`amount_rule` are the knobs `tc6` turns. Turning them must move
    where the fee books and must NOT move what the customer is charged.
    """
    charge = the_tenants_late_fee_code(tenant)
    charge.gl_account_id = _account_by_code(gl_code).id if gl_code else None
    if amount_rule is not None:
        charge.amount_rule = amount_rule
        charge.amount = amount
    charge.save(update_fields=["gl_account_id", "amount_rule", "amount"])
    return charge


def a_prepared_run(data):
    """Phase 1's output around ONE account, in `apply_decisions`' own shape."""
    return runs.PreparedRun(
        cycle_id="cycle-1",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=SERVICE_DATE,
        cycle_days=30,
        scope_services=None,
        ready=(data,),
    )


def a_plan_pointed_at_the_late_code(tenant, name="DEF-719 plan"):
    """A published plan naming the tenant's own `LATE` charge code (BR-RAT-1011).

    `get_or_create` so repeated calls inside one test share one plan; the
    pointer is (re)set every time, because a test that RETIRES the code between
    calls must see the plan follow it rather than a cached row.
    """
    from tests.test_us_met_helpers import make_plan

    plan = make_plan(tenant, name=name, code="def719-plan")
    charge = rating_models.Charge.objects.filter(
        tenant=tenant, code=decisions.DEFAULT_LATE_FEE_CHARGE_CODE, deleted_at__isnull=True
    ).first()
    rating_models.RatePlan.objects.filter(pk=plan.pk).update(late_fee_charge=charge)
    plan.refresh_from_db()
    return plan


def a_bill_with_an_applied_late_fee(tenant, actor, *, fee=LATE_FEE, account_no="A-10432"):
    """THE REAL PATH, end to end, with nothing between the clerk and the draft.

    S31.3's write (`decisions.record_decision`) → phase 2's fold
    (`decisions.apply_decisions`) → the production calculate entry point
    (`runs.calculate_account`, stages 1 → 2 → rating → 6). The fee line is NOT
    hand-built: the whole of DEF-719 lived in what `apply_decisions` did and did
    not put on that line, so a fixture that built it here would test the fixture.
    """
    _jurisdiction, tax, tax_account = a_tax_authority("State of Texas", TAX_RATE, actor=actor)
    account = an_account(actor, tenant, account_no=account_no)
    run = an_authorised_run(tenant, actor)
    data = billing_data(
        account,
        # ── `CR-078` (BR-RAT-1011, PO 2026-09-07) — A REAL PLAN, POINTED ──────
        # ⚠ This used to ride `billing_data`'s synthetic `rate_plan_id="plan-1"`,
        # and after CR-078 that is no longer billable: the late fee's percent
        # and minimum come from the charge code THE PLAN NAMES, so a bill with
        # no readable plan has no late-fee terms to read. The fixture now builds
        # the state a real account is in — a published plan pointed at the
        # tenant's own `LATE` code — which is what makes 8.13 below still 8.13.
        rate_plan_id=str(a_plan_pointed_at_the_late_code(tenant).id),
        taxes=(rating_seam.TaxRule(code="STATE+LOCAL", rate=TAX_RATE, tax_id=str(tax.id)),),
    )
    decisions.record_decision(
        bill_run=run,
        account_id=str(account.id),
        case="late_fee",
        choice=decisions.CHOICE_APPLY,
        # ❄️ B4's figure, carried by the decision row exactly as the run screen
        # records it. `apply_decisions` must not recompute it and must not read
        # one off the charge code.
        amount=fee,
        reason="Late fee",
        decided_by=actor.user,
    )
    decided = decisions.apply_decisions(a_prepared_run(data), bill_run=run)
    draft = runs.calculate_account(decided.ready[0], bill_run=run, service_date=SERVICE_DATE)
    return draft, run, account, tax_account


def _issue(draft, actor):
    return issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=actor,
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE CASE DEF-719 EXISTS FOR — and the one three fixes did not have
# ═══════════════════════════════════════════════════════════════════════════
def test_def_719_tc1__a_bill_carrying_an_applied_late_fee_can_be_issued(brazos, dana):
    """END TO END: apply the fee on S31.3, run the bill, ISSUE it.

    Before BR-BIL-075 this raised `BillingRuleError: a fee line ('Late fee')
    names no charge code` and the whole bill died — not the fee line, the bill.

    Four different failures are asserted apart, because three of them are
    silent: the bill issues at all (DEF-719); the fee is **8.13** and not a
    figure read off a code (❄️ GT-10); the tax is **8.30**, computed on the
    100.58 of electricity and NOT on the 108.71 that includes the fee (B4.2);
    and the 8.13 lands in the tenant's late-fee account rather than swept into
    electric revenue, where it would be indistinguishable from electricity sold
    forever, on a row hard rule 4 forbids editing.
    """
    with tenant_ctx(brazos):
        code = a_mapped_late_fee_code(brazos)
        draft, _run, _account, _tax_account = a_bill_with_an_applied_late_fee(brazos, dana)
        assert draft.lines.get(kind="fee").charge_id == code.id, "BR-BIL-075: it names the code"

        bill = _issue(draft, dana)

        stored = models.Invoice.objects.get(pk=bill.pk)
        assert stored.status == models.INVOICE_ISSUED, "DEF-719: this is the whole defect"
        lines = list(stored.lines.all())
        assert all(
            line.gl_account_id is not None for line in lines
        ), "BR-BIL-010: every line, or the bill does not issue at all"

        # ── the money, to the digit — ❄️ GT-10 ──────────────────────────────
        fee_line = stored.lines.get(kind="fee")
        assert fee_line.amount == LATE_FEE, "❄️ GT-10 / GT-8: 8.13 is a signed figure"
        assert stored.subtotal == TAXABLE_BASE  # B4.2: the fee is NOT in it
        assert stored.tax_total == TAX_TOTAL  # 8.25% of 100.58, not of 108.71
        assert stored.total == BILL_TOTAL  # 100.58 + 8.13 + 8.30 = 117.01

        # ── the account: the tenant's OWN code's, not a service's revenue ────
        late_account = _account_by_code(LATE_GL_CODE)
        assert str(fee_line.gl_account_id) == str(late_account.id)
        usage_account, base_account = electric_gl_accounts()
        by_kind = {line.kind: str(line.gl_account_id) for line in lines if line.kind != "tax"}
        assert by_kind == {
            "usage": usage_account,
            "base": base_account,
            "fee": str(late_account.id),
        }


def test_def_719_tc2__the_late_fee_lands_in_its_own_bucket_and_the_books_balance(brazos, dana):
    """CLAUDE.md rule 5 + US-BIL-005 §7 — read out of `journal_lines` itself.

    The entry debits AR for the whole **117.01** and credits **8.13 to 4200**
    beside 82.08/18.50 of electric revenue and 8.30 of tax. What matters is what
    LANDED in the books, not what a result object reported, so the figures come
    off the rows.
    """
    with tenant_ctx(brazos):
        a_mapped_late_fee_code(brazos)
        draft, _run, _account, tax_account = a_bill_with_an_applied_late_fee(brazos, dana)
        _issue(draft, dana)

        entry = ledger_models.JournalEntry.objects.filter(tenant=brazos).get()
        totals: dict[str, dict[str, Decimal]] = {}
        for gl_code, side, amount in ledger_models.JournalLine.objects.filter(
            tenant=brazos, journal_entry=entry
        ).values_list("ledger_account__code", "side", "amount"):
            bucket = totals.setdefault(gl_code, {"debit": Decimal("0"), "credit": Decimal("0")})
            bucket[side] += amount

        assert totals[LATE_GL_CODE]["credit"] == LATE_FEE
        assert totals["4100"]["credit"] == Decimal("82.08")
        assert totals["4105"]["credit"] == Decimal("18.50")
        assert totals["1200"]["debit"] == BILL_TOTAL
        # Balanced pairs (hard rule 5): Σ debits == Σ credits, to the digit.
        debits = sum((row["debit"] for row in totals.values()), Decimal("0"))
        credits = sum((row["credit"] for row in totals.values()), Decimal("0"))
        assert debits == credits == BILL_TOTAL
        assert str(tax_account.id)  # the authority's own account exists and is used


def test_def_719_tc3__the_destination_is_the_tenants_choice_and_not_a_hardwired_4200(brazos, dana):
    """**THE REJECTED SHAPE, proved rejected.**

    The alternative put to the PO was a twelfth GL designation pinning every
    late fee to the seeded `4200`. They chose the charge code *"like NSF and
    reconnect already do"* — so a utility that points their `LATE` code at
    `4210` gets their late-fee revenue in `4210`, and nothing in this product
    overrules them.

    A test that only ever configured 4200 would pass identically against the
    rejected implementation. This one cannot.
    """
    with tenant_ctx(brazos):
        a_mapped_late_fee_code(brazos, gl_code=OTHER_GL_CODE)
        draft, _run, _account, _tax = a_bill_with_an_applied_late_fee(brazos, dana)
        bill = _issue(draft, dana)

        fee_line = models.Invoice.objects.get(pk=bill.pk).lines.get(kind="fee")
        chosen = _account_by_code(OTHER_GL_CODE)
        assert str(fee_line.gl_account_id) == str(chosen.id)
        assert str(fee_line.gl_account_id) != str(_account_by_code(LATE_GL_CODE).id)
        # …and the money is unmoved by where it went (❄️ GT-10).
        assert models.Invoice.objects.get(pk=bill.pk).total == BILL_TOTAL


# ═══════════════════════════════════════════════════════════════════════════
# ⚠⚠ THE HALF THE RULING DOES NOT SETTLE — the AMOUNT stays B4's
# ═══════════════════════════════════════════════════════════════════════════
def test_def_719_tc6__a_flat_amount_on_the_code_is_used_for_nothing(brazos, dana):
    """**A CHARGE CODE CARRYING AN AMOUNT DOES NOT MOVE A FROZEN FIGURE.**

    ⚠ **SUPERSEDED IN PART 2026-10-17 (PO *"we ahve to allow flat as we wll
    %age"*, `DEF-BIL-10201`).** A late-fee code whose amount rule is FLAT now
    charges its flat amount when the bill run COMPUTES the fee
    (`late_fee_run` → `assess_late_fee_on_terms`; Flat $10.00 → $10.00). This
    case still holds for what it exercises: a decision row that already carries
    B4's computed figure is billed at that figure, and the code supplies the GL
    account. ❄️ GT-8's $8.13 — the percentage path — is unchanged.

    "Like NSF and reconnect" is exact about the GL account and SILENT about the
    amount, and the analogy breaks at precisely that point: those two are flat
    and their code carries the figure. This tenant has re-keyed their `LATE`
    code to a flat **$99.00** — a lawful thing for them to do on S13 — and the
    customer is still charged **8.13**, because BR-BIL-001's rule is ❄️ FROZEN
    B4 math and GT-10 signed the bill it makes.

    A pass here that read 99.00 would not be a bug in this file. It would be a
    frozen figure changed without a finance re-sign under HUMAN-GUIDE §6.

    The $99.00 code is not ignored, though — it is what supplies the ACCOUNT.
    Both halves are asserted, because the rule is exactly that one applies and
    the other does not.
    """
    with tenant_ctx(brazos):
        a_mapped_late_fee_code(brazos, amount=Decimal("99.00"), amount_rule="flat")
        draft, _run, _account, _tax = a_bill_with_an_applied_late_fee(brazos, dana)
        bill = _issue(draft, dana)

        stored = models.Invoice.objects.get(pk=bill.pk)
        fee_line = stored.lines.get(kind="fee")
        assert fee_line.amount == LATE_FEE, "❄️ B4 / GT-10 — never the code's 99.00"
        assert fee_line.amount != Decimal("99.00")
        assert stored.total == BILL_TOTAL, "117.01 — the whole bill is unmoved"
        # WHERE, though, IS the code's: that half of BR-BIL-075 does apply.
        assert str(fee_line.gl_account_id) == str(_account_by_code(LATE_GL_CODE).id)


# ═══════════════════════════════════════════════════════════════════════════
# WHAT REFUSES — by name, never by silently dropping the fee
# ═══════════════════════════════════════════════════════════════════════════
def test_def_719_tc4__a_tenant_with_no_late_fee_code_now_charges_ZERO(brazos, dana):
    """⚠ **SUPERSEDED BEHAVIOUR — `CR-078` (BR-RAT-1011) REVERSED THIS ON
    2026-09-07, AND THE OLD ASSERTION IS QUOTED HERE RATHER THAN DELETED.**

    THIS TEST USED TO ASSERT A REFUSAL. Its name was
    `..._refuses_by_name` and its docstring read, verbatim:

        *"No code ⇒ REFUSE, naming it — never a hardcoded account, never no
        fee. … Dropping the fee is money the utility decided to charge and
        never charged, on a bill that looks perfectly normal."*

    That reasoning was RIGHT under BR-BIL-075, where the missing code meant the
    fee could not be BOOKED. The PO has since ruled the other way about a
    different question — where the fee's AMOUNT comes from — and the two
    answers meet here. PO verbatim, 2026-09-07, finance re-signed the same day:

        *"you ahve to take late fees form charge code mentione din the plan -
        if plan doent provide you that charge code then you have to put zero on
        late payment."*

    So a plan naming no live late-fee charge code now charges **$0.00** and the
    bill is produced without a fee line. **The old objection is answered, not
    ignored:** the drop is no longer silent — `plans_missing_late_fee_charge`,
    `manage.py cr078_late_fee_codes` and gate `G121` each count a plan in this
    state, which is what the PO's *"put zero"* costs and what step 5 of the CR
    buys back.

    ⚠ **WHAT DID NOT CHANGE:** a plan that cannot be READ still refuses, by
    name, with `br_ref` (`decisions._late_fee_charge_id_for_plan`). Zero is for
    a plan that exists and names nothing; a plan nobody can find is a data
    fault and stops the run exactly as it did.
    """
    with tenant_ctx(brazos):
        # A tenant who deleted theirs outright. `LATE` is seeded, so this state
        # is reached by a clerk removing it — which they may.
        the_tenants_late_fee_code(brazos).delete()
        assert not rating_models.Charge.objects.filter(
            tenant=brazos, code=decisions.DEFAULT_LATE_FEE_CHARGE_CODE
        ).exists()

        draft, _run, _account, _tax_account = a_bill_with_an_applied_late_fee(brazos, dana)

        # The bill EXISTS and carries no fee line — the ruled zero.
        kinds = list(
            models.InvoiceLine.objects.filter(invoice=draft).values_list("kind", flat=True)
        )
    assert "fee" not in kinds, (
        "BR-RAT-1011: a plan naming no late-fee charge code charges $0.00, so there is "
        "no fee line. A $0.00 line would tell the customer a fee was calculated."
    )
    # …and the state is COUNTED rather than silent, which is what makes the
    # ruled zero safe (CR-078 step 5).
    with tenant_ctx(brazos):
        missing = rating_selectors.plans_missing_late_fee_charge()
    assert any(row["reason"] == "names_no_charge_code" for row in missing), missing


def test_def_719_tc5__a_retired_late_fee_code_also_charges_zero(brazos, dana):
    """IS-1 — a retired charge is not chargeable, and is not silently revived.

    ⚠ **SUPERSEDED THE SAME WAY AS TC-4 (`CR-078`, 2026-09-07).** This asserted
    `pytest.raises(BillingRuleError, match="not a live charge code")`. A retired
    code is still not chargeable and still not revived; what changed is the
    ANSWER — zero rather than a refusal — because the PO ruled that a plan
    providing no charge code puts zero on late payment, and a retired code
    provides nothing.

    A clerk who retired `LATE` and one who never made it get the same outcome,
    which is the honest answer: the product cannot tell which of those two
    things they meant.
    """
    with tenant_ctx(brazos):
        code = a_mapped_late_fee_code(brazos)
        code.deleted_at = ISSUED_AT
        code.save(update_fields=["deleted_at"])

        draft, _run, _account, _tax_account = a_bill_with_an_applied_late_fee(brazos, dana)
        kinds = list(
            models.InvoiceLine.objects.filter(invoice=draft).values_list("kind", flat=True)
        )
    assert "fee" not in kinds


def test_def_719_tc11__a_seeded_but_unmapped_late_code_refuses_at_issue_by_name(brazos, dana):
    """An UNMAPPED late-fee code refuses at issue, by name, and atomically.

    ⚠ **THIS DOCSTRING OPENED *"THIS IS THE STATE EVERY FRESH TENANT IS IN"*
    AND THAT STOPPED BEING TRUE ON 2026-09-02 (`CR-066`, closing `DEF-2386`).
    Read it in the past tense (hard-won law 1).** Provisioning used to seed
    `LATE` with its percent and its $5.00 minimum and **no GL account**, so a
    fresh tenant could not bill a late fee at all until a clerk went to S13 and
    pointed the code somewhere. The platform seed now points it at **4200
    Late-fee revenue** — one of the 28 mappings the Product Owner approved —
    so the sentence this test was written to prevent anybody believing,
    *"a fresh tenant can bill a late fee"*, is now simply TRUE.

    **THE BEHAVIOUR UNDER TEST IS UNCHANGED AND STILL MATTERS**, because a
    tenant may clear the mapping (clearing is a real act the Accounting screen
    offers) or point it at an account they later deactivate. BR-BIL-075 resolves
    the CODE happily — the draft names it — and the bill then refuses at ISSUE
    with `charge_code_has_no_live_account`, naming the code and the screen,
    while the other bills in the run still issue (BR-BIL-055). So the unmapped
    state is now REACHED EXPLICITLY below instead of being inherited from the
    seed, which is the honest way to keep asserting it.
    """
    with tenant_ctx(brazos):
        # ⚠ **THE SEED NOW MAPS THIS CODE (`CR-066`), so the state under test is
        # reached by CLEARING it — the same act a clerk performs on Settings →
        # Accounting when they retire an account.** Asserting the seeded value
        # first, because a seed that silently stopped mapping is a defect this
        # line would otherwise hide.
        seeded = the_tenants_late_fee_code(brazos)
        assert seeded.gl_account_id is not None, (
            "the seeded state since CR-066: LATE arrives pointed at 4200 Late-fee revenue. "
            "If this is None the platform GL defaults have stopped being applied and "
            "DEF-2386 is back — a fee line refuses the WHOLE bill at issue."
        )
        seeded.gl_account_id = None
        seeded.save(update_fields=["gl_account_id"])
        draft, run, _account, _tax = a_bill_with_an_applied_late_fee(brazos, dana)
        assert draft.lines.get(kind="fee").charge_id is not None, "BR-BIL-075 still resolved"

        with pytest.raises(BillingRuleError, match="has no GL account"):
            _issue(draft, dana)

        # Atomic: nothing stamped, the draft is still a draft (US-BIL-007 TC-5).
        untouched = models.Invoice.objects.get(pk=draft.pk)
        assert untouched.status == models.INVOICE_DRAFT
        assert all(line.gl_account_id is None for line in untouched.lines.all())

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        assert result.issued == ()
        assert result.broken[0].reason == issue.ISSUE_FEE_CHARGE_UNMAPPED


def test_def_719_tc7__a_run_with_no_late_fee_never_asks_for_the_code(brazos, dana):
    """The refusal must not become a NEW total outage — DEF-714's own shape.

    DEF-714 was total because a recurring code rides EVERY bill: one missing
    mapping stopped the whole book. A late-fee code is not on every bill, so
    resolving it eagerly would have made a tenant who has never charged a late
    fee unable to bill at all. It is resolved only when some account in the run
    actually has one applied.
    """
    with tenant_ctx(brazos):
        # No late-fee code at all — the state `tc4` refuses in. Here nobody
        # applied a late fee, so nothing asks and the bill goes out.
        the_tenants_late_fee_code(brazos).delete()
        account = an_account(dana, brazos, account_no="A-10440")
        run = an_authorised_run(brazos, dana)
        # `taxes=()` keeps this case about the late fee: a tax line needs its
        # authority's own 2200-series account (BR-BIL-069) and that is a
        # different refusal, tested in its own file.
        prepared = a_prepared_run(billing_data(account, taxes=()))

        decided = decisions.apply_decisions(prepared, bill_run=run)

        assert decided.ready[0].fees == ()
        draft = runs.calculate_account(decided.ready[0], bill_run=run, service_date=SERVICE_DATE)
        bill = _issue(draft, dana)
        assert models.Invoice.objects.get(pk=bill.pk).status == models.INVOICE_ISSUED
        # GT-1's own bill, untaxed and with no fee: 82.08 + 18.50.
        assert models.Invoice.objects.get(pk=bill.pk).total == TAXABLE_BASE


def test_def_719_tc8__the_draft_names_the_code_and_only_the_fee_line_does(brazos, dana):
    """`invoice_lines.charge_id`, asserted at DRAFT time where it belongs.

    It is a fact about what was PRICED (like `service` and `tax_id`); issue only
    RESOLVES it into a GL account. A regression in stage 6 is then named as a
    stage-6 regression rather than as a mysterious issue failure. And it is on
    the FEE line only — a usage line naming a charge code would post electricity
    into the late-fee bucket.
    """
    with tenant_ctx(brazos):
        code = a_mapped_late_fee_code(brazos)
        draft, _run, _account, _tax = a_bill_with_an_applied_late_fee(brazos, dana)

        by_kind = {line.kind: line for line in draft.lines.all()}
        assert str(by_kind["fee"].charge_id) == str(code.id)
        assert by_kind["usage"].charge_id is None
        assert by_kind["base"].charge_id is None
        assert by_kind["tax"].charge_id is None
        # Still a draft: identity is not the GL stamp (BR-BIL-010).
        assert all(line.gl_account_id is None for line in draft.lines.all())


def test_def_719_tc9__issuing_twice_neither_re_stamps_nor_double_posts(brazos, dana):
    """Hard rule 6 + rule 4 — the fee does not get charged to the books twice.

    A retried release is an ordinary event (a timeout, a double click, a resumed
    batch), and the late fee is the line most likely to be noticed twice: 8.13
    posted twice is 16.26 of revenue nobody billed, on rows that cannot be
    edited.

    The second `issue_invoice` REFUSES rather than no-ops (BR-BIL-004 — an
    issued bill is a fact about what a customer was told), and the run-level
    pass then finds no remaining draft. Both doors, because a release is retried
    through the run and a clerk retries through the bill.
    """
    with tenant_ctx(brazos):
        a_mapped_late_fee_code(brazos)
        draft, run, _account, _tax = a_bill_with_an_applied_late_fee(brazos, dana)
        first = _issue(draft, dana)
        stamps = [str(line.gl_account_id) for line in first.lines.all().order_by("id")]

        with pytest.raises(BillingRuleError, match="cannot be issued again"):
            _issue(models.Invoice.objects.get(pk=first.pk), dana)
        again = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        assert again.issued == ()

        # The stamp is frozen and untouched by either retry (BR-BIL-010).
        assert [
            str(line.gl_account_id)
            for line in models.Invoice.objects.get(pk=first.pk).lines.all().order_by("id")
        ] == stamps
        assert ledger_models.JournalEntry.objects.filter(tenant=brazos).count() == 1
        credited = sum(
            (
                row
                for row in ledger_models.JournalLine.objects.filter(
                    tenant=brazos, ledger_account__code=LATE_GL_CODE, side="credit"
                ).values_list("amount", flat=True)
            ),
            Decimal("0"),
        )
        assert credited == LATE_FEE  # 8.13 once, not 16.26


def test_def_719_tc10__the_seeded_late_code_is_reachable_on_every_tenant(brazos):
    """**DEF-700's trap, checked rather than repeated.**

    `CC-RECON` is named by `customers.disconnects` and written by NO seed, so
    the reconnect feature is unreachable on every tenant in this tree. A late
    fee that needed an unseeded code would have shipped the same defect with a
    ruling behind it.

    `LATE` is in `seed_demo.CHARGE_CODES` and in provisioning's `[F]` fixture,
    and this asserts the NAME this module resolves is that same one — read out
    of the seed's own declaration, not retyped, so renaming either half fails
    here rather than in production.
    """
    from apps.tenancy.management.commands import seed_demo

    seeded = {row["code"] for row in seed_demo.CHARGE_CODES}
    assert (
        decisions.DEFAULT_LATE_FEE_CHARGE_CODE in seeded
    ), "BR-BIL-075's code must be one a tenant actually has, or this is DEF-700 again"
    late = next(
        row
        for row in seed_demo.CHARGE_CODES
        if row["code"] == decisions.DEFAULT_LATE_FEE_CHARGE_CODE
    )
    # …and the seeded row carries NO flat amount, because BR-BIL-001 computes it.
    assert "amount" not in late
    assert late["amount_rule"] == "percent_with_minimum"


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-BIL-075 (04-docs/05-modules/07-billing/02-business-rules.md, last
#         row) · DEF-719 (12-governance/10-defect-log.csv) ·
#         12-governance/02-decision-log.md §2026-08-26 · B4 ❄️ §Late fee ·
#         B5 ❄️ GT-8/GT-10 · 07-billing/03-field-map.md (the row that names
#         `invoice_lines.charge_id → LATE`) · EP-BIL-01-bill-run.md §5
# generated: 2026-08-26 by the LATEFEE lane (closing DEF-719)
# checklist: A✔ B✔ C✔ D=deferred(no new API surface — the refusal travels the
#         existing `api.run_calculate` 422 with `br_ref`) E=deferred(the
#         on-screen statement that a code's amount is ignored is a FRONTEND
#         half and is REPORTED as owed, not faked here) F✔ G✔ H=deferred(PO
#         2026-08-09)
# gates: ruff✔ black✔ · golden-verify 33 PASS / 0 FAIL before and after
#         (exit 0) · pytest -m golden unchanged
# exceptions: (1) the GL account is asserted through TWO different tenant
#         choices (4200 in tc1, 4210 in tc3) rather than one, because a
#         single-destination test passes identically against the twelfth-GL-
#         designation shape the PO REJECTED
#         (2) `tc6` deliberately configures an unlawful-looking flat $99.00
#         late-fee code. It is lawful for a tenant to do and the product must
#         not spend it — that is the one line between BR-BIL-075 and a change
#         to a ❄️ FROZEN figure
#         (3) the fee line is never hand-built: every case drives
#         `record_decision` → `apply_decisions` → `calculate_account` → `issue`,
#         because DEF-561 and DEF-714 each tested one hop short of the failure
#         and each shipped it again
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
