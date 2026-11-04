# ── Trace ──────────────────────────────────────────────
# Change:  CR-068 wave Q — *Pay now, autopay, refunds and fees*
#          (04-docs/05-modules/15-portal/10-execution-plan.md, task Q4)
# Stories: US-CWP-045 · US-CWP-047 · US-CWP-049 · US-CWP-050
# Rules:   CLAUDE.md hard rule 1 (every read and write inside one tenant's
#          context, and the TENANT IN THE QUERY — not left to RLS, which the
#          local settings bypass) · hard rule 2 (money 4 dp stored, 2 dp shown) ·
#          BR-CWP-029 (a credential attaches to somebody ALREADY ON FILE)
# Tests:   this is fixture prep for
#          10-scripts/render-checks/cr068-q-pay-now-autopay-refunds.mjs
# ───────────────────────────────────────────────────────
"""THE STATE WAVE Q's FOUR SCREENS ARE NORMALLY IN — never the state they default to.

WHY THIS FILE EXISTS, AND IT IS THE WHOLE POINT OF IT
----------------------------------------------------
`DEF-WRK-4121` shipped a dispatcher who could not raise a work order on any
non-empty list, because every test used the empty list — **the one state where
it worked**. Wave Q's four screens have exactly that trap waiting, and
`seed_portal_demo` walks straight into it:

    instruments             0   -> CWP-038 draws its EMPTY state and the Pay
                                   control is held on `no_saved_method`
    integration_connection  0   -> ...and held on `no_provider` underneath that,
                                   so a run would "pass" having never priced a
                                   payment, never pressed Pay and never written
                                   a payment row
    refunds                 1   -> on ONE account out of 52, which a login
                                   picked by any other rule will not hold
    portal service requests 0   -> CWP-050 draws *nothing to pay* and the
                                   arithmetic the wave exists for is never shown

**A walkthrough run against that database is green and proves almost nothing.**
So this file puts one account into the shape the demo script describes, and the
walkthrough asserts the state is really there before it asserts anything about
it.

WHAT IT MAKES, AND WHY EACH PIECE
---------------------------------
  1. **A login** on the account holding the MOST OPEN BILLS with an amount
     owing. Two open bills is what `US-CWP-045` TC-4/TC-5 need — *oldest first,
     by the tenant's rule* is unprovable on an account holding one.
  2. **A `payments_sandbox` connection**, sandbox environment, `behaviour:
     approve`. Without it `gateway.provider_for` finds nothing and every Pay
     control on the tenant is held on `no_provider`. Its `behaviour` is the
     switch demo-script step 3 asks for: the walkthrough flips this one row to
     `timeout` and back.
  3. **Two saved instruments** — `Chase ••••4021` (bank, verified) and
     `Visa ••••8812` (card, 11/2027) — which are the wireframe's own two rows.
     ⚠ `verified` is bank-only by database CHECK (`ck_instrument_verified_is_
     bank_only`), so the card is `active`; that is the product's rule and not a
     shortcut taken here.
  4. **A card payment and a refund drawn from it**, so `CWP-045` shows the
     answer the AS BUILT stamp records: *the money came in on the card ending
     8812; we have sent cheque 10241 instead*. And **a voided refund**, because
     `US-CWP-056` TC-4 is that a voided refund stays on the timeline.
  5. **An approved portal service request** carrying the signed fee lines —
     `$185.00` + `$150.00` payable, `$25.00` waived — so `CWP-050` reads
     `to_pay_now $335.00`.

IDEMPOTENT. Run it twice; the second run finds what it made and writes nothing.

RUN IT
------
    10-scripts/proof-db.sh clone <label> --export      # export the DATABASE_URL
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    (cd 06-backend && python3 manage.py seed_portal_demo)
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-q-fixture.py)
"""

import json
import uuid
from decimal import Decimal
from pathlib import Path

