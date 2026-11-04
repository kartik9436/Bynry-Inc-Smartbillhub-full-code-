# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-4448 (the bill-ready email named no merge values) ·
#          DEF-NOT-4449 (the disconnect/dunning generator, the staff resend and
#          the two send-test buttons named none either) ·
#          DEF-PAY-4450 (the collections ladder's letters named none) ·
#          DEF-PAY-4451 (the disconnect tier composed a template code that has
#          never existed, so the letter could not render at all)
# Ruling:  PO 2026-09-07 — *"(a) Fix all of them now"*, after opening a queued
#          receipt on the live product and reading every value as an em-dash
#          (`DEF-PAY-4409`, the receipt half, already landed).
# Rules:   BR-NOT-027 (a legal document keeps all its underlying data, and the
#          rule's reach INCLUDES the bill) · BR-NOT-012 (the notification's own
#          stored render context) · BR-BIL-026 (the pin is stamped at queue
#          time and never re-resolved) · BR-BIL-030/035 (the bill's figures are
#          the LOCKED payload's) · BR-NOT-014 (the ladder selects the wording
#          BY TIER) · BR-BIL-007 (the reconnect fee is displayed, never
#          invented) · CLAUDE.md rule 2 (money stored at 4dp, DISPLAYED at 2) ·
#          rule 8 (an address is the premises' and is reached by walking) ·
#          hard-won law 14 (a savepoint, because SQLite cannot show the fault)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""Every letter this product queues states its own figures.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked BEFORE trusting them   ║
║  green, because the receipts lane's fourth guard came back green the      ║
║  first time over a fixture where every value happened to be present.      ║
╚══════════════════════════════════════════════════════════════════════════╝
Three answers, and each shapes a case below:

  1. **A fixture whose values are all present anyway.** A test that asserts
     "no em-dash in the body" passes over a caller that supplies nothing IF the
     template happens to use only renderer-supplied tokens. So every case here
     asserts a NAMED TOKEN carries a NAMED VALUE — `total_due` is `393.76 USD`,
     not merely "something" — and the bill case asserts the count of
     caller-supplied tokens the body declares (ELEVEN) so a body that loses a
     token cannot quietly shrink the claim.
  2. **A context stamped but never read.** `queue_document` writes the column;
     nothing proves the RENDERER sees it. So the letter cases render THROUGH
     `rendering.render_for_dispatch` off the stored row, which is the path the
     dispatcher takes, rather than calling `render` with a context in hand.
  3. **A template code that resolves to nothing.** `DEF-PAY-4451` is exactly
     this: a queue write REPORTS an unresolved pin and returns success, so a
     test asserting "a row was queued" is green over a letter that can never be
     produced. `test_def_pay_4451_*` therefore asserts the pin RESOLVED and the
     row RENDERS, not that a row exists.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.billing import delivery_seam
from apps.notifications import catalogs, rendering, template_preview
from apps.payments import notices as payment_notices
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-4448 · THE BILL-READY EMAIL
# ══════════════════════════════════════════════════════════════════════════


class _Payload(dict):
    """A locked `bill_payload` — six-decimal money as TEXT, ISO dates as TEXT.

    Shaped exactly as `issue._stamp_balance_forward` and `gather` write it,
    because the whole claim of `bill_render_context` is that it reads THAT and
    converts, rather than looking anything up.
    """


class _Invoice:
    """The row `queue_bill_delivery` is handed, with nothing else attached."""

    def __init__(self, **kwargs):
        self.invoice_no = "BL-2608-000058"
        self.period_start = date(2026, 7, 1)
        self.period_end = date(2026, 7, 31)
        self.due_date = date(2026, 8, 22)
        self.total = Decimal("393.760000")
        self.currency = "USD"
        self.corrects_invoice_id = None
        self.tenant_id = None
        self.bill_payload = _Payload(
            {
                "account_no": "AC-2026-00007",
                "customer_name": "Grace Gagnon",
                # `DEF-MET-4629` moved the estate's state and postcode
                # together — `TX` and `78611`, one spelling for the whole
                # fixture. This string is hand-built rather than read from the
                # seeder, so it is updated by hand; what keeps the SEEDED rows
                # honest is `test_def_met_4629_one_town_one_state.py`.
                "service_address": "113 Willow Bend Dr, Silver Creek, TX 78611",
                "bill_date": "2026-08-02",
                "previous_balance": "45.000000",
                "payments_credits": "0.000000",
                "total_due": "438.760000",
            }
        )
        self.__dict__.update(kwargs)


