# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-37 · task 29 — the proof CS-37 asks for BY NAME:
#           *"Two credit notes in one run proved to take CONSECUTIVE numbers;
#           the account tab proved to list credit notes FROM SEVERAL DIFFERENT
#           BILLS; and the sign-off panel proved to contain no id — the check
#           that would have caught this one."*
# Story:    US-BIL-016 (the correction that writes them) · US-BIL-005 (the
#           release sign-off panel that reads them) · US-CUS-010 (S21's tabs)
#           Screens: S21 (Credits tab) · S28 (bill detail) · S31 (sign-off)
# Rules:    B14 rule 31 (RATIFIED 2026-08-31, PO: *"no Databse ID on screen -
#           that is a rule"*) · BR-TEN-035 (in-transaction allocation; gaps ok,
#           never reused) · BR-TEN-043 (the issue date is an argument, never a
#           clock) · BR-BIL-074 (a credit note's amount is never positive) ·
#           BR-BIL-004 / CLAUDE.md hard rule 4 (the row freezes at issue, so
#           historic rows are not back-filled) · hard rule 1 (tenant scoping)
# Golden:   ❄️ GT-6 — a $25.00 goodwill credit against a $247.30 invoice leaves
#           the customer owing **$222.30**. Asserted here UNMOVED: numbering a
#           credit note changes what it is CALLED and nothing about what it is
#           WORTH.
# Tests:    this file
# Impacts:  apps/billing/corrections.py (`_allocate_credit_note_no`, both
#           writers) · apps/billing/release.py (`_credit_note_label`) ·
#           apps/billing/selectors.account_credit_notes ·
#           apps/billing/credit_notes_api.py · config/urls.py
# ───────────────────────────────────────────────────────
"""CS-37 — a credit note nobody could name, in a place nobody could find.

**TWO PROBLEMS WITH ONE CAUSE.** A credit note had no identity a person could
quote — `credit_note_no` was null on every row in the product — and no home a
person could find it in. A customer ringing about a credit they were given could
not be helped without opening their bills one by one, and the finance user
signing off a bill run **was shown a raw database id**.

**THE THIRD FACT IS THE ONE THAT MAKES THIS A DEFECT AND NOT A GAP.**
`release.py` composed its sign-off sentence as `f"{number or pk} ({abs(amount)})"`,
and because `number` was null on every row **the `or pk` branch was the only one
that ever ran**. B14 rule 31 forbids it outright: *no database id is ever the
visible value of a field.* CS-37's rollback note is equally explicit that the
fallback is not to be restored — *"it is a rule breach, not a safety net"*.

════════════════════════════════════════════════════════════════════════════
THE RED PROOF, RUN BEFORE ANY OF THESE ASSERTIONS WAS TRUSTED GREEN (law 7)
════════════════════════════════════════════════════════════════════════════
Each guard below was first driven RED against the pre-change behaviour, by
restoring that behaviour in-process rather than by trusting a paragraph:

* `_allocate_credit_note_no` patched to return `(None, None)` — which is
  *exactly* the world before this lane, where nothing ever asked the series for
  a number. `test_cs37__two_credit_notes_in_one_run_take_consecutive_numbers`
  then failed on `assert None is not None`, and the account-tab case failed with
  every `credit_note_no` null.
* `_credit_note_label` patched back to `f"{number or pk} ({abs(amount)})"`.
  `test_cs37__the_sign_off_panel_names_no_database_id` then failed naming the
  uuid it found in the sentence.

The verbatim failures are quoted in the lane report and in
`12-governance/09-human-review-ledger.md`.

════════════════════════════════════════════════════════════════════════════
WHY A BACKEND TEST CAN HONESTLY SAY "THE PANEL CONTAINS NO ID"
════════════════════════════════════════════════════════════════════════════
Rule 31 is about RENDERED OUTPUT and **no gate in this repository reads any** —
B14's own status table says so, and CR-059 §0d says it again: *"Nine content
gates pass or fail on SOURCE; none of them looks at what a screen actually
prints."*

So this file closes as much of that as a Python test can, using the shape
`tests/test_cr059_rule31_collections_account_no.py` established one screen
along: it takes the sentence the SERVER composes for the panel — which is the
only place the id could come from, since the screen has no credit-note query of
its own — and scans **every string in it** for a uuid. The day a lane puts a
`pk` back into that sentence, this test finds it without depending on a
hand-kept list of fields.

It is **not** a substitute for a rendered check, and that is stated rather than
quietly covered: S31 has no render-check script, the shape for one is
`10-scripts/render-checks/cr053-bill-surface.mjs`, and the frontend half of this
proof lives in `07-frontend/src/features/billing/BillRunWizard.test.tsx`.
"""

