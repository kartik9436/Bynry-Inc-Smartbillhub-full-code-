# ── Trace ──────────────────────────────────────────────
# Story:   CR-052 wave W0 task 1 — the cut is the WHOLE event
# Rule:    **PO ruling 2026-08-30**, verbatim: *"when we disconnect - we
#          generate final bill at that time itself - so later bill is not
#          required ... entire workflow including all settlement and status
#          update is taken care at time of disconnect or move out - so account
#          status changes and outstanding is pending on account if any"*.
#          Closes `OQ-1170`.
# Rules:   BR-CUS-103 (base is billed right up to the cut) · BR-CUS-107 (the
#          sixth status) · BR-BIL-005 (cutting twice must not bill twice) ·
#          `DSC-02.4` (the cut leaves the account OPEN) · B4.3 ❄️ ·
#          CLAUDE.md rules 1, 2, 4, 6, 7
# Tests:   this file
# ───────────────────────────────────────────────────────
"""**THE $23.23, RUN.** The days before a cut, billed by somebody.

`OQ-1170` was put to the PO with one figure: `A-11488`, cut on **18 August** on
a **$40.00** monthly base, uses the service from the 1st to the 18th and — the
moment BR-CUS-107's `Disconnected` status is written — drops out of the bill run
that would have charged for those days. **18 days of 31 is $23.23**, plus every
gallon and every kWh, billed to nobody.

This file reproduces that account and proves the ruling closed it: the bill
exists, it is ISSUED, its base line reads **$23.23** — the PO's own figure,
to the cent — and the account is `Disconnected` afterwards.

════════════════════════════════════════════════════════════════════════════
WHAT IS REAL HERE — AND SINCE 2026-08-31 THAT IS EVERYTHING
════════════════════════════════════════════════════════════════════════════
**REAL:** the whole ladder (three `advance()` steps, a tier-3 notice, a recorded
proof of service), `schedule_cut`, `commit_cut`, billing's own
`single.prepare_single_bill` → `calculate_single_bill` → `issue.issue_invoice`,
the rating engine, B4.3's frozen proration and the ledger posting. **No
arithmetic in this file computes 23.23** — it is read off `invoice_lines`.

⚠ **ONE READ USED TO BE STUBBED HERE AND IS NOT ANY MORE — `DEF-2708`, FIXED
2026-08-31.** B4.3 divides base by the CYCLE's length, and
`apps.metering.selectors.billing_period_for_unit` — the contract written out in
`apps/customers/seams.billing_period_for_unit`, with
`apps/customers/services.PERIOD_UNAVAILABLE` reporting the same absence for a
mid-cycle plan change — **had never been published**. So the denominator fell
back to the billed window's own length, the factor was 1, and this customer was
charged the FULL **$40.00** for 18 days: **$16.77 too much, on a real final
bill.** Metering now derives the period from the cycle's own ruled schedule
(`OQ-340`'s anchor, B17 §2's frequency step, `OQ-339`'s month-end clamp), so
`_schedule_the_august_cycle` CONFIGURES a cycle instead of a test handing the
product an answer, and the $23.23 below is end-to-end.

**The absence is still reachable and is still asserted**
(`test_a_cycle_that_cannot_be_read_still_says_so_and_charges_the_full_base`):
a cycle provisioned before CR-029 carries no frequency and no first run, so it
answers nothing, and `cut_bill.CUT_BILL_DENOMINATOR_ABSENT` still says so on the
bill rather than the customer discovering it on the paper.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.billing import models as billing_models
from apps.customers import disconnects
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.rating import models as rating_models

from tests.test_us_bil_001_prepare import a_billed_unit, a_cycle
from tests.test_us_met_reads_helpers import commit_read
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    lonestar,
    make_plan,
    marcus,
    tenant_ctx,
)
from tests.test_w7_disconnects import _at_tier, _owes, _prove_tier_3_service

pytestmark = pytest.mark.django_db

# ── `A-11488`, exactly as OQ-1170 and BR-CUS-103 put it to the PO ───────────
#: The arrears the account was cut owing. CR-052 task 3's figure, unchanged.
ARREARS = D("612.75")
#: The tenant's own `CC-RECON` amount (BR-BIL-007 — never a literal in product
#: code; this fixture writes the tenant's catalogue row and the product reads it).
RECONNECT_FEE = D("75.00")

#: August 2026: **31 days**, and the cut falls on the 18th → **18 served days**.
#: The two numbers B4.3's factor is made of, and the whole of the PO's figure.
AUGUST_START = date(2026, 8, 1)
AUGUST_END = date(2026, 8, 31)
CUT_ON = date(2026, 8, 18)
LADDER_DAY = date(2026, 8, 1)
SERVED_ON = date(2026, 8, 5)
RECONNECT_ON = date(2026, 9, 12)
RESTORE_ON = date(2026, 9, 15)

#: The monthly base charge the PO was shown. Written into the tenant's own
#: tariff version below, so nothing in the product carries the literal.
MONTHLY_BASE = D("40.000000")
#: **$23.23** — the figure `OQ-1170` put to the PO, and what the engine writes.
#:
#: ⚠ **IT IS 23.23 AND NOT 23.2258, AND THE DIFFERENCE IS B4's ROUNDING RULE
#: RATHER THAN A LOOSE ASSERTION.** The exact quotient 40.00 × 18 / 31 is
#: 23.2258064…; B4 rounds a LINE at finalization, and `invoice_lines.amount`
#: therefore holds **23.230000** (a legacy NUMERIC(18,6) container — CLAUDE.md
#: rule 2 as re-signed 2026-08-22 governs what is written, not the column's
#: width). So the stored line, the displayed line and the PO's own figure are
#: all the same number, which is the happiest possible outcome for a rule that
#: was put to a human as *"$23.23"*. **NOT computed by this file** — it is the
#: expectation the engine's own answer is compared to.
BASE_FOR_18_OF_31 = D("23.23")


def _forty_dollar_plan(tenant):
    """A published plan whose tariff version carries the PO's own $40.00 base.

    `tests.test_us_bil_001_prepare.a_priced_plan`'s shape with one number
    changed, because this file's whole subject is what happens to that number.
    The rate is one 0→∞ tier (BR-RAT-032), which is how rating really stores a
    flat rate.
    """
    from apps.rating import selectors as rating_selectors
    from apps.tenancy import models as tenancy_models

    plan = make_plan(tenant, name="A-11488 Residential", services=("electric",))
    # ⚠ `DEF-CUS-9059` — THE $40.00 IS DECLARED WHERE A BILL READS IT. Since
    # `DEF-BIL-7170` (2026-09-28: *"we will never take default value from plan
    # … that is retired"*) the version's `base_charge` below is never read, and
    # a base comes from the service's `is_base` charge code (BR-RAT-088). The
    # same figure, unscoped and one price for all sizes — `a_priced_plan`'s
    # repair (`0ee4cccc9`), which this fixture's docstring names as its shape.
    rating_models.Charge.objects.get_or_create(
        tenant=tenant,
        code="BASE-ELECTRIC-A11488",
        defaults=dict(
            name="Electric base",
            charge_type="recurring",
            amount_rule="flat",
            amount=MONTHLY_BASE,
            service=tenancy_models.Service.objects.get(code="electric"),
            is_base=True,
        ),
    )
    for row in rating_selectors.plan_rate_schedules(plan.id):
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            # `DEF-RAT-9832` (PO 2026-10-06): the schedule NAMES the code above.
            base_charge_code=rating_models.Charge.objects.get(tenant=tenant, code="BASE-ELECTRIC-A11488"),
            model="flat",
            base_charge=MONTHLY_BASE,
            uom="kWh",
            currency="USD",
            effective_from=date(2026, 1, 1),
        )
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=1,
            from_qty=D("0"),
            to_qty=None,
            unit_price=D("0.120000"),
        )
        # `DEF-CUS-9059` — and the schedule states which sizes it serves, or R3
        # refuses every account on a banded service (`DEF-2816`, 2026-09-01).
        state_size_axis(version, row["service_code"])
    return plan


def _reconnect_charge(tenant):
    """The tenant's `CC-RECON` row, with the GL account DEF-708 requires.

    ⚠ **NO SEED IN THIS REPO CREATES ONE** (DEF-700): the demo seeds `CONN`,
    `DISC`, `NSF` and `TAMPER`. Every test that reaches a cut configures it
    first, and since DEF-708 the code needs a GL account or the fee — now a real
    receivable — could never be booked (BR-BIL-010).
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
            "amount": RECONNECT_FEE,
            "gl_account_id": gl.id if gl else None,
        },
    )
    return row


