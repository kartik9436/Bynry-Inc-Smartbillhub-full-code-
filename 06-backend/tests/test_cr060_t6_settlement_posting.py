# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 C1 / task T6 — "Post supplier costs on settlement", the
#           change request's own "core change". PO ruling 2026-09-02
#           (12-governance/02-decision-log.md, top row).
# Story:    US-LED-018 (capture) · US-LED-019 (the register)
#           Screens: S73 (R8 "Costs")
#           ⚠ THE POSTING-CONTRACT STORY IS DELIBERATELY NOT NAMED ANYWHERE IN
#           THIS HEADER, even though this file exercises that contract end to
#           end. G23 collects EVERY US-ID in the trace header — not only the
#           Story line — and attributes the trailer's D/E marks to all of them,
#           so naming it here with `D✔` would mark the source-event posting
#           contracts as API-reached when they are not, and `surface_debt.txt`
#           counts exactly that. Caught by G23 going PASS → FAIL on it,
#           2026-09-02; the id is written out in the module docstring below,
#           which the gate does not read.
# Rules:    BR-LED-028 (AMENDED 2026-09-02 — full accounts payable STILL
#           declined; a date recording that payment happened elsewhere is not
#           accounts payable) · BR-LED-034 (editable while the period is open) ·
#           BR-LED-035 (void, never delete) · BR-LED-025 (the ledger refuses a
#           posting carrying more than two decimals and never rounds) ·
#           BR-TEN-038 / BR-LED-006 (a settlement dated into a closed period
#           books forward) · BR-TEN-043 (nothing in a money path reads a clock)
#           · CLAUDE.md hard rule 5 (only the posting service writes journal
#           lines) · rule 6 (idempotency) · rule 7 (every money action audits)
#           · the signed DR/CR source-event contract table (depended on here,
#             never extended — see the module docstring)
# Golden:   LE-1 — the signed July trial balance **598.69 = 598.69** (GT-51).
#           LE-11 — nine supplier invoices, **$51,902.50 USD**. Settling all
#           nine takes the books to **52,501.19 = 52,501.19**.
# ───────────────────────────────────────────────────────
"""C1's four proofs, and the six refusals that come with them.

C1's proof list, verbatim: *"settlement posts DR cost / CR cash · an unset
`paid_on` posts nothing · a second settlement is a replay no-op · settlement
into a closed period books forward"*. Each is one case below and each is named
for the sentence it proves.

════════════════════════════════════════════════════════════════════════════
WHAT RUNS WHERE, AND WHY THE LAW-14 CASES ARE MARKED
════════════════════════════════════════════════════════════════════════════
Every case here runs on the default in-memory SQLite suite. **Three of them are
transaction-sensitive and were ALSO run against a real PostgreSQL 16.13**, which
is CLAUDE.md hard-won law 14 and C1's own instruction (*"prove on PostgreSQL,
not the SQLite suite"*): the settlement that posts (an `atomic()` wrapping a
column write and a posting), the replay no-op (which leans on
`uq_journal_entries_posting_key`, a constraint SQLite's test database does have
but whose IntegrityError path differs), and the ledger refusal, which unwinds a
write that has already happened inside the same transaction. SQLite has no
aborted-transaction state, so a green run here is not by itself the proof.

Run them the way the law names:

    DATABASE_URL=postgres://... DJANGO_SETTINGS_MODULE=config.settings.local \\
    JOBS_EAGER=false pytest tests/test_cr060_t6_settlement_posting.py --reuse-db

════════════════════════════════════════════════════════════════════════════
THE FROZEN FIGURE, AND WHY THIS FILE CAN ASSERT IT WITHOUT MOVING IT
════════════════════════════════════════════════════════════════════════════
LE-1's trial balance is finance-signed at **598.69 = 598.69** and is ❄️ frozen.
Settling July's **$51,902.50** of captured costs takes it to **52,501.19 =
52,501.19**, and that movement takes the HUMAN-GUIDE §6 re-sign route — never an
inline edit. **Nothing in B4 or B5 is touched by this file.** What it does is
build the settled month IN A TEST DATABASE and assert the arithmetic, so that
the day the re-sign happens the figure it ratifies is one this suite already
computes, and so that a drift in either signed input goes red here first.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import chart, close, cost_capture, posting, reporting, selectors
from apps.ledger import models as ledger_models

from tests import ledger_le_fixtures as le
from tests.cost_of_service_fixtures import (
    JULY_CLOSED_AT,
    JULY_END,
    JULY_START,
    LE11_REGISTER_TOTAL,
    capture_le11_month,
    enable_le11_services,
    with_monthly_fiscal_year,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    lonestar,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: BR-TEN-043 — the caller names the moment. One constant, so a retried
#: settlement in any case below stamps the same instant rather than two.
SETTLED_AT = datetime(2026, 8, 4, 10, 30, tzinfo=dt_timezone.utc)

#: The day the utility's bank moved the money for CI-1. Inside July, so the
#: ordinary case books on the day the clerk typed.
PAID_IN_JULY = date(2026, 7, 28)

#: CI-1, LE-11's first bulk-water invoice: RS-2607-0141, $1,240.00, GL 5110.
CI1 = "RS-2607-0141"
CI1_AMOUNT = Decimal("1240.00")

#: LE-1's signed footing (GT-51). Transcribed, never computed, so a drift in the
#: signed source goes red here rather than being absorbed.
LE1_FOOTING = le.LE1_FOOTING  # Decimal("598.69")

#: ⚠ **THE FIGURE CR-060 PROJECTS, AND IT IS 150.00 HIGH. MEASURED 2026-09-02.**
#: C1, the decision-log row of 2026-09-02 and this lane's own first draft all say
#: that settling July's $51,902.50 takes LE-1's **598.69 = 598.69** to
#: **52,501.19 = 52,501.19**. That is 598.69 + 51,902.50, and it is the answer
#: only if no account already on the books flips sides. One does.
SETTLED_FOOTING_AS_PROJECTED = Decimal("52501.19")

#: **WHAT THE PRODUCT ACTUALLY COMPUTES: 52,351.19 = 52,351.19.**
#:
#: A trial balance carries each account's NET balance on ONE side — that is what
#: a trial balance IS, and `reporting.trial_balance` argues it at length against
#: LE-1's own table. LE-1 leaves **150.00 of DEBIT in 1000 Cash** (the customer
#: deposit; the 292.87 payment sits in 1010 Undeposited funds under the PO's
#: OQ-143 ruling). Paying suppliers CREDITS cash 51,902.50, so 1000 nets to
#: **−51,752.50** and moves from the debit column to the credit column
#: altogether. The 150.00 that used to foot on the debit side is gone from it.
#:
#: So the footing rises by **51,902.50 − 150.00 = 51,752.50**, not by 51,902.50:
#:     598.69 − 150.00 + 51,902.50 = **52,351.19**, and the credit side
#:     598.69 + 51,752.50 = **52,351.19**. Balanced, as it must be.
#:
#: **NEITHER NUMBER IS SIGNED AND NOTHING FROZEN MOVED.** 598.69 is the signed
#: figure (LE-1 / GT-51) and it is untouched; 52,501.19 was a PROJECTION written
#: into a change request, never a finance signature. The correction is recorded
#: in `12-governance/02-decision-log.md` (2026-09-02) so that the HUMAN-GUIDE §6
#: re-sign, when it is owed, is put to a person with the figure the product
#: computes rather than the one somebody added up.
SETTLED_FOOTING = Decimal("52351.19")

#: The 150.00 of cash LE-1 leaves on the debit side — the whole of the
#: difference, named so the assertion below reads as arithmetic and not as a
#: fudge factor.
LE1_CASH_ON_THE_DEBIT_SIDE = le.LE1_CASH_REALISED  # Decimal("150.00")


def brazos_ready(tenant, actor=None):
    """The LE-11 preconditions — a fiscal calendar and the five services sold.

    Copied in shape from `tests/test_us_led_018_capture.py` for the reason that
    file states: both are SYSTEM ADMIN actions while a capture is a clerk's, so
    the setup mints its own admin rather than borrowing the capturing actor.
    """
    admin = actor if getattr(actor, "role", None) == "system_admin" else staff_actor(
        tenant, "system_admin", f"setup-{tenant.subdomain}@brazosbendutilities.test"
    )
    with_monthly_fiscal_year(admin)
    enable_le11_services(admin)
    return admin


def _entry_for(invoice_id):
    return cost_capture.settlement_entry(invoice_id)


def _sides(entry):
    """{(code, side): amount} for one posted entry — the shape an assertion about
    DR/CR reads without caring what order the lines were written in."""
    out = {}
    for line in entry.lines.select_related("ledger_account"):
        out[(line.ledger_account.code, line.side)] = line.amount
    return out


# ═══════════════════════════════════════════════════════════════════════════
# C1 PROOF 1 — "settlement posts DR cost / CR cash"
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6__recording_a_settlement_posts_dr_cost_cr_cash(brazos, marcus, audit_rows):
    """**CI-1 settled on 2026-07-28 posts DR 5110 purchased water 1,240.00 /
    CR 1000 cash 1,240.00** — one balanced entry, and no payable anywhere.

    PO ruling 2026-09-02, verbatim: *"why cant to add the check that whether this
    is paid or unpaid and allow clark to udpaet it - that way we can reconcicle -
    again system of record we dont have to match we can take input from Clark and
    close it"*.

    ⚠ **THE CREDIT IS CASH AND THAT IS THE WHOLE REASON THIS IS LAWFUL.** The PO
    refused posting on RECEIPT in 2026-08-16's sitting because it credits an
    accounts payable BR-LED-028 forbids this product from ever draining —
    $37,200.00 a year standing for invoices settled by cheque. This entry creates
    no payable at all, which is asserted below rather than described.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        assert not ledger_models.JournalEntry.objects.filter(tenant=brazos).exists()
        audit_rows.clear()

        settled = cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )

        entry = _entry_for(captured[CI1]["id"])
        assert entry is not None
        sides = _sides(entry)
        cash_code = selectors.gl_account_for_designation(chart.CASH).code

    # DR the cost account the invoice was classified to, CR cash. Both 1,240.00.
    assert sides[("5110", ledger_models.SIDE_DEBIT)] == CI1_AMOUNT
    assert sides[(cash_code, ledger_models.SIDE_CREDIT)] == CI1_AMOUNT
    assert len(sides) == 2

    # Balanced to the cent, which is what "balanced" means (hard rule 5).
    assert sum(a for (_, s), a in sides.items() if s == ledger_models.SIDE_DEBIT) == sum(
        a for (_, s), a in sides.items() if s == ledger_models.SIDE_CREDIT
    )

    # NO PAYABLE IS CREATED — the objection of 2026-08-16, asserted.
    assert not any(code.startswith("25") for code, _ in sides)

    # It went through the ONE posting service (hard rule 5): the entry carries
    # the replay key `posting.posting_key` composes and nothing else could have
    # written it, because ledger/0004 refuses an insert unless posting.py opens
    # the write window.
    assert entry.posting_key == cost_capture.settlement_posting_key(captured[CI1]["id"])
    assert entry.posting_key.split("|") == ["supplier_invoice", str(captured[CI1]["id"]), "settled"]
    assert entry.status == ledger_models.JE_POSTED
    assert entry.entry_date == PAID_IN_JULY
    assert entry.posted_at == SETTLED_AT

    # Hard rule 7 — TWO money actions, and they answer different questions.
    settled_rows = [r for r in audit_rows if r["action"] == "supplier_invoice.settled"]
    posted_rows = [r for r in audit_rows if r["action"] == "journal.posted"]
    assert len(settled_rows) == 1 and len(posted_rows) == 1
    assert settled_rows[0]["actor_user_id"] == marcus.id
    assert settled_rows[0]["before"]["paid_on"] is None
    assert settled_rows[0]["after"]["paid_on"] == PAID_IN_JULY.isoformat()
    assert settled_rows[0]["after"]["settlement"]["posted"] is True

    # And the row SAYS which of R8's two states it is in.
    assert settled["paid_on"] == PAID_IN_JULY
    assert settled["settlement"]["in_the_books"] is True
    assert settled["settlement"]["replayed"] is False