from django.utils import timezone

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.integrations import models as integration_models
from apps.payments import models as payments_models
from apps.portal import credentials
from apps.portal import models as portal_models
from apps.portal.seams import payments_seam
from apps.tenancy import models as tenancy_models
from apps.tenancy.models import Tenant
from core.tenancy import tenant_context

#: ⚠ **THE LOGIN IS NAMED AFTER THE ACCOUNT, AND THAT IS WHAT MAKES THE PAIR
#: RE-RUNNABLE.** The walkthrough PAYS — it settles both open bills — so the
#: account it ran against last time has nothing left to be oldest of, and a
#: fixed email pinned to that account would make every later run fail on
#: *"0 open bills"*: a truthful failure about the fixture rather than about the
#: product. So the account is chosen fresh each run and the email follows it,
#: and the pair is handed to the walkthrough through `HANDOFF` below rather
#: than guessed at both ends.
EMAIL_TEMPLATE = "q-payer+{account_no}@example.test"
PASSWORD = "Pine-Hill-2026!"
HANDOFF = "/tmp/cr068-q/fixture.json"

#: The wireframe's own two rows (`CWP-038.png`, `CWP-039.png`).
BANK_BRAND, BANK_LAST_FOUR = "Chase", "4021"
CARD_BRAND, CARD_LAST_FOUR = "Visa", "8812"

#: `US-CWP-050` §4's signed lines. `$185.00 + $150.00 = $335.00` to pay now;
#: `$25.00` waived and in NEITHER total.
FEE_LINES = (
    (1, "CONN", "New connection", Decimal("185.0000"), False),
    (2, "CC-METERT", "Meter installation", Decimal("150.0000"), False),
    (3, "CC-REQFEE", "Account set-up", Decimal("25.0000"), True),
)

#: `US-CWP-049` §4's worked refund — a card overpayment returned by cheque.
REFUND_AMOUNT = Decimal("89.8000")
REFUND_CHEQUE = "10241"
VOIDED_REFUND_AMOUNT = Decimal("12.5000")


def _tenant():
    tenant = Tenant.objects.filter(name__icontains="Pine Hill").first()
    if tenant is None:  # pragma: no cover — a run against an unseeded database
        raise SystemExit("no Pine Hill tenant — run `manage.py seed_portal_demo` first")
    return tenant


def _best_account(tenant_id):
    """The account with the MOST OPEN bills and something owing.

    ⚠ **THE TENANT IS IN EVERY QUERY.** `def-cwp-3965-fixture.py` reads
    `CustomerAccount.objects.all()` and leans on RLS to scope it — and
    `config.settings.local` runs as a superuser, for which RLS is skipped
    (the server prints `core.W001` saying so on every boot). On a database
    holding more than one tenant it therefore walks into another utility's
    accounts and dies inside `open_bill_position`. Filed as a defect; not
    repeated here.
    """
    holdings: dict[str, list] = {}
    for link in customers_models.CustomerAccount.objects.filter(tenant_id=tenant_id):
        holdings.setdefault(str(link.customer_id), []).append(link.account_id)
    best = None
    for customer_id, account_ids in holdings.items():
        for account_id in account_ids:
            position = payments_seam.account_balance(account_id)
            owing = Decimal(str(position.get("owing") or "0"))
            open_bills = [
                one for one in position.get("bills") or [] if Decimal(str(one["open_balance"])) > 0
            ]
            if owing <= 0 or not open_bills:
                continue
            # ⚠ **THE NUMBER OF OPEN BILLS OUTRANKS EVERYTHING**, including the
            # tidiness of a single-account customer. Two open bills is the only
            # state in which *oldest first, by the tenant's rule* is provable,
            # and the seeded estate holds very few: a run that preferred a neat
            # switcher over a provable rule would be choosing the empty case
            # again by a prettier route.
            rank = (len(open_bills), -len(account_ids), owing)
            if best is None or rank > best[0]:
                best = (rank, customer_id, account_id, position, open_bills)
    if best is None:
        raise SystemExit(
            "no account on this tenant has an open bill and an amount owing — a walkthrough "
            "against it would exercise CWP-038's EMPTY state and prove none of wave Q"
        )
    return best[1], best[2], best[3], best[4]


