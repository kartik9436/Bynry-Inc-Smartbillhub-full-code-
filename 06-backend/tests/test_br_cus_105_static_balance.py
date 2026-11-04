# ── Trace ──────────────────────────────────────────────
# Rules:   **BR-CUS-103** (PO 2026-08-25, closing OQ-380 — base charges STOP at
#          the cut; the boundary is the CUT date, not the notice date) ·
#          **BR-CUS-104** (PO 2026-08-25, closing OQ-381 — the reconnection fee
#          lands AT THE CUT: *"does reconnection need $8,315.00 - this is
#          correct"*) · **BR-CUS-105** (derived the same day: together the two
#          make a cut account's balance STATIC) · B4.3 ❄️ (calendar-day
#          proration, `service_days / cycle_days`) · BR-BIL-007 (a fee is the
#          tenant's charge code, never a literal) · CLAUDE.md rule 2 (money 4dp
#          stored / 2dp displayed)
# Defects: **DEF-707** (a cut service is still billed its base charge — closed
#          by this change) · **DEF-708** (the reconnection gate lets a customer
#          through $75.00 short — STILL OPEN, pinned below)
# ───────────────────────────────────────────────────────
"""BR-CUS-105 — a cut account's balance does not move with the calendar.

**THIS IS THE CHEAPEST GUARD EITHER RULING HAS, AND THAT IS WHY IT IS ITS OWN
FILE.** BR-CUS-105, verbatim: *"a single test that runs a bill cycle over a cut
account and asserts the balance is unchanged catches a violation of EITHER rule
— a base line that should not exist, or a fee that landed late — without knowing
which. A property that falls out of two rules is still a property somebody must
not break."*

**The worked case is the PO's own.** `A-11488` was cut on **2026-08-18** owing
**$612.75** with a **$75.00** reconnection fee. It owes **$687.75** on the day
of the cut and **$687.75** on any later day until it is paid.

────────────────────────────────────────────────────────────────────────────
WHAT IS MEASURED, AND WHY IT IS THE BILL AND NOT A PAYLOAD KEY
────────────────────────────────────────────────────────────────────────────
Nothing in `apps/customers/disconnects.py` bills, so an assertion on the cut's
own answer proves only that a dict has a key in it. These cases price REAL
bills through `single.prepare_single_bill` → `single.calculate_single_bill` —
the same two calls a cycle run makes — over a plan whose base charge is
**$18.50** a month, and read the money off `invoice_lines`.

A balance moves when a bill is ISSUED. A bill whose total is **$0.00** cannot
move one, and that is the form the staticness takes here.

────────────────────────────────────────────────────────────────────────────
⛔ ONE CASE IS AN `xfail(strict=True)` PIN AND IT IS THE HALF THAT IS NOT BUILT
────────────────────────────────────────────────────────────────────────────
BR-CUS-104's **$687.75** needs the reconnection fee to be a RECEIVABLE at the
cut. It is not — **DEF-708** — so the amount that actually clears a reconnection
today is **$612.75**. The rule is asserted anyway, under `xfail(strict=True)`,
which is the idiom DEF-705 established one day earlier: *"the day the behaviour
arrives the pin XPASSes and fails and whoever built it must close this row."*

⚠ **AND THE FIX THAT WOULD MAKE IT PASS CHEAPLY IS THE WRONG ONE.** Adding
`case.reconnection_fee_amount` to `mark_reconnecting`'s comparison deadlocks the
product: paying takes AR to zero, the recorded fee never clears, and no cut
customer could ever be reconnected. The pin exists for the RECEIVABLE, not for
a bigger number in a comparison.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.billing import gather, single
from apps.customers import disconnects
from apps.metering import models as metering_models
from apps.rating import models as rating_models

from tests.test_us_bil_001_prepare import (
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import commit_read
from tests.test_w7_disconnects import _at_tier, _owes, _prove_tier_3_service

pytestmark = pytest.mark.django_db

# ── The PO's own figures, and nothing rounded toward them ───────────────────
#: `A-11488`, cut owing this much. BR-CUS-103's worked case.
ARREARS = D("612.75")
#: Brazos Bend's configured `CC-RECON` amount — **the TENANT's figure, not the
#: product's** (BR-BIL-007). It is written into this tenant's catalogue by the
#: fixture below and read back through `charge_by_code`; no literal 75 reaches
#: any assertion about product behaviour.
BRAZOS_RECONNECT_FEE = D("75.00")
#: BR-CUS-105's static figure: what `A-11488` owes on the cut date and on every
#: later day until it is paid.
STATIC_BALANCE = ARREARS + BRAZOS_RECONNECT_FEE  # 687.75

#: `a_priced_plan`'s base charge, restated here as the EXPECTATION rather than
#: imported, because this file's whole subject is what happens to it.
MONTHLY_BASE = D("18.500000")

#: June: the cycle the cut falls inside. 30 days, cut on the 15th → 15 served
#: days → B4.3's factor is exactly ½ and the base is **$9.25**. A half chosen
#: deliberately: a figure a reader can check without a calculator is a figure a
#: reader will check.
JUNE_START = date(2026, 6, 1)
JUNE_END = date(2026, 6, 30)
JUNE_SERVICE_DATE = date(2026, 6, 30)
CUT_ON = date(2026, 6, 15)
HALF_MONTH_BASE = D("9.25")

#: July: the cycle ENTIRELY after the cut. 31 days, 0 served → base **$0.00**.
JULY_START = date(2026, 7, 1)
JULY_END = date(2026, 7, 31)
JULY_SERVICE_DATE = date(2026, 7, 31)

LADDER_DAY = date(2026, 6, 1)
SERVED_ON = date(2026, 6, 5)


def _reconnect_charge(tenant, amount=BRAZOS_RECONNECT_FEE):
    """Brazos Bend's OWN `CC-RECON` row — BR-BIL-007, never a literal in code.

    ⚠ **NO SEED IN THIS REPO CREATES ONE** (DEF-700): the demo seeds `CONN`,
    `DISC`, `NSF` and `TAMPER`, so every test that reaches a cut has to
    configure the tenant first.
    ⚠ **AND IT NOW CARRIES A GL ACCOUNT — `DEF-2709`, and this suite had been
    RED since 2026-08-27 without it.** DEF-708 made the fee a REAL charge, so
    `fee_bill.charge_code_line` refuses a code with no GL account by name
    (BR-BIL-010: *charge codes carry their own GL*) — and every test in this file
    that reaches `commit_cut` has been failing on
    `charge code 'CC-RECON' has no GL account` ever since, on the branch tip,
    unnoticed, because **no gate in this repository runs pytest**. The W7 suite's
    own fixture was re-pointed in that same change and this one was missed.
    """
    from apps.ledger import models as ledger_models

    gl = (
        ledger_models.LedgerAccount.objects.filter(
            tenant=tenant, deleted_at__isnull=True, code="4200"
        ).first()
        or ledger_models.LedgerAccount.objects.filter(
            tenant=tenant, deleted_at__isnull=True
        ).first()
    )
    row, _ = rating_models.Charge.objects.get_or_create(
        tenant=tenant,
        code=disconnects.RECONNECT_CHARGE_CODE,
        defaults={
            "name": "Reconnection fee",
            "charge_type": "one_time",
            "amount_rule": "flat",
            "amount": amount,
            "gl_account_id": gl.id if gl else None,
        },
    )
    return row


def _a_cut_account(actor, tenant, monkeypatch, *, consumption="412.000000", services=None):
    """`A-11488`: a real billable account, cut through the REAL ladder.

    Walked with `advance()` three times, a real tier-3 notice and a real
    recorded proof of service, then `schedule_cut` and `commit_cut` — never by
    writing `cut_on` with an UPDATE. DEF-702 is what a fixture that writes
    around the service layer costs: a row that the `ck_cut_records_the_price_of
    _coming_back` CHECK says cannot exist.
    """
    _owes(monkeypatch, ARREARS)
    _reconnect_charge(tenant)
    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    unit = a_billed_unit(
        actor, tenant, cycle, plan, asset_no="M-11488", label="A", consumption=consumption
    )
    account = an_account(tenant, unit["id"], "A-11488")

    _at_tier(actor, account.id, disconnects.TIER_3)
    _prove_tier_3_service(actor, account.id, served_on=SERVED_ON)
    disconnects.schedule_cut(
        actor,
        account.id,
        cut_on=CUT_ON,
        as_of=LADDER_DAY,
        reason=disconnects.CUT_REASON_NON_PAYMENT,
        services=services or {"electric": disconnects.TREATMENT_FULL},
    )
    cut = disconnects.commit_cut(actor, account.id, cut_on=CUT_ON, as_of=CUT_ON)
    return account, unit, cut


def _a_run(tenant, key):
    """The `bill_runs` row every engine requires. A cycle run's own shape."""
    from apps.billing import models as billing_models

    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=metering_models.Cycle.objects.filter(tenant=tenant).first(),
        period_start=JUNE_START,
        period_end=JULY_END,
        idempotency_key=key,
    )


