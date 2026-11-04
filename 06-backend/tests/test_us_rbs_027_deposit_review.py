# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-027 (EP-RBS-05) — CR-075 wave R′, runbook 15.
# Rules:    BR-RBS-004 · BR-RBS-010 · BR-RBS-012 · BR-RBS-014 · BR-RBS-018 ·
#           BR-RBS-020 · BR-RBS-021 · BR-RBS-023 · BR-RBS-035 · BR-CUS-050 ·
#           BR-CUS-057 · BR-PAY-021 · CLAUDE.md hard rule 2 · B14 rules 31, 32
# Golden:   ❄️ GT-61 — $150 @ 2.0%, 89 months → $22.25. Asserted here as a
#           figure this runbook CARRIES; the arithmetic itself is asserted in
#           tests/test_cr059_cs20_deposit_interest.py, where it belongs.
# Tests:    this file.
# Impacts:  apps/runbooks/definitions/deposit_review.py
# ───────────────────────────────────────────────────────
"""Runbook 15, against the rules rather than against itself.

⚠ **THE SEAMS ARE REPLACED, AND THREE CASES CAN BE PROVED NOWHERE ELSE.** On the
seeded tenant every account is `is_sample=True` and the deposit interest rate is
**0.000000**, so a **credit**, a **refund over the limit** and a **non-zero
interest figure** cannot be reached with real data at all. They are exercised
here; what the real tenant produces is in the lane report beside them, and
neither number is quoted alone.

⚠ **WHAT WOULD MAKE THIS FILE PASS WRONGLY** (hard-won law 7, habit 2), asked of
each case before it was written:

* **A fixture that releases everything.** The default state below is *nothing is
  eligible* — no history, no rate — so a case that forgets to give the runbook a
  clean payer cannot accidentally assert on a happy path.
* **A case that would be green on a runbook with the guard deleted.** Every
  guard case gives the runbook a subject it WOULD otherwise act on, and asserts
  the count moved as well as the row vanishing.
* **Asserting a sentence the fixture wrote.** The account label is `"A-10432"`
  and never contains the id, so the *no database id on screen* case fails over
  the RUNBOOK rather than over the fixture (`test_us_rbs_034`'s own near-miss).
"""

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.runbooks import models
from apps.runbooks.contract import BLOCK_TYPES, validate_report
from apps.runbooks.definitions import deposit_review as dr
from apps.runbooks.engine import executor
from core import tenancy as core_tenancy
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 1)

#: ⚠ **REAL UUIDs, AND A REAL RUN ROW, BECAUSE `acts.plan()` WRITES ONE.**
#: `runbook_run_records.run_id` is NOT NULL, so a context with `run_id=None`
#: makes every INSERT raise `IntegrityError` — which `plan()` correctly reads as
#: *"already done"* and returns `already=True`. A fixture that skipped the run
#: row would therefore turn every write step into `already` and pass the shape
#: of the assertions while proving the opposite of what they say. That is a
#: false pass of exactly the kind hard-won law 7's second habit asks about, and
#: it is why this file builds the row.
ACCOUNT_A = "8b1d6c0e-0000-4000-8000-000000000001"
ACCOUNT_B = "8b1d6c0e-0000-4000-8000-000000000002"


def _deposit(
    account_id=ACCOUNT_A,
    account_no="A-10432",
    held="150.0000",
    received_on="2019-04-01",
    eligible=True,
    closed=False,
):
    return {
        "account_id": account_id,
        "account_no": account_no,
        "label": account_no,
        "held": held,
        "currency": "USD",
        "received_on": received_on,
        "held_days": 2000,
        "eligible": eligible,
        "closed": closed,
        "interest_accrued_so_far": "0.0000",
    }


def _verdict(on_time=True, past_due_today=False, bills=12):
    return {
        "on_time": on_time,
        "bills_looked_at": bills,
        "bills_late": 0 if on_time else 1,
        "bills_open_now": 1 if past_due_today else 0,
        "bills_with_no_due_date": 0,
        "past_due_today": past_due_today,
    }


