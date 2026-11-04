# ── Trace ──────────────────────────────────────────────
# Rule:     **PO ruling 2026-09-21, ruling 1** — *"in single bill we have final
#           bill workflow - so if clark want to complete the bill he can do it
#           from there - we will need to allow clark to complete the cut request
#           later without bill."*
#           **PO ruling 2026-09-21, ruling 2** — *"you create the bill from last
#           bill date - if last bill was generated in feb and data is 28 feb you
#           start the bill from 1 mar - for arreras - it is previous balance -
#           bill will anyway calculate previous balance and mention it on bill;
#           hence we have accounted or all oustanding amount."*
#           **PO ruling 2026-09-21, the third sign-off** — *"A fee is a charge
#           for an event, not for a period of service - this is correct"*.
# Rules:    BR-CUS-107 · BR-CUS-103 · BR-BIL-004 · BR-BIL-035/160 ·
#           `DSC-02.4` · CLAUDE.md rule 7 (every money action writes
#           `audit_log`) · rule 4 (financial immutability)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The three rulings of 2026-09-21, each with the figure the PO was shown.

════════════════════════════════════════════════════════════════════════════
WHAT RULING 1 REVERSED, STATED SO NOBODY RESTORES IT BY ACCIDENT
════════════════════════════════════════════════════════════════════════════
`commit_cut` writes BR-CUS-107's status **only when the days are billed**, and
`finish_cut` — built 2026-09-20 under `DEF-CUS-6063` — kept that refusal: it
raised the bill and, if billing refused again, wrote nothing. **That refusal is
what the PO removed.** The reasoning behind it was ours, not theirs.

**So a cut request is COMPLETED with no bill at all and the status is written**,
and the final bill is raised afterwards from billing's own single-bill
workflow. Completing a cut and raising its final bill are two acts.

⚠ **AND THE HALF THAT MUST NOT BE LOST.** The reason the status was held is
real: a `disconnected` account leaves `selectors.accounts_for_bill_run`, so no
ordinary run will ever pick those days up. The PO ruled WHO raises the bill,
not that the days stop mattering. **`tc2` and `tc6` are that half** — the days
travel on the payload, the audit row and the record screen, and the statement
CLOSES ITSELF the day a bill covers the cut.

════════════════════════════════════════════════════════════════════════════
THE SEAM IS STUBBED AT THE MODULE BOUNDARY FOR RULING 1 AND REAL FOR RULING 2
════════════════════════════════════════════════════════════════════════════
`test_def_cus_6063_finish_the_cut.py` states the reason and it holds here:
raising a bill is BILLING's (BR-CUS-037, CLAUDE.md rule 5), so a customers test
that reached into invoice rows would be asserting another module's contract.
What ruling 1 owns is the DECISION. **Ruling 2 is billing's own arithmetic**,
so `tc8`–`tc10` run against real `invoices` and a real stamped bill.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.billing import cut_bill as billing_cut_bill
from apps.customers import disconnect_record
from apps.customers import disconnects
from apps.customers import models as customers_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    erin,
    lonestar,
    marcus,
    tenant_ctx,
)
from tests.test_w7_cut_reconnect import CUT_ON, TODAY, _scheduled
from tests.test_def_cus_6063_finish_the_cut import (  # noqa: F401
    ENGINE_SENTENCE,
    FINISH_ON,
    _answer_with,
    _blocked,
    _fee_seam_answers,
    _plain_account,
    _raised,
    _row,
    _status_of,
)

pytestmark = pytest.mark.django_db


def _held_cut(actor, tenant, monkeypatch):
    """A REALLY cut account whose final bill billing refused.

    The whole W7 ladder is walked and `commit_cut` is the thing that cuts it —
    a case put into `cut` with an UPDATE proves only that a column can hold a
    string.
    """
    account = _scheduled(actor, tenant, monkeypatch)
    _answer_with(monkeypatch, _blocked())
    cut = disconnects.commit_cut(actor, account["id"], cut_on=CUT_ON, as_of=TODAY)
    assert cut["cut_bill"]["billed"] is False, cut["cut_bill"]
    assert cut["account_status_written"] is None
    return account