def _meter_id(unit):
    """The meter on this unit — `a_billed_unit` creates it and returns the unit."""
    from apps.assets import models as asset_models

    return asset_models.Asset.objects.get(asset_no="M-11488").id


def _bill(account, *, period_start, period_end, service_date, cycle_days):
    """One real bill, priced the way a cycle run prices one."""
    prepared = single.prepare_single_bill(
        account_id=account.id,
        period_start=period_start,
        period_end=period_end,
        service_date=service_date,
        cycle_days=cycle_days,
    )
    return prepared


# ════════════════════════════════════════════════════════════════════════════
# BR-CUS-105 — THE PROPERTY, ON A REAL BILL
# ════════════════════════════════════════════════════════════════════════════
def test_br_cus_105__a_cycle_entirely_after_the_cut_bills_nothing(brazos, marcus, monkeypatch):
    """**THE GUARD.** A bill cycle over a cut account cannot move the balance.

    July is entirely after the 15 June cut. The meter is off, so its read does
    not move (`14212 → 14212`, 0 kWh), and BR-CUS-103 says the base does not
    run. **The bill totals $0.00**, and a $0.00 bill cannot change what anybody
    owes — which is BR-CUS-105 in the form the ledger can see.

    ⚠ Under the behaviour DEF-707 records, this bill carried a **$18.50** base
    line every month for as long as the service stayed off.
    """
    with tenant_ctx(brazos):
        account, unit, _cut = _a_cut_account(marcus, brazos, monkeypatch)
        # The dead meter's July read: the same dial, so nothing was consumed.
        commit_read(
            marcus,
            _meter_id(unit),
            day="2026-07-28",
            value="14212",
            prior_value="14212",
            consumption="0.000000",
            unit="kWh",
        )
        prepared = _bill(
            account,
            period_start=JULY_START,
            period_end=JULY_END,
            service_date=JULY_SERVICE_DATE,
            cycle_days=31,
        )

        assert prepared.blocked == ()
        data = prepared.ready[0]
        # B4.3's numerator. 0 served days over a 31-day cycle is a factor of 0.
        assert data.service_days == 0, (
            "BR-CUS-103: a service cut on 15 June has NO served days in July, so the "
            f"proration factor is 0/31 — this bill claims {data.service_days}/31."
        )

        invoice = single.calculate_single_bill(prepared, bill_run=_a_run(brazos, "static-jul"))
        base = [line for line in invoice.lines.all() if line.kind == "base"]
        assert all(line.amount == D("0") for line in base), (
            "BR-CUS-103 (PO 2026-08-25, 'no'): a cut service is billed NO base charge. "
            f"This July bill carries {[str(line.amount) for line in base]}."
        )
        assert invoice.total == D("0"), (
            "BR-CUS-105: a bill cycle over a cut account must not move the balance, and a "
            f"bill of {invoice.total} does. A-11488 owes {STATIC_BALANCE} on the cut date "
            "and on any later day."
        )