def _schedule_the_august_cycle(cycle):
    """Configure the cycle the way CR-029 says a cycle is configured.

    ⚠ **THIS USED TO BE A `monkeypatch` OF `apps.metering.selectors
    .billing_period_for_unit`, BECAUSE THE READ DID NOT EXIST.** It exists
    (`DEF-2708`, 2026-08-31), so the world this file describes is now built out
    of the cycle's own ruled fields and NOTHING here is stubbed. B4.3's
    denominator is the CYCLE's 31 days rather than the billed window's 18 —
    the difference between **$23.23** and **$40.00** on this one bill — and it
    is derived by metering rather than handed to the product by a test.

    ⚠ **`days_to_complete` IS 5 AND NOT 31, DELIBERATELY.** That is the READ
    window (1–5 August, the days the crew is out); the BILLING period is
    1–31 August. A fixture whose two numbers were equal could not tell the two
    apart, and treating them as one thing is exactly what `DEF-2708` was.
    """
    cycle.frequency = "Monthly"
    cycle.days_to_complete = 5
    cycle.first_run_date = AUGUST_START
    cycle.save(update_fields=["frequency", "days_to_complete", "first_run_date"])
    return cycle


def _a11488(actor, tenant, monkeypatch, *, consumption="412.000000", scheduled=True):
    """`A-11488`: a real, billable, metered account walked to a REAL cut.

    `opened_at` is 1 August, so the first unbilled day billing derives is the
    1st and the window it bills is **1–18 August inclusive** (BR-CUS-103: the
    cut day itself is served).
    """
    _owes(monkeypatch, ARREARS)
    _reconnect_charge(tenant)
    cycle = a_cycle(tenant, code="08-A")
    if scheduled:
        _schedule_the_august_cycle(cycle)
    plan = _forty_dollar_plan(tenant)
    unit = a_billed_unit(
        actor, tenant, cycle, plan, asset_no="M-11488", label="A", consumption=None
    )
    # ⚠ **THE READ MUST FALL INSIDE THE WINDOW THE CUT BILLS.** `a_billed_unit`'s
    # own read is dated 2026-06-28 (it was written for a June cycle), and a bill
    # for 1 → 18 August with no reading in it is refused by stage 1 rather than
    # priced at zero — correctly (BR-BIL-015: a missing read is an exception for
    # a human, never a silent zero). The crew reads the meter as it goes dark,
    # so the reading is dated the CUT DAY.
    if consumption is not None:
        from apps.assets import models as asset_models

        commit_read(
            actor,
            asset_models.Asset.objects.get(asset_no="M-11488").id,
            day=CUT_ON.isoformat(),
            value="14212",
            prior_value="13800",
            consumption=consumption,
            unit="kWh",
        )
    account = customers_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no="A-11488",
        status=customers_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customers_models.AccountType.objects.first(),
        opened_at=AUGUST_START,
    )
    _at_tier(actor, account.id, disconnects.TIER_3)
    _prove_tier_3_service(actor, account.id, served_on=SERVED_ON)
    disconnects.schedule_cut(
        actor,
        account.id,
        cut_on=CUT_ON,
        as_of=LADDER_DAY,
        reason=disconnects.CUT_REASON_NON_PAYMENT,
        services={"electric": disconnects.TREATMENT_FULL},
    )
    return account, unit