import re
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import corrections, credit_notes_api, models, release, selectors
from apps.billing.correction_models import CLASS_RESTATEMENT
from core import numbering as core_numbering

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx

# `_RatedBill` is IMPORTED rather than redefined. A second stub of the rating
# result would drift from the real shape the moment `build_impact` reads one
# more attribute off it — which is exactly how the first draft of this file
# failed, on `lines_of`.
from tests.test_us_bil_016_bulk_corrections import _RatedBill
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

ISSUED_AT = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)
TODAY = date(2026, 8, 16)

#: ❄️ GT-6, finance-signed 2026-08-08. Quoted, never recomputed.
GT6_BILL_TOTAL = Decimal("247.30")
GT6_CREDIT = Decimal("25.00")
GT6_OWED = Decimal("222.300000")

#: A uuid as it would reach a screen. Deliberately the shape the PO reported on
#: the sibling defect — eight hex and a dash — and not a strict uuid parse,
#: because a truncated or re-formatted id on a screen is the same breach.
UUID_ON_SCREEN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-", re.IGNORECASE)


def a_bill(tenant, account, run, *, total=GT6_BILL_TOTAL, invoice_no=None, status=None):
    """One ISSUED bill with a single usage line — a real correction target."""
    from apps.tenancy import models as tenancy_models

    service = tenancy_models.Service.objects.get(code="electric")
    bill = models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        bill_run=run,
        invoice_no=invoice_no,
        service_date=date(2026, 7, 31),
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        subtotal=total,
        tax_total=Decimal("0"),
        total=total,
        currency="USD",
        status=status or models.INVOICE_ISSUED,
        issued_at=ISSUED_AT,
    )
    models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=bill,
        account=account,
        service=service,
        kind="usage",
        description="electric usage",
        quantity=Decimal("100"),
        unit="kWh",
        amount=total,
    )
    return bill


def a_numbered_note(tenant, account, bill, *, amount, number, issued_at=ISSUED_AT):
    """A credit note written straight, so a case can fix its own number.

    Used only where the NUMBER is the variable under test. The cases that prove
    the WRITERS allocate one go through `corrections` itself.
    """
    return models.CreditNote.objects.create(
        tenant=tenant,
        account=account,
        original_invoice=bill,
        credit_note_no=number,
        amount=amount,
        currency="USD",
        reason="goodwill",
        issued_at=issued_at,
    )


# ══ 1 · CONSECUTIVE NUMBERS IN ONE RUN ══════════════════════════════════════


