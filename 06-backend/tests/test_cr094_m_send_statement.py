# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-014 (Send statement) — `CR-094-BRC01` wave M, releasing the
#           ✉ quick action `ACC-Q07`
# Rules:    BR-CUS-040 (statement != bill: a range ledger plus the "nothing is
#           due" disclaimer) · A19 §1 + rule 1 · BR-LED-010 (the range ledger) ·
#           BR-REP-002 (read models over the books) · BR-NOT-005 / BR-NOT-013
#           (queued, never sent) · BR-NOT-024 (print is the floor on a customer
#           document) · BR-TEN-043 (the caller names the date) · HR-1/G4
#           (404-never-403) · CLAUDE.md hard rule 2 (money 4dp stored, 2dp
#           displayed) · rule 6 (idempotency)
# ───────────────────────────────────────────────────────
"""`CR-094-BRC01` wave M — **the account statement**, queued from the books.

══════════════════════════════════════════════════════════════════════════
THE WORKED FIGURE, AND IT IS ALREADY SIGNED SOMEWHERE ELSE
══════════════════════════════════════════════════════════════════════════
**`ACC-1042`, 1–31 July 2026.** LE-1's own month: the account opens at
**45.00** (a cutover balance posted 2026-06-30, BEFORE the window), is billed
**247.87** on 15 July, pays **292.87** on 25 July, and closes at **0.00**.
`apps/ledger/reporting.account_ledger`'s docstring states the same three
movements in the same order — *"opens ACC-1042 at 45.00, bills it to 292.87 and
pays it to 0.00"* — and US-LED-009 §7's formula is what makes them foot:
`45.00 + 247.87 - 292.87 = 0.00`.

**Nothing in this wave computes any of that.** The statement RESTATES the books
(`BR-REP-002`), so this file's job is to prove the figures arrive unchanged and
that a document is queued carrying them — never to re-derive them. If a figure
here ever disagrees with the ledger's, the statement is the one that is wrong.

══════════════════════════════════════════════════════════════════════════
PROVED RED FIRST (hard-won law 7), AND IN THE HARNESS THAT RUNS IT
══════════════════════════════════════════════════════════════════════════
Before `apps/billing/statement.py` existed, every case in this file failed with

    ModuleNotFoundError: No module named 'apps.billing.statement'

and the endpoint case, once the module existed but the route was not mounted,
with

    django.urls.exceptions.NoReverseMatch / Resolver404 on
    /api/brazosbend/accounts/<id>/statement

Each guarantee below was then broken ONE AT A TIME in the working tree, run
through `pytest` (the harness that will run it, not a `__main__` — DEF-GOV-3733),
and the failure quoted in the lane report before the fix was restored.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import statement as billing_statement
from apps.billing import statement_api
from apps.notifications import models as notification_models
from core import errors

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE1_OPENING_AR,
    LE1_PAYMENT,
    LE1_WE1_BILL,
    make_accounts,
    post_le1_month,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: `45.00 + 247.87 - 292.87`. Written as the arithmetic rather than as `0`
#: so a reader can check the claim without leaving the line.
LE1_CLOSING = LE1_OPENING_AR + LE1_WE1_BILL - LE1_PAYMENT


def a_month(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def call(tenant, account, **body):
    return api_call(
        statement_api.queue_account_statement,
        "post",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        data=body or None,
        account_id=str(account.id),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 — THE FIGURES ARE THE BOOKS' OWN AND ARRIVE UNCHANGED
# ═══════════════════════════════════════════════════════════════════════════
def test_the_statement_restates_le1s_july_and_computes_nothing(brazos, dana):
    """**45.00 in, 247.87 charged, 292.87 paid, 0.00 out** — A19 §1's statement.

    This is the whole claim of the wave in one assertion: the four figures on
    the statement are `account_ledger`'s four figures, and the statement adds
    nothing to them. A19 §1 defines the document as *"a running ledger over a
    date range — date / description / reference / charges / payments /
    balance"*, and that is what comes back.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        figures = billing_statement.statement_figures(
            accounts["ACC-1042"].id, start=JULY_START, end=JULY_END
        )

        assert figures.readable is True
        assert figures.opening_balance == LE1_OPENING_AR  # 45.00, from BEFORE the window
        assert figures.charges == LE1_WE1_BILL  # 247.87
        assert figures.payments == LE1_PAYMENT  # 292.87
        assert figures.closing_balance == LE1_CLOSING  # 0.00, and it FOOTS
        # The running ledger itself, not merely its totals — a statement without
        # its rows is a balance, which is the CR-060 C16 report and a different
        # document entirely.
        assert figures.rows, "a statement with no rows is not a statement"
        assert figures.rows[-1]["running_balance"] == LE1_CLOSING