def _base_line(invoice_id):
    """The BASE line of a bill, read off `invoice_lines`. No arithmetic here."""
    return billing_models.InvoiceLine.objects.filter(invoice_id=invoice_id, kind="base").first()


# ════════════════════════════════════════════════════════════════════════════
# THE $23.23. THE WHOLE POINT OF THE RULING, RUN END TO END.
# ════════════════════════════════════════════════════════════════════════════
def test_the_days_before_the_cut_are_billed_at_the_cut(brazos, marcus, monkeypatch):
    """**`OQ-1170`'s money, closed.** 18 days of 31 on a $40.00 base = $23.23.

    Before the ruling this was billed to NOBODY: the September run would have
    charged it, and writing `Disconnected` at the cut drops the account out of
    `selectors.accounts_for_bill_run` before billing is ever called. The PO
    removed the lateness — *"we generate final bill at that time itself"* — so
    the same days are billed by the same engine, a month earlier.

    Six assertions, in the order a reader would ask them:
      1. a bill EXISTS for 1–18 August, issued, not a draft;
      2. its base line is **$23.23** — the exact quotient is 23.2258064… and
         B4 rounds a line at finalization, so the stored figure, the displayed
         figure and the figure the PO was shown are one number;
      3. B4.3's two numbers are the PO's — 18 service days of a 31-day cycle;
      4. the account reads `Disconnected` / `non_billable` afterwards;
      5. it has left the bill run, which is now CORRECT rather than costly;
      6. and the account is still OPEN (`DSC-02.4`) with the money outstanding.

    ⚠ **NOTHING IS MONKEYPATCHED — `DEF-2708`.** The 31 in assertion 3 is
    derived by `apps.metering.selectors.billing_period_for_unit` off the
    cycle this fixture CONFIGURES, not handed to the product by this file.
    """
    with tenant_ctx(brazos):
        account, unit = _a11488(marcus, brazos, monkeypatch)
        cut = disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)
        bill = cut["cut_bill"]
        invoice = billing_models.Invoice.objects.get(id=bill["invoice_id"])
        base = _base_line(bill["invoice_id"])
        row = customers_models.Account.objects.get(id=account.id)
        scoped = list(customers_selectors.accounts_for_bill_run([str(unit["id"])]))

    # 1 ─ the bill exists, for the ruled window, and it is ISSUED ───────────
    assert bill["outcome"] == "raised"
    assert bill["billed"] is True
    assert (bill["period_start"], bill["period_end"]) == ("2026-08-01", "2026-08-18")
    assert invoice.status == "issued"
    assert invoice.bill_type == "cycle"  # an ordinary bill over an unusual window
    assert invoice.currency == "USD"  # rule 2 — never without its currency

    # 2 ─ **THE $23.23**, read off the line the engine wrote ────────────────
    assert base is not None
    assert base.amount == BASE_FOR_18_OF_31
    # ⚠ `invoice_lines.amount` is a legacy NUMERIC(18,6) container, so the raw
    # string is `23.230000`. CLAUDE.md rule 2 as re-signed 2026-08-22 governs
    # what is WRITTEN and what is DISPLAYED — 4dp stored, 2dp shown — and both
    # are asserted on the value rather than on the column's own width.
    assert f"{base.amount:.4f}" == "23.2300"
    assert f"{base.amount:.2f}" == "23.23"  # what the customer reads

    # 3 ─ B4.3's two numbers are the ones the PO was shown ──────────────────
    assert (bill["service_days"], bill["cycle_days"]) == (18, 31)
    assert "unavailable" not in bill  # the cycle WAS read, so no absence stated

    # 4 ─ BR-CUS-107's status, written by the product and not by a test ─────
    assert row.status.code == "disconnected"
    assert row.status.behavior_class == customers_services.CLASS_NON_BILLABLE
    assert cut["account_status_written"] == "disconnected"
    assert cut["account_status_before_cut"] == "active"

    # 5 ─ out of the run, and that is now correct ───────────────────────────
    assert scoped == []

    # 6 ─ `DSC-02.4` — a cut leaves the account OPEN, owing money ───────────
    assert row.closed_at is None
    assert cut["account_open"] is True
    assert cut["settlement"]["written_off"] is None
    assert cut["settlement"]["account_closed"] is False
    assert cut["settlement"]["deposit_settled"] is False