def test_cs37__two_credit_notes_in_one_run_take_consecutive_numbers(brazos, dana, monkeypatch):
    """CS-37's first named proof, through the REAL writer and the REAL series.

    Two bills in ONE run are restated. Each correction is its own transaction
    (BR-BIL-047: one bill is one transaction), each asks the tenant's **Credit
    memo #** series for a number under BR-TEN-035's row lock, and the two
    numbers that come back are consecutive.

    **`CM-0001` then `CM-0002`** on a tenant that has never raised one — the
    seeded default format is `CM-{0000}` (`core/numbering.py:317`) and
    `_seed_number_series` starts every counter at 1.

    Numbering is a 🔒 sensitive path because it is an idempotency key: two
    writers minting from one series must not collide and must not skip. The
    collision half is held by `uq_credit_notes_no` — unique per tenant — and the
    skip half is what this asserts: the second number is the first plus one, not
    merely different from it.

    ⚠ **THE DATE IS AN ARGUMENT** (BR-TEN-043, gate G6). Both allocations pass
    the correction's own `issued_at`, so a backdated correction numbers under
    ITS date. That is invisible on `CM-{0000}`, which carries no date token, and
    it is the whole difference the day an admin picks `CR-{YYYY}-{000}`.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        first = a_bill(brazos, account, run, invoice_no="BL-2607-000001")
        second = a_bill(brazos, account, run, invoice_no="BL-2607-000002")

        _restate(monkeypatch, first, actor=dana)
        _restate(monkeypatch, second, actor=dana)

        numbers = [
            note.credit_note_no
            for note in models.CreditNote.objects.filter(tenant=brazos).order_by("created_at", "id")
        ]
        assert numbers == ["CM-0001", "CM-0002"], (
            "two credit notes raised in one run must take CONSECUTIVE numbers from "
            "the tenant's Credit memo series — no collision and no skip (BR-TEN-035)"
        )


def test_cs37__the_number_is_minted_in_the_writers_own_transaction(brazos, dana):
    """BR-TEN-035, the half that makes a rollback safe.

    `_allocate_credit_note_no` is called from inside each writer's
    `@transaction.atomic`, so a correction that fails after the credit note is
    written rolls the SERIES COUNTER back with the row it would have numbered.
    Asserted by allocating and rolling back, then allocating again: the number
    is handed out a second time because the first was never committed.

    This is the ONE respect in which a gap and a duplicate are not the same
    thing. BR-TEN-035 tolerates gaps — *"gaps ok, never reused"* — but a rolled
    back allocation is not a gap, it is a number that was never issued, and
    burning it would drift the counter every time a correction was refused.
    """
    from django.db import transaction

    with tenant_ctx(brazos):
        try:
            with transaction.atomic():
                first, problem = corrections._allocate_credit_note_no(ISSUED_AT)
                assert first == "CM-0001"
                assert problem is None
                raise _RollBack()
        except _RollBack:
            pass
        again, _problem = corrections._allocate_credit_note_no(ISSUED_AT)
        assert again == "CM-0001", (
            "a rolled-back correction must roll the counter back with it — the number "
            "was never issued, so it is not a gap"
        )


def test_cs37__a_tenant_with_no_credit_memo_series_is_reported_never_faked(brazos, dana):
    """A settings gap does not stop a utility fixing a wrong bill.

    `runs._allocate_run_no`'s posture, applied one table along, and CS-37's own
    rule is what makes it safe: *"historic rows keep a null number; they are NOT
    back-filled"*, so a numberless credit note is already a state every reader
    must handle.

    The absence is REPORTED — a code, not silence — and never invented. A number
    this module chose would be a second numbering authority in the product, which
    is `DEF-615` (`IMP-` against `RUN-`) exactly.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        tenancy_models.NumberSeries.objects.filter(
            tenant=brazos, series=core_numbering.CREDIT_MEMO
        ).delete()
        number, problem = corrections._allocate_credit_note_no(ISSUED_AT)
        assert number is None
        assert problem == corrections.CREDIT_NOTE_SERIES_MISSING


# ══ 2 · THE ACCOUNT TAB, LISTING NOTES FROM SEVERAL BILLS ═══════════════════