def _enrol(tenant_id, account_id, account_no):
    email = EMAIL_TEMPLATE.format(account_no=account_no.lower())
    existing = credentials.credential_by_email(tenant_id, email)
    if existing is not None:
        print(f"  {email} already enrolled — left alone")
        return email
    account = customers_models.Account.objects.filter(tenant_id=tenant_id, pk=account_id).first()
    credentials.create_credential(
        tenant_id,
        account=account,
        email=email,
        password=PASSWORD,
        otp_channel=portal_models.CHANNEL_SMS,
    )
    print(f"  {email} enrolled on {account.account_no}")
    return email


def _connect_sandbox(tenant_id):
    """The provider row without which every Pay control on this tenant is held.

    `behaviour: approve` — and demo-script step 3 flips this one field to
    `timeout` rather than reaching into `apps/payments`, because that is the
    only place in the product where *the gateway did not answer* is decided.
    """
    row, made = integration_models.IntegrationConnection.objects.get_or_create(
        tenant_id=tenant_id,
        provider_key="payments_sandbox",
        environment=integration_models.ENVIRONMENT_SANDBOX,
        defaults={
            "label": "Sandbox card and bank rails",
            "status": "connected",
            "enabled": True,
            "config": {"behaviour": "approve"},
            "connected_at": timezone.now(),
        },
    )
    print(f"  payments_sandbox {'connected' if made else 'already connected'} "
          f"(behaviour={row.config.get('behaviour')!r}, status={row.status})")
    return row


def _instruments(tenant_id, customer_id):
    made = []
    for kind, brand, last_four, status, expiry in (
        (payments_models.INSTRUMENT_BANK, BANK_BRAND, BANK_LAST_FOUR,
         payments_models.INSTRUMENT_VERIFIED, (None, None)),
        # ⚠ A CARD MAY NOT BE `verified` — `ck_instrument_verified_is_bank_only`.
        (payments_models.INSTRUMENT_CARD, CARD_BRAND, CARD_LAST_FOUR,
         payments_models.INSTRUMENT_ACTIVE, (11, 2027)),
    ):
        token = f"tok_test_cr068q_{kind}_{last_four}"
        row, created = payments_models.StoredPaymentInstrument.objects.get_or_create(
            tenant_id=tenant_id,
            gateway_token=token,
            defaults={
                "customer_id": customer_id,
                "brand": brand,
                "last_four": last_four,
                "kind": kind,
                "status": status,
                "expires_month": expiry[0],
                "expires_year": expiry[1],
                "used_for": [payments_models.INSTRUMENT_USE_ONE_OFF,
                             payments_models.INSTRUMENT_USE_AUTOPAY],
            },
        )
        made.append((row, created))
        print(f"  {brand} ••••{last_four} ({kind}, {status}) "
              f"{'saved' if created else 'already saved'}")
    return [row for row, _ in made]


def _card_payment(tenant_id, account_id):
    """One CLEARED card payment, so a refund drawn from it can say where the
    money came in — `destination_of` reads the payment's TENDER and nothing else.
    """
    card_method = tenancy_models.PaymentMethod.objects.filter(
        tenant_id=tenant_id, code="card"
    ).first()
    if card_method is None:  # pragma: no cover — the seeded tender list has it
        raise SystemExit("this tenant has no `card` tender, so no card refund can be shown")
    existing = payments_models.Payment.objects.filter(
        tenant_id=tenant_id, account_id=account_id, method_id=card_method.pk,
        confirmation=f"{CARD_BRAND} ••••{CARD_LAST_FOUR}",
    ).first()
    if existing is not None:
        print(f"  card payment {existing.amount} already present")
        return existing
    row = payments_models.Payment.objects.create(
        tenant_id=tenant_id,
        account_id=account_id,
        method_id=card_method.pk,
        amount=Decimal("250.0000"),
        currency="USD",
        status="cleared",
        # `posted_at` is when the RECORD entered the system, `cleared_at` when
        # the MONEY arrived — the pair r12 #1 splits and B2's single
        # `received_at` deliberately is not.
        posted_at=timezone.now() - timezone.timedelta(days=5),
        cleared_at=timezone.now() - timezone.timedelta(days=4),
        confirmation=f"{CARD_BRAND} ••••{CARD_LAST_FOUR}",
    )
    print(f"  card payment {row.amount} recorded (tender `card`)")
    return row


