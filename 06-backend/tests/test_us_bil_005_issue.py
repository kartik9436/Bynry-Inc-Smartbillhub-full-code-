# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the draft becomes a bill)
#           Screens: S31 step 5 · S31 step 6 · S30
# Rules:    BR-BIL-004 (an issued bill is immutable) · BR-BIL-010 (the GL stamp
#           is at issue and frozen) · BR-BIL-023 (all remaining drafts or a
#           named subset) · BR-BIL-024 (the due date is derived) · BR-BIL-026
#           (template pinned) · BR-BIL-030 (the locked bill instance) ·
#           BR-BIL-055 (a break never blocks the run) · BR-BIL-058 (the release
#           gate is five recorded facts) · BR-BIL-063 (the number was allocated
#           at DRAFT creation — issue mints nothing) · BR-MET-009 (due =
#           bill_date + due_days) · CLAUDE.md rule 4 · rule 7 (audit)
# ───────────────────────────────────────────────────────
"""Issue: what becomes true, what becomes unchangeable, and what refuses.

WHY THESE TEST NUMBERS START AT 20. US-BIL-005's `tc1`..`tc7` are already taken
by two earlier files with meanings of their own — `test_w3_billing_models.py`
(tc1 the partial unique index, tc2 the payload round-trip) and
`test_us_bil_005_release_gate.py` (tc3..tc7 the phase-4 record). The epic's TC
numbers and this repo's test numbers parted company before this lane existed,
so rather than deepen a collision these cases are numbered from 20 and each
names the epic TC it implements in its own docstring. Inherited, not made.

THE ONE THING TO READ FIRST. Almost everything issue writes is unrepairable a
millisecond later: the moment the status leaves `draft`, the money, the dates,
the number, the template pin and the locked instance are frozen by the database
triggers themselves. So the tests that matter most here are the REFUSALS —
`tc24` (an unreachable ledger refuses the whole bill and leaves the draft
untouched), `tc27` (nothing issues without a recorded release) and `tc31` (a
tax line that names no tax refuses, because nothing may pick an authority). A
bill that issues slightly wrong cannot be edited, only credited and re-billed.

NOTHING HERE FAKES THE GL MAP. The ledger owns it (PO ruling 2026-08-11,
OQ-106 closed) and published `revenue_account_id_for_service` /
`gl_account_id_for_designation` the same day, and the provisioned fixture seeds
the finance-signed chart — so these tests stamp REAL accounts (Electric usage →
4100, base → 4105) read back from the ledger's own selector rather than from a
hardcoded uuid. The one case that substitutes anything is `tc24`, which makes
the ledger unreachable on purpose to prove the stamp refuses instead of
stamping NULL.

THE TWO GAPS THIS FILE USED TO ASSERT ARE CLOSED (2026-08-11), and both tests
were REWRITTEN rather than deleted — read them, because what they now pin is
the regression each gap would be. This paragraph used to say: *"`tc26`: stage 6
writes no `service` on its lines, so the bill the real run produces cannot be
issued. `tc31`: a tax line cannot name its authority, so a taxed bill cannot be
issued."* Both were true, and together they meant **no bill in this product
could be issued at all**. The PO closed OQ-116 (BR-BIL-069: an account per tax
authority, the line tagged with its tax, the tenant managing both), stage 6
now writes `service` and `tax` on every line, and a taxed bill issues. `tc26`
asserts the unpatched end-to-end path; `tc31` asserts the refusal that
survives — a tax line that genuinely names no tax. The three-authority bill
lives in `tests/test_br_bil_069_tax_authority_gl.py`.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import issue, models
from apps.billing.exceptions import BillingRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_release_gate import a_release
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

#: The run goes out TWO DAYS LATE, deliberately. The cycle `a_run` builds has
#: bill date 1 Jul 2026 and due-days 21 (BR-MET-009), so the derived due date is
#: 22 Jul whether the batch ran on the 1st or the 3rd. If these two dates were
#: equal the "derived from the cycle, not from the issue stamp" half of
#: BR-BIL-024 would be untestable — every wrong basis would give the right
#: answer.
ISSUED_AT = datetime(2026, 7, 3, 9, 41, tzinfo=UTC)
DUE_DATE = date(2026, 7, 22)

TEMPLATE_ID = uuid.UUID("9f0e6a52-3c14-4a7d-8f21-2b6d0c9e5a71")
TEMPLATE_VERSION = 3

#: GT-1's frozen figures, so the money in these rows is money finance signed:
#: 684 kWh × $0.12 = **82.08** usage + **18.50** base = **100.58**. The default
#: fixture carries NO tax line, which keeps every case in this file about issue
#: rather than about the GL map — it is also a real customer type (B4.2 puts
#: exemption on the account). CORRECTED 2026-08-11: this note used to say "a
#: taxed bill cannot be issued at all today"; since the PO closed OQ-116
#: (BR-BIL-069) a taxed bill issues, and the three-authority case lives in
#: `tests/test_br_bil_069_tax_authority_gl.py`.
USAGE_AMOUNT = Decimal("82.08")
BASE_AMOUNT = Decimal("18.50")
SUBTOTAL = Decimal("100.58")
TAX_TOTAL = Decimal("8.30")


def electric_gl_accounts():
    """What the LEDGER says Electric's revenue accounts are — 4100 and 4105.

    Read from `apps.ledger.selectors` rather than hardcoded, and asserted to be
    two DIFFERENT accounts, because the usage/base split is the thing the stamp
    has to get right per line. A test that hardcoded the uuids would still pass
    if billing stamped every line with the usage account.
    """
    from apps.ledger import selectors as ledger_selectors

    usage = ledger_selectors.revenue_account_id_for_service("electric")
    base = ledger_selectors.revenue_account_id_for_service("electric", base=True)
    assert usage and base and usage != base, "the seeded chart splits Electric 4100/4105"
    return usage, base


def an_unpublished_ledger(monkeypatch):
    """A deployment where the ledger has published nothing — W5 not migrated.

    The seam resolves by NAME at call time (the idiom `test_us_bil_002_gather`
    uses for rating and metering), so making `_resolve` answer None is exactly
    the state a partial deployment is in. `tc24` proves the stamp REFUSES there
    rather than stamping NULL and freezing revenue into no bucket.
    """
    monkeypatch.setattr(issue, "_resolve", lambda *args, **kwargs: None)


def a_priced_draft(tenant, account, run, *, invoice_no="BL-2607-000101", taxed=False, **overrides):
    """A draft in the shape stage 6 leaves it, built by hand.

    `service` is set on the lines here, as stage 6 also does since 2026-08-11
    (BR-BIL-069's lane). This fixture predates that and kept working unchanged;
    the note that used to stand here — *"⚠ `service` IS SET ON THE LINES HERE
    AND STAGE 6 DOES NOT SET IT"* — is now false and was removed rather than
    left to mislead. `tc26` is the case that drives the real stage 6 unpatched.

    `taxed=True` builds a tax line with NO tax behind it, which is a real state
    (a plan rule carrying a rate_override for a jurisdiction with no `taxes`
    row) and refuses at issue — `tc31`. A tax line that DOES name its tax
    resolves its authority's own 2200-series account and issues; that path is
    `tests/test_br_bil_069_tax_authority_gl.py`. The default here stays
    untaxed, which is also a real customer type (B4.2 puts exemption on the
    account).
    """
    from apps.tenancy import models as tenancy_models

    electric = tenancy_models.Service.objects.get(code="electric")
    values = dict(
        tenant=tenant,
        account=account,
        bill_run=run,
        invoice_no=invoice_no,
        service_date=date(2026, 6, 30),
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        subtotal=SUBTOTAL,
        tax_total=TAX_TOTAL if taxed else Decimal("0"),
        total=SUBTOTAL + (TAX_TOTAL if taxed else Decimal("0")),
        bill_payload={
            "account_no": account.account_no,
            "customer_name": "Sarah Chen",
            "plan": {"name": "Residential Standard", "version": 3},
        },
        payload_version=1,
    )
    values.update(overrides)
    invoice = models.Invoice.objects.create(**values)
    rows = [
        ("usage", "Electric usage 684 kWh", USAGE_AMOUNT, True),
        ("base", "Electric base charge", BASE_AMOUNT, True),
    ]
    if taxed:
        rows.append(("tax", "State + local tax 8.25%", TAX_TOTAL, False))
    for kind, description, amount, taxable in rows:
        models.InvoiceLine.objects.create(
            tenant=tenant,
            invoice=invoice,
            account=account,
            service=electric,
            kind=kind,
            description=description,
            amount=amount,
            taxable=taxable,
            quantity=Decimal("684") if kind == "usage" else None,
            unit="kWh" if kind == "usage" else None,
        )
    return invoice


def an_authorised_run(tenant, dana, *, key="2026-06|cycle-1"):
    """A run whose release gate has been passed — all four confirmations.

    Every issue in this file goes through the gate, because in the product
    every issue does (BR-BIL-058): the release record is the authorisation and
    `tc27` is the case that proves it cannot be walked around.
    """
    run = a_run(tenant, key=key)
    a_release(tenant, run, dana)
    return run


def test_us_bil_005_tc20b__the_due_date_follows_the_clerks_typed_bill_date(brazos, dana):
    """BR-BIL-070 — the ruling reaches the DUE date, not only the pricing date.

    THE DEFECT THIS PINS, which existed for a few hours and was reported rather
    than hidden. OQ-122 (*"Store what they type and use it"*) was built: the run
    stored the clerk's bill date and PRICED on it. But `_due_terms_for` still
    read `cycle__bill_date`, so the two halves of one bill disagreed — the S31
    wizard previewed **24 Aug** from the typed date while issue stamped
    **22 Aug** from the cycle's. A customer would be told one date on screen and
    a different one on the document, which is the kind of difference that
    becomes a dispute rather than a bug report.

    The lane that built BR-BIL-070 found it, could not close it (this file
    belonged to another lane at the time) and REPORTED it. This is the close.

    Worked, and it is the PO's own case: the cycle is dated **1 Jul** with 21
    due-days, the clerk types **3 Jul**, so the bill falls due **24 Jul** — not
    22 Jul, which is what the cycle alone would give.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana, key="2026-06|typed-bill-date")
        run.bill_date = date(2026, 7, 3)  # the clerk typed it; the cycle says 1 Jul
        run.save(update_fields=["bill_date"])
        draft = a_priced_draft(brazos, account, run)

        issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )

        bill = models.Invoice.objects.get(pk=draft.pk)
        assert bill.due_date == date(2026, 7, 24)
        # And the cycle's own date is still the fallback: an untyped run is
        # unchanged, which is what keeps every other case in this file true.
        assert DUE_DATE == date(2026, 7, 22)