def test_cs37__the_account_read_lists_credit_notes_from_several_different_bills(brazos, dana):
    """CS-37's second named proof — and the question that had NO answer at all.

    CR-059 §7: *"To find every credit note Ajinkya has ever been given, somebody
    must open each of his bills one at a time and read the panel on each. There
    is no list, no filter, no account tab and no report — and the database index
    built for exactly that lookup, on utility plus account, has never had a
    query run against it."*

    Three credit notes against THREE DIFFERENT BILLS on one account, and one
    read returns all three, each carrying the bill it came from.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bills = [a_bill(brazos, account, run, invoice_no=f"BL-2607-00010{n}") for n in range(1, 4)]
        for index, bill in enumerate(bills, start=1):
            a_numbered_note(
                brazos,
                account,
                bill,
                amount=Decimal(f"-{index}0.00"),
                number=f"CM-000{index}",
                issued_at=datetime(2026, 8, 10 + index, 9, 0, tzinfo=UTC),
            )

        served = selectors.account_credit_notes(account.pk)
        assert served["count"] == 3
        assert served["truncated"] is False
        # Newest first — the order a person asking "what have I been given" reads.
        assert [row["credit_note_no"] for row in served["credit_notes"]] == [
            "CM-0003",
            "CM-0002",
            "CM-0001",
        ]
        assert {row["invoice_no"] for row in served["credit_notes"]} == {
            "BL-2607-000101",
            "BL-2607-000102",
            "BL-2607-000103",
        }, "the three notes must be traceable to THREE different bills"


def test_cs37__the_account_route_is_reachable_and_returns_the_same_rows(brazos, dana):
    """Hard-won law 2 — built is not wired.

    The read is resolved through the ROOT URLconf and then called, so a future
    lane cannot lose the `config/urls.py` include silently. `reverse()` cannot
    be used because these patterns are registered unnamed, so the resolver is
    asked for the view the way `test_us_bil_surface_apis.py` asks.
    """
    from django.urls import resolve

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = a_bill(brazos, account, run, invoice_no="BL-2607-000201")
        a_numbered_note(brazos, account, bill, amount=Decimal("-25.00"), number="CM-0001")

        # `/api/<subdomain>/…` — the whole tree is mounted under the tenant
        # segment, so a bare path resolves to nothing and would prove nothing.
        match = resolve(f"/api/{brazos.subdomain}/accounts/{account.pk}/credit-notes")
        assert match.func is credit_notes_api.account_credit_notes

        response = api_call(
            credit_notes_api.account_credit_notes,
            "get",
            user=FakeUser(),
            role="billing_clerk",
            tenant=brazos,
            account_id=str(account.pk),
        )
        assert response.status_code == 200
        assert [row["credit_note_no"] for row in response.data["credit_notes"]] == ["CM-0001"]


def test_cs37__an_account_with_no_credit_notes_answers_an_empty_list(brazos, dana):
    """ "This customer has never been given a credit" is an ANSWER, not a 404.

    A 404 would say the account does not exist, which is a different fact and
    one the screen would have to draw as an error over a perfectly ordinary
    customer.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        response = api_call(
            credit_notes_api.account_credit_notes,
            "get",
            user=FakeUser(),
            role="billing_clerk",
            tenant=brazos,
            account_id=str(account.pk),
        )
        assert response.status_code == 200
        assert response.data["credit_notes"] == []
        assert response.data["count"] == 0


def test_cs37__another_tenants_account_reads_as_empty_never_as_its_rows(brazos, lonestar, dana):
    """CLAUDE.md hard rule 1 + HR-1 — a cross-tenant id resolves to NO rows.

    Not to somebody else's, and not to a 500. The tenant filter is explicit and
    RLS FORCE is under it; this asserts the pair behaves as one.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = a_bill(brazos, account, run, invoice_no="BL-2607-000301")
        a_numbered_note(brazos, account, bill, amount=Decimal("-25.00"), number="CM-0001")

    with tenant_ctx(lonestar):
        served = selectors.account_credit_notes(account.pk)
        assert served["credit_notes"] == []


def test_cs37__a_historic_row_shows_its_bill_and_date_and_never_an_id(brazos, dana):
    """CS-37's second new rule, on the read that feeds the tab.

    *"Where the number is genuinely absent on historic rows, the screen shows
    the bill it was raised against and the date, never the id."* Historic rows
    are not back-filled — the row freezes at issue — so this branch is permanent
    rather than transitional, and the row therefore has to carry both facts.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = a_bill(brazos, account, run, invoice_no="BL-2607-000401")
        models.CreditNote.objects.create(
            tenant=brazos,
            account=account,
            original_invoice=bill,
            amount=Decimal("-25.00"),
            currency="USD",
            reason="goodwill",
            issued_at=ISSUED_AT,
        )
        row = selectors.account_credit_notes(account.pk)["credit_notes"][0]
        assert row["credit_note_no"] is None
        assert row["invoice_no"] == "BL-2607-000401"
        assert row["issued_at"] is not None