def _window(monkeypatch, answer):
    """Make billing's WINDOW read answer `answer` — a `dict` or `None`."""
    monkeypatch.setattr(
        disconnects.seams, "unbilled_service_window", lambda *_a, **_k: answer
    )
    monkeypatch.setattr(disconnects.seams, "billing_selectors_answer", lambda: True)


def _refuse_to_bill(monkeypatch):
    """⚠ **A SEAM THAT EXPLODES IF IT IS CALLED AT ALL.**

    `without_bill=True` must SKIP the bill, not attempt it and ignore the
    answer, and the difference is a money act nobody asked for. A stub that
    merely returned `blocked` could not tell the two apart — the test would
    pass on an implementation that billed the customer and threw the invoice
    away. This one goes red on the call itself.
    """

    def _boom(*_a, **_k):  # pragma: no cover - the assertion IS that it never runs
        raise AssertionError(
            "billing was asked for a cut bill on a completion the clerk asked to make "
            "WITHOUT one (PO ruling 2026-09-21)."
        )

    monkeypatch.setattr(disconnects.seams, "raise_and_issue_cut_bill", _boom)


# ════════════════════════════════════════════════════════════════════════════
# RULING 1 · tc1 — THE CUT IS COMPLETED WITH NO BILL, AND THE STATUS IS WRITTEN
# ════════════════════════════════════════════════════════════════════════════
def test_tc1_a_cut_is_completed_without_a_bill_and_the_status_is_written(
    marcus, brazos, monkeypatch
):
    """The whole of ruling 1, and billing is never asked.

    RED-FIRST (r11 step 2d): before this change `finish_cut` took no such
    argument at all — `finish_cut(actor, id, as_of=…, without_bill=True)` was a
    `TypeError`, and the only path through the function raised the bill first.
    """
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        before = _status_of(account["id"])
        assert before != disconnects.CUT_STATUS_CODE

        _refuse_to_bill(monkeypatch)
        _window(monkeypatch, {"start": "2026-08-01", "end": str(CUT_ON), "days": 24})
        answer = disconnects.finish_cut(
            marcus, account["id"], as_of=FINISH_ON, without_bill=True
        )

        assert answer["finished"] is True
        assert answer["billed"] is False
        # No bill was asked for, so there is no engine answer to carry — NOT an
        # empty one. A caller must be able to tell "no bill" from "a bill that
        # came back blank".
        assert answer["cut_bill"] is None
        assert answer["completed"]["code"] == "cut_completed_without_a_final_bill"
        assert answer["account_status_written"] == disconnects.CUT_STATUS_CODE
        assert answer["account_status_before_cut"] == before
        assert _status_of(account["id"]) == disconnects.CUT_STATUS_CODE
        case = disconnects.open_case_for(account["id"])
        assert case.status_before_cut == before


def test_tc2_the_days_nobody_billed_travel_with_the_completion(
    marcus, brazos, monkeypatch
):
    """**THE HALF THAT MUST NOT BE LOST.** A `disconnected` account leaves the
    bill run, so the window has to be stated somewhere or it is nowhere."""
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        _refuse_to_bill(monkeypatch)
        _window(monkeypatch, {"start": "2026-08-01", "end": str(CUT_ON), "days": 24})
        answer = disconnects.finish_cut(
            marcus, account["id"], as_of=FINISH_ON, without_bill=True
        )

        stated = answer["days_not_billed"]
        assert stated is not None, "the days were completed away into nothing"
        assert stated["code"] == "days_before_the_cut_are_not_billed"
        assert (stated["from"], stated["to"], stated["days"]) == (
            "2026-08-01",
            str(CUT_ON),
            24,
        )


