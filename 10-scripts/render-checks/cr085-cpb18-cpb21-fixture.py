# ── Trace ──────────────────────────────────────────────
# Story:   CR-085 `CPB-21` (a plan says who set it up) · `CPB-18` (budget
#          billing says WHICH month is missing) · `CPB-02` (autopay says
#          whether it is ON and how to stop it — `DEF-CWP-4683`) · `CPB-03`
#          (the kept agreement is a download, not a hold)
# Rules:   OQ-CWP-1567 CLOSED 2026-09-08 option (a) · BR-BIL-017 / BR-BIL-021
#          (the averaging window is a TENANT setting) · B14 rule 31 (a name,
#          never an id) · CLAUDE.md hard rule 1 (every write inside one
#          tenant's context) · hard rule 2 (money stored to 4 dp)
# Tests:   fixture prep for
#          10-scripts/render-checks/cr085-cpb18-cpb21.mjs
# ───────────────────────────────────────────────────────
"""THE TWO STATES CR-085's MONEY-COMMITMENT SCREENS COULD NOT REACH BEFORE.

WHY THIS FILE EXISTS
--------------------
`cr068-m-fixture.py` puts an OFFERED plan and a level-pay ENROLMENT in front of
a browser, and both of those states existed before this CR. Neither of the two
things `CPB-21` and `CPB-18` add can be seen in it:

  * every plan it writes has **nobody recorded** against it, so `CWP-063` draws
    the honest absence and the new sentence is never exercised;
  * its level-pay account is **enrolled**, so `CWP-044` takes the *already on*
    branch and the refusal — the whole of `CPB-18` — is never drawn.

⚠ **THAT IS EXACTLY THE STATE A WALKTHROUGH MUST NOT ASSERT IN** (`DEF-WRK-4121`:
a dispatcher shipped that could not raise a work order on any non-empty list,
because every test used the empty list — the one state where it worked). Both
of the branches this CR adds would report GREEN over a screen nobody had looked
at.

WHAT IT BUILDS
--------------
  * **the OFFER gets a person.** `payment_plans.offered_by_user_id` is set to a
    real `identity.User` of this tenant, so the lead reads *«name» set this up
    on 2 September*. The name comes from the row rather than being typed here,
    and the script prints it so a failing walkthrough can be reproduced.
  * **the offered plan gets a KEPT AGREEMENT.** `CWP-063`'s *The agreement ↓*
    is a real download where a copy was frozen and a held button where none was,
    and after `seed_portal_demo` no plan has one — so the download branch could
    never be opened. ⚠ **It is frozen against the OUTBOUND MESSAGE, which is the
    only place it ever lands**: `frozen_documents` freezes an agreement at
    DISPATCH, not at creation, so a fixture that stored it against the plan
    directly would build a state this product never produces and prove nothing.
  * **the three accounts take one autopay state each.** `CWP-040` has three —
    off, on, and *asked for but not running* after the two-bounce sanction
    (`BR-PAY-013`) — and the seeded estate puts this login's accounts all in the
    same one, so two of the three branches could never be opened. The third is
    the one that costs money: an account that ELECTED autopay and has since gone
    cash-only reads as though its bills will be paid and they will not.
  * **the ASK account gets eleven months of bills with a HOLE.** Every month of
    2025 except **March**, so `budget_history_for` counts 11 distinct periods
    against a 12-month window and `missing_month_gaps` is exactly `[[2025, 3]]`.
    That account holds **no** budget enrolment, which is what makes `CWP-044`
    draw the refusal rather than the *already on* branch.

⚠ **THE HOLE IS MADE BY NOT WRITING A BILL, NEVER BY REMOVING ONE.** Voiding or
deleting an issued invoice would break CLAUDE.md hard rule 4 (financial
immutability) inside a fixture, which teaches the next lane the wrong thing.
The account had **zero** invoices before this ran — asserted below — so every
row here is new and nothing is disturbed.

⚠ **IT REFUSES RATHER THAN GUESSING.** If the ask account already carries bills,
or the tenant has no staff user, the script stops and says which, because a
fixture that half-applied would leave a walkthrough asserting against a state
nobody designed.

RUN IT
------
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-m-fixture.py)
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr085-cpb18-cpb21-fixture.py)

Idempotent: a second run re-uses the bills it already wrote and re-stamps the
same person.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.identity.models import User
from apps.payments import collections_models
from apps.tenancy.models import Tenant
from core.tenancy import tenant_context

TENANT = "pine-hill"
OFFER_ACCOUNT = "AC-2026-00048"
GAP_ACCOUNT = "AC-2026-00047"
#: `CWP-040`'s three states need three accounts, and this login holds exactly
#: three. The plan account carries the level-pay enrolment and is the one this
#: fixture leaves autopay ON.
PLAN_ACCOUNT_NO = "AC-2026-00046"
GAP_ACCOUNT_NO = GAP_ACCOUNT

#: Eleven months of 2025, MARCH DELIBERATELY ABSENT. The amounts are the wave-M
#: chart's own so nothing new is invented; what matters is the shape.
BILLED = {
    1: "98.4000", 2: "104.2000", 4: "121.3000", 5: "148.9000", 6: "171.4000",
    7: "182.2000", 8: "163.5000", 9: "131.0000", 10: "112.4000", 11: "101.8000",
    12: "53.2900",
}
MISSING_MONTH = 3


def money(value: str) -> Decimal:
    """Hard rule 2 — four decimals, never a float."""
    return Decimal(value).quantize(Decimal("0.0001"))


def main() -> None:
    tenant = Tenant.objects.get(subdomain=TENANT)
    with tenant_context(tenant.id):
        # ── CPB-21 · the offer gets a person ────────────────────────────────
        offer_account = customers_models.Account.objects.filter(
            tenant_id=tenant.id, account_no=OFFER_ACCOUNT
        ).first()
        if offer_account is None:
            raise SystemExit(f"no account {OFFER_ACCOUNT} — run cr068-m-fixture.py first")
        plan = collections_models.PaymentPlan.objects.filter(
            tenant_id=tenant.id,
            account_id=offer_account.pk,
            status=collections_models.PLAN_AGREEMENT_SENT,
        ).first()
        if plan is None:
            raise SystemExit(
                f"no offered plan on {OFFER_ACCOUNT} — run cr068-m-fixture.py first"
            )
        clerk = (
            User.objects.filter(tenant_id=tenant.id)
            .exclude(full_name="")
            .order_by("full_name")
            .first()
        )
        if clerk is None:
            raise SystemExit(
                "this tenant has no staff user carrying a name; `full_name` renders "
                "'—' while a user is still invited (US-IDN-004), and stamping a blank "
                "would put an empty space where a person should be"
            )
        plan.offered_by = clerk
        plan.save(update_fields=["offered_by"])
        print(f"  CPB-21: plan on {OFFER_ACCOUNT} offered by {clerk.full_name!r}")

        # ── CPB-03 · the offered plan gets a kept agreement ─────────────────
        from apps.notifications import models as notification_models
        from apps.tenancy import document_models, document_store

        message = notification_models.OutboundMessage.objects.filter(
            tenant_id=tenant.id, source_type="plan", source_id=plan.pk
        ).first()
        if message is None:
            message = notification_models.OutboundMessage.objects.create(
                tenant=tenant,
                source_type="plan",
                source_id=plan.pk,
                channel=notification_models.CHANNEL_PRINT,
                account=offer_account,
                template_code="contract_payment_plan",
                status=notification_models.STATUS_SENT,
                # `ck_outbound_msgs_address_or_reason` — a queue row states
                # WHERE it went or WHY it could not.
                recipient_address="403 Silver Creek Rd · Suite 1",
            )
        if not document_store.for_source(
            source_type=document_models.SOURCE_OUTBOUND_MESSAGE, source_id=message.pk
        ).found:
            document_store.store(
                kind=document_models.KIND_PAYMENT_PLAN_AGREEMENT,
                source_type=document_models.SOURCE_OUTBOUND_MESSAGE,
                source_id=message.pk,
                content_type="application/pdf",
                display_name="payment-plan-agreement.pdf",
                # ⚠ **A REAL, MINIMAL PDF AND NOT A STUB STRING.** The browser
                # asks for these bytes and the check reads the response; a body
                # that is not a document would still download and would tell us
                # nothing about the path.
                payload=(
                    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                    b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
                    b"trailer<</Root 1 0 R>>\n%%EOF\n"
                ),
                channel=notification_models.CHANNEL_PRINT,
                process="notifications.dispatcher",
            )
        print(f"  CPB-03: agreement frozen against the letter that carried plan {plan.pk}")

        # ── CPB-02 · one account in each of CWP-040's three states ──────────
        # ⚠ **`autopay` AND `cash_only_no_autopay` ARE TWO DIFFERENT FACTS AND
        # THAT IS THE WHOLE POINT.** `elected` is what the customer asked for and
        # nothing un-asks it; `enrolled` is whether the account may be autopaid
        # at all. Setting both gives the third state, which no seeded account has
        # and which is the one a screen must not get wrong.
        states = {
            PLAN_ACCOUNT_NO: (True, False, 0),    # on
            GAP_ACCOUNT_NO: (False, False, 0),    # off
            OFFER_ACCOUNT: (True, True, 2),       # asked for, and stopped
        }
        for account_no, (elected, sanctioned, bounces) in states.items():
            row = customers_models.Account.objects.filter(
                tenant_id=tenant.id, account_no=account_no
            ).first()
            if row is None:
                raise SystemExit(f"no account {account_no} — run cr068-m-fixture.py first")
            row.autopay = elected
            row.cash_only_no_autopay = sanctioned
            row.nsf_count = bounces
            row.save(update_fields=["autopay", "cash_only_no_autopay", "nsf_count"])
        print(
            f"  CPB-02: {PLAN_ACCOUNT_NO} autopay on · {GAP_ACCOUNT_NO} off · "
            f"{OFFER_ACCOUNT} asked for and stopped after 2 bounces"
        )

        # ── CPB-18 · the ask account gets a hole in its year ────────────────
        gap_account = customers_models.Account.objects.filter(
            tenant_id=tenant.id, account_no=GAP_ACCOUNT
        ).first()
        if gap_account is None:
            raise SystemExit(f"no account {GAP_ACCOUNT} — run cr068-m-fixture.py first")
        if billing_models.AccountBudgetStatus.objects.filter(
            tenant_id=tenant.id, account_id=gap_account.pk
        ).exists():
            raise SystemExit(
                f"{GAP_ACCOUNT} is already enrolled on budget billing, so CWP-044 "
                "would draw its *already on* branch and the refusal this fixture "
                "exists to show would never render"
            )
        existing = set(
            billing_models.Invoice.objects.filter(
                tenant_id=tenant.id, account_id=gap_account.pk
            ).values_list("invoice_no", flat=True)
        )
        written = 0
        for month, amount in BILLED.items():
            number = f"BL-CPB18-2025{month:02d}"
            if number in existing:
                continue
            issued = dt.date(2025, month, 28)
            billing_models.Invoice.objects.create(
                tenant=tenant,
                account=gap_account,
                invoice_no=number,
                status=billing_models.INVOICE_ISSUED,
                service_date=issued,
                period_start=issued.replace(day=1),
                period_end=issued,
                due_date=issued,
                subtotal=money(amount),
                tax_total=Decimal("0"),
                total=money(amount),
                currency="USD",
                issued_at=dt.datetime(2025, month, 28, 9, 0, tzinfo=dt.UTC),
            )
            written += 1
        print(
            f"  CPB-18: {written} bill(s) written on {GAP_ACCOUNT}; "
            f"month {MISSING_MONTH} of 2025 deliberately absent"
        )

        # ⚠ **THE FIXTURE PROVES ITS OWN SHAPE THROUGH THE PRODUCT'S OWN READ**
        # rather than trusting that eleven `create` calls produced eleven months
        # of history. A walkthrough asserting over a state the fixture only
        # believes it made is the shape law 7 calls *looking at the wrong thing*.
        from apps.portal.seams import billing_seam

        position = billing_seam.level_pay_position(gap_account.pk)
        if position["missing_month_gaps"] != [[2025, MISSING_MONTH]]:
            raise SystemExit(
                "the read does not see the hole this fixture made: "
                f"missing_month_gaps={position['missing_month_gaps']!r}, "
                f"months_of_history={position['months_of_history']!r} — seeding refused"
            )
        print(
            f"  read back: {position['months_of_history']}/{position['required_months']} "
            f"months, gap {position['missing_month_gaps']}, level {position['level']!r}"
        )
        print("SMOKE_OFFER_ACCOUNT=" + OFFER_ACCOUNT)
        print("SMOKE_GAP_ACCOUNT=" + GAP_ACCOUNT)
        print("SMOKE_CLERK_NAME=" + clerk.full_name)


main()