def test_cs37__a_blank_bill_number_is_served_as_null_not_as_an_empty_cell(brazos, dana):
    """An empty cell breaches rule 31 as loudly as a uuid did.

    `Invoice.invoice_no` is a `TextField()`, so a draft carries `""` rather than
    NULL. A blank renders as an EMPTY CELL, and a person reads that as *"there
    is nothing here"* about a document that exists — which is the finding
    `test_cr059_rule31_collections_account_no` recorded one screen along. The
    read normalises it, so the screen can say so in words.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = a_bill(brazos, account, run, invoice_no="", status=models.INVOICE_DRAFT)
        a_numbered_note(brazos, account, bill, amount=Decimal("-25.00"), number="CM-0001")
        row = selectors.account_credit_notes(account.pk)["credit_notes"][0]
        assert row["invoice_no"] is None


# ══ 3 · THE SIGN-OFF PANEL CONTAINS NO ID ═══════════════════════════════════


def test_cs37__the_sign_off_panel_names_no_database_id(brazos, dana):
    """CS-37's third named proof, and the reason this whole spec exists.

    **THE BREACH, as CR-059 recorded it.** `release.py` named the credit notes
    in a run as `f"{number or pk} ({abs(amount)})"`, and every credit note in the
    product carried a null number — so the `or pk` branch was the ONLY branch
    that ever ran and a finance user signing off a run read a sentence with a raw
    UUID in it. B14 rule 31, ratified 2026-08-31 in the PO's own words: *"no
    Databse ID on screen - that is a rule"*.

    This scans EVERY string the summary carries — not a named field — so a lane
    that reintroduces an id anywhere in the panel's own words is caught without
    this test having to know which field it landed in.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-A")
        account = an_account(dana, brazos, account_no="A-50063")
        bill = a_bill(brazos, account, run, invoice_no="BL-2607-000501")
        a_numbered_note(brazos, account, bill, amount=-GT6_CREDIT, number="CM-0001")

        summary = release.summary_for(run)
        offenders = [
            text for text in _every_string(summary.as_payload()) if UUID_ON_SCREEN.search(text)
        ]
        assert offenders == [], (
            "B14 rule 31 — no database id is ever the visible value of a field. "
            f"The sign-off panel carries: {offenders}"
        )
        credits = _credit_problem(summary)
        assert "CM-0001" in credits["detail"], "the sentence names the note by its NUMBER"


def test_cs37__a_numberless_credit_note_names_its_bill_and_date_never_its_id(brazos, dana):
    """The fallback that REPLACED the id, proved on the row that needs it.

    A historic credit note has no number and never will — it is not back-filled,
    because the row freezes at issue. The panel names the bill it was raised
    against and the date instead. **Restoring `or pk` here is what CS-37's
    rollback note refuses in terms:** *"it is a rule breach, not a safety net."*
    """
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-A")
        account = an_account(dana, brazos, account_no="A-50064")
        bill = a_bill(brazos, account, run, invoice_no="BL-2607-000601")
        note = models.CreditNote.objects.create(
            tenant=brazos,
            account=account,
            original_invoice=bill,
            amount=-GT6_CREDIT,
            currency="USD",
            reason="goodwill",
            issued_at=ISSUED_AT,
        )

        detail = _credit_problem(release.summary_for(run))["detail"]
        assert str(note.pk) not in detail
        assert not UUID_ON_SCREEN.search(detail)
        assert "BL-2607-000601" in detail, "the bill it was raised against"
        assert "2026-08-16" in detail, "and the date"


def test_cs37__a_credit_note_with_neither_number_nor_bill_says_so_in_words(brazos, dana):
    """Rule 31's other half, and it is the half a blank cell breaks.

    `test_cr059_rule31_collections_account_no` records it: *"where neither
    exists, the field says so IN WORDS"* — an empty cell is read as *"there is
    nothing here"* about a document that exists, which is the same wrong answer
    the uuid gave for the opposite reason.
    """
    label = release._credit_note_label(None, None, None, Decimal("-25.00"))
    assert label == "credit with no number (25.00)"
    assert not UUID_ON_SCREEN.search(label)