def test_a_cycle_that_cannot_be_read_still_says_so_and_charges_the_full_base(
    brazos, marcus, monkeypatch
):
    """**THE REMAINING ABSENCE, AND IT IS NO LONGER EVERY BILL — `DEF-2708`.**

    ⚠ **THIS TEST'S WORLD USED TO BE THE PRODUCT'S REAL WORLD.** Until
    2026-08-31 metering published no `billing_period_for_unit` at all, so B4.3's
    denominator fell back to the billed window's own length on EVERY cut, the
    factor was 1, and `A-11488` was charged the FULL **$40.00** for 18 days —
    **$16.77** more than the $23.23 the PO was shown. The read exists now, so
    the scheduled case above bills $23.23 and this case is what is left: a
    cycle provisioned **before CR-029**, carrying no frequency and no first run,
    which metering honestly cannot place on a calendar (`scheduled=False`).

    The days ARE billed either way (which is the ruling's whole point and is
    worth far more than the $16.77), and the over-charge is STATED on the result
    rather than discovered on the paper. That is
    `one_time.ONE_TIME_UNAVAILABLE`'s `partial_window_charges_a_full_base_charge`
    reaching one more caller — the behaviour the PO ruled on in CR-029 D8④
    (*"this is not required"*) — so nothing here is a new rule.
    """
    with tenant_ctx(brazos):
        account, _unit = _a11488(marcus, brazos, monkeypatch, scheduled=False)
        cut = disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)
        bill = cut["cut_bill"]
        base = _base_line(bill["invoice_id"])
        row = customers_models.Account.objects.get(id=account.id)

    assert bill["outcome"] == "raised"
    assert (bill["service_days"], bill["cycle_days"]) == (18, 18)
    assert base.amount == MONTHLY_BASE  # the whole month, for 18 days
    # …and the absence is NAMED, with the two figures in it.
    assert bill["unavailable"]["code"] == "cut_bill_prorates_on_the_window_not_the_cycle"
    assert "$23.23" in bill["unavailable"]["detail"]
    assert "$16.77" in bill["unavailable"]["detail"]
    # The days are billed either way, which is what lets the status be written.
    assert row.status.code == "disconnected"