def test_def_bil_4448_tc1__the_bill_email_states_all_eleven_of_its_values(brazos):
    """The eleven merge fields `email_bill_ready` declares, each with a value.

    ⚠ **THE COUNT IS ASSERTED AND NOT ONLY THE MEMBERSHIP.** A body that loses
    a token would otherwise make this case easier to pass every time somebody
    edited the seeded wording — the failure shape hard-won law 7 calls *a check
    that cannot fail*.
    """
    from apps.notifications import seed_templates

    # THE SEEDED BODY, which is what actually renders — eleven caller-supplied
    # tokens. The class's WHITELIST is wider (thirteen: it also permits
    # `{account_no}` and `{customer_name}`, which a tenant may add), and the two
    # counts answer different questions. Both are asserted, because the body is
    # the promise to the customer and the whitelist is the promise to the tenant.
    body_tokens = set(rendering.tokens_in(seed_templates.EMAIL_BILL_READY_BODY)) | set(
        rendering.tokens_in(seed_templates.EMAIL_BILL_READY_SUBJECT)
    )
    declared_by_body = body_tokens - rendering.RENDERER_SUPPLIED
    # DEF-BIL-10531 (2026-10-22): ELEVEN + `{bill_link}` + `{link_expires_on}`.
    assert len(declared_by_body) == 13, sorted(declared_by_body)

    with tenant_ctx(brazos):
        klass = catalogs.catalog_for("email_bill_ready")
        whitelisted = set(klass.tokens) - rendering.RENDERER_SUPPLIED
        assert len(whitelisted) == 15, sorted(whitelisted)

        context, problems = delivery_seam.bill_render_context(_Invoice())

    # DEF-BIL-10531 — the suite's settings carry no public address, so no link
    # can be built: said once, and the two OPTIONAL link tokens are left out
    # (their paragraph drops). `test_def_bil_10531_bill_link.py` fills them.
    from apps.billing import bill_links

    assert [entry["code"] for entry in problems] == [bill_links.NO_PUBLIC_ORIGIN]
    assert klass.optional == {"bill_link", "link_expires_on"}
    whitelisted -= klass.optional
    missing = sorted(token for token in whitelisted if context.get(token) is None)
    assert missing == [], f"the bill-ready email would print `——` for {missing}"


def test_def_bil_4448_tc1b__the_figures_reach_the_QUEUE_ROW_not_only_the_helper(brazos, dana):
    """Issue a real bill and read the column the dispatcher renders from.

    ⚠ **THE CASE ABOVE IS GREEN WITH `render_context=` DELETED FROM THE QUEUE
    WRITE, AND THAT IS WHY THIS ONE EXISTS.** Building a context proves nothing
    about whether it travels; the shipped defect was a caller that had the
    figures in hand and never passed them. Proved by deleting the keyword and
    watching this case — and only this case — go red.

    It reads `outbound_messages.render_context` off the row `issue_invoice`
    wrote, through the same decoder `render_for_dispatch` uses, so it asserts
    the whole path from the locked payload to the letter.
    """
    from apps.notifications import models as outbound
    from tests.test_us_bil_023_delivery_queue import issue_one

    with tenant_ctx(brazos):
        billed, _account, _run = issue_one(
            brazos, dana, invoice_no="BL-4448-000001", account_no="A-4448-1"
        )
        row = outbound.OutboundMessage.objects.filter(source_id=billed.pk).first()
        assert row is not None
        stored = rendering.decode_context(row.render_context)

    assert stored, "the bill was queued for delivery with no merge values at all"
    assert stored["bill_no"] == "BL-4448-000001"
    assert isinstance(stored["period_start"], date)
    assert isinstance(stored["period_end"], date)
    # Every one of the eleven the seeded body names is STATED on the row, even
    # where this fixture's payload leaves a figure absent.
    for token in (
        "first_name",
        "service_address",
        "bill_no",
        "bill_date",
        "period_start",
        "period_end",
        "prev_balance",
        "payments",
        "current_charges",
        "total_due",
        "due_date",
    ):
        assert token in stored, f"{{{token}}} never reached the queue row"