def test_money_travels_as_decimal_so_the_renderer_can_do_the_2dp_rounding(brazos, dana):
    """CLAUDE.md rule 2 — stored 4dp, DISPLAYED 2, rounded in exactly one place.

    A string here would reach the queue row's JSON column already formatted and
    print `45.0000` on a customer's statement: `rendering.encode_context` tags
    `Decimal`s on the way in and `format_money` does the 2dp on the far side.
    This asserts the TYPE because the type is the mechanism.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        context, _figures, _problems = billing_statement.statement_render_context(
            accounts["ACC-1042"].id, start=JULY_START, end=JULY_END
        )
        for token in ("opening_balance", "closing_balance", "charges", "payments"):
            assert isinstance(context[token], Decimal), f"{token} must stay a Decimal"
        assert context["period_start"] == JULY_START
        assert context["period_end"] == JULY_END


def test_a_statement_carries_no_bill_number_cycle_or_bill_date(brazos, dana):
    """`BR-CUS-040` — **statement != bill**, asserted rather than described.

    `catalogs.py` derives this class's palette from `_BILL_META`, which drags
    three bill-shaped tokens along with it. A statement has no bill number, no
    cycle and no bill date, so supplying one would be inventing a fact. The
    renderer's named-absence path is the right answer for a token a document
    genuinely has no value for (OQ-117's closure).
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        context, _f, _p = billing_statement.statement_render_context(
            accounts["ACC-1042"].id, start=JULY_START, end=JULY_END
        )
        for invented in ("bill_no", "cycle", "bill_date", "due_date", "total_due"):
            assert invented not in context, f"a statement must not carry {invented}"


def test_the_utilitys_own_values_are_stamped_at_render_and_not_here(brazos, dana):
    """`BR-TEN-017` — the masthead is the RENDERER's, so this must not copy it.

    `rendering._identity_context` fills `utility_name`, `support_phone` and
    their four siblings at render time, which is why the seeded email body can
    say *"Call {support_phone}"* without this module knowing the number. A
    second copy here would be the one that goes stale when a tenant edits
    Settings (hard-won law 1).
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        context, _f, _p = billing_statement.statement_render_context(
            accounts["ACC-1042"].id, start=JULY_START, end=JULY_END
        )
        for stamped in (
            "utility_name",
            "utility_address",
            "support_phone",
            "support_email",
            "utility_website",
        ):
            assert stamped not in context, f"{stamped} is stamped at render, never here"

    # ═══════════════════════════════════════════════════════════════════════════
    # 2 — IT QUEUES, ON BOTH CHANNELS, AND IT DOES NOT SEND
    # ═══════════════════════════════════════════════════════════════════════════


def test_it_queues_both_channels_and_says_dispatched_false(brazos, dana):
    """`BR-NOT-005` / `BR-NOT-013` — **nothing in this product sends.**

    Two rows, one document: `frozen_documents.py` already maps the printed
    statement and the statement email onto the single kind `statement`, and
    `channel` is its own column. `account` carries `BR-NOT-024`'s print floor,
    so the paper copy is queued whether or not anyone asked for it — which is
    the PO's own ruling that print is always on for a customer document.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        answer = billing_statement.queue_statement(
            account_id=accounts["ACC-1042"].id, start=JULY_START, end=JULY_END, actor=dana
        )

        channels = {row["channel"] for row in answer["queued"]}
        assert channels == {"pdf_print", "email"}
        assert all(row["created"] for row in answer["queued"])
        assert answer["row_count"] == len(
            billing_statement.statement_figures(
                accounts["ACC-1042"].id, start=JULY_START, end=JULY_END
            ).rows
        )

        rows = notification_models.OutboundMessage.objects.filter(
            tenant_id=brazos.id, source_type="account"
        )
        assert rows.count() == 2
        # NOT SENT. The queue is a queue: nothing has a sent timestamp, because no
        # vendor is connected on any channel this release.
        for row in rows:
            assert getattr(row, "sent_at", None) is None


