# ── Trace ──────────────────────────────────────────────
# Change:  CR-185-BRC10 D5 — "Balance to owner" POSTS. PO 2026-10-14, closing
#          OQ-1250 → (a): *"option 1; property is always under landload
#          agreement"*.
# Rules:   BR-CUS-097 (as qualified 2026-08-27) · OQ-069 · US-LED-001 (the
#          *"Master-account balance transfer"* contract row) · CLAUDE.md hard
#          rules 1, 2, 4, 5, 6, 7
# Code:    apps/ledger/balance_transfer.py 🔒 · apps/customers/move_out_settlement.py
#          · apps/customers/seams.py (`post_balance_to_owner`)
# ───────────────────────────────────────────────────────
"""The residue a clerk ties back moves in the books — ONE entry, AR to AR.

Worked on the case every rule about this was written against: `A-11024 ·
Ridge Coffee Co.` closes owing **$328.70**; with no deposit held, the whole
**$328.70** is the residue, and the clerk ties it back to the owner.

⚠ **ONLY MONEY IN THE BOOKS MOVES** (coordinator rulings 2026-10-14, the
walk's `DEF-CUS-10152`): step 3 records the choice and previews the figure.
When the move-out DRAFTS a final bill, the commit records the tie-back
PENDING and posts nothing; the entry posts when that bill is ISSUED, for what
the closed account owes then (prior + the bill − deposit and interest). A
voided draft posts nothing and the tie-back stays pending. With nothing left to
bill the commit posts at once. In the nothing-to-bill case the tenant's ledger
balance falls **328.70 → 0.00**, the owner's rises **0.00 → 328.70**, and the
AR control total is **328.70 before and after** — nothing reaches revenue or
bad debt.

Every case runs on SQLite (the default suite) and on PostgreSQL 16
(`--ds=config.settings.pgtest`), where the ledger's sole-writer fence and the
balance trigger are real.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.customers import move_out_settlement
from apps.customers import seams as customer_seams
from apps.customers import services as customer_services
from apps.customers.tie_back_models import STATUS_PENDING, STATUS_POSTED, BalanceTieBack
from apps.ledger import balance_transfer, chart, models, posting, reporting, selectors
from core import errors

from tests import identity_fixtures
from tests.move_out_draft_isolation import move_out_draft_isolated  # noqa: F401
from tests.test_cr056_w6_the_move_out_story import _apartment_block
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_bil_011_final_bill import MOVE_OUT
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, owner_for, tenant_ctx

#: The REAL draft, captured before `move_out_draft_isolated` answers
#: `nothing_to_bill` for every case; the drafted-bill cases put it back.
REAL_DRAFT = customer_seams.draft_move_out_final_bill

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("move_out_draft_isolated")]

CLOSING_BALANCE = Decimal("328.70")
AS_OF = "2026-08-31"
ZERO = Decimal("0")


def _owe(account, amount=CLOSING_BALANCE, *, seed="ridge"):
    """Put a prior balance on `account` the lawful way — through the posting
    service, DR AR (this account) / CR opening clearing — so the settlement
    reads it from the ledger exactly as it reads a real one (DEF-127)."""
    ar = selectors.gl_account_id_for_designation(chart.AR)
    clearing = selectors.gl_account_id_for_designation(chart.OPENING_CLEARING)
    return posting.post(
        posting.PostingRequest(
            posting_key=posting.posting_key(
                source_type="opening_balance", source_id=account.id, event=f"cutover:{seed}"
            ),
            entry_date=date(2026, 8, 1),
            posted_at=datetime(2026, 8, 1, tzinfo=dt_timezone.utc),
            currency="USD",
            source_type="opening_balance",
            source_id=account.id,
            lines=(
                posting.PostingLine(
                    ledger_account_id=ar,
                    side=models.SIDE_DEBIT,
                    amount=amount,
                    source_type="opening_balance",
                    source_id=account.id,
                    account_id=account.id,
                ),
                posting.PostingLine(
                    ledger_account_id=clearing,
                    side=models.SIDE_CREDIT,
                    amount=amount,
                    source_type="opening_balance",
                    source_id=account.id,
                    account_id=account.id,
                ),
            ),
        )
    )


def _owed(*accounts):
    answer = reporting.ar_positions(account_ids=[str(a.id) for a in accounts])
    positions = answer.get("positions") or {}
    return [Decimal(str(positions.get(str(a.id)) or "0")) for a in accounts]


def _tie_back(actor, account, **extra):
    return move_out_settlement.shortfall_decision(
        actor,
        str(account.id),
        {
            "final_bill": Decimal("0.00"),
            "as_of": date.fromisoformat(AS_OF),
            "path": move_out_settlement.SHORTFALL_TRANSFER,
            **extra,
        },
    )


def _transfer_entries(tenant):
    return models.JournalEntry.objects.filter(
        tenant=tenant, source_type=balance_transfer.SOURCE_TRANSFER
    )


def _move_out(actor, account, **extra):
    return customer_services.move_out(
        actor, str(account.id), {"moved_out_on": AS_OF, "shortfall_path": "transfer", **extra}
    )


def _ar_line(entry_id):
    return models.LedgerAccount.objects.get(
        pk=selectors.gl_account_id_for_designation(chart.AR)
    ).code


def _lone_tenant(brazos, dana):
    """A tenant at an address with NO owner (master) account."""
    from apps.metering import services as metering_services

    plan = make_plan(brazos, name="Residential", services=["electric"])
    premises = make_premises(
        dana,
        address_line="9 Pine Rd",
        premises_type="apartment_complex",
        owner_manager="Nobody Opened LLC",
        owner_id=owner_for(dana, "Nobody Opened LLC"),
        services_available=["electric"],
    )
    unit = make_unit(dana, premises["id"], label="Unit 1", services=["electric"])
    metering_services.assign_unit_plan(
        dana, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    created = customer_services.create_account(
        dana,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": "2026-08-01",
            "contact": {"full_name": "Lone Tenant"},
            "customer": identity_fixtures.customer_block("Lone Tenant", account_type="residential"),
        },
    )
    customer_services.activate_account(dana, created["id"])
    return customer_models.Account.objects.get(pk=created["id"])


# ══════════════════════════════════════════════════════════════════════════
# 1 · STEP 3 RECORDS AND PREVIEWS — NOTHING IS POSTED BEFORE THE MOVE-OUT EXISTS
# ══════════════════════════════════════════════════════════════════════════
def test_step_3_records_the_tie_back_and_previews_the_figure_but_posts_nothing(brazos, dana):
    """Coordinator ruling 2026-10-14 (`CR-185-BRC10`, the walk's `DEF-CUS-10152`):
    the money moves AT MOVE-OUT, so on an open account step 3 posts nothing."""
    with tenant_ctx(brazos):
        _premises, _unit, master, regular = _apartment_block(dana, brazos, declare_owner=True)
        _owe(regular)
        decision = _tie_back(dana, regular)
        assert decision["target"]["account_no"] == master.account_no
        assert decision["posting"]["posted"] is False
        assert decision["posting"]["posts_at"] == "final_bill_issue"
        assert decision["posting"]["amount"]["display"] == "328.70"
        assert decision["posting"]["to_account_no"] == master.account_no
        assert not _transfer_entries(brazos).exists()
        assert _owed(regular, master) == [CLOSING_BALANCE, ZERO]


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE COMMIT POSTS ONE BALANCED ENTRY — by account code AND by figure
# ══════════════════════════════════════════════════════════════════════════
def test_the_commit_posts_one_entry_dr_ar_owner_cr_ar_tenant(brazos, dana):
    with tenant_ctx(brazos):
        _premises, _unit, master, regular = _apartment_block(dana, brazos, declare_owner=True)
        _owe(regular)
        tenant_before, owner_before = _owed(regular, master)
        control_before = reporting.ar_control()

        result = _move_out(dana, regular)

        moved = result["balance_to_owner"]
        assert moved["posted"] is True and moved["created"] is True
        assert moved["amount"]["display"] == "328.70"
        entry = models.JournalEntry.objects.get(pk=moved["entry_id"])
        assert entry.status == models.JE_POSTED
        assert entry.entry_date == date(2026, 8, 31)
        assert entry.posting_key == f"transfer|{regular.id}|balance_to_owner"
        lines = list(entry.lines.select_related("ledger_account").order_by("side"))
        assert len(lines) == 2
        credit, debit = lines
        ar_code = _ar_line(entry.id)
        assert debit.ledger_account.code == ar_code == credit.ledger_account.code
        assert (debit.side, debit.amount, str(debit.account_id)) == (
            models.SIDE_DEBIT, CLOSING_BALANCE, str(master.id)
        )
        assert (credit.side, credit.amount, str(credit.account_id)) == (
            models.SIDE_CREDIT, CLOSING_BALANCE, str(regular.id)
        )
        # The tenant falls to zero, the owner rises by the same, total AR stays.
        assert (tenant_before, owner_before) == (CLOSING_BALANCE, ZERO)
        assert _owed(regular, master) == [ZERO, CLOSING_BALANCE]
        assert reporting.ar_control() == control_before == CLOSING_BALANCE
        ar = selectors.gl_account_id_for_designation(chart.AR)
        assert not models.JournalLine.objects.filter(
            tenant=brazos, source_type="transfer"
        ).exclude(ledger_account_id=ar).exists()
        assert customer_models.Account.objects.get(pk=regular.id).closed_at == date(2026, 8, 31)


def test_nothing_left_to_bill_the_commit_records_the_tie_back_as_posted(brazos, dana):
    """No final bill drafted (every day already on an issued bill): everything
    owed is in the books at the commit, so it posts there and the record says so."""
    with tenant_ctx(brazos):
        _premises, _unit, master, regular = _apartment_block(dana, brazos, declare_owner=True)
        _owe(regular)
        moved = _move_out(dana, regular)["balance_to_owner"]
        row = BalanceTieBack.objects.get(account_id=regular.id)
        assert row.status == STATUS_POSTED
        assert str(row.journal_entry_id) == str(moved["entry_id"])
        assert row.posted_amount == CLOSING_BALANCE
        state = move_out_settlement.balance_to_owner_for(regular)
        assert state["status"] == "posted" and state["amount"]["display"] == "328.70"


# ══════════════════════════════════════════════════════════════════════════
# 2b · A DRAFTED FINAL BILL — PENDING AT COMMIT, POSTED WHEN THE BILL ISSUES
# ══════════════════════════════════════════════════════════════════════════
# The real draft and the real Send (`tests/test_def_cus_10093_…`): a metered
# account read on the move day, $150.00 deposit + $3.50 interest, $500.00 of
# arrears, and an owner (master) account at the same address.
ARREARS = Decimal("500")
DEPOSIT_APPLIED = Decimal("153.50")


def _billable_tenant_with_an_owner(brazos, dana, monkeypatch, *, asset_no, account_no):
    from apps.metering import models as metering_models
    from apps.metering import selectors as metering_selectors
    from tests.test_br_bil_013_final_bill_preview import _a_moving_out_account

    monkeypatch.setattr(customer_seams, "draft_move_out_final_bill", REAL_DRAFT)
    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "06-S", "name": "Cycle 06", "due_days": 21},
    )
    account = _a_moving_out_account(
        brazos, dana, monkeypatch, asset_no=asset_no, account_no=account_no, arrears=ARREARS
    )
    premises_id = metering_models.Unit.objects.get(pk=account.unit_id).premises_id
    make_unit(dana, str(premises_id), label="Q", services=["electric"])
    master = customer_services.create_master_account(
        dana,
        {
            "premises_id": str(premises_id),
            "account_type": "commercial",
            "opened_at": "2026-01-01",
            "customer": identity_fixtures.customer_block("Maple Rentals LLC", kind="company"),
        },
    )
    return account, customer_models.Account.objects.get(pk=master["id"])


def _final_draft(account):
    from apps.billing import models as billing_models

    return billing_models.Invoice.objects.get(account_id=account.id, bill_type="final")


def _send_final(account, actor):
    from apps.billing import models as billing_models
    from tests.test_def_cus_10093_move_out_drafts_the_final_bill import _send

    invoice = _final_draft(account)
    _send(billing_models.BillRun.objects.get(pk=invoice.bill_run_id), actor)
    invoice.refresh_from_db()
    return invoice


def _commit(actor, account, **extra):
    from tests.test_us_bil_011_final_bill import MOVE_OUT

    return customer_services.move_out(
        actor,
        str(account.id),
        {"moved_out_on": MOVE_OUT.isoformat(), "shortfall_path": "transfer", **extra},
    )


def test_a_drafted_final_bill_the_commit_records_pending_and_posts_nothing(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        account, master = _billable_tenant_with_an_owner(
            brazos, dana, monkeypatch, asset_no="M-9851", account_no="A-18501"
        )
        lines_before = models.JournalLine.objects.filter(tenant=brazos).count()

        result = _commit(dana, account)

        draft = _final_draft(account)
        moved = result["balance_to_owner"]
        assert moved["posted"] is False and moved["pending"] is True
        assert moved["posts_at"] == "final_bill_issue"
        assert moved["to_account_no"] == master.account_no
        assert moved["final_bill_no"] == draft.invoice_no
        preview = ARREARS + draft.total - DEPOSIT_APPLIED
        assert Decimal(moved["amount"]["display"]) == preview
        assert not _transfer_entries(brazos).exists()
        assert models.JournalLine.objects.filter(tenant=brazos).count() == lines_before
        assert _owed(account, master) == [ARREARS, ZERO]
        row = BalanceTieBack.objects.get(account_id=account.id)
        assert row.status == STATUS_PENDING and str(row.final_invoice_id) == str(draft.pk)
        assert move_out_settlement.balance_to_owner_for(account)["pending"] is True


def test_issuing_the_final_bill_posts_one_entry_for_what_is_owed_then(
    brazos, dana, monkeypatch, audit_rows
):
    with tenant_ctx(brazos):
        account, master = _billable_tenant_with_an_owner(
            brazos, dana, monkeypatch, asset_no="M-9852", account_no="A-18502"
        )
        _commit(dana, account)
        control_before = reporting.ar_control()
        del audit_rows[:]

        invoice = _send_final(account, dana)

        assert invoice.status == "issued"
        owed_then = ARREARS + invoice.total - DEPOSIT_APPLIED
        (entry,) = _transfer_entries(brazos)
        lines = list(entry.lines.order_by("side"))
        credit, debit = lines
        assert (debit.side, debit.amount, str(debit.account_id)) == (
            models.SIDE_DEBIT, owed_then, str(master.id)
        )
        assert (credit.side, credit.amount, str(credit.account_id)) == (
            models.SIDE_CREDIT, owed_then, str(account.id)
        )
        # The tenant falls to $0.00, the owner rises by the amount, and AR moves
        # only by the bill and the deposit — the transfer adds nothing to it.
        assert _owed(account, master) == [ZERO, owed_then]
        assert reporting.ar_control() == control_before + invoice.total - DEPOSIT_APPLIED
        row = BalanceTieBack.objects.get(account_id=account.id)
        assert row.status == STATUS_POSTED and row.posted_amount == owed_then
        assert str(row.journal_entry_id) == str(entry.id)
        assert str(row.final_invoice_id) == str(invoice.pk)
        posted = [r for r in audit_rows if r["action"] == "account.move_out.balance_to_owner_posted"]
        assert len(posted) == 1
        state = move_out_settlement.balance_to_owner_for(account)
        assert state["status"] == "posted" and Decimal(state["amount"]["display"]) == owed_then

        # A retry of the hand-off — or a re-issue — posts nothing new.
        again = move_out_settlement.post_pending_balance_to_owner(
            str(account.id),
            invoice_id=str(invoice.pk),
            entry_date=date(2026, 6, 15),
            posted_at=datetime(2026, 6, 15, tzinfo=dt_timezone.utc),
        )
        assert again["created"] is False and again["posted"] is True
        assert _transfer_entries(brazos).count() == 1
        assert _owed(account, master) == [ZERO, owed_then]


def test_a_voided_final_draft_posts_nothing_and_the_tie_back_stays_pending(
    brazos, dana, monkeypatch
):
    """The draft is thrown away instead of sent: nothing posts and the move-out
    record still shows the tie-back pending. The record page can then post it,
    because nothing is waiting to be billed any more."""
    from apps.billing import models as billing_models
    from apps.billing import runs

    with tenant_ctx(brazos):
        account, master = _billable_tenant_with_an_owner(
            brazos, dana, monkeypatch, asset_no="M-9853", account_no="A-18503"
        )
        _commit(dana, account)
        draft = _final_draft(account)
        runs.discard_run(billing_models.BillRun.objects.get(pk=draft.bill_run_id), actor=dana)
        assert not billing_models.Invoice.objects.filter(pk=draft.pk, status="draft").exists()

        assert not _transfer_entries(brazos).exists()
        assert _owed(account, master) == [ARREARS, ZERO]
        assert BalanceTieBack.objects.get(account_id=account.id).status == STATUS_PENDING
        assert move_out_settlement.balance_to_owner_for(account)["pending"] is True


def test_the_move_out_record_waits_for_a_draft_still_unsent_then_posts_at_issue(
    brazos, dana, monkeypatch
):
    """Tied back on the move-out RECORD (account closed) while the final draft is
    still waiting: recorded pending, nothing posted; the Send posts it."""
    with tenant_ctx(brazos):
        account, master = _billable_tenant_with_an_owner(
            brazos, dana, monkeypatch, asset_no="M-9854", account_no="A-18504"
        )
        _commit(dana, account, shortfall_path=None)
        account.refresh_from_db()
        draft = _final_draft(account)
        decision = move_out_settlement.shortfall_decision(
            dana,
            str(account.id),
            {"final_bill": draft.total, "as_of": MOVE_OUT, "path": move_out_settlement.SHORTFALL_TRANSFER},
        )
        assert decision["posting"]["pending"] is True
        assert not _transfer_entries(brazos).exists()

        invoice = _send_final(account, dana)
        owed_then = ARREARS + invoice.total - DEPOSIT_APPLIED
        assert _transfer_entries(brazos).count() == 1
        assert _owed(account, master) == [ZERO, owed_then]


# ══════════════════════════════════════════════════════════════════════════
# 3 · A REFUSED COMMIT POSTS NOTHING — and a retry posts once
# ══════════════════════════════════════════════════════════════════════════
def test_a_refused_commit_posts_nothing_and_a_retry_posts_once(brazos, dana, monkeypatch):
    from apps.customers import seams as customer_seams

    def refused(actor, *, account_id, moved_out_on):
        return {"outcome": "refused", "reason": "missing_read_undecided_at_calculate",
                "message_key": None, "detail": "water has no usable read"}

    with tenant_ctx(brazos):
        _premises, _unit, master, regular = _apartment_block(dana, brazos, declare_owner=True)
        _owe(regular)
        isolated = customer_seams.draft_move_out_final_bill
        lines_before = models.JournalLine.objects.filter(tenant=brazos).count()
        control_before = reporting.ar_control()

        monkeypatch.setattr(customer_seams, "draft_move_out_final_bill", refused)
        with pytest.raises(errors.BizError) as no:
            _move_out(dana, regular)
        assert no.value.message_key == "customers.move_out.final_bill_not_drafted"
        assert not _transfer_entries(brazos).exists()
        assert models.JournalLine.objects.filter(tenant=brazos).count() == lines_before
        assert _owed(regular, master) == [CLOSING_BALANCE, ZERO]
        assert reporting.ar_control() == control_before
        assert customer_models.Account.objects.get(pk=regular.id).closed_at is None

        # The retry succeeds and posts ONE entry …
        monkeypatch.setattr(customer_seams, "draft_move_out_final_bill", isolated)
        first = _move_out(dana, regular)["balance_to_owner"]
        assert first["created"] is True
        assert _transfer_entries(brazos).count() == 1
        # … a re-delivered handoff posts nothing new …
        again = balance_transfer.post_balance_to_owner(
            from_account_id=regular.id,
            to_account_id=master.id,
            amount=CLOSING_BALANCE,
            entry_date=date(2026, 8, 31),
            posted_at=datetime(2026, 8, 31, tzinfo=dt_timezone.utc),
            currency="USD",
        )
        assert again.created is False and again.entry_id == first["entry_id"]
        # … one for a different figure is refused, never answered "posted" …
        with pytest.raises(balance_transfer.BalanceTransferError):
            balance_transfer.post_balance_to_owner(
                from_account_id=regular.id,
                to_account_id=master.id,
                amount=Decimal("10.00"),
                entry_date=date(2026, 8, 31),
                posted_at=datetime(2026, 8, 31, tzinfo=dt_timezone.utc),
                currency="USD",
            )
        # … and the move-out cannot run twice.
        with pytest.raises(errors.BizError):
            _move_out(dana, regular)
        assert _transfer_entries(brazos).count() == 1
        assert _owed(regular, master) == [ZERO, CLOSING_BALANCE]


# ══════════════════════════════════════════════════════════════════════════
# 4 · NO OWNER ACCOUNT — refused by name, at step 3 and at commit
# ══════════════════════════════════════════════════════════════════════════
def test_with_no_owner_account_the_tie_back_is_refused_and_nothing_moves(brazos, dana):
    with tenant_ctx(brazos):
        tenant_account = _lone_tenant(brazos, dana)
        _owe(tenant_account, seed="lone")
        lines_before = models.JournalLine.objects.filter(tenant=brazos).count()
        with pytest.raises(errors.BizError) as refused:
            _tie_back(dana, tenant_account)
        assert refused.value.message_key == "customers.move_out.shortfall_transfer_no_target"
        with pytest.raises(errors.BizError) as at_commit:
            _move_out(dana, tenant_account)
        assert at_commit.value.message_key == "customers.move_out.shortfall_transfer_no_target"
        assert models.JournalLine.objects.filter(tenant=brazos).count() == lines_before
        assert _owed(tenant_account) == [CLOSING_BALANCE]
        assert customer_models.Account.objects.get(pk=tenant_account.id).closed_at is None


# ══════════════════════════════════════════════════════════════════════════
# 5 · AUDIT — the decision and the entry, both written by the commit
# ══════════════════════════════════════════════════════════════════════════
def test_the_commit_writes_both_audit_rows(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        _premises, _unit, master, regular = _apartment_block(dana, brazos, declare_owner=True)
        _owe(regular)
        del audit_rows[:]
        moved = _move_out(dana, regular)["balance_to_owner"]
        decided = [r for r in audit_rows if r["action"] == "account.move_out.shortfall_decided"]
        assert len(decided) == 1
        assert decided[0]["after"]["posting"]["entry_id"] == moved["entry_id"]
        posted = [
            r for r in audit_rows
            if r["action"] == "journal.posted" and str(r["entity_id"]) == str(moved["entry_id"])
        ]
        assert len(posted) == 1
        assert posted[0]["after"]["balance_to_owner"] == "328.70"


# ══════════════════════════════════════════════════════════════════════════
# 6 · AFTER THE MOVE-OUT (the move-out record) — posted, dated the close
# ══════════════════════════════════════════════════════════════════════════
def test_a_tie_back_after_the_move_out_posts_now_dated_the_close(brazos, dana):
    """The move-out record ties back on a CLOSED account: the move-out exists,
    so the entry posts at once, dated `accounts.closed_at`, never a clock."""
    with tenant_ctx(brazos):
        _premises, _unit, master, regular = _apartment_block(dana, brazos, declare_owner=True)
        _owe(regular)
        customer_services.move_out(dana, str(regular.id), {"moved_out_on": AS_OF})
        assert not _transfer_entries(brazos).exists()
        decision = move_out_settlement.shortfall_decision(
            dana,
            str(regular.id),
            {"final_bill": Decimal("0.00"), "path": move_out_settlement.SHORTFALL_TRANSFER},
        )
        assert decision["posting"]["posted"] is True
        entry = models.JournalEntry.objects.get(pk=decision["posting"]["entry_id"])
        assert entry.entry_date == date(2026, 8, 31)
        assert _owed(regular, master) == [ZERO, CLOSING_BALANCE]


def test_nothing_owed_at_commit_posts_nothing(brazos, dana):
    with tenant_ctx(brazos):
        _premises, _unit, master, regular = _apartment_block(dana, brazos, declare_owner=True)
        result = _move_out(dana, regular)
        assert result["balance_to_owner"]["posted"] is False
        assert result["balance_to_owner"]["reason"] == "nothing_owed_at_move_out"
        assert not _transfer_entries(brazos).exists()


# ══════════════════════════════════════════════════════════════════════════
# 7 · THE OTHER PATHS STILL MOVE NOTHING
# ══════════════════════════════════════════════════════════════════════════
def test_collect_posts_nothing_at_step_3_or_at_commit(brazos, dana):
    with tenant_ctx(brazos):
        _premises, _unit, master, regular = _apartment_block(dana, brazos, declare_owner=True)
        _owe(regular)
        decision = _tie_back(dana, regular, path=move_out_settlement.SHORTFALL_COLLECT)
        assert decision["posting"]["posted"] is False
        result = _move_out(dana, regular, shortfall_path="collect")
        assert result["balance_to_owner"] is None
        assert not _transfer_entries(brazos).exists()
        assert _owed(regular, master) == [CLOSING_BALANCE, ZERO]


# ══════════════════════════════════════════════════════════════════════════
# 8 · ISOLATION — another tenant can neither reach the account nor see the entry
# ══════════════════════════════════════════════════════════════════════════
def test_another_tenant_cannot_tie_back_or_see_the_transfer(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        _premises, _unit, master, regular = _apartment_block(dana, brazos, declare_owner=True)
        _owe(regular)
        entry_id = _move_out(dana, regular)["balance_to_owner"]["entry_id"]
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            _tie_back(erin, regular)
        assert not models.JournalEntry.objects.filter(
            tenant=lonestar, source_type="transfer"
        ).exists()
        positions = reporting.ar_positions(account_ids=[str(regular.id), str(master.id)])
        assert not (positions.get("positions") or {})
    with tenant_ctx(brazos):
        assert models.JournalEntry.objects.filter(pk=entry_id).count() == 1