def test_def_bil_4448_tc2__total_due_is_the_arrears_figure_not_this_period():
    """`{total_due}` is A19 §1.3's headline, NOT `invoices.total`.

    The fixture owes 45.00 from before and 393.76 this period. Serving
    `invoices.total` would put **393.76** in the subject line of the one email
    a customer reads and understate what they owe by their entire arrears —
    which is the single most expensive way this context could be wrong.
    """
    context, _ = delivery_seam.bill_render_context(_Invoice())

    assert context["total_due"] == Decimal("438.760000")
    assert context["current_charges"] == Decimal("393.760000")
    assert context["prev_balance"] == Decimal("45.000000")


def test_def_bil_4448_tc3__money_reaches_the_page_at_two_decimals(brazos):
    """Rule 2: stored to 4 (here 6, the column's own scale), DISPLAYED at 2.

    `DEF-NOT-4413` was this exact fault one screen over — `Balance 0.000000`
    two inches under `0.00 USD`. The payload holds TEXT at six places; passing
    it through as text would print `438.760000` on a customer's email. This
    asserts the rendered STRING, not the type, because the type is not what a
    customer reads.
    """
    with tenant_ctx(brazos):
        context, _ = delivery_seam.bill_render_context(_Invoice())
        body = rendering.render(
            template_code="email_bill_ready",
            template_version=1,
            body="Total due {total_due} by {due_date}. Previous {prev_balance}.",
            context=context,
        ).body

    assert "438.76" in body
    assert "438.760000" not in body
    assert rendering.ABSENT_MARK not in body


def test_def_bil_4448_tc4__an_unstamped_payload_gives_absences_never_zeros():
    """A bill whose balance-forward stamp could not be written prints `——`.

    `_stamp_balance_forward` writes NULLS — not zeros — when the payments seam
    is unreachable, and `DEF-127`'s lesson is that an absence must never be
    spelled the same way as zero. `0.00 USD` here would tell a customer in
    arrears that they are square, on an immutable document.
    """
    invoice = _Invoice()
    invoice.bill_payload = _Payload(
        {"account_no": "AC-1", "previous_balance": None, "total_due": ""}
    )

    context, _ = delivery_seam.bill_render_context(invoice)

    assert context["prev_balance"] is None
    assert context["total_due"] is None
    # …and stated rather than absent from the dict, so the queue's own gap
    # report can tell "nobody had it" from "nobody remembered it".
    assert "prev_balance" in context and "total_due" in context


def test_def_bil_4448_tc5__every_token_is_stated_even_when_it_has_no_value():
    """The convention the guard depends on: a key present with `None` MEANS none.

    `notifications.services._context_gap` cannot tell a figure nobody had from
    a figure nobody remembered unless the caller says which, and it tests
    `key in context`. A correction reason this seam does not hold must
    therefore be STATED, not omitted.
    """
    context, _ = delivery_seam.bill_render_context(_Invoice())

    assert "correction_reason" in context
    assert context["correction_reason"] is None
    assert "original_total" in context


# ══════════════════════════════════════════════════════════════════════════
# DEF-PAY-4451 · THE DISCONNECT TIER'S WORDING
# ══════════════════════════════════════════════════════════════════════════


