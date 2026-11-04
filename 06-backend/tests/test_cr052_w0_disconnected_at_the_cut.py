# ── Trace ──────────────────────────────────────────────
# Story:    CR-052 wave W0, tasks 1, 2 and 3   Screens: S90 (the disconnects tab)
# Rules:    BR-CUS-107 (a cut account gets the sixth status, `Disconnected`,
#           class `non_billable`) · BR-CUS-110 (a cut ENDS occupancy and the
#           debt follows the person — PO 2026-08-26, closing OQ-386) ·
#           BR-CUS-103 (base is billed right up to the cut) · BR-CUS-055
#           (billability is a CLASS, never a label) · BR-CUS-430/431 (the
#           close-out door) · `DSC-02.4` · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 4 (financial immutability — a disconnection changes a STATUS,
#           never a debt)
# Tests:    this file
# Rule:     **PO ruling 2026-08-30 — THE DISCONNECT IS THE WHOLE EVENT**,
#           closing OQ-1170: *"when we disconnect - we generate final bill at
#           that time itself - so later bill is not required ... entire workflow
#           including all settlement and status update is taken care at time of
#           disconnect or move out - so account status changes and outstanding
#           is pending on account if any"*
# Impacts:  apps/customers/disconnects.py (DISCONNECTED_STATUS_ASSIGNED ·
#           CUT_BILL_BLOCKED_SO_STATUS_HELD · RESTORED_STATUS_NOT_RECORDED) ·
#           apps/billing/cut_bill.py (the seam) ·
#           apps/customers/close_out.py (DISCONNECTED_IS_NOT_CLOSED)
# ───────────────────────────────────────────────────────
"""CR-052 W0 — `Disconnected` at the cut. **BUILT 2026-08-31.**

CR-052 tasks 1-3 ask for three things: assign BR-CUS-107's seeded status at the
cut (1), handle the two measured consequences of the `non_billable` class (2),
and prove that an account cut owing **$612.75** still owes $612.75, accrues
nothing and can be taken back (3).

⚠ **THIS FILE USED TO SAY "TASK 1 IS NOT DONE HERE AND THIS FILE IS WHY".** It
measured, correctly, that assigning the status cost a customer-facing bill: the
account leaves `selectors.accounts_for_bill_run` and the days it used BEFORE the
cut are billed to nobody — **$23.23** of a **$40.00** monthly base on `A-11488`,
cut 18 August (18 days of 31), plus every gallon and every kWh. That was
`OQ-1170`, and it is CLOSED.

**PO ruling 2026-08-30 — THE DISCONNECT IS THE WHOLE EVENT**, verbatim: *"when
we disconnect - we generate final bill at that time itself - so later bill is not
required ... entire workflow including all settlement and status update is taken
care at time of disconnect or move out - so account status changes and
outstanding is pending on account if any"*.

So the collision was an artefact of billing LATE and the ruling removes the
lateness. Neither signed rule gives way: BR-CUS-103 keeps its words exactly
(*"a service is billed base right up to the moment it is cut"*) because those
days are now billed AT the cut, and BR-CUS-107 writes `Disconnected`
immediately, because nothing is left for the next run to do.

════════════════════════════════════════════════════════════════════════════
THE ONE INVARIANT THIS FILE EXISTS FOR, AND IT HAS TWO BRANCHES
════════════════════════════════════════════════════════════════════════════
    **The days before a cut are never billed by nobody.**

  * **The bill is RAISED** → the status is written, the account leaves the run,
    and the days are on an issued invoice. `test_the_days_before_the_cut_are
    _never_billed_by_nobody` proves this branch, and the **$23.23** is run end
    to end in `tests/test_cr052_w0_the_23_23_case.py`.
  * **Billing REFUSES the account** — no tariff version in force at the service
    date, no plan, no recorded move-in date — → **the status is NOT written**,
    the account stays billable and stays in the run, and the ordinary run bills
    those days once a human fixes the configuration. `disconnects.
    CUT_BILL_BLOCKED_SO_STATUS_HELD` is that rule, by name.

The second branch is what the W7 ladder fixture below exercises, because its
tariff has no version in force — which makes it the right fixture for exactly
that half and the wrong one for the money, and both halves are proved rather
than assumed.

════════════════════════════════════════════════════════════════════════════
THE RULED HALF OF TASK 2 IS ALREADY CORRECT, AND THAT IS ASSERTED NOT ASSUMED
════════════════════════════════════════════════════════════════════════════
BR-CUS-110 (PO 2026-08-26, closing OQ-386, verbatim *"B Yes, a cut ends
occupancy and the debt follows the person"*) rules that
`OCCUPYING_BEHAVIOR_CLASSES` is CORRECT AS WRITTEN, so the unit reading vacant
is the INTENDED behaviour rather than a hazard.
`test_the_cut_account_stops_occupying_and_the_unit_reads_vacant` proves the
whole consequence chain in one place, and `test_the_terminal_path_exists`
proves the half DEF-724 closed — because "the unit is free" is only safe if the
cut customer can still reach an end.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import close_out as close_out_service
from apps.customers import disconnects
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    erin,
    lonestar,
    marcus,
    tenant_ctx,
)
from tests.test_cr052_w0_the_23_23_case import (
    _a11488,
)

# ⚠ `_publish_the_august_cycle` IS GONE — `DEF-2708`, 2026-08-31. It stubbed
# `apps.metering.selectors.billing_period_for_unit`, which did not exist; the
# read is published now, so `_a11488` CONFIGURES the cycle and the calls that
# used to precede it are simply deleted. Nothing about these cases changed.

from tests.test_cr052_w0_the_23_23_case import CUT_ON as A11488_CUT_ON
from tests.test_cr052_w0_the_23_23_case import RECONNECT_ON as A11488_RECONNECT_ON
from tests.test_cr052_w0_the_23_23_case import RESTORE_ON as A11488_RESTORE_ON
from tests.test_w7_cut_reconnect import CUT_ON, TODAY, _scheduled
from tests.test_w7_disconnects import _owes

pytestmark = pytest.mark.django_db

#: `A-11488` — the account BR-CUS-107, BR-CUS-110, OQ-386 and DEF-724 were every
#: one of them put to the PO with: cut owing **$612.75**, 12 Foundry Row.
#: CR-052 task 3 names the same figure and this file reproduces it exactly.
OWED = D("612.75")

#: The month `A-11488` is dark for the whole of. The cut is 18 August, so
#: September is the first period in which a still-billable account would be
#: charged a full base — which is exactly what must not happen.
SEPTEMBER_START = date(2026, 9, 1)
SEPTEMBER_END = date(2026, 9, 30)
#: And the month after the restoration (15 September), in which it must be
#: billed again, because a customer whose supply is back on is a paying one.
OCTOBER_START = date(2026, 10, 1)
OCTOBER_END = date(2026, 10, 31)

#: The W7 ladder fixture walks to a lawful cut on 2026-08-24. BR-CUS-107's own
#: worked case says 2026-08-18; the DATE is the fixture's and the FIGURE is the
#: ruling's, which is `test_def724_close_out.py`'s split and is kept here so the
#: two files cannot drift into two different $612.75 accounts.
RECONNECT_ON = date(2026, 9, 12)
RESTORE_ON = date(2026, 9, 15)
CLOSED_OUT_ON = date(2026, 9, 30)


@pytest.fixture(autouse=True)
def _fee_seam_answers(monkeypatch):
    """`commit_cut` raises the reconnection fee through BILLING's service.

    Stubbed AT THE MODULE BOUNDARY, which is not a convenience: BR-CUS-037 makes
    the fee billing's to raise, and a customers test that depended on billing's
    invoice internals would be asserting another module's contract. `_owes`
    stubs `seams.ar_positions` in the same place for the same reason.
    """
    monkeypatch.setattr(
        disconnects.seams,
        "raise_and_issue_charge_fee",
        lambda *_a, **_k: {"invoice_id": None, "stubbed_at": "the customers/billing seam"},
    )


def _cut(actor, tenant, monkeypatch, *, owed=OWED, label="Unit A"):
    """A really-cut account: the whole W7 ladder walked, then `commit_cut`."""
    account = _scheduled(actor, tenant, monkeypatch, owed=owed, label=label)
    disconnects.commit_cut(actor, account["id"], cut_on=CUT_ON, as_of=TODAY)
    return account


def _cycle_id_for(unit):
    """The cycle `A-11488`'s service point is on, read through metering's rows.

    Taken from the SERVICE POINT rather than passed in, because that is where
    `runs.prepare_run` looks and a fixture that named its own cycle could pass
    while the product scoped a different one.
    """
    from apps.metering import models as metering_models

    point = metering_models.ServicePoint.objects.filter(unit_id=unit["id"]).first()
    assert point is not None and point.cycle_id is not None, unit
    return point.cycle_id


def _row(account_id):
    return customers_models.Account.objects.get(id=account_id)


def _make_it_disconnected(account_id):
    """Assign BR-CUS-107's seeded `Disconnected` status.

    ✅ **THE PRODUCT DOES THIS NOW** — `commit_cut` writes it in the same act
    that raises the final bill (CR-052 task 1, PO ruling 2026-08-30). This
    helper survives for the cases below whose fixture billing REFUSES: on the
    W7 ladder account the tariff has no version in force at the service date, so
    the cut bill is blocked and the status is deliberately HELD
    (`CUT_BILL_BLOCKED_SO_STATUS_HELD`). Those cases are about what the STATUS
    does to occupancy, to the unit and to the terminal path, so they still need
    to stand in the world where it was written — and they say so here rather
    than looking like the product.
    """
    row = _row(account_id)
    row.status = customers_models.AccountStatus.objects.get(
        tenant_id=row.tenant_id, code="disconnected"
    )
    row.save(update_fields=["status", "updated_at"])
    return row


# ════════════════════════════════════════════════════════════════════════════
# TASK 1 — BUILT. THE STATUS, AND THE ONE CASE WHERE IT IS DELIBERATELY HELD.
# ════════════════════════════════════════════════════════════════════════════
def test_the_seeded_status_is_assigned_at_the_cut(brazos, marcus, monkeypatch):
    """BR-CUS-107's seeded row, written by `commit_cut` — **DEF-701, closed.**

    ⚠ **THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-08-31, AND IT WAS RIGHT TO.**
    It read: *"BR-CUS-107's row is seeded and `commit_cut` still writes no
    `accounts` column"*, and measured that a cut customer's pill still said
    **Active** — worse than DEF-701's own report of *"Marked disconnect"*,
    because no code path ever wrote that either. DEF-705's lesson one week
    earlier is why it is re-pointed here rather than left green beside a
    reversed rule.

    The account is `A-11488` on a real, priceable plan, so the final bill can be
    raised and the status is therefore lawful to write. The blocked branch is
    the test below.
    """
    with tenant_ctx(brazos):
        seeded = customers_models.AccountStatus.objects.get(
            tenant_id=brazos.id, code="disconnected"
        )
        assert seeded.behavior_class == customers_services.CLASS_NON_BILLABLE
        account, _unit = _a11488(marcus, brazos, monkeypatch)
        cut = disconnects.commit_cut(marcus, account.id, cut_on=A11488_CUT_ON, as_of=A11488_CUT_ON)
        row = _row(account.id)
    assert cut["cut_bill"]["outcome"] == "raised"
    assert row.status.code == "disconnected"
    assert row.status.behavior_class == customers_services.CLASS_NON_BILLABLE


def test_a_cut_billing_cannot_bill_holds_the_status_and_says_why(brazos, marcus, monkeypatch):
    """**THE SAFETY RULE, ON THE FIXTURE THAT NATURALLY TRIPS IT.**

    The W7 ladder account is on a plan whose tariff has **no version in force at
    the service date**, so billing refuses it by name — exactly as it would on
    the phase-3 exception list of an ordinary cycle run. The cut still HAPPENS
    (a household's supply is not left connected because a tariff is
    unconfigured) and the status is NOT written, so the account stays billable,
    stays in the run, and those days remain somebody's to bill.

    Writing the status here is the whole of `OQ-1170`'s $23.23, and this is the
    test that stops a later lane doing it for tidiness.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        cut = disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        row = _row(account["id"])
        unit_id = str(row.unit_id)
        scoped = [str(r.id) for r in customers_selectors.accounts_for_bill_run([unit_id])]
    assert cut["state"] == disconnects.STATE_CUT  # the cut happened
    assert cut["cut_bill"]["outcome"] == "blocked"
    assert cut["cut_bill"]["billed"] is False
    # `DEF-CUS-9060` — the ladder account has no meter, and since 2026-09-30
    # (`31358c239`, BR-BIL-300/301) a service with no meter is NOT IN SERVICE,
    # so the plan resolves to nothing billable and the gather says THAT, by
    # name. It read *"no tariff version is in force"* until then. The rule this
    # case guards — refused by name, status not written — is unchanged.
    assert "resolves to no tariff for any service" in cut["cut_bill"]["detail"]
    assert cut["account_status_written"] is None
    assert cut["account_status_held"]["code"] == "cut_bill_blocked_status_not_written"
    # …so the account is still billable and still in the run.
    assert row.status.behavior_class == customers_services.CLASS_BILLABLE
    assert scoped == [str(account["id"])]


