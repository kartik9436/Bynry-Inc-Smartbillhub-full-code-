# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C19 / task T7d — the class breakdown on the allocation row.
#           Screens: S41 (the dual-basis remittance table) · S36
# Rules:    BR-PAY-010 (the within-invoice class order — a TENANT SETTING since
#           2026-08-12) · BR-PAY-031 (a reapply is reversing rows plus new rows,
#           never an edit) · BR-PAY-038 (the fourth class is tenant-defined) ·
#           BR-LED-002 (BOTH remittance bases always computed) · BR-LED-794
#           (how one bill's collected tax is split across its authorities —
#           NEW 2026-09-02) · CLAUDE.md rules 1, 2, 4, 7
# Ruling:   OQ-129 CLOSED 2026-08-16 · OQ-174 CLOSED 2026-08-12. THE TWO
#           DISAGREE, and CR-060 C19 rules that the disposition is to RECORD the
#           breakdown rather than pick a winner.
# Golden:   LE-3 — WE-1's 247.87 = 226.90 revenue + 20.97 tax, split State
#           13.87 · County 2.22 · City 4.44 · PUC 0.44. Every figure is
#           transcribed from `tests/ledger_le_fixtures.py`, none computed here.
# ───────────────────────────────────────────────────────
"""Which kinds of charge a payment met, written down — and the tax return that
could not be produced until it was.

════════════════════════════════════════════════════════════════════════════
THE WORKED FIGURE THIS FILE PINS — the one a reviewer signs (CR-060 T19)
════════════════════════════════════════════════════════════════════════════
WE-1 is a signed bill: **247.87 = 226.90 of revenue + 20.97 of tax**, and the
tax is four authorities' — **State 13.87 · County 2.22 · City 4.44 · PUC 0.44**.

  * **Paid in full.** The allocation records `usage_base 226.90` and
    `taxes 20.97`, and the remittance report's collected column reads
    **20.97** — LE-3's signed figure, produced rather than refused.
  * **Paid 150.00, shipped order (usage and base first, taxes second).** The
    money never reaches the tax lines, so the breakdown records
    `usage_base 150.00` and no tax row at all, and collected tax is **0.00**.
  * **Paid 150.00, tax first** — the order `OQ-174` closed on, and a tenant may
    set it. The breakdown records `taxes 20.97` and `usage_base 129.03`, and
    collected tax is **20.97**. (Two tests, on the same tenant in two
    rolled-back databases: an order is a tenant's own and running both inside
    one book would sum them into one report.)
  * **THE SPREAD IS 20.97 ON ONE BILL**, which is the whole reason the question
    was raised — and **this change adjudicates neither ruling.** Whatever order
    a tenant set is what their money walked, and it is written down afterwards.
  * **A bounced cheque takes it back.** The reversal writes the negated
    breakdown from the original's own rows, so collected tax nets to **0.00**
    and the utility does not remit on money that came back.
  * **Per authority, BR-LED-794.** A bill's collected tax is split across the
    authorities THAT BILL charged in proportion to what each was billed on it.
    On full coverage the split is the identity — State gets exactly **13.87** —
    and on the 150.00 tax-first case State gets 13.87 too, because the whole
    tax was met.

════════════════════════════════════════════════════════════════════════════
PROVED RED BEFORE GREEN — THREE GUARDS, EACH MEASURED, NO LIVE FILE MUTATED
════════════════════════════════════════════════════════════════════════════
Every sabotage was applied through `monkeypatch`, so no shipped file was edited
to produce a failure (DEF-3101's discipline). Quoted as seen:

  **1 · The child rows not written at allocation time.** The collected column
  went straight back to what it was before this change — `None` — while the
  screen beside it showed a billed figure. Measured:
  `AssertionError: assert None == Decimal('20.97')`. That is the bug this task
  exists to close, reproduced on demand.

  **2 · The reversal's negated mirror removed.** A bounced cheque then left its
  collected tax standing: after the reversal the report still read **20.97**
  and a utility would have remitted tax on money that came back. Measured:
  `AssertionError: assert Decimal('20.97') == Decimal('0')`.

  ⚠ **AND THE SAME CASE FOUND A REAL DEFECT IN THIS LANE'S OWN CODE, WHICH IS
  WHY IT IS WRITTEN DOWN RATHER THAN QUIETLY FIXED.** The first draft of
  `payments.selectors.collected_by_class_for_invoices` filtered on
  `payment__status = cleared`, which reads as obviously right and is not: a
  reversal writes a **NEW payment row at status `reversed`**, so its negative
  breakdown was filtered out while the original's positive one stayed, and the
  report read **20.97 collected on money that had come back** — the identical
  symptom to the deliberate sabotage above, from a bug rather than from a
  scalpel. Nothing had shipped, so no defect row is owed; the filter now asks
  what it means (*money that reached the bank in this window*, which
  `cleared_at` carries) and excludes only `processing` and `failed`.

  **3 · The apportionment replaced by an even split across the four
  authorities.** State's share of a fully-covered WE-1 became **5.2425**
  instead of **13.87** — four returns wrong in the same month, each by a
  different amount, none of them obviously so. Measured:
  `AssertionError: assert Decimal('5.24') == Decimal('13.87')`.

════════════════════════════════════════════════════════════════════════════
POSTGRESQL — CLAUDE.md hard-won law 14
════════════════════════════════════════════════════════════════════════════
`allocation_classes` carries an append-only trigger and a tenant RLS policy
(`payments/0016`), and both are PostgreSQL-only: SQLite has neither, so the
immutability case below carries `requires_postgres` and SKIPS on the default
suite rather than passing vacuously.

**RUN, AND MEASURED — and the arithmetic is the point.** On the SQLite suite this
file reports **9 passed and 1 SKIPPED**; on PostgreSQL 16 it runs beside the two
ratified suites it amends (`test_us_led_014_remittance.py` and
`test_us_led_ledger_api.py`) for **53 passed and NO skips at all**. The case that
changes is TC-9, the append-only trigger, and it is the whole reason this law
exists: a green SQLite run over a database rule SQLite does not have proves
nothing. The command, verbatim:

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL=postgres://... SBH_TEST_DB_NAME=test_sbh_cr060b \\
    JOBS_EAGER=false pytest tests/test_cr060_t7d_allocation_classes.py --create-db

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE DOES NOT TOUCH
════════════════════════════════════════════════════════════════════════════
**No ❄️ frozen figure moves.** 247.87, 226.90, 20.97 and the four authority
amounts are `tests/ledger_le_fixtures.py`'s transcriptions of LE-3 and are
asserted here, never recomputed. B4 and B5 are not opened. The allocation ORDER
and its default are untouched — this file sets a non-default order only by
passing `class_order` explicitly, which is the tenant setting BR-PAY-010 already
ships.
"""

