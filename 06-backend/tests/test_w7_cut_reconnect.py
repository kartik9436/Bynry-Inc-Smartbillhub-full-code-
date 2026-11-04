# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-015 (S22's disconnect-notice modal — the only story that
#           owns any part of this surface; **S90 still has none and one is
#           OWED**, hard-won law 8)
#           Screens: S22 · S90 (`DSC-02.1` … `DSC-02.5`, B18 §5.8)
# Tasks:    CR-030 W7 **7.8 — the cut** (*"danger tier, `audit_log`, base
#           charges keep accruing"*) and **7.9 — the reconnect flow**
# Rules:    BR-CUS-039 (the ladder, certified mail on the final tier) ·
#           BR-CUS-100 (a tier-3 cut needs a recorded proof of service) ·
#           BR-CUS-082 (a closed account cannot be cut) · BR-CUS-055 (the five
#           seeded account statuses and their behaviour classes — none of them
#           is `disconnected`) · BR-CUS-037 (customers writes no financial
#           table) · BR-BIL-007 (*"NSF/reconnect fees are tenant-configured
#           charge codes, never hardcoded"*) · BR-PAY-036 (a payment NEVER
#           auto-changes account status; restoration is an explicit, audited
#           staff action) · BR-PAY-021 (on-time is judged on the POSTING date) ·
#           BR-TEN-043 (the event date is an argument, never a wall clock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money 4dp stored / 2dp
#           displayed) · rule 4 (corrections are new rows) · rule 5 (only the
#           ledger posting service writes journal lines) · rule 7 (audit)
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.8.7 —
#           `DSC-02.1` (five reason cards; *"One decision per service, not all
#           or nothing"*; the restrictor column) · `DSC-02.3` (the CREW banner
#           and the locked earliest-lawful date) · **`DSC-02.4` (the fee table,
#           `What this will do` / `What this will not do`, and the deposit
#           radio) — the specification for 7.8** · `DSC-02.5` (the review step)
#           · §5.8.3's ladder diagram (`CUT → RECONNECTING → restored`) ·
#           §5.8.4 (*"Reconnect is its own short flow"*) · §5.8.5 TC-DSC-7 and
#           TC-DSC-8 · §5.8.6's `A-11507`
# ───────────────────────────────────────────────────────
"""7.8 and 7.9 — the cut, and the path back.

**THE CASE THIS FILE EXISTS FOR IS
`test_tc_dsc_7__the_cut_leaves_the_account_open_and_accruing`**, and it is the
one to read first. `DSC-02.4` prints two columns side by side and the second is
chipped *"Worth being clear about"*:

    WILL                                    WILL NOT
    Cut the services chosen at step 1 on    Close the account or settle the
    the scheduled date, leaving the         deposit — that is a move-out, not
    account open                            a disconnect
    Keep charging base and standing         Stop the balance growing, or write
    charges — a disconnected account        any of it off
    still accrues                           Remove the meter, unless you chose
    Add $75.00 to the balance as the        meter removal as the field work
    price of getting service back
    Move the account into the disconnected
    state, which blocks new service
    elsewhere until it is settled

Every line of the right-hand column is something `commit_cut` could do in one
statement, so the tests assert the ABSENCE of each: the account row is read
before and after and must be byte-identical, and the deposit is untouched.

⚠ **FOUR ASSERTIONS HERE ARE DELIBERATELY NEGATIVE AND MUST STAY THAT WAY.**

  1. `test_a_restrictor_is_refused_and_names_what_it_would_take` asserts that a
     per-service RESTRICTOR raises. B18 draws it as the DEFAULT treatment for
     water and calls it *"what many jurisdictions require"* — so the temptation
     to make this test green by recording a restrictor as a cut is real, and
     doing that would tell a regulator a household's water was stopped when it
     was throttled.
  2. `test_the_cut_reason_is_recorded_and_drives_nothing` asserts that two cuts
     differing only in their reason behave IDENTICALLY. B18 §5.8.7: *"Nothing in
     `disconnects.py` keys off a reason."* Four of the five drawn reasons are
     operational and *"must not require a dunning ladder at all"* — making one
     of them behave differently is a ruling about when a household may be cut
     with no notice served.
  3. `test_paying_does_not_reconnect_by_itself` asserts that a CUT account whose
     balance falls to zero is STILL `cut` until somebody acts. BR-PAY-036:
     *"acceptance NEVER auto-changes account status — restoration stays an
     explicit, audited staff action."* The ladder stops itself; the meter does
     not turn itself back on.
  4. `test_the_new_service_block_is_built_and_consumed_by_nothing` asserts that
     the block exists as a read and that NOTHING calls it. It is green because
     the feature is incomplete, and it says so — hard-won law 2.

**RED PROVED FIRST for every guard** (hard-won law 7). Each was broken under a
`# BREAK: … — RESTORE …` marker, run, the failure quoted in the lane report, and
the mutation reverted — DEF-666 is a lane that died mid-proof and left its
mutation in a shared tree, so no marker survives in this file.
"""

import pathlib
from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnects
from apps.customers import models as customers_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models  # noqa: F401 — parity with the W7 suite

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    audit_rows,
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_w7_disconnects import _account, _at_tier, _owes, _prove_tier_3_service

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 25)