def test_tc2b_every_completion_writes_an_audit_row_carrying_the_days(
    marcus, brazos, monkeypatch, audit_rows
):
    """CLAUDE.md rule 7, and the row is where the days survive a screen refresh.

    ⚠ **READ FROM THE BE-03 SINK, NOT FROM `audit_log`** — `audit_rows` REPLACES
    the table writer for the duration of a test, so a case querying the table
    finds zero rows and reads as *"rule 7 was not honoured"* when it was.
    """
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        _refuse_to_bill(monkeypatch)
        _window(monkeypatch, {"start": "2026-08-01", "end": str(CUT_ON), "days": 24})
        disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON, without_bill=True)

        written = [
            row for row in audit_rows if row["action"] == disconnects.AUDIT_CUT_FINISHED
        ]
        assert len(written) == 1, audit_actions(audit_rows)  # noqa: F405
        after = written[0]["after"]
        assert after["account_status_written"] == disconnects.CUT_STATUS_CODE
        assert after["cut_bill"] is None
        assert after["days_not_billed"]["days"] == 24
        assert after["completed"]["code"] == "cut_completed_without_a_final_bill"


def test_tc2c_the_cut_itself_names_the_days_it_could_not_bill(
    marcus, brazos, monkeypatch
):
    """The HELD branch states them too, on the act that left them unbilled.

    ⚠ **THIS IS THE ONE PLACE THE FACT REACHES `audit_log` FROM `commit_cut`**,
    and `audit_log` is where a support person looks a week later. Without a case
    on it the line is a call site nothing exercises — built and not wired in the
    quietest way, because the payload would simply carry a `None` nobody reads.

    The status is still HELD here, so the account is still in the bill run: the
    days are stated as a FACT about the cut, not as a warning that they have
    been stranded. `finish_cut(without_bill=True)` is the act that strands them
    and it states them again when it does (tc2).
    """
    with tenant_ctx(brazos):
        _window(monkeypatch, {"start": "2026-08-01", "end": str(CUT_ON), "days": 24})
        account = _scheduled(marcus, brazos, monkeypatch)
        _answer_with(monkeypatch, _blocked())
        cut = disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)

        assert cut["cut_bill"]["billed"] is False
        assert cut["account_status_written"] is None
        stated = cut["days_not_billed"]
        assert stated is not None, "the cut said nothing about the days it could not bill"
        assert (stated["from"], stated["to"], stated["days"]) == (
            "2026-08-01",
            str(CUT_ON),
            24,
        )


def test_tc3_it_is_still_not_a_close_out(marcus, brazos, monkeypatch):
    """`DSC-02.4`, untouched by the reversal: no close, no deposit, no write-off.

    The ruling moved ONE refusal. A lane reading *"the status is written even
    when nothing is billed"* as *"the cut may now finish the tenancy"* would be
    converting a disconnect into a move-out, which BR-CUS-091 forbids by name.
    """
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        _refuse_to_bill(monkeypatch)
        _window(monkeypatch, None)
        answer = disconnects.finish_cut(
            marcus, account["id"], as_of=FINISH_ON, without_bill=True
        )

        row = _row(account["id"])
        assert row.closed_at is None
        assert answer["settlement"]["written_off"] is None
        assert answer["settlement"]["account_closed"] is False
        assert answer["settlement"]["deposit_settled"] is False
        # And the cut itself is not re-recorded — a cut happens once.
        case = disconnects.open_case_for(account["id"])
        assert (case.state, case.cut_on) == (disconnects.STATE_CUT, CUT_ON)