import uuid
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from django.db import connection

from apps.ledger import models as ledger_models
from apps.ledger import payments_seam, reporting
from apps.payments import allocation as payments_allocation
from apps.payments import models as payment_models
from apps.payments import reversal as payments_reversal
from apps.payments import selectors as payment_selectors
from apps.payments import services as payment_services

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE1_WE1_BILL,
    LE3_AUTHORITIES,
    WE1_REVENUE,
    WE1_TAX,
    ensure_authority_accounts,
    gl,
    line,
    a_request,
)
from tests.test_w3_billing_models import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    marcus,
    staff_actor,
    tenant_ctx,
)

from apps.ledger import posting as ledger_posting

pytestmark = pytest.mark.django_db

requires_postgres = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="RLS and the append-only trigger are PostgreSQL-only (CLAUDE.md law 14) — "
    "SQLite would pass this vacuously, which is worse than skipping it",
)

UTC = dt_timezone.utc
BILLED_ON = date(2026, 7, 15)
POSTED_AT = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
CLEARED_AT = datetime(2026, 7, 20, 16, 0, tzinfo=UTC)
REVERSED_AT = datetime(2026, 7, 25, 11, 0, tzinfo=UTC)

PARTIAL = Decimal("150.00")
#: 150.00 met against 226.90 of revenue leaves nothing for the tax lines.
PARTIAL_USAGE_BASE_SHIPPED_ORDER = Decimal("150.00")
#: Tax first: the whole 20.97, then 129.03 of the revenue.
PARTIAL_USAGE_BASE_TAX_FIRST = PARTIAL - WE1_TAX  # 129.03