def test_us_bil_005_tc20__a_draft_becomes_a_bill_and_its_number_does_not_move(
    brazos, dana, monkeypatch
):
    """Epic TC-1 — everything issue makes true, in one pass.

    The assertion people will not expect is `invoice_no`: it is the SAME string
    before and after. BR-BIL-063 (PO ruling 2026-08-11) allocates the number
    when the draft is created — *"Give a running number always even for Draft"*
    — so issue mints nothing. A re-mint here would hand the customer a number
    that does not match the one on the draft the clerk approved, and would burn
    a second number out of the tenant's series for one bill.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)
        payload_before = dict(draft.bill_payload)

        issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )

        bill = models.Invoice.objects.get(pk=draft.pk)
        assert bill.status == models.INVOICE_ISSUED
        assert bill.issued_at == ISSUED_AT
        assert bill.invoice_no == "BL-2607-000101"  # unchanged — issue mints nothing
        # BR-BIL-024: 1 Jul (the cycle's bill date) + 21 due-days. Derived from
        # the cycle, never typed and never taken from the issue timestamp — a
        # run that goes out late does not move the customer's terms.
        assert bill.due_date == DUE_DATE
        # BR-BIL-026: the pin a reprint renders from, forever.
        assert bill.template_id == TEMPLATE_ID
        assert bill.template_version == TEMPLATE_VERSION
        # BR-BIL-030: the locked instance is the DRAFT's — issue FREEZES it and
        # does not re-assemble it from rows that have moved.
        #
        # ⚠ AMENDED 2026-08-15 (DEF-116). This line read `assert
        # bill.bill_payload == payload_before` and it was too strong: BR-BIL-035
        # says in as many words that *"the figures are STAMPED into
        # `bill_payload` at issue (BR-BIL-030)"*, so issue ADDS the
        # balance-forward section and always was meant to. The guarantee that
        # matters is narrower and is asserted exactly: every key stage 6 wrote
        # is unchanged, byte for byte, and the ONLY thing issue added is
        # BR-BIL-035's own section. That is the difference between freezing a
        # snapshot and re-joining live rows — a customer's name, address, plan
        # and services must not move, and this proves none of them did.
        # ⚠ AMENDED AGAIN 2026-08-30 (CR-052 W2 tasks 8 and 10). The set grew by
        # three and the GUARANTEE did not: issue may still only ADD, and every
        # key stage 6 wrote is still asserted byte-identical below. The three
        # newcomers are the blocks A19 describes that the snapshot never
        # carried — `usage_history` (§1.7, twelve months of stored usage frozen
        # from BR-MET-106's grain) and `message` / `ways_to_pay` (§1.8,
        # BR-BIL-021's tenant copy, off the PINNED template version). Each is
        # stamped at ISSUE for the same reason the arrears are: they must read
        # as they stood on the bill date, not as they stand at reprint.
        # ⚠ AND AGAIN 2026-08-31 (`DEF-2865`), by five, and the guarantee is
        # STILL the same one. A19 §1.1's masthead — `utility_name`,
        # `utility_address`, `utility_contact` — plus §1.2's `bill_date` and
        # `cycle`: every field in the header of the PO's own BL-2608-000048
        # printed an em-dash, because nothing wrote any of them. They are
        # stamped at ISSUE beside the arrears and the tenant's copy, for the
        # identical reason — a utility that changes its trading name next year
        # has not changed the bill it sent this year, so the bill carries what
        # was true when it was SENT. **This assertion is the one that proves
        # they are ADDED and never re-joined**: every key stage 6 wrote is still
        # byte-identical below.
        after = dict(bill.bill_payload)
        added = set(after) - set(payload_before)
        assert added == {
            "balance_forward",
            "previous_balance",
            "payments_credits",
            "total_due",
            "usage_history",
            "utility_name",
            "utility_address",
            "utility_contact",
            "bill_date",
            "cycle",
            "message",
            "ways_to_pay",
        }, "issue may only ADD the stamped-at-issue blocks to the locked instance"
        assert {key: after[key] for key in payload_before} == payload_before, (
            "a key stage 6 stamped has MOVED at issue — that is the live re-join "
            "BR-BIL-030 exists to prevent, not the BR-BIL-035 stamp"
        )
        # This account has no earlier bill, so the arrears are computed zeros
        # from a seam that ANSWERED — never the absent figures of a seam that
        # could not be reached (`test_us_bil_005_release_issue_api.py::…tc49`).
        assert after["balance_forward"]["total_due"] == "100.580000"
        assert after["balance_forward"]["currency"] == "USD"
        # BR-BIL-010: every line stamped, and stamped from the LEDGER's own
        # answer — Electric usage to 4100, Electric base to 4105. The split is
        # the ledger's rule (`base=True`), not billing's; what billing decides
        # is which question a `usage` line versus a `base` line asks.
        usage_account, base_account = electric_gl_accounts()
        stamps = {line.kind: str(line.gl_account_id) for line in bill.lines.all()}
        assert stamps == {"usage": usage_account, "base": base_account}
        # And the money is untouched by issue — it was settled at pricing.
        assert (bill.subtotal, bill.total) == (SUBTOTAL, SUBTOTAL)


def test_us_bil_005_tc21__an_issued_bill_refuses_a_second_issue(brazos, dana, monkeypatch):
    """Epic TC-6 — a double-click must not bill anyone twice.

    Two different answers to two different questions, and both are here. Asking
    to issue ONE bill that is already a bill is refused: the caller asked for
    something impossible and a cheerful return would claim work this call did
    not do. Asking to issue the RUN again is a no-op: the second pass finds no
    remaining drafts, which is where the no-duplicate guarantee actually comes
    from — not from a lock, not from a flag.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)
        issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )

        with pytest.raises(BillingRuleError, match="already issued"):
            issue.issue_invoice(
                models.Invoice.objects.get(pk=draft.pk),
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )

        again = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        assert again.issued == () and again.broken == ()
        assert models.Invoice.objects.filter(bill_run=run).count() == 1
        assert models.Invoice.objects.get(pk=draft.pk).issued_at == ISSUED_AT


