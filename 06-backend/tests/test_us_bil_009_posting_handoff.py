# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-009 (the balanced posting handoff contract — §7 CONFIRMED,
#           WE-1 verbatim) · US-BIL-005 (issue emits it, TC-1/TC-4/TC-6) ·
#           US-BIL-029 (BR-BIL-037 stage 7 — post-to-ledger)
#           Screens: S31 step 6 · S56
# Rules:    BR-BIL-011 (one bill = one balanced JE, DR AR total / CR per-GL
#           buckets; the posting service is the sole writer) · BR-BIL-010 (the
#           GL stamp this handoff READS) · BR-BIL-055 (a break never blocks the
#           run) · BR-LED-001 (dimensions on every journal line) · BR-LED-003
#           (balanced at post) · CLAUDE.md rule 2 (money) · rule 4
#           (immutability) · rule 5 (sole writer) · rule 6 (idempotency) ·
#           rule 7 (audit)
# Golden:   US-BIL-005 §7 / US-BIL-009 §7 — CONFIRMED (WE-1/BS-1, workbook
#           verbatim): DR 1200 AR 247.87 / CR 4100 88.60 · 4105 12.00 · 4110
#           39.50 · 4115 8.00 · 4120 15.80 · 4130 18.00 · 4150 40.00 · 2200–2203
#           20.97 · 4200 5.00 · LE-2 (the revenue slice of the same entry)
# ───────────────────────────────────────────────────────
"""Stage 7: the bill reaches the books, or the bill does not issue.

**WHAT THIS FILE EXISTS FOR.** Two large, correct engines existed and nothing
connected them: `apps/ledger/posting.py` could write a balanced entry and
`apps/billing/issue.py` could freeze a bill, and a bill could therefore issue
while its money never reached a single ledger account. Every case below is
about that wire.

THE ONE THING TO READ FIRST — the tests that matter most here are the ones that
assert **nothing happened**. `tc4` (the books refuse → the bill stays a DRAFT),
`tc5` (an unbalanced handoff is refused naming the delta and nothing is
plugged), `tc8` (a negative bucket refuses and names OQ-152). An issued bill is
immutable; a journal entry is immutable; so the only lawful moment to stop
either is before both, and these are the cases that prove that moment is
guarded.

**EVERY FIGURE IS COPIED, NEVER COMPUTED HERE.** `tc2` transcribes four of §7's
own signed bucket figures (electric usage 88.60 / electric base 12.00 / water
usage 39.50 / water base 8.00) and asserts the AR debit is their sum. A test
that re-derived an expected figure from the code's own arithmetic would agree
with a broken implementation.

**WHY §7's OTHER FIVE BUCKETS ARE NOT ASSERTED, said out loud rather than left
as a gap in the numbers.** WE-1 posts nine buckets; four are reachable on this
fixture and five are not, for two different and honest reasons:

  * **4120 sewer · 4130 trash · 4150 capacity** — the provisioned test tenant
    sells electric and water only (PO ruling 2026-08-11, OQ-115: a tenant is
    seeded revenue accounts for the services it actually sells), so those three
    GLs do not exist in its chart at all.
  * **4200 late-fee revenue** — a FEE line still names no charge code, so
    BR-BIL-010 refuses to stamp it and the bill carrying it cannot issue. That
    is the standing refusal `issue.py` reports, not something stage 7 changed;
    `tc9` asserts it explicitly so the day `charge_id` reaches a priced line
    this file goes RED and someone extends the fixture.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import issue, models, posting_seam
from apps.billing.exceptions import BillingRuleError
from apps.customers import models as customer_models
from apps.ledger import models as ledger_models
from apps.ledger import posting as ledger_posting
from apps.ledger import selectors as ledger_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_br_bil_069_tax_authority_gl import (
    SPLIT_TAX_TOTAL,
    THREE_AUTHORITIES,
    tax_rules_for,
    three_authorities,
)
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    SUBTOTAL,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_authorised_run,
)
from tests.test_us_bil_029_assemble import assemble, billing_data
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

#: The draft fixture's own service date (`a_priced_draft`), and it is NOT the
#: day the bill issues (`ISSUED_AT` is 3 Jul 2026). The two differing is what
#: makes `tc7`'s book-date assertion mean anything.
SERVICE_DATE = date(2026, 6, 30)

#: US-BIL-005 §7 / US-BIL-009 §7, CONFIRMED (WE-1/BS-1), transcribed — the four
#: buckets a tenant selling electric and water can reach. Copied, not computed.
WE1_ELECTRIC_USAGE = Decimal("88.60")  # "CR 4100 88.60"
WE1_ELECTRIC_BASE = Decimal("12.00")  # "4105 12.00"
WE1_WATER_USAGE = Decimal("39.50")  # "4110 39.50"
WE1_WATER_BASE = Decimal("8.00")  # "4115 8.00"
#: Arithmetic over four signed figures, and stated as such: this is the AR
#: debit of the SLICE below, not one of §7's own totals (§7's AR is 247.87 for
#: all nine buckets).
WE1_SLICE_AR = Decimal("148.10")


def journal_entries(tenant):
    return ledger_models.JournalEntry.objects.filter(tenant=tenant)


def journal_totals(tenant, entry):
    """Σ per GL CODE straight out of `journal_lines` — never off a result object.

    Deliberately not read from `PostingResult` and deliberately not through a
    ledger selector: what these cases must check is what LANDED in the table,
    not what the code that wrote it says it wrote.
    """
    totals: dict[str, dict[str, Decimal]] = {}
    rows = ledger_models.JournalLine.objects.filter(tenant=tenant, journal_entry=entry).values_list(
        "ledger_account__code", "side", "amount"
    )
    for code, side, amount in rows:
        bucket = totals.setdefault(code, {"debit": Decimal("0"), "credit": Decimal("0")})
        bucket[side] += amount
    return totals


def credit_of(totals, code):
    return totals.get(code, {"credit": Decimal("0")})["credit"]


def debit_of(totals, code):
    return totals.get(code, {"debit": Decimal("0")})["debit"]


def a_multi_service_draft(tenant, account, run, *, invoice_no="BL-2607-000201"):
    """WE-1's ELECTRIC + WATER slice, hand-built, with §7's own line figures.

    Hand-built rather than priced, on purpose: §7 states the POSTING figures and
    this file is about the posting, so the lines carry those figures directly
    instead of a second rating fixture that would have to reproduce them.
    """
    from apps.tenancy import models as tenancy_models

    rows = (
        ("electric", "usage", "Electric usage", WE1_ELECTRIC_USAGE),
        ("electric", "base", "Electric base charge", WE1_ELECTRIC_BASE),
        ("water", "usage", "Water usage", WE1_WATER_USAGE),
        ("water", "base", "Water base charge", WE1_WATER_BASE),
    )
    invoice = models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        bill_run=run,
        invoice_no=invoice_no,
        service_date=SERVICE_DATE,
        period_start=date(2026, 6, 1),
        period_end=SERVICE_DATE,
        subtotal=WE1_SLICE_AR,
        tax_total=Decimal("0"),
        total=WE1_SLICE_AR,
        bill_payload={"account_no": account.account_no, "customer_name": "Sarah Chen"},
        payload_version=1,
    )
    for service_code, kind, description, amount in rows:
        models.InvoiceLine.objects.create(
            tenant=tenant,
            invoice=invoice,
            account=account,
            service=tenancy_models.Service.objects.get(code=service_code),
            kind=kind,
            description=description,
            amount=amount,
            taxable=True,
        )
    return invoice


# ═══════════════════════════════════════════════════════════════════════════
# tc1 — a bill that issues reaches the books, as ONE balanced entry
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_009_tc1__issuing_a_bill_posts_one_balanced_entry(brazos, dana):
    """BR-BIL-011 — *"one bill = … one balanced journal entry (DR AR total / CR
    per-GL buckets); posting service is the sole writer."*

    Before this lane a bill could issue and this assertion had no rows to make:
    `journal_entries` stayed empty forever and the meter-to-cash loop was open
    at its last step. The entry is read back out of `journal_lines`, not off
    the result object, so what is asserted is what LANDED.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)
        assert not journal_entries(brazos).exists(), "nothing in the books before issue"

        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        entries = list(journal_entries(brazos))
        assert len(entries) == 1, "one bill, one entry — never two, never none"
        entry = entries[0]
        assert entry.status == ledger_models.JE_POSTED
        assert entry.source_type == "invoice"
        assert str(entry.source_id) == str(bill.pk)
        assert entry.currency == bill.currency
        assert entry.posted_at == ISSUED_AT  # BR-TEN-043 — the caller's moment

        # DR AR = the STORED invoice total; CR the buckets of the stamped lines.
        totals = journal_totals(brazos, entry)
        ar_code = ledger_models.LedgerAccount.objects.get(
            pk=ledger_selectors.gl_account_id_for_designation("accounts_receivable")
        ).code
        assert debit_of(totals, ar_code) == SUBTOTAL == bill.total
        usage_code, base_code = "4100", "4105"
        assert credit_of(totals, usage_code) == Decimal("82.08")  # GT-1, frozen
        assert credit_of(totals, base_code) == Decimal("18.50")  # GT-1, frozen
        credited = sum(bucket["credit"] for bucket in totals.values())
        debited = sum(bucket["debit"] for bucket in totals.values())
        assert debited == credited == bill.total

        # The transient outcome the run aggregates, and it says CREATED.
        assert bill.posting.created is True
        assert bill.posting.debits == bill.posting.credits == bill.total
        # Hard rule 6: the key is the LEDGER's own composition, not billing's.
        assert bill.posting.posting_key == ledger_posting.posting_key(
            source_type="invoice", source_id=bill.pk, event="issued"
        )
        assert entry.posting_key == bill.posting.posting_key