# ═══════════════════════════════════════════════════════════════════════════
# C1 PROOF 2 — "an unset paid_on posts nothing"
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6__an_unset_paid_on_posts_nothing(brazos, marcus):
    """**Nine captures, $51,902.50, and not one journal row.**

    This is the case that makes the column shippable on a live database: with no
    `paid_on` set anywhere the settlement path is unreachable, so LE-1's signed
    **598.69 = 598.69** does not move by a cent when the migration applies. The
    HUMAN-GUIDE §6 re-sign is owed at the FIRST settlement, not at landing.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)

        rows = ledger_models.SupplierInvoice.objects.filter(tenant=brazos)
        assert rows.count() == 9
        assert all(row.paid_on is None for row in rows)
        assert sum(row.amount for row in rows) == LE11_REGISTER_TOTAL

        # The posting function itself is the first line of the design: unset in,
        # None out, no request built and no write window opened.
        for row in rows:
            assert (
                posting_result := cost_capture.post_settlement_to_journal(
                    row, posted_at=SETTLED_AT
                )
            ) is None, posting_result

        assert not ledger_models.JournalEntry.objects.filter(tenant=brazos).exists()
        assert not ledger_models.JournalLine.objects.filter(tenant=brazos).exists()
        assert cost_capture.settlement_entry(captured[CI1]["id"]) is None

        # And the register says so in R8's own vocabulary rather than leaving a
        # clerk to infer it.
        listed = cost_capture.register()
    assert all(row["paid_on"] is None for row in listed["rows"])


# ═══════════════════════════════════════════════════════════════════════════
# C1 PROOF 3 — "a second settlement is a replay no-op"
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6__a_second_settlement_is_a_replay_no_op(brazos, marcus):
    """**A double-clicked Save posts once.** Hard rule 6, by construction.

    The posting key is `supplier_invoice|<id>|settled` and `posting.post()`
    answers a known key with `created=False` rather than an exception — a replay
    is the correct outcome of a resumed act, not an error anybody should catch
    (US-LED-001 TC-6). So the second call is idempotent all the way down: one
    entry, two lines, and the same 1,240.00 in the books.

    ⚠ Law 14: this leans on `uq_journal_entries_posting_key` and on the
    IntegrityError path behind it, so it is one of the three cases in this file
    re-run against real PostgreSQL.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        invoice_id = captured[CI1]["id"]

        first = cost_capture.record_settlement(
            marcus, invoice_id, paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )
        second = cost_capture.record_settlement(
            marcus, invoice_id, paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )

        entries = ledger_models.JournalEntry.objects.filter(
            tenant=brazos, posting_key=cost_capture.settlement_posting_key(invoice_id)
        )
        assert entries.count() == 1
        assert ledger_models.JournalLine.objects.filter(tenant=brazos).count() == 2

    assert first["settlement"]["replayed"] is False
    assert second["settlement"]["replayed"] is True
    # The SAME entry both times, so a screen linking to the books cannot end up
    # pointing at two different rows for one act.
    assert first["settlement"]["journal_entry_id"] == second["settlement"]["journal_entry_id"]