def test_us_bil_005_tc22__a_named_subset_issues_and_the_run_stays_open(brazos, dana, monkeypatch):
    """Epic TC-2 — BR-BIL-023: issue = all remaining, OR a selected subset.

    The run is not closed by a subset issue: the rest stay drafts and stay
    issuable. And a bill named in the subset that is ALREADY issued comes back
    reported rather than silently dropped — a clerk who selected 100 and sees
    60 issued is owed the other 40's reason.
    """
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        drafts = [
            a_priced_draft(
                brazos,
                an_account(dana, brazos, account_no=f"A-104{n}"),
                run,
                invoice_no=f"BL-2607-00010{n}",
            )
            for n in (1, 2, 3)
        ]

        first = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            invoice_ids=(drafts[0].pk,),
        )
        assert first.issued == (str(drafts[0].pk),)
        assert first.already_issued == ()
        remaining = models.Invoice.objects.filter(bill_run=run, status=models.INVOICE_DRAFT)
        assert {row.pk for row in remaining} == {drafts[1].pk, drafts[2].pk}

        # The same subset again: nothing new issues, and the bill is REPORTED
        # as already issued rather than disappearing from the caller's count.
        second = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            invoice_ids=(drafts[0].pk,),
        )
        assert second.issued == ()
        assert second.already_issued == (str(drafts[0].pk),)

        # And an id that is not a draft of THIS run — another run's bill,
        # another tenant's (invisible under RLS), or a typo — is reported by
        # name. A subset issue that quietly returned fewer bills than it was
        # asked for would leave the missing ones for a customer to find.
        stranger = str(uuid.uuid4())
        third = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            invoice_ids=(drafts[1].pk, stranger),
        )
        assert third.issued == (str(drafts[1].pk),)
        assert [(b.reason, b.invoice_id) for b in third.broken] == [
            (issue.ISSUE_NOT_IN_RUN, stranger)
        ]