# ═══════════════════════════════════════════════════════════════════════════
# tc2 — §7's own bucket figures, through the real posting service
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_009_tc2__the_we1_slice_posts_its_signed_buckets(brazos, dana):
    """US-BIL-005 §7 / US-BIL-009 §7, CONFIRMED (WE-1/BS-1) — four of the nine.

    *"Posting handoff per bill: DR AR = current charges; CR per-GL buckets = Σ
    stamped lines per GL."* Four services' worth of lines, four DIFFERENT GL
    accounts, each landing at the figure the workbook signed — and the debit
    equal to their sum. The other five buckets and why they are unreachable on
    this fixture are in the module docstring; `tc9` guards the fee half.

    The bucket COUNT is asserted because a handoff that merged its buckets, or
    that emitted one line per invoice line, would still balance — and would
    still be wrong about §7.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_multi_service_draft(brazos, account, run)

        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        entry = journal_entries(brazos).get()
        totals = journal_totals(brazos, entry)
        assert credit_of(totals, "4100") == WE1_ELECTRIC_USAGE
        assert credit_of(totals, "4105") == WE1_ELECTRIC_BASE
        assert credit_of(totals, "4110") == WE1_WATER_USAGE
        assert credit_of(totals, "4115") == WE1_WATER_BASE
        assert credit_of(totals, "1200") == Decimal("0")
        assert debit_of(totals, "1200") == WE1_SLICE_AR == bill.total
        assert len(bill.posting.buckets) == 4, "four GLs, four buckets — never merged"
        assert ledger_models.JournalLine.objects.filter(journal_entry=entry).count() == 5

        # BR-LED-001's dimensions — ALL OF THEM, since 2026-08-16.
        #
        # ⚠ THIS BLOCK USED TO ASSERT THE OPPOSITE. It read *"US-LED-002 —
        # carried, not resolved; reported, never guessed"* and required
        # `premises_id is None and unit_id is None`, because the posting service
        # carried the two columns and nothing resolved the chain. US-LED-002
        # landed, so a REAL bill — priced, issued and posted through stage 7 —
        # is now the end-to-end proof that the dimension reaches the books:
        # billing hands over the account, the posting service resolves
        # account → unit → premises, and every line of the entry carries it.
        expected_unit = customer_models.Account.objects.get(pk=bill.account_id).unit_id
        for line in ledger_models.JournalLine.objects.filter(journal_entry=entry):
            assert line.source_type == "invoice"
            assert str(line.source_id) == str(bill.pk)
            assert str(line.account_id) == str(bill.account_id)
            assert str(line.unit_id) == str(expected_unit)
            assert line.premises_id is not None


# ═══════════════════════════════════════════════════════════════════════════
# tc3 — three authorities, three tax buckets (BR-BIL-069 meets §7)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_009_tc3__each_tax_authority_gets_its_own_posting_bucket(brazos, dana):
    """BR-BIL-069 + §7 — the split survives all the way into the books.

    The whole point of the PO's ruling (*"For each atheority have separate
    account and tagging"*) is that remittance can be reconstructed per
    authority. A stamp that split three ways and a HANDOFF that merged them back
    into one credit would satisfy BR-BIL-010 and defeat the ruling one layer
    later — the money would be in one 2200 bucket and no report could take it
    apart. This is the case that watches the second layer.

    The bill is the real chain (stage 1 → 2 → rating → stage 6 → issue), so the
    figures are the engine's under the ❄️ frozen per-line rounding law; the one
    cent between $8.30 and $8.31 is OQ-148 and is explained in
    tests/test_br_bil_069_tax_authority_gl.py.
    """
    with tenant_ctx(brazos):
        built = three_authorities(actor=dana)
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = assemble(brazos, account, run, billing_data(account, taxes=tax_rules_for(built)))

        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        entry = journal_entries(brazos).get()
        totals = journal_totals(brazos, entry)
        for name, _rate, expected in THREE_AUTHORITIES:
            code = ledger_models.LedgerAccount.objects.get(pk=built[name][1].id).code
            assert credit_of(totals, code) == expected, f"{name} owed into its own bucket"
        assert (
            credit_of(totals, "2200-01")
            + credit_of(totals, "2200-02")
            + credit_of(totals, "2200-03")
        ) == SPLIT_TAX_TOTAL
        # Six buckets: 4100, 4105 and one per authority. Merged tax would be four.
        assert len(bill.posting.buckets) == 5
        assert debit_of(totals, "1200") == bill.total

        # ── INVERTED 2026-10-01 (billing red triage), NOT DELETED ───────────
        # This asserted the authority DIMENSION as a reported absence — every
        # line NULL and the problem `tax_bucket_names_no_authority` — because
        # rating published no `tax_authority_id_for_tax`. It does since
        # `b813394a6` (2026-09-24, Finance `P0.3`), so the absence this pinned
        # is closed on purpose, and the strongest form now is WHICH authority:
        # each tax bucket's line names its own tax row's jurisdiction, the
        # revenue and receivable lines name none, and the problem is gone.
        by_code = {
            ledger_models.LedgerAccount.objects.get(pk=built[name][1].id).code: str(
                built[name][0].jurisdiction_id
            )
            for name, _rate, _expected in THREE_AUTHORITIES
        }
        for line in entry.lines.select_related("ledger_account"):
            code = line.ledger_account.code
            expected_authority = by_code.get(code)
            assert (
                str(line.tax_authority_id) if line.tax_authority_id else None
            ) == expected_authority, code
        assert len(set(by_code.values())) == 3
        assert "tax_bucket_names_no_authority" not in {
            problem["code"] for problem in bill.posting.problems
        }


# ═══════════════════════════════════════════════════════════════════════════
# tc4 — the books refuse → the bill does NOT issue (the rollback)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_009_tc4__a_posting_refusal_rolls_the_whole_issue_back(brazos, dana):
    """A bill that cannot reach the books must stay a DRAFT. All of it.

    This is the case the transaction placement exists for. If stage 7 ran
    outside the issue transaction — or inside a `try/except` that shrugged — the
    product would produce an issued, immutable bill whose money is in no ledger
    account, and hard rule 4 leaves no path to add the entry afterwards. The
    only lawful moment to refuse is while the draft is still discardable.

    The refusal used here is a REAL tenant state: nobody has designated an
    `accounts_receivable` account, so the entry has no debit side. Six things
    must be untrue afterwards, and each is a separate assertion because each is
    a separate way for a half-issue to survive.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)

        ar = ledger_models.LedgerAccount.objects.get(
            pk=ledger_selectors.gl_account_id_for_designation("accounts_receivable")
        )
        ar.designation = None
        ar.save(update_fields=["designation"])

        with pytest.raises(BillingRuleError, match="accounts_receivable"):
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
                actor=dana,
            )

        untouched = models.Invoice.objects.get(pk=draft.pk)
        assert untouched.status == models.INVOICE_DRAFT  # 1 — still discardable
        assert untouched.issued_at is None  # 2
        assert untouched.due_date is None  # 3
        assert all(line.gl_account_id is None for line in untouched.lines.all())  # 4
        assert not journal_entries(brazos).exists()  # 5 — nothing in the books
        assert not ledger_models.JournalLine.objects.filter(tenant=brazos).exists()  # 6

        # And the run reports it as ONE named break, with the other bills of the
        # batch unaffected (BR-BIL-055) — never as a crashed run.
        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )
        assert result.issued == ()
        assert [problem.reason for problem in result.broken] == [issue.ISSUE_POSTING_NO_AR]
        assert result.posted == 0 and result.already_posted == 0