def test_the_blocker_is_customers_own_scope_seam_not_billings_stage(brazos, marcus, monkeypatch):
    """**THE CORRECTION. → DEF-2640.**

    Four places in this repository say billing's `CLASSES_THAT_BILL` is what
    drops a `Disconnected` account, and that it is therefore a change customers
    may not make. Measured here: the account is dropped by
    `customers.selectors.accounts_for_bill_run`, one module earlier, and never
    reaches billing at all.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        unit_id = str(_row(account["id"]).unit_id)

        # BEFORE: a cut account is in the run — which is what makes BR-CUS-103's
        # dark-day subtraction reachable.
        before = [str(row.id) for row in customers_selectors.accounts_for_bill_run([unit_id])]
        assert str(account["id"]) in before

        _make_it_disconnected(account["id"])

        # AFTER: gone from the run's SCOPE. Silently — `accounts_for_bill_run`'s
        # own docstring says excluded classes are excluded silently on purpose.
        after = [str(row.id) for row in customers_selectors.accounts_for_bill_run([unit_id])]
    assert after == []
    # And the constant that actually did it is CUSTOMERS'.
    assert (
        customers_services.CLASS_NON_BILLABLE not in customers_services.OCCUPYING_BEHAVIOR_CLASSES
    )
    assert customers_selectors.accounts_for_bill_run.__module__ == "apps.customers.selectors"


def test_the_days_before_the_cut_are_never_billed_by_nobody(brazos, marcus, monkeypatch):
    """**`OQ-1170`'s MONEY, CLOSED — and this test is its supersession.**

    ⚠ **IT WAS CALLED `test_the_days_before_the_cut_are_billed_by_nobody` AND IT
    ASSERTED EXACTLY THAT.** Written to measure the defect, it ended
    `assert scoped == []` on an account whose pre-cut days nobody had billed. On
    the PO's own case that is **$23.23** of a **$40.00** monthly base — 18 days
    of 31 — plus every gallon and every kWh, on `A-11488`, cut 18 August. Left
    as it was, it would now be a green test pinning a reversed rule, which is
    DEF-705's lesson and the reason it is re-pointed in the same change.

    **PO ruling 2026-08-30:** *"when we disconnect - we generate final bill at
    that time itself - so later bill is not required"*. So the invariant is:

        THE DAYS BEFORE A CUT ARE NEVER BILLED BY NOBODY.

    and it has two branches, both asserted here in one place because the whole
    hazard is a lane satisfying one and forgetting the other:

      * billing CAN bill → the bill is issued for 1 → 18 August and the account
        leaves the run, which is now correct;
      * billing REFUSES → the status is held, and the account is still in the
        run with those days still to bill.

    The **$23.23** itself is run end to end, off `invoice_lines`, in
    `tests/test_cr052_w0_the_23_23_case.py`. Here the question is only *does
    anybody own these days*, and the answer must be yes on both branches.
    """
    with tenant_ctx(brazos):
        # ── BRANCH 1 · the bill is raised, so the account may leave the run ──
        billable, unit = _a11488(marcus, brazos, monkeypatch)
        cut = disconnects.commit_cut(marcus, billable.id, cut_on=A11488_CUT_ON, as_of=A11488_CUT_ON)
        billed_scope = list(customers_selectors.accounts_for_bill_run([str(unit["id"])]))
        windows = disconnects.service_off_windows(billable.id)

        # ── BRANCH 2 · billing refuses, so the account MUST stay in the run ──
        blocked_account = _scheduled(marcus, brazos, monkeypatch, label="Unit B")
        blocked_cut = disconnects.commit_cut(
            marcus, blocked_account["id"], cut_on=CUT_ON, as_of=TODAY
        )
        blocked_unit = str(_row(blocked_account["id"]).unit_id)
        blocked_scope = [
            str(r.id) for r in customers_selectors.accounts_for_bill_run([blocked_unit])
        ]

    # BRANCH 1 — somebody owns the days: an ISSUED bill does.
    assert cut["cut_bill"]["outcome"] == "raised"
    assert (cut["cut_bill"]["period_start"], cut["cut_bill"]["period_end"]) == (
        "2026-08-01",
        "2026-08-18",
    )
    assert cut["cut_bill"]["service_days"] == 18
    assert billed_scope == []  # out of the run, AFTER the bill — correct now
    # BR-CUS-103's own mechanism is intact and still serves the cut DAY: the
    # first dark day is the day AFTER the cut, which is why 18 days are billed.
    assert len(windows) == 1
    assert windows[0]["off_from"] == date(2026, 8, 19)
    assert windows[0]["off_through"] is None

    # BRANCH 2 — somebody owns the days: the next ordinary run does.
    assert blocked_cut["cut_bill"]["outcome"] == "blocked"
    assert blocked_cut["account_status_written"] is None
    assert blocked_scope == [str(blocked_account["id"])]


def test_restoring_puts_the_account_status_back(brazos, marcus, monkeypatch):
    """**`OQ-1170`'s SECOND HALF — the cut that CAN be un-cut.**

    ⚠ **IT WAS CALLED `test_restoring_writes_no_account_status` AND IT ASSERTED
    EXACTLY THAT**: `restore_service` wrote `reconnected_on` and touched no
    account column, so an implementation that wrote `Disconnected` at the cut
    and stopped there would leave a RECONNECTED customer `non_billable` for
    ever — outside every bill run, silently, until a year of bills was missing.
    Re-pointed with the rule it measured (DEF-705).

    **The account returns to the billable status it held before the cut.**
    DERIVED, not asked (CLAUDE.md law 13): `mark_reconnecting` refuses with
    `not_settled` while a cent is owed and records `settled_balance` when it
    succeeds, so `RECONNECTING → RESTORED` is only reachable on a settled
    account and the debt that would justify `Marked disconnect` cannot exist by
    then.

    The last assertion is the one that matters: **the restored account is back
    IN the bill run.**
    """
    with tenant_ctx(brazos):
        account, unit = _a11488(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account.id, cut_on=A11488_CUT_ON, as_of=A11488_CUT_ON)
        assert _row(account.id).status.code == "disconnected"

        _owes(monkeypatch, D("0.00"))
        disconnects.mark_reconnecting(marcus, account.id, on_date=A11488_RECONNECT_ON)
        restored = disconnects.restore_service(marcus, account.id, on_date=A11488_RESTORE_ON)
        row = _row(account.id)
        scoped = [str(r.id) for r in customers_selectors.accounts_for_bill_run([str(unit["id"])])]
    assert restored["account_status_restored_to"] == "active"
    assert row.status.code == "active"
    assert row.status.behavior_class == customers_services.CLASS_BILLABLE
    # Service is back on and so is the bill run.
    assert scoped == [str(account.id)]


# ════════════════════════════════════════════════════════════════════════════
# TASK 2 — THE TWO CONSEQUENCES. BR-CUS-110 RULED THE FIRST; IT IS PROVED HERE.
# ════════════════════════════════════════════════════════════════════════════
def test_the_cut_account_stops_occupying_and_the_unit_reads_vacant(brazos, marcus, monkeypatch):
    """CR-052 task 2, both halves, in the order the task names them.

    BR-CUS-110 (PO 2026-08-26): *"B Yes, a cut ends occupancy and the debt
    follows the person"*. So this is the INTENDED behaviour, not the hazard the
    2026-08-25 notes in `services.py` and `disconnects.py` still call it — those
    two comments are corrected in this same change.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        unit_id = str(_row(account["id"]).unit_id)

        # Occupying, before.
        assert customers_selectors.active_account_for_unit(unit_id) is not None

        _make_it_disconnected(account["id"])

        # (a) the account stops occupying its unit …
        occupying = [
            str(row.id) for row in customers_selectors.occupying_accounts_for_unit(unit_id)
        ]
        # (b) … and the unit reads vacant.
        vacant = customers_selectors.active_account_for_unit(unit_id)
    assert occupying == []
    assert vacant is None


