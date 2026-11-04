# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-036 (EP-RBS-05) — CR-075 wave R′, runbook 26.
# Rules:    BR-RBS-013 (a correction is a NEW row through the owning module —
#           CLAUDE.md hard rule 4) · BR-RBS-018 · BR-RBS-027 · BR-RBS-004 ·
#           BR-RBS-010 · BR-RBS-012 · BR-RBS-014 · BR-RBS-020 · BR-RBS-021 ·
#           BR-RBS-035 · BR-PAY-013 · BR-PAY-1070 · BR-BIL-007 ·
#           CLAUDE.md hard rule 2 · B14 rules 31, 32, 33
# Tests:    this file.
# Impacts:  apps/runbooks/definitions/returned_payments.py
# ───────────────────────────────────────────────────────
"""Runbook 26, against the rules rather than against itself.

⚠ **ON EVERY DEPLOYMENT TODAY THIS RUNBOOK STOPS AT STEP 1, AND EVERYTHING AFTER
IT CAN BE PROVED NOWHERE ELSE.** There is no returns feed, no column for a bank's
return code, and no port that reverses a payment — three separate absences, named
in the module docstring and carried by `OQ-RBS-1756`. So steps 2 to 6 are
exercised HERE with a feed supplied, and the point of doing that is stated rather
than implied: **the day the feed lands, this runbook works without a line
changing in it.**

⚠ **WHAT WOULD MAKE THIS FILE PASS WRONGLY** (hard-won law 7, habit 2):

* **A default fixture with a feed in it.** The default is the STOP — the screen
  every real utility meets — so the stop cases cannot be green by accident and a
  case wanting items has to ask.
* **Asserting the stop and not asserting what a stopped run DRAWS.** A stop that
  drew a KPI strip reading *0 reversed · $0.00* would pass a headline check and
  fail the clerk. So the shape of the stopped report is asserted block by block.
* **A privilege case at one return.** `BR-PAY-013`'s limit is 2, so an account
  at ONE prior return plus this one is exactly at it and an account at zero is
  not — the fixture carries both, and one alone is green whether the limit is
  read or inlined.
"""

import datetime as dt

import pytest
from django.utils import timezone

from apps.runbooks import models
from apps.runbooks.contract import BLOCK_TYPES, validate_report
from apps.runbooks.definitions import returned_payments as rp
from apps.runbooks.engine import executor
from core import tenancy as core_tenancy
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 7)

#: Real UUIDs — `acts.plan()` writes a row whose `subject_id` is a `UUIDField`.
#: See `test_us_rbs_027_deposit_review.py` for why a missing run row is a FALSE
#: PASS rather than a crash.
ITEM_ONE = "8b1d6c0e-0000-4000-8000-00000000cc01"
ITEM_TWO = "8b1d6c0e-0000-4000-8000-00000000cc02"
ITEM_UNMATCHED = "8b1d6c0e-0000-4000-8000-00000000cc03"
ACCOUNT_ONE = "8b1d6c0e-0000-4000-8000-00000000dd01"
ACCOUNT_TWO = "8b1d6c0e-0000-4000-8000-00000000dd02"


def _item(
    item_id=ITEM_ONE,
    account_id=ACCOUNT_ONE,
    account_no="A-10432",
    payment_id="pay-1",
    amount="292.8700",
    bank_said="Insufficient funds",
    already_reversed=False,
):
    return {
        "item_id": item_id,
        "label": "PMT-000412",
        "reference": "CHECK 4410",
        "account_id": account_id,
        "account_no": account_no,
        "payment_id": payment_id,
        "amount": amount,
        "currency": "USD",
        "bank_said": bank_said,
        "already_reversed": already_reversed,
    }


@pytest.fixture()
def run_row(brazos):
    runbook = models.Runbook.objects.create(
        tenant=brazos,
        key=rp.RUNBOOK_KEY,
        name=rp.RUNBOOK.name,
        kind=rp.RUNBOOK.kind,
        category=rp.RUNBOOK.category,
        subject_type=rp.RUNBOOK.subject_type,
        unit_of_work=rp.RUNBOOK.unit_of_work,
    )
    return models.RunbookRun.objects.create(
        tenant=brazos,
        runbook=runbook,
        version=1,
        mode=models.MODE_DRY,
        status=models.RUN_STATUS_RUNNING,
        started_at=timezone.now(),
    )