def test_cs37__gt6s_signed_222_30_is_unmoved_by_numbering(brazos, dana):
    """❄️ B4/B5 — the frozen figure, asserted rather than assumed.

    GT-6 is *a $25.00 goodwill credit against a $247.30 invoice → the customer
    owes $222.30*, finance-signed 2026-08-08. Giving the credit note a NAME
    cannot move what it is WORTH, and CS-37 says so — *"CS-37 and CS-38 need NO
    schema at all"* and nothing in this CR touches a frozen figure. This is the
    assertion that would go red if it did.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-A")
        account = an_account(dana, brazos, account_no="A-50065")
        bill = a_bill(brazos, account, run, invoice_no="BL-2607-000701")
        a_numbered_note(brazos, account, bill, amount=-GT6_CREDIT, number="CM-0001")

        summary = release.summary_for(run)
        assert summary.amount == GT6_OWED
        assert summary.gross_amount == Decimal("247.300000")
        assert summary.credits_applied == Decimal("25.000000")


# ── helpers ────────────────────────────────────────────────────────────────


class _RollBack(Exception):
    """Rolls a test transaction back without pretending to be a rule refusal."""


def _restate(monkeypatch, bill, *, actor):
    """One class-R correction, with the RATING and ISSUE halves stubbed out.

    The same shape `test_us_bil_016_bulk_corrections` uses for its direct
    `execute_restatement` cases: this file is about the NUMBER the credit note
    takes, so re-pricing a rebill through the engine would be testing another
    lane's arithmetic to reach an assertion about a string.
    """
    rebill = models.Invoice.objects.create(
        tenant=bill.tenant,
        account=bill.account,
        bill_run=bill.bill_run,
        service_date=bill.service_date,
        period_start=bill.period_start,
        period_end=bill.period_end,
        subtotal=bill.total,
        tax_total=Decimal("0"),
        total=bill.total,
        currency=bill.currency,
        bill_type="rebill",
    )
    monkeypatch.setattr(corrections.single, "prepare_single_bill", lambda **k: _PreparedStub())
    monkeypatch.setattr(corrections.single, "calculate_single_bill", lambda *a, **k: rebill)
    import apps.billing.issue as issue_module

    monkeypatch.setattr(issue_module, "issue_invoice", lambda invoice, **k: invoice)
    monkeypatch.setattr(corrections, "post_credit_note_reversal", lambda *a, **k: None)

    impact = corrections.build_impact(
        bill,
        reason_codes=("wrong_read",),
        correction_class=CLASS_RESTATEMENT,
        corrected=_RatedBill([], bill.total),
    )
    return corrections.execute_restatement(
        bill,
        impact=impact,
        reason="wrong_read",
        issued_at=ISSUED_AT,
        on_date=TODAY,
        template_id=bill.template_id,
        template_version=1,
        actor=actor,
    )


class _PreparedStub:
    blocked = ()
    ready = ()


def _every_string(value):
    """Every string anywhere in the served payload, however deeply nested.

    Deliberately structure-blind: the point of rule 31 is that an id must not
    reach a person, and a test that only checked the field it happened to live
    in on the day it was written would go quiet the moment it moved.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _every_string(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _every_string(item)


def _credit_problem(summary):
    """The panel's credit-note sentence, by its stable support-line code."""
    for problem in summary.problems:
        if problem["code"] == release.SUMMARY_CREDITS_NETTED:
            return problem
    raise AssertionError("the summary carries no credit-note sentence")


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §7 (how credit notes work today) · §7b · §8 CS-37 · §11 tasks
#         27/29 · B14 rules 31/32 · BR-TEN-035 · BR-TEN-043 · BR-BIL-074
# generated: 2026-09-02 by the CR-059 W5 credit-note identity lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(the rendered half is CR-059 task 28's
#            `BillRunWizard.test.tsx` case, same lane, next commit) F✔ G✔
#            H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — see the module docstring for the two patches used
#        and the lane report for the verbatim failures.
# exceptions:
#   E3 the restatement case stubs `prepare_single_bill`, `calculate_single_bill`,
#      `issue_invoice` and `post_credit_note_reversal`. This file asserts the
#      NUMBER a credit note takes; re-pricing a rebill through the rating engine
#      and posting a balanced pair to reach an assertion about a string would be
#      re-testing two other lanes' work and would tie this file's health to
#      theirs. `test_us_bil_016_bulk_corrections` owns the unstubbed path.
#   E3 no rendered check of S31 exists and this file does not claim to be one.
#      REPORTED, not covered: the shape is 10-scripts/render-checks/.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