def test_metering_reads_the_same_vacancy_through_the_published_seam(brazos, marcus, monkeypatch):
    """The consequence lands in METERING and travels through metering's own
    door — never a cross-module read of `accounts` (B1 / B2 §2).

    `metering.seams.occupying_account_status_codes` resolves customers'
    vocabulary by name and answers the CODES that occupy. `disconnected` must
    not be among them, or BR-MET-036's `vacant_unit` reading and this module's
    disagree.

    ⚠ **IT ANSWERS THROUGH ITS FALLBACK, AND THAT IS REPORTED (→ DEF-2641).**
    Metering documents TWO doors and prefers the first:
    `apps.customers.selectors.occupying_status_codes()`, *"the documented
    contract, and the ONLY one that can see a status this tenant added or
    renamed"*. **Customers has never authored it**, so every caller falls
    through to door 2 — the seeded CONSTANTS — which by metering's own
    admission cannot see a tenant-added status or a seeded one whose class a
    tenant changed. It is right for `disconnected` (a PLATFORM-seeded row) and
    that is what this asserts; it is not right in general, and door 1 cannot be
    published without a metering-side change, because metering's door-1 branch
    iterates the result and so cannot carry the `None` its own contract
    requires.
    """
    from apps.metering import seams as metering_seams

    with tenant_ctx(brazos):
        _cut(marcus, brazos, monkeypatch)
        codes = metering_seams.occupying_account_status_codes()
    assert codes is not None
    assert "disconnected" not in codes
    assert {"active", "marked_disconnect", "vacation_hold"} <= set(codes)
    # Door 1 is still unauthored — the fallback above is what answered.
    assert not hasattr(customers_selectors, "occupying_status_codes")


