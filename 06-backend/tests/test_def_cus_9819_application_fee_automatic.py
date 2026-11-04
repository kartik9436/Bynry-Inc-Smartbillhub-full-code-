# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9819 (PO request 2026-10-06) — the application fee is added
#           to every new request automatically; a utility without a fee prices
#           it at $0.00 and staff can still waive.
# Rules:    BR-CUS-090 (amended 2026-10-06) · BR-CUS-1092 (amended 2026-10-06)
# Impacts:  apps/rating/{models,services,selectors}.py + migrations/0067 ·
#           apps/customers/service_request_service.py · apps/portal/{services,
#           availability}.py · apps/portal/seams/rating_seam.py
# ───────────────────────────────────────────────────────
"""🔒 HUMAN-REVIEW-PENDING — **every new request arrives with the utility's
application fee, at its live price.**

PO, verbatim: *"No - we wil ahve application fees as zero and pprovide option to
waive off"*, then *"Should the application fee be added to every request
automatically? I recommend (a)."* — (a) read *"Every new request, from the
portal or the counter, gets the utility's application fee line automatically at
its current price: $10.00 for Ann Arbor, $0.00 for a utility that charges
nothing. The clerk then takes it or waives it."*

**Worked, as shown for review:** Kyle Mark's portal request arrives with
*Application fee $10.00* already on it; the clerk takes it or waives it. A
utility that charges nothing prices its fee at $0.00, and its requests read
*Nothing to collect* with no collect button.

WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2)
* **A copied figure would pass a $10.00 assertion.** So the price is MOVED to
  $12.00 between two requests and the second must read $12.00 while the first
  keeps $10.00 — a constant cannot do both.
* **"Every request" would pass if every portal door added it.** So a portal
  problem report is created on the same tenant and must carry NO line.
* **"Idempotent" would pass if the helper simply never ran twice.** So it is
  called a second time on the same request and the line count is read back.
* **"$0.00 is savable" would pass on a fixture that bypasses the form's
  door.** So the code is created through `rating.services.create_charge`, the
  door the charge-code form posts to.

RUN ON POSTGRESQL 16 (law 14) — the creation paths write inside the request's
own transaction: `DJANGO_SETTINGS_MODULE=config.settings.local` with
`DATABASE_URL` set, `JOBS_EAGER=false --reuse-db`.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.customers import service_request as rules
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from apps.portal import availability
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from apps.rating import services as rating_services
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403

pytestmark = pytest.mark.django_db

CAPTURE = {
    "channel": "counter",
    "applicant_kind": "person",
    "applicant_name": "Mark, Kyle",
    "applicant_phone": "734-555-0190",
    "address_as_given": "410 Packard St, Ann Arbor",
    "what_they_said": "New service",
}
PORTAL = {
    "applicant_kind": "person",
    "applicant_name": "Kyle Mark",
    "applicant_phone": "734-555-0190",
    "address_as_given": "410 Packard St, Ann Arbor",
    "what_they_said": "Start service",
}


def _app_fee(actor, amount, *, code="APP-FEE", marked=True):
    return rating_services.create_charge(
        actor,
        {
            "code": code,
            "name": "Application fee",
            "charge_type": "one_time",
            "amount_rule": "flat",
            "amount": str(amount),
            "kind": "other",
            "is_application_fee": marked,
        },
    )


def _lines(request_id):
    return list(
        customers_models.ServiceRequestFee.objects.filter(request_id=request_id).order_by("line_no")
    )


def test_a_staff_request_arrives_with_the_application_fee_at_its_live_price(pine_hill, sarah):
    with tenant_context(pine_hill.id):
        row = _app_fee(sarah, "10.00")
        assert row["is_application_fee"] is True
        first = sr.create_request(sarah, dict(CAPTURE))
        [line] = _lines(first.id)
        assert (line.charge_code, line.amount, line.quantity) == (
            "APP-FEE",
            Decimal("10.0000"),
            Decimal("1.0000"),
        )
        # The price is READ, never copied: move it and the NEXT request moves,
        # while the first keeps what it was raised at (DEF-CUS-6416's lock).
        rating_services.update_charge(sarah, row["id"], {"amount": "12.00"})
        second = sr.create_request(sarah, dict(CAPTURE))
        assert _lines(second.id)[0].amount == Decimal("12.0000")
        assert _lines(first.id)[0].amount == Decimal("10.0000")
        # One line per request, however often the helper is asked.
        assert sr.add_application_fee_line(sarah, second.id) is None
        assert len(_lines(second.id)) == 1
        # It owes the fee — approval waits until it is paid or waived (unchanged).
        fees = reads.fees_tab(sr.request_row(first.id))
        assert Decimal(fees["outstanding"]["amount"]) == Decimal("10")


def test_a_portal_application_gets_it_and_a_portal_report_does_not(pine_hill, sarah):
    with tenant_context(pine_hill.id):
        _app_fee(sarah, "10.00")
        applied = sr.create_from_portal(dict(PORTAL), application=True)
        [line] = _lines(applied.id)
        assert (line.charge_code, line.amount) == ("APP-FEE", Decimal("10.0000"))
        report = sr.create_from_portal(dict(PORTAL, what_they_said="Water leaking at the curb"))
        assert _lines(report.id) == []


def test_a_utility_that_charges_nothing_saves_a_zero_fee_and_owes_nothing(pine_hill, sarah):
    with tenant_context(pine_hill.id):
        _app_fee(sarah, "0.00")
        request = sr.create_request(sarah, dict(CAPTURE))
        [line] = _lines(request.id)
        assert line.amount == Decimal("0.0000")
        fees = reads.fees_tab(sr.request_row(request.id))
        assert Decimal(fees["quoted"]["amount"]) == Decimal(fees["outstanding"]["amount"]) == 0
        assert fees["shortfall_is_open_balance"] is False
        # A $0.00 line owes nothing, so it does not block approval …
        condition = rules.fee_condition(
            outstanding_lines=fees["outstanding_lines"], outstanding_amount=Decimal("0")
        )
        assert condition.blocking is False
        # … and staff can still waive it.
        waived = sr.waive_fee_line(sarah, line.id, reason="No fee here")
        assert waived.waived is True


def test_no_marked_code_adds_nothing_and_refuses_nothing(pine_hill, sarah):
    with tenant_context(pine_hill.id):
        _app_fee(sarah, "10.00", marked=False)
        request = sr.create_request(sarah, dict(CAPTURE))
        assert _lines(request.id) == []
        assert rating_selectors.application_fee_charge() is None


def test_only_one_one_time_code_may_be_the_application_fee(pine_hill, sarah):
    with tenant_context(pine_hill.id):
        _app_fee(sarah, "10.00")
        with pytest.raises(errors.ValidationError) as second:
            _app_fee(sarah, "25.00", code="CC-REQFEE")
        assert second.value.field_errors[0]["message_key"] == "rating.charges.application_fee_taken"
        assert second.value.field_errors[0]["params"]["charge_code"] == "APP-FEE"
        with pytest.raises(errors.ValidationError) as recurring:
            rating_services.create_charge(
                sarah,
                {
                    "code": "MONTHLY",
                    "name": "Monthly",
                    "charge_type": "recurring",
                    "amount_rule": "flat",
                    "amount": "3.00",
                    "kind": "other",
                    "is_application_fee": True,
                },
            )
        assert (
            recurring.value.field_errors[0]["message_key"]
            == "rating.charges.application_fee_one_time"
        )
        assert rating_models.Charge.objects.filter(is_application_fee=True).count() == 1


def test_the_portal_shows_the_same_figure_before_send(pine_hill, sarah):
    with tenant_context(pine_hill.id):
        unmarked = availability.availability(pine_hill.id, "nowhere at all")
        assert unmarked["application_fee"]["amount"] is None
        _app_fee(sarah, "10.00")
        answer = availability.availability(pine_hill.id, "nowhere at all")
        assert answer["application_fee"]["amount"] == "10.0000"
        assert answer["application_fee"]["display"] == "$10.00"


# ═══════════════════════════════════════════════════════════════════════════
# THE STATEMENT THE PO SIGNED ON 2026-10-06
# ═══════════════════════════════════════════════════════════════════════════
def test_the_statement_the_po_signed_on_2026_10_06(pine_hill, sarah, pine_clerk, oak_ridge, elena):
    """**SIGNED 2026-10-06** — review-ledger AMENDMENT row *"SIGN-OFF RECORDED"*
    for `DEF-CUS-9819`; decision log *"THE AUTOMATIC APPLICATION FEE SIGNED"*.

    Shown to the PO, verbatim: *"Kyle Mark's portal request arrives with
    Application fee $10.00 already on it; the clerk takes it or waives it. A
    utility that charges nothing prices its fee at $0.00, and its requests read
    'nothing to collect' with no collect button."* PO, verbatim: *"2. Approve
    the automatic application fee (built, 2.552.0)? (a). It's exactly your two
    rulings: no setting, and the fee added automatically."*

    Each sentence is asserted on the figure shown, so a drift goes RED:

    * Kyle Mark's PORTAL request (the guest door, `create_from_portal(
      application=True)`) carries exactly ONE line, the marked code, $10.0000,
      quantity 1 — nobody added it by hand.
    * *"the clerk takes it"* — a Billing Clerk collects $10.00 and nothing is
      left owing; *"or waives it"* — on a second request the clerk waives the
      line and nothing is left owing.
    * A utility that charges nothing (Oak Ridge, its code priced $0.00) gets a
      $0.00 line on its requests, owes $0.00, and serves the panel exactly the
      two facts `FeesBlock` reads to print *Nothing to collect.* in place of the
      collect button (`fees.lines.length > 0 && owesNothing(outstanding)`,
      `ServiceRequestDetailPage.tsx`; the render itself is asserted in
      `ServiceRequestDetailPage.test.tsx`'s DEF-CUS-9819 block). The line is
      neither waived nor settled, so its waive action is still drawn, and the
      waive is accepted.

    What this does NOT carry is listed in the ledger row (one marked code per
    utility, the unmarked case, a portal report getting no fee, the live-price
    read, Check and send's figure) — machine evidence only, in the cases above,
    still on the agenda.
    """
    # ── "Kyle Mark's portal request arrives with Application fee $10.00" ──
    with tenant_context(pine_hill.id):
        _app_fee(sarah, "10.00")
        kyle = sr.create_from_portal(dict(PORTAL), application=True)
        [line] = _lines(kyle.id)
        assert (line.charge_code, line.amount, line.quantity, line.waived) == (
            "APP-FEE",
            Decimal("10.0000"),
            Decimal("1.0000"),
            False,
        )
        fees = reads.fees_tab(sr.request_row(kyle.id))
        assert fees["outstanding"]["display"] == "10.00"

        # ── "the clerk takes it" ──
        sr.collect_fee(
            pine_clerk, kyle.id, amount=Decimal("10.00"), method="cash", receipt_no="RCP-26-9819"
        )
        assert sr.fee_total_to_collect(kyle.id)["outstanding"] == Decimal("0.0000")

        # ── "… or waives it" ──
        again = sr.create_from_portal(dict(PORTAL), application=True)
        [owed] = _lines(again.id)
        assert owed.amount == Decimal("10.0000")
        sr.waive_fee_line(pine_clerk, owed.id, reason="No fee here")
        assert _lines(again.id)[0].waived is True
        assert sr.fee_total_to_collect(again.id)["outstanding"] == Decimal("0.0000")

    # ── "A utility that charges nothing prices its fee at $0.00" ──
    with tenant_context(oak_ridge.id):
        _app_fee(elena, "0.00")
        free = sr.create_from_portal(dict(PORTAL), application=True)
        [zero] = _lines(free.id)
        assert (zero.charge_code, zero.amount) == ("APP-FEE", Decimal("0.0000"))

        # ── "… its requests read 'nothing to collect' with no collect button" ──
        fees = reads.fees_tab(sr.request_row(free.id))
        assert len(fees["lines"]) == 1  # a line IS there (no line keeps the button)
        assert Decimal(fees["outstanding"]["amount"]) == Decimal("0")
        # The very string FeesBlock's `owesNothing` reads: /^0+(\.0+)?$/.
        assert re.fullmatch(r"0+(\.0+)?", fees["outstanding"]["amount"].strip())
        assert fees["outstanding"]["display"] == "0.00"
        assert fees["shortfall_is_open_balance"] is False
        # Nothing owed does not hold approval up.
        assert (
            rules.fee_condition(
                outstanding_lines=fees["outstanding_lines"],
                outstanding_amount=Decimal(fees["outstanding"]["amount"]),
            ).blocking
            is False
        )

        # ── and the waive is still there on the $0.00 line ──
        served = fees["lines"][0]
        assert (served["waived"], served["settled_at"]) == (False, None)
        assert sr.waive_fee_line(elena, zero.id, reason="No fee here").waived is True