# ═══════════════════════════════════════════════════════════════════════════
# C1 PROOF 4 — "settlement into a closed period books forward"
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6__a_settlement_dated_into_a_closed_july_books_into_august(
    brazos, dana, marcus, audit_rows
):
    """**July closed on Aug 5; the July water bill was paid on Jul 28; the entry
    lands on Aug 1** — BR-TEN-038, LE-9's rule, BORROWED and never re-written.

    ⚠ **AND THE PURCHASE DOES NOT MOVE.** Only the settlement ENTRY's book date
    is resolved against the calendar; the invoice keeps `period_start` /
    `period_end` of July, so July's bought-versus-billed is untouched. Moving the
    purchase would take its amount out of one month's reconciliation and put it
    into another's, which is exactly the distinction OQ-227 settled for a
    re-dating: *a correction is a correction; a move is a move.*
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, dana)
        captured = capture_le11_month(marcus)
        invoice_id = captured[CI1]["id"]
        close.close_period(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            closed_at=JULY_CLOSED_AT,
            reason="the deposit register is still being matched",
        )
        audit_rows.clear()

        cost_capture.record_settlement(
            marcus, invoice_id, paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )

        entry = _entry_for(invoice_id)
        row = ledger_models.SupplierInvoice.objects.get(pk=invoice_id)

    # The entry booked FORWARD into the first open period.
    assert entry.entry_date == date(2026, 8, 1)
    # The purchase stayed where it was bought, and the date the clerk typed is
    # still the date the clerk typed.
    assert row.period_start == JULY_START and row.period_end == JULY_END
    assert row.paid_on == PAID_IN_JULY
    # And the trail says WHY the entry is in August (LE-9's own note).
    posted_rows = [r for r in audit_rows if r["action"] == "journal.posted"]
    assert len(posted_rows) == 1
    note = posted_rows[0]["after"]["period_auto_forwarded"]
    assert note["code"] == "period_closed_auto_forwarded"
    assert note["detail"] == "period closed; auto-forwarded"
    assert note["requested_date"] == PAID_IN_JULY.isoformat()

    # NO correction reason was asked for, and that is deliberate: paying July's
    # bill in August is the ORDINARY case, not an after-close correction of a
    # captured fact.
    assert not any(
        "after_close_correction" in (r.get("after") or {}) for r in audit_rows
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE FROZEN FIGURE — 598.69 = 598.69 becomes 52,501.19 = 52,501.19
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6__settling_julys_nine_purchases_moves_the_signed_trial_balance(
    brazos, dana, marcus
):
    """**LE-1's signed 598.69 = 598.69 becomes 52,351.19 = 52,351.19** once all
    nine of July's captured purchases ($51,902.50) are settled.

    ⚠ **AND CR-060 PROJECTS 52,501.19, WHICH IS 150.00 HIGH. MEASURED HERE, ON
    2026-09-02, AND CORRECTED IN THE DECISION LOG RATHER THAN ABSORBED.** The
    projection is 598.69 + 51,902.50 and it assumes nothing already on the books
    changes sides. **One account does.** A trial balance carries each account's
    NET balance on ONE side; LE-1 leaves **150.00 of debit in 1000 Cash**, paying
    suppliers CREDITS cash 51,902.50, and 1000 therefore nets to −51,752.50 and
    leaves the debit column altogether. So the footing rises by 51,902.50 −
    150.00 = **51,752.50**, and 598.69 − 150.00 + 51,902.50 = **52,351.19**.

    **NOTHING SIGNED MOVED AND NOTHING FROZEN WAS EDITED.** 598.69 (LE-1 / GT-51)
    is the finance-signed figure and it is asserted untouched below; 52,501.19
    was a projection written into a change request, never a signature. The
    correction matters because the HUMAN-GUIDE §6 re-sign, when it is owed, must
    be put to a person with the figure the PRODUCT computes.

    ⚠ **THIS FILE ASSERTS THE FIGURE; IT DOES NOT RATIFY IT.** What this case does
    is make the arithmetic checkable BEFORE the re-sign is put to a human, and
    make a drift in either signed input go red: the 598.69 comes from
    `tests/ledger_le_fixtures.LE1_FOOTING` and the 51,902.50 from
    `tests/cost_of_service_fixtures.LE11_REGISTER_TOTAL`, both transcribed from
    their signed sources and neither computed here.

    ⚠ **AND THE RE-SIGN IS OWED AT THE FIRST SETTLEMENT, NOT AT LANDING**, which
    is what makes T6 shippable today: `test_cr060_t6__an_unset_paid_on_posts_
    nothing` above proves that on a database where nothing is settled the books
    do not move at all.
    """
    # Where the change request's number came from, stated so the correction is
    # legible rather than looking like a different fixture.
    assert LE1_FOOTING + LE11_REGISTER_TOTAL == SETTLED_FOOTING_AS_PROJECTED
    assert SETTLED_FOOTING_AS_PROJECTED - SETTLED_FOOTING == LE1_CASH_ON_THE_DEBIT_SIDE

    with tenant_ctx(brazos):
        world: dict = {}
        accounts = le.make_accounts(dana, brazos, world, service="electric")
        le.post_le1_month(brazos, accounts)
        before = reporting.trial_balance()
        assert before["balanced"] is True
        assert Decimal(str(before["total_debit"])) == LE1_FOOTING

        brazos_ready(brazos, dana)
        captured = capture_le11_month(marcus)
        for reference in captured:
            cost_capture.record_settlement(
                marcus, captured[reference]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
            )
        after = reporting.trial_balance()
        cash = [row for row in after["rows"] if row["code"] == "1000"]

    assert after["balanced"] is True
    assert Decimal(str(after["total_debit"])) == SETTLED_FOOTING
    assert Decimal(str(after["total_credit"])) == SETTLED_FOOTING
    # The footing rose by the cost LESS the cash debit it cancelled — which is
    # the whole of the difference from the projection, asserted rather than
    # asserted-around.
    assert (
        Decimal(str(after["total_debit"])) - LE1_FOOTING
        == LE11_REGISTER_TOTAL - LE1_CASH_ON_THE_DEBIT_SIDE
    )
    # And 1000 Cash is the account that moved sides: 150.00 debit before,
    # 51,752.50 credit after.
    assert len(cash) == 1
    assert Decimal(str(cash[0]["debit"])) == Decimal("0")
    assert Decimal(str(cash[0]["credit"])) == LE11_REGISTER_TOTAL - LE1_CASH_ON_THE_DEBIT_SIDE


# ═══════════════════════════════════════════════════════════════════════════
# CLEARING AND MOVING — C1: "clearing it is refused once posted"
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6__clearing_a_posted_paid_on_is_refused_by_name(brazos, marcus):
    """C1, verbatim: *"clearing it is refused once posted"*. The entry is in the
    books and hard rule 4 leaves no path to change it, so a cleared date would
    leave the register saying unpaid and the trial balance saying otherwise."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        invoice_id = captured[CI1]["id"]
        cost_capture.record_settlement(
            marcus, invoice_id, paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )

        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.record_settlement(
                marcus, invoice_id, paid_on=None, settled_at=SETTLED_AT
            )

        row = ledger_models.SupplierInvoice.objects.get(pk=invoice_id)

    assert "cannot be cleared" in str(refused.value)
    assert "hard rule 4" in str(refused.value)
    assert refused.value.br_ref == "BR-LED-034 · CR-060 C1"
    # And the refusal left the row exactly as it was — no half-cleared state.
    assert row.paid_on == PAID_IN_JULY