def test_asking_twice_for_the_same_period_queues_nothing_the_second_time(brazos, dana):
    """CLAUDE.md hard rule 6 — a double-clicked button is one statement.

    The key is `(tenant, source_type, source_id, channel, copy_no)` and the
    `source_id` is a UUID5 of the account and the two dates, so the replay
    finds its own rows. `created` is False and **no second row exists** — a
    clerk must never be told a document was queued twice.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        first = billing_statement.queue_statement(
            account_id=accounts["ACC-1042"].id, start=JULY_START, end=JULY_END, actor=dana
        )
        second = billing_statement.queue_statement(
            account_id=accounts["ACC-1042"].id, start=JULY_START, end=JULY_END, actor=dana
        )

        assert all(row["created"] for row in first["queued"])
        assert not any(row["created"] for row in second["queued"])
        assert (
            notification_models.OutboundMessage.objects.filter(
                tenant_id=brazos.id, source_type="account"
            ).count()
            == 2
        )


def test_a_different_period_is_a_different_document(brazos, dana):
    """The period is IN the idempotency key, and it has to be.

    Two periods are two statements. If the id keyed only on the account, a
    clerk running June after July would be told June was "already queued" and
    would be handed July's figures.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        july = billing_statement.statement_source_id(
            account_id=accounts["ACC-1042"].id, start=JULY_START, end=JULY_END
        )
        june = billing_statement.statement_source_id(
            account_id=accounts["ACC-1042"].id, start=date(2026, 6, 1), end=date(2026, 6, 30)
        )
        assert july != june
        # ...and the same period is the SAME id, which is the other half.
        assert july == billing_statement.statement_source_id(
            account_id=accounts["ACC-1042"].id, start=JULY_START, end=JULY_END
        )