def test_us_bil_009_tc5__an_unbalanced_handoff_is_refused_naming_the_delta(brazos, dana):
    """DR AR ≠ Σ CR buckets → REFUSE, and never, ever plug the difference.

    The bill's stored total says one thing and its own stamped lines say
    another. A handoff that balanced itself — by taking the AR debit from the
    lines it just summed, or by adding a rounding line — would post an entry
    that balances and books a figure the customer's bill does not show, on every
    affected bill of a run, silently.

    The delta is asserted to be IN THE MESSAGE, because "unbalanced" without a
    number is not something a human can act on.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)
        # A draft is still editable (BR-BIL-004 binds at issue). 100.58 of lines
        # under a header that claims 110.58 — a 10.00 hole.
        draft.total = SUBTOTAL + Decimal("10.00")
        draft.save(update_fields=["total"])

        with pytest.raises(BillingRuleError) as refusal:
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
                actor=dana,
            )
        message = str(refusal.value)
        assert "does not foot" in message
        assert "10.00" in message, "the delta is named, so a human can act on it"
        assert issue._reason_for(refusal.value) == issue.ISSUE_POSTING_UNBALANCED

        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT
        assert not journal_entries(brazos).exists()


def test_us_bil_009_tc6__a_replayed_handoff_writes_no_second_entry(brazos, dana):
    """CLAUDE.md rule 6 / US-LED-001 TC-6 — *"one entry, ever"*.

    A release that crashes between the issue and the `released_at` stamp is
    resumed (US-BIL-005 TC-13), and a resumed stage 7 must find the entry
    already there and write nothing. The key is `invoice|<id>|issued` composed
    by the LEDGER's own `posting_key()`, so both calls key the same string —
    which is the whole reason billing does not compose it itself.

    Both halves of the guarantee are asserted: the second call reports
    `created=False` (never an exception — a replay is the correct outcome) and
    the books hold exactly one entry with exactly the same lines.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)
        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )
        first_entry = journal_entries(brazos).get()
        lines_before = ledger_models.JournalLine.objects.filter(tenant=brazos).count()

        replay = posting_seam.post_bill_issue(
            models.Invoice.objects.get(pk=bill.pk),
            lines=list(models.Invoice.objects.get(pk=bill.pk).lines.all()),
            posted_at=ISSUED_AT,
            actor=dana,
        )

        assert replay.created is False
        assert replay.entry_id == str(first_entry.pk)
        assert journal_entries(brazos).count() == 1
        assert ledger_models.JournalLine.objects.filter(tenant=brazos).count() == lines_before
        assert replay.debits == replay.credits == bill.total

        # And re-issuing the RUN finds no remaining drafts, so it posts nothing.
        again = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )
        assert again.issued == () and again.posted == 0 and again.already_posted == 0
        assert journal_entries(brazos).count() == 1