def test_cr060_t6__moving_a_posted_paid_on_is_refused_for_the_same_reason(brazos, marcus):
    """⚠ **THIS ONE IS A JUDGMENT, RECORDED RATHER THAN SMUGGLED IN.** C1 names
    only the CLEARING. Moving the date to a different day is the identical hazard
    — the entry is already posted at the old date, and the replay guard would
    make the new date a silent no-op, so the register would say one thing and the
    books another — and it is refused for the identical reason. The decision log
    row of 2026-09-02 carries it with its reasoning."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        invoice_id = captured[CI1]["id"]
        cost_capture.record_settlement(
            marcus, invoice_id, paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )

        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.record_settlement(
                marcus, invoice_id, paid_on=date(2026, 8, 3), settled_at=SETTLED_AT
            )

        entries = ledger_models.JournalEntry.objects.filter(tenant=brazos)
        row = ledger_models.SupplierInvoice.objects.get(pk=invoice_id)

    assert "moved to 2026-08-03" in str(refused.value)
    assert entries.count() == 1
    assert entries.first().entry_date == PAID_IN_JULY
    assert row.paid_on == PAID_IN_JULY


def test_cr060_t6__clearing_an_unposted_paid_on_is_lawful(brazos, marcus):
    """A clerk who ticked the wrong row un-ticks it. Nothing posted, nothing to
    unwind — and the audit trail still records both acts, because hard rule 7
    does not ask whether money actually moved."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        invoice_id = captured[CI1]["id"]

        # A settlement that the LEDGER never saw, because nothing calls the
        # posting path for an unset date — so this row is set and then cleared
        # while the books stay empty.
        cleared = cost_capture.record_settlement(
            marcus, invoice_id, paid_on=None, settled_at=SETTLED_AT
        )
        row = ledger_models.SupplierInvoice.objects.get(pk=invoice_id)

    assert cleared["paid_on"] is None
    assert cleared["settlement"]["in_the_books"] is False
    assert row.paid_on is None