#: `DSC-02.1` … `DSC-02.5`'s own worked case, so a reader can hold this file
#: beside the screen: `A-11340 · Northwind Mfg. · 77 Industrial Way`, **$8,240.00**
#: outstanding, **$500.00** deposit held, tier 3 served **Aug 22** by certified
#: mail, earliest lawful cut **Aug 24**, services *"Cutting electric and sewer ·
#: restricting water"*, reconnection fee **$75.00**.
NORTHWIND_OWED = D("8240.00")
DEPOSIT_HELD_FIGURE = D("500.00")
SERVED_ON = date(2026, 8, 22)
CUT_ON = date(2026, 8, 24)
RECONNECT_FEE = D("75.00")


def _reconnect_charge(tenant, amount=RECONNECT_FEE):
    """The tenant's own `CC-RECON` row — BR-BIL-007, never a literal in code.

    ⚠ **THIS SAID "NO SEED IN THIS REPO CREATES ONE" UNTIL 2026-09-21, AND IT
    WAS TRUE WHEN WRITTEN.** Measured 2026-08-25: `seed_demo.py` seeded `CONN`,
    `DISC`, `NSF` and `TAMPER` and **no reconnection code at all**. The PO's
    ruling of 2026-09-21 — *"reconnection fee is $75 - fix the code and seed"* —
    added `RECON` to `seed_demo.py` AND moved `lookup_defaults.json` to `$75.00`,
    so **a provisioned tenant now HAS one** and this helper's `get_or_create`
    finds it rather than making it.
    ⚠ **THE CODE IS `RECON` AND NOT `CC-RECON`.** The `CC-` prefix resolved on
    no tenant in the product and is why no cut could ever complete; the seed,
    the ledger's chart of accounts and every tenant row all spell it `RECON`.
    Written through `disconnects.RECONNECT_CHARGE_CODE` here, so a future
    respelling moves the product and this fixture together.

    ⚠ **IT NOW CARRIES A GL ACCOUNT, AND THAT IS DEF-708 (2026-08-27).** The
    fee has become a REAL CHARGE — the cut raises and issues a `fee` bill for
    this code — so a code with no GL account is a fee that could never be
    booked (BR-BIL-010: *charge codes carry their own GL*) and `commit_cut`
    refuses by name rather than recording a cut whose money nothing collects.
    Re-pointed here in the same change that made the rule, which is DEF-705's
    lesson: a green fixture pinning the old behaviour is worse than no fixture.
    `test_def_708_the_fee_is_a_real_charge.py::tc5` is the case that asserts
    the refusal, so the requirement is proved and not merely assumed.
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


#: `DSC-02.5`'s review line, verbatim: *"Services cut · Electric, Sewer"* and
#: *"Services restricted · water — a restrictor, not a cut"*. The restrictor is
#: dropped from this fixture on purpose — `assert_treatments_expressible`
#: refuses it, and the test that proves that is its own.
SERVICES = {"electric": disconnects.TREATMENT_FULL, "sewer": disconnects.TREATMENT_FULL}


def _scheduled(
    actor,
    tenant,
    monkeypatch,
    *,
    owed=NORTHWIND_OWED,
    services=None,
    deposit=None,
    reason=disconnects.CUT_REASON_NON_PAYMENT,
    charge=True,
    label="Unit A",
):
    """A case standing exactly where step 5 leaves it: scheduled, not cut.

    Walked through the REAL ladder — `advance()` three times, a real tier-3
    notice, a real recorded proof of service — because a case put into
    `scheduled` with an UPDATE proves only that a column can hold a string.
    """
    _owes(monkeypatch, owed)
    if charge:
        _reconnect_charge(tenant)
    else:
        # ⚠ **`charge=False` HAD TO START DOING SOMETHING ON 2026-09-21.** It
        # used to mean *"do not create one"*, and that was enough because NO
        # SEED IN THIS REPO CREATED A RECONNECTION CODE. The PO's ruling —
        # *"reconnection fee is $75 - fix the code and seed"* — put `RECON` in
        # `lookup_defaults.json` AND in `seed_demo.py`, so a provisioned tenant
        # now has one and *not creating* it no longer produces the state this
        # flag names.
        #
        # **The behaviour under test is unchanged and must stay real:** a cut
        # nobody can price is a cut the customer cannot undo. So the row is
        # REMOVED rather than the assertion relaxed — the alternative was to
        # weaken the case to match the fixture, which is how a guard quietly
        # stops guarding.
        rating_models.Charge.objects.filter(
            tenant=tenant, code=disconnects.RECONNECT_CHARGE_CODE
        ).delete()
    account = _account(actor, tenant, label=label, name="Northwind Mfg.")
    _at_tier(actor, account["id"], disconnects.TIER_3)
    _prove_tier_3_service(actor, account["id"], served_on=SERVED_ON)
    disconnects.schedule_cut(
        actor,
        account["id"],
        cut_on=CUT_ON,
        as_of=TODAY,
        reason=reason,
        services=SERVICES if services is None else services,
        deposit=deposit,
    )
    return account


def _account_row(account_id):
    return customers_models.Account.objects.get(id=account_id)


def _snapshot(account_id):
    """The fields a cut must not move — `DSC-02.4`'s `Will NOT` column as data."""
    row = _account_row(account_id)
    return {
        "status_code": row.status.code,
        "behavior_class": row.status.behavior_class,
        "closed_at": row.closed_at,
        "deposit_on_file": row.deposit_on_file,
    }


