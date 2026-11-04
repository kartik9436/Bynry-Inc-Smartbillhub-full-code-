# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 CS-10 (task 54) — the ladder runs on a schedule, on the
#           utility's OWN business day · CR-059 CS-19 (task 13) — billing's
#           ISSUE path satisfies the first bill's deposit line
#           Screens: S34 · S70 (task 55) · S21
# Rules:    BR-PAY-017 (the ladder) · BR-PAY-016 (the pause) · BR-CUS-039 /
#           A15 (a medical hold is excluded from EVERY step) · BR-TEN-081 (the
#           utility's own clock) · BR-TEN-043 (the moment is named, not read) ·
#           BR-BIL-012 + BR-PAY-012 (a deposit-purpose payment satisfies the
#           first bill's deposit line) · CLAUDE.md rule 6 (idempotency) ·
#           hard-won law 2 (built is not wired) · law 3 (defaults fail closed) ·
#           law 7 (prove the guard RED first)
# Defects:  DEF-3150 (ONE STEP PER PASS IS NOT ONE STEP PER DAY)
# ───────────────────────────────────────────────────────
"""The scheduled ladder, and the first bill that stops charging a paid deposit.

**THE ONE THAT MATTERS, AND IT IS NOT THE SCHEDULE.** Registering a beat entry
is easy and nearly harmless. What made it dangerous is `DEF-3150`: every rung's
due date is derived from the OLDEST UNPAID BILL alone, so on an account 62 days
overdue the friendly reminder, the 10-day notice, the 5-day notice and the
certified 48-hour final are **all past due at the same moment**. The engine
guaranteed *"one step per account per pass"* and the CR repeated it as *"the
idempotence it needs already holds"* — and **four passes on one day took four
steps**, each one lawfully. A clerk could already do it by pressing the S34
button four times; a scheduler with `CELERY_TASK_ACKS_LATE` on would do it by
re-delivering a message.

    RED, against the unfixed `ladder.decide`, on ONE `as_of` of 2026-09-01
    with the oldest bill due 2026-07-01:

        pass 1  →  runs=True   rung=reminder            (correct)
        pass 2  →  runs=True   rung=disconnect_10_day   ← a second letter
        pass 3  →  runs=True   rung=disconnect_5_day
        pass 4  →  runs=True   rung=final_48_hour       ← the $8.00 certified one

        E   assert decision.runs is False
        E    +  where True = LadderDecision(account_id='acct', runs=True,
                 rung='disconnect_10_day', ...).runs

    GREEN, with the guard: pass 2 returns `already_noticed_today` and the
    account's tier is still the reminder.

**CS-19 IS THE OPPOSITE SHAPE AND IT IS WORTH SAYING SO.** CS-19 reads
*"Payments publishes the figure; billing never asks for it"*, and that was
measured by grep — the seam resolves `apps.payments.credit.
deposit_payments_for_account` BY NAME at call time, so there is no import and no
literal call site to find. Billing has asked for it since 2026-08-15. What was
never proved is CS-19's own stated Proof — *"take a deposit, ISSUE the first
bill, and the deposit line reads zero owing"* — because `test_us_bil_010`'s own
docstring says of itself *"This file never issued one."* That is the half this
file adds, and the figures are WE-6's: **150.00** asked, **150.00** paid at the
counter, **0** deposit lines on the issued bill.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.utils import timezone as django_timezone

from apps.billing import first_bill, issue, models as billing_models
from apps.payments import collections_schedule, ladder
from apps.payments import models as payment_models
from apps.payments.collections_models import (
    TIER_FIRST_10_DAY,
    TIER_FRIENDLY,
    AccountCollectionState,
    NoticeHistory,
)
from apps.payments.exceptions import PaymentRuleError
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_release_gate import a_release
from tests.test_us_bil_010_first_bill import (
    DEPOSIT_ASKED,
    MOVED_IN_ON,
    _a_deposit_rule,
    _a_first_bill_world,
    _prepare,
)
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_us_pay_007_credit import _pay
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

FLOOR = Decimal("25.00")

#: An account long enough overdue that EVERY rung is past due at once — which is
#: the whole of DEF-3150. Oldest unpaid bill due 1 July; today is 1 September.
OLDEST_DUE_ON = date(2026, 7, 1)
LONG_OVERDUE = date(2026, 9, 1)
OWED = Decimal("948.20")

#: The instant DEF-082's own worked figure straddles, reused rather than
#: recomputed: 04:30 UTC, when a utility on `America/Chicago` (UTC−5 in August)
#: is still on the PREVIOUS day. The scheduled ladder must take the utility's
#: day, and 6 a.m. Central is 11:00 UTC — so a job on the server's clock would
#: run on the wrong date AND at the wrong hour.
STRADDLE_UTC = datetime(2026, 8, 22, 4, 30, tzinfo=UTC)
CENTRAL_6AM_UTC = datetime(2026, 8, 22, 11, 5, tzinfo=UTC)


def _decide(**overrides):
    values = dict(
        account_id="acct",
        as_of=LONG_OVERDUE,
        balance=OWED,
        oldest_due_on=OLDEST_DUE_ON,
        balance_floor=FLOOR,
        partial_pause_percent=None,
    )
    values.update(overrides)
    return ladder.decide(**values)


def _a_debtor(tenant, dana, *, account_no, number, total=OWED):
    account = an_account(dana, tenant, account_no=account_no)
    an_issued_bill(
        tenant,
        account,
        number=number,
        total=total,
        issued_on=OLDEST_DUE_ON,
        due_date=OLDEST_DUE_ON,
    )
    return account


def _set_clock(monkeypatch, moment):
    """Freeze the ONE clock `tenant_today()` and `_tenant_moment()` both read.

    Not a money path (G6): this is the date-derivation clock BR-TEN-020 governs,
    and freezing it is how DEF-082 proved the tenant's day moves with the
    setting.
    """
    monkeypatch.setattr(django_timezone, "now", lambda: moment)


def _configure(tenant, *, zone="America/Chicago", enabled=True, hour=6):
    row = tenancy_models.TenantSettings.objects.filter(tenant=tenant).first()
    assert row is not None, "the fixture tenant is provisioned with a settings row"
    row.timezone = zone
    document = dict(row.collections or {})
    document["collections_schedule_enabled"] = enabled
    document["collections_schedule_hour"] = hour
    row.collections = document
    row.save(update_fields=["timezone", "collections", "updated_at"])
    return row


# ═══════════════════════════════════════════════════════════════════════════
# 1 · DEF-3150 — ONE STEP PER PASS IS NOT ONE STEP PER DAY
# ═══════════════════════════════════════════════════════════════════════════
def test_cr059_cs10__a_second_pass_on_one_day_takes_no_second_step(brazos, dana):
    """CLAUDE.md hard rule 6, on the case that made the schedule unsafe.

    Two months overdue, so all four rungs are past due together. The first pass
    sends the friendly reminder; the second, on the SAME `as_of`, must not send
    the 10-day disconnect notice an hour later.
    """
    first = _decide(current_rung=None, last_notice_on=None)
    assert first.runs is True and first.rung == TIER_FRIENDLY

    second = _decide(current_rung=TIER_FRIENDLY, last_notice_on=LONG_OVERDUE)
    assert second.runs is False, "a second pass on one business day sends nothing"
    assert second.skip_reason == ladder.SKIP_ALREADY_NOTICED_TODAY
    assert "already written to" in second.detail


def test_cr059_cs10__the_guard_is_not_one_of_the_five_and_never_masks_one(brazos, dana):
    """The floor is a fact about the CUSTOMER; the same-day guard is a fact
    about the PASS. An account both under the floor and already written to today
    reports the floor — the durable answer, and the one a clerk can act on."""
    both = _decide(balance=Decimal("2.40"), last_notice_on=LONG_OVERDUE)
    assert both.skip_reason == ladder.SKIP_BELOW_FLOOR


def test_cr059_cs10__a_backdated_pass_cannot_undo_a_later_notice(brazos, dana):
    """The comparison is `>=`, not `==`, and this is why.

    `run_ladder` promises *"a job re-run for last Tuesday must take last
    Tuesday's decision"*. Re-run for 20 August against an account written to on
    1 September and it would both post a letter to a customer who has moved on
    AND stamp `tier_sent_on` back to August in `_advance`.
    """
    stale = _decide(as_of=date(2026, 8, 20), last_notice_on=LONG_OVERDUE)
    assert stale.runs is False
    assert stale.skip_reason == ladder.SKIP_ALREADY_NOTICED_TODAY


def test_cr059_cs10__running_the_ladder_twice_on_one_day_sends_one_notice(brazos, dana):
    """THE END-TO-END IDEMPOTENCY PROOF (hard rule 6), through the real engine.

    One account, one `as_of`, two full passes. One notice, one advance, one
    `sent` row — and the second pass records its skip rather than staying
    silent, because J4 step 2 requires every skip on the trail.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-59010", number="BL-2609-059010")

        first = ladder.run_ladder(
            account_ids=(account.pk,), as_of=LONG_OVERDUE, actor=dana, balance_floor=FLOOR
        )
        assert len(first.stepped) == 1 and first.stepped[0].rung == TIER_FRIENDLY

        second = ladder.run_ladder(
            account_ids=(account.pk,), as_of=LONG_OVERDUE, actor=dana, balance_floor=FLOOR
        )
        assert second.stepped == (), "a repeated pass must not advance a second rung"
        assert second.skipped[0].skip_reason == ladder.SKIP_ALREADY_NOTICED_TODAY

        state = AccountCollectionState.objects.get(account=account)
        assert state.tier == TIER_FRIENDLY, "still rung 1, not the 10-day notice"
        assert state.tier != TIER_FIRST_10_DAY
        assert NoticeHistory.objects.filter(account=account, outcome="sent").count() == 1
        # The next business day the ladder moves on — the guard is a same-day
        # guard, not a freeze.
        third = ladder.run_ladder(
            account_ids=(account.pk,),
            as_of=date(2026, 9, 2),
            actor=dana,
            balance_floor=FLOOR,
        )
        assert len(third.stepped) == 1 and third.stepped[0].rung == TIER_FIRST_10_DAY


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE BEAT ENTRY — the schedule as DATA, and the schedule as INSTALLED
# ═══════════════════════════════════════════════════════════════════════════
class _StubApp:
    """A celery app with the two surfaces `install()` touches, and nothing else.

    A stub rather than a real app because *the schedule being correct* and *the
    schedule being installed* are two different claims (hard-won law 2), and the
    second one must be assertable without a broker.
    """

    def __init__(self):
        self.conf = type("Conf", (), {"beat_schedule": {}})()
        self.registered = {}

    def task(self, *, name, bind=False):
        def wrap(fn):
            self.registered[name] = fn
            return fn

        return wrap