USAGE_BASE = payments_allocation.CLASS_USAGE_BASE
TAXES = payments_allocation.CLASS_TAXES

TAX_FIRST_ORDER = (TAXES, USAGE_BASE)


def we1_bill(tenant, account):
    """WE-1 as an ISSUED bill row — created through billing's ORM for the reason
    `tests/test_us_pay_001_record_payment.py` states: driving the whole issue
    path would put the rating engine into a payments test, and what this file is
    about is what happens to a bill AFTER it exists."""
    from apps.billing import models as billing_models

    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no="BL-2607-000001",
        status=billing_models.INVOICE_ISSUED,
        service_date=BILLED_ON,
        period_start=date(2026, 7, 1),
        period_end=JULY_END,
        due_date=date(2026, 8, 1),
        subtotal=WE1_REVENUE,
        tax_total=WE1_TAX,
        total=LE1_WE1_BILL,
        issued_at=datetime(2026, 7, 15, 9, 0, tzinfo=UTC),
    )


def a_composition_read(monkeypatch, bill):
    """Publish billing's PREFERRED read with WE-1's two classes.

    The seam resolves it BY NAME at call time, so this is exactly the state a
    deployment is in the day billing publishes it — the wiring, not a mock. Same
    helper, same reason, as `tests/test_us_pay_001_record_payment.py`.
    """
    from apps.billing import selectors as billing_selectors

    rows = [
        {
            "id": bill.pk,
            "number": bill.invoice_no,
            "total": LE1_WE1_BILL,
            "issued_on": BILLED_ON,
            "composition": {"usage_base": WE1_REVENUE, "taxes": WE1_TAX},
        }
    ]
    monkeypatch.setattr(
        billing_selectors, "issued_invoices_for_account", lambda _id: rows, raising=False
    )


def post_we1_to_the_authorities(tenant, account, bill, authorities):
    """WE-1's issue entry, keyed to the REAL invoice id.

    `source_id = bill.pk` is what lets `remittance_by_authority` tie the bill's
    authority credits to the allocation rows the payment wrote — the join the
    whole collected basis rests on, and the reason this fixture cannot use the
    LE-3 helper's synthetic key.
    """
    ar = gl(tenant, "1200", "asset")
    revenue = gl(tenant, "4100", "revenue")
    lines = [
        line(ar, ledger_models.SIDE_DEBIT, LE1_WE1_BILL, account_id=account.id),
        line(revenue, ledger_models.SIDE_CREDIT, WE1_REVENUE, account_id=account.id),
    ]
    for code, _name, amount in LE3_AUTHORITIES:
        lines.append(
            line(authorities[code], ledger_models.SIDE_CREDIT, amount, account_id=account.id)
        )
    ledger_posting.post(
        a_request(
            lines,
            key=f"invoice|{bill.pk}|issued",
            entry_date=BILLED_ON,
            source_id=bill.pk,
        )
    )


def a_payment(actor, account, amount, **overrides):
    values = dict(
        account_id=account.pk,
        amount=amount,
        posted_at=POSTED_AT,
        cleared_at=CLEARED_AT,
        confirmation="8842",
        idempotency_reference=uuid.uuid4(),
    )
    values.update(overrides)
    return payment_services.record_payment(actor, **values)


def class_rows(tenant):
    """`{line_class: amount}` summed over every allocation of this tenant."""
    out = {}
    for line_class, amount in payment_models.AllocationClass.objects.filter(
        tenant=tenant
    ).values_list("line_class", "amount"):
        out[line_class] = out.get(line_class, Decimal("0")) + amount
    return out