def test_def_pay_4451_disconnect_tiers_name_seeded_wording(brazos, dana):
    """Each tier's letter RESOLVES to a published version — asserted at the SEND.

    ⚠ **THE FIRST VERSION OF THIS CASE WAS GREEN OVER THE ORIGINAL DEFECT, AND
    THAT IS RECORDED HERE RATHER THAN QUIETLY FIXED.** It read
    `TIER_TEMPLATE_CODES[tier]` and checked the catalogue knew it — so it
    asserted the MAP was right and never that the caller USED it. Restoring
    `f"{template_code}_{tier}"` in `send_disconnect_notices` left all eighteen
    cases in this file passing. A test named after an assertion it does not make
    (hard-won law 7's fourth shape), found by running the sabotage rather than
    by reading the test.

    So it sends through the real function and asserts the QUEUED ROW carries a
    resolved pin. `template_pin_unresolved` is a PROBLEM on a SUCCESSFUL write —
    the row exists, the count is right, the toast says *Sent* — so the pin is
    the only thing that separates a letter from a row that can never render.
    """
    from apps.notifications import models as notification_models
    from tests.test_w3_billing_models import an_account

    with tenant_ctx(brazos):
        for index, tier in enumerate(payment_notices.DISCONNECT_TIERS):
            account = an_account(dana, brazos, account_no=f"A-4449-{index}")
            payment_notices.send_disconnect_notices(
                account_ids=(account.id,),
                tier=tier,
                cut_date=date(2026, 9, 17),
                on_date=date(2026, 9, 7),
                channels=("pdf_print",),
                reconnect_fee=Decimal("35.00"),
                actor=dana,
            )
            row = notification_models.OutboundMessage.objects.filter(
                source_type="notice", account_id=account.id
            ).first()
            assert row is not None, f"tier {tier!r} queued nothing at all"
            assert row.template_version is not None, (
                f"tier {tier!r} queued a row pinned to {row.template_code!r}, which "
                "resolves to no published version — the notice can never be rendered, "
                "and the ladder has already advanced this account towards disconnection"
            )
            assert catalogs.catalog_for(row.template_code) is not None


# ══════════════════════════════════════════════════════════════════════════
# DEF-PAY-4450 · THE COLLECTIONS LETTER'S FIGURES
# ══════════════════════════════════════════════════════════════════════════


def test_def_pay_4450_tc1__a_disconnect_notice_states_the_amount_and_the_deadline(brazos, dana):
    """The four things a disconnection notice exists to say, ASSERTED AT THE SEND.

    ⚠ **THE FIRST VERSION CALLED `_notice_context` DIRECTLY AND WAS GREEN WITH
    THE CONTEXT DELETED FROM `send_disconnect_notices` ENTIRELY.** Same fault as
    the case above and found the same way. What matters is not that the helper
    can build a context — it is that the SENDER hands one to the queue — so this
    reads the stored column off the row the real bulk sender wrote.
    """
    from apps.notifications import models as notification_models
    from tests.test_w3_billing_models import an_account

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-4448-1")
        payment_notices.send_disconnect_notices(
            account_ids=(account.id,),
            tier="second_5_day",
            cut_date=date(2026, 9, 17),
            on_date=date(2026, 9, 7),
            channels=("pdf_print",),
            reconnect_fee=Decimal("35.00"),
            actor=dana,
        )
        row = notification_models.OutboundMessage.objects.filter(
            source_type="notice", account_id=account.id
        ).first()
        stored = rendering.decode_context(row.render_context)

    assert stored, "the notice was queued with no merge values at all"
    assert stored["cut_date"] == date(2026, 9, 17)
    assert stored["pay_by_date"] == date(2026, 9, 17)
    assert stored["reconnect_fee"] == Decimal("35.00")
    # Stated even where this account has no debt on file — a key present with
    # no value MEANS none, which is what lets the queue's gap report tell an
    # oversight from an absence.
    assert "balance" in stored and "customer_name" in stored


def test_def_pay_4450_tc1b__the_context_helper_shapes_every_value_it_is_given():
    """The helper's own conversion, given facts — the unit half of TC-1.

    Kept beside the send case rather than instead of it: this one says the
    values are shaped right, and TC-1 says they actually travel.
    """