def test_cr059_cs10__the_beat_entry_names_the_fanout_and_an_interval(brazos):
    """The entry is DATA — no clock, no broker, no side effect."""
    entry = collections_schedule.beat_schedule(every_seconds=900)
    assert set(entry) == {collections_schedule.BEAT_ENTRY}
    assert entry[collections_schedule.BEAT_ENTRY]["task"] == collections_schedule.FANOUT_TASK
    assert entry[collections_schedule.BEAT_ENTRY]["schedule"] == 900.0


def test_cr059_cs10__install_registers_the_entry_and_both_tasks(brazos):
    """RED before green (hard-won law 7): with `install()` not called, the app's
    `beat_schedule` held `{}` and `payments.collections_ladder` was a `KeyError`.

    The task OBJECTS are asserted too, for the reason `install()` records: a
    fan-out that kept the plain function would run every utility's ladder INLINE
    inside beat's own process, silently, with every test still passing.
    """
    app = _StubApp()
    result = collections_schedule.install(app)
    assert result["installed"] is True
    assert collections_schedule.BEAT_ENTRY in app.conf.beat_schedule
    assert collections_schedule.LADDER_TASK in app.registered
    assert collections_schedule.FANOUT_TASK in app.registered
    # Installing twice REPLACES rather than duplicating — two entries would be
    # two sweeps per interval.
    collections_schedule.install(app)
    assert len(app.conf.beat_schedule) == 1


