# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 tasks T6c and T6d — the two rows the T6 settlement lane
#           handed on by name (`cost_capture.SETTLEMENT_INHERITS_T6C` and
#           `…_T6D`) and deliberately did not build.
# Story:    US-LED-021 (the cost section of the accounting export — TC-1's five
#           rows, TC-7's register-derived label) · US-LED-004 (the S36 tie-out
#           panel and its release blocker)
#           Screens: S42 · S43 (the export) · S36 (the tie-out panel)
# Rules:    BR-LED-039 (the payable side rides the SAME batch as the receivable
#           side) · BR-LED-007 (control = register; ANY drift = red flag +
#           release blocker) · BR-LED-028 (AMENDED 2026-09-02 — a settlement
#           posts DR cost / CR cash) · BR-REP-001 (every money figure labels
#           its basis) · BR-REP-002 (a read model, never a side-maintained
#           number) · CLAUDE.md rule 2 (money 4 dp, display 2) · rule 4
#           (financial immutability) · rule 5 (only the posting service writes
#           journal lines)
# Golden:   LE-1 — July's signed trial balance **598.69 = 598.69**.
#           LE-11 — nine captured July purchases, **$51,902.50 USD**, none of
#           which carries a `paid_on`, so every signed figure in this file is
#           the one already in the workbook.
#           LE-14 — July → QuickBooks: LE-5's receivable rows PLUS the five cost
#           rows summing $51,902.50.
# ───────────────────────────────────────────────────────
"""A settled purchase must leave the utility ONCE, and a drift must be visible.

════════════════════════════════════════════════════════════════════════════
T6c — THE SAME MONEY WAS LEAVING TWICE, AND THE LABEL SAID OTHERWISE
════════════════════════════════════════════════════════════════════════════
The accounting export carries two sections in ONE batch under one content hash
(BR-LED-039). The receivable section is derived from `reporting.trial_balance`;
the cost section is summed straight off the captured supplier-invoice register.

While a capture posted nothing those two could not overlap, and the section's
own label said so in as many words: *"these rows are NOT in the trial balance
and this total MUST NOT be added to the balanced footer beside it"*.

**CR-060 T6 landed on 2026-09-02 and made that sentence false.** A settled
purchase posts `DR cost / CR cash` through the one posting service, so it is in
the trial balance — and the cost section went on summing it as well. Export the
month and the ERP is handed the same $1,240.00 twice, once as a journal-derived
5110 debit and once as a register row telling the reader it is not in the books.

`test_..._red_before_green__…` below is the case that was PROVED RED first, and
its failure is quoted in the defect row and in this file's trailer.

**THE FIX IS SUBTRACTION, NOT RE-DERIVATION.** Re-deriving the settled rows out
of `journal_lines` and marking them journal-derived would put them in the batch
twice over — the summary section already carries them. And it would not even be
the same batch: a July purchase paid on 4 August books into AUGUST, so its books
and its register row are in two different export windows. So the register
section carries what is still ONLY in the register, and it STATES what it left
out, with the reason.

════════════════════════════════════════════════════════════════════════════
T6d — COST IS THE FOURTH THING THAT CAN DRIFT
════════════════════════════════════════════════════════════════════════════
`tie_out.py` proves three controls against their registers and blocks a release
on any drift. With settlement posting live there is a fourth pair: what the
supplier register says was settled, against what the books hold from those
settlements. Nothing compared them, so nothing could surface a divergence.

`_refuse_if_settled` (OQ-1350, MINTED not answered) already refuses the ordinary
edit path, so the two can only diverge through a write that goes round the
service — which is exactly the failure mode a tie-out exists to catch, and the
same posture the AR row takes. The drift case below therefore writes through the
queryset on purpose.

════════════════════════════════════════════════════════════════════════════
LAW 14 — WHAT MUST BE RUN ON POSTGRESQL
════════════════════════════════════════════════════════════════════════════
Every case here posts through `posting.post`, which the ledger's own triggers
guard, and the export cases run inside a closed period. The whole file was run
against a real PostgreSQL 16 as well as the default in-memory SQLite suite; the
command is in the trailer.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import close, cost_capture, exports, tie_out
from apps.ledger import models as ledger_models

from tests.cost_of_service_fixtures import (
    JULY_CLOSED_AT,
    JULY_END,
    JULY_START,
    LE11_REGISTER_TOTAL,
    LE14_COST_ROWS,
    LE14_QBO_REFS,
    capture_le11_month,
    enable_le11_services,
    with_monthly_fiscal_year,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: CI-1 — City of Rosenberg bulk water, 400,000 gal, **$1,240.00** to 5110.
#: The same purchase the T6 lane settled, so the two files talk about one row.
CI1 = "RS-2607-0141"
CI1_AMOUNT = Decimal("1240.00")

#: Paid INSIDE July, so the settlement entry books into July and lands in the
#: very window the export reads. A purchase paid in August books into August and
#: is the harder, quieter version of the same double-count — the money leaves in
#: two different batches — and is asserted separately below.
PAID_IN_JULY = date(2026, 7, 28)
PAID_IN_AUGUST = date(2026, 8, 4)
SETTLED_AT = datetime(2026, 8, 4, 15, 5, tzinfo=dt_timezone.utc)


def july_captured(tenant, clerk, *, refs=True):
    """LE-11's nine purchases and the QBO refs Norma sets. NOT closed — the
    settlement has to post into an OPEN July for the same-window case."""
    admin = staff_actor(tenant, "system_admin", f"setup-t6c-{tenant.subdomain}@brazos.test")
    with_monthly_fiscal_year(admin)
    enable_le11_services(admin)
    captured = capture_le11_month(clerk)
    if refs:
        for code, ref in LE14_QBO_REFS.items():
            ledger_models.LedgerAccount.objects.filter(tenant=tenant, code=code).update(
                qbo_ref=ref
            )
    return captured, admin


def close_july(admin):
    close.close_period(
        admin,
        period_start=JULY_START,
        period_end=JULY_END,
        closed_at=JULY_CLOSED_AT,
        reason="the deposit register is still being matched",
    )


def _summary_amount(preview, code):
    """What the RECEIVABLE (journal-derived) section carries for one GL code."""
    return sum(
        (row.debit - row.credit for row in preview["rows"] if row.code == code),
        Decimal("0"),
    )


def _register_amount(preview, code):
    """What the register-derived cost section carries for one GL code."""
    return sum(
        (row["amount"] for row in preview["cost_section"]["rows"] if row["code"] == code),
        Decimal("0"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# T6c — a settled purchase leaves ONCE
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6c_red_before_green__a_settled_purchase_is_not_in_both_sections_of_one_batch(
    brazos, marcus
):
    """**THE CASE THIS ROW EXISTS FOR.** CI-1 is settled on 28 July, so its
    `DR 5110 1,240.00 / CR 1000 1,240.00` is in July's trial balance. Export
    July: the receivable section carries the 1,240.00 debit on 5110, and the
    register section must NOT carry it a second time.

    **PROVED RED FIRST**, before `cost_section` learned about settlement:

        assert Decimal('3100.00') == Decimal('1860.00')

    — the register section still summed all five July water purchases at
    3,100.00 while the books already held 1,240.00 of them, so QuickBooks was
    handed 4,340.00 of purchased water against 3,100.00 actually bought.
    """
    with tenant_ctx(brazos):
        captured, admin = july_captured(brazos, marcus)
        cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )
        close_july(admin)
        preview = exports.export_preview(
            period_start=JULY_START, period_end=JULY_END, target=ledger_models.EXPORT_QBO
        )

    # The books hold it — that is what T6 built, and it is not in question here.
    assert _summary_amount(preview, "5110") == CI1_AMOUNT
    # And the register section must have stepped back by exactly that much.
    assert _register_amount(preview, "5110") == LE14_COST_ROWS["5110"] - CI1_AMOUNT
    # Together, ONE 3,100.00 of purchased water leaves the utility, not 4,340.00.
    assert _summary_amount(preview, "5110") + _register_amount(preview, "5110") == (
        LE14_COST_ROWS["5110"]
    )


def test_cr060_t6c__the_section_states_what_it_left_out_and_why(brazos, marcus):
    """A row that silently vanishes from a total a clerk reconciled last month
    is worse than one that leaves loudly. The section names the settled count
    and the settled total, so `register + settled` is still LE-11's $51,902.50.
    """
    with tenant_ctx(brazos):
        captured, admin = july_captured(brazos, marcus)
        cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )
        close_july(admin)
        preview = exports.export_preview(
            period_start=JULY_START, period_end=JULY_END, target=ledger_models.EXPORT_QBO
        )
    section = preview["cost_section"]

    assert section["settled"]["count"] == 1
    assert section["settled"]["total"] == CI1_AMOUNT
    assert section["cost_total"] == LE11_REGISTER_TOTAL - CI1_AMOUNT
    assert section["cost_total"] + section["settled"]["total"] == LE11_REGISTER_TOTAL
    # BR-REP-001 — the settled block labels its own basis, and it is the books.
    assert section["settled"]["source"] == exports.COST_SECTION_SOURCE_JOURNAL
    assert section["source"] == exports.COST_SECTION_SOURCE_REGISTER


def test_cr060_t6c__the_label_no_longer_claims_every_cost_is_out_of_the_books(brazos, marcus):
    """Hard-won law 1 — a comment claiming a guarantee is not the guarantee, and
    a LABEL claiming one is worse because a finance officer reads it.

    The old sentence said, of the whole section, *"these rows are NOT in the
    trial balance"*. That is now a claim about the rows the section CARRIES, and
    the label has to be readable as such by the person holding the batch.
    """
    label = exports.COST_SECTION_LABEL
    # It still says what it is: the rows here are the register's.
    assert "REGISTER-DERIVED" in label
    # And it no longer promises that a settled cost is absent from the books.
    assert "settled" in label.lower()
    # The expiry it used to name — "the day a supplier-payment path ships" — has
    # been overtaken: the boundary moved by a different route (a paid-on date),
    # and a label naming a day that will never come is a stale claim.
    assert "supplier-payment path" not in label


def test_cr060_t6c__nothing_settled_means_nothing_moves(brazos, marcus):
    """**NO SIGNED FIGURE MOVES.** LE-11's nine purchases carry no `paid_on`, so
    on the fixture every other test in the suite runs against, the section is
    byte-for-byte what US-LED-021 TC-1 signed: five rows, $51,902.50, and a
    settled block that is honestly empty rather than absent.
    """
    with tenant_ctx(brazos):
        _captured, admin = july_captured(brazos, marcus)
        close_july(admin)
        preview = exports.export_preview(
            period_start=JULY_START, period_end=JULY_END, target=ledger_models.EXPORT_QBO
        )
    section = preview["cost_section"]

    assert {row["code"]: row["amount"] for row in section["rows"]} == LE14_COST_ROWS
    assert section["entries"] == 5
    assert section["cost_total"] == LE11_REGISTER_TOTAL
    assert section["settled"]["count"] == 0
    assert section["settled"]["total"] == Decimal("0")


def test_cr060_t6c__a_purchase_paid_next_month_leaves_july_too(brazos, marcus):
    """The quieter half of the same defect, and the reason the fix is subtraction
    rather than re-derivation.

    A July purchase paid on 4 August books into AUGUST. Its register row is in
    JULY's window. So without this change the money leaves in two different
    batches, months apart, and no single payload shows the duplication at all.
    """
    with tenant_ctx(brazos):
        captured, admin = july_captured(brazos, marcus)
        cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_AUGUST, settled_at=SETTLED_AT
        )
        close_july(admin)
        preview = exports.export_preview(
            period_start=JULY_START, period_end=JULY_END, target=ledger_models.EXPORT_QBO
        )

    # July's books do NOT carry it — it booked into August.
    assert _summary_amount(preview, "5110") == Decimal("0")
    # And July's register section does not carry it either, because it is in the
    # books SOMEWHERE and the register section is what is only in the register.
    assert _register_amount(preview, "5110") == LE14_COST_ROWS["5110"] - CI1_AMOUNT
    assert preview["cost_section"]["settled"]["count"] == 1


def test_cr060_t6c__drill_back_answers_for_the_rows_the_section_carries(brazos, marcus):
    """TC-4's discipline — every exported figure explains itself — applied to a
    section that now carries fewer rows. Drilling into 5110 must return the four
    purchases still in the register, not the five it used to.

    It also stops riding `posting_shape_is_not_ruled`: that code was superseded
    on 2026-08-16 when OQ-200 was closed, was removed from `cost_section` then
    and was left on the drill-back — a screen calling a ruled question open.
    """
    with tenant_ctx(brazos):
        captured, admin = july_captured(brazos, marcus)
        cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )
        close_july(admin)
        drill = exports.cost_drill_back(
            code="5110", period_start=JULY_START, period_end=JULY_END
        )

    assert len(drill["purchases"]) == 4
    assert CI1 not in {row["reference"] for row in drill["purchases"]}
    assert drill["total"] == LE14_COST_ROWS["5110"] - CI1_AMOUNT
    assert exports.COST_SHAPE_NOT_RULED not in drill["problems"]


# ═══════════════════════════════════════════════════════════════════════════
# T6d — the fourth tie-out row
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t6d__cost_is_the_fourth_row_and_agrees_on_a_book_with_no_settlements(
    brazos, marcus
):
    """LE-11 captured and nothing settled: the register's settled total is 0.00
    and the books hold 0.00 of settlement cost. **AGREED, and never
    UNVERIFIABLE** — nothing was unreadable, there was simply nothing to read,
    which is the same distinction `_tax_row` already draws for a utility that
    bills no tax.
    """
    with tenant_ctx(brazos):
        july_captured(brazos, marcus)
        result = tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)

    rows = {row.subledger: row for row in result["rows"]}
    assert tie_out.SUBLEDGER_COST in rows
    cost = rows[tie_out.SUBLEDGER_COST]
    assert cost.state == tie_out.STATE_AGREED
    assert cost.gl == Decimal("0")
    assert cost.register == Decimal("0")
    assert cost.drift == Decimal("0")
    assert cost.blocks_release is False


def test_cr060_t6d__a_settled_purchase_puts_the_same_figure_on_both_sides(brazos, marcus):
    """CI-1 settled: the register says $1,240.00 was paid, the books hold
    $1,240.00 of debit on 5110 from that settlement. The row agrees, and it
    agrees for the RIGHT reason — both sides are derived, neither is stored.
    """
    with tenant_ctx(brazos):
        captured, _admin = july_captured(brazos, marcus)
        cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )
        result = tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)

    cost = {row.subledger: row for row in result["rows"]}[tie_out.SUBLEDGER_COST]
    assert cost.gl == CI1_AMOUNT
    assert cost.register == CI1_AMOUNT
    assert cost.state == tie_out.STATE_AGREED
    assert result["release_blocked"] is False


def test_cr060_t6d__a_register_that_moved_without_the_books_goes_red(brazos, marcus):
    """**OQ-1350's argument, made visible.** `_refuse_if_settled` stops the
    ordinary edit path, so this writes through the queryset — a bypass of the
    service, which is precisely what a tie-out is for (`_ar_row` takes the same
    posture about a line posted with no account).

    The register now says $1,260.00 was paid and the books hold $1,240.00.
    Before this row existed that divergence surfaced NOWHERE.
    """
    with tenant_ctx(brazos):
        captured, _admin = july_captured(brazos, marcus)
        cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )
        cost_capture.models.SupplierInvoice.objects.filter(
            pk=captured[CI1]["id"]
        ).update(amount=Decimal("1260.00"))
        result = tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)

    cost = {row.subledger: row for row in result["rows"]}[tie_out.SUBLEDGER_COST]
    assert cost.state == tie_out.STATE_DRIFTING
    assert cost.gl == CI1_AMOUNT
    assert cost.register == Decimal("1260.00")
    assert cost.drift == Decimal("-20.00")
    assert cost.blocks_release is True
    assert result["release_blocked"] is True
    assert tie_out.SUBLEDGER_COST in result["drifting"]
    # BR-LED-007's row must say WHICH path is behind rather than accuse the
    # books, exactly as the deposit row does.
    assert any(cause["code"] == tie_out.CAUSE_SETTLED_COST_DIVERGED["code"] for cause in cost.causes)


def test_cr060_t6d__the_handoff_constants_now_describe_a_closed_row(brazos, marcus):
    """The T6 lane named both inheritances as constants so *"we told somebody"*
    was a thing a grep could find. Both are closed here, and the sentence that
    said the export label was still the register-derived one has to stop being
    true — otherwise the next reader inherits a hand-off that already happened.
    """
    assert "T6c" in cost_capture.SETTLEMENT_INHERITS_T6C
    assert "T6d" in cost_capture.SETTLEMENT_INHERITS_T6D
    # Both rows are built, and each constant says so with its landing date.
    assert "BUILT" in cost_capture.SETTLEMENT_INHERITS_T6C
    assert "BUILT" in cost_capture.SETTLEMENT_INHERITS_T6D


def test_cr060_t6d__the_cost_row_is_tenant_scoped_like_every_other(brazos, lonestar, marcus, dana):
    """US-LED-004 TC-6's isolation, extended to the new row. Lone Star settles
    nothing, so its cost row must read 0.00 whatever Brazos Bend has paid — a
    tie-out that leaked across tenants would report drift on a clean book.
    """
    with tenant_ctx(brazos):
        captured, _admin = july_captured(brazos, marcus)
        cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )
    with tenant_ctx(lonestar):
        result = tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)

    cost = {row.subledger: row for row in result["rows"]}[tie_out.SUBLEDGER_COST]
    assert cost.gl == Decimal("0")
    assert cost.register == Decimal("0")
    assert cost.state == tie_out.STATE_AGREED


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060-T6c-T6d@export-and-tie-out (the authorities this file was
#         written from, in order: 12-governance/11-change-requests.md CR-060 §12
#         rows T6c and T6d verbatim, §7 C1, §8a's W1/W7 screen notes and §9's
#         endpoint delta · 12-governance/02-decision-log.md — the PO ruling of
#         2026-09-02 that made a settlement post, and the row correcting the
#         52,501.19 projection to a measured 52,351.19 ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-004/007/028/
#         035/039 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-1,
#         LE-11, LE-14 · apps/ledger/cost_capture.SETTLEMENT_INHERITS_T6C and
#         _T6D, read from the code)
# generated: 2026-09-02 by the CR-060 T6c/T6d lane
# checklist: A✔ B✔ C✔ D✔ E✔(the S43 settled-cost disclosure and the S36 fourth tie-out row, both with catalogue strings in all eleven locales) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: PROVED RED BEFORE GREEN, on REAL PostgreSQL 16 both times.
#         T6c: `assert Decimal('3100.000000') == (Decimal('3100.00') -
#         Decimal('1240.00'))` — the register section summed all five July water
#         purchases while the books already held 1,240.00 of them, so one batch
#         carried 4,340.00 of purchased water against 3,100.00 bought (DEF-3380).
#         T6d: the drift row was sabotaged to compare the control against itself
#         (`register = gl`) and went `assert 'agreed' == 'drifting'` — a check
#         that cannot fail reads as protection and is none.
# exceptions: (1) the DRIFT case writes through the queryset ON PURPOSE.
#         `cost_capture._refuse_if_settled` refuses the ordinary edit path with
#         NotImplementedError(OQ-1350), so a divergence can only arrive by a
#         write that goes round the service — which is what a tie-out is for,
#         and the posture `_ar_row` already takes about a line posted with no
#         account · (2) NO SIGNED FIGURE MOVES: LE-11's nine purchases carry no
#         `paid_on`, so US-LED-021 TC-1's five rows and $51,902.50 are asserted
#         here unchanged · (3) `tests/test_us_led_016_export.py::…tc6…` fails on
#         PostgreSQL for a reason that predates this lane and is DEF-3381 — its
#         simulated posting bypass is refused by the append-only trigger, so the
#         drift release-blocker has only ever been proved on SQLite
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