# ════════════════════════════════════════════════════════════════════════════
# CLAUDE.md HARD RULE 6 — CUTTING TWICE MUST NOT BILL TWICE
# ════════════════════════════════════════════════════════════════════════════
def test_cutting_twice_does_not_bill_twice(brazos, marcus, monkeypatch):
    """Two independent guards, and the second is the DATABASE.

      1. `commit_cut` refuses a case already in state `cut` — `already_cut` —
         so the ordinary replay never reaches billing at all.
      2. `bill_runs.idempotency_key` is unique per tenant (BR-BIL-005), keyed on
         the account, the bill type and the window, so even a caller that got
         past guard 1 could not mint a second run over 1–18 August.

    Both are asserted, because a Python check alone loses a race and a unique
    index alone would let a second cut re-date the enforcement record.
    """
    with tenant_ctx(brazos):
        account, _unit = _a11488(marcus, brazos, monkeypatch)
        first = disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)

        # ── guard 1 · the case refuses ──────────────────────────────────────
        with pytest.raises(disconnects.DisconnectRuleError) as again:
            disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)

        # ── guard 2 · billing's own door, called directly, refuses too ──────
        from apps.billing import cut_bill

        second = cut_bill.raise_and_issue_cut_bill(
            marcus, account_id=account.id, cut_on=CUT_ON, due_days=0, cycle_days=31
        )
        invoices = billing_models.Invoice.objects.filter(account_id=account.id, bill_type="cycle")
        # ⚠ SCOPED TO THE CUT BILL'S OWN TYPE. The $75.00 reconnection fee is a
        # `fee` bill and mints a run of its own (`fee_bill.raise_charge_fee`),
        # so an unfiltered count would be 2 on a first cut and would say
        # nothing at all about whether the METERED bill had been raised twice.
        runs = billing_models.BillRun.objects.filter(scope_account_id=account.id, bill_type="cycle")

    assert again.value.code == "already_cut"
    # ⚠ **THE SECOND CALL ANSWERS `nothing_to_bill`, NOT `already_billed`, AND
    # THAT IS THE STRONGER ANSWER.** The first cut ISSUED a bill through
    # 18 August, so the account's first unbilled day is now the 19th and the
    # window `period_start > cut_on` is empty — BR-BIL-004 says an issued bill
    # is never re-billed, and that check is reached BEFORE the BR-BIL-005 run
    # key. The `already_billed_at_the_cut` branch is the one that catches a race
    # where two callers open the same window at once; it cannot be reached from
    # here because the first bill closed the window.
    assert second.outcome in ("nothing_to_bill", "already_billed_at_the_cut")
    assert second.billed is True  # either way, the days ARE billed
    assert second.invoice_id != first["cut_bill"]["invoice_id"] or second.invoice_id is None
    # ONE metered bill and ONE metered run for this window, after three attempts.
    assert invoices.count() == 1
    assert runs.count() == 1
    assert str(invoices.first().pk) == first["cut_bill"]["invoice_id"]