def test_us_bil_005_tc23__one_broken_bill_never_blocks_the_others(brazos, dana, monkeypatch):
    """BR-BIL-055 / BR-BIL-047 — one bill is the unit of atomicity.

    The run of 500 where number 7 fails must issue 499 and report one break.
    Here the middle draft has no locked instance (BR-BIL-030), so it cannot
    lawfully issue; the other two must be bills by the end of the pass, and the
    break must carry a code the screen can group on rather than a sentence.
    """
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        good_one = a_priced_draft(
            brazos, an_account(dana, brazos, account_no="A-1041"), run, invoice_no="BL-2607-000101"
        )
        broken = a_priced_draft(
            brazos,
            an_account(dana, brazos, account_no="A-1042"),
            run,
            invoice_no="BL-2607-000102",
            bill_payload=None,
        )
        good_two = a_priced_draft(
            brazos, an_account(dana, brazos, account_no="A-1043"), run, invoice_no="BL-2607-000103"
        )

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )

        assert set(result.issued) == {str(good_one.pk), str(good_two.pk)}
        assert len(result.broken) == 1
        assert result.broken[0].reason == issue.ISSUE_NO_PAYLOAD
        assert result.broken[0].invoice_no == "BL-2607-000102"
        # The break is a DRAFT still — it can be fixed and issued, which is the
        # whole point of not rolling the other two back.
        assert models.Invoice.objects.get(pk=broken.pk).status == models.INVOICE_DRAFT
        # And the caller is told what issue did NOT do, on every result.
        # AMENDED 2026-08-11 (delivery-queue lane): this used to require
        # `delivery_records_not_queued`, and that code is gone because the thing
        # it named is done — issue writes the queue rows now. What replaced it
        # says the narrower truth, which is the one a caller must not misread:
        # the rows were QUEUED and nothing was DISPATCHED (R4 switches email on).
        # AMENDED AGAIN 2026-08-11 (stage-7 lane): `posting_handoff_not_emitted`
        # is gone for the same reason — issue EMITS the BR-BIL-011 handoff now
        # (`posting_seam.post_bill_issue`, inside the transaction). Its successor
        # says the narrower truth: the entry is posted and the US-LED-002
        # dimensions on its lines are still unresolved.
        assert {row["code"] for row in result.unavailable} >= {
            "posting_emitted_without_the_us_led_002_dimensions",
            "delivery_queued_but_nothing_dispatched",
        }
        assert "posting_handoff_not_emitted" not in {row["code"] for row in result.unavailable}