def test_tc4_the_ordinary_path_still_refuses_and_names_the_way_out(
    marcus, brazos, monkeypatch
):
    """⛔ **THE HOLD STAYS AVAILABLE — IT STOPS BEING COMPULSORY.**

    A clerk who asked for the bill and was refused still gets nothing written
    and the engine's own sentence. What changed is that the refusal now NAMES
    the other door, so a screen reading it can offer one.
    """
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        before = _status_of(account["id"])
        _answer_with(monkeypatch, _blocked())
        answer = disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON)

        assert answer["finished"] is False
        assert answer["account_status_written"] is None
        assert _status_of(account["id"]) == before
        held = answer["account_status_held"]
        assert held["code"] == "cut_bill_still_blocked_status_not_written"
        assert "without a bill" in held["detail"] or "no bill at all" in held["detail"]
        assert "2026-09-21" in held["br_ref"]
        # The ENGINE's own words still come back — that is what a clerk fixes.
        # AMENDED 2026-10-01 (billing red triage): the refusal now reaches the
        # clerk as its CLERK sentence (`2b5c1b4c6`, 2026-09-24, DEF-CUS-6550:
        # "the move-out's draft-bill refusal is 10 words, not 63"), which
        # begins the instruction with a capital. Same instruction, B14 rule 33.
        assert answer["cut_bill"]["detail"] == (
            "This connection's size is not recorded. Record the connection's size."
        )
        # …and the refused attempt states the days too, because that is what a
        # clerk is weighing when they decide to complete without a bill.
        assert answer["days_not_billed"] is not None


def test_tc5_a_completed_cut_cannot_be_completed_twice(
    marcus, brazos, monkeypatch
):
    """Idempotent BY REFUSAL, on the new path as on the old one."""
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        _refuse_to_bill(monkeypatch)
        _window(monkeypatch, None)
        disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON, without_bill=True)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.finish_cut(
                marcus, account["id"], as_of=FINISH_ON, without_bill=True
            )
        assert refusal.value.code == "cut_already_finished"


# ════════════════════════════════════════════════════════════════════════════
# RULING 1 · tc6 — THE DAYS STAY VISIBLE ON THE RECORD, AND CLOSE THEMSELVES
# ════════════════════════════════════════════════════════════════════════════
def test_tc6_the_record_states_the_days_after_the_cut_is_completed(
    marcus, brazos, monkeypatch
):
    """⚠ **THE ONE CASE THIS ROW EXISTS FOR IS THE FINISHED ONE.**

    `cut_unfinished` goes null the moment the status is written — correctly,
    the cut IS finished — so if the days rode only on that block they would
    disappear at exactly the moment nothing else was going to bill them.
    """
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        _refuse_to_bill(monkeypatch)
        _window(monkeypatch, {"start": "2026-08-01", "end": str(CUT_ON), "days": 24})
        disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON, without_bill=True)

        case = disconnects.open_case_for(account["id"])
        record = disconnect_record.record_detail(case.case_no, as_of=FINISH_ON)
        panel = record["what_a_cut_would_do"]
        assert panel["cut_unfinished"] is None, "the cut IS finished"
        assert panel["days_not_billed"]["days"] == 24
        assert "finish_cut" not in record["actions"]["available"]


def test_tc6b_the_statement_closes_itself_once_a_bill_covers_the_cut(
    marcus, brazos, monkeypatch
):
    """**DERIVED, NEVER STORED** — and this is what that buys.

    A column written at completion would say *unbilled* for ever. Billing is
    asked the same question on every read, so the day the single-bill workflow
    raises the bill the row goes quiet on its own and nobody clears a flag.
    That is hard-won law 1's shape avoided rather than described.
    """
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        _refuse_to_bill(monkeypatch)
        _window(monkeypatch, {"start": "2026-08-01", "end": str(CUT_ON), "days": 24})
        disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON, without_bill=True)
        case = disconnects.open_case_for(account["id"])
        assert disconnects.unbilled_days_at_cut(case)["days"] == 24

        # …now billing's single-bill workflow raises it. Nothing else changes.
        _window(monkeypatch, None)
        assert disconnects.unbilled_days_at_cut(case) is None
        record = disconnect_record.record_detail(case.case_no, as_of=FINISH_ON)
        assert record["what_a_cut_would_do"]["days_not_billed"] is None