@pytest.fixture
def seams(monkeypatch):
    """The default is the STOP — no feed — which is what every deployment is."""
    state = {
        "feed_available": False,
        "items": [],
        "already_by_hand": 0,
        "prior": {},
        "settings": {
            "readable": True,
            "reminder_days_before": 3,
            "missed_notice_days_after": 1,
            "void_after_misses": 2,
            "returns_before_privilege_lost": 2,
        },
        "samples": frozenset(),
    }
    monkeypatch.setattr(
        rp.payments_seam,
        "returned_items_landed",
        lambda *, as_of, window_days=1: {
            "rows": list(state["items"]),
            "feed_available": state["feed_available"],
            "why_not": (
                ""
                if state["feed_available"]
                else "no bank returns feed is connected, and nothing in this product records a "
                "return code, so returned items cannot be found automatically."
            ),
            "from": (as_of - dt.timedelta(days=window_days)).isoformat(),
            "to": as_of.isoformat(),
            "already_reversed_by_hand": state["already_by_hand"],
            "missing": (
                "a returns operation on a payment connection",
                "a column for the bank's return code and its reason",
                "an importer for a returns file",
            ),
        },
    )
    monkeypatch.setattr(
        rp.payments_seam,
        "returned_payment_counts",
        lambda ids: {str(one): state["prior"].get(str(one), 0) for one in ids},
    )
    monkeypatch.setattr(
        rp.payments_seam, "plan_notice_settings", lambda: dict(state["settings"])
    )
    monkeypatch.setattr(
        rp.customers_seam, "sample_account_ids", lambda: frozenset(state["samples"])
    )
    return state