def test_us_bil_005_tc24__an_unreachable_ledger_refuses_the_whole_bill(brazos, dana, monkeypatch):
    """US-BIL-007 TC-5 — *"issue fails atomically if any line cannot resolve a GL"*.

    The ledger owns the GL maps (PO ruling 2026-08-11, OQ-106 CLOSED) and has
    now published the two reads this stamp stands on. This case is the OTHER
    deployment: a host where W5 is not migrated, or a lane that has not landed,
    so the reads resolve to nothing.

    What must be true afterwards is the point. The draft is STILL A DRAFT —
    no due date, no pin, no issue stamp, no half-stamped lines. A line's
    `gl_account_id` freezes with its invoice, so a bill issued with an empty
    stamp is revenue in no bucket, permanently: there is no repair, only a
    credit note and a rebill. An empty answer must never become a NULL stamp.
    """
    an_unpublished_ledger(monkeypatch)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)

        with pytest.raises(BillingRuleError) as raised:
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )
        # The refusal NAMES both callables billing is waiting for, so the fix is
        # a grep away from either side of the boundary.
        assert issue.GL_REVENUE_READ in str(raised.value)
        assert issue.GL_DESIGNATION_READ in str(raised.value)

        untouched = models.Invoice.objects.get(pk=draft.pk)
        assert untouched.status == models.INVOICE_DRAFT
        assert untouched.due_date is None
        assert untouched.issued_at is None
        assert untouched.template_id is None
        assert [line.gl_account_id for line in untouched.lines.all()] == [None, None]

        # Through the run it becomes a named break the screen can group on,
        # rather than an exception that takes the whole pass down.
        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        assert result.issued == ()
        assert result.broken[0].reason == issue.ISSUE_GL_MAP_UNPUBLISHED