# ════════════════════════════════════════════════════════════════════════════
# THE SETTLEMENT — $612.75 IN, NOTHING WRITTEN OFF, THE ACCOUNT STILL OPEN
# ════════════════════════════════════════════════════════════════════════════
def test_the_cut_settles_and_leaves_the_remainder_outstanding(brazos, marcus, monkeypatch):
    """**PO verbatim:** *"outstanding is pending on account if any"*.

    `A-11488` is cut owing **$612.75**. The cut adds the final metered bill and
    the **$75.00** reconnection fee, and every cent of it stays OUTSTANDING on an
    account that is still open. `DSC-02.4`'s two prohibitions are what make this
    a settlement and not a move-out: the deposit is untouched and nothing is
    written off.

    ⚠ The recorded figure comes from the LEDGER seam, which this suite stubs at
    `$612.75` (`_owes`) exactly as every other W7 test does — so what is proved
    here is that the cut RECORDS the position it read and moves none of it, not
    that the ledger arithmetic is right, which is `apps/ledger`'s own suite.
    """
    with tenant_ctx(brazos):
        account, _unit = _a11488(marcus, brazos, monkeypatch)
        before = customers_models.Account.objects.get(id=account.id)
        deposit_before, closed_before = before.deposit_on_file, before.closed_at
        cut = disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)
        case = disconnects.DisconnectCase.objects.get(account_id=account.id)
        row = customers_models.Account.objects.get(id=account.id)

    assert case.outstanding_at_cut == ARREARS
    assert cut["settlement"]["outstanding"]["stored"] == "612.7500"
    assert cut["settlement"]["outstanding"]["display"] == "612.75"
    assert cut["settlement"]["currency"] == "USD"  # rule 2 — never without it
    # `DSC-02.4` — no close, no deposit settlement, nothing written off.
    assert (row.deposit_on_file, row.closed_at) == (deposit_before, closed_before)
    assert case.status_before_cut == "active"


# ════════════════════════════════════════════════════════════════════════════
# OQ-1170's SECOND HALF — THE CUT THAT CAN BE UN-CUT
# ════════════════════════════════════════════════════════════════════════════
def test_restoring_puts_back_the_status_held_before_the_cut(brazos, marcus, monkeypatch):
    """**The account comes back as Active** (PO 2026-10-29, *"2A"*,
    `DEF-CUS-10668`; until then: *"the billable status it held before the cut"*,
    which on this fixture is the same word — `test_def_cus_10668_restored_is_active`
    holds the case where the two differ).

    The test that matters is the last one: **the restored account is back IN the
    bill run.** Without the status write, a customer whose supply was turned back
    on would have been `non_billable` for ever, silently, and nobody would have
    noticed until a year of bills was missing.
    """
    with tenant_ctx(brazos):
        account, unit = _a11488(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)
        cut_row = customers_models.Account.objects.get(id=account.id)
        assert cut_row.status.code == "disconnected"

        _owes(monkeypatch, D("0.00"))
        disconnects.mark_reconnecting(marcus, account.id, on_date=RECONNECT_ON)
        restored = disconnects.restore_service(marcus, account.id, on_date=RESTORE_ON)
        row = customers_models.Account.objects.get(id=account.id)
        scoped = [str(r.id) for r in customers_selectors.accounts_for_bill_run([str(unit["id"])])]

    assert restored["state"] == disconnects.STATE_RESTORED
    assert restored["account_status_restored_to"] == "active"
    assert "account_status_restore" not in restored  # nothing was unresolvable
    assert row.status.code == "active"
    assert row.status.behavior_class == customers_services.CLASS_BILLABLE
    # THE ONE THAT MATTERS: service is back on and so is the bill run.
    assert scoped == [str(account.id)]