def test_us_bil_009_tc7__the_book_date_is_the_service_date_not_the_issue_date(brazos, dana):
    """US-BIL-009 §1 — the handoff carries `service_date`, and no other date.

    A June bill issued on 3 July books in JUNE. The two dates differ in this
    fixture on purpose: `service_date` is 2026-06-30 and `issued_at` is
    2026-07-03, so a handoff that booked "today" would pass every balance check
    and put a period's revenue in the wrong month — invisible on the bill,
    visible only when finance closes June.

    ⚠ This is a READING of the ratified handoff shape rather than a figure §7
    restates, so it is flagged in this file's human-review row for the PO to
    confirm in plain English: *"the June bill you issue on 3 July is recorded in
    the books under 30 June."*
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)
        assert draft.service_date == SERVICE_DATE != ISSUED_AT.date()

        issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        entry = journal_entries(brazos).get()
        assert entry.entry_date == SERVICE_DATE
        assert entry.posted_at == ISSUED_AT  # the wall clock is a separate fact


def test_us_bil_009_tc8__a_negative_bucket_refuses_and_names_oq_152(brazos, dana):
    """A GL bucket below zero is a RULING nobody has made — OQ-152, not a guess.

    A discount is a negative charge rule (BR-RAT-043, OQ-055 CLOSED), so this is
    reachable rather than hypothetical. §7 makes the buckets CREDITS and the
    ledger cannot take a negative amount at all (B2 §2 `CHECK (amount >= 0)`),
    so the only two moves are to flip the side and post the absolute value — a
    money rule nobody signed — or to refuse. It refuses.

    The test names the OQ, so the day the PO rules it, this case is the first
    thing that has to change.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)
        # A −100.00 discount on the electric usage line's own GL, and the header
        # moved with it so the bill still foots: the ONLY thing wrong is the
        # sign of one bucket.
        from apps.tenancy import models as tenancy_models

        models.InvoiceLine.objects.create(
            tenant=brazos,
            invoice=draft,
            account=account,
            service=tenancy_models.Service.objects.get(code="electric"),
            kind="usage",
            description="Goodwill discount",
            amount=Decimal("-100.00"),
            taxable=True,
        )
        draft.total = SUBTOTAL - Decimal("100.00")
        draft.save(update_fields=["total"])

        with pytest.raises(BillingRuleError, match="OQ-152") as refusal:
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
                actor=dana,
            )
        assert issue._reason_for(refusal.value) == issue.ISSUE_POSTING_NEGATIVE_BUCKET
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT
        assert not journal_entries(brazos).exists()