def test_us_bil_005_tc31__a_tax_line_that_names_no_tax_still_refuses(brazos, dana):
    """A tax line with nothing to identify it is REFUSED, and always will be.

    **REWRITTEN 2026-08-11.** This case used to be called
    `..._a_taxed_bill_cannot_issue_at_all_today` and asserted the state of the
    whole product: no `invoice_lines` column named the authority, so 2200-01 and
    2200-03 were indistinguishable from any tax line and every taxed bill
    refused. The PO closed that (OQ-116 → BR-BIL-069), the column exists, and a
    taxed bill issues — `tests/test_br_bil_069_tax_authority_gl.py::..._tc1`
    proves it end to end with three authorities and three accounts.

    What survives, and is what this case now pins, is the REFUSAL for a line
    that genuinely names no tax. It is still reachable: a plan rule may carry a
    `rate_override` for a jurisdiction with no `taxes` row behind it, so the
    rate is real and the authority is unknown. Nothing picks one — tax credited
    to the wrong authority is a filing error with a regulator on the other end
    of it, not a rounding error.

    `a_priced_draft(taxed=True)` builds exactly that line: kind `tax`, a real
    amount, `tax=None`.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run, taxed=True)

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        assert result.issued == ()
        assert result.broken[0].reason == issue.ISSUE_TAX_LINE_UNMAPPABLE
        assert "authority" in result.broken[0].detail
        # Atomic: the usage and base lines resolve perfectly well, and NONE of
        # them is stamped, because the bill is one unit (US-BIL-007 TC-5).
        stored = models.Invoice.objects.get(pk=draft.pk)
        assert stored.status == models.INVOICE_DRAFT
        assert all(line.gl_account_id is None for line in stored.lines.all())


def test_us_bil_005_tc25__issue_writes_the_audit_row_and_a_refusal_writes_none(
    brazos, dana, monkeypatch, audit_rows
):
    """CLAUDE.md hard rule 7 — issue is a money action, so it is audited.

    Both halves matter. A bill that issued without its trail row would be money
    that moved with nobody's name on it; a trail row for a bill that did NOT
    issue is worse, because it is evidence of something that never happened.
    The row is written inside the same transaction as the issue for exactly
    that reason.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)
        issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        issued_rows = [row for row in audit_rows if row["action"] == "invoice.issued"]
        assert len(issued_rows) == 1
        row = issued_rows[0]
        assert row["entity_type"] == "invoice" and row["entity_id"] == str(draft.pk)
        assert row["actor_user_id"] == dana.id
        assert row["before"]["status"] == models.INVOICE_DRAFT
        assert row["after"]["status"] == models.INVOICE_ISSUED
        assert row["after"]["invoice_no"] == "BL-2607-000101"
        assert row["after"]["due_date"] == DUE_DATE.isoformat()
        # Rule 2: the amount travels as a STRING of the stored decimal (six
        # places, as the column keeps it) with its currency beside it — never a
        # float, which is what a JSON number would have made of it.
        assert Decimal(row["after"]["total"]) == SUBTOTAL
        assert row["after"]["currency"] == "USD"
        # PII stays out of the trail (BR-AUD-006): the locked instance holds the
        # customer's name and the trail row points at the bill, not into it.
        assert "customer_name" not in row["after"]

        # A refused issue leaves no trail row claiming one happened.
        refused = a_priced_draft(
            brazos,
            an_account(dana, brazos, account_no="A-1049"),
            run,
            invoice_no="BL-2607-000109",
            bill_payload=None,
        )
        with pytest.raises(BillingRuleError):
            issue.issue_invoice(
                refused,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
                actor=dana,
            )
        assert len([r for r in audit_rows if r["action"] == "invoice.issued"]) == 1


