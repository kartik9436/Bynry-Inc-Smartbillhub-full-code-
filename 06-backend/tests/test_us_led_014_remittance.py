# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-014 (S41 dual-basis remittance — TC-1 LE-3's two bases,
#           TC-2 the per-authority basis setting, TC-3 the remittance JE,
#           TC-4 the tie-out, TC-5 the filing trail, TC-6/TC-7 the refusals and
#           the replay, TC-8 isolation)
#           Screens: S41 · S56
# Rules:    BR-LED-002 (BOTH bases always computed; the remittance payment is a
#           JE draining the authority's liability) · BR-LED-013 (billed ·
#           collected · remitted · outstanding per authority) · BR-LED-007 (tax
#           payable GL = remittance outstanding) · BR-LED-019 (confirmation ref
#           + receipt) · BR-REP-001 (basis labels) · BR-BIL-069 (each authority
#           has its own 2200-series account) · CLAUDE.md rules 1/2/5/6/7
# Golden:   LE-3 (billed 47.38 vs collected 20.97; State 13.87 · County 2.22 ·
#           City 4.44 · PUC 0.44) · B5 line 74 ❄️ (the 2200 series) ·
#           US-LED-014 §7 CONFIRMED
# ───────────────────────────────────────────────────────
"""The two bases diverge, and only one of them can be computed from the books.

**WHAT WORKS.** The per-authority BILLED basis needs no `tax_authority_id`
dimension at all — the PO ruled on 2026-08-11 (BR-BIL-069) that *"For each
atheority have separate account and tagging"* and B5 line 74 ❄️ signs the series,
so **the authority's own 2200-nn account IS its identity in the books**. LE-3's
State 13.87 · County 2.22 · City 4.44 · PUC 0.44 come straight out of a group-by
over accounts.

⚠ **AND WHAT DID NOT, UNTIL 2026-09-02 (CR-060 C19 / task T7d).** This paragraph
read *"WHAT DOES NOT. The COLLECTED basis is tax inside cleared payments via
allocation, and an `allocations` row carries a payment, an invoice, an amount and
NO LINE CLASS (OQ-129) … The column is None with the reason attached and the OQ
minted"*. **`allocation_classes` (payments/0015) records what every payment met
inside every bill**, so the column is PRODUCED now and its refusal is retired.

**THE FAILURE THIS FILE GUARDS AGAINST IS UNCHANGED AND IS THE ONLY REASON THE
CASE STILL EXISTS: the collected column must never be the billed figure wearing
a different name.** On this fixture nothing has been paid at all, so collected is
a REAL 0.00 against billed 47.38 — and a utility filing on the collected basis
remits nothing, correctly, rather than 47.38 of money it has not received.

**AND CASH IS NOT CASH UNTIL THE BANK SAYS SO.** PO ruling 2026-08-11 (OQ-143):
*"until bank record and reconcilaition confirm it it is not realised."* A
collected-basis figure that counted a keyed-but-unbanked payment would remit tax
on money the utility does not have.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import chart, journal, models, reporting

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE1_TAX_PAYABLE,
    LE3_AUTHORITIES,
    LE3_BILLED_BASIS_JULY,
    LE3_COLLECTED_BASIS_JULY,
    LE3_STATE_REMIT_NOW,
    WE1_TAX,
    ensure_authority_accounts,
    make_accounts,
    post_le1_month,
    post_le3_authorities,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")
REMITTED_ON = date(2026, 8, 18)  # US-LED-014 §4: "State 13.87 recorded Aug 18, 2026"
REMITTED_AT = datetime(2026, 8, 18, 14, 5, tzinfo=dt_timezone.utc)
CONFIRMATION = "TXC-2026-08-9012"  # US-LED-014 §4 verbatim


def a_month(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def the_four_authorities(tenant, actor):
    """LE-3's four authorities, minted through the real service call, with
    WE-1's 20.97 tax posted across them."""
    accounts = make_accounts(actor, tenant, {})
    authorities = ensure_authority_accounts(tenant, actor)
    post_le3_authorities(tenant, accounts, authorities)
    return accounts, authorities


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the two bases, side by side, both labelled
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_014_tc1__billed_basis_is_le3s_47_38_and_collected_is_never_billeds_number(
    brazos, dana
):
    """US-LED-014 TC-1: *"Billed basis **47.38** (all three bills) vs collected
    basis **20.97** … both shown side by side per authority with basis labels."*

    ⚠ **AMENDED 2026-09-02 (CR-060 C19 / task T7d) — THE COLLECTED COLUMN IS A
    FIGURE NOW.** This case read
    `..._and_collected_is_reported_unavailable` and asserted `collected is None`
    with `tax_inside_a_cleared_payment_is_not_derivable` attached, which was the
    honest answer for as long as an `allocations` row carried no line class.
    `allocation_classes` records what every payment met, so the column is
    produced and the refusal is RETIRED (never reworded — C19's own
    instruction).

    **THE FAILURE THIS ASSERTS AGAINST IS THE SAME ONE AND IS THE POINT OF THE
    CASE: showing 47.38 in BOTH columns.** On this fixture NOTHING HAS BEEN PAID,
    so collected is a real **0.00** — a utility on the collected basis remits
    nothing this month, correctly, instead of tax on 47.38 of money it has not
    received. The produced 20.97 for a bill that IS paid is
    `tests/test_cr060_t7d_allocation_classes.py` TC-2.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)

        assert report["totals"]["billed"] == LE3_BILLED_BASIS_JULY == LE1_TAX_PAYABLE
        # A REAL zero — no payment exists on this fixture — and never billed's
        # number under collected's heading.
        assert report["totals"]["collected"] == Decimal("0")
        assert report["totals"]["collected"] != report["totals"]["billed"]
        assert all(row.collected == Decimal("0") for row in report["rows"])
        assert all(row.outstanding_collected == -row.remitted for row in report["rows"])

        # BR-REP-001 — each column names its own basis, and they differ.
        assert report["basis"] == {
            "billed": reporting.BASIS_POSTING,
            # The POSTING date since 2026-10-21 (DEF-PAY-10321, PO ruling).
            "collected": reporting.BASIS_POSTING,
        }

        codes = {gap["code"] for gap in report["unavailable"]}
        assert "tax_inside_a_cleared_payment_is_not_derivable" not in codes

        # The number that must NOT appear in the collected column, unchanged.
        assert LE3_BILLED_BASIS_JULY != LE3_COLLECTED_BASIS_JULY
        assert LE3_BILLED_BASIS_JULY - LE3_COLLECTED_BASIS_JULY == Decimal("26.41")


def test_us_led_014_tc1b__the_per_authority_split_is_le3s_and_needs_no_dimension(brazos, dana):
    """LE-3 / US-LED-014 §4 verbatim: *"per-authority billed split: State 13.87 ·
    County 2.22 · City 4.44 · PUC 0.44"* — summing to WE-1's **20.97**.

    This is BR-BIL-069 doing the work. `journal_lines.tax_authority_id` is NULL
    on every line in the product (rating publishes no
    `tax_authority_id_for_tax`), and the split still resolves — because the PO
    ruled each authority gets its OWN account and the account is the identity.
    """
    with tenant_ctx(brazos):
        the_four_authorities(brazos, dana)
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        by_code = {row.code: row for row in report["rows"]}

        for code, name, amount in LE3_AUTHORITIES:
            assert by_code[code].billed == amount, f"{code} is not LE-3's figure"
            assert by_code[code].name == name
        assert report["totals"]["billed"] == WE1_TAX == Decimal("20.97")

        # …and the dimension really is absent, so this is not an accident.
        assert not models.JournalLine.objects.filter(
            tenant=brazos, tax_authority_id__isnull=False
        ).exists()
        codes = {gap["code"] for gap in report["unavailable"]}
        assert "authority_identity_is_the_gl_account_not_the_jurisdiction_row" in codes


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — the per-authority remitting basis
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_014_tc2__the_remitting_basis_setting_has_no_home_and_is_not_defaulted(brazos, dana):
    """US-LED-014 TC-2 wants *"State = collected → remit-now figure 13.87;
    County = billed"*. The per-AUTHORITY setting that would hold it does not
    exist.

    ⚠ **THIS DOCSTRING SAID *"there is no `tax_remittances` table in the schema
    at all"* UNTIL 2026-09-24, AND THE CASE ASSERTED THAT ABSENCE.** `P4.4`
    built the table, so that line is false and is amended rather than deleted —
    **what it was really guarding is still true.** `tax_remittances.basis`
    records the basis of ONE FILING, which is what a clerk typed on the day.
    The per-authority SETTING — *this authority always files on collected* — has
    no home still, and `per_authority_remitting_basis_is_not_stored` is
    therefore still the honest answer. Conflating the two would make the
    product answer *"collected"* for an authority nobody has ever configured,
    on the strength of one past filing.

    So every row's `remitting_basis` is None and BOTH bases are offered. That is
    BR-LED-002 honoured rather than approximated: LE-3 has State on collected
    and County on billed, so ANY default is wrong for one of them in its first
    month.
    """
    with tenant_ctx(brazos):
        the_four_authorities(brazos, dana)
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)

        assert all(row.remitting_basis is None for row in report["rows"])
        assert all(
            # (billed, collected) — collected is posting-dated since 2026-10-21.
            row.bases == (reporting.BASIS_POSTING, reporting.BASIS_POSTING)
            for row in report["rows"]
        )
        codes = {gap["code"] for gap in report["unavailable"]}
        assert "per_authority_remitting_basis_is_not_stored" in codes

        from django.db import connection

        # The table EXISTS as of `ledger/0020` — asserted, so that a revert of
        # `P4.4` makes this case RED rather than quietly restoring the world
        # this docstring used to describe.
        assert "tax_remittances" in connection.introspection.table_names()
        # ⚠ **AND IT STILL CARRIES NO PER-AUTHORITY SETTING, WHICH IS WHAT THIS
        # CASE IS ABOUT.** A `basis` column on a FILING is the basis of one
        # return; a setting is a property of the AUTHORITY. Naming the columns
        # is what keeps this from being satisfied by the first of them.
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                connection.cursor(), "tax_remittances"
            )
        }
        assert "basis" in columns  # per FILING
        assert not {"default_basis", "remitting_basis"} & columns  # per AUTHORITY


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the remittance JE that drains the liability
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_014_tc3__recording_the_state_remittance_drains_13_87(brazos, dana):
    """US-LED-014 TC-3 verbatim: *"JE: DR 2200 State **13.87** / CR cash
    **13.87** — balanced, posting service 🔒 … outstanding drops by 13.87"*, and
    §7: *"outstanding(State, collected) = 13.87 − 13.87 = **0.00** after
    recording."*

    The REMITTED column is read back out of the books — Σ remittance-sourced
    debits on that account — not out of a register, because there is no register
    and because BR-REP-002 makes the books the number that has to be right.
    """
    with tenant_ctx(brazos):
        _accounts, authorities = the_four_authorities(brazos, dana)
        state = authorities["2200-01"]

        before = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        state_before = next(row for row in before["rows"] if row.code == "2200-01")
        assert state_before.billed == LE3_STATE_REMIT_NOW
        assert state_before.remitted == ZERO
        assert state_before.outstanding_billed == LE3_STATE_REMIT_NOW

        result = journal.record_tax_remittance(
            tax_account_id=state.id,
            period_start=JULY_START,
            period_end=JULY_END,
            amount=LE3_STATE_REMIT_NOW,
            basis=journal.BASIS_COLLECTED,
            confirmation_ref=CONFIRMATION,
            entry_date=REMITTED_ON,
            posted_at=REMITTED_AT,
            actor=dana,
        )
        assert result.created is True
        assert result.amount == LE3_STATE_REMIT_NOW

        entry = models.JournalEntry.objects.get(pk=result.entry_id)
        legs = {(row.ledger_account.code, row.side): row.amount for row in entry.lines.all()}
        assert legs[("2200-01", models.SIDE_DEBIT)] == LE3_STATE_REMIT_NOW
        assert legs[("1000", models.SIDE_CREDIT)] == LE3_STATE_REMIT_NOW
        assert entry.status == models.JE_POSTED

        after = reporting.remittance_by_authority(start=JULY_START, end=date(2026, 8, 31))
        state_after = next(row for row in after["rows"] if row.code == "2200-01")
        assert state_after.remitted == LE3_STATE_REMIT_NOW
        assert state_after.outstanding_billed == ZERO


def test_us_led_014_tc3b__it_credits_cash_and_never_undeposited_funds(brazos, dana):
    """A remittance is money LEAVING the utility's bank. `undeposited_funds` is
    money that has not reached the bank yet (PO 2026-08-11, OQ-143), so
    crediting it would report the payment as made out of a drawer."""
    with tenant_ctx(brazos):
        _accounts, authorities = the_four_authorities(brazos, dana)
        result = journal.record_tax_remittance(
            tax_account_id=authorities["2200-01"].id,
            period_start=JULY_START,
            period_end=JULY_END,
            amount=LE3_STATE_REMIT_NOW,
            basis=journal.BASIS_COLLECTED,
            confirmation_ref=CONFIRMATION,
            entry_date=REMITTED_ON,
            posted_at=REMITTED_AT,
            actor=dana,
        )
        codes = {
            row.ledger_account.code
            for row in models.JournalEntry.objects.get(pk=result.entry_id).lines.all()
        }
        assert codes == {"2200-01", "1000"}
        assert "1010" not in codes


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — the S36 tie-out
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_014_tc4__tax_payable_gl_equals_remittance_outstanding(brazos, dana):
    """BR-LED-007: *"tax payable = remittance outstanding"*, and US-LED-014
    TC-4: *"S36 tax tie-out = Σ outstanding across authorities."*

    Both sides come out of the SAME rows, which is the point — one derivation
    cannot drift from itself. The tie is asserted before AND after a remittance,
    because a drain that moved one side and not the other is exactly the drift
    BR-LED-007 calls a release blocker.
    """
    with tenant_ctx(brazos):
        _accounts, authorities = the_four_authorities(brazos, dana)

        window = {"start": JULY_START, "end": date(2026, 8, 31)}
        report = reporting.remittance_by_authority(**window)
        assert report["tie_out"]["tax_payable_gl"] == report["totals"]["outstanding_billed"]
        assert report["tie_out"]["tax_payable_gl"] == WE1_TAX

        journal.record_tax_remittance(
            tax_account_id=authorities["2200-01"].id,
            period_start=JULY_START,
            period_end=JULY_END,
            amount=LE3_STATE_REMIT_NOW,
            basis=journal.BASIS_COLLECTED,
            confirmation_ref=CONFIRMATION,
            entry_date=REMITTED_ON,
            posted_at=REMITTED_AT,
            actor=dana,
        )
        after = reporting.remittance_by_authority(**window)
        assert after["tie_out"]["tax_payable_gl"] == after["totals"]["outstanding_billed"]
        assert after["tie_out"]["tax_payable_gl"] == WE1_TAX - LE3_STATE_REMIT_NOW

        # …and the books still foot.
        assert reporting.trial_balance(end=date(2026, 8, 31))["balanced"] is True


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — the filing trail, and the artifact that has no home
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_014_tc5__the_confirmation_ref_survives_and_an_unusable_receipt_is_refused(
    brazos, dana, audit_rows
):
    """BR-LED-019: *"remittance records carry a filing CONFIRMATION REF +
    receipt file attachment (auditor artifact)"*.

    The ref is REQUIRED and lands on the immutable entry memo and in the
    append-only audit payload.

    ⚠ **THE RECEIPT HALF WAS AMENDED 2026-09-24 (`P4.3`/`P4.4`) AND STILL
    BITES ON THE SAME BYTES.** It used to assert that EVERY receipt was refused,
    because `tax_remittances` did not exist and accepting an attachment only to
    drop it is the worst of the three options — the clerk who attached it
    believes it was kept. The table exists now, so what is refused is narrower:
    a receipt in a shape the store cannot take. `b"scan.pdf"` is still refused
    here because raw bytes carry no media type and no filename, and
    `document_store.store()` measures neither — so a caller handing them over
    would store whatever it happened to contain. A receipt that IS kept is
    `tests/test_cr140_p4_filing_register.py`, which reads the bytes back.
    """
    with tenant_ctx(brazos):
        _accounts, authorities = the_four_authorities(brazos, dana)
        state = authorities["2200-01"].id

        with pytest.raises(journal.JournalActionError):
            journal.record_tax_remittance(
                tax_account_id=state,
                period_start=JULY_START,
                period_end=JULY_END,
                amount=LE3_STATE_REMIT_NOW,
                basis=journal.BASIS_COLLECTED,
                confirmation_ref="",
                entry_date=REMITTED_ON,
                posted_at=REMITTED_AT,
                actor=dana,
            )
        with pytest.raises(journal.JournalActionError):
            journal.record_tax_remittance(
                tax_account_id=state,
                period_start=JULY_START,
                period_end=JULY_END,
                amount=LE3_STATE_REMIT_NOW,
                basis=journal.BASIS_COLLECTED,
                confirmation_ref=CONFIRMATION,
                entry_date=REMITTED_ON,
                posted_at=REMITTED_AT,
                actor=dana,
                receipt=b"scan.pdf",
            )

        result = journal.record_tax_remittance(
            tax_account_id=state,
            period_start=JULY_START,
            period_end=JULY_END,
            amount=LE3_STATE_REMIT_NOW,
            basis=journal.BASIS_COLLECTED,
            confirmation_ref=CONFIRMATION,
            entry_date=REMITTED_ON,
            posted_at=REMITTED_AT,
            actor=dana,
        )
        entry = models.JournalEntry.objects.get(pk=result.entry_id)
        assert CONFIRMATION in entry.memo
        assert "collected" in entry.memo

        posted = [row for row in audit_rows if row["action"] == "journal.posted"]
        trail = next(row for row in posted if row["entity_id"] == result.entry_id)
        assert trail["after"]["confirmation_ref"] == CONFIRMATION
        assert trail["after"]["basis"] == "collected"
        assert trail["after"]["amount"] == str(LE3_STATE_REMIT_NOW)
        assert trail["after"]["authority_account_code"] == "2200-01"

        # ⚠ **THESE TWO LINES ASSERTED THE OPPOSITE UNTIL 2026-09-24.** They
        # read `assert "remittance_receipt_attachment_has_no_column" in codes`
        # and `assert "tax_remittances_register_not_built" in codes` — two
        # `unavailable` entries that rode on EVERY remittance response this
        # product ever gave. `ledger/0020` builds the register and
        # `tenancy/0052` gives the receipt a home, so both refusals have
        # stopped being true and are DELETED rather than reworded (B14 rule
        # 33). **Asserting their ABSENCE is what makes their return RED** —
        # hard-won law 2's mirror is a refusal outliving the thing it refused.
        assert result.unavailable == ()
        # And the register row the first of them said did not exist.
        assert result.remittance_id != ""
        assert models.TaxRemittance.objects.filter(
            pk=result.remittance_id, journal_entry_id=result.entry_id
        ).exists()


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 / TC-7 — the refusals and the replay
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_014_tc6__a_remittance_may_not_debit_an_account_outside_the_2200_series(
    brazos, dana
):
    """The disaster this refusal prevents: a remittance keyed against 4100 would
    drain REVENUE, balance perfectly, pass every trigger, and be findable only by
    someone reading the trial balance line by line.

    B5 line 74 ❄️ signs the SERIES — *"2200-series Tax payable per authority"* —
    so that half is law and this refuses everything else.
    """
    with tenant_ctx(brazos):
        the_four_authorities(brazos, dana)
        revenue = models.LedgerAccount.objects.get(tenant=brazos, code="4100")
        assert not chart.is_tax_payable_code(revenue.code)

        with pytest.raises(journal.JournalActionError):
            journal.record_tax_remittance(
                tax_account_id=revenue.id,
                period_start=JULY_START,
                period_end=JULY_END,
                amount=LE3_STATE_REMIT_NOW,
                basis=journal.BASIS_BILLED,
                confirmation_ref=CONFIRMATION,
                entry_date=REMITTED_ON,
                posted_at=REMITTED_AT,
                actor=dana,
            )
        assert not models.JournalEntry.objects.filter(
            tenant=brazos, source_type="remittance"
        ).exists()


def test_us_led_014_tc6b__float_amounts_bad_bases_and_backwards_periods_are_refused(brazos, dana):
    """CLAUDE.md rule 2 (money is never a float), BR-LED-002 (the basis is one of
    two ruled values), and a period that runs backwards names no period.

    Each is refused rather than coerced: a float converted here would hide the
    place money became binary, and a defaulted basis would be wrong for half of
    LE-3's authorities.
    """
    with tenant_ctx(brazos):
        _accounts, authorities = the_four_authorities(brazos, dana)
        state = authorities["2200-01"].id
        common = {
            "tax_account_id": state,
            "period_start": JULY_START,
            "period_end": JULY_END,
            "basis": journal.BASIS_COLLECTED,
            "confirmation_ref": CONFIRMATION,
            "entry_date": REMITTED_ON,
            "posted_at": REMITTED_AT,
            "actor": dana,
        }
        with pytest.raises(journal.JournalActionError):
            journal.record_tax_remittance(**{**common, "amount": 13.87})
        with pytest.raises(journal.JournalActionError):
            journal.record_tax_remittance(**{**common, "amount": Decimal("0")})
        with pytest.raises(journal.JournalActionError):
            journal.record_tax_remittance(
                **{**common, "amount": LE3_STATE_REMIT_NOW, "basis": "accrual"}
            )
        with pytest.raises(journal.JournalActionError):
            journal.record_tax_remittance(
                **{
                    **common,
                    "amount": LE3_STATE_REMIT_NOW,
                    "period_start": JULY_END,
                    "period_end": JULY_START,
                }
            )
        assert not models.JournalEntry.objects.filter(
            tenant=brazos, source_type="remittance"
        ).exists()


def test_us_led_014_tc7__the_same_remittance_twice_is_one_entry_never_a_double_drain(brazos, dana):
    """US-LED-014 TC-7 verbatim: *"The same remittance recorded twice for the
    same authority+period+amount → second attempt surfaces the existing row — no
    silent double-drain."*

    Authority + period + AMOUNT is the identity, which is TC-7's own wording.
    The amount is in the key deliberately: a second, DIFFERENT payment against
    the same authority and period is a lawful partial remittance and must post,
    while the double-clicked identical one must not.
    """
    with tenant_ctx(brazos):
        _accounts, authorities = the_four_authorities(brazos, dana)
        state = authorities["2200-01"].id
        common = {
            "tax_account_id": state,
            "period_start": JULY_START,
            "period_end": JULY_END,
            "basis": journal.BASIS_COLLECTED,
            "confirmation_ref": CONFIRMATION,
            "entry_date": REMITTED_ON,
            "posted_at": REMITTED_AT,
            "actor": dana,
        }
        first = journal.record_tax_remittance(**common, amount=LE3_STATE_REMIT_NOW)
        second = journal.record_tax_remittance(**common, amount=LE3_STATE_REMIT_NOW)

        assert first.created is True
        assert second.created is False
        assert second.entry_id == first.entry_id
        assert (
            models.JournalEntry.objects.filter(tenant=brazos, source_type="remittance").count() == 1
        )

        window = {"start": JULY_START, "end": date(2026, 8, 31)}
        row = next(
            r for r in reporting.remittance_by_authority(**window)["rows"] if r.code == "2200-01"
        )
        assert row.remitted == LE3_STATE_REMIT_NOW, "drained once, not twice"

        # …and a DIFFERENT amount for the same authority + period is a lawful
        # partial remittance, so it posts.
        third = journal.record_tax_remittance(**common, amount=Decimal("0.50"))
        assert third.created is True
        row = next(
            r for r in reporting.remittance_by_authority(**window)["rows"] if r.code == "2200-01"
        )
        assert row.remitted == LE3_STATE_REMIT_NOW + Decimal("0.50")


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 — isolation
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_us_led_014_tc8__authorities_and_liabilities_never_cross_tenants(
    brazos, dana, lonestar, erin
):
    """US-LED-014 TC-8: *"Its authorities/liability only (RLS; tax_jurisdictions
    tenant-scoped per r6.5)."*"""
    with tenant_ctx(brazos):
        _accounts, authorities = the_four_authorities(brazos, dana)
        assert (
            reporting.remittance_by_authority(start=JULY_START, end=JULY_END)["totals"]["billed"]
            == WE1_TAX
        )
    with tenant_ctx(lonestar):
        theirs = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        assert theirs["rows"] == ()
        assert theirs["totals"]["billed"] == ZERO
        # Brazos Bend's own authority account reaches nothing from in here.
        with pytest.raises(journal.JournalActionError):
            journal.record_tax_remittance(
                tax_account_id=authorities["2200-01"].id,
                period_start=JULY_START,
                period_end=JULY_END,
                amount=LE3_STATE_REMIT_NOW,
                basis=journal.BASIS_COLLECTED,
                confirmation_ref=CONFIRMATION,
                entry_date=REMITTED_ON,
                posted_at=REMITTED_AT,
                actor=erin,
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-014@e3b0c44 (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md US-LED-014 §1/§3/§4/§7 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-3 · 04-docs/05-modules/09-ledger/07-pre-session-model.md §5 · 04-docs/02-decisions/05-golden-tests.md line 74 ❄️ · 12-governance/02-decision-log.md 2026-08-11 BR-BIL-069 + OQ-143)
# generated: 2026-08-11 by Eng-Lead (W5 ledger reporting lane)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: the collected-basis column was proved to BITE — a variant returning the BILLED figure in the collected column was written, RUN and seen to fail TC-1 before the refusing version was trusted. ⚠ **TC-1 WAS AMENDED 2026-09-02 (CR-060 C19 / task T7d): the column is PRODUCED now and the refusal is retired, and the case still bites on exactly the same failure — billed's number in collected's column — because on this fixture nothing is paid and collected is a real 0.00 against billed 47.38**
# exceptions: TC-1's collected basis is asserted ABSENT rather than equal to
#         20.97: an `allocations` row carries no line class (OQ-129) and there is
#         no signed partial-coverage apportionment, so the figure is not
#         derivable — the OQ this lane minted is the route to making it one ·
#         TC-2's per-authority basis is asserted None: the setting has no table
#         (r13 #3) · TC-5's RECEIPT half asserts a REFUSAL, since BR-LED-019's
#         attachment has no column and no storage seam · the filing-history
#         TABLE is not exercised at all — `tax_remittances` does not exist and
#         the trail asserted here is the entry memo plus the audit row
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