@pytest.fixture()
def run_row(brazos):
    """A real runbook and a real run for this tenant — see the note above."""
    runbook = models.Runbook.objects.create(
        tenant=brazos,
        key=dr.RUNBOOK_KEY,
        name=dr.RUNBOOK.name,
        kind=dr.RUNBOOK.kind,
        category=dr.RUNBOOK.category,
        subject_type=dr.RUNBOOK.subject_type,
        unit_of_work=dr.RUNBOOK.unit_of_work,
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
    """Fixed answers for the five reads runbook 15 makes.

    Defaults deliberately settle NOTHING: one deposit, no payment history and no
    interest rate. A case must add what it wants to prove.
    """
    state = {
        "deposits": [_deposit()],
        "verdicts": {},
        "history_readable": True,
        "rate": None,
        "accrued": {},
        "samples": frozenset(),
        "position": {},
    }
    monkeypatch.setattr(
        dr.payments_seam,
        "deposits_held",
        lambda *, as_of, months=12: {
            "rows": list(state["deposits"]),
            "readable": True,
            "cutoff": "2025-09-01",
            "months": months,
            "held_count": len(state["deposits"]),
            "eligible_count": len([one for one in state["deposits"] if one["eligible"]]),
            "undated_count": 0,
            "held_value": "150.0000",
        },
    )
    monkeypatch.setattr(
        dr.payments_seam,
        "payment_history_verdict",
        lambda ids, *, as_of, months=12: {
            "verdicts": {str(one): state["verdicts"].get(str(one), _verdict(on_time=None, bills=0)) for one in ids},
            "readable": state["history_readable"],
            "from": "2025-09-01",
            "to": "2026-09-01",
        },
    )
    monkeypatch.setattr(
        dr.payments_seam,
        "open_bill_position",
        lambda account_id: state["position"].get(str(account_id)),
    )
    monkeypatch.setattr(
        dr.customers_seam, "sample_account_ids", lambda: frozenset(state["samples"])
    )
    monkeypatch.setattr(
        dr.customers_seam, "deposit_interest_rate_annual", lambda: state["rate"]
    )
    monkeypatch.setattr(
        dr.customers_seam,
        "deposit_interest_accrued",
        lambda account_id, *, as_of: state["accrued"].get(str(account_id)),
    )
    return state


def _run(run_row, params=None):
    # ⚠ **THE GUC, NOT ONLY `ctx.tenant_id`.** The engine writes an audit row for
    # every act (hard rule 7) and `core.audit` refuses an orphaned one by name —
    # *"no tenant context set for audit row 'runbook.port_write'"* (`BR-AUD-007`).
    # A context object carrying a tenant id is not the same thing as
    # `app.tenant_id` being SET, and hard rule 1 is about the second.
    definition = dr.RUNBOOK
    ctx = executor.build_context(
        definition,
        tenant_id=run_row.tenant_id,
        run_id=run_row.pk,
        params={"as_of": TODAY.isoformat(), **(params or {})},
    )
    with core_tenancy.tenant_context(run_row.tenant_id):
        return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _plan(result):
    return (result.set_results.get(dr.STEP_DECIDE) or {}).get("plan", {})


def _clean_payer(state, **deposit):
    """One deposit whose account has twelve months of on-time payment behind it."""
    row = _deposit(**deposit)
    state["deposits"] = [row]
    state["verdicts"] = {row["account_id"]: _verdict()}
    state["rate"] = Decimal("2.000000")
    state["accrued"] = {row["account_id"]: Decimal("22.2500")}
    return row


# ── the day is an argument, never a clock (BR-TEN-043 / G6) ───────────────


def test_a_run_with_no_business_day_refuses_and_says_why(seams, run_row):
    with pytest.raises(ValueError) as caught:
        executor.execute(dr.RUNBOOK, tenant_id=run_row.tenant_id, params={})
    assert "never a clock read" in str(caught.value)


# ── guards — absolute, before step 1 (BR-RBS-012) ─────────────────────────


def test_a_sample_deposit_is_never_acted_on_and_is_still_counted(seams, run_row):
    """`BR-RBS-014`. It would otherwise be credited, which is what makes this
    case fail on a build with the guard removed rather than on an empty set."""
    row = _clean_payer(seams)
    seams["position"] = {row["account_id"]: {"bills": [{"invoice_id": "i1", "open": "40.0000"}]}}
    assert len(_run(run_row).records) == 2  # settle + letter

    seams["samples"] = frozenset({row["account_id"]})
    result = _run(run_row)
    assert result.records == ()
    # BR-RBS-035 — no record row, and still in the counts.
    assert result.counts.get("skipped") == 1


def test_an_account_past_due_this_morning_is_guarded_and_the_step_says_so(seams, run_row):
    row = _clean_payer(seams)
    seams["verdicts"] = {row["account_id"]: _verdict(past_due_today=True)}
    result = _run(run_row)
    assert result.records == ()
    assert result.counts.get("skipped") == 1
    past_due = result.set_results[dr.STEP_PAST_DUE]
    assert past_due["past_due_today"] == 1
    # *The morning of, not the month of* — the day is on the result.
    assert past_due["checked_on"] == TODAY.isoformat()


def test_the_plan_voided_guard_is_declared_and_cannot_fire_and_the_run_says_so(seams, run_row):
    """A guard a clerk reads as protection and which is not there is worse than
    an absent one. `payment_plans` has no `voided` status, so the runbook prints
    the absence rather than implying the exclusion happened."""
    assert any(one.key == "plan_voided" for one in dr.RUNBOOK.guards)
    _clean_payer(seams)
    absences = _blocks(_run(run_row))["downloads"]["stated_absences"]
    assert any("records a failed plan and a finished one the same way" in one for one in absences)


# ── TC-RBS-027.1 · the interest, and the frozen figure it carries ─────────


def test_interest_is_read_from_customers_and_never_computed_here(seams, run_row):
    """❄️ `GT-61` — $150 @ 2.0% over 89 months is **$22.25**.

    Asserted as the figure the runbook CARRIES. The arithmetic is asserted in
    `test_cr059_cs20_deposit_interest.py`; a second implementation of a frozen
    money rule is what B4's freeze exists to prevent.
    """
    _clean_payer(seams)
    interest = _run(run_row).set_results[dr.STEP_INTEREST]
    # Four decimals stored — the renderer shows two (hard rule 2).
    assert interest["total"] == "22.2500"
    assert interest["rate_configured"] is True


def test_a_zero_rate_and_an_unreadable_rate_are_different_sentences(seams, run_row):
    """One means *this state requires no interest*; the other means *we could
    not find out*. Paying the first as the second is a compliance failure."""
    row = _clean_payer(seams)

    seams["rate"] = Decimal("0.000000")
    seams["accrued"] = {row["account_id"]: Decimal("0.0000")}
    tile = _interest_tile(_run(run_row))
    assert tile["detail"] == "No interest rate is set for this utility"

    seams["rate"] = None
    seams["accrued"] = {row["account_id"]: None}
    result = _run(run_row)
    assert _interest_tile(result)["detail"] == "The rate could not be read"
    # And the deposit is NOT settled on an interest figure nobody could take.
    assert _plan(result)[row["account_id"]]["outcome"] == dr.OUTCOME_NOT_CONFIGURED


def _interest_tile(result):
    return next(
        one for one in _blocks(result)["kpis"]["tiles"] if one["id"] == "interest"
    )


def test_a_zero_interest_tile_never_ships_without_its_sentence(seams, run_row):
    """A bare `$0.00` reads as *worked out and nil*. The detail line is what
    stops that, and it is asserted rather than trusted."""
    row = _clean_payer(seams)
    seams["rate"] = Decimal("0.000000")
    seams["accrued"] = {row["account_id"]: Decimal("0.0000")}
    tile = _interest_tile(_run(run_row))
    assert tile["value"] == {"kind": "money", "amount": "0.0000", "currency": "USD"}
    assert tile["detail"]


# ── TC-RBS-027.3 · every refund names WHY, in one of two sentences ────────


def test_a_closed_account_is_a_refund_and_says_account_closed(seams, run_row):
    row = _clean_payer(seams, closed=True)
    decision = _plan(_run(run_row))[row["account_id"]]
    assert decision["outcome"] == dr.OUTCOME_REFUND_WAITING
    assert decision["why"] == "Account closed"


def test_a_deposit_over_the_limit_is_a_refund_and_says_the_limit(seams, run_row):
    row = _clean_payer(seams, held="1000.0000")
    seams["accrued"] = {row["account_id"]: Decimal("20.0000")}
    decision = _plan(_run(run_row))[row["account_id"]]
    assert decision["outcome"] == dr.OUTCOME_REFUND_WAITING
    # ⚠ TWO DECIMALS IN CLERK COPY, never the stored four (hard rule 2).
    assert decision["why"] == "Over the $250.00 limit"
    assert "250.0000" not in decision["why"]


def test_an_open_account_under_the_limit_is_a_credit(seams, run_row):
    row = _clean_payer(seams)
    seams["position"] = {row["account_id"]: {"bills": [{"invoice_id": "i1", "open": "40.0000"}]}}
    decision = _plan(_run(run_row))[row["account_id"]]
    assert decision["outcome"] == dr.OUTCOME_CREDITED
    assert decision["settle_by"] == "credit"


def test_a_credit_with_no_open_bill_says_so_rather_than_inventing_a_path(seams, run_row):
    """`post_credit`'s bound writer draws a credit down against an OPEN INVOICE
    (`BR-PAY-010`). An account with nothing open has nowhere to put it, and the
    row says so instead of the runbook inventing a second credit path."""
    _clean_payer(seams)
    seams["position"] = {}
    outcome = next(
        one for one in _run(run_row).records if one.step_key == dr.STEP_SETTLE
    )
    assert outcome.outcome == dr.OUTCOME_NO_OPEN_BILL
    assert "nothing open" in outcome.reason


# ── the on-time verdict is three-valued, and the third value is load-bearing ──


def test_an_account_with_no_bills_is_not_released(seams, run_row):
    """The false pass this file was written to catch.

    Two of the five deposits on the seeded tenant belong to accounts with ZERO
    issued bills. A build that started every verdict at *on time* would release
    both — $300.00 out of the door on evidence nobody has.
    """
    row = _clean_payer(seams)
    seams["verdicts"] = {row["account_id"]: _verdict(on_time=None, bills=0)}
    decision = _plan(_run(run_row))[row["account_id"]]
    assert decision["outcome"] == dr.OUTCOME_NOT_ELIGIBLE
    assert decision["why"] == dr.NOT_ELIGIBLE_SENTENCES["no_history"]


def test_a_bill_paid_late_holds_the_deposit_and_names_the_reason(seams, run_row):
    row = _clean_payer(seams)
    seams["verdicts"] = {row["account_id"]: _verdict(on_time=False)}
    decision = _plan(_run(run_row))[row["account_id"]]
    assert decision["outcome"] == dr.OUTCOME_NOT_ELIGIBLE
    assert decision["why"] == dr.NOT_ELIGIBLE_SENTENCES["paid_late"]


def test_a_deposit_with_no_receipt_date_stays_in_scope_and_is_not_settled(seams, run_row):
    """Dropping it would make it invisible for ever on the one screen whose job
    is finding money a utility owes back."""
    row = _deposit(received_on=None, eligible=False)
    seams["deposits"] = [row]
    result = _run(run_row)
    assert [one.subject_id for one in result.subjects] == [row["account_id"]]
    assert _plan(result)[row["account_id"]]["why"] == dr.NOT_ELIGIBLE_SENTENCES["no_receipt_date"]


def test_a_deposit_held_too_short_a_time_is_not_in_scope_at_all(seams, run_row):
    seams["deposits"] = [_deposit(eligible=False)]
    assert _run(run_row).subjects == ()


# ── TC-RBS-027.2 · nothing leaves on one approval (BR-RBS-018) ────────────


def test_the_approve_refunds_control_is_drawn_disabled_with_its_reason(seams, run_row):
    """B14 draws a control a user may not use DISABLED with its reason, never
    hidden — and `OQ-RBS-1732` closed with every money action carrying a second
    approval and NO threshold, so this is never enabled by any parameter."""
    _clean_payer(seams, closed=True)
    action = _blocks(_run(run_row))["action"]
    assert action["enabled"] is False
    assert action["reason"] == "A second admin approves refunds"
    # B14 rule 33 — a refusal caps at five or six words.
    assert len(action["reason"].split()) <= 6


def test_a_refund_never_reaches_done_in_a_dry_run(seams, run_row):
    """No runbook is on `LIVE_ENABLED_RUNBOOKS`, so the port has no writer and
    the engine records `planned` on the identical statements a live run walks."""
    _clean_payer(seams, closed=True)
    settle = next(one for one in _run(run_row).records if one.step_key == dr.STEP_SETTLE)
    assert settle.outcome == "planned"


def test_there_is_no_threshold_parameter_on_this_runbook(seams):
    """`OQ-RBS-1732` closed on 2026-09-06: every money-bearing action carries the
    second approval and there is NO threshold. Adding one would be a new ruling,
    and a threshold can only ever WIDEN what an automation may do unattended."""
    names = {one.name for one in dr.RUNBOOK.parameters}
    assert not any("threshold" in one for one in names)


# ── the report obeys the contract (BR-RBS-020 · BR-RBS-021 · DEF-RBS-4352) ──


def test_the_report_validates_at_close_and_names_only_the_twelve(seams, run_row):
    _clean_payer(seams)
    frozen = validate_report(_run(run_row).report, runbook_key=dr.RUNBOOK_KEY)
    assert {one["block"] for one in frozen} <= set(BLOCK_TYPES)


def test_the_records_empty_state_carries_the_two_fields_the_renderer_reads(seams, run_row):
    """`RecordsPayload.empty` is `{title, helper}` — `DEF-RBS-4352` one level
    down: the payload validator checks the top-level key and not its shape, so a
    `{headline, body}` empty state renders two blank lines with every test
    green."""
    seams["deposits"] = []
    empty = _blocks(_run(run_row))["records"]["empty"]
    assert set(empty) == {"title", "helper"}
    assert empty["title"] and empty["helper"]


def test_no_database_id_and_no_rule_id_reaches_a_clerk(seams, run_row):
    """B14 rules 31 and 32. `decided_by_rule` IS on every row, in `meta`, and no
    block draws it — this is what proves that."""
    row = _clean_payer(seams, closed=True)
    rows = _blocks(_run(run_row))["records"]["rows"]
    drawn = str([one["cells"] for one in rows])
    assert row["account_id"] not in drawn
    assert "BR-" not in drawn and "OQ-" not in drawn
    assert all("decided_by_rule" in one["meta"] for one in rows)


def test_every_row_carries_a_reason_a_person_can_read(seams, run_row):
    """`BR-RBS-010` — every record states the rule that decided it, in words."""
    _clean_payer(seams, closed=True)
    assert all(one.reason.strip() for one in _run(run_row).records)
    assert all(one.decided_by_rule.strip() for one in _run(run_row).records)


def test_the_stated_absences_carry_a_number_and_not_only_a_sentence(seams, run_row):
    """Hard-won law 7's fifth shape: a declared blind spot with no NUMBER
    attached is indistinguishable from an empty one."""
    row = _deposit()
    seams["deposits"] = [row]
    seams["verdicts"] = {row["account_id"]: _verdict(on_time=None, bills=0)}
    absences = _blocks(_run(run_row))["downloads"]["stated_absences"]
    assert any("1 of these accounts have no bills" in one for one in absences)


# ── the shape of the declaration ──────────────────────────────────────────


def test_the_steps_declare_the_modes_the_card_asks_for(seams, run_row):
    """`TC-RBS-17`: a set step runs ONCE and a per-record step once per subject.
    Registering a set step as per-record is a real mistake with a real cost —
    one payment-history read per deposit on the morning of the 1st."""
    _clean_payer(seams)
    runs = _run(run_row).step_runs
    assert runs[dr.STEP_ON_TIME] == 1
    assert runs[dr.STEP_INTEREST] == 1
    assert runs[dr.STEP_SETTLE] == 1


def test_it_holds_exactly_the_three_ports_the_story_names(seams):
    assert set(dr.RUNBOOK.ports) == {"post_credit", "raise_refund", "queue_notice"}