def a_world(monkeypatch, tenant, actor, account_no="ACC-1042"):
    # `an_account` is `tests/test_w3_billing_models`'s minimal row, for the
    # reason it states: driving customers' whole activation path would put that
    # story into this test. The PAYMENT and the REVERSAL below go through their
    # real services; only the surrounding cast is built directly.
    account = an_account(actor, tenant, account_no=account_no)
    bill = we1_bill(tenant, account)
    authorities = ensure_authority_accounts(tenant, actor)
    post_we1_to_the_authorities(tenant, account, bill, authorities)
    a_composition_read(monkeypatch, bill)
    return account, bill, authorities


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the rows exist, in the same transaction as their parent
# ═══════════════════════════════════════════════════════════════════════════
def test_t7d_tc1__a_full_payment_records_what_it_met(brazos, marcus, monkeypatch):
    """**usage_base 226.90 · taxes 20.97**, one child row each, hanging off the
    allocation. The figure was computed before today and had nowhere to live but
    a pruned audit payload."""
    with tenant_ctx(brazos):
        account, bill, _ = a_world(monkeypatch, brazos, marcus)
        result = a_payment(marcus, account, LE1_WE1_BILL)

        allocation = payment_models.Allocation.objects.get(tenant=brazos)
        children = {row.line_class: row.amount for row in allocation.classes.all()}

    assert result.applied == LE1_WE1_BILL
    assert children == {USAGE_BASE: WE1_REVENUE, TAXES: WE1_TAX}
    # The audit payload still carries it too — one `by_class` tuple, two
    # destinations, written in one transaction, so they cannot disagree.
    assert result.allocations[0]["by_class"]["taxes"] == str(WE1_TAX)


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — THE FIGURE: the collected column reads 20.97 instead of refusing
# ═══════════════════════════════════════════════════════════════════════════
def test_t7d_tc2__the_collected_basis_is_produced_not_refused(brazos, marcus, monkeypatch):
    """LE-3's signed **20.97**, in the column that answered `None` until today —
    and the old refusal is RETIRED rather than reworded (C19's own instruction).
    """
    with tenant_ctx(brazos):
        account, bill, _ = a_world(monkeypatch, brazos, marcus)
        a_payment(marcus, account, LE1_WE1_BILL)
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        codes = {gap["code"] for gap in report["unavailable"]}

    assert report["totals"]["billed"] == WE1_TAX
    assert report["totals"]["collected"] == WE1_TAX
    assert "tax_inside_a_cleared_payment_is_not_derivable" not in codes
    # Nothing was left unclassified, so the floor caveat does not fire either.
    assert report["totals"]["allocated_without_breakdown"] == Decimal("0")
    assert reporting.GAP_COLLECTED_IS_A_FLOOR["code"] not in codes


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — BR-LED-794: per authority, and on full coverage it is the identity
# ═══════════════════════════════════════════════════════════════════════════
def test_t7d_tc3__the_split_is_per_authority_and_exact_on_full_coverage(
    brazos, marcus, monkeypatch
):
    """State **13.87** · County **2.22** · City **4.44** · PUC **0.44** — each
    authority collected exactly what it was billed, because the bill was met in
    full. The apportionment is the identity here and that is the point: it can
    only ever divide money that came in."""
    with tenant_ctx(brazos):
        account, bill, _ = a_world(monkeypatch, brazos, marcus)
        a_payment(marcus, account, LE1_WE1_BILL)
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        by_code = {row.code: row for row in report["rows"]}

    for code, _name, amount in LE3_AUTHORITIES:
        assert by_code[code].billed == amount
        assert by_code[code].collected == amount
        assert by_code[code].outstanding_collected == amount  # nothing remitted yet
    assert sum(row.collected for row in report["rows"]) == WE1_TAX


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — THE 20.97 SPREAD: the same partial payment, two orders, two answers
# ═══════════════════════════════════════════════════════════════════════════
#
# **THIS IS THE PAIR THAT PROVES THE BREAKDOWN IS READ AND NOT ASSUMED.**
# 150.00 against WE-1 under the SHIPPED order collects 0.00 of tax; under *tax
# first* it collects the whole 20.97. Both are correct answers to different
# tenant settings, and the product now reports whichever actually happened
# instead of refusing to answer.
#
# Two tests rather than one, on the same tenant in two rolled-back databases: an
# allocation order is a tenant's own, and running both inside one book would sum
# two orders into one report and prove nothing about either.
def test_t7d_tc4a__the_shipped_order_collects_no_tax_from_a_partial_payment(
    brazos, marcus, monkeypatch
):
    """Usage and base first, taxes second — BR-PAY-010's shipped default. The
    150.00 is entirely absorbed by the 226.90 of revenue and never reaches the
    tax lines, so **0.00** of tax is collected and there is no tax row at all
    (a class that received nothing gets no row)."""
    with tenant_ctx(brazos):
        account, bill, _ = a_world(monkeypatch, brazos, marcus)
        a_payment(marcus, account, PARTIAL)
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        rows = class_rows(brazos)

    assert rows == {USAGE_BASE: PARTIAL_USAGE_BASE_SHIPPED_ORDER}
    # A REAL 0.00 — nothing provably collected — and never an absence.
    assert report["totals"]["collected"] == Decimal("0")
    assert all(row.collected == Decimal("0") for row in report["rows"])