def test_cr059_cs10__a_deployment_without_celery_starts_anyway(brazos, monkeypatch):
    """A Django app that refused to boot because a scheduler is absent would be
    a worse product than one whose reminders go out when the worker returns."""

    import builtins

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "config.celery":
            raise ImportError("no celery here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    result = collections_schedule.install()
    assert result["installed"] is False
    assert "celery" in result["reason"]


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE BUSINESS DAY — CS-10's ONE new rule
# ═══════════════════════════════════════════════════════════════════════════
def test_cr059_cs10__the_run_takes_the_utilitys_day_and_not_the_servers(brazos, dana, monkeypatch):
    """CS-10, verbatim: *"per-utility and runs on that utility's business day,
    not on UTC"*.

    At **2026-08-22T11:05Z** a utility on `America/Chicago` is at 06:05 on the
    **22nd**, so its 6 a.m. sweep fires and the ladder runs for **2026-08-22**.
    A job on the server's clock would have fired at 06:05 UTC — 01:05 Central,
    on the 22nd for UTC and still the 21st for a utility further west.
    """
    with tenant_ctx(brazos):
        _configure(brazos, zone="America/Chicago", hour=6)
        _a_debtor(brazos, dana, account_no="A-59020", number="BL-2609-059020")
        _set_clock(monkeypatch, CENTRAL_6AM_UTC)

        report = collections_schedule._run_within_tenant(
            {"subdomain": "brazos", "ran": False, "problems": []}, force=False
        )
    assert report["as_of"] == "2026-08-22"
    assert report["ran"] is True, report.get("reason")
    assert len(report["stepped"]) == 1


def test_cr059_cs10__it_does_not_fire_outside_the_utilitys_chosen_hour(brazos, dana, monkeypatch):
    """04:30 UTC is 23:30 on the 21st in Chicago — not 6 a.m., and not even the
    same DAY as UTC. Nothing runs, and the report says when it next will."""
    with tenant_ctx(brazos):
        _configure(brazos, zone="America/Chicago", hour=6)
        _a_debtor(brazos, dana, account_no="A-59021", number="BL-2609-059021")
        _set_clock(monkeypatch, STRADDLE_UTC)

        report = collections_schedule._run_within_tenant(
            {"subdomain": "brazos", "ran": False, "problems": []}, force=False
        )
    assert report["ran"] is False
    assert report["reason"] == "not_the_hour"
    assert report["as_of"] == "2026-08-21", "the UTILITY's day, which UTC has already left"
    assert report["next_run_at"].startswith("2026-08-22T06:00")


def test_cr059_cs10__the_switch_is_off_until_a_utility_turns_it_on(brazos, dana, monkeypatch):
    """Hard-won law 3 — the unsafe option is the one that has to be typed.

    Deploying this code chases nobody. On an account 62 days overdue the very
    first unattended pass would post the reminder and the next four days would
    walk it to the $8.00 certified final; nobody chose that.
    """
    with tenant_ctx(brazos):
        _configure(brazos, enabled=False)
        account = _a_debtor(brazos, dana, account_no="A-59022", number="BL-2609-059022")
        _set_clock(monkeypatch, CENTRAL_6AM_UTC)

        report = collections_schedule._run_within_tenant(
            {"subdomain": "brazos", "ran": False, "problems": []}, force=False
        )
        assert report["ran"] is False
        assert report["reason"] == "schedule_off"
        assert not AccountCollectionState.objects.filter(account=account).exists()


def test_cr059_cs10__the_seeded_default_of_the_switch_is_off(brazos):
    """Read through the SEAM, from a tenant nobody has configured — so the
    ratified seeded default is what a fresh utility actually gets, not what a
    constant in this test says."""
    with tenant_ctx(brazos):
        assert collections_schedule.schedule_enabled() is False
        assert collections_schedule.schedule_hour() == 6


def test_cr059_cs10__an_hour_that_is_not_an_hour_is_refused_not_defaulted(brazos):
    """An hour nobody can read is not an hour, and picking one would be this
    module deciding when a utility writes to its customers."""
    with tenant_ctx(brazos):
        _configure(brazos, hour=25)
        with pytest.raises(PaymentRuleError, match="0 to 23"):
            collections_schedule.schedule_hour()


# ═══════════════════════════════════════════════════════════════════════════
# 4 · BR-CUS-039 — NO MEDICAL-HOLD READ, NO RUN
# ═══════════════════════════════════════════════════════════════════════════
def test_cr059_cs10__an_unreadable_medical_hold_refuses_the_whole_run(brazos, dana, monkeypatch):
    """A15 via BR-CUS-039 — a medical-hold account is excluded from EVERY step.

    `ladder.run_ladder` takes the holds as an argument and never infers a
    clinical fact, so an unattended job that could not read them would chase
    everybody. It REFUSES instead: nothing is stepped and the reason is named.
    """
    real_resolve = collections_schedule._resolve

    def _no_medical(module, attribute, kind="selectors"):
        if attribute == "medical_hold_for":
            return None
        return real_resolve(module, attribute, kind)

    with tenant_ctx(brazos):
        _configure(brazos)
        account = _a_debtor(brazos, dana, account_no="A-59030", number="BL-2609-059030")
        _set_clock(monkeypatch, CENTRAL_6AM_UTC)
        monkeypatch.setattr(collections_schedule, "_resolve", _no_medical)

        report = collections_schedule._run_within_tenant(
            {"subdomain": "brazos", "ran": False, "problems": []}, force=False
        )
        assert report["ran"] is False
        assert report["reason"] == "medical_hold_unreadable"
        assert not AccountCollectionState.objects.filter(account=account).exists()
        assert not NoticeHistory.objects.filter(account=account).exists()
    codes = [problem["code"] for problem in report["problems"]]
    assert "medical_hold_not_readable" in codes


def test_cr059_cs10__the_medical_hold_read_is_actually_called(brazos, dana, monkeypatch):
    """Hard-won law 2, from the other side. `apps.customers.disconnects.
    medical_hold_for` shipped on 2026-08-25 saying of itself *"AND NOTHING CALLS
    IT YET"*. This is the call site, and the account it names is excluded."""
    with tenant_ctx(brazos):
        _configure(brazos)
        account = _a_debtor(brazos, dana, account_no="A-59031", number="BL-2609-059031")
        _set_clock(monkeypatch, CENTRAL_6AM_UTC)

        from apps.customers import disconnects

        monkeypatch.setattr(disconnects, "medical_hold_for", lambda account_id, *, as_of: True)
        report = collections_schedule._run_within_tenant(
            {"subdomain": "brazos", "ran": False, "problems": []}, force=False
        )
        assert report["ran"] is True, report.get("reason")
        assert report["stepped"] == []
        assert report["skipped"][0]["reason"] == ladder.SKIP_MEDICAL_HOLD
        assert not AccountCollectionState.objects.filter(account=account).exists()


# ═══════════════════════════════════════════════════════════════════════════
# 5 · WHAT THE SCREEN IS STILL TOLD, AND WHEN IT STOPS BEING TOLD IT
# ═══════════════════════════════════════════════════════════════════════════
def test_cr059_cs10__the_no_scheduled_caller_sentence_stands_until_it_is_false(brazos):
    """S34 prints *"Nothing runs the collection sequence overnight."*

    It is dropped ONLY where a scheduled caller is demonstrably live for this
    utility — the entry registered on a celery app AND the utility's switch on.
    On a deployment with no beat, or a utility that has not turned it on, the
    sentence is exactly as true as it was, and withdrawing it would be hard-won
    law 1 with the sign flipped: a claimed guarantee, printed for a clerk.
    """
    with tenant_ctx(brazos):
        _configure(brazos, enabled=False)
        codes = [problem["code"] for problem in ladder.ladder_problems()]
        assert "no_scheduled_caller" in codes
        assert collections_schedule.is_live() is False


def test_cr059_cs10__the_sweep_reports_rather_than_looking_healthy(brazos, monkeypatch):
    """No utility configured is a REPORT, not a quiet success — the shape
    DEF-320 was, where four job kinds enqueued and nothing dispatched."""
    monkeypatch.delenv(collections_schedule.LADDER_TENANTS_ENV, raising=False)
    result = collections_schedule.run_all()
    assert result["dispatched"] == 0
    assert result["problem"] == collections_schedule.NO_TENANTS_CONFIGURED
    # B14 rule 32 — no rule id and no internal code in a sentence a person reads.
    assert "BR-" not in result["problem"] and "OQ-" not in result["problem"]


def test_cr059_cs10__the_partial_payment_pause_absence_is_carried_not_hidden(brazos):
    """DEF-3151 — `recent_payments` has no supplier anywhere in this repository,
    so one of BR-PAY-017's five stop conditions never stops anything, on the
    scheduled run and on `POST /collections/run` alike. Stated on every result
    rather than left for somebody to discover."""
    codes = [problem["code"] for problem in collections_schedule.SCHEDULE_UNAVAILABLE]
    assert "partial_payment_pause_not_supplied" in codes
    assert "no_pass_record" in codes


# ═══════════════════════════════════════════════════════════════════════════
# 6 · CR-059 CS-19 (task 13) — THE ISSUE HALF OF THE DEPOSIT LINE
# ═══════════════════════════════════════════════════════════════════════════
#: The connection size the shared first-bill fixture's meter carries. Named
#: here because the fixture does not price it — see `_price_the_size_axis`.
FIXTURE_SIZE_CLASS = "E-1P-100"


def _price_the_size_axis(tenant, *, size_class=FIXTURE_SIZE_CLASS):
    """Give every tariff version a row for the size this fixture's meter has.

    ⚠ **WITHOUT THIS THE BILL DOES NOT PRICE AT ALL, AND IT IS NOT THIS LANE'S
    DEFECT.** `CR-057` switched `SBH_BILLING_RESOLUTION_STEPS` on by default at
    **R3,R4** (decision log 2026-09-01), so the ruled chain now prices the base
    charge of every account — and R3 asks *does this schedule serve this size*
    by looking for a `rate_size_rows` row. `tests/test_us_bil_001_prepare.
    a_priced_plan` writes a tariff version and one 0→∞ tier and **no size row**,
    so the chain refuses by name:

        R3: connection size 'E-1P-100' has no row on the rate schedule version
        … pricing 'electric'. The bill refuses rather than charging $0.00 for a
        size the utility has never priced.

    That is `DEF-2799`'s exact shape one fixture over — it was measured there as
    *"47 of 47 refused at R3 … `rate_size_rows` held 0 rows"* and fixed for the
    SAMPLE tenant, and this test fixture was never given the same fact.
    **`test_us_bil_010_first_bill.py` is red at the pinned tip for this reason,
    with none of this lane's files present** (`DEF-3155`); the shared fixture is
    left to the lane that owns it, and this lane supplies the missing fact for
    its own cases rather than asserting CS-19 against a bill that cannot price.

    The MINIMUM BILL is left NULL deliberately: absent is not zero (DEF-277),
    electric draws an em-dash for every size in r10's matrix, and a zero here
    would be a minimum-bill rule nobody wrote.
    """
    from apps.rating import models as rating_models

    for version in rating_models.TariffVersion.objects.filter(tenant=tenant):
        rating_models.RateSizeRow.objects.get_or_create(
            tenant=tenant,
            tariff_version=version,
            size_class=size_class,
            defaults={"minimum_bill": None, "currency": "USD"},
        )


def _issue_the_first_bill(brazos, dana, account, plan, *, key):
    _price_the_size_axis(brazos)
    run = a_run(brazos, key=key)
    # BR-BIL-024 needs a bill date and due-days or `issue` refuses the bill by
    # name (`cycle_has_no_due_terms`) — correctly: *"a guessed due date decides
    # when a late fee starts."* The first-bill fixture's cycle carries neither,
    # and `a_run`'s `get_or_create` hands back that existing row rather than its
    # own. So the terms are stated ON THE RUN, which is where the PO put them
    # for a run whose cycle has none (CR-029 D8③, closing OQ-241): 1 July + 21
    # days → due **22 July**.
    run.bill_date = date(2026, 7, 1)
    run.due_days = 21
    run.save(update_fields=["bill_date", "due_days"])
    a_release(brazos, run, dana)
    draft = first_bill.calculate_first_bill(
        _prepare(account),
        bill_run=run,
        moved_in_on=MOVED_IN_ON,
        account_type_id=account.account_type_id,
        # NO CONNECTION CHARGE, stated rather than defaulted. `calculate_first_
        # bill` defaults this to `CONN`, and provisioning seeds that code with no
        # GL account, so `issue._gl_account_for` refuses the whole bill by name
        # (`charge_code_has_no_live_account`) — correctly, per BR-BIL-010. CS-19
        # is about the DEPOSIT line, and a bill that cannot issue for an
        # unrelated reason proves nothing about it. The connection charge's own
        # untaxed-and-priced case is `test_us_bil_010_tc3`'s.
        connection_charge_code=None,
    )
    issued = issue.issue_run(
        run,
        issued_at=datetime(2026, 7, 3, 9, 41, tzinfo=UTC),
        template_id=uuid.UUID("9f0e6a52-3c14-4a7d-8f21-2b6d0c9e5a71"),
        template_version=3,
    )
    assert issued.broken == (), [row.reason for row in issued.broken]
    return billing_models.Invoice.objects.get(pk=draft.pk)


def test_cr059_cs19__a_deposit_paid_at_the_counter_is_not_billed_on_the_issued_bill(brazos, dana):
    """CS-19's OWN Proof, which nothing in this repository had run.

    *"Take a deposit, issue the first bill, and the deposit line reads zero
    owing — the case the test suite already describes and cannot exercise end to
    end."* WE-6's figures: **150.00** asked, **150.00** paid last week at the
    counter, and the ISSUED bill carries **no deposit line at all** — not a
    $0.00 one, which would say a deposit was assessed and waived.

    ⚠ It is asserted on the ISSUED row rather than on the draft deliberately.
    `test_us_bil_010`'s own docstring says of itself *"This file never issued
    one"*, and that is how DEF-181 survived: the deposit line priced correctly
    for weeks while `issue._gl_account_for` refused every bill that carried one.
    """
    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana, account_no="ACC-59040")
        _a_deposit_rule(brazos, plan, account)
        _pay(dana, account, DEPOSIT_ASKED, purpose=payment_models.PURPOSE_DEPOSIT)

        bill = _issue_the_first_bill(brazos, dana, account, plan, key="2026-06|cs19-paid")

        assert bill.issued_at is not None, "the bill actually issued"
        deposits = [line for line in bill.lines.all() if line.kind == "deposit"]
        assert deposits == [], "the utility does not hold the customer's deposit twice"