def test_us_bil_005_tc26__the_bill_the_real_run_writes_issues(brazos, dana):
    """END TO END across the phase boundary — and it WORKS as of 2026-08-11.

    Every other case builds its own draft, which proves issue works on the draft
    issue EXPECTS. This one runs the real stage 6 (stage 1 → stage 2 → rating's
    priced pass → assemble) and issues what it actually WROTE, which is the only
    way to catch the two halves disagreeing about what a draft is.

    **REWRITTEN 2026-08-11, and the previous version is worth knowing about.**
    This test used to be called `..._cannot_be_issued_yet` and asserted a GAP:
    stage 6 wrote no `service` on the lines it created, the ledger's revenue map
    is keyed on the service, so every usage and base line of every real bill
    refused — and the product could not issue a bill at all. The old test proved
    the field was the ONLY thing missing by setting it BY HAND and watching the
    same bill issue. That hand-patch is gone because stage 6 now writes the
    field itself (BR-BIL-069's lane, alongside the tax tagging: both identities
    were missing for the same reason and were closed together).

    So this now asserts the whole path, unpatched. It goes RED if anyone
    un-wires `service` from stage 6 — which is the regression the old gap was.
    The same field is what makes per-service revenue, the PO's requirement of
    2026-08-11, computable from `invoice_lines` at all.

    Tax is left out of THIS fixture (`taxes=()`) so the case stays about the
    service half; the three-authority bill is
    `tests/test_br_bil_069_tax_authority_gl.py::..._tc1`.
    """
    from tests.test_us_bil_029_assemble import assemble, billing_data

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = assemble(brazos, account, run, billing_data(account, taxes=()))
        allocated_number = draft.invoice_no
        assert allocated_number is not None  # BR-BIL-063 — already there

        # The service is on the lines BEFORE issue, written by stage 6 itself.
        assert {line.service.code for line in draft.lines.all()} == {"electric"}

        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        usage_account, base_account = electric_gl_accounts()
        stored = models.Invoice.objects.get(pk=bill.pk)
        assert stored.status == models.INVOICE_ISSUED
        assert stored.invoice_no == allocated_number  # unchanged by issue
        assert stored.due_date == DUE_DATE
        assert stored.total == SUBTOTAL  # GT-1 without tax, unmoved by issue
        assert {line.kind: str(line.gl_account_id) for line in stored.lines.all()} == {
            "usage": usage_account,
            "base": base_account,
        }