def test_t7d_tc4b__tax_first_collects_the_whole_20_97_from_the_same_payment(
    brazos, marcus, monkeypatch
):
    """The order `OQ-174` closed on, which a tenant may set (BR-PAY-010). The
    same 150.00 meets all **20.97** of tax and then 129.03 of the revenue.

    The difference between this figure and TC-4a's is **20.97 on one bill** —
    the exact spread the question was raised over, now readable either way
    rather than refused. Neither ruling is overturned by that; both are simply
    answerable.
    """
    with tenant_ctx(brazos):
        account, bill, _ = a_world(monkeypatch, brazos, marcus)
        a_payment(marcus, account, PARTIAL, class_order=TAX_FIRST_ORDER)
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        rows = class_rows(brazos)
        by_code = {row.code: row for row in report["rows"]}

    assert rows[TAXES] == WE1_TAX
    assert rows[USAGE_BASE] == PARTIAL_USAGE_BASE_TAX_FIRST
    assert report["totals"]["collected"] == WE1_TAX
    # BR-LED-794 again: the whole tax was met, so every authority collected
    # exactly what it was billed and the apportionment is the identity.
    for code, _name, amount in LE3_AUTHORITIES:
        assert by_code[code].collected == amount
    # The spread, stated as arithmetic against TC-4a's zero.
    assert report["totals"]["collected"] - Decimal("0") == WE1_TAX


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — a bounced cheque takes its collected tax back with it
# ═══════════════════════════════════════════════════════════════════════════
def test_t7d_tc5__a_reversal_writes_the_negated_breakdown(brazos, marcus, monkeypatch):
    """The mirror is copied from the ORIGINAL's own rows and negated, never
    recomputed — what the payment met is already a recorded fact, and a second
    derivation would eventually disagree with the first.

    ⚠ **THIS CASE EARNED ITS KEEP BEFORE IT WAS EVER GREEN.** It failed on a
    real bug in this lane's own read — a `status == cleared` filter that dropped
    the reversing row, because a reversal's mirror is a NEW payment at status
    `reversed` — and the symptom was exactly the one a utility would meet:
    **20.97 of tax reported collected on a cheque that bounced.** The selector
    now filters on money that reached the bank rather than on one status word.
    """
    with tenant_ctx(brazos):
        account, bill, _ = a_world(monkeypatch, brazos, marcus)
        paid = a_payment(marcus, account, LE1_WE1_BILL)
        # A reversal is a System Admin's (BR-PAY-1070) — a clerk records money,
        # an admin unmakes it — so the actor changes here rather than the gate.
        admin = staff_actor(brazos, "system_admin", "nsf@brazosbendutilities.test")
        payments_reversal.reverse_payment(
            admin,
            payment_id=paid.payment_id,
            returned_on=REVERSED_AT,
            idempotency_reference=uuid.uuid4(),
        )
        totals = class_rows(brazos)
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)

    # The two sets of rows net to nothing — the money came back.
    assert totals[TAXES] == Decimal("0")
    assert totals[USAGE_BASE] == Decimal("0")
    assert report["totals"]["collected"] == Decimal("0")
    # And the originals are untouched: a correction is new rows (BR-PAY-031).
    assert payment_models.AllocationClass.objects.filter(tenant=brazos).count() == 4


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — the FLOOR is published, not absorbed
# ═══════════════════════════════════════════════════════════════════════════
def test_t7d_tc6__allocated_money_with_no_breakdown_is_reported_by_amount(
    brazos, marcus, monkeypatch
):
    """A bill whose composition billing cannot state is allocated by amount
    alone and carries no breakdown — the state EVERY allocation was in before
    today. The report says how much rather than quietly reporting a smaller
    collected figure as though it were the whole month."""
    with tenant_ctx(brazos):
        account, bill, _ = a_world(monkeypatch, brazos, marcus)
        # Billing states nothing: `_composition_from` returns () and the walk
        # allocates by amount, exactly as it does on B5 GT-7's shape.
        from apps.billing import selectors as billing_selectors

        monkeypatch.setattr(
            billing_selectors,
            "issued_invoices_for_account",
            lambda _id: [
                {
                    "id": bill.pk,
                    "number": bill.invoice_no,
                    "total": LE1_WE1_BILL,
                    "issued_on": BILLED_ON,
                }
            ],
            raising=False,
        )
        a_payment(marcus, account, LE1_WE1_BILL)
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        codes = {gap["code"] for gap in report["unavailable"]}

    assert payment_models.AllocationClass.objects.filter(tenant=brazos).count() == 0
    # A real 0.00: nothing PROVABLY collected. And the amount that could not be
    # classified is a number on the response.
    assert report["totals"]["collected"] == Decimal("0")
    assert report["totals"]["allocated_without_breakdown"] == LE1_WE1_BILL
    assert report["totals"]["allocations_without_breakdown"] == 1
    assert reporting.GAP_COLLECTED_IS_A_FLOOR["code"] in codes


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — the window is the CLEARING date, and a processing payment is not cash
# ═══════════════════════════════════════════════════════════════════════════
def test_t7d_tc7__the_window_is_the_posting_day_before_and_after_reconciliation(
    brazos, marcus, monkeypatch
):
    """`DEF-PAY-10321` — PO ruling 2026-10-21 (decision log *"Two CR-186
    follow-up rulings"*, item 2): the collected-tax basis counts `posted` +
    `cleared` by POSTING date. This case read *"only cleared payments count and
    the window is the clearing day"* until then.

    The PO's worked shape: money taken on the 20th (after the 15 Jul bill) and
    reconciled on the 22nd is collected on the 20th — before the reconciliation
    and after it — and never on the 22nd.
    """
    day_taken = date(2026, 7, 20)
    day_reconciled = date(2026, 7, 22)
    with tenant_ctx(brazos):
        account, bill, _ = a_world(monkeypatch, brazos, marcus)
        paid = a_payment(
            marcus,
            account,
            LE1_WE1_BILL,
            posted_at=datetime(2026, 7, 20, 15, 0, tzinfo=UTC),
            cleared_at=None,
        )
        row = payment_models.Payment.objects.get(pk=paid.payment_id)
        assert row.status == payment_models.PAYMENT_POSTED

        def collected(day):
            return payment_selectors.collected_by_class_for_invoices(
                (bill.pk,), line_class=TAXES, start=day, end=day
            )["collected"].get(str(bill.pk), Decimal("0"))

        before = (collected(day_taken), collected(day_reconciled))
        # The deposit batch is reconciled on the 22nd — written directly: what
        # is under test is the read, not the reconciliation service.
        payment_models.Payment.objects.filter(pk=row.pk).update(
            status=payment_models.PAYMENT_CLEARED,
            cleared_at=datetime(2026, 7, 22, 11, 0, tzinfo=UTC),
        )
        after = (collected(day_taken), collected(day_reconciled))
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)

    assert before == (WE1_TAX, Decimal("0"))
    assert after == (WE1_TAX, Decimal("0"))
    assert report["basis"]["collected"] == reporting.BASIS_POSTING
    assert report["totals"]["collected"] == WE1_TAX