def test_tc7_an_unanswerable_window_is_reported_and_never_read_as_silence(
    marcus, brazos, monkeypatch
):
    """⛔ **DEF-035's SHAPE, REFUSED IN ADVANCE.**

    A seam that resolves to nothing answers `None`, which is byte-identical to
    *nothing is unbilled*. Only one of those is good news, and a screen drawing
    silence over the other would be telling a clerk the days are covered
    because nobody could be asked.
    """
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        case = disconnects.open_case_for(account["id"])
        monkeypatch.setattr(
            disconnects.seams, "unbilled_service_window", lambda *_a, **_k: None
        )
        monkeypatch.setattr(disconnects.seams, "billing_selectors_answer", lambda: False)
        stated = disconnects.unbilled_days_at_cut(case)
        assert stated is not None
        assert stated["code"] == "unbilled_days_not_readable"
        assert "from" not in stated, "an absence of an answer has no dates to print"


# ════════════════════════════════════════════════════════════════════════════
# RULING 2 · THE WINDOW OPENS THE DAY AFTER THE LAST BILL — AND ARREARS ARE
#            PREVIOUS BALANCE, NEVER BILLABLE DAYS
# ════════════════════════════════════════════════════════════════════════════
def _a_bill(brazos, account_id, *, invoice_no, bill_type, start, end, total=D("40.0000")):
    from apps.billing import models as billing_models

    return billing_models.Invoice.objects.create(
        tenant_id=brazos.id,
        account_id=account_id,
        invoice_no=invoice_no,
        bill_type=bill_type,
        status="issued",
        period_start=start,
        period_end=end,
        service_date=end,
        currency="USD",
        total=total,
    )


def test_tc8_the_last_bill_beats_the_cutover_and_the_cutover_beats_the_move_in(
    brazos, marcus
):
    """**PO ruling 2026-09-21 ruling 2 — PRECEDENCE, AND NOT A MAXIMUM.**

    Verbatim: *"you create the bill from last bill date."* `DEF-BIL-6093`
    narrowed rather than kept: the cutover is the FALLBACK for the account that
    has no bill of ours, not the preferred answer.

    ⚠ **THE DOCSTRING CLAIMED A MAXIMUM UNTIL TODAY** — *"the LATEST of the two
    answers wins overall"* — and the code has always returned on the first
    answer it got. That is hard-won law 1 on a money path, and this case is
    what stops the sentence and the code drifting apart again.
    """
    with tenant_ctx(brazos):
        account = _plain_account(marcus, brazos, label="Unit R2a")
        row = customers_models.Account.objects.get(id=account["id"])
        row.opened_at = date(2021, 3, 15)
        row.save(update_fields=["opened_at", "updated_at"])
        # 3 · with nothing else, the move-in date answers.
        assert billing_cut_bill.first_unbilled_day(row.id) == date(2021, 3, 15)

        # 2 · a migration covers everything up to its own `as_of`.
        customers_models.AccountOpeningBucket.objects.create(
            tenant_id=brazos.id,
            account_id=row.id,
            as_of=date(2026, 6, 30),
            bucket=customers_models.AccountOpeningBucket.BUCKET_90_PLUS,
            amount=D("8240.0000"),
            currency="USD",
        )
        assert billing_cut_bill.first_unbilled_day(row.id) == date(2026, 7, 1)

        # 1 · and OUR own last bill beats it, which is the PO's own sentence.
        _a_bill(
            brazos,
            row.id,
            invoice_no="BL-TEST-R2A-1",
            bill_type="cycle",
            start=date(2026, 7, 1),
            end=date(2026, 8, 31),
        )
        assert billing_cut_bill.first_unbilled_day(row.id) == date(2026, 9, 1)


def test_tc9_the_po_worked_case_february_to_the_first_of_march(brazos, marcus):
    """**THE PO'S OWN SHAPE, IN THEIR OWN FIGURES.**

    *"if last bill was generated in feb and data is 28 feb you start the bill
    from 1 mar"*. Written as its own case rather than folded into `tc8`,
    because this is the sentence a reader will come looking for.
    """
    with tenant_ctx(brazos):
        account = _plain_account(marcus, brazos, label="Unit R2b")
        row = customers_models.Account.objects.get(id=account["id"])
        _a_bill(
            brazos,
            row.id,
            invoice_no="BL-TEST-R2B-1",
            bill_type="cycle",
            start=date(2026, 2, 1),
            end=date(2026, 2, 28),
        )
        assert billing_cut_bill.first_unbilled_day(row.id) == date(2026, 3, 1)