def test_us_bil_009_tc9__a_fee_line_still_blocks_the_bill_so_4200_is_unreachable(brazos, dana):
    """§7's ninth bucket (4200 late fee 5.00) cannot be posted, and WHY.

    Not a stage-7 limitation: BR-BIL-010 gives every charge code its own GL and
    a priced fee line names no `charge_id`, so the STAMP refuses and the bill
    never reaches stage 7 at all. Asserted rather than described, so this file
    goes RED the day `charge_id` reaches a priced line — which is the day
    someone should extend `tc2`'s fixture to all nine buckets.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)
        models.InvoiceLine.objects.create(
            tenant=brazos,
            invoice=draft,
            account=account,
            kind="fee",
            description="Late fee",
            amount=Decimal("5.00"),
            taxable=False,
        )
        draft.total = SUBTOTAL + Decimal("5.00")
        draft.save(update_fields=["total"])

        with pytest.raises(BillingRuleError, match="names no charge code"):
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
                actor=dana,
            )
        assert not journal_entries(brazos).exists()


def test_us_bil_009_tc10__the_run_counts_entries_the_way_it_counts_queue_rows(brazos, dana):
    """BR-BIL-055 — three bills, one broken; the counters tell the true story.

    `posted + already_posted == len(issued)` is a property of every pass, and it
    is what makes "480 bills issued" and "480 entries in the books" the same
    morning rather than two claims nobody compared.
    """
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        good_one = a_priced_draft(
            brazos, an_account(dana, brazos, account_no="A-2041"), run, invoice_no="BL-2607-000301"
        )
        broken = a_priced_draft(
            brazos,
            an_account(dana, brazos, account_no="A-2042"),
            run,
            invoice_no="BL-2607-000302",
        )
        broken.total = SUBTOTAL + Decimal("1.00")  # does not foot — refused at stage 7
        broken.save(update_fields=["total"])
        good_two = a_priced_draft(
            brazos, an_account(dana, brazos, account_no="A-2043"), run, invoice_no="BL-2607-000303"
        )

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        assert set(result.issued) == {str(good_one.pk), str(good_two.pk)}
        assert result.posted == 2 and result.already_posted == 0
        assert result.posted + result.already_posted == len(result.issued)
        assert [problem.reason for problem in result.broken] == [issue.ISSUE_POSTING_UNBALANCED]
        assert journal_entries(brazos).count() == 2
        # The break is a DRAFT still, with nothing of it in the books.
        assert models.Invoice.objects.get(pk=broken.pk).status == models.INVOICE_DRAFT


def test_us_bil_009_tc11__the_result_no_longer_claims_the_handoff_is_unemitted(brazos, dana):
    """Hard-won law 1, as a test: the absence list must not describe a done thing.

    `ISSUE_UNAVAILABLE` carried `posting_handoff_not_emitted` on every result
    until this lane. A reader — or a caller — that still saw that code would
    conclude the books were empty. The code is asserted GONE and its successor
    asserted present, because a docstring correction that a gate cannot read is
    exactly the failure law 1 is about.
    """
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        codes = {row["code"] for row in result.unavailable}
        assert "posting_handoff_not_emitted" not in codes
        assert "posting_emitted_without_the_us_led_002_dimensions" in codes
        # And what the seam itself still cannot say travels with it.
        seam_codes = {row["code"] for row in posting_seam.POSTING_UNAVAILABLE}
        assert "premises_and_unit_dimensions_not_resolved" in seam_codes
        assert "prior_balance_and_total_due_are_not_posted" in seam_codes


def test_us_bil_009_tc12__billing_writes_no_journal_line_of_its_own(brazos, dana):
    """CLAUDE.md rule 5, asserted rather than promised.

    Every journal row that exists after an issue was written by
    `apps.ledger.posting.post` — so if the seam cannot reach it, NOTHING lands.
    Making the owner unresolvable is the same deployment shape `tc24` of the
    issue suite uses for the GL map: a host where W5 has not been migrated.

    A billing path that had quietly kept its own writer would sail straight
    through this and leave rows behind.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-06|cycle-9")
        from tests.test_us_bil_005_release_gate import a_release

        a_release(brazos, run, dana)
        draft = a_priced_draft(brazos, account, run, invoice_no="BL-2607-000401")

        import apps.billing.posting_seam as seam

        original = seam._resolve
        try:
            seam._resolve = lambda module, attribute, kind: (
                None if kind == seam.POSTING_KIND else original(module, attribute, kind)
            )
            with pytest.raises(BillingRuleError, match="publishes no"):
                issue.issue_invoice(
                    draft,
                    issued_at=ISSUED_AT,
                    template_id=TEMPLATE_ID,
                    template_version=TEMPLATE_VERSION,
                    actor=dana,
                )
        finally:
            seam._resolve = original

        assert not ledger_models.JournalLine.objects.filter(tenant=brazos).exists()
        assert not journal_entries(brazos).exists()
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT


# ═══════════════════════════════════════════════════════════════════════════
# tc13 — US-LED-001's *"First-bill deposit line"* row (added 2026-08-16,
# DEF-181): the deposit lands in the LIABILITY bucket, never in revenue
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_009_tc13__a_deposit_line_credits_the_deposit_liability_never_revenue(brazos, dana):
    """US-LED-001's contract table: *"First-bill deposit line | (within issue
    entry) | **deposit liability — never revenue**"* (BR-BIL-012, WE-6).

    ⚠ **THIS IS THE CASE `tc9` DESCRIBES AND IS NOT THE SAME CASE.** Until
    2026-08-16 the first bill's security deposit arrived as `kind="fee"`, so it
    hit the branch `tc9` asserts and **no first bill carrying a deposit could
    issue at all** — refused with a message about a missing charge code, on a
    line that is not a charge. `tc9` still holds for a real fee (a late fee does
    name a charge code the seam does not carry); a DEPOSIT never had one to
    carry, because its account comes from a designation.

    ❄️ WE-6's own figure: Residential Standard asks **150.00**. The bill's AR
    debit rises by it and the credit lands in **2300 customer deposit
    liability** — the utility is holding the customer's money, and a version of
    this that credited revenue would recognise somebody else's deposit as
    income on a record that can never be edited (hard rule 4).
    """
    deposit = Decimal("150.00")
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)
        models.InvoiceLine.objects.create(
            tenant=brazos,
            invoice=draft,
            account=account,
            kind="deposit",
            description="Security deposit",
            amount=deposit,
            taxable=False,
        )
        draft.total = SUBTOTAL + deposit
        draft.save(update_fields=["total"])

        issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        entry = journal_entries(brazos).get()
        totals = journal_totals(brazos, entry)
        assert credit_of(totals, "2300") == deposit
        # And it is NOT in any revenue bucket — the half of the rule that costs
        # money to get wrong. 4100/4105/4110/4115 hold the priced draft's own
        # lines and not one cent of the deposit.
        revenue_credited = sum(
            (credit_of(totals, code) for code in ("4100", "4105", "4110", "4115")), Decimal("0")
        )
        assert revenue_credited == SUBTOTAL
        # The entry still balances against the AR debit, deposit included.
        assert debit_of(totals, "1200") == SUBTOTAL + deposit


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-009@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-02-invoice-gl.md US-BIL-009 §1/§7 + EP-BIL-01-bill-run.md
#         US-BIL-005 §7 · 07-billing/02-business-rules.md · 03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (stage-7 posting-handoff lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — no billing endpoints yet) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · FOUR MUTATIONS PROVED RED before any green was trusted
#         (hard-won law 7) — the handoff not emitted, an unbalanced handoff
#         accepted, a double-issue posting twice, and a posting failure NOT
#         rolling the issue back; every measured failure is quoted verbatim in
#         12-governance/09-human-review-ledger.md
# exceptions: (1) FIVE OF §7's NINE BUCKETS ARE NOT ASSERTED and the module
#         docstring says which and why — three services the fixture tenant does
#         not sell (OQ-115), and the late-fee bucket, which `tc9` asserts is
#         unreachable because a priced fee line names no charge code. That last
#         one goes RED the day it is fixed, which is the point of asserting it.
#         (2) THE BOOK DATE (`tc7`) is a READING of US-BIL-009 §1's handoff
#         shape, not a figure §7 restates — flagged for the human review.
#         (3) NO POSTGRES-ONLY CASE HERE. The balance law has a database half
#         (ledger/0002's deferred trigger) and it is exercised by
#         tests/test_us_led_001_posting.py, which owns that fence; this file
#         asserts the SERVICE-layer refusals, which run on every vendor.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