def test_t7d_tc7b__a_cancelled_payment_collects_no_tax(brazos, marcus, monkeypatch):
    """`DEF-PAY-10321` — a cancelled payment is never counted. On the clearing
    date it was outside the window only because it never cleared; on the
    posting date it would be inside, so the set is an ALLOW list and both the
    original and its reversing row (both `cancelled`) are out."""
    from apps.payments import cancel

    with tenant_ctx(brazos):
        account, bill, _ = a_world(monkeypatch, brazos, marcus)
        paid = a_payment(marcus, account, LE1_WE1_BILL, cleared_at=None)
        cancel.cancel_payment(
            actor=marcus,
            payment_id=paid.payment_id,
            reason="wrong_account",
            cancelled_on=POSTED_AT,
        )
        answer = payment_selectors.collected_by_class_for_invoices(
            (bill.pk,), line_class=TAXES, start=JULY_START, end=JULY_END
        )

    assert answer["collected"].get(str(bill.pk), Decimal("0")) == Decimal("0")
    assert answer["allocations_read"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 — the seam publishes an absence rather than a zero when the read is dark
# ═══════════════════════════════════════════════════════════════════════════
def test_t7d_tc8__an_unpublished_read_keeps_the_column_absent(brazos, marcus, monkeypatch):
    """The behaviour this change REPLACES, kept as the fallback: a deployment
    where payments publishes no such read degrades to the honest answer — the
    column absent with its reason — rather than to a zero a return could be
    filed from."""
    with tenant_ctx(brazos):
        account, bill, _ = a_world(monkeypatch, brazos, marcus)
        a_payment(marcus, account, LE1_WE1_BILL)
        monkeypatch.delattr(
            payment_selectors, payments_seam.COLLECTED_BY_CLASS_READ, raising=True
        )
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        codes = {gap["code"] for gap in report["unavailable"]}

    assert report["totals"]["collected"] is None
    assert all(row.collected is None for row in report["rows"])
    assert payments_seam.COLLECTED_UNAVAILABLE in codes


# ═══════════════════════════════════════════════════════════════════════════
# TC-9 — append-only, in the DATABASE (PostgreSQL only — law 14)
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_t7d_tc9__a_class_row_cannot_be_updated_or_deleted(brazos, marcus, monkeypatch):
    """`payments/0016`'s trigger. A child that could be edited would be a back
    door into the same fact: somebody could leave the allocation untouched and
    rewrite what the money met, which changes a tax figure and leaves the parent
    looking undisturbed."""
    from django.db import DatabaseError, transaction

    with tenant_ctx(brazos):
        account, bill, _ = a_world(monkeypatch, brazos, marcus)
        a_payment(marcus, account, LE1_WE1_BILL)
        row = payment_models.AllocationClass.objects.filter(
            tenant=brazos, line_class=TAXES
        ).first()
        assert row is not None

        # A SAVEPOINT around each refusal — hard-won law 14: on PostgreSQL a
        # failed statement poisons the whole transaction, so without it the
        # second assertion could not run at all.
        with pytest.raises(DatabaseError) as updated:
            with transaction.atomic():
                payment_models.AllocationClass.objects.filter(pk=row.pk).update(
                    amount=Decimal("0")
                )
        with pytest.raises(DatabaseError) as deleted:
            with transaction.atomic():
                payment_models.AllocationClass.objects.filter(pk=row.pk).delete()

        still = payment_models.AllocationClass.objects.get(pk=row.pk)

    assert "append-only" in str(updated.value)
    assert "append-only" in str(deleted.value)
    assert still.amount == WE1_TAX


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C19 + task T7d (12-governance/11-change-requests.md §7 · §12) ·
#         12-governance/01-open-questions.md OQ-129 · OQ-174 (both CLOSED, and
#         they disagree) · 04-docs/05-modules/09-ledger/02-business-rules.md
#         BR-LED-002 / BR-LED-794 ·
#         04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-010 /
#         BR-PAY-031 / BR-PAY-038 · 08-worked-examples.md LE-3 ·
#         CLAUDE.md hard rules 1, 2, 4, 7 and hard-won laws 1, 2, 7, 14
# generated: 2026-09-02 by the CR-060 T7b/T7d/T7f lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(C19's surface is the EXISTING S41 collected
#         column, which stops returning absent) F✔ G✔ H=deferred(🔒
#         HUMAN-REVIEW-PENDING, row under CR-060 T19)
# gates: THREE SABOTAGES, each through monkeypatch so no live file was mutated,
#         each failure quoted VERBATIM in the module docstring above. TC-9
#         carries `requires_postgres` and SKIPS on the default suite rather than
#         passing vacuously
# exceptions: (1) the payment goes through the REAL `record_payment` and the
#         reversal through the REAL `reverse_payment`; only the BILL row and
#         billing's unpublished composition read are stood up, each for the
#         reason `tests/test_us_pay_001_record_payment.py` already records ·
#         (2) the ISSUE entry is posted through the ledger's own posting service
#         with `source_id = the real invoice id`, because that join is what the
#         collected basis rests on · (3) LE-3's figures are transcribed from
#         `tests/ledger_le_fixtures.py`, never recomputed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