# ════════════════════════════════════════════════════════════════════════════
# TC-DSC-7 — THE CUT COMMITS
# ════════════════════════════════════════════════════════════════════════════
def test_tc_dsc_7__the_cut_leaves_the_account_open_and_stops_base(
    brazos, marcus, monkeypatch, audit_rows
):
    """`DSC-02.4`'s two columns, asserted line by line.

    TC-DSC-7 as WRITTEN said *"the cut commits → danger tier; `audit_log`
    written; base charges **keep accruing** and the screen said so."*

    ⚠ **THE ACCRUAL CLAUSE IS SUPERSEDED AND THIS TEST IS RE-POINTED WITH IT
    (BR-CUS-103, PO 2026-08-25, closing OQ-380, answer "no").** DEF-705's lesson,
    one week old: *"when a rule is superseded, the tests that assert the old one
    are part of the supersession and must be found and re-pointed in the same
    change"* — a green test pinning a reversed rule is worse than no test.

    What is asserted now: the account row still does not move (`DSC-02.4`'s
    first prohibition, unchanged — a cut is not a move-out), the cut records
    the ruling, and **the base charge stops**. The last of those is proved in
    `tests/test_br_cus_105_static_balance.py` against a REAL bill, because
    nothing in this module bills and a payload key is not a base charge.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        before = _snapshot(account["id"])

        cut = disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)

        # ── WILL: the services chosen at step 1, on the scheduled date ──────
        assert cut["state"] == disconnects.STATE_CUT
        assert cut["cut_on"] == str(CUT_ON)
        assert set(cut["services_cut"]) == {"electric", "sewer"}

        # ── WILL NOT: close the account or settle the deposit ───────────────
        # ⚠ **THE STATUS IS PART OF THIS SNAPSHOT AND IT NO LONGER MOVES *ONLY
        # BECAUSE OF THIS FIXTURE* — 2026-08-31, CR-052 W0 task 1.** The PO
        # ruled the cut is the WHOLE event, so `commit_cut` writes
        # BR-CUS-107's `Disconnected` on an account whose days it could bill.
        # THIS ladder account is on a plan whose tariff has no version in force
        # at the service date, so billing refuses it and the status is
        # deliberately HELD (`CUT_BILL_BLOCKED_SO_STATUS_HELD`) — which is what
        # keeps the account in the run with those days still billable. The two
        # prohibitions `DSC-02.4` actually names are asserted separately below
        # and hold in BOTH branches: `closed_at` and `deposit_on_file` never
        # move. `tests/test_cr052_w0_the_23_23_case.py` is where the status IS
        # written, on an account that can be billed.
        assert cut["cut_bill"]["outcome"] == "blocked"
        assert cut["account_status_written"] is None
        assert _snapshot(account["id"]) == before
        assert _account_row(account["id"]).closed_at is None
        assert cut["account_open"] is True

        # ── BR-CUS-103: base charges STOP at the cut ────────────────────────
        # The mechanism is still a READ billing takes (`service_off_windows`),
        # unchanged by CR-052 W0: the cut subtracts dark days and B4.3's frozen
        # factor prices them. What CHANGED on 2026-08-31 is WHEN the days
        # BEFORE the cut are billed — at the cut, not a month later — which is
        # what let BR-CUS-107's status be written without losing them.
        assert before["behavior_class"] == "billable"
        assert cut["accrual"]["code"] == "cut_stops_base_at_the_cut"
        assert "BR-CUS-103" in cut["accrual"]["br_ref"]

        # ── rule 7, widened: a cut is a service action against a named person ─
        assert disconnects.AUDIT_CUT_COMMITTED in audit_actions(audit_rows)


def test_the_cut_quotes_the_reconnection_fee_from_the_tenants_own_charge_code(
    brazos, marcus, monkeypatch
):
    """*"Add $75.00 to the balance as the price of getting service back."*

    The figure comes from the tenant's `CC-RECON` row and never from this
    module: BR-BIL-007, *"NSF/reconnect fees are tenant-configured charge codes,
    never hardcoded"*. Money is STORED at 4 decimals and DISPLAYED at 2
    (CLAUDE.md rule 2, PO re-sign 2026-08-22).

    ✅ **AND IT IS NOW IN AR — DEF-708, 2026-08-27.** This paragraph read *"AND
    IT IS NOT IN AR … `apps.billing.services` publishes no ad-hoc charge service
    to hand it to"*. Billing publishes one now (`fee_bill.raise_and_issue_charge
    _fee`), so the cut raises and ISSUES the fee and `FEE_POSTED` rides on the
    answer. Re-pointed in the same change that made the rule — DEF-705's lesson,
    and the file this test lives beside said so of itself: *"if that ever
    changes, this test is the reminder"*.

    ⚠ **THE TWO FIGURES ARE STILL TWO FACTS.** `reconnection_fee` is what was
    QUOTED and is frozen on the case; the balance is the MONEY. A caller states
    both and never adds them together.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        cut = disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)

        assert cut["reconnection_fee"] == {"stored": "75.0000", "display": "75.00"}
        # ⊕ `OQ-CUS-12518` CLOSED 2026-09-21 (PO: *"reconnection fee is $75 -
        # fix the code and seed"*). This pinned `"CC-RECON"` — a spelling that
        # resolved on NO tenant, so this assertion was holding the defect in
        # place rather than guarding against it. Compared to the CONSTANT now,
        # so a future respelling moves the product and the test together.
        assert cut["reconnection_fee_code"] == disconnects.RECONNECT_CHARGE_CODE
        assert cut["fee_posting"]["code"] == "reconnection_fee_posted_to_ar"
        # BR-CUS-104 (PO 2026-08-25, OQ-381) RULED the timing: the fee lands at
        # the CUT — and since 2026-08-27 it also LANDS, so `mark_reconnecting`
        # requires $8,315.00 where it used to clear $8,240.00.
        assert cut["fee_timing"]["code"] == "reconnection_fee_lands_at_the_cut"
        assert cut["fee_timing"]["tracks"] == "DEF-708"
        assert cut["fee_posting"]["closes"] == "DEF-708"
        # …and the payload names the DOCUMENT, so the figure can be traced to a
        # bill rather than standing on its own (DEF-628's shape).
        assert cut["fee_invoice"]["invoice_no"]

        case = disconnects.DisconnectCase.objects.get(id=cut["case_id"])
        assert case.reconnection_fee_amount == D("75.0000")

        # The tenant edits the figure; nothing here does. A second tenant with a
        # different price gets a different quote from the same code.
        rating_models.Charge.objects.filter(
            tenant=brazos, code=disconnects.RECONNECT_CHARGE_CODE
        ).update(amount=D("92.5000"))
        terms = disconnects.reconnection_terms(account["id"], case=case)
        assert terms["fee"]["display"] == "92.50"


def test_a_cut_refuses_when_no_reconnection_fee_is_configured(brazos, marcus, monkeypatch):
    """A cut nobody can price is a cut the customer cannot undo.

    `DSC-02.4`: *"The reconnection fee is quoted now so the customer is told what
    it will cost to get service back **before it is taken away**."* This is
    `apps/notifications/notices.py`'s posture for the same figure in the same
    letter — *"Configure the reconnect charge code, then generate"* — applied to
    the act the letter warns about.

    ⚠ **THIS WAS TODAY'S DEFAULT UNTIL 2026-09-21 AND IS NOW A DELIBERATE
    STATE.** No seed created a reconnection code, so every tenant was in it. The
    PO's ruling seeded `RECON` at `$75.00`, so the fixture now REMOVES the row
    to reach this case — see `_scheduled`'s `charge=False` branch.
    **The case is not weaker for that:** a utility that deletes or never
    configures its reconnection code is a real state, and a cut nobody can
    price is still a cut the customer cannot undo.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, charge=False)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert refusal.value.code == "reconnect_charge_code_not_seeded"

        case = disconnects.open_case_for(account["id"])
        assert case.state == disconnects.STATE_SCHEDULED
        assert case.cut_on is None


def test_a_cut_cannot_run_before_the_date_the_customer_was_given(brazos, marcus, monkeypatch):
    """`DSC-02.3`: *"EARLIEST LAWFUL CUT · Aug 24 · Locked — computed, not chosen"*
    and *"Cannot be earlier than Aug 24."*

    The date is the notice period the household was given, so cutting before it
    is cutting without the notice. ⚠ The date itself is NOT computed here — the
    *"Aug 22 plus 48 hours, rolled forward past weekends and public holidays"*
    roll is `schedule_cut`'s input, and B18 warns that *"a lane must not read
    '48 hours' as '+2 days'"*.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.commit_cut(marcus, account["id"], cut_on=date(2026, 8, 23), as_of=TODAY)
        assert refusal.value.code == "cut_before_the_scheduled_date"


def test_a_cut_refuses_on_a_case_nobody_scheduled(brazos, marcus, monkeypatch):
    """`DSC-02`'s footer, on all five steps: *"nothing is cut until the scheduled date"*.

    The scheduling is what serves the notice, locks the earliest lawful date and
    records the services chosen. A cut with no schedule behind it is a cut
    nobody was told about — and it would also skip `assert_service_proved`,
    which is the guard BR-CUS-100 exists for.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, NORTHWIND_OWED)
        _reconnect_charge(brazos)
        account = _account(marcus, brazos)
        _at_tier(marcus, account["id"], disconnects.TIER_2)

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert refusal.value.code == "cut_not_scheduled"


def test_a_scheduled_cut_stops_itself_when_they_pay(brazos, marcus, monkeypatch):
    """B18 §5.8.7 step 5, verbatim: *"This schedules it. Nothing is cut until the
    date, and **it stops automatically if they pay or agree a plan**."*

    **NOTHING IS CANCELLED HERE.** The money posts and `commit_cut` refuses on
    its next call, because `halt_reason` is computed from the balance every time
    rather than read from a stored "running" flag. That is task 7.6's safety
    property reaching the most serious act in the module: a schedule-time-only
    check would cut a household that paid on the Friday.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        _owes(monkeypatch, D("0.00"))  # they paid — and NOTHING is called

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert refusal.value.code == disconnects.HALT_NOTHING_OWED
        assert disconnects.open_case_for(account["id"]).cut_on is None


def test_a_protection_filed_after_the_schedule_stops_the_cut(brazos, marcus, monkeypatch):
    """A medical certificate filed between the schedule and the date.

    `assert_cut_reachable`, `_require_running` and `assert_service_proved` are
    all re-run at the cut, not only at the schedule — days pass in between and
    B18 §5.8.7 says why this step exists at all: *"cutting service to a
    protected household is the single most serious thing this product can do"*.

    ⚠ **NO PRECEDENCE IS INVENTED.** This case is at TIER 3 **and** protected,
    which is exactly `OQ-374`'s open question — which segment holds it and which
    chip it wears. This test asserts only that the CUT is refused with the
    protection named; it does not rank the two facts, and nothing here may.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.record_protection(
            marcus,
            account["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 24),
            expires_on=date(2026, 11, 1),
        )
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert refusal.value.code == disconnects.HALT_PROTECTED
        assert "medical_certificate" in str(refusal.value)


def test_a_cut_is_recorded_once(brazos, marcus, monkeypatch):
    """Hard rule 4's discipline: the record cannot be re-pointed afterwards.

    Re-recording would re-quote the reconnection fee at today's catalogue price
    and re-date the enforcement. If a crew attended twice, that is a field
    record, not a second cut.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert refusal.value.code == "already_cut"


# ════════════════════════════════════════════════════════════════════════════
# `DSC-02.1` — ONE DECISION PER SERVICE, AND THE THIRD STATE THAT IS REFUSED
# ════════════════════════════════════════════════════════════════════════════
def test_a_restrictor_is_refused_and_names_what_it_would_take(brazos, marcus, monkeypatch):
    """⛔ **DELIBERATELY NEGATIVE — see the module docstring.**

    `DSC-02.1` offers three treatments per service and this schema holds two.
    The drawn caption makes the stakes plain: *"restricting water rather than
    cutting it. A restrictor limits flow to a minimum rather than stopping it,
    **which many jurisdictions require for water**."*

    Recording it as a cut says a household's water was STOPPED when it was
    throttled; recording it as `leave_connected` loses the enforcement
    altogether. So it raises, and the refusal carries what building it would
    take rather than only that it is missing.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, NORTHWIND_OWED)
        _reconnect_charge(brazos)
        account = _account(marcus, brazos)
        _at_tier(marcus, account["id"], disconnects.TIER_3)
        _prove_tier_3_service(marcus, account["id"], served_on=SERVED_ON)

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.schedule_cut(
                marcus,
                account["id"],
                cut_on=CUT_ON,
                as_of=TODAY,
                services={
                    "electric": disconnects.TREATMENT_FULL,
                    "water": disconnects.TREATMENT_RESTRICTOR,
                },
            )
        assert refusal.value.code == "restrictor_is_a_third_state"
        assert "disconnect_case_services" in str(refusal.value)

        # Nothing was written on the way to the refusal.
        assert disconnects.open_case_for(account["id"]).cut_scheduled_for is None


def test_leave_connected_is_a_decision_and_a_cut_must_name_its_services(
    brazos, marcus, monkeypatch
):
    """*"One decision per service, not all or nothing."*

    A service marked `leave_connected` is a DECISION that it keeps flowing, so
    it is simply absent from `services_cut`. And a case where every service was
    left connected cannot fall back on cutting everything — that is precisely
    the assumption the drawn table exists to prevent.
    """
    with tenant_ctx(brazos):
        account = _scheduled(
            marcus,
            brazos,
            monkeypatch,
            services={
                "electric": disconnects.TREATMENT_FULL,
                "water": disconnects.TREATMENT_LEAVE,
            },
        )
        case = disconnects.open_case_for(account["id"])
        assert case.services_cut == ["electric"]

        case.services_cut = []
        case.save(update_fields=["services_cut"])
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert refusal.value.code == "no_services_chosen"


def test_the_cut_reason_is_recorded_and_drives_nothing(brazos, marcus, monkeypatch):
    """⛔ **DELIBERATELY NEGATIVE — see the module docstring.**

    B18 §5.8.7: *"THE REASON IS NOT DECORATION. Only the first is a collections
    outcome; the other four are operational and **must not require a dunning
    ladder at all**. … Nothing in `disconnects.py` keys off a reason."*

    Two cuts differing only in their reason must be identical in every other
    respect. **And the reason is why four of the five drawn reasons have no path
    to a cut at all today** — `schedule_cut` requires TIER 3 and a certified
    proof, and a tampering cut has no ladder to climb. That is REPORTED, and the
    `reason_absence` on every payload is where a reader finds it.
    """
    with tenant_ctx(brazos):
        first = _scheduled(marcus, brazos, monkeypatch, reason=disconnects.CUT_REASON_NON_PAYMENT)
        cut_one = disconnects.commit_cut(marcus, first["id"], cut_on=CUT_ON, as_of=TODAY)

        second = _scheduled(
            marcus,
            brazos,
            monkeypatch,
            reason=disconnects.CUT_REASON_TAMPERING,
            label="Unit B",
        )
        cut_two = disconnects.commit_cut(marcus, second["id"], cut_on=CUT_ON, as_of=TODAY)

        assert cut_one["cut_reason"] == "non_payment"
        assert cut_two["cut_reason"] == "tampering_or_theft"
        # ⚠ **`case_no` JOINED THIS SET ON 2026-08-27 — DEF-920, AND IT IS A
        # SIXTH KIND OF PLACE A NEW NUMBER SERIES REACHES.** The five the
        # numbering questions listed are hand-written PINS (a size, a prefix, a
        # wired set, a guard, a label). This is not a pin at all: it is a test
        # that compares two whole payloads for equality and therefore has to
        # ignore every PER-RECORD IDENTITY field — which `case_id` and
        # `account_id` already were.
        #
        # **`case_no` was not in the set because it was NULL on every row**, and
        # `None == None`, so a field that is empty everywhere compares EQUAL and
        # is invisible to an equality test. The moment `OQ-427` closed and the
        # `disconnect_case` series started allocating, the two cases drew
        # `DSC-26-0001` and `DSC-26-0002` and this went RED, verbatim:
        #
        #     AssertionError: assert {'case_no': '...': 'cut', ...} == {…}
        #       Differing items:
        #       {'case_no': 'DSC-26-0001'} != {'case_no': 'DSC-26-0002'}
        #
        # Nothing about the product was wrong: two different cases having two
        # different numbers is BR-TEN-035 working. What this case asserts is
        # that a cut REASON drives nothing, and an identity does not bear on it.
        # ⚠ **`fee_invoice` JOINED THIS SET ON 2026-08-27 (DEF-708), FOR THE EXACT
        # REASON `case_no` DID.** The cut now raises a real `fee` bill, so each case
        # carries its own invoice id and number — `BL-2608-000001` and
        # `BL-2608-000002` — and two different bills having two different numbers is
        # BR-TEN-035 working, not a reason for these payloads to disagree:
        #
        #     AssertionError: assert {'fee_invoice': {…'BL-2608-000001'…}}
        #                         == {'fee_invoice': {…'BL-2608-000002'…}}
        #
        # What this case asserts is that a cut REASON drives nothing, and an identity
        # does not bear on it. The FEE's own behaviour is asserted in
        # `tests/test_def_708_the_fee_is_a_real_charge.py`, where the amount is the
        # subject rather than the noise.
        # ⚠ **`notification_queued` JOINED THIS SET ON 2026-10-29 (DEF-NOT-10649),
        # for `fee_invoice`'s reason:** each cut now queues its own *Service
        # disconnected* rows, so each payload names its own message ids. The
        # notice's behaviour is `tests/test_def_not_10649_cut_restore_notices.py`'s.
        ignored = {
            "case_id",
            "account_id",
            "case_no",
            "cut_reason",
            "fee_invoice",
            "notification_queued",
        }
        assert {k: v for k, v in cut_one.items() if k not in ignored} == {
            k: v for k, v in cut_two.items() if k not in ignored
        }
        assert cut_one["reason_absence"]["code"] == "cut_reason_drives_nothing"

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.schedule_cut(
                marcus, first["id"], cut_on=CUT_ON, as_of=TODAY, reason="because"
            )
        assert refusal.value.code == "cut_reason_unknown"


# ════════════════════════════════════════════════════════════════════════════
# `DSC-02.4` — THE DEPOSIT: AN ELECTION, NEVER A POSTING
# ════════════════════════════════════════════════════════════════════════════
def test_a_held_deposit_stays_held_and_an_applied_one_means_a_new_deposit(
    brazos, marcus, monkeypatch
):
    """`DSC-02.4`'s radio, and the sentence that makes the two options differ.

    ● **Hold it** — *"The $500.00 stays held. The arrear stands at $8,240.00 and
    the deposit is available if they reconnect."*
    ○ **Apply it against the arrear** — *"Reduces the arrear to $7,740.00.
    Nothing is held, so a new deposit is required to reconnect."*

    ⚠ **NEITHER OPTION MOVES ANY MONEY HERE.** The chip on that panel is the
    accounting rule stated to a clerk — *"A liability, not revenue"* — and
    applying a deposit against an arrear is a balance-sheet posting, which
    CLAUDE.md rule 5 leaves to the ledger posting service alone. What the
    election decides TODAY is whether a new deposit is required to come back.
    """
    with tenant_ctx(brazos):
        held = _scheduled(marcus, brazos, monkeypatch, deposit=disconnects.DEPOSIT_HELD)
        customers_models.Account.objects.filter(id=held["id"]).update(
            deposit_on_file=DEPOSIT_HELD_FIGURE
        )
        cut = disconnects.commit_cut(marcus, held["id"], cut_on=CUT_ON, as_of=TODAY)
        assert cut["deposit_disposition"] == "held"
        assert cut["new_deposit_required"] is False
        # It was NOT settled: *"Close the account or settle the deposit — that
        # is a move-out, not a disconnect."*
        assert _account_row(held["id"]).deposit_on_file == DEPOSIT_HELD_FIGURE
        assert cut["deposit_posting"]["code"] == "deposit_application_not_posted"

        applied = _scheduled(
            marcus,
            brazos,
            monkeypatch,
            deposit=disconnects.DEPOSIT_APPLIED,
            label="Unit B",
        )
        customers_models.Account.objects.filter(id=applied["id"]).update(
            deposit_on_file=DEPOSIT_HELD_FIGURE
        )
        cut = disconnects.commit_cut(marcus, applied["id"], cut_on=CUT_ON, as_of=TODAY)
        assert cut["deposit_disposition"] == "applied_against_arrear"
        assert cut["new_deposit_required"] is True
        # The election is recorded and the money did not move — the arrear in AR
        # is untouched and so is the deposit column.
        assert _account_row(applied["id"]).deposit_on_file == DEPOSIT_HELD_FIGURE
        terms = disconnects.reconnection_terms(
            applied["id"], case=disconnects.open_case_for(applied["id"])
        )
        assert terms["deposit"]["new_deposit_required"] is True
        assert "a new deposit is required" in terms["deposit"]["detail"]


def test_an_unstated_deposit_election_lands_on_the_drawn_default(brazos, marcus, monkeypatch):
    """`DSC-02.4` draws ● **Hold it** as the selected option, and holding is also
    the option that moves no money. An election nobody made must not leave a cut
    account with the question open, and it must not silently apply somebody's
    deposit — so the default is the reversible half."""
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, deposit=None)
        assert disconnects.open_case_for(account["id"]).deposit_disposition is None
        cut = disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert cut["deposit_disposition"] == disconnects.DEPOSIT_HELD


def test_a_third_deposit_disposition_is_refused(brazos, marcus, monkeypatch):
    """A deposit is money held on the customer's behalf; a third disposition is
    an accounting rule, not a value to pass."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, NORTHWIND_OWED)
        account = _account(marcus, brazos)
        _at_tier(marcus, account["id"], disconnects.TIER_3)
        _prove_tier_3_service(marcus, account["id"], served_on=SERVED_ON)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.schedule_cut(
                marcus, account["id"], cut_on=CUT_ON, as_of=TODAY, deposit="refund_it"
            )
        assert refusal.value.code == "deposit_disposition_unknown"


# ════════════════════════════════════════════════════════════════════════════
# 7.9 — CUT → RECONNECTING → RESTORED
# ════════════════════════════════════════════════════════════════════════════
def test_tc_dsc_8__a_paid_cut_account_reconnects_and_stays_on_the_tab(
    brazos, marcus, monkeypatch, audit_rows
):
    """TC-DSC-8: *"`A-11507` owes $0.00 → `Reconnecting`, tier `—` — a paid
    account still on the tab because a visit is due."*

    §5.8.4: *"Reconnect is its own short flow: payment confirmed → visit
    scheduled → restored → the row leaves the tab."*

    ⚠ **NOTHING BOOKS THE VISIT** — `work_orders` is metering's table and a
    cross-module write is forbidden, so `RECONNECTING` records that a visit is
    DUE and the absence travels on the answer.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)

        _owes(monkeypatch, D("0.00"))
        moved = disconnects.mark_reconnecting(marcus, account["id"], on_date=date(2026, 8, 28))
        assert moved["state"] == disconnects.STATE_RECONNECTING
        assert moved["owed_at_reconnection"]["display"] == "0.00"
        assert moved["visit"]["code"] == "reconnection_visit_not_scheduled"
        # Still on the tab: the case is OPEN, which is what keeps the row there.
        assert disconnects.open_case_for(account["id"]) is not None

        restored = disconnects.restore_service(marcus, account["id"], on_date=date(2026, 8, 29))
        assert restored["state"] == disconnects.STATE_RESTORED
        assert restored["reconnected_on"] == "2026-08-29"
        assert restored["leaves_the_tab"] is True
        # …and NOW the row leaves the list.
        assert disconnects.open_case_for(account["id"]) is None

        actions = audit_actions(audit_rows)
        assert disconnects.AUDIT_RECONNECTING in actions
        assert disconnects.AUDIT_RESTORED in actions


def test_paying_does_not_reconnect_by_itself(brazos, marcus, monkeypatch):
    """⛔ **DELIBERATELY NEGATIVE — BR-PAY-036.**

    *"A payment is ALWAYS accepted and acceptance NEVER auto-changes account
    status — restoration stays an explicit, audited staff action."*

    The money posts, NOTHING is called, and the account is still CUT. The ladder
    stops itself (task 7.6, and `halt_reason` says so in its own words); the
    meter does not turn itself back on. A lane that makes this test green by
    auto-restoring has rebuilt the defect BR-PAY-036 forbids.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        _owes(monkeypatch, D("0.00"))

        assert disconnects.open_case_for(account["id"]).state == disconnects.STATE_CUT
        assert disconnects.ladder_state(account["id"], as_of=TODAY).runs is False


def test_reconnecting_states_what_is_outstanding_and_does_not_refuse_it(
    brazos, marcus, monkeypatch
):
    """⛔ **RE-POINTED 2026-09-25 — THIS ASSERTED `not_settled` AND THAT RULE IS
    SUPERSEDED (`BR-CUS-1097`, `DEF-CUS-6735`).**

    It read *"reconnecting is refused while anything is outstanding"*, on
    `DSC-02.4`'s drawn *"until it is settled"*. That drawn line went to the PO
    under B14 rule 41 and the answer, verbatim, choosing option (a) of two, was
    **"Show what's still owed and let the clerk proceed"**.

    ⚠ **A GREEN TEST PINNING A REVERSED RULE IS WORSE THAN NO TEST** — DEF-705's
    lesson, and this file already carries it one case above
    (`test_tc_dsc_7…`, re-pointed for `BR-CUS-103`). So the case is re-pointed
    rather than deleted: what it now proves is that the figure is STATED where
    it used to refuse.

    ⚠ **THE SECOND HALF IS UNTOUCHED AND MUST STAY.** An UNREADABLE balance is a
    different fact from a known, unpaid one, and `BR-CUS-1097` does not reach it
    (DEF-127/DEF-628). The full argument and Brett Calloway's worked figure are
    in `tests/test_br_cus_1097_1099_warn_do_not_stop.py`.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)

        readiness = disconnects.reconnection_readiness(account["id"])
        assert readiness["ready"] is True
        assert [w["code"] for w in readiness["warnings"]] == ["money_still_owed"]

        # ⚠ **THE UNREADABLE HALF RUNS FIRST, AND THE ORDER IS THE POINT.** It
        # used to run second because the first call REFUSED and left the case
        # where it was. It no longer refuses, so a second call on a case now in
        # `reconnecting` would be refused `not_cut` — a true refusal for the
        # wrong reason, which would have passed a sloppier assertion.
        _owes(monkeypatch, None, available=False)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.mark_reconnecting(marcus, account["id"], on_date=TODAY)
        assert refusal.value.code == disconnects.HALT_BALANCE_UNREADABLE

        _owes(monkeypatch, NORTHWIND_OWED)
        assert disconnects.mark_reconnecting(marcus, account["id"], on_date=TODAY)[
            "state"
        ] == disconnects.STATE_RECONNECTING


def test_restoring_goes_through_reconnecting_and_not_around_it(brazos, marcus, monkeypatch):
    """A cut account cannot jump to `restored`.

    The middle state is *"paid, awaiting a visit"*, so skipping it records a
    restoration on an account that never settled — a statement on the record
    that it paid.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.restore_service(marcus, account["id"], on_date=date(2026, 8, 29))
        assert refusal.value.code == "not_reconnecting"


def test_reconnecting_is_refused_on_an_account_that_was_never_cut(brazos, marcus, monkeypatch):
    """§5.8.3 draws `RECONNECTING` between `CUT` and `restored`, and nowhere else."""
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        _owes(monkeypatch, D("0.00"))
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.mark_reconnecting(marcus, account["id"], on_date=TODAY)
        assert refusal.value.code == "not_cut"


# ════════════════════════════════════════════════════════════════════════════
# *"BLOCKS NEW SERVICE ELSEWHERE UNTIL IT IS SETTLED"* — BUILT, UNCONSUMED
# ════════════════════════════════════════════════════════════════════════════
def test_the_new_service_block_is_built_and_consumed_by_nothing(brazos, marcus, monkeypatch):
    """⛔ **DELIBERATELY NEGATIVE — hard-won law 2, built is not wired.**

    B18 §5.8.7's own finding: *"'Blocks new service elsewhere until it is
    settled' is a CROSS-PREMISES rule with no id: a debt at one address stops a
    move-in at another. That reaches into move-in, which does not check it."*

    Three-valued on purpose: `True` while cut and owing, `False` once settled,
    and **`None` when AR cannot be read** — a reading that failed is not a
    clearance, and a consumer that treats `None` as *not blocked* would let a
    household take service elsewhere on a failure.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        assert disconnects.new_service_block_for(account["id"])["blocked"] is False

        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        blocked = disconnects.new_service_block_for(account["id"])
        assert blocked["blocked"] is True
        assert blocked["balance"]["display"] == "8240.00"
        assert blocked["absence"]["code"] == "new_service_block_not_consumed"

        _owes(monkeypatch, None, available=False)
        assert disconnects.new_service_block_for(account["id"])["blocked"] is None

        _owes(monkeypatch, D("0.00"))
        assert disconnects.new_service_block_for(account["id"])["blocked"] is False


def test_the_new_service_block_has_exactly_one_consumer_and_it_is_named(brazos):
    """The other half of law 2 — a READ with no caller is dead code.

    ⚠ **THIS TEST WAS `test_nothing_in_this_repo_consumes_the_block_or_the
    _disconnected_state` AND IT HAS BEEN RED ON THE BRANCH TIP SINCE THE
    DISCONNECT ROUTES LANDED — `DEF-2710`.** It asserted that
    `new_service_block_for` had NO caller outside its own module, and its own
    docstring said the right fix was to *"delete it and say so in the lane
    report, not to keep the absence alive"*. `apps/customers/transfer_disconnect
    _api.py` became that caller (the eleven ladder doors, `DEF-2030`,
    2026-08-28) and nobody re-pointed the test. **No gate in this repository
    runs pytest**, so it sat red and unread.

    ⚠ **AND IT READ THE WRONG TREE.** It greped a hardcoded absolute repository
    path, so in a `git worktree` — which CLAUDE.md law 12 now tells every lane to
    use — it measured the SHARED checkout and not the lane's own. That is
    `DEF-524`'s shape (a hardcoded path outliving what it names) and it means a
    lane that ADDED a caller would not have seen this fail. The walk now starts
    from this file's own location.

    **What it guards now:** the block is COMPUTED in `disconnects.py` and READ
    by exactly one surface, the disconnect API. If a third file appears, either
    `OQ-384` (whose subject the block still has — account, customer, or the
    person named on it) has been answered, or somebody is consuming a
    three-valued read whose meaning is unruled.
    """
    import subprocess

    backend = pathlib.Path(__file__).resolve().parent.parent
    found = sorted(
        subprocess.run(
            ["grep", "-rl", "new_service_block_for", "apps", "--include=*.py"],
            capture_output=True,
            text=True,
            cwd=str(backend),
        ).stdout.split()
    )
    assert found == [
        "apps/customers/disconnects.py",
        "apps/customers/transfer_disconnect_api.py",
    ], found


# ════════════════════════════════════════════════════════════════════════════
# THE DATABASE, AND THE TENANT
# ════════════════════════════════════════════════════════════════════════════
def test_another_tenants_case_cannot_be_cut(brazos, lonestar, marcus, erin, monkeypatch):
    """CLAUDE.md rule 1 — no cross-tenant queryset, and TC-DSC-9's shape.

    `open_case_for` is tenant-scoped, so tenant B asking to cut tenant A's
    account finds no case at all — the refusal cannot tell a caller that
    somebody else's case exists (BR-TEN-003's posture).
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)

    with tenant_ctx(lonestar):
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.commit_cut(erin, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert refusal.value.code == "no_open_case"
        assert disconnects.new_service_block_for(account["id"])["blocked"] is False

    with tenant_ctx(brazos):
        assert disconnects.open_case_for(account["id"]).state == disconnects.STATE_SCHEDULED


def test_the_database_holds_the_price_of_coming_back(brazos, marcus, monkeypatch):
    """Hard-won law 1 — a comment claiming a guarantee is not the guarantee.

    `commit_cut` refuses before it writes; this test writes AROUND the service
    on purpose. `ck_cut_records_the_price_of_coming_back` is what makes *"a cut
    row carries the price of coming back"* true of the DATA: `DSC-02.4` quotes
    the fee before the cut so the customer knows what restoration costs, and a
    row saying service was cut with no price beside it cannot answer the first
    question they will ask.
    """
    from django.db.utils import IntegrityError

    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        case = disconnects.open_case_for(account["id"])
        with pytest.raises(IntegrityError):
            disconnects.DisconnectCase.objects.filter(pk=case.pk).update(
                cut_on=CUT_ON, state=disconnects.STATE_CUT
            )