def _run(run_row, params=None):
    ctx = executor.build_context(
        rp.RUNBOOK,
        tenant_id=run_row.tenant_id,
        run_id=run_row.pk,
        params={"as_of": TODAY.isoformat(), **(params or {})},
    )
    # ⚠ **THE GUC, NOT ONLY `ctx.tenant_id`.** The engine writes an audit row
    # for every act (hard rule 7) and `core.audit` refuses an orphaned one by
    # name — *"no tenant context set for audit row 'runbook.port_write'"*
    # (`BR-AUD-007`). A context object carrying a tenant id is not the same
    # thing as `app.tenant_id` being SET, and hard rule 1 is about the second.
    with core_tenancy.tenant_context(run_row.tenant_id):
        return executor.execute(rp.RUNBOOK, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _outcomes(result, step):
    return {
        one.subject.label: one.outcome for one in result.records if one.step_key == step
    }


def _with_feed(state, items=None):
    state["feed_available"] = True
    state["items"] = items if items is not None else [_item()]
    return state["items"]


# ── the day is an argument, never a clock (BR-TEN-043 / G6) ───────────────


def test_a_run_with_no_business_day_refuses_and_says_why(seams, run_row):
    with pytest.raises(ValueError) as caught:
        executor.execute(rp.RUNBOOK, tenant_id=run_row.tenant_id, params={})
    assert "never a clock read" in str(caught.value)


# ── the STOP, which is the screen every real utility meets ────────────────


def test_no_feed_stops_the_run_and_names_all_three_absences(seams, run_row):
    stop = _run(run_row).set_results[rp.STEP_GATHER]["stop"]
    assert stop["headline"] == "No returns have landed."
    assert "No bank returns feed is connected" in stop["detail"]
    assert "records the code a bank sends back" in stop["detail"]
    assert "Connect a payment provider" in stop["detail"]


def test_a_stopped_run_draws_no_kpi_strip(seams, run_row):
    """A strip reading *0 reversed · $0.00 · 0 need a person* over a run that
    examined nothing is indistinguishable from a clean morning."""
    blocks = _blocks(_run(run_row))
    assert "kpis" not in blocks
    assert set(blocks) == {"verdict", "sentence", "chain", "records"}


def test_a_stopped_run_says_stopped_and_never_says_failed(seams, run_row):
    """The Product Owner ruled this a valid state. A screen calling it a failure
    would be arguing with them."""
    result = _run(run_row)
    assert _blocks(result)["verdict"]["word"] == "Stopped"
    assert "failed" not in str(result.report).lower()


def test_every_later_step_reads_never_reached(seams, run_row):
    """`BR-RBS-027`. A blank cell reads as *nothing wrong*; **Never reached**
    reads as *it never ran*. They are opposite sentences."""
    cells = _blocks(_run(run_row))["chain"]["cells"]
    assert len(cells) == len(rp.RUNBOOK.steps)
    assert cells[0]["state"] == "bad"
    assert [one["note"] for one in cells[1:]] == ["Never reached"] * (len(cells) - 1)


def test_the_number_travels_beside_the_absence(seams, run_row):
    """The only figure on this deployment that would move if the feed arrived,
    and a stop without it leaves a cashier unable to tell *nothing bounced* from
    *nothing can tell us*."""
    seams["already_by_hand"] = 4
    stop = _run(run_row).set_results[rp.STEP_GATHER]["stop"]
    assert "4 were reversed by hand in this window" in stop["detail"]
    assert _run(run_row).set_results[rp.STEP_GATHER]["checked"]["already_reversed_by_hand"] == 4


def test_the_what_to_do_box_is_the_sentence_block(seams, run_row):
    sentence = _blocks(_run(run_row))["sentence"]
    assert sentence["label"] == "What to do"
    assert sentence["tone"] == "muted"


# ── TC-RBS-036.1 · a reversal is planned, never performed ────────────────


def test_a_returned_item_is_planned_for_reversal_and_names_who_performs_it(seams, run_row):
    """There is no port that reverses a payment: `reverse_payment` is Admin-only
    on the SERVICE (`BR-PAY-1070`) and is bound to nothing, deliberately."""
    _with_feed(seams)
    outcome = next(one for one in _run(run_row).records if one.step_key == rp.STEP_REVERSE)
    assert outcome.outcome == rp.OUTCOME_TO_REVERSE
    assert "only an administrator can" in outcome.reason
    assert outcome.data["reversal_needs_an_admin"] is True


def test_nothing_this_runbook_holds_could_reverse_a_payment(seams, run_row):
    """The structural half of `TC-RBS-036.1`: the original payment cannot be
    touched because there is no port that reaches it."""
    assert set(rp.RUNBOOK.ports) == {"apply_fee", "queue_notice", "flag_account"}
    assert "apply_payment" not in rp.RUNBOOK.ports


def test_an_item_matching_no_payment_is_listed_and_never_dropped(seams, run_row):
    """A returned item nobody can place is exactly the row a cashier must see."""
    _with_feed(seams, [_item(item_id=ITEM_UNMATCHED, payment_id=None)])
    outcome = next(one for one in _run(run_row).records if one.step_key == rp.STEP_REVERSE)
    assert outcome.outcome == rp.OUTCOME_NO_MATCH
    assert outcome.fix_route == rp.FIX_PAYMENTS


# ── TC-RBS-036.2 · the fee waits on a second approval ────────────────────


def test_no_fee_is_applied_when_the_utility_named_no_charge_code(seams, run_row):
    """`BR-BIL-007`: the fee is the tenant's own charge code, never typed. **A
    runbook must not decide that a customer owes a fee.**"""
    _with_feed(seams)
    outcome = next(one for one in _run(run_row).records if one.step_key == rp.STEP_FEE)
    assert outcome.data["fee"] == "no_charge_code"
    assert "No returned-payment charge code is set" in outcome.reason


def test_a_named_charge_code_drafts_the_fee_and_it_still_waits(seams, run_row):
    """`OQ-RBS-1732` closed with every money-bearing action carrying the second
    approval and NO threshold, so the fee reaches `planned` and never `done` —
    and `issue_charge_fee` is bound to no port at all, so a person issues it."""
    _with_feed(seams)
    outcome = next(
        one
        for one in _run(run_row, {"returned_payment_charge_code": "NSF"}).records
        if one.step_key == rp.STEP_FEE
    )
    assert outcome.data["fee"] == "planned"
    assert "The fee waits for a second person." in outcome.reason


def test_there_is_no_threshold_parameter_on_this_runbook():
    names = {one.name for one in rp.RUNBOOK.parameters}
    assert not any("threshold" in one for one in names)


# ── TC-RBS-036.3 · the Nth return removes the privilege, naming the rule ──


def test_the_privilege_is_removed_at_the_limit_and_not_before(seams, run_row):
    """The fixture carries an account at ONE prior return — which with this one
    is exactly the limit — and one at zero, which is not. One alone is green
    whether the limit is read from Settings or inlined."""
    _with_feed(
        seams,
        [
            _item(item_id=ITEM_ONE, account_id=ACCOUNT_ONE, account_no="A-10432"),
            _item(item_id=ITEM_TWO, account_id=ACCOUNT_TWO, account_no="A-10650", payment_id="pay-2"),
        ],
    )
    seams["prior"] = {ACCOUNT_ONE: 1, ACCOUNT_TWO: 0}
    privilege = _run(run_row).set_results[rp.STEP_PRIVILEGE]
    assert privilege["at_the_limit"] == 1
    assert privilege["limit"] == 2
    assert "An account loses the privilege after 2 returned payments." == privilege["reason"]


def test_the_privilege_port_is_called_and_its_own_refusal_is_recorded(seams, run_row):
    """`DEF-RBS-4331` — `customers` carries only `cash_only` and nothing
    auto-clears it, and `BR-RBS-040` forbids writing a note instead. There is no
    `if is_bound` branch: the port is called and refuses on the identical code
    path a live run walks."""
    _with_feed(seams)
    seams["prior"] = {ACCOUNT_ONE: 1}
    privilege = _run(run_row).set_results[rp.STEP_PRIVILEGE]
    assert privilege["removed"] == 0
    assert "has no writer bound" in privilege["refused"]
    absences = _blocks(_run(run_row))["downloads"]["stated_absences"]
    assert any("could not be removed automatically" in one for one in absences)


def test_an_unreadable_limit_removes_nothing_and_says_so(seams, run_row):
    _with_feed(seams)
    seams["settings"] = {"readable": False, "why_not": "the settings row could not be read"}
    privilege = _run(run_row).set_results[rp.STEP_PRIVILEGE]
    assert privilege["removed"] == 0
    assert "nobody has set how many returned payments" in privilege["reason"]


def test_the_prior_count_is_read_from_reversing_rows_not_from_nsf_count(seams, run_row):
    """`DEF-069`: `accounts.nsf_count` is never incremented on this product, so a
    limit read off it would never be reached on any account. This asserts the
    runbook asks the seam that counts ROWS."""
    _with_feed(seams)
    calls = []
    original = rp.payments_seam.returned_payment_counts
    rp.payments_seam.returned_payment_counts = lambda ids: (calls.append(list(ids)) or original(ids))
    try:
        _run(run_row)
    finally:
        rp.payments_seam.returned_payment_counts = original
    assert calls and ACCOUNT_ONE in calls[0]


# ── guards — absolute, before step 1 (BR-RBS-012) ─────────────────────────


def test_a_sample_account_is_never_charged_or_stripped(seams, run_row):
    _with_feed(seams)
    seams["samples"] = frozenset({ACCOUNT_ONE})
    result = _run(run_row)
    assert result.records == ()
    assert result.counts.get("skipped") == 1


def test_an_already_reversed_item_is_never_reversed_twice(seams, run_row):
    """A payment a person already reversed has had its letter queued and its
    ladder restarted by `reverse_payment` itself. Reversing it again would double
    the fee and double the letter, and hard rule 4 means neither could be taken
    back."""
    _with_feed(seams, [_item(already_reversed=True)])
    result = _run(run_row)
    assert result.records == ()
    assert result.counts.get("skipped") == 1


# ── the report obeys the contract (BR-RBS-020 · BR-RBS-021) ───────────────


def test_the_report_validates_at_close_on_both_shapes(seams, run_row):
    stopped = validate_report(_run(run_row).report, runbook_key=rp.RUNBOOK_KEY)
    assert {one["block"] for one in stopped} <= set(BLOCK_TYPES)
    _with_feed(seams)
    finished = validate_report(_run(run_row).report, runbook_key=rp.RUNBOOK_KEY)
    assert {one["block"] for one in finished} <= set(BLOCK_TYPES)
    assert "kpis" in {one["block"] for one in finished}


def test_the_by_reason_table_reads_the_banks_words_and_never_a_code(seams, run_row):
    """B14 rule 32, and the whole value of the table: *Insufficient funds* and
    *Account closed* need different conversations with the customer."""
    _with_feed(
        seams,
        [
            _item(),
            _item(item_id=ITEM_TWO, account_id=ACCOUNT_TWO, payment_id="pay-2", bank_said="Account closed"),
        ],
    )
    rows = _blocks(_run(run_row))["breakdown"]["rows"]
    assert {one["cells"]["reason"]["text"] for one in rows} == {
        "Insufficient funds",
        "Account closed",
    }


def test_no_database_id_reaches_a_clerk(seams, run_row):
    _with_feed(seams)
    drawn = str([one["cells"] for one in _blocks(_run(run_row))["records"]["rows"]])
    assert ITEM_ONE not in drawn
    assert ACCOUNT_ONE not in drawn
    assert "BR-" not in drawn and "OQ-" not in drawn


def test_the_result_says_out_loud_that_it_cannot_reverse(seams, run_row):
    _with_feed(seams)
    absences = _blocks(_run(run_row))["downloads"]["stated_absences"]
    assert absences[0].startswith("this run cannot reverse a payment")


# ── the shape of the declaration ──────────────────────────────────────────


def test_it_declares_no_event_trigger_because_none_is_emitted():
    """`batch.landed` is emitted by nothing (`CR-069`), and a runbook whose only
    trigger is an event is not runnable — declaring one would put a **Run ▶** on
    a screen that must refuse."""
    assert set(rp.RUNBOOK.triggers) == {models.TRIGGER_SCHEDULE, models.TRIGGER_MANUAL}


def test_the_six_steps_declare_the_modes_the_card_asks_for(seams, run_row):
    _with_feed(seams)
    runs = _run(run_row).step_runs
    assert runs[rp.STEP_GATHER] == 1
    assert runs[rp.STEP_MATCH] == 1
    assert runs[rp.STEP_PRIOR] == 1
    assert runs[rp.STEP_REVERSE] == 1
    assert runs[rp.STEP_FEE] == 1
    assert runs[rp.STEP_PRIVILEGE] == 1