def test_the_terminal_path_exists(brazos, marcus, monkeypatch):
    """DEF-724, closed 2026-08-27 — and re-proved here rather than quoted.

    "The unit is free" is only safe if the cut customer can still reach an end.
    `move_out` refuses them (correctly — BR-CUS-430 keeps the two doors
    disjoint) and `close_out` finishes it.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        assert close_out_service.eligibility(account["id"])["eligible"] is True
        close_out_service.close_out(
            marcus,
            account["id"],
            {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "settled and gone"},
        )
        row = _row(account["id"])
    assert row.status.behavior_class == customers_services.CLASS_TERMINAL
    assert row.closed_at is not None


# ════════════════════════════════════════════════════════════════════════════
# TASK 3 — THE REGRESSION. $612.75, THREE ASSERTIONS, ONE ACCOUNT.
# ════════════════════════════════════════════════════════════════════════════
def test_cut_owing_612_75_still_owes_it_accrues_nothing_and_can_be_taken_back(
    brazos, marcus, monkeypatch
):
    """CR-052 task 3, verbatim: *"an account cut owing `$612.75` still owes
    `$612.75`, accrues nothing, and can be taken back"*.

    Three assertions, and the third is the one that catches a bad
    implementation: a cut that cannot be reversed is data loss dressed as a
    status change.

      1. **STILL OWES $612.75** — CLAUDE.md hard rule 4. A disconnection changes
         a STATUS; it never touches an issued invoice, a payment or a journal
         line, so the debt is exactly what it was. Read through the ledger seam,
         at 4 decimals, with its CHAR(3) partner.
      2. **ACCRUES NOTHING** — BR-CUS-103 (PO 2026-08-25, OQ-380, *"no"*). The
         cut opens an OPEN-ENDED dark window from the day after the cut, which
         is the fact billing subtracts. `CUT_STOPS_BASE` travels on the payload
         so a caller cannot miss it.
      3. **CAN BE TAKEN BACK** — the account is not closed and not written off:
         once the $612.75 is settled, `mark_reconnecting` and `restore_service`
         still walk it home. The `Disconnected` status does not close that door,
         which is BR-CUS-107's own ⚠ clause (*a `non_billable` account MUST
         still accept a PAYMENT*) holding.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])

        # ── 1 · STILL OWES $612.75 ──────────────────────────────────────────
        owed_after_the_cut = disconnects._balance_for(account["id"])
        positions = disconnects.seams.ar_positions([account["id"]])

        # ── 2 · ACCRUES NOTHING ─────────────────────────────────────────────
        windows = disconnects.service_off_windows(account["id"])
        case = disconnects.open_case_for(account["id"])
        payload = disconnects.cut_payload(case)

        # ── 3 · CAN BE TAKEN BACK ───────────────────────────────────────────
        # ⛔ **RE-POINTED 2026-09-25 — THIS BLOCK ASSERTED A REFUSAL THAT IS
        # SUPERSEDED (`BR-CUS-1097`, `DEF-CUS-6735`).** It read *"refused while
        # the money is outstanding — `DSC-02.4` blocks new service until it is
        # settled"*. That drawn line went to the PO under B14 rule 41 and the
        # answer was **"Show what's still owed and let the clerk proceed"**.
        # The $612.75 is now STATED where it used to refuse, which is what
        # `still_owing` holds below.
        still_owing = disconnects.reconnection_readiness(account["id"])
        _owes(monkeypatch, D("0.00"))
        reconnecting = disconnects.mark_reconnecting(marcus, account["id"], on_date=RECONNECT_ON)
        restored = disconnects.restore_service(marcus, account["id"], on_date=RESTORE_ON)
        row = _row(account["id"])

    # 1 ─────────────────────────────────────────────────────────────────────
    assert owed_after_the_cut == OWED
    assert str(owed_after_the_cut) == "612.75"
    assert positions.currency == "USD"
    assert row.closed_at is None  # cut, not closed: the debt has somewhere to live

    # 2 ─────────────────────────────────────────────────────────────────────
    assert len(windows) == 1
    assert windows[0]["off_from"] == date(2026, 8, 25)
    assert windows[0]["off_through"] is None
    assert payload["accrual"] == dict(disconnects.CUT_STOPS_BASE)
    assert payload["account_open"] is True

    # 3 ─────────────────────────────────────────────────────────────────────
    assert still_owing["ready"] is True
    assert [w["code"] for w in still_owing["warnings"]] == ["money_still_owed"]
    assert still_owing["balance"]["display"] == "612.75"
    assert reconnecting["state"] == disconnects.STATE_RECONNECTING
    assert restored["state"] == disconnects.STATE_RESTORED
    assert restored["reconnected_on"] == str(RESTORE_ON)
    assert restored["leaves_the_tab"] is True