def test_br_cus_103__the_cut_day_is_still_billed_and_the_boundary_is_the_cut_date(
    brazos, marcus, monkeypatch
):
    """The cycle CONTAINING the cut: base prorated to the cut day, not to zero.

    BR-CUS-103, verbatim: *"The boundary is the cut date, not the notice date —
    a service is billed base right up to the moment it is cut, because until
    then it was available."* June has 30 days and the cut is on the 15th, so
    **15 days are served** (1–15 inclusive, the same convention `_service_days`
    already applies to a move-out's `closed_at`) and the base is
    **$18.50 × 15/30 = $9.25**.

    ⚠ **BOTH WRONG ANSWERS ARE NAMED IN THE ASSERTIONS**, because each is one
    plausible reading of the rule: $18.50 is base that never stopped (DEF-707),
    and $0.00 is a cut backdated to the start of the cycle — which would refund
    a fortnight of service the customer actually had.
    """
    with tenant_ctx(brazos):
        account, _unit, _cut = _a_cut_account(marcus, brazos, monkeypatch)
        prepared = _bill(
            account,
            period_start=JUNE_START,
            period_end=JUNE_END,
            service_date=JUNE_SERVICE_DATE,
            cycle_days=30,
        )
        data = prepared.ready[0]
        assert (data.service_days, data.cycle_days) == (15, 30), (
            "BR-CUS-103: 1–15 June were served and 16–30 June were not, so B4.3's factor "
            f"is 15/30 — this bill claims {data.service_days}/{data.cycle_days}."
        )

        invoice = single.calculate_single_bill(prepared, bill_run=_a_run(brazos, "static-jun"))
        base = sum(line.amount for line in invoice.lines.all() if line.kind == "base")
        assert base == HALF_MONTH_BASE, (
            f"the base charge for June must be {HALF_MONTH_BASE} — $18.50 for half a month. "
            f"{MONTHLY_BASE} would be base that never stopped (DEF-707); 0.00 would backdate "
            f"the cut to 1 June and refund service the customer had. Got {base}."
        )