def _refunds(tenant_id, account_id, card_payment):
    now = timezone.now()
    made = 0
    if not payments_models.Refund.objects.filter(
        tenant_id=tenant_id, account_id=account_id, reference=REFUND_CHEQUE
    ).exists():
        payments_models.Refund.objects.create(
            tenant_id=tenant_id,
            account_id=account_id,
            payment_id=card_payment.pk,
            amount=REFUND_AMOUNT,
            currency="USD",
            status="issued",
            method=payments_models.REFUND_METHOD_CHECK,
            reference=REFUND_CHEQUE,
            reason="Overpayment returned",
            requested_at=now - timezone.timedelta(days=3),
            approved_at=now - timezone.timedelta(days=2),
            issued_at=now - timezone.timedelta(days=1),
            idempotency_key=f"cr068q-refund-{uuid.uuid4()}",
        )
        made += 1
    # ⚠ **A VOIDED REFUND STAYS ON THE TIMELINE** (`US-CWP-056` TC-4). A customer
    # told money was coming and then shown nothing cannot ask what happened to it.
    if not payments_models.Refund.objects.filter(
        tenant_id=tenant_id, account_id=account_id, voided_at__isnull=False
    ).exists():
        payments_models.Refund.objects.create(
            tenant_id=tenant_id,
            account_id=account_id,
            payment_id=card_payment.pk,
            amount=VOIDED_REFUND_AMOUNT,
            currency="USD",
            status="void",
            method=payments_models.REFUND_METHOD_CHECK,
            reference="10198",
            reason="Cheque lost in the post",
            requested_at=now - timezone.timedelta(days=20),
            approved_at=now - timezone.timedelta(days=19),
            issued_at=now - timezone.timedelta(days=18),
            voided_at=now - timezone.timedelta(days=9),
            void_reason="never presented",
            idempotency_key=f"cr068q-void-{uuid.uuid4()}",
        )
        made += 1
    total = payments_models.Refund.objects.filter(
        tenant_id=tenant_id, account_id=account_id
    ).count()
    print(f"  refunds: {made} written this run, {total} on the account")