# ═══════════════════════════════════════════════════════════════════════════
# THE DOORS — paid_on does not travel through the edit form
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6__paid_on_is_refused_by_name_in_the_edit_form(brazos, marcus):
    """Recording a settlement POSTS and needs the moment the clerk acted, so it
    is its own audited act exactly as a void is. A clerk (or a lane) reaching for
    `edit(paid_on=…)` is reaching for the right feature by the wrong door, and
    gets a sentence that names the right one."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)

        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.edit_supplier_invoice(
                marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY
            )

    assert "record_settlement" in str(refused.value)
    assert "paid_on" not in cost_capture.EDITABLE_FIELDS
    assert cost_capture.SETTLEMENT_FIELD == "paid_on"


# ═══════════════════════════════════════════════════════════════════════════
# OQ-1350 — MINTED, NOT ANSWERED (CLAUDE.md prime directive)
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6__correcting_a_settled_invoices_amount_is_an_open_question(brazos, marcus):
    """**OQ-1350.** Editing a settled invoice's amount from 1,240.00 to 1,242.40
    would leave the register saying one figure and the books another, with
    nothing red anywhere — and CR-060 T6d, the tie-out row that would surface it,
    is not built. Reverse-and-re-post, a delta entry and an outright refusal are
    all defensible and none is ruled, so this lane MINTS the question and stubs.

    ⚠ **AND THE STUB IS NARROW.** Only the four facts the entry COPIED are
    guarded. Everything else on a settled invoice is still corrected exactly as
    BR-LED-034 says, which is asserted here too — a blanket refusal would have
    REVERSED a signed rule, which is not a lane's to do.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        invoice_id = captured[CI1]["id"]
        cost_capture.record_settlement(
            marcus, invoice_id, paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )

        for field, value in (
            ("amount", Decimal("1242.40")),
            ("currency", "CAD"),
        ):
            with pytest.raises(NotImplementedError) as unruled:
                cost_capture.edit_supplier_invoice(marcus, invoice_id, **{field: value})
            assert "OQ-1350" in str(unruled.value)

        # The memo is NOT one of the four, so BR-LED-034 still applies in full.
        edited = cost_capture.edit_supplier_invoice(
            marcus, invoice_id, memo="cheque 10421, First National"
        )
        row = ledger_models.SupplierInvoice.objects.get(pk=invoice_id)

    assert edited["memo"] == "cheque 10421, First National"
    assert row.amount == CI1_AMOUNT
    assert cost_capture.SETTLEMENT_COPIES == (
        "amount",
        "currency",
        "ledger_account_id",
        "premises_id",
    )