def test_us_bil_005_tc27__nothing_issues_without_a_recorded_release(brazos, dana, monkeypatch):
    """Epic TC-14 / BR-BIL-058 — the gate cannot be walked around.

    *"Forged POST straight to issue with no release record for the run"* is the
    epic's own case. The gate is the last moment at which nothing has been
    billed, so the check belongs at the door: after it, there is no un-issuing.
    A release with one confirmation missing is not a release — that is what
    makes the four separate columns worth having.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)  # no release row at all
        draft = a_priced_draft(brazos, account, run)

        with pytest.raises(BillingRuleError, match="no authorised release"):
            issue.issue_run(
                run,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT

        # Four facts recorded, one of them false: still refused, and the run
        # remains entirely unbilled.
        a_release(brazos, run, dana, sms_mandate_confirmed=False)
        with pytest.raises(BillingRuleError, match="no authorised release"):
            issue.issue_run(
                run,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT


def test_us_bil_005_tc28__the_due_date_is_derived_and_a_bad_cycle_refuses(
    brazos, dana, monkeypatch
):
    """BR-BIL-024 / BR-MET-009 — and the two ways the derivation must refuse.

    A due date decides when a late fee starts (BR-BIL-001), so the two failure
    modes are not cosmetic: a cycle with no terms must not fall back to "today"
    or to zero days, and a negative due-days must not produce a bill that is
    overdue on the day it is sent.
    """
    assert issue.derive_due_date(date(2026, 8, 1), 21) == date(2026, 8, 22)  # the epic's own case
    with pytest.raises(BillingRuleError, match="never typed"):
        issue.derive_due_date(date(2026, 8, 1), None)
    with pytest.raises(BillingRuleError, match="due_days ≥ 0"):
        issue.derive_due_date(date(2026, 8, 1), -1)

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        run.cycle.due_days = None
        run.cycle.save(update_fields=["due_days"])
        draft = a_priced_draft(brazos, account, run)

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        assert result.issued == ()
        assert result.broken[0].reason == issue.ISSUE_NO_DUE_TERMS
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT


def test_us_bil_005_tc29__a_numberless_or_unpinned_draft_refuses(brazos, dana, monkeypatch):
    """BR-BIL-063 and BR-BIL-026 — the two facts issue can never supply itself.

    A numberless draft is refused rather than numbered here, because BR-BIL-063
    moved allocation to draft creation and a second minting point is how a
    series grows two sequences. A pin-less issue is refused because
    `template_id`/`template_version` freeze with the money: a bill that issues
    without them can never record what it was rendered with, and BR-BIL-026's
    "renders the pinned version forever" becomes unsatisfiable for that bill.
    """
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        numberless = a_priced_draft(
            brazos, an_account(dana, brazos, account_no="A-1051"), run, invoice_no=None
        )
        with pytest.raises(BillingRuleError, match="carries no number"):
            issue.issue_invoice(
                numberless,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )

        unpinned = a_priced_draft(
            brazos,
            an_account(dana, brazos, account_no="A-1052"),
            run,
            invoice_no="BL-2607-000152",
        )
        with pytest.raises(BillingRuleError, match="no template pin"):
            issue.issue_invoice(
                unpinned,
                issued_at=ISSUED_AT,
                template_id=None,
                template_version=None,
            )
        assert models.Invoice.objects.get(pk=unpinned.pk).status == models.INVOICE_DRAFT


@requires_postgres
def test_us_bil_005_tc30__the_database_refuses_what_the_trigger_does_not_permit(
    brazos, dana, monkeypatch
):
    """Epic TC-5 / CLAUDE.md hard rule 4 — the fence is the DATABASE, not the code.

    POSTGRES ONLY, and that is the whole reason this case exists separately:
    the developer database is SQLite and has no triggers, so every other test
    in this file proves the SERVICE layer's half of hard rule 4 and none of
    them proves the fence. A management command, a data fix or a queryset
    write bypasses the service layer entirely; only the trigger stops those.

    Three statements, all of which must be refused after issue: moving the
    money, rewriting the locked instance, and touching a line. The narrow door
    the trigger leaves open (a status move to paid/void/corrected) is checked
    too, because a freeze that also blocked settlement would be a different
    bug and just as expensive.
    """
    from django.db import IntegrityError, InternalError, ProgrammingError, connection, transaction

    refusals = (IntegrityError, InternalError, ProgrammingError)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run)
        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        line_id = bill.lines.first().pk

        with pytest.raises(refusals), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE invoices SET total = 0 WHERE id = %s", [str(bill.pk)])
        with pytest.raises(refusals), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE invoices SET bill_payload = '{}'::jsonb WHERE id = %s", [str(bill.pk)]
            )
        with pytest.raises(refusals), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE invoice_lines SET gl_account_id = NULL WHERE id = %s", [str(line_id)]
            )

        # The narrow door still opens: settlement must remain possible.
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE invoices SET status = 'paid' WHERE id = %s", [str(bill.pk)])
        assert models.Invoice.objects.get(pk=bill.pk).status == models.INVOICE_PAID


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane — the PO's phase 5)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — no billing endpoints yet) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the RED PROOF in this file's report and in apps/billing/issue.py's
#         trailer — every guard was mutated and shown to fail before it was
#         trusted green
# exceptions: (1) THE GL MAP IS FAKED in every case except tc24, which asserts
#         the real, unsubstituted refusal. Stated in the docstring rather than
#         left for a reader to discover, because a suite that fakes the seam
#         everywhere would look like proof that issue works end to end when the
#         ledger has published nothing.
#         (2) tc30 is the ONLY case that touches a trigger, and it SKIPS on
#         sqlite with a vendor reason. Everything else here proves the service
#         layer's half of hard rule 4; the database's half is Postgres-only and
#         is not implied anywhere else in this file.
#         (3) CORRECTED 2026-08-11 (stage-7 lane). This entry read "NOT COVERED,
#         deliberately: the posting handoff (BR-BIL-011), the delivery queue rows
#         (BR-BIL-016) and the pre-issue render (BR-BIL-033). None is built" —
#         and ALL THREE are built now, each inside the issue transaction. They
#         are not covered HERE because each has its own suite:
#         tests/test_us_bil_009_posting_handoff.py (BR-BIL-011),
#         tests/test_us_bil_023_delivery_queue.py (BR-BIL-016) and
#         tests/test_us_bil_022_documents.py (BR-BIL-033). `ISSUE_UNAVAILABLE`
#         now names what each still cannot do rather than that it does not run,
#         and tc23 asserts the caller is told.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