def test_def_pay_4450_tc2__the_regulatory_reference_stays_a_named_absence():
    """`{state_puc_ref}` is stated with no value, and that is the correct answer.

    Nothing in this product stores a commission reference — `rights_footer.py`
    records it and `notifications.notices` takes it as a caller argument for
    the same reason. A fabricated regulatory citation is the worst thing that
    could appear on a disconnection notice, so the key is present and empty:
    the letter goes out with `——` on that line and the queue's gap report
    stays silent about it, because nobody forgot it.
    """
    context = payment_notices._notice_context({})

    assert "state_puc_ref" in context
    assert context["state_puc_ref"] is None


def test_def_pay_4450_tc3__an_unreadable_account_costs_lines_not_the_notice():
    """No facts at all still yields a full context of stated absences.

    The ladder has already decided to send; a figure it could not read must
    cost that line and never the letter, and never raise inside a nightly run.
    """
    context = payment_notices._notice_context({}, cut_date=date(2026, 9, 17))

    assert context["balance"] is None
    assert context["customer_name"] is None
    assert context["cut_date"] == date(2026, 9, 17)


# ══════════════════════════════════════════════════════════════════════════
# DEF-NOT-4449 · THE SEND TEST
# ══════════════════════════════════════════════════════════════════════════


def test_def_not_4449__a_send_test_carries_the_previews_own_samples():
    """A test message and the preview of the same class say the same thing.

    Two sample sets would eventually disagree and the System Admin could not
    tell which one was the letter. The identity is asserted rather than the
    contents, so adding a sample to the preview cannot silently leave the test
    send behind.

    ⚠ **AMENDED 2026-09-30 — THE SAMPLE CUSTOMER IS `Pat`, NOT `Sample`, BY PO
    RULING.** This case was written at 10:26 on 2026-09-07 (`ceb0b2544`) and
    went red at 12:28 the same day (`1c9c3771a`), when the Product Owner ruled
    that the preview reads *"Hi Pat, your bill for 12 Oak Street is ready…
    Account AC-000000 …"* (decision log 2026-09-07; `template_preview.py`'s
    header quotes the superseded sentence). What keeps a screenshot from
    passing for a real customer is now the ACCOUNT NUMBER — `AC-000000`, the
    right shape with digits no live account can hold — so that is what is
    asserted as the "visibly a sample" half, beside the ruled name.
    """
    for code in ("email_bill_ready", "email_payment_receipt"):
        sample = template_preview.sample_context(code)
        assert sample, f"{code} has no sample context to send"
        # Visibly a sample, and NOT a clock read (BR-TEN-043): a preview that
        # read today's date could never be reproduced from a screenshot.
        assert sample.get("first_name") == "Pat"
        assert sample.get("account_no") == "AC-000000"
        for value in sample.values():
            if isinstance(value, date):
                assert value == date(2026, 1, 31)


def test_def_not_4449__the_identity_tokens_stay_unsampled_on_a_test():
    """A test send is the one message where `——` for the support phone HELPS.

    It tells the System Admin that their real letters will print it blank
    (`DEF-TEN-4412`: 45 absences across 28 of 41 classes on a self-served
    tenant). Sampling them would hide the one thing a test proves.
    """
    sample = template_preview.sample_context("email_bill_ready")

    for token in ("utility_name", "support_phone", "support_email"):
        assert token not in sample


# ══════════════════════════════════════════════════════════════════════════
# THE ROUND TRIP — the column is JSON and money must survive it
# ══════════════════════════════════════════════════════════════════════════


def test_the_stored_context_survives_the_json_column_with_its_types():
    """`Decimal` and `date` in, `Decimal` and `date` out.

    This is what makes `format_money` run on the far side of the column. A
    string would print six decimals on a customer's bill and a date would print
    ISO on a tenant whose Regional format is `DD/MM/YYYY` — and both would look
    like data problems rather than like a codec.
    """
    context, _ = delivery_seam.bill_render_context(_Invoice())
    restored = rendering.decode_context(rendering.encode_context(context))

    assert restored["total_due"] == Decimal("438.760000")
    assert isinstance(restored["total_due"], Decimal)
    assert restored["due_date"] == date(2026, 8, 22)
    assert isinstance(restored["due_date"], date)