def test_accrues_nothing_MEASURED_BY_RUNNING_THE_THING_THAT_WOULD_ACCRUE(
    brazos, marcus, monkeypatch
):
    """CR-052 task 3's middle assertion, run rather than described.

    ⚠ **EVERY OTHER PROOF OF "ACCRUES NOTHING" IN THIS REPO READS A PAYLOAD, AND
    A PAYLOAD IS THE CODE DESCRIBING ITSELF.** The case above asserts
    `payload["accrual"] == CUT_STOPS_BASE` and an open-ended dark window from
    `cut_on + 1`; `test_cr052_w0_the_23_23_case.py` asserts the settlement
    RECORDS the position and moves none of it. Both are true and neither runs
    the one thing that could actually charge this customer again — **a bill
    run over the month after the cut.** A constant named `CUT_STOPS_BASE` that
    travels on a response is a statement of intent (hard-won law 1: a comment
    claiming a guarantee is not the guarantee), and the guarantee is that the
    SEPTEMBER run bills nobody for this account.

    `A-11488` is used and not the W7 ladder account, deliberately: the ladder's
    tariff has no version in force, so billing refuses it for a reason that has
    nothing to do with the cut, and a run that bills it nothing would prove
    nothing at all. `A-11488` is on a real `$40.00` plan that the AUGUST run
    priced to `$23.23`, so if the September run charges it, it charges it for
    real.

    **THREE THINGS, IN THE ORDER THEY MATTER:**

      1. the cut account is not in September's run at all — it never reaches a
         pricing stage, because `accounts_for_bill_run` drops it a module
         earlier (`DEF-2640`);
      2. **NO INVOICE EXISTS FOR IT** with a period after the cut — which is
         the assertion that would still catch a future run that scoped the
         account back in and priced it at `$0.00`, and the count is read off
         `invoices` rather than off any response;
      3. and the AUGUST bill the cut itself raised is still there and still
         issued, so "accrues nothing" has not been achieved by losing the
         money the cut was supposed to collect.
    """
    from apps.billing import models as billing_models
    from apps.billing import runs as billing_runs

    with tenant_ctx(brazos):
        account, unit = _a11488(marcus, brazos, monkeypatch)
        cut = disconnects.commit_cut(
            marcus, account.id, cut_on=A11488_CUT_ON, as_of=A11488_CUT_ON
        )
        assert cut["cut_bill"]["outcome"] == "raised", cut["cut_bill"]

        cut_invoices = list(
            billing_models.Invoice.objects.filter(account_id=account.id).values_list(
                "id", flat=True
            )
        )

        # ── SEPTEMBER. The month the customer is dark for all of. ──────────
        cycle_id = _cycle_id_for(unit)
        prepared = billing_runs.prepare_run(
            cycle_id=cycle_id,
            period_start=SEPTEMBER_START,
            period_end=SEPTEMBER_END,
            service_date=SEPTEMBER_END,
        )
        scoped = [row.account_no for row in prepared.ready] + [
            getattr(row, "account_no", None) for row in getattr(prepared, "blocked", ())
        ]
        after = list(
            billing_models.Invoice.objects.filter(account_id=account.id).values_list(
                "id", flat=True
            )
        )
        issued_in_august = billing_models.Invoice.objects.filter(
            account_id=account.id, id__in=cut_invoices
        ).count()

    # 1 ─ the cut account is in no part of September's run, ready or blocked.
    assert "A-11488" not in scoped, scoped

    # 2 ─ and no new invoice exists for it. Read off the table, not a response.
    assert after == cut_invoices, "September raised a bill for a cut account"

    # 3 ─ …while the bill the CUT raised is untouched. "Accrues nothing" must
    #     not have been bought by losing the $23.23 the ruling exists to collect.
    assert issued_in_august == len(cut_invoices) >= 1