def test_tc10_on_a_migrated_account_the_arrears_are_previous_balance(brazos, dana):  # noqa: F405
    """**ARREARS ARE NEVER RE-BILLED — the half that closes the double-bill worry.**

    PO, verbatim: *"for arreras - it is previous balance - bill will anyway
    calculate previous balance and mention it on bill; hence we have accounted
    or all oustanding amount."*

    Two things are proved together, because either alone is half an answer:

      * the WINDOW covers no day anybody has billed — the account arrived at
        cutover **2026-08-31** and the first day this product owns is
        **2026-09-01**, not the move-in date of **2021-03-15**;
      * the arrears appear as **PREVIOUS BALANCE** on the bill itself —
        ❄️ GT-16's **267.30**, stamped by `issue._stamp_balance_forward` under
        BR-BIL-160 and PRINTED on the rendered page.

    ⚠ **THE PRINTED HALF IS NOT DECORATION.** A payload key that the renderer
    could not read would pass an assertion on the payload and still leave the
    customer holding a dash, which is DEF-116 exactly.
    """
    from apps.billing import documents, issue
    from tests.test_oq530_opening_balance_on_the_first_bill import (
        GT16_CUTOVER,
        GT16_OPENING,
        _block,
        _foots,
        _issue_one,
        a_migrated_account,
    )
    from tests.test_us_bil_005_issue import electric_gl_accounts
    from tests.test_us_bil_005_release_issue_api import (
        CURRENT_CHARGES,
        a_bill_of,
        an_actor_user,
    )
    from tests.test_w3_billing_models import a_run

    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = a_run(brazos, key="2026-09|po20260921-tc10")
        account = a_migrated_account(brazos, dana, account_no="A-12103")
        account.opened_at = date(2021, 3, 15)
        account.save(update_fields=["opened_at", "updated_at"])

        # THE WINDOW — the day after the cutover, never the day service began.
        assert billing_cut_bill.first_unbilled_day(account.pk) == date(2026, 9, 1)
        assert GT16_CUTOVER == date(2026, 8, 31)

        draft = a_bill_of(
            brazos, account, run, invoice_no="BL-2609-000901", total=CURRENT_CHARGES
        )
        bill = _issue_one(brazos, an_actor_user(brazos), run, draft)
        page = documents.render_invoice(bill)

    block = _block(bill)
    # THE ARREARS — previous balance, not billable days.
    assert D(block["previous_balance"]) == GT16_OPENING == D("267.30")
    assert D(block["opening_balance"]) == GT16_OPENING
    assert D(block["current_charges"]) == CURRENT_CHARGES
    assert _foots(block), block
    assert block["basis"] == issue.BALANCE_FORWARD_BASIS
    printed = {field.label: field.value for field in page.summary}
    assert printed["Previous balance"] == "267.30 USD"


# ════════════════════════════════════════════════════════════════════════════
# THE THIRD SIGN-OFF · RATIFIED 2026-09-21 — A FEE IS A CHARGE FOR AN EVENT,
#                       NOT FOR A PERIOD OF SERVICE
# ════════════════════════════════════════════════════════════════════════════
#: **THE RATIFIED SENTENCE, VERBATIM**, so a reader of this file never has to
#: go and look it up: *"A fee is a charge for an event, not for a period of
#: service - this is correct"* (PO, 2026-09-21, choosing option (a) and quoting
#: the reasoning back). It RATIFIES what `DEF-CUS-6086` already built; nothing
#: about the behaviour changed on the day it was signed.
RATIFIED_SENTENCE = (
    "A fee is a charge for an event, not for a period of service - this is correct"
)

