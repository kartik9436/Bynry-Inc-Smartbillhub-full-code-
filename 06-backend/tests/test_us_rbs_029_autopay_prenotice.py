# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-029 (EP-RBS-05) — CR-075 wave R′, runbook 17.
# Rules:    BR-RBS-031 (a debit that fails twice is not retried a third time) ·
#           BR-RBS-016 · BR-RBS-004 · BR-RBS-010 · BR-RBS-012 · BR-RBS-014 ·
#           BR-RBS-020 · BR-RBS-021 · BR-RBS-035 · BR-PAY-015 · BR-PAY-013 ·
#           CLAUDE.md hard rule 2 · B14 rules 31, 32
# Tests:    this file.
# Impacts:  apps/runbooks/definitions/autopay_prenotice.py
# ───────────────────────────────────────────────────────
"""Runbook 17, against the rules rather than against itself.

⚠ **THE WHOLE FAILED-DEBIT HALF CAN BE PROVED NOWHERE ELSE, AND THAT IS SAID
FIRST.** Nothing on this product drafts an autopay payment — `BR-PAY-015`,
`AutopayCaptureIntent.status` has ONE value and nothing consumes an intent — so
**no debit is ever attempted and none can fail**. `BR-RBS-031`'s *two attempts
and the third goes to the ladder* is therefore exercised HERE with the seam
replaced, and nowhere else. On the seeded tenant the runbook finds **6 accounts
on autopay and 0 debits scheduled**; both numbers are in the lane report and
neither is quoted alone.

⚠ **WHAT WOULD MAKE THIS FILE PASS WRONGLY** (hard-won law 7, habit 2):

* **A fixture that reports failures.** The default state has `reported: False`,
  which is what every deployment actually produces — so a case that wants a
  failure has to say so, and the *not reported* cases cannot be green by
  accident.
* **Asserting `0 failed` and calling it correct.** The two cases that matter
  assert the tile says **Not reported** and carries its reason, because `0` and
  *not reported* are the two readings this runbook exists to keep apart.
* **A retry case with only one attempt in it.** `BR-RBS-031` bounds the SECOND,
  so the fixture carries an attempt-1 debit and an attempt-2 debit and asserts
  the pair; one alone is green whether the bound exists or not.
"""

import datetime as dt

import pytest
from django.utils import timezone

from apps.runbooks import models
from apps.runbooks.contract import BLOCK_TYPES, validate_report
from apps.runbooks.definitions import autopay_prenotice as ap
from apps.runbooks.engine import executor
from core import tenancy as core_tenancy
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 7)

#: Real UUIDs — `acts.plan()` writes a row whose `subject_id` is a `UUIDField`
#: and whose `run_id` is NOT NULL. A missing run row is a FALSE PASS rather than
#: a crash; `test_us_rbs_027_deposit_review.py` carries the note.
FIRST = "8b1d6c0e-0000-4000-8000-00000000bb01"
CHANGED = "8b1d6c0e-0000-4000-8000-00000000bb02"
SAME = "8b1d6c0e-0000-4000-8000-00000000bb03"
PAUSED = "8b1d6c0e-0000-4000-8000-00000000bb04"


def _debit(account_id, account_no, amount="184.2000", previous=None, scheduled="2026-09-12", cash_only=False):
    return {
        "intent_id": f"intent-{account_no}",
        "account_id": account_id,
        "account_no": account_no,
        "label": account_no,
        "invoice_id": f"invoice-{account_no}",
        "amount": amount,
        "currency": "USD",
        "scheduled_on": scheduled,
        "previous_amount": previous,
        "amount_changed": previous is None or previous != amount,
        "autopay_on": True,
        "cash_only": cash_only,
    }


def _failure(account_id, account_no, attempt, bank_said="Insufficient funds", amount="96.1000"):
    return {
        "account_id": account_id,
        "account_no": account_no,
        "invoice_id": f"invoice-{account_no}",
        "amount": amount,
        "currency": "USD",
        "bank_said": bank_said,
        "attempt": attempt,
        "attempts_allowed": 2,
        "next": ap.NEXT_RETRY if attempt < 2 else ap.NEXT_LADDER,
        "retry_on": "2026-09-10",
        "decided_by_rule": "A failed debit is tried once more",
    }