def test_taken_back_MEANS_BACK_IN_A_REAL_RUN_not_just_a_status(brazos, marcus, monkeypatch):
    """CR-052 task 3's third assertion, taken one step further than a column.

    `test_cr052_w0_the_23_23_case.py::test_restoring_puts_back_the_status_held
    _before_the_cut` proves the status returns and that `accounts_for_bill_run`
    lists the account again. **That is the SCOPE seam, which is one module's
    answer.** This asserts the consequence a customer would notice: after
    `restore_service`, preparing a real run over the next month puts `A-11488`
    back among the accounts it will bill.

    Without this, "can be taken back" could be satisfied by a status write that
    every later run still skipped for some second reason, and the symptom would
    be a reconnected customer who is never billed again — silently, for as long
    as nobody adds the year up.
    """
    from apps.billing import runs as billing_runs

    with tenant_ctx(brazos):
        account, unit = _a11488(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account.id, cut_on=A11488_CUT_ON, as_of=A11488_CUT_ON)
        cycle_id = _cycle_id_for(unit)

        dark = [
            row.account_no
            for row in billing_runs.prepare_run(
                cycle_id=cycle_id,
                period_start=SEPTEMBER_START,
                period_end=SEPTEMBER_END,
                service_date=SEPTEMBER_END,
            ).ready
        ]

        _owes(monkeypatch, D("0.00"))
        disconnects.mark_reconnecting(marcus, account.id, on_date=A11488_RECONNECT_ON)
        disconnects.restore_service(marcus, account.id, on_date=A11488_RESTORE_ON)

        back = [
            row.account_no
            for row in billing_runs.prepare_run(
                cycle_id=cycle_id,
                period_start=OCTOBER_START,
                period_end=OCTOBER_END,
                service_date=OCTOBER_END,
            ).ready
        ]

    assert "A-11488" not in dark
    assert "A-11488" in back