def test_cr060_t6__voiding_a_settled_invoice_is_an_open_question(brazos, marcus):
    """**OQ-1350, the other door.** A void drops the row out of every aggregate
    from that moment — LE-13's July footer moves 51,902.50 → 51,747.50 — and a
    SETTLED row's cost is also in the trial balance, which a void does not touch.
    Unposting is a reversal, and whether a void should reverse is not ruled."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        invoice_id = captured[CI1]["id"]
        cost_capture.record_settlement(
            marcus, invoice_id, paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )

        with pytest.raises(NotImplementedError) as unruled:
            cost_capture.void_supplier_invoice(
                marcus, invoice_id, reason="duplicate of RS-2607-0175", voided_at=SETTLED_AT
            )

        row = ledger_models.SupplierInvoice.objects.get(pk=invoice_id)

    assert "OQ-1350" in str(unruled.value)
    assert row.status == ledger_models.SUPPLIER_INVOICE_CAPTURED


def test_cr060_t6__a_voided_invoice_cannot_be_settled(brazos, marcus):
    """A void records that the purchase was withdrawn, so paying it is not a
    thing that happened. BR-LED-035's own remedy applies: if it WAS paid, the
    void was the mistake and the correction is a fresh capture."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        invoice_id = captured[CI1]["id"]
        cost_capture.void_supplier_invoice(
            marcus, invoice_id, reason="duplicate of RS-2607-0175", voided_at=SETTLED_AT
        )

        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.record_settlement(
                marcus, invoice_id, paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
            )

        assert not ledger_models.JournalEntry.objects.filter(tenant=brazos).exists()

    assert refused.value.br_ref == "BR-LED-035"
    assert "cannot be settled" in str(refused.value)