def test_a_human_can_ask_for_a_second_copy_with_copy_no(brazos, dana):
    """`copy_no` is the one deliberate door through the key, and it is a HUMAN's.

    Automatic writers leave it 0 so a replay collides. A clerk who genuinely
    wants another copy passes 1, which is a different key and a genuinely new
    message — the same posture a bill reprint takes (US-BIL-024 TC-4).
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        billing_statement.queue_statement(
            account_id=accounts["ACC-1042"].id, start=JULY_START, end=JULY_END, actor=dana
        )
        again = billing_statement.queue_statement(
            account_id=accounts["ACC-1042"].id,
            start=JULY_START,
            end=JULY_END,
            actor=dana,
            copy_no=1,
        )
        assert all(row["created"] for row in again["queued"])
        assert (
            notification_models.OutboundMessage.objects.filter(
                tenant_id=brazos.id, source_type="account"
            ).count()
            == 4
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # 3 — THE ENDPOINT
    # ═══════════════════════════════════════════════════════════════════════════


def test_the_endpoint_queues_and_reports_the_period_and_the_two_balances(brazos, dana):
    """`POST /accounts/{id}/statement` — the door the ✉ glyph opens.

    The response carries what a clerk checks the statement BY before they trust
    it: the period, the opening and closing balances and how many rows are on
    it. Money goes out at 4 decimals (rule 2's STORED precision); the 2dp
    display rounding is `MoneyCell`'s on the screen, in one place.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        response = call(brazos, accounts["ACC-1042"], **{"from": "2026-07-01", "to": "2026-07-31"})

        assert response.status_code == 200
        body = response.data
        assert body["dispatched"] is False
        assert body["opening_balance"] == "45.0000"
        assert body["closing_balance"] == "0.0000"
        assert {row["channel"] for row in body["queued"]} == {"pdf_print", "email"}


def test_a_missing_or_malformed_period_is_a_422_naming_the_field(brazos, dana):
    """`BR-TEN-043` — there is no default period and no clock in this module.

    *"You did not say when"* and *"that is not a date"* are different answers
    and get different codes, both naming WHICH field is wrong. A default
    invented server-side would be a product decision taken where nobody could
    see it: a statement covering the wrong three months is wrong quietly.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)

        # DRF's handler RENDERS a catalogue refusal into the G1 envelope rather
        # than letting it escape the view, so these assert the envelope — the
        # status, the code and the named field — which is also what the browser
        # will actually receive.
        missing = call(brazos, accounts["ACC-1042"], **{"to": "2026-07-31"})
        assert missing.status_code == 422
        assert missing.data["code"] == errors.VAL_REQUIRED
        assert missing.data["field_errors"][0]["field"] == "from"

        malformed = call(brazos, accounts["ACC-1042"], **{"from": "the first", "to": "2026-07-31"})
        assert malformed.status_code == 422
        assert malformed.data["code"] == errors.VAL_FORMAT
        assert malformed.data["field_errors"][0]["field"] == "from"

        # ⚠ THE SENTENCE IS THE POINT, NOT THE CODE. Since the PO's ruling of
        # 2026-08-19 the server's own `detail` never reaches a screen, so a
        # refusal with a message key no catalogue defines arrives as SILENCE —
        # the click does nothing and nothing appears. Both keys are asserted to
        # RESOLVE, which is the half a status code cannot check.
        assert missing.data["message_key"] == "billing.statement.periodRequired"
        assert malformed.data["message_key"] == "billing.statement.periodFormat"


def test_an_account_this_tenant_does_not_hold_is_a_404_and_never_a_403(brazos, dana):
    """HR-1 / G4 — from outside a tenant, "not yours" and "not there" are one fact.

    Telling them apart is a membership oracle. The refusal is the customers
    module's own and is let through rather than caught: a statement for
    somebody else's account is not a document with a gap in it.
    """

    def ask(account_id):
        return api_call(
            statement_api.queue_account_statement,
            "post",
            user=FakeUser(),
            role="billing_clerk",
            tenant=brazos,
            data={"from": "2026-07-01", "to": "2026-07-31"},
            account_id=account_id,
        )

    with tenant_ctx(brazos):
        a_month(brazos, dana)
        # DRF's handler renders the customers module's `deny_as_not_found` into
        # the envelope, so the assertion is on the STATUS — the same way
        # CR-060 C16's own cross-tenant case asserts it one module along.
        assert ask("11111111-2222-3333-4444-555555555555").status_code == 404
        # A MALFORMED id is the same answer for the same reason: it must not be
        # possible to tell "no such account" from "not yours" from outside.
        assert ask("not-a-uuid").status_code == 404


def test_an_inverted_range_is_the_ledgers_own_refusal(brazos, dana):
    """US-LED-009 TC-6 — *"never an empty-but-plausible report"*.

    `account_ledger` raises on `start > end` and this wave lets that through.
    Catching it to return a friendlier shape would be a second statement of the
    same rule and the weaker one.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        with pytest.raises(errors.ValidationError):
            billing_statement.statement_figures(
                accounts["ACC-1042"].id, start=JULY_END, end=JULY_START
            )