def test_the_cut_writes_no_financial_row_of_its_own(brazos, marcus, monkeypatch):
    """CLAUDE.md hard rule 4 and `DSC-02.4`, stated as properties of the cut.

    ⚠ **AMENDED 2026-08-31 — THE CUT NOW CAUSES TWO INVOICES AND STILL WRITES
    NEITHER.** It said *"it issues no invoice, voids none, and writes nothing to
    `accounts`"*. Since the PO's ruling of 2026-08-30 the cut causes a final
    metered bill AND the reconnection fee, and since `OQ-1170` closed it writes
    `accounts.status`. What has not changed, and is what this test is actually
    for, is that **customers writes no financial table**: both bills are billing's
    (BR-CUS-037), both postings are the ledger's (rule 5), and a disconnection
    still has no path by which it can move an existing debt — no issued invoice
    is edited, no payment is touched, nothing is written off.

    `DSC-02.4`'s two surviving prohibitions are the assertion: `closed_at` and
    `deposit_on_file` do not move. A cut is not a move-out.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        before = _row(account["id"])
        snapshot = (before.status_id, before.closed_at, before.deposit_on_file)
        _make_it_disconnected(account["id"])
        after = _row(account["id"])
    # Only the status moved, and only because this test moved it.
    assert (after.closed_at, after.deposit_on_file) == (snapshot[1], snapshot[2])
    assert after.status_id != snapshot[0]
    # customers writes no financial table — the two bills a cut causes are
    # billing's, raised through published seams, and this module has no writer.
    import inspect

    source = inspect.getsource(disconnects)
    assert "Invoice.objects.create" not in source
    assert "JournalLine" not in source


# ════════════════════════════════════════════════════════════════════════════
# CLAUDE.md RULE 1 — TENANT SCOPING, ON EVERY READ THIS FILE ADDS
# ════════════════════════════════════════════════════════════════════════════
def test_another_tenant_cannot_see_the_cut_accounts_scope_row(
    brazos, lonestar, marcus, monkeypatch
):
    """RLS FORCE is on and no queryset crosses a tenant. The scope seam is the
    one this file leans on hardest, so it is the one proved isolated."""
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        unit_id = str(_row(account["id"]).unit_id)
        assert [str(r.id) for r in customers_selectors.accounts_for_bill_run([unit_id])] == [
            str(account["id"])
        ]
    with tenant_ctx(lonestar):
        assert list(customers_selectors.accounts_for_bill_run([unit_id])) == []