# ═══════════════════════════════════════════════════════════════════════════
# THE LEDGER'S OWN REFUSALS, REACHING THE CLERK
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6__a_three_decimal_amount_is_unsettleable_and_was_flagged_at_capture(
    brazos, marcus
):
    """**BR-LED-025, and the warning was already on the row.**

    US-LED-018 §7 rules that a captured amount is *"stored exactly as keyed at
    six decimals and is never rounded by the ledger"*, and the capture flags it
    with `amount_carries_more_than_two_decimals`. `cost_capture.py` predicted in
    its own docstring that *"the day OQ-200 closes as reading (a), such a capture
    becomes unpostable"*. It became unpostable on 2026-09-02 by a different route
    and the prediction holds: the ledger refuses, naming the amount, and the
    clerk's remedy is to correct the capture.

    ⚠ Law 14: this is the third transaction-sensitive case — the `paid_on` write
    has already happened inside the transaction when the ledger refuses, and the
    whole thing must unwind. Re-run against real PostgreSQL.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = cost_capture.capture_supplier_invoice(
            marcus,
            invoice_date=date(2026, 7, 6),
            service="water",
            supplier_name="City of Rosenberg — Bulk Water Supply",
            amount=Decimal("1240.005"),
            currency="USD",
            reference="RS-2607-0999",
        )
        assert cost_capture.AMOUNT_PRECISION_WARNING in captured["problems"]

        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.record_settlement(
                marcus, captured["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
            )

        row = ledger_models.SupplierInvoice.objects.get(pk=captured["id"])
        assert not ledger_models.JournalEntry.objects.filter(tenant=brazos).exists()

    assert refused.value.br_ref == "BR-LED-025"
    assert "MORE THAN TWO DECIMAL PLACES" in str(refused.value)
    assert "still unpaid" in str(refused.value)
    # THE UNWIND IS THE POINT: nothing half-happened.
    assert row.paid_on is None


def test_cr060_t6__a_settlement_needs_the_moment_it_was_recorded(brazos, marcus):
    """BR-TEN-043 / gate G6 — nothing in a money path reads a clock, so a
    retried settlement stamps ONE moment rather than two."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.record_settlement(
                marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY, settled_at="2026-08-04"
            )
    assert "BR-TEN-043" in str(refused.value)


def test_cr060_t6__paid_on_must_be_a_date_and_not_a_timestamp(brazos, marcus):
    """The name is load-bearing. `paid_at` is one of the four names BR-LED-028
    refuses; this is the DAY the bank moved the money, which is the granularity a
    bank statement has and the granularity a book date is."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.record_settlement(
                marcus, captured[CI1]["id"], paid_on=SETTLED_AT, settled_at=SETTLED_AT
            )
    assert "must be a DATE" in str(refused.value)


# ═══════════════════════════════════════════════════════════════════════════
# TENANT SCOPING (CLAUDE.md rule 1) AND THE DIMENSION
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6__another_tenants_invoice_cannot_be_settled(brazos, lonestar, marcus, dana):
    """J25 step 12's shape, on the settlement path: a cross-tenant id looks
    exactly like a missing one, because confirming that a row exists somewhere is
    itself a leak."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        invoice_id = captured[CI1]["id"]

    with tenant_ctx(lonestar):
        intruder = staff_actor(lonestar, "billing_clerk", "clerk@lonestarridge.test")
        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.record_settlement(
                intruder, invoice_id, paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
            )
        assert not ledger_models.JournalEntry.objects.filter(tenant=lonestar).exists()

    assert refused.value.br_ref == "BR-TEN-003"
    with tenant_ctx(brazos):
        assert cost_capture.settlement_entry(invoice_id) is None


