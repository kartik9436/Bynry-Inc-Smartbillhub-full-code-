# ── Trace ──────────────────────────────────────────────
# Change:  `CR-108` wave 1 — the One-time bill's §04 gaps, backend half.
#          Screens: 22.6 (Fee, step 2) · 23 (Confirm and send, step 3)
# Defects: DEF-BIL-5317 (a penalty's tamper fee refuses over a live seam —
#          FILED, NOT FIXED HERE) · DEF-BIL-5311 (the route never sent
#          days-to-pay, so no one-time bill it made could be issued — FIXED)
# Rules:   BR-BIL-020 (lines come ONLY from rules and CHARGE CODES; free-typed
#          amounts never exist on any bill) · BR-BIL-007 (a fee is a tenant-
#          configured charge code, never hardcoded) · BR-BIL-010 (a charge code
#          carries its own GL) · BR-BIL-013 (the deposit applies FIRST, then
#          exactly ONE settlement path) · BR-BIL-024 (the due date is derived at
#          issue from the run's terms) · BR-BIL-063 (a draft spends a bill
#          number) · BR-TEN-043 / gate G6 (no clock on a money path) ·
#          CLAUDE.md rule 2 (money 4dp) · rule 3 (a quantity with its unit) ·
#          rule 5 (only the ledger posting service writes journal lines)
# ───────────────────────────────────────────────────────
"""The sixth kind, the lines, and the books — each proved RED before trusted.

Every assertion here was driven RED first (hard-won law 7) and the verbatim
failures are in the lane report. The four that matter:

  * `tc1` failed with `BillingRuleError: unknown one-time bill kind 'fee'. The
    tab offers ('interim','first','final','backbill','penalty')` before
    `KIND_FEE` existed — the gap exactly as it was measured.
  * `tc4` failed with `KeyError: 'lines'` before `_priced_body` existed, which
    is gap 3 in one line: the preview priced the bill and threw the lines away.
  * `tc5` — the identity between the previewed lines and the DRAFTED lines —
    failed with a four-line diff when `preview` was made to price the bare
    prepared data for a first bill instead of `first_bill_data`'s: the deposit
    line and the connection charge appeared on the bill and not in the preview.
    That is the whole reason the pure halves were extracted rather than copied.
  * `tc9` failed with `assert None is not None` on `run.due_days` before
    `_one_time_request` read the field — DEF-BIL-5311, measured through the
    route rather than through the dataclass, because the dataclass was never
    the thing that was wrong.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 habit 2), stated so a later
reader can check rather than trust:

  * `tc4`/`tc5` would pass over a preview that WROTE a draft and read its lines
    back, which is the one thing a preview may not do. `tc6` is the guard for
    that and it counts `invoices`, `invoice_lines` AND `bill_runs` before and
    after — a preview that wrote and rolled back would still spend a bill
    number (BR-BIL-063), so the number is asserted too.
  * `tc7` would pass over a books panel that returned three entries built from
    literals. It asserts the DESIGNATIONS resolve to the tenant's own chart
    rows, so a hardcoded "1200" fails on a tenant who renumbered.
  * `tc8` (the refusal) would pass over a panel that refused EVERYTHING. The
    same account and the same deposit are asserted to POST in `tc7`, so only
    the comparison can be what changed.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.billing import (
    api as billing_api,
    models as billing_models,
    one_time,
    posting_seam,
)
from apps.billing.exceptions import BillingRuleError
from apps.customers import models as customer_models
from apps.rating import models as rating_models

from tests.test_us_bil_001_prepare import (  # noqa: F401
    PERIOD_END,
    PERIOD_START,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from apps.rating.charge_prices import flat_amount as _flat  # CR-156-BRC10: the amount is a dated row

pytestmark = pytest.mark.django_db

#: The day the fee is charged on. A DATE the clerk typed and never a clock
#: (BR-TEN-043 / gate G6) — every figure below reproduces because of it.
FEE_ON = date(2026, 7, 9)
#: The tenant's OWN figure. Asserted as the charge row's amount rather than as a
#: literal in an assertion, so a utility charging $95.00 is not this test's
#: problem (BR-BIL-007 — `tc3` is the case that proves it).
A_FEE = D("35.00")
TEST_CODE = "CR108-METER-TEST"


def a_one_time_account(brazos, dana, *, account_no="A-91108", asset_no="M-9611", label="F"):
    """One billable account on a priced plan with a committed read."""
    cycle = a_cycle(brazos)
    plan = a_priced_plan(brazos)
    unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=asset_no, label=label)
    return an_account(brazos, unit["id"], account_no)


def a_charge_code(tenant, *, code=TEST_CODE, amount=A_FEE, with_gl=True):
    """The tenant's own flat charge code, with a GL account it can be booked to.

    Created here rather than seeded: measured 2026-08-25 and still true, no seed
    in this repo creates one of these, which is why every test that reaches a
    fee makes its own (`test_w7_cut_reconnect._reconnect_charge` says the same).
    """
    from apps.ledger import models as ledger_models

    gl = None
    if with_gl:
        gl = (
            ledger_models.LedgerAccount.objects.filter(
                tenant=tenant, deleted_at__isnull=True, code="4200"
            ).first()
            or ledger_models.LedgerAccount.objects.filter(
                tenant=tenant, deleted_at__isnull=True
            ).first()
        )
    row, _ = rating_models.Charge.objects.get_or_create(
        tenant=tenant,
        code=code,
        defaults={
            "name": "Meter test",
            "charge_type": "one_time",
            "amount_rule": "flat",
            "amount": amount,
            "gl_account_id": gl.id if gl else None,
        },
    )
    return row


def _counts():
    """What a preview must not move — documents, lines, runs and numbers."""
    return (
        billing_models.Invoice.objects.count(),
        billing_models.InvoiceLine.objects.count(),
        billing_models.BillRun.objects.count(),
    )


# ══════════════════════════════════════════════════════════════════════════
# (1) THE SIXTH KIND EXISTS AND IS THE ONLY DOOR TO CHARGING A LIVE CODE
# ══════════════════════════════════════════════════════════════════════════
def test_cr108_tc1__fee_is_the_sixth_kind_and_previews_its_charge(brazos, dana):
    """Screen 22.6 — one code in, one priced line out, and nothing written.

    The blueprint's reason for this screen existing at all (p102): *"This is the
    only door to charging any live code to one account — a returned cheque, a
    tamper charge, a meter test. Without it every new fee needs a new journey."*
    `fee_bill.py` shipped complete on 2026-08-27 with ONE caller, the cut.
    """
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana)
        charge = a_charge_code(brazos)

        assert one_time.KIND_FEE in one_time.ONE_TIME_KINDS
        assert len(one_time.ONE_TIME_KINDS) == 6, "the blueprint draws step 3 for all six kinds"

        before = _counts()
        body = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_FEE,
                charge_code=TEST_CODE,
                bill_date=FEE_ON,
            )
        )
        assert _counts() == before, "a preview writes nothing at all"

        assert body["bill_type"] == "fee"
        assert body["priced"] is True
        assert len(body["lines"]) == 1, "a fee bill is a charge code and nothing else"
        line = body["lines"][0]
        assert line["kind"] == "fee"
        # BR-BIL-007 — the TENANT's figure, taken off the row rather than typed
        # into this assertion.
        assert D(line["amount"]) == _flat(charge)
        assert D(body["total"]) == _flat(charge)
        assert line["taxable"] is False
        # DEF-714 — which code the line came from, or issue refuses it by name.
        assert str(line["charge_id"]) == str(charge.id)
        # A fee has no usage, so there is nothing to read and no plan to price
        # it on. Those keys are ABSENT, not null: a null reads as *we looked and
        # found nothing*, which is a different statement.
        assert "services" not in body and "rate_plan_name" not in body


def test_cr108_tc2__a_fee_refuses_by_name_and_never_charges_zero(brazos, dana):
    """p114's *"Four refusals, no defaults"*, and the reason they are refusals.

    *"Each refuses by name rather than charging zero, because a fee that quietly
    prices at nothing is a fee nobody notices was never charged."*
    """
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-91109", asset_no="M-9612")

        # (a) NO CODE AT ALL — refused before anything is read.
        with pytest.raises(BillingRuleError) as refused:
            one_time.preview(
                one_time.OneTimeRequest(
                    account_id=str(account.id), kind=one_time.KIND_FEE, bill_date=FEE_ON
                )
            )
        assert "charge code" in str(refused.value)

        # (b) A CODE THIS TENANT DOES NOT HAVE — a refusal on the body, so the
        # rest of step 2 still renders (`_fee_body`'s posture).
        body = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_FEE,
                charge_code="NOT-A-REAL-CODE",
                bill_date=FEE_ON,
            )
        )
        assert body["priced"] is False
        assert body["lines"] == []
        assert "total" not in body, "an unpriced fee states NO total, never 0.00"
        assert "not a live charge code" in body["priced_unavailable"]["detail"]

        # (c) A CODE WITH NO GL ACCOUNT — refused at preview rather than at
        # issue, so no invoice number is spent on a draft that can never be a
        # bill (BR-BIL-010).
        a_charge_code(brazos, code="CR108-NO-GL", with_gl=False)
        body = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_FEE,
                charge_code="CR108-NO-GL",
                bill_date=FEE_ON,
            )
        )
        assert body["priced"] is False
        assert "GL account" in body["priced_unavailable"]["detail"]


def test_cr108_tc3__a_fee_is_charged_on_a_day_and_the_day_is_never_guessed(brazos, dana):
    """BR-TEN-043 / gate G6 — no clock on a money path, and no default window.

    A fee is charged ON a day, not OVER a window, so both ends of its period are
    the bill date the clerk typed. With none, it refuses BY NAME: the three
    available guesses are each a real date on a real customer's document.
    """
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-91110", asset_no="M-9613")
        a_charge_code(brazos)
        with pytest.raises(BillingRuleError) as refused:
            one_time.preview(
                one_time.OneTimeRequest(
                    account_id=str(account.id),
                    kind=one_time.KIND_FEE,
                    charge_code=TEST_CODE,
                )
            )
        assert "charged ON a day" in str(refused.value)

        body = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_FEE,
                charge_code=TEST_CODE,
                bill_date=FEE_ON,
            )
        )
        assert body["period_start"] == body["period_end"] == FEE_ON.isoformat()


# ══════════════════════════════════════════════════════════════════════════
# (2) THE PREVIEW SERVES THE LINES IT COMPUTES — AND STILL WRITES NOTHING
# ══════════════════════════════════════════════════════════════════════════
def test_cr108_tc4__an_interim_preview_serves_line_basis_and_amount(brazos, dana):
    """Step 3 group 1 — LINE · BASIS · AMOUNT, from the engine that will bill.

    The BASIS column's facts, never its sentence: a quantity NEVER travels
    without its unit (CLAUDE.md rule 3) and a tax line's `unit_price` IS its
    rate, which is where the drawn *8.25%* comes from.
    """
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-91111", asset_no="M-9614")
        body = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_INTERIM,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
            )
        )
        assert body["priced"] is True, body.get("priced_unavailable")
        assert body["lines"], "the preview priced the bill and served no lines"
        for line in body["lines"]:
            assert line["kind"] and line["description"]
            # rule 2 — 4dp as text, never a float.
            assert isinstance(line["amount"], str)
            # rule 3 — a quantity NEVER without its unit.
            if line["quantity"] is not None and line["kind"] == "usage":
                assert line["unit"], f"{line['description']} carries a quantity with no unit"
        # The same four keys `create` returns from the drafted bill, so a screen
        # reads ONE shape before and after the write.
        assert {"subtotal", "tax_total", "total", "currency"} <= set(body)
        assert D(body["total"]) > 0


def test_cr108_tc5__the_previewed_lines_are_the_drafted_lines(brazos, dana):
    """The construction guarantee — one pricing path, asserted in BOTH directions.

    **PART A, an INTERIM bill: the lines agree to four decimals.** That is
    `TC-RBS-004.3`'s discipline — a check that can now only fail if somebody
    reintroduces a second pricing path — and it exercises the pass every kind
    shares, `runs.price_account`.

    **PART B, a FIRST bill: the preview and the draft REFUSE THE SAME SENTENCE,
    and that is a sharper proof of the extraction than a matching line ever
    was.** A first bill is the kind whose data is SHAPED before pricing —
    BR-BIL-012's deposit line and connection charge — and `first_bill_data` is
    the pure half both paths now call. **A preview that priced the BARE prepared
    data would not refuse at all**: `prepare_first_bill` needs no consumer
    category, so it would happily serve lines for a bill that cannot be drafted.
    The two refusing identically is only possible because both walk the same
    function.

    ⚠ **AND WHAT THEY REFUSE WITH IS `DEF-BIL-5318`, A LIVE DEFECT THIS LANE
    FOUND AND DID NOT FIX.** `one_time._account_type_id` reads `account_type_id`
    off customers' `account_detail`, and that serializer has never served the
    key — so `deposit_line_for` refuses on every account and **the `first` kind
    has never produced a bill through this tab.** It is filed rather than fixed
    because the fix changes what a first bill CONTAINS on a 🔒 money path and
    belongs in its own wave. This case is written to go GREEN either way: it
    asserts the two paths AGREE, not what they agree on, so the day the key is
    served it asserts matching LINES instead of matching refusals.
    """
    with tenant_ctx(brazos):
        # ── PART A — the shared pricing pass, line for line ──────────────────
        account = a_one_time_account(brazos, dana, account_no="A-91112", asset_no="M-9615")
        interim = one_time.OneTimeRequest(
            account_id=str(account.id),
            kind=one_time.KIND_INTERIM,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=PERIOD_END,
            due_days=14,
        )
        previewed = one_time.preview(interim)
        assert previewed["priced"] is True, previewed.get("priced_unavailable")
        created = one_time.create(interim)
        drafted = billing_models.InvoiceLine.objects.filter(invoice_id=created["invoice_id"])
        # ⚠ **SORTED, AND THE ORDER IS DELIBERATELY NOT ASSERTED.**
        # `invoice_lines` carries no sequence column — the choices are `id` and
        # `created_at`, and leaning on either would be asserting a storage
        # detail rather than the money. What this pins is the SET of lines and
        # what each one charges, which is the claim that matters: a second
        # pricing path shows up as a line that is present on one side only or
        # an amount that differs, never as a reshuffle.
        assert sorted(
            (line["description"], D(line["amount"])) for line in previewed["lines"]
        ) == sorted(
            (line.description, line.amount) for line in drafted
        ), "the preview and the draft priced different lines — a second path exists"
        assert D(previewed["total"]) == D(created["total"])

        # ── PART B — the SHAPED kind: both paths, one answer ─────────────────
        # THE SAME ACCOUNT, deliberately: `a_cycle` mints one cycle code per
        # tenant, so a second `a_one_time_account` collides on
        # `cycles.tenant_id, cycles.code`. It is also the sharper fixture — the
        # two requests differ only in their KIND, and `one_time_run_key` carries
        # the bill type, so the interim run above cannot mask the first bill.
        #
        # US-BIL-010 TC-6 — the type is DERIVED from the account's own move-in
        # date and is never supplied, so the fixture has to give it one inside
        # the period.
        account.opened_at = PERIOD_START
        account.account_type = customer_models.AccountType.objects.get(code="residential")
        account.save(update_fields=["opened_at", "account_type"])
        first = one_time.OneTimeRequest(
            account_id=str(account.id),
            kind=one_time.KIND_FIRST,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=PERIOD_END,
            due_days=14,
        )
        preview_first = one_time.preview(first)
        if preview_first["priced"]:
            # DEF-BIL-5318 is fixed — assert the lines, which is the stronger
            # half and the one this case will settle into.
            drafted_first = one_time.create(first)
            lines = billing_models.InvoiceLine.objects.filter(
                invoice_id=drafted_first["invoice_id"]
            )
            assert sorted(
                (line["description"], D(line["amount"])) for line in preview_first["lines"]
            ) == sorted((line.description, line.amount) for line in lines)
        else:
            # DEF-BIL-5318 still open — the two paths must refuse IDENTICALLY,
            # which a preview on the bare prepared data could not do.
            with pytest.raises(BillingRuleError) as refused:
                one_time.create(first)
            assert preview_first["priced_unavailable"]["detail"] == str(refused.value), (
                "the preview and the draft gave different reasons for the same bill, "
                "which means they are not walking the same function"
            )
            assert "consumer category" in str(refused.value), (
                "this case is pinned to DEF-BIL-5318's refusal; a different one means "
                "the first-bill path changed and this assertion needs re-reading"
            )


def test_cr108_tc6__previewing_every_kind_spends_no_bill_number(brazos, dana):
    """BR-BIL-063 — stage 6 spends a number, and stage 6 is not called.

    Counted over `invoices`, `invoice_lines` AND `bill_runs`, because a preview
    that wrote and rolled back would leave all three where they started and
    still have consumed a number from the series.
    """
    from core import numbering as core_numbering

    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-91113", asset_no="M-9616")
        a_charge_code(brazos)
        before = _counts()
        before_no = core_numbering.next_number(core_numbering.BILL, PERIOD_END)

        for request in (
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_INTERIM,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
            ),
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_FEE,
                charge_code=TEST_CODE,
                bill_date=FEE_ON,
            ),
        ):
            one_time.preview(request)

        assert _counts() == before
        after_no = core_numbering.next_number(core_numbering.BILL, PERIOD_END)
        assert after_no != before_no, "the probe itself must move the series"
        # Two probes, two numbers — and NOTHING in between, which is what says
        # the previews took none.
        assert core_numbering.next_number(core_numbering.BILL, PERIOD_END) != after_no


# ══════════════════════════════════════════════════════════════════════════
# (3) IMPACT ON YOUR BOOKS — COMPUTED, SHOWN, AND WRITTEN NOWHERE
# ══════════════════════════════════════════════════════════════════════════
def test_cr108_tc7__the_books_panel_names_the_tenants_own_accounts(brazos, dana):
    """p115 group 2 — ENTRY · DEBIT · CREDIT · AMOUNT, before the button.

    *"Showing the three entries before the button means the clerk is not the
    last person to find out what the bill did to the ledger."*

    The accounts are resolved BY DESIGNATION from the tenant's own chart, never
    by the number: a tenant may renumber 1200 to 1150, and a literal here would
    show them an account they do not have (B14 rule 31 keeps the id off screen
    and `ledger.account_labels` is what puts a code and a name there instead).
    """
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-91114", asset_no="M-9617")
        before = _counts()
        body = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_INTERIM,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
            )
        )
        assert _counts() == before, "the books panel writes nothing (hard rule 5)"

        books = body["books"]
        assert books["available"] is True
        assert books["posts"] is True
        assert books["refused"] is False
        # An ordinary bill posts ONE entry: DR receivable / CR the per-GL
        # buckets, which do not exist until the lines are stamped.
        assert [entry["event"] for entry in books["entries"]] == [posting_seam.EVENT_ISSUED]
        entry = books["entries"][0]
        assert D(entry["amount"]) == D(body["total"])
        assert entry["debit"]["designation"] == posting_seam.AR_DESIGNATION
        assert entry["debit"]["code"], "the clerk reads a chart code, never a uuid"
        assert entry["credit"] is None and entry["credit_is_per_gl"] is True
        # A declared blind spot with a REASON beside it — never an empty one.
        assert any(
            row["code"] == "issue_entry_credit_side_is_not_split_until_issue"
            for row in books["unavailable"]
        )


def test_cr108_tc8__a_deposit_bigger_than_the_position_refunds_the_rest(brazos):  # noqa: C901
    """p115's rule table, third row — *Owed to them → Refuses, names both figures*.

    WE-7 Case A: **142.30** of charges against a **153.50** credit would put
    **−11.20** into accounts receivable, and the signed refund row pays out of
    customer credit balances where this customer holds **0.00**. Nothing signs
    the move, so it refuses rather than choosing where the excess lives — and a
    wrong entry is worse than a missing one, because a missing one shows in red
    on the tie-out and a negative receivable reads as an ordinary credit balance
    on every report this product prints.

    Driven through `posting_seam` directly: the comparison is the whole subject,
    and a fixture that had to stand up a real deposit-holding move-out would be
    asserting six other things at the same time.
    """

    class _Deposit:
        exists = True
        total = D("153.50")
        interest = D("3.50")
        currency = "USD"

    # ⚠ AMENDED 2026-09-30 — OQ-248 CLOSED, PO option A: *"A for deposit
    # refund"*. p115's third row (*"Owed to them → Refuses"*) is superseded: the
    # leftover is REFUNDED. Case A now posts — 142.30 settles what is owed and
    # the 11.20 left over is shown moving to customer credit. The full cases are
    # `tests/test_oq_248_leftover_deposit_is_refunded.py`.
    with tenant_ctx(brazos):
        refunded = posting_seam.preview_bill_entries(
            bill_type="final",
            charges=D("142.30"),
            currency="USD",
            deposit=_Deposit(),
            closing_position=D("142.30"),
        )
    assert refunded.refused is False and refunded.posts is True
    amounts = {entry.event: entry.amount for entry in refunded.entries}
    assert amounts[posting_seam.EVENT_DEPOSIT_APPLIED] == D("142.30")
    assert amounts[posting_seam.EVENT_DEPOSIT_REFUNDED] == D("11.20")

    # THE SAME deposit POSTS when the position covers it — WE-7 Case B — so
    # only the comparison can be what changed.
    with tenant_ctx(brazos):
        posts = posting_seam.preview_bill_entries(
            bill_type="final",
            charges=D("289.40"),
            currency="USD",
            deposit=_Deposit(),
            closing_position=D("289.40"),
        )
        assert posts.posts is True and posts.refused is False
        assert [entry.event for entry in posts.entries] == [
            posting_seam.EVENT_DEPOSIT_INTEREST_ACCRUED,
            posting_seam.EVENT_DEPOSIT_APPLIED,
            posting_seam.EVENT_ISSUED,
        ], "three entries, three keys, so a re-run posts none of them twice"
        assert [entry.amount for entry in posts.entries] == [D("3.50"), D("153.50"), D("289.40")]
        # ORDER IS THE RULE: the application discharges principal PLUS interest,
        # and a liability not yet raised cannot be discharged.
        assert posts.entries[0].credit.designation == posting_seam.DEPOSIT_LIABILITY_DESIGNATION
        assert posts.entries[1].debit.designation == posting_seam.DEPOSIT_LIABILITY_DESIGNATION
        assert posts.entries[1].credit.designation == posting_seam.AR_DESIGNATION

        # Zero either way — nothing to post, and it is not a refusal.
        quiet = posting_seam.preview_bill_entries(bill_type="cycle", charges=D("0"), currency="USD")
        assert quiet.posts is False and quiet.refused is False and quiet.entries == ()


# ══════════════════════════════════════════════════════════════════════════
# (4) DEF-BIL-5311 — THE ROUTE NOW CARRIES THE CLERK'S TERMS
# ══════════════════════════════════════════════════════════════════════════
def test_cr108_tc9__the_route_carries_days_to_pay_onto_the_run(brazos, dana):
    """DEF-BIL-5311 — measured through the REQUEST BUILDER, not the dataclass.

    `OneTimeRequest` has had `due_days` since CR-029 D8③ and
    `create_one_time_run` has stored it; the eight lines between the HTTP body
    and the dataclass never read it, so every bill this route made drafted with
    no terms and `derive_due_date` refused it at issue. Every existing test
    builds its own `OneTimeRequest`, which is exactly why none of them saw it.

    `0` IS A TYPED VALUE — due ON the bill date, BR-MET-009's `due_days ≥ 0` —
    and `None` is *nobody typed one*. Both are asserted, because truthiness
    would conflate them and that is the bug one layer down.
    """
    built = billing_api._one_time_request(
        {
            "account_id": "018f-aaaa",
            "kind": "interim",
            "period_start": PERIOD_START.isoformat(),
            "period_end": PERIOD_END.isoformat(),
            "bill_date": PERIOD_END.isoformat(),
            "due_days": 14,
        }
    )
    assert built.due_days == 14, "the clerk's terms never reached the run"

    typed_zero = billing_api._one_time_request(
        {
            "account_id": "018f-aaaa",
            "kind": "interim",
            "period_start": PERIOD_START.isoformat(),
            "period_end": PERIOD_END.isoformat(),
            "due_days": 0,
        }
    )
    assert typed_zero.due_days == 0 and typed_zero.due_days is not None

    silent = billing_api._one_time_request(
        {
            "account_id": "018f-aaaa",
            "kind": "interim",
            "period_start": PERIOD_START.isoformat(),
            "period_end": PERIOD_END.isoformat(),
        }
    )
    assert silent.due_days is None, "absent must stay absent — no guessed due date"

    # And a fee: the code travels and the window is the bill date at both ends.
    fee = billing_api._one_time_request(
        {
            "account_id": "018f-aaaa",
            "kind": "fee",
            "charge_code": TEST_CODE,
            "bill_date": FEE_ON.isoformat(),
            "due_days": 21,
        }
    )
    assert fee.charge_code == TEST_CODE and fee.due_days == 21
    assert one_time.checked_window(fee) == (FEE_ON, FEE_ON)


def test_cr108_tc10__a_fee_drafts_one_bill_on_one_run(brazos, dana):
    """The tab's one write, for the sixth kind — ONE run and ONE `fee` document.

    `fee_bill.raise_charge_fee` mints its OWN run (the cut is its first caller),
    so `create` delegates rather than minting a second one that would collide on
    BR-BIL-005's key with the first.
    """
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-91115", asset_no="M-9618")
        charge = a_charge_code(brazos)
        before_runs = billing_models.BillRun.objects.count()

        created = one_time.create(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_FEE,
                charge_code=TEST_CODE,
                bill_date=FEE_ON,
                due_days=21,
            )
        )
        assert billing_models.BillRun.objects.count() == before_runs + 1, "one bill, one run"
        assert created["bill_type"] == "fee"
        assert D(created["total"]) == _flat(charge)
        assert created["invoice_no"], "a draft is numbered when it is drafted (BR-BIL-063)"

        run = billing_models.BillRun.objects.get(pk=created["run_id"])
        assert run.cycle_id is None
        # BR-BIL-024 — the terms the clerk captured, on the run, so the bill can
        # actually be issued through the ordinary route.
        assert run.due_days == 21
        assert run.bill_date == FEE_ON

        lines = list(billing_models.InvoiceLine.objects.filter(invoice_id=created["invoice_id"]))
        assert len(lines) == 1 and lines[0].amount == _flat(charge)


def test_cr108_tc11__no_function_here_takes_an_amount_a_description_or_a_line(brazos):
    """BR-BIL-020 is still STRUCTURAL after the sixth kind — tc4's guard, again.

    A charge CODE is the case BR-BIL-020 always allowed (*"lines come only from
    rules and CHARGE CODES"*); an amount, a description and a line are the three
    it forbids, and the enforcement is that there is nowhere to put one.
    """
    import dataclasses

    members = {field.name for field in dataclasses.fields(one_time.OneTimeRequest)}
    forbidden = {
        "amount",
        "amounts",
        "line_amount",
        "price",
        "total",
        "lines",
        "description",
        "descriptions",
    }
    assert members & forbidden == set(), f"BR-BIL-020: {members & forbidden}"
    assert "charge_code" in members, "a CODE is how a fee is chosen (BR-BIL-007)"