@pytest.fixture()
def run_row(brazos):
    runbook = models.Runbook.objects.create(
        tenant=brazos,
        key=ap.RUNBOOK_KEY,
        name=ap.RUNBOOK.name,
        kind=ap.RUNBOOK.kind,
        category=ap.RUNBOOK.category,
        subject_type=ap.RUNBOOK.subject_type,
        unit_of_work=ap.RUNBOOK.unit_of_work,
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
    """Three debits and NO reported failures — which is what every deployment
    actually produces. A case wanting a failure has to ask for one."""
    state = {
        "debits": [
            _debit(FIRST, "A-10001"),
            _debit(CHANGED, "A-10002", amount="212.7000", previous="184.2000"),
            _debit(SAME, "A-10003", amount="184.2000", previous="184.2000"),
        ],
        "autopay_accounts": 6,
        "failures": [],
        "reported": False,
        "samples": frozenset(),
    }
    monkeypatch.setattr(
        ap.payments_seam,
        "autopay_debits_due",
        lambda *, as_of, within_days=10: {
            "rows": list(state["debits"]),
            "from": as_of.isoformat(),
            "to": (as_of + dt.timedelta(days=within_days)).isoformat(),
            "autopay_accounts": state["autopay_accounts"],
            "intents_in_total": len(state["debits"]),
            "scheduled_in_window": len(state["debits"]),
        },
    )
    monkeypatch.setattr(
        ap.payments_seam,
        "failed_debits",
        lambda *, as_of: {
            "rows": list(state["failures"]),
            "reported": state["reported"],
            "why_not": (
                ""
                if state["reported"]
                else "nothing in this product drafts an autopay payment yet, so no debit can fail."
            ),
            "as_of": as_of.isoformat(),
            "intent_statuses": ("awaiting_rails",),
        },
    )
    monkeypatch.setattr(
        ap.customers_seam, "sample_account_ids", lambda: frozenset(state["samples"])
    )
    return state


def _run(run_row, params=None):
    ctx = executor.build_context(
        ap.RUNBOOK,
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
        return executor.execute(ap.RUNBOOK, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _tile(result, tile_id):
    return next(one for one in _blocks(result)["kpis"]["tiles"] if one["id"] == tile_id)


def _outcomes(result):
    return {one.subject.label: one.outcome for one in result.records}


# ── the day is an argument, never a clock (BR-TEN-043 / BR-RBS-016 / G6) ──


def test_a_run_with_no_business_day_refuses_and_says_why(seams, run_row):
    with pytest.raises(ValueError) as caught:
        executor.execute(ap.RUNBOOK, tenant_id=run_row.tenant_id, params={})
    assert "never a clock read" in str(caught.value)


# ── TC-RBS-029.3 · the amount is the bill's own, quoted ──────────────────


def test_the_amount_told_is_the_amount_payments_recorded(seams, run_row):
    """`US-RBS-029` §7: *None of its own. The amount is the bill's, quoted.* A
    runbook that re-priced the bill would tell the customer a different number
    from the one the debit will take."""
    notified = next(
        one for one in _run(run_row).records if one.subject.label == "A-10002"
    )
    assert notified.data["amount"] == "212.7000"
    # ⚠ TWO DECIMALS IN CLERK COPY, never the stored four (hard rule 2).
    assert "$212.70" in notified.reason
    assert "212.7000" not in notified.reason


# ── the *only when the amount changed* rule ───────────────────────────────


def test_an_unchanged_amount_needs_no_notice_and_a_first_debit_always_does(seams, run_row):
    """A fixed amount needs no notice; a varying one does, which is the bank
    rule the card cites. A first-ever debit has no previous amount, so the
    customer has been told nothing at all and the safe direction is to tell
    them — reading *no history* as *unchanged* would silence the very first
    notice a customer ever gets."""
    outcomes = _outcomes(_run(run_row))
    assert outcomes["A-10001"] == "planned"  # first ever
    assert outcomes["A-10002"] == "planned"  # amount moved
    assert outcomes["A-10003"] == ap.OUTCOME_NO_NOTICE_NEEDED


def test_turning_the_toggle_off_notifies_everybody(seams, run_row):
    outcomes = _outcomes(_run(run_row, {"only_when_amount_changed": False}))
    assert set(outcomes.values()) == {"planned"}


# ── the failed-debit half: NOT REPORTED, never zero ───────────────────────


def test_the_failed_tile_says_not_reported_and_carries_its_reason(seams, run_row):
    """Hard-won law 7's fifth shape. A tile reading **0** over a product that
    cannot draft a debit is indistinguishable from a morning when every debit
    went through, and those are opposite facts."""
    tile = _tile(_run(run_row), "failed")
    assert tile["value"] == {"kind": "text", "text": "Not reported"}
    assert "drafts an autopay payment" in tile["detail"]


def test_the_records_empty_state_says_not_reported_rather_than_all_clear(seams, run_row):
    empty = _blocks(_run(run_row))["records"]["empty"]
    assert empty["title"] == "Failed debits are not reported here yet."
    assert set(empty) == {"title", "helper"}


def test_both_numbers_travel_when_nothing_is_scheduled(seams, run_row):
    """*6 on autopay · 0 scheduled* is a sentence; *0* alone is not, and it is
    what the seeded tenant actually produces."""
    seams["debits"] = []
    absences = _blocks(_run(run_row))["downloads"]["stated_absences"]
    assert any("6 accounts are on autopay and none has a debit scheduled" in one for one in absences)


def test_no_bank_reason_column_is_named_as_its_own_absence(seams, run_row):
    """Two different absences: nothing drafts a debit, AND nothing records the
    bank's reason. A lane that fixed only the first would still have an empty
    *Bank said* column."""
    absences = _blocks(_run(run_row))["downloads"]["stated_absences"]
    assert any("no column in this product holds the bank's reason" in one for one in absences)


# ── BR-RBS-031 · two attempts, and the third goes to the ladder ───────────


def test_a_first_failure_is_retried_and_a_second_goes_to_the_ladder(seams, run_row):
    """`TC-RBS-029.2`. The pair is asserted together: one attempt alone is green
    whether the bound exists or not."""
    seams["reported"] = True
    seams["failures"] = [
        _failure(FIRST, "A-10001", attempt=1),
        _failure(CHANGED, "A-10002", attempt=2, bank_said="Account closed"),
    ]
    retry = _run(run_row).set_results[ap.STEP_RETRY]
    assert retry["retried"] == 1
    assert retry["to_the_ladder"] == 1


def test_the_retry_key_carries_the_attempt_and_not_the_run(seams, run_row):
    """One retry per attempt per debit, however often this runs. Put the run in
    it and the same customer is drafted again every morning."""
    seams["reported"] = True
    seams["failures"] = [_failure(FIRST, "A-10001", attempt=1)]
    result = _run(run_row)
    assert result.set_results[ap.STEP_RETRY]["retried"] == 1
    # The engine composed the key; the run is deliberately not in it.
    from apps.runbooks.engine import acts
    from apps.runbooks.contract import SubjectRef

    key = acts.idempotency_key(
        runbook_key=ap.RUNBOOK_KEY,
        action_kind="schedule_retry",
        subject=SubjectRef(subject_type="account", subject_id=FIRST),
        discriminator="invoice-A-10001|1",
    )
    assert str(run_row.pk) not in key
    assert key.endswith("|1")


def test_the_bank_reason_reaches_the_screen_in_words_and_never_as_a_code(seams, run_row):
    """`RB-117`'s own design note, and B14 rule 32: *insufficient funds*, never
    the return code."""
    seams["reported"] = True
    seams["failures"] = [_failure(FIRST, "A-10001", attempt=1)]
    rows = _blocks(_run(run_row))["records"]["rows"]
    assert rows[0]["cells"]["bank_said"] == {"kind": "text", "text": "Insufficient funds"}
    assert rows[0]["cells"]["next"]["text"] == "Retry 2026-09-10"


def test_fix_reads_a_dash_on_a_debit_that_is_simply_retrying(seams, run_row):
    """The card says so, because there is nothing for a person to do."""
    seams["reported"] = True
    seams["failures"] = [
        _failure(FIRST, "A-10001", attempt=1),
        _failure(CHANGED, "A-10002", attempt=2),
    ]
    rows = {one["cells"]["account"]["text"]: one["cells"]["fix"] for one in _blocks(_run(run_row))["records"]["rows"]}
    assert rows["A-10001"] == {"kind": "text", "text": "—"}
    assert rows["A-10002"]["kind"] == "link"


def test_flag_account_is_called_and_its_own_refusal_is_recorded(seams, run_row):
    """`DEF-RBS-4331`: `customers` has no column for a flag with a reason, and
    `BR-RBS-040` forbids the substitute of writing a note. There is no
    `if is_bound` branch — the port is called and refuses, on the identical code
    path a live run walks (`BR-RBS-003`)."""
    seams["reported"] = True
    seams["failures"] = [_failure(FIRST, "A-10001", attempt=1)]
    retry = _run(run_row).set_results[ap.STEP_RETRY]
    assert retry["flagged"] == 0
    assert "has no writer bound" in retry["flag_refused"]
    absences = _blocks(_run(run_row))["downloads"]["stated_absences"]
    assert any("could not be flagged" in one for one in absences)


# ── guards — absolute, before step 1 (BR-RBS-012) ─────────────────────────


def test_a_sample_account_is_never_told_anything(seams, run_row):
    seams["samples"] = frozenset({FIRST})
    result = _run(run_row)
    assert "A-10001" not in _outcomes(result)
    assert result.counts.get("skipped", 0) >= 1


def test_a_cash_only_account_is_guarded(seams, run_row):
    """`BR-PAY-013`'s privilege sanction: the account cannot be drafted at all,
    so a pre-notification would promise a debit that will never happen."""
    seams["debits"] = [_debit(PAUSED, "A-10004", cash_only=True)]
    result = _run(run_row)
    assert result.records == ()
    assert result.counts.get("skipped") == 1


# ── the report obeys the contract (BR-RBS-020 · BR-RBS-021) ───────────────


def test_the_report_validates_at_close_and_names_only_the_twelve(seams, run_row):
    frozen = validate_report(_run(run_row).report, runbook_key=ap.RUNBOOK_KEY)
    assert {one["block"] for one in frozen} <= set(BLOCK_TYPES)
    # The notices are a DOWNLOAD, not a table — the card's own closed question.
    names = {one["name"] for one in _blocks(_run(run_row))["downloads"]["files"]}
    assert "Notices" in names


def test_no_database_id_reaches_a_clerk(seams, run_row):
    seams["reported"] = True
    seams["failures"] = [_failure(FIRST, "A-10001", attempt=1)]
    drawn = str([one["cells"] for one in _blocks(_run(run_row))["records"]["rows"]])
    assert FIRST not in drawn
    assert "BR-" not in drawn and "OQ-" not in drawn


# ── the shape of the declaration ──────────────────────────────────────────


def test_the_three_read_steps_are_SET_and_the_notice_is_PER_RECORD(seams, run_row):
    runs = _run(run_row).step_runs
    assert runs[ap.STEP_DEBIT] == 1
    assert runs[ap.STEP_CHANGED] == 1
    assert runs[ap.STEP_FAILED] == 1
    assert runs[ap.STEP_NOTIFY] == 3
    assert runs[ap.STEP_RETRY] == 1


def test_it_holds_exactly_the_three_ports_the_card_names():
    assert set(ap.RUNBOOK.ports) == {"queue_notice", "flag_account", "schedule_retry"}
    assert ap.RUNBOOK.category == "payments"