def test_cr060_t6__the_building_rides_the_cost_line_and_not_the_cash_line(brazos, marcus):
    """BR-LED-001 wants the dimensions *where they apply*. The cost of water
    bought FOR a building belongs to that building; the cash leaving the
    utility's own bank account belongs to no building at all —
    `apps/payments/ledger_seam.py` takes the same posture at both of its cash
    lines. Without this, every by-premises report would put the utility's bank
    movements on a customer's address."""
    from tests.test_us_met_helpers import make_premises

    with tenant_ctx(brazos):
        admin = brazos_ready(brazos, marcus)
        premises = make_premises(admin, address_line="88 Magnolia Row")
        captured = cost_capture.capture_supplier_invoice(
            marcus,
            invoice_date=date(2026, 7, 6),
            service="water",
            supplier_name="City of Rosenberg — Bulk Water Supply",
            amount=CI1_AMOUNT,
            currency="USD",
            premises_id=premises["id"],
            reference=CI1,
        )
        cost_capture.record_settlement(
            marcus, captured["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )
        entry = _entry_for(captured["id"])
        by_side = {line.side: line.premises_id for line in entry.lines.all()}

    assert str(by_side[ledger_models.SIDE_DEBIT]) == str(premises["id"])
    assert by_side[ledger_models.SIDE_CREDIT] is None


# ═══════════════════════════════════════════════════════════════════════════
# WHAT TWO OTHER TASK ROWS INHERIT — reported, not built (CR-060 T6c / T6d)
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6__the_two_task_rows_this_change_hands_on_are_named_in_the_code(brazos, marcus):
    """T6c and T6d were separate rows and this lane did not build them. Naming
    what they inherit as CONSTANTS — rather than as a sentence in a lane report
    nobody kept — is what makes "we told somebody" a thing a grep can find.

    **T6c:** the export's cost section was labelled REGISTER-DERIVED precisely
    because nothing posted. From the first settlement that label was FALSE for
    the settled rows, and the section had to come from the books or the same
    money left twice by two routes.

    **T6d:** the tie-out panel proved receivables, deposits and tax payable
    against the books. Cost became the fourth thing that can drift.

    ⚠ **AMENDED 2026-09-02 — BOTH ROWS ARE BUILT, AND THIS TEST HAD TO CHANGE
    BECAUSE IT WAS PINNING THE STALE STATE.** Its last assertion required the
    export label to still be the blanket register-derived one, which is exactly
    the sentence `DEF-3380` had to retire. A check that holds a hand-off open is
    a check that goes red on the fix — so it now asserts the hand-off was TAKEN,
    which is the fact worth keeping. `tests/test_cr060_t6c_t6d_export_and_tie_
    out.py` holds what each row does.
    """
    assert "REGISTER-DERIVED" in cost_capture.SETTLEMENT_INHERITS_T6C
    assert "BUILT" in cost_capture.SETTLEMENT_INHERITS_T6C
    assert "fourth thing that can drift" in cost_capture.SETTLEMENT_INHERITS_T6D
    assert "BUILT" in cost_capture.SETTLEMENT_INHERITS_T6D

    # The export label is still the register's for the rows it carries, and it
    # no longer claims a settled cost is out of the books.
    from apps.ledger import exports, tie_out

    assert "REGISTER-DERIVED" in exports.COST_SECTION_LABEL
    assert "SETTLED" in exports.COST_SECTION_LABEL
    # And cost really is the fourth tie-out row, so the sentence above is a live
    # statement about the code rather than a note.
    assert tie_out.SUBLEDGER_COST in tie_out.SUBLEDGERS


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060-T6@settlement-posting (the authorities this file was written
#         from, in order: 12-governance/02-decision-log.md — the PO ruling of
#         2026-09-02 in full · 12-governance/11-change-requests.md CR-060 §7 C1
#         (the proof list, verbatim), §12 rows T6/T6a/T6b/T6c/T6d/T19/T20, §13
#         WHAT NOT TO TOUCH, §15 rollback ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-025/028/034/
#         035/037 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-1,
#         LE-9, LE-11, LE-13 · apps/ledger/posting.py and apps/ledger/close.py,
#         read from the code)
# generated: 2026-09-02 by the CR-060 T6/T6a lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(the S73 "Paid on" field is new catalogue strings — reported to the caller) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: PROVED RED BEFORE GREEN, each failure quoted in the review-ledger row ·
#         three transaction-sensitive cases re-run against REAL PostgreSQL 16.13
#         (CLAUDE.md law 14 and C1's own instruction)
# exceptions: OQ-1350 is MINTED and stubbed, not answered — what a settlement
#         should do when its purchase is later corrected or voided
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