def test_a_restoration_with_nothing_recorded_still_returns_to_active(
    brazos, marcus, monkeypatch
):
    """A case cut BEFORE the ruling of 2026-08-30 has no `status_before_cut` —
    0034 backfills nothing. Until `DEF-CUS-10668` (PO 2026-10-29, *"2A"*) that
    left the account `disconnected` and reported an absence; the pre-cut status
    no longer decides anything, so it comes back Active like any other.
    """
    with tenant_ctx(brazos):
        account, _unit = _a11488(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)
        disconnects.DisconnectCase.objects.filter(account_id=account.id).update(
            status_before_cut=None
        )
        _owes(monkeypatch, D("0.00"))
        disconnects.mark_reconnecting(marcus, account.id, on_date=RECONNECT_ON)
        restored = disconnects.restore_service(marcus, account.id, on_date=RESTORE_ON)
        row = customers_models.Account.objects.get(id=account.id)

    assert restored["account_status_restored_to"] == "active"
    assert "account_status_restore" not in restored
    assert row.status.code == "active"


def test_a_tenant_with_no_live_active_status_keeps_the_status_and_says_why(
    brazos, marcus, monkeypatch
):
    """The one thing that can still stop the write: no live `active` row.
    Nothing else is chosen — the account keeps its status, service is restored,
    and `RESTORED_STATUS_NOT_RECORDED` names the reason."""
    with tenant_ctx(brazos):
        account, _unit = _a11488(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)
        _owes(monkeypatch, D("0.00"))
        disconnects.mark_reconnecting(marcus, account.id, on_date=RECONNECT_ON)
        customers_models.AccountStatus.objects.filter(
            tenant_id=brazos.id, code="active"
        ).update(active=False)
        restored = disconnects.restore_service(marcus, account.id, on_date=RESTORE_ON)
        row = customers_models.Account.objects.get(id=account.id)

    assert restored["state"] == disconnects.STATE_RESTORED
    assert restored["account_status_restored_to"] is None
    assert restored["account_status_restore"]["code"] == "status_before_cut_not_resolvable"
    assert row.status.code == "disconnected"  # untouched, and REPORTED


# ════════════════════════════════════════════════════════════════════════════
# CLAUDE.md RULE 1 — TENANT SCOPING ON THE BILL THIS CHANGE CREATES
# ════════════════════════════════════════════════════════════════════════════
def test_another_tenant_cannot_see_the_bill_the_cut_raised(brazos, lonestar, marcus, monkeypatch):
    """CLAUDE.md rule 1 — no queryset crosses a tenant. The cut bill is the new
    financial record this change creates, so it is the one proved isolated.

    ⚠ **ASKED THROUGH A TENANT-SCOPED READ AND NOT THROUGH `Invoice.objects`.**
    RLS `FORCE` is the real guarantee and it lives in PostgreSQL, while this
    suite runs on the in-memory SQLite `config/settings/test.py` hardcodes — so
    a bare `Invoice.objects.filter(id=...)` would prove nothing here and would
    look like proof (hard-won law 14's neighbour: a check that cannot fail).
    `billing.selectors.last_issued_invoice_date` narrows on
    `core.tenancy.current_tenant_id()` in its own query, which is the isolation
    this test can actually assert on either database.
    """
    from apps.billing import selectors as billing_selectors

    with tenant_ctx(brazos):
        account, _unit = _a11488(marcus, brazos, monkeypatch)
        cut = disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)
        assert cut["cut_bill"]["outcome"] == "raised"
        mine = billing_selectors.last_issued_invoice_date(account.id)
        rows = billing_selectors.last_issued_invoice_dates([str(account.id)])
    with tenant_ctx(lonestar):
        theirs = billing_selectors.last_issued_invoice_date(account.id)
        their_rows = billing_selectors.last_issued_invoice_dates([str(account.id)])

    assert mine is not None  # brazos can see the bill its own cut raised
    assert rows.get(str(account.id)) is not None
    assert theirs is None  # lonestar cannot, and gets an ABSENCE, not an error
    assert their_rows.get(str(account.id)) is None