def _fees(tenant_id, account_id):
    """An APPROVED portal request quoting the signed lines.

    `paying.fees_position` finds a request by **tenant · channel `portal` · a
    phone one of my own accounts holds** — three clauses, all three in the query
    (`BR-CWP-010`). So the request has to carry this account's own phone or the
    screen correctly shows nothing.
    """
    from apps.portal.seams import customers_seam

    details = customers_seam.contact_details(tenant_id, [str(account_id)])
    phone = details.get("phone")
    if not phone:
        raise SystemExit("this account holds no phone, so no portal request can be matched to it")

    request = customers_models.ServiceRequest.objects.filter(
        tenant_id=tenant_id, channel="customer_portal", applicant_phone=phone, state="approved"
    ).first()
    if request is None:
        request = customers_models.ServiceRequest.objects.filter(
            tenant_id=tenant_id, channel="customer_portal", applicant_phone=phone
        ).first()
    if request is None:
        # ⚠ **THE SEED SPELLS THIS CHANNEL `portal` AND THE PRODUCT SPELLS IT
        # `customer_portal`.** `service_request_service.CHANNEL_CUSTOMER_PORTAL`
        # is what `create_from_portal` writes and what `my_requests` filters on,
        # so a seeded `portal` row is invisible to `CWP-050` for ever. The
        # column is deliberately free text (no lookup, no choices), so nothing
        # can catch the divergence — filed as a defect, and corrected here so
        # the screen has a request to draw.
        seed = customers_models.ServiceRequest.objects.filter(
            tenant_id=tenant_id, channel__in=("customer_portal", "portal")
        ).first()
        if seed is None:
            print("  no portal-channel service request on this tenant — CWP-050 stays empty")
            return None
        request = seed
    request.channel = "customer_portal"
    request.applicant_phone = phone
    request.state = "approved"
    request.fee_timing = "collect_now"
    request.save(update_fields=["channel", "applicant_phone", "state", "fee_timing"])

    existing = {
        row.line_no: row
        for row in customers_models.ServiceRequestFee.objects.filter(
            tenant_id=tenant_id, request_id=request.id
        )
    }
    for line_no, code, description, amount, waived in FEE_LINES:
        if line_no in existing:
            row = existing[line_no]
            row.charge_code, row.description = code, description
            row.unit_amount = row.amount = amount
            row.waived, row.currency, row.quantity = waived, "USD", Decimal("1")
            row.waived_at = timezone.now() if waived else None
            row.save()
        else:
            customers_models.ServiceRequestFee.objects.create(
                tenant_id=tenant_id, request_id=request.id, line_no=line_no,
                charge_code=code, description=description, quantity=Decimal("1"),
                unit_amount=amount, amount=amount, currency="USD", waived=waived,
                waived_at=timezone.now() if waived else None,
            )
    # Any seeded line beyond the three signed ones would change the total the
    # walkthrough asserts, so it goes.
    customers_models.ServiceRequestFee.objects.filter(
        tenant_id=tenant_id, request_id=request.id, line_no__gt=len(FEE_LINES)
    ).delete()
    payable = sum(amount for _, _, _, amount, waived in FEE_LINES if not waived)
    print(f"  {request.request_no} approved, {len(FEE_LINES)} fee line(s), "
          f"${payable:.2f} payable and $25.00 waived")
    return request


tenant = _tenant()
print(f"tenant: {tenant.subdomain}")
with tenant_context(tenant.pk):
    customer_id, account_id, position, open_bills = _best_account(tenant.pk)
    account = customers_models.Account.objects.filter(tenant_id=tenant.pk, pk=account_id).first()
    print(f"\naccount {account.account_no}: ${Decimal(position['owing']):.2f} owing, "
          f"{len(open_bills)} open bill(s)")
    for bill in open_bills:
        print(f"    {bill['number']}  issued {bill['issued_on']}  "
              f"owing ${Decimal(bill['open_balance']):.2f}")
    if len(open_bills) < 2:
        print("  ⚠ ONE OPEN BILL ONLY — the oldest-first step cannot be proved on this estate")

    print("\nenrolling:")
    email = _enrol(tenant.pk, account_id, account.account_no)
    print("\nrails:")
    _connect_sandbox(tenant.pk)
    print("\nsaved methods:")
    _instruments(tenant.pk, customer_id)
    print("\nmoney back:")
    payment = _card_payment(tenant.pk, account_id)
    _refunds(tenant.pk, account_id, payment)
    print("\nfees:")
    _fees(tenant.pk, account_id)

    # ⚠ **HANDED OVER AS DATA, NOT PRINTED FOR A HUMAN TO RETYPE.** The
    # walkthrough reads this file; a run where the two disagree about which
    # account is under test is a run that proves nothing about either.
    Path(HANDOFF).parent.mkdir(parents=True, exist_ok=True)
    Path(HANDOFF).write_text(
        json.dumps(
            {
                "tenant": tenant.subdomain,
                "email": email,
                "password": PASSWORD,
                "account_id": str(account_id),
                "account_no": account.account_no,
                "open_bills": len(open_bills),
            },
            indent=2,
        )
    )
    print(f"\nsign in as {email}, password {PASSWORD}")
    print(f"handed to the walkthrough in {HANDOFF}")