def test_cr059_cs19__a_part_paid_deposit_bills_the_remainder_on_the_issued_bill(brazos, dana):
    """**150.00** asked, **50.00** paid → the issued bill carries **100.00**,
    once, untaxed, and stamped to the deposit-liability designation rather than
    to revenue (US-LED-001: *"never revenue"*)."""
    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana, account_no="ACC-59041")
        _a_deposit_rule(brazos, plan, account)
        _pay(dana, account, Decimal("50.00"), purpose=payment_models.PURPOSE_DEPOSIT)

        bill = _issue_the_first_bill(brazos, dana, account, plan, key="2026-06|cs19-part")

        deposits = [line for line in bill.lines.all() if line.kind == "deposit"]
        assert len(deposits) == 1
        assert deposits[0].amount == Decimal("100.00"), "the REMAINDER, not the whole"
        assert deposits[0].taxable is False, "B4.2 — a deposit is never taxed"


def test_cr059_cs19__the_seam_is_what_billing_asks_through_and_it_resolves(brazos, dana):
    """CS-19 reads *"billing never asks for it"*, and that was measured by grep.

    There is no import and no literal call site to find: `billing/payments_seam`
    resolves `apps.payments.credit.deposit_payments_for_account` BY NAME at call
    time (B1), which is exactly why a grep finds nothing. This asserts the
    contract from both ends so the claim cannot go stale in either direction.
    """
    from apps.billing import payments_seam
    from apps.payments import credit

    assert payments_seam.CREDIT_DEPOSIT_READ == "deposit_payments_for_account"
    assert callable(getattr(credit, payments_seam.CREDIT_DEPOSIT_READ))
    with tenant_ctx(brazos):
        _cycle, _plan, account = _a_first_bill_world(brazos, dana, account_no="ACC-59042")
        _pay(dana, account, DEPOSIT_ASKED, purpose=payment_models.PURPOSE_DEPOSIT)
        assert payments_seam.deposit_paid_for_account(account.pk) == DEPOSIT_ASKED