def test_br_cus_103__an_account_that_was_never_cut_is_untouched(brazos, marcus, monkeypatch):
    """The control, and it is not ceremony.

    A change that stopped base for EVERY account would pass both cases above.
    The same plan, the same period, no disconnect case: the full **$18.50**.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(marcus, brazos, cycle, plan, asset_no="M-90001", label="B")
        account = an_account(brazos, unit["id"], "A-90001")

        prepared = _bill(
            account,
            period_start=JUNE_START,
            period_end=JUNE_END,
            service_date=JUNE_SERVICE_DATE,
            cycle_days=30,
        )
        assert prepared.ready[0].service_days == 30
        invoice = single.calculate_single_bill(prepared, bill_run=_a_run(brazos, "control-jun"))
        base = sum(line.amount for line in invoice.lines.all() if line.kind == "base")
        assert base == D("18.50"), f"an account nobody cut pays its whole base charge; got {base}"


def test_br_cus_103__a_partial_cut_refuses_rather_than_averaging(brazos, marcus, monkeypatch):
    """⛔ Some services cut and some not: the bill is HELD, never approximated.

    `DSC-02.1` is *"One decision per service, not all or nothing"* and B4.3 has
    exactly ONE `service_days / cycle_days` factor for the whole account. So a
    bill charging a service that was cut AND a service that was not has two
    right answers and no way to express either. `gather` refuses by name and the
    account goes to the exception screen (BR-BIL-015).

    Proved with a cut naming a service this bill does NOT charge — the same
    shape from the other side, and the one a fixture can build without a
    second tariff.

    ⚠ **BLOCKED, NOT RAISED.** `prepare_single_bill` turns a `GatherProblem`
    into an exception ROW (BR-BIL-015), which is the whole point: the run keeps
    going and a human is handed the account with the reason on it. The
    assertion is on `prepared.blocked` because that is what a clerk sees.
    """
    with tenant_ctx(brazos):
        account, _unit, _cut = _a_cut_account(
            marcus, brazos, monkeypatch, services={"water": disconnects.TREATMENT_FULL}
        )
        prepared = _bill(
            account,
            period_start=JULY_START,
            period_end=JULY_END,
            service_date=JULY_SERVICE_DATE,
            cycle_days=31,
        )
    assert prepared.ready == (), "a partially cut account must not be priced at all"
    assert [row.reason for row in prepared.blocked] == [gather.GATHER_PARTIAL_CUT]
    detail = prepared.blocked[0].detail
    assert "electric" in detail and "water" in detail, (
        "the refusal names BOTH lists — what was cut and what was not — because that is "
        f"the decision the human has to take: {detail}"
    )


# ════════════════════════════════════════════════════════════════════════════
# BR-CUS-104 — THE HALF THAT IS NOT BUILT
# ════════════════════════════════════════════════════════════════════════════
def test_br_cus_104__the_fee_is_quoted_from_the_tenants_own_code_and_recorded(
    brazos, marcus, monkeypatch
):
    """What IS true today: the fee is read from `CC-RECON` and written at 4dp.

    BR-BIL-007 — *"NSF/reconnect fees are tenant-configured charge codes, never
    hardcoded"*. **$75.00 is Brazos Bend's configured figure, not the
    product's**, and the assertion proves it by changing the tenant's row and
    watching the quote follow.
    """
    with tenant_ctx(brazos):
        account, _unit, cut = _a_cut_account(marcus, brazos, monkeypatch)
        assert cut["reconnection_fee"] == {"stored": "75.0000", "display": "75.00"}
        assert cut["reconnection_fee_code"] == disconnects.RECONNECT_CHARGE_CODE
        # The ruling is recorded on the answer, and so is the defect.
        assert cut["fee_timing"]["code"] == "reconnection_fee_lands_at_the_cut"
        # ⚠ **`tracks` BECAME `closes` ON 2026-08-27 AND THIS LINE WAS NOT
        # RE-POINTED — `DEF-2709`'s second half.** DEF-708 turned the fee into
        # a real receivable and renamed `FEE_NOT_POSTED` to `FEE_POSTED`, whose
        # key says the defect is CLOSED rather than tracked. This assertion has
        # raised `KeyError: 'tracks'` on the branch tip ever since, hidden
        # behind the GL-account refusal one fixture earlier, and no gate in this
        # repository runs pytest.
        assert cut["fee_posting"]["closes"] == "DEF-708"

        case = disconnects.DisconnectCase.objects.get(id=cut["case_id"])
        rating_models.Charge.objects.filter(
            tenant=brazos, code=disconnects.RECONNECT_CHARGE_CODE
        ).update(amount=D("92.5000"))
        assert disconnects.reconnection_terms(account.id, case=case)["fee"]["display"] == "92.50"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEF-708 — BR-CUS-104 makes the reconnection fee a RECEIVABLE at the cut and nothing "
        "posts it. A-11340 must clear $8,315.00 and clears at $8,240.00; A-11488 must clear "
        "$687.75 and clears at $612.75. The fee is recorded on the disconnect case, "
        "`mark_reconnecting` reads AR, and the two never meet. ⚠ DO NOT close this by adding "
        "the recorded fee to the gate's comparison — paying takes AR to zero, the recorded fee "
        "never clears, and no cut customer could ever be reconnected. The close is the posting."
    ),
)
def test_br_cus_104__the_amount_that_reconnects_a_cut_account_includes_the_fee(
    brazos, marcus, monkeypatch
):
    """**$687.75, not $612.75.** BR-CUS-104, PO 2026-08-25, closing OQ-381.

    Put to the PO with both amounts because the whole difference is which one a
    customer must pay: *"does reconnection need $8,315.00 - this is correct"*.
    On this account: arrears **$612.75** + the tenant's **$75.00** fee =
    **$687.75** to be cleared before `mark_reconnecting` accepts.

    The pin fires the day the fee posts.
    """
    with tenant_ctx(brazos):
        account, _unit, _cut = _a_cut_account(marcus, brazos, monkeypatch)
        # Everything the ledger knows about is paid — the arrears, and nothing else.
        _owes(monkeypatch, D("0.00"))
        disconnects.mark_reconnecting(marcus, account.id, on_date=CUT_ON)
        cleared = disconnects.seams.ar_positions([account.id]).amount_for(str(account.id))
    raise AssertionError(
        f"BR-CUS-104: {STATIC_BALANCE} must be cleared to reach RECONNECTING on A-11488 "
        f"({ARREARS} arrears + {BRAZOS_RECONNECT_FEE} reconnection fee). The gate accepted at "
        f"{cleared} because the fee is on the disconnect case and not in AR (DEF-708)."
    )