def test_a_float_in_a_bill_context_is_refused_at_the_write():
    """Rule 2 at the boundary: money is Decimal and never float.

    Not a new guard — `encode_context` already refuses — asserted here because
    `bill_render_context` is a new producer of that column and a `float` would
    otherwise be caught one dispatch cycle at a time instead of at the write.
    """
    invoice = _Invoice()
    invoice.total = 393.76  # the mistake this refusal exists for

    context, _ = delivery_seam.bill_render_context(invoice)

    with pytest.raises(rendering.RenderRefused):
        rendering.encode_context(context)


def test_the_correction_read_is_skipped_entirely_on_an_ordinary_bill(
    django_assert_num_queries,
):
    """A five-hundred-bill run makes NO extra query for its covering emails.

    The whole design claim of `bill_render_context` is that it reads the locked
    payload and queries nothing — it runs inside `issue_invoice`'s transaction,
    once per bill. `corrects_invoice_id` is NULL on nearly every bill, so the
    one read this function can make is not reached.

    ⚠ Asserted as a QUERY COUNT rather than by reading the code, because *"it
    does not query"* is exactly the kind of claim that stops being true in a
    refactor and that no reviewer notices.
    """
    with django_assert_num_queries(0):
        delivery_seam.bill_render_context(_Invoice())


def test_the_ladders_two_dates_are_one_value_and_that_is_recorded():
    """`{pay_by_date}` and `{cut_date}` are two spellings of one stored date.

    Written as its own case because it is a JUDGMENT and not a mechanism: tier
    1 asks *"pay by X (10 days)"* and carries no cut date; tiers 2 and 3 ask
    for the cut date and carry no pay-by. `ladder._send` computes ONE date
    (`as_of + 10 days`) and hands it in. If a utility ever needs a grace day
    between the two, this case is what goes red.
    """
    cut = date(2026, 9, 17)
    context = payment_notices._notice_context({}, cut_date=cut)

    assert context["pay_by_date"] == cut == context["cut_date"]


def test_the_final_notice_hours_come_from_the_tenant_not_from_the_number_48():
    """`{48h}` renders the tenant's own `final_notice_hours` setting.

    BR-REP-016's discipline — *"dunning day numbers render from the tenant's
    cadence config, never constants"* — applied to the one figure in hours. A
    utility whose final notice is 72 hours must not have its letter say 48.
    """
    context = payment_notices._notice_context({})

    assert context["48h"] in (None, "48 hours"), context["48h"]
    # And it is DERIVED, not spelled: monkeypatching the setting moves it.
    original = payment_notices.settings_seam.final_notice_hours
    try:
        payment_notices.settings_seam.final_notice_hours = lambda: 72
        assert payment_notices._notice_context({})["48h"] == "72 hours"
    finally:
        payment_notices.settings_seam.final_notice_hours = original


def test_a_resend_is_offered_the_stored_context_decoded_not_the_raw_column():
    """The figures travel with the copy, and they travel DECODED.

    `queue_document` encodes on the way in, so handing the raw column back
    would double-wrap the tags and print `{'__money__': '100.0000'}` on a
    customer's receipt. Asserted on the codec rather than through the endpoint
    because the endpoint's own suite covers the route; what is new here is the
    direction of the conversion.
    """
    stored = rendering.encode_context({"amount": Decimal("100.0000")})

    assert rendering.decode_context(stored)["amount"] == Decimal("100.0000")
    assert rendering.encode_context(rendering.decode_context(stored)) == stored


def test_the_ladders_grace_window_is_not_silently_widened():
    """A guard against the easy 'improvement': pay-by one day before the cut.

    Nothing in this product stores a grace day, so inventing one would move a
    legal deadline printed on a notice. If a rule ever adds one it comes with a
    stored date and this case is deleted deliberately rather than drifting.
    """
    cut = date(2026, 9, 17)
    context = payment_notices._notice_context({}, cut_date=cut)

    assert context["pay_by_date"] != cut - timedelta(days=1)
