# ── Trace ──────────────────────────────────────────────
# Story:   US-CWP-057 · US-CWP-058 · US-CWP-059 · US-CWP-056 (EP-CWP-10) — the
#          wave L demo script, 04-docs/05-modules/15-portal/10-execution-plan.md
#          lines 586-612: "$412.60 overdue 19 days; certificate to 30 Nov;
#          moratorium 1 Dec - 1 Mar".
# Rules:   BR-CWP-047 (the credit figure is re-read on every load, never
#          cached) · BR-CWP-089 (no portal form creates a protection) ·
#          BR-CWP-090 (three lifetimes) · BR-CWP-092 (an unmapped rung is an
#          absence) · CLAUDE.md hard rule 1 (every read and write inside one
#          tenant's context, and EXPLICITLY scoped because the seeding role
#          bypasses RLS) · hard rule 2 (money to 4 dp, displayed to 2)
# Tests:   fixture prep for
#          10-scripts/render-checks/cr068-l-overdue-and-protections.mjs
# ───────────────────────────────────────────────────────
"""The overdue account, the three protections, the refund and the two credits.

WHY THIS FILE EXISTS, AND WHY IT IS NOT IN THE SEEDER
-----------------------------------------------------
`seed_portal_demo` provisions Pine Hill and plants a sample estate, and
**measured on a freshly seeded database on 2026-09-06, every one of its
accounts owes `0.0000` and has no open bill at all.** That is correct for a
demo of the rest of the portal and it is fatal to a walkthrough of this wave,
because all four of wave L's screens are ABSENCES on an account in good
standing:

  * `/overdue` answers `overdue: false` and states one sentence,
  * `/protections` answers `any: false`,
  * `/money-back` answers `any: false`,
  * and `/help-paying` renders three routes but no moratorium.

⚠ **SO A WALKTHROUGH RUN AGAINST THE SEEDER ALONE WOULD PASS EVERY ASSERTION
IT MAKES ABOUT ROWS, BECAUSE THERE ARE NO ROWS.** That is `DEF-WRK-4121`'s
shape — a dispatcher proved on the one list state where the feature worked —
and it is the reason this file writes the state the screens are NORMALLY in
before anything is asserted. The walkthrough additionally checks that each
list HAS rows before asserting about them.

THE DATES ARE ANCHORED TO TODAY, AND THE MONEY IS NOT
-----------------------------------------------------
The demo script reads *"$412.60 overdue by 19 days"*. `days_overdue` is
computed by the server as `today - oldest_due_on` (`selectors.arrears_position`
passes `as_of=date.today()`), so a fixture that wrote the drawing's literal
`14 Aug` would print `19 days` on 2 September and something else on every other
day — a walkthrough that goes red because a night passed. **The intervals are
therefore taken from the drawing and the anchor is today**, which reproduces
the demo script's own sentence on any day it is run:

    due            today - 19      $412.60
    reminder       due + 7
    late fee       due + 10        $8.25
    first notice   due + 18
    final notice   due + 32        (a floor: "no earlier than")
    disconnection  due + 42        (a floor)

**The MONEY is fixed and never anchored** — `412.60`, `95.00`, `25.88`,
`89.80` and the `2026-11-30` certificate expiry are the signed figures the
walkthrough asserts, and a fixture that computed any of them would be asserting
its own arithmetic instead of the product's.

IDEMPOTENT
----------
Every row it writes is named (`BL-L-*`, `DSC-L-*`, `CN-L-*`, the three
protection kinds on the three accounts it uses, and the `l-*@example.test`
credentials) and a replay deletes those and rebuilds them. It touches nothing a
person created and nothing another lane seeded.

RUN IT
------
    eval "$(10-scripts/proof-db.sh clone cwpl --export)"
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    python3 06-backend/manage.py migrate && \
      python3 06-backend/manage.py seed_portal_demo
    python3 10-scripts/render-checks/cr068-l-fixture.py

    # and, between two loads of CWP-045 (demo script step 6):
    python3 10-scripts/render-checks/cr068-l-fixture.py --spend-a-credit
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

BACKEND = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "06-backend",
)
sys.path.insert(0, BACKEND)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from core.tenancy import tenant_context  # noqa: E402

# ── the figures, and every one of them is the demo script's own ────────────
OWED = Decimal("412.60")
LATE_FEE = Decimal("8.25")
RECONNECT_FEE = Decimal("95.00")
CREDIT = Decimal("-25.88")
REFUND = Decimal("89.80")
CERTIFICATE_ENDS = date(2026, 11, 30)
MORATORIUM_FROM = date(2026, 12, 1)
MORATORIUM_UNTIL = date(2027, 3, 1)

DAYS_OVERDUE = 19

OVERDUE_EMAIL = "l-overdue@example.test"
UNMAPPED_EMAIL = "l-fiveday@example.test"
CLEAR_EMAIL = "l-clear@example.test"
PASSWORD = "Elm-Street-1408"

BILL_PREFIX = "BL-L-"
CASE_PREFIX = "DSC-L-"
CREDIT_PREFIX = "CN-L-"


def _tenant():
    from apps.tenancy import models as tenancy_models

    return tenancy_models.Tenant.objects.get(subdomain="pine-hill")


def _actor(tenant):
    """Pine Hill's provisioned owner, as a real user id.

    ⚠ **`record_protection` IS `@require_role(SYSTEM_ADMIN, BILLING_CLERK)`**,
    so a fixture that passed `None` here is refused — correctly, because a
    protection is a decision a named person made and the audit row has to say
    who. Reusing `sample_data._owner_actor` keeps the writes attributable to
    the same user the seeder itself writes as, rather than to an invented id.
    """
    from apps.portal import sample_data

    return sample_data._owner_actor(
        tenant.id, sample_data.PINE_HILL["signup"]["owner"]["email"]
    )


def _accounts(tenant, how_many: int):
    """Three DISTINCT customers' accounts — one credential each.

    ⚠ **THE FILTER IS EXPLICIT ABOUT THE TENANT AND IT HAS TO BE**
    (CLAUDE.md hard rule 1). This runs as a seeding role with `rolsuper=t`, so
    RLS is skipped for every query the process makes and an unscoped queryset
    silently returns ANOTHER tenant's account — which the payments seam then
    refuses by name, reading like a broken product rather than like a leak.
    Measured here on 2026-09-06: the first unscoped `Account.objects.all()`
    returned a Brazos Bend row.

    ⚠ **ONE ACCOUNT PER CUSTOMER, because a credential is attached to the
    CUSTOMER** (`credentials.create_credential` resolves `CustomerAccount`), so
    two accounts of one customer would land in one switcher and the *absent
    screen* steps could not be walked separately.

    ⚠ **AND EVERY ONE MUST START WITH NO OPEN BILL, WHICH THE FIRST DRAFT DID
    NOT CHECK AND WHICH SILENTLY BROKE EVERY FIGURE IN THIS FILE.** `owing` is
    the SUM of an account's open bills and `due_on` is the OLDEST of their due
    dates (`payments_seam.account_balance`), so an account the sample plant
    already left `$312.66` in arrears answered `$725.26` overdue by `38 days`
    where this fixture intended `$412.60` by `19`. Nothing failed: the screen
    rendered a perfectly ordinary ladder, the arithmetic was the product's own
    and correct, and only comparing it against the demo script caught it. The
    account in good standing was not in good standing either, so the three
    *this screen is absent* steps would have proved nothing at all.

    **So the pick is BY POSITION rather than by name** — an account with zero
    open bills, which the fixture then owns completely.
    """
    from apps.customers import models as customers_models
    from apps.portal.seams import payments_seam

    picked: list = []
    seen: set = set()
    with tenant_context(tenant.id):
        rows = (
            customers_models.CustomerAccount.objects.filter(tenant_id=tenant.id)
            .select_related("account")
            .order_by("account__account_no")
        )
        for link in rows:
            if link.customer_id in seen or link.account is None:
                continue
            position = payments_seam.account_balance(link.account.pk)
            #: ⚠ **THE TEST IS `owing`, NOT `open_bill_count`, AND THE
            #: DIFFERENCE IS NOT COSMETIC.** `account_balance` composes TWO
            #: reads: `open_bills.open_bill_position` (which supplies
            #: `open_bill_count`) and `payments_billing_seam
            #: .outstanding_positions` (which supplies `owing`). On this
            #: database they DISAGREE — measured 2026-09-06, account
            #: `AC-2026-00001` answered `open_bill_count: 0` while carrying an
            #: issued, unpaid `BL-2607-000001` for `$174.22`, and `owing` said
            #: `174.2200`. A picker that trusted the count therefore chose an
            #: account that was not clean, and the overdue screen went on to
            #: read `$725.26 overdue by 46 days` — the product's own arithmetic,
            #: correct, over a fixture that had lied to it.
            #: **`owing` is the number the screen prints, so `owing` is the
            #: number the pick is made on.** (The disagreement itself is
            #: reported as a finding rather than worked around here.)
            if Decimal(position["owing"] or "0") != Decimal("0") or position["due_on"] is not None:
                continue
            seen.add(link.customer_id)
            picked.append(link.account)
            if len(picked) == how_many:
                break
    if len(picked) < how_many:
        raise SystemExit(
            f"only {len(picked)} distinct customers on pine-hill have no open bill; "
            f"the fixture needs {how_many}. Was seed_portal_demo run?"
        )
    return picked


def _accounts_from_last_run(tenant):
    """The three accounts a previous run used, found through its credentials.

    ⚠ **WITHOUT THIS THE FIXTURE CANNOT BE RUN TWICE, AND THE REASON IS ITS OWN
    GUARD.** `_accounts` picks accounts whose `owing` is zero — and after one
    run the overdue account owes `$412.60`, so a second run picks three
    DIFFERENT accounts and `_money_already_there` correctly refuses, because
    `BL-L-0141` is on somebody else. The financial rows cannot be moved (hard
    rule 4), so the only way to replay is to go back to the SAME accounts, and
    the credentials this fixture created are the record of which ones they
    were. Resolved BEFORE `_wipe` deletes them.
    """
    from apps.customers import models as customers_models
    from apps.portal import models as portal_models

    found = []
    with tenant_context(tenant.id):
        for email in (OVERDUE_EMAIL, UNMAPPED_EMAIL, CLEAR_EMAIL):
            credential = portal_models.PortalCredential.objects.filter(
                tenant_id=tenant.id, email=email
            ).first()
            if credential is None:
                return None
            link = customers_models.CustomerAccount.objects.filter(
                tenant_id=tenant.id, customer_id=credential.customer_id
            ).select_related("account").first()
            if link is None or link.account is None:
                return None
            found.append(link.account)
    return found


def _wipe(tenant, accounts) -> None:
    """Delete only what a previous run of THIS file wrote **and may lawfully go**.

    ⚠ **THE MONEY ROWS CANNOT BE DELETED AND THE FIRST DRAFT ASSUMED THEY
    COULD.** CLAUDE.md hard rule 4 is enforced in the DATABASE, not by
    convention, and a replay of this fixture met it head on:

        django.db.utils.ProgrammingError: BR-BIL-004: credit note CN-L-0001
        has been issued and cannot be deleted
        CONTEXT: PL/pgSQL function billing_credit_note_immutable() line 7

    An issued credit note may not be deleted and its amount, account, source
    invoice and number may not be changed either; issued invoices, payments and
    refunds are held the same way. **That is the product being right**, so the
    fixture is what changes: cases, notices, protections and credentials are
    ordinary records and are rebuilt on every run, and the financial rows are
    written ONCE and then reused. `build()` refuses rather than duplicating
    them if it finds them dated for a different day — see `_money_already_there`.
    """
    from apps.customers import disconnects
    from apps.portal import models as portal_models

    ids = [a.pk for a in accounts]
    with tenant_context(tenant.id):
        # ⚠ **THE CREDENTIALS ARE LEFT ALONE, AND A REPLAY TAUGHT US WHY.**
        # `PortalSession.portal_credential` is PROTECT, so once the walkthrough
        # has signed in, deleting the credential raises
        # `ProtectedError: ... referenced through protected foreign keys`. That
        # is the product being right — a sign-in is a record — so `build()`
        # creates a credential only when there is not one already.
        disconnects.AccountProtection.objects.filter(
            tenant_id=tenant.id, account_id__in=ids
        ).delete()
        # A notice points at a case, so the notices go first.
        cases = disconnects.DisconnectCase.objects.filter(
            tenant_id=tenant.id, case_no__startswith=CASE_PREFIX
        )
        disconnects.DisconnectNotice.objects.filter(
            tenant_id=tenant.id, case__in=cases
        ).delete()
        cases.delete()
    return None


def _money_already_there(tenant, account, due_on: date):
    """The bill this fixture writes, if a previous run already wrote it.

    Returns the row when it is there AND still dated for the run we are about
    to make; raises when it is there and dated for a different day, because
    hard rule 4 leaves no way to move it and a second bill would silently
    double `owing` — the screen would read `$825.20` and be arithmetically
    right about a fixture that had lied to it.
    """
    from apps.billing import models as billing_models

    row = billing_models.Invoice.objects.filter(
        tenant_id=tenant.id, invoice_no=f"{BILL_PREFIX}0141"
    ).first()
    if row is None:
        return None
    #: ⚠ **THE ACCOUNT IS PART OF THE IDENTITY AND KEYING ON THE NUMBER ALONE
    #: WAS A BUG THIS FIXTURE ACTUALLY HAD.** `_accounts` picks by POSITION —
    #: the first customers with no open bill — so a second run picks DIFFERENT
    #: accounts, and a check that asked only *does BL-L-0141 exist* answered
    #: yes about the previous run's account and skipped writing the bill for
    #: the new one. The overdue screen then rendered *nothing is overdue* and
    #: every assertion about the ladder would have failed pointing at the
    #: screen rather than at the fixture.
    if row.account_id != account.pk:
        raise SystemExit(
            f"{BILL_PREFIX}0141 is on this database against a DIFFERENT account "
            f"({row.account_id}) than this run picked ({account.pk}). An issued invoice "
            f"cannot be moved or deleted (hard rule 4), so start from a fresh clone:  "
            f"10-scripts/proof-db.sh drop cwpl && 10-scripts/proof-db.sh clone cwpl "
            f"--template <the newest sbh_tpl_*>"
        )
    if row.due_date != due_on:
        raise SystemExit(
            f"{BILL_PREFIX}0141 is already on this database due {row.due_date}, and this run "
            f"wants it due {due_on}. An issued invoice cannot be moved or deleted (hard rule 4), "
            f"so start from a fresh clone:  10-scripts/proof-db.sh drop cwpl && "
            f"10-scripts/proof-db.sh clone cwpl"
        )
    return row


def _bill(tenant, account, *, number, total, issued_on, due_on):
    from apps.billing import models as billing_models

    amount = Decimal(total)
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=number,
        status=billing_models.INVOICE_ISSUED,
        service_date=issued_on,
        period_start=issued_on.replace(day=1),
        period_end=issued_on,
        due_date=due_on,
        subtotal=amount,
        tax_total=Decimal("0"),
        total=amount,
        issued_at=datetime(issued_on.year, issued_on.month, issued_on.day, 9, 0, tzinfo=UTC),
    )


def _reconnect_charge(tenant) -> None:
    """The tenant's `CC-RECON` row — **the ONE place the fee comes from.**

    `BR-BIL-007`: never a literal `$95.00` in the product. The portal reads
    whatever the utility configured, through `disconnects.reconnection_terms`,
    so the fixture configures it and the screen is left to find it.
    """
    from apps.customers import disconnects
    from apps.rating import models as rating_models

    existing = rating_models.Charge.objects.filter(
        tenant_id=tenant.id, code=disconnects.RECONNECT_CHARGE_CODE
    ).first()
    if existing is not None:
        if existing.amount != RECONNECT_FEE:
            existing.amount = RECONNECT_FEE
            existing.save(update_fields=["amount"])
        return
    rating_models.Charge.objects.create(
        tenant=tenant,
        code=disconnects.RECONNECT_CHARGE_CODE,
        name="Reconnection",
        amount_rule="flat",
        amount=RECONNECT_FEE,
    )


def build() -> dict:
    from apps.customers import disconnects
    from apps.portal import credentials, models as portal_models

    tenant = _tenant()
    actor = _actor(tenant)
    #: A replay goes back to the accounts the last run used; a first run picks.
    picked = _accounts_from_last_run(tenant) or _accounts(tenant, 3)
    overdue_account, unmapped_account, clear_account = picked
    _wipe(tenant, [overdue_account, unmapped_account, clear_account])

    today = date.today()
    due_on = today - timedelta(days=DAYS_OVERDUE)
    reminder_on = due_on + timedelta(days=7)
    late_fee_on = due_on + timedelta(days=10)
    first_notice_on = due_on + timedelta(days=18)
    final_notice_on = due_on + timedelta(days=32)
    cut_on = due_on + timedelta(days=42)
    issued_on = due_on - timedelta(days=17)

    with tenant_context(tenant.id):
        _reconnect_charge(tenant)

        # ── 1 · the overdue account: ONE open bill, so `owing` is exactly the
        #        demo script's figure and nothing else contributes to it.
        #        ⚠ Written once and then REUSED — hard rule 4 forbids deleting
        #        it, so a replay must not write a second one.
        if _money_already_there(tenant, overdue_account, due_on) is None:
            _bill(
                tenant,
                overdue_account,
                number=f"{BILL_PREFIX}0141",
                total=str(OWED),
                issued_on=issued_on,
                due_on=due_on,
            )
        case = disconnects.DisconnectCase.objects.create(
            tenant=tenant,
            account=overdue_account,
            case_no=f"{CASE_PREFIX}0001",
            sequence=disconnects.SEQ_SERVICE,
            state=disconnects.STATE_NOTICE_SENT,
            # ⚠ **THE CASE HAS REACHED THE RUNG ITS LAST NOTICE ANNOUNCED.**
            # An earlier draft left this at `TIER_1` while seeding a `TIER_2`
            # notice, and the screen then drew *Ten-day notice* TWICE — once as
            # sent and once as the next step — because `ladder_state.next_tier`
            # is computed from the CASE's tier. The drawing's fifth rung is
            # *Final notice*, and it is the next rung only if the case is at
            # the ten-day one.
            tier=disconnects.TIER_2,
            tier_reached_on=first_notice_on,
            amount_owed_at_open=OWED,
            currency="USD",
            opened_on=reminder_on,
            next_step_due=final_notice_on,
            cut_scheduled_for=cut_on,
        )
        # ⚠ **TWO NOTICES, BECAUSE THE DRAWING SHOWS TWO.** `P43` puts a
        # *reminder sent* and a *first notice sent* on the ladder before the
        # final one, and the product builds a `notice_sent` row per
        # `DisconnectNotice`. Seeding one would have drawn a one-notice ladder
        # and proved nothing about the ordering.
        disconnects.DisconnectNotice.objects.create(
            tenant=tenant, case=case, tier=disconnects.TIER_1, issued_on=reminder_on
        )
        disconnects.DisconnectNotice.objects.create(
            tenant=tenant, case=case, tier=disconnects.TIER_2, issued_on=first_notice_on
        )

        # ── 2 · the three protections, three lifetimes (`BR-CWP-090`) ───────
        disconnects.record_protection(
            actor,
            overdue_account.pk,
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=due_on - timedelta(days=5),
            expires_on=CERTIFICATE_ENDS,
        )
        disconnects.record_protection(
            actor,
            overdue_account.pk,
            kind=disconnects.PROTECTION_PLAN,
            effective_from=due_on + timedelta(days=6),
        )
        disconnects.record_protection(
            actor,
            overdue_account.pk,
            kind=disconnects.PROTECTION_MORATORIUM,
            effective_from=MORATORIUM_FROM,
            expires_on=MORATORIUM_UNTIL,
        )

        # ── 3 · money coming back: one refund in flight, two credits ────────
        # ⚠ **THE CREDITS HANG OFF THE OVERDUE BILL ITSELF, AND AN EARLIER
        # DRAFT ADDED A SECOND BILL FOR THEM TO POINT AT.** That draft marked
        # the second bill `paid` so it would not move the headline — and it
        # moved it anyway, to `$551.04`, because `owing` is computed from what
        # the account owes rather than from an invoice's status column.
        # Setting a status is not making a payment. One bill, one figure.
        credited_bill = _bill_once(
            tenant,
            overdue_account,
            number=f"{BILL_PREFIX}0141",
            total=str(OWED),
            issued_on=issued_on,
            due_on=due_on,
        )
        _credit_once(tenant, overdue_account, number=f"{CREDIT_PREFIX}0001", invoice=credited_bill)
        _credit_once(tenant, overdue_account, number=f"{CREDIT_PREFIX}0002", invoice=credited_bill)
        _refund_once(tenant, overdue_account)

        # ── 4 · the five-day rung: an ABSENCE, never a neighbour's chip ─────
        # ⚠ The unmapped rung is stored on the CASE and never on a notice —
        # `ck_disconnect_notice_tier` restricts a notice to the three lawful
        # chips (`test_us_cwp_057_tc3`'s own finding).
        _bill_once(
            tenant,
            unmapped_account,
            number=f"{BILL_PREFIX}0142",
            total="212.00",
            issued_on=issued_on,
            due_on=due_on,
        )
        disconnects.DisconnectCase.objects.create(
            tenant=tenant,
            account=unmapped_account,
            case_no=f"{CASE_PREFIX}0002",
            sequence=disconnects.SEQ_SERVICE,
            state=disconnects.STATE_NOTICE_SENT,
            tier=disconnects.PAYMENTS_RUNG_5_DAY,
            tier_reached_on=first_notice_on,
            amount_owed_at_open=Decimal("212.00"),
            currency="USD",
            opened_on=reminder_on,
            next_step_due=final_notice_on,
        )

        # ── 5 · the clear account gets NOTHING, which is the point ──────────

        for account, email in (
            (overdue_account, OVERDUE_EMAIL),
            (unmapped_account, UNMAPPED_EMAIL),
            (clear_account, CLEAR_EMAIL),
        ):
            if portal_models.PortalCredential.objects.filter(
                tenant_id=tenant.id, email=email
            ).exists():
                continue
            credentials.create_credential(
                tenant.id,
                account=account,
                email=email,
                password=PASSWORD,
                otp_channel=portal_models.CHANNEL_SMS,
            )

    return {
        "tenant": str(tenant.id),
        "overdue_account": overdue_account.account_no,
        "unmapped_account": unmapped_account.account_no,
        "clear_account": clear_account.account_no,
        "due_on": due_on.isoformat(),
        "late_fee_on": late_fee_on.isoformat(),
        "days_overdue": DAYS_OVERDUE,
    }


def _bill_once(tenant, account, *, number, total, issued_on, due_on):
    """The bill if it is already there, else a new one. Hard rule 4."""
    from apps.billing import models as billing_models

    row = billing_models.Invoice.objects.filter(
        tenant_id=tenant.id, invoice_no=number
    ).first()
    if row is not None:
        return row
    return _bill(
        tenant, account, number=number, total=total, issued_on=issued_on, due_on=due_on
    )


def _credit_once(tenant, account, *, number, invoice):
    from apps.billing import models as billing_models

    row = billing_models.CreditNote.objects.filter(
        tenant_id=tenant.id, credit_note_no=number
    ).first()
    if row is not None:
        return row
    return _credit(tenant, account, number=number, invoice=invoice)


def _refund_once(tenant, account):
    from apps.payments import models as payments_models

    row = payments_models.Refund.objects.filter(
        tenant_id=tenant.id, account_id=account.pk, reference="10241"
    ).first()
    if row is not None:
        return row
    return _refund(tenant, account)


def _settle(tenant, invoice) -> None:
    """Mark a bill settled so it leaves the open position.

    Written against the model rather than through the payment service on
    purpose: the point of this row is to be a bill a CREDIT was used on, not to
    prove anything about how a payment is taken, and a real payment would post
    a ledger pair this walkthrough never looks at.
    """
    from apps.billing import models as billing_models

    for field in ("status",):
        if hasattr(invoice, field):
            setattr(invoice, field, billing_models.INVOICE_PAID)
    invoice.save(update_fields=["status"])


def _credit(tenant, account, *, number, invoice):
    from apps.billing import models as billing_models

    return billing_models.CreditNote.objects.create(
        tenant=tenant,
        account=account,
        credit_note_no=number,
        original_invoice=invoice,
        amount=CREDIT,
        currency="USD",
        reason="goodwill after a reading dispute",
        issued_at=datetime(2026, 7, 12, 9, 0, tzinfo=UTC),
    )


def _refund(tenant, account):
    from apps.payments import models as payments_models

    return payments_models.Refund.objects.create(
        tenant=tenant,
        account=account,
        amount=REFUND,
        currency="USD",
        status="issued",
        method=payments_models.REFUND_METHOD_CHECK,
        reference="10241",
        reason="final bill overpayment",
        requested_at=datetime(2026, 9, 18, 9, 0, tzinfo=UTC),
        approved_at=datetime(2026, 9, 19, 9, 0, tzinfo=UTC),
        issued_at=datetime(2026, 9, 21, 9, 0, tzinfo=UTC),
    )


def spend_a_credit() -> dict:
    """Demo script step 6 — *the credit figure changes between two loads*.

    ⚠ **THIS IS THE ONLY WAY `BR-CWP-047` CAN BE PROVED IN A BROWSER.** The
    rule is that the credit figure is re-read on every load and never cached.
    A screen that cached would show the SAME credits after this runs, and **no
    assertion made on a single page load can tell the two implementations
    apart** — which is exactly the shape of a check that cannot fail. So the
    walkthrough loads `CWP-045`, calls this, loads it again and compares the
    two readings.

    ⚠ **AND IT ISSUES A THIRD CREDIT RATHER THAN REMOVING ONE, BECAUSE THE
    DATABASE REFUSES TO REMOVE ONE.** The first draft of this file deleted
    `CN-L-0002` and PostgreSQL answered:

        BR-BIL-004: credit note CN-L-0002 has been issued and cannot be deleted

    `billing_credit_note_immutable` refuses a DELETE outright on an issued row
    and refuses any UPDATE that moves its amount, account, source invoice,
    number or issue date — CLAUDE.md hard rule 4, enforced by the database
    rather than by agreement. **Hard rule 4 also says what to do instead:
    corrections are NEW ROWS**, so the change this makes is a third credit
    note, issued while the customer has the page open. That is a real thing a
    clerk does, it changes what the screen must say, and it is lawful.
    """
    from apps.billing import models as billing_models

    tenant = _tenant()
    with tenant_context(tenant.id):
        source = billing_models.CreditNote.objects.filter(
            tenant_id=tenant.id, credit_note_no=f"{CREDIT_PREFIX}0001"
        ).select_related("account", "original_invoice").first()
        if source is None:
            raise SystemExit(f"{CREDIT_PREFIX}0001 is not there — run the fixture first")
        # ⚠ **A FRESH NUMBER EVERY TIME, BECAUSE THE ROW CANNOT BE TAKEN BACK.**
        # A first draft always wrote `CN-L-0003`; on the second run of the
        # walkthrough it found that row already there, changed NOTHING, and the
        # re-read assertion went red reading `3 → 3`. The assertion was right —
        # nothing had changed — and the fixture was the thing at fault, which is
        # the failure mode worth naming: a step whose whole job is *make one
        # thing different* must not be idempotent.
        taken = set(
            billing_models.CreditNote.objects.filter(
                tenant_id=tenant.id, credit_note_no__startswith=CREDIT_PREFIX
            ).values_list("credit_note_no", flat=True)
        )
        number = next(
            f"{CREDIT_PREFIX}{n:04d}" for n in range(3, 1000)
            if f"{CREDIT_PREFIX}{n:04d}" not in taken
        )
        _credit(
            tenant,
            source.account,
            number=number,
            invoice=source.original_invoice,
        )
    return {"issued": number}


if __name__ == "__main__":
    if "--spend-a-credit" in sys.argv:
        print(spend_a_credit())
    else:
        summary = build()
        for key, value in summary.items():
            print(f"  {key}: {value}")
        print(
            f"  sign in: {OVERDUE_EMAIL} / {UNMAPPED_EMAIL} / {CLEAR_EMAIL}  (password {PASSWORD})"
        )