#: **THE WORKED CASE THE PO WAS SHOWN, AND IT IS WHAT THE SIGNATURE COVERS.**
#: On `A-11340` the $75.00 reconnection fee landed dated the day of the cut, so
#: every later attempt to finish that cut answered *"an issued bill already
#: covers this account through 2026-09-20"* with `billed=true` — which would
#: have written **Disconnected across 2021-03-15 → 2026-09-20 on the strength of
#: $75.00**. The PO was shown that span and that figure.
A11340_FEE = D("75.0000")
A11340_OPENED = date(2021, 3, 15)
A11340_CUT = date(2026, 9, 20)


def test_the_ratified_sentence__an_event_charge_never_answers_a_period_question(
    brazos, marcus
):
    """**CLAUDE.md §"What counts as that sign-off", part 2: a test asserts the
    ratified figure so drift goes RED.**

    The behaviour had tests. What it did not have was a test of **the SENTENCE
    the PO signed** — *a fee is a charge for an EVENT, not for a period of
    service* — so a lane could put `fee` back into the period question, watch
    `DEF-CUS-6086`'s own cases still pass on whatever they happened to assert,
    and no check would name the ruling. This one does.

    ⛔ **THE SCOPE OF THE SIGNATURE, STATED SO IT IS NOT STRETCHED.** It covers
    the reconnection fee and the *has this been billed* test it was wrongly
    satisfying. It does **not** reclassify every other charge in the product: a
    `penalty` bill is priced per SUB-PERIOD against the tariff version in force
    then (BR-BIL-018/019), so its window is a real span of days that really were
    billed, and it stays OUT of the event class. A lane finding the same shape
    elsewhere raises it; it does not assume this ruling already covered it.
    """
    from apps.billing import selectors as billing_selectors

    # The classification the sentence ratifies, in the one place the product
    # states it. `penalty` is NOT in it, deliberately — see the docstring.
    assert billing_selectors.NON_SERVICE_BILL_TYPES == ("fee",)

    with tenant_ctx(brazos):
        account = _plain_account(marcus, brazos, label="Unit FEE-RATIFIED")
        row = customers_models.Account.objects.get(id=account["id"])
        row.opened_at = A11340_OPENED
        row.save(update_fields=["opened_at", "updated_at"])

        # THE EVENT: a $75.00 reconnection fee, dated the day of the cut, which
        # is what `fee_bill` writes — `period_start = period_end = the date`,
        # because a row needs a date and not because a day was priced.
        _a_bill(
            brazos,
            row.id,
            invoice_no="BL-TEST-RATIFIED-FEE",
            bill_type="fee",
            start=A11340_CUT,
            end=A11340_CUT,
            total=A11340_FEE,
        )

        # THE RATIFIED SENTENCE: the event charge answers the DOCUMENT question
        # and never the PERIOD one.
        assert (
            billing_selectors.last_issued_invoice_period_end(row.id) == A11340_CUT
        ), "a fee IS an issued document — that half was always true"
        assert (
            billing_selectors.last_issued_service_period_end(row.id) is None
        ), RATIFIED_SENTENCE

        # AND THE FIGURE THE PO WAS SHOWN: unmoved by the fee, the window still
        # opens on the day service began — 2021-03-15, not the day after the
        # cut — so nothing writes `Disconnected` across five and a half years on
        # the strength of $75.00.
        assert billing_cut_bill.first_unbilled_day(row.id) == A11340_OPENED
        window = billing_selectors.unbilled_service_window(row.id, through=A11340_CUT)
        assert window is not None, RATIFIED_SENTENCE
        assert window["start"] == str(A11340_OPENED)
        assert window["days"] == (A11340_CUT - A11340_OPENED).days + 1 == 2016

        # THE NEGATIVE HALF, or the fix above could be `return None`: a bill
        # that really did price a period still moves the answer.
        _a_bill(
            brazos,
            row.id,
            invoice_no="BL-TEST-RATIFIED-CYCLE",
            bill_type="cycle",
            start=date(2026, 8, 1),
            end=date(2026, 8, 31),
        )
        assert billing_selectors.last_issued_service_period_end(row.id) == date(
            2026, 8, 31
        )
        assert billing_cut_bill.first_unbilled_day(row.id) == date(2026, 9, 1)
