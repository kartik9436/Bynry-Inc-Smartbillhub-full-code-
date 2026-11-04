# ── Trace ──────────────────────────────────────────────
# Change:  CR-068 waves P and R — *Rails and the webhook* (task P5) and
#          *Quick pay for a guest* (task R4)
#          (04-docs/05-modules/15-portal/10-execution-plan.md)
# Stories: US-CWP-006 · US-CWP-022 · US-CWP-046 (P) ·
#          US-CWP-003 · US-CWP-004 · US-CWP-005 (R)
# Rules:   CLAUDE.md hard rule 1 (the tenant is IN THE QUERY, never left to RLS,
#          which config.settings.local bypasses as a superuser) · hard rule 2
#          (money written to 4 dp) · hard rule 4 (financial immutability — this
#          file creates rows and updates none)
# Tests:   fixture prep for
#          10-scripts/render-checks/cr068-p-rails-and-webhook.mjs and
#          10-scripts/render-checks/cr068-r-quick-pay.mjs
# ───────────────────────────────────────────────────────
"""THE STATE WAVES P AND R'S SCREENS ARE NORMALLY IN — never the state they default to.

WHY THIS FILE EXISTS
--------------------
`DEF-WRK-4121` shipped a dispatcher that could not raise a work order on any
non-empty list, because every test used the empty one — the single state where
it happened to work. `seed_portal_demo` walks both of this lane's waves into
exactly that trap:

    stored instruments      0  -> CWP-039 draws its EMPTY state, so a run
                                  "passes" having never seen the masked method
                                  string that is the whole point of US-CWP-046
    integration_connection  0  -> every Pay control on the tenant is held on
                                  `no_provider`, so quick pay's commit is never
                                  pressed and no payment row is ever written
    portal credential       0  -> CWP-039 is behind a login, so without one the
                                  wave P screen half cannot be opened at all

**A walkthrough run against that database is green and proves almost nothing.**
So this file puts the tenant into the shape the two demo scripts describe, and
each walkthrough asserts the state is really there before asserting anything
about it.

WHAT IT MAKES, AND WHY EACH PIECE
---------------------------------
  1. **A `payments_sandbox` connection**, `behaviour: approve`. Without it
     `gateway.provider_for` finds nothing, and wave R's *Pay* is held on
     `no_provider` before the customer types a digit.
  2. **A login** on an account that has an open bill, so `CWP-039` can be
     opened as the customer who owns the saved cards.
  3. **The wireframe's own two instruments** — `Chase ••••4021` (bank,
     verified) and `Visa ••••8812` (card, active, expires 11/27), which are
     literally the two rows drawn in `wireframes/CWP-039.png`.
     ⚠ `verified` is bank-only by database CHECK (`ck_instrument_verified_is_
     bank_only`), so the card is `active`. That is the product's rule, not a
     shortcut taken here.
  4. **Nothing at all for wave R's bills.** The seeded estate already holds a
     payable, a settled and a replaced bill against a premises with a postcode,
     and this file FINDS them rather than making them — a fixture that minted
     its own bills would be proving its own arithmetic. It prints the three it
     found and hands them over. ⚠ **It does NOT make a cancelled one**: voiding
     an issued invoice is an UPDATE on an issued invoice, which hard rule 4
     forbids outright, and a fixture is not the place to invent a lawful void
     path. The walkthrough records that fourth state as a known gap instead.

IDEMPOTENT. Run it twice; the second run finds what it made and writes nothing.

RUN IT
------
    eval "$(10-scripts/proof-db.sh clone cwppr --export)"
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    (cd 06-backend && python3 manage.py seed_portal_demo)
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-pr-fixture.py)
"""

import json
from decimal import Decimal
from pathlib import Path

from django.utils import timezone

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.integrations import models as integration_models
from apps.payments import models as payments_models
from apps.portal import credentials
from apps.portal import models as portal_models
from apps.portal import selectors
from apps.portal.seams import customers_seam, payments_seam
from apps.tenancy.models import Tenant
from core.tenancy import tenant_context

EMAIL_TEMPLATE = "pr-payer+{account_no}@example.test"
PASSWORD = "Pine-Hill-2026!"
HANDOFF = "/tmp/cr068-pr/fixture.json"

#: The wireframe's own two rows (`wireframes/CWP-039.png`).
BANK_BRAND, BANK_LAST_FOUR = "Chase", "4021"
CARD_BRAND, CARD_LAST_FOUR = "Visa", "8812"


def _tenant():
    tenant = Tenant.objects.filter(subdomain="pine-hill").first()
    if tenant is None:  # pragma: no cover — a run against an unseeded database
        raise SystemExit("no pine-hill tenant — run `manage.py seed_portal_demo` first")
    return tenant


def _connect_sandbox(tenant_id):
    """The provider row without which every Pay control on this tenant is held."""
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
    print(
        f"  payments_sandbox {'connected' if made else 'already connected'} "
        f"(behaviour={row.config.get('behaviour')!r}, status={row.status})"
    )
    return row


def _account_for_wave_p(tenant_id):
    """The customer wave P signs in as — chosen DETERMINISTICALLY, not by balance.

    ⚠ **THIS PICKED *the first account that owes something* UNTIL THE SECOND RUN
    CAUGHT IT, AND THE FAULT IS WORTH KEEPING WRITTEN DOWN.** Wave R PAYS, so
    the set of accounts owing money changes on every run — which meant wave P's
    login moved to a different customer each time while `_instruments` below
    kept its tokens on a FIXED string and so went on finding the rows it had
    made for the FIRST customer. The second run therefore signed in as somebody
    with **no saved cards at all**, and `CWP-039` would have drawn its empty
    state: `DEF-WRK-4121`'s exact shape, manufactured by the very fixture
    written to avoid it.

    It was caught only because the walkthrough asserts the state before using
    it and STOPPED. That guard is the whole reason this is a paragraph rather
    than a green run proving nothing.

    So the account is now chosen by a rule that does not move — the lowest
    `account_no` — and it needs no balance: `CWP-039` lists saved cards and has
    nothing to do with what is owed.

    ⚠ **THE TENANT IS IN EVERY QUERY.** `config.settings.local` runs as a
    superuser, for which every RLS policy is skipped — the server says so on
    every boot (`core.W001`) — so a queryset that leaned on row-level security
    to scope itself would walk into another utility's rows on any database
    holding more than one tenant, and this one holds three.
    """
    links = customers_models.CustomerAccount.objects.filter(tenant_id=tenant_id)
    best = None
    for link in links:
        account = customers_models.Account.objects.filter(
            tenant_id=tenant_id, pk=link.account_id
        ).first()
        if account is None:
            continue
        if best is None or account.account_no < best[1].account_no:
            best = (str(link.customer_id), account)
    if best is None:
        raise SystemExit("this tenant has no customer holding an account")
    position = payments_seam.account_balance(best[1].pk)
    return best[0], best[1], Decimal(str(position.get("owing") or "0"))


def _enrol(tenant_id, account):
    email = EMAIL_TEMPLATE.format(account_no=account.account_no.lower())
    if credentials.credential_by_email(tenant_id, email) is not None:
        print(f"  {email} already enrolled — left alone")
        return email
    credentials.create_credential(
        tenant_id,
        account=account,
        email=email,
        password=PASSWORD,
        otp_channel=portal_models.CHANNEL_SMS,
    )
    print(f"  {email} enrolled on {account.account_no}")
    return email


def _instruments(tenant_id, customer_id):
    """The two rows the wireframe draws, and no others."""
    for kind, brand, last_four, status, expiry in (
        (
            payments_models.INSTRUMENT_BANK,
            BANK_BRAND,
            BANK_LAST_FOUR,
            payments_models.INSTRUMENT_VERIFIED,
            (None, None),
        ),
        # ⚠ A CARD MAY NOT BE `verified` — `ck_instrument_verified_is_bank_only`.
        (
            payments_models.INSTRUMENT_CARD,
            CARD_BRAND,
            CARD_LAST_FOUR,
            payments_models.INSTRUMENT_ACTIVE,
            (11, 2027),
        ),
    ):
        #: ⚠ **KEYED ON THE CUSTOMER.** A token fixed across customers made the
        #: second run find the FIRST customer's rows and create none for the new
        #: one — see `_account_for_wave_p`. Belt as well as braces.
        token = f"tok_test_cr068pr_{customer_id}_{kind}_{last_four}"
        #: ⚠ **IDEMPOTENT ON WHAT A PERSON SEES, NOT ON THE TOKEN.** Keyed on
        #: `gateway_token` this drew FOUR rows on `CWP-039` — `Chase ••••4021`
        #: twice and `Visa ••••8812` twice — the moment the token string changed
        #: shape, because a new token is a new row to `get_or_create` and the
        #: old one is still there. A fixture whose second run doubles the table
        #: is a fixture that makes its own screenshot a lie.
        _, created = payments_models.StoredPaymentInstrument.objects.get_or_create(
            tenant_id=tenant_id,
            customer_id=customer_id,
            kind=kind,
            last_four=last_four,
            defaults={
                "gateway_token": token,
                "brand": brand,
                "status": status,
                "expires_month": expiry[0],
                "expires_year": expiry[1],
                "used_for": [
                    payments_models.INSTRUMENT_USE_ONE_OFF,
                    payments_models.INSTRUMENT_USE_AUTOPAY,
                ],
            },
        )
        print(
            f"  {brand} ••••{last_four} ({kind}, {status}) "
            f"{'saved' if created else 'already saved'}"
        )


def _bills_for_the_guest(tenant_id):
    """One bill per state the guest lookup can answer with — FOUND, not made.

    Walks the tenant's invoices, asks the very selector the endpoint asks, and
    keeps the first hit for each state. Anything this cannot find is reported by
    name so the walkthrough can record it as a gap rather than assert over it.
    """
    wanted = ("payable", "settled", "replaced", "cancelled")
    found: dict[str, dict] = {}
    for invoice in billing_models.Invoice.objects.filter(tenant_id=tenant_id).order_by(
        "invoice_no"
    ):
        if len(found) == len(wanted):
            break
        premises_id = customers_seam.account_premises_id(tenant_id, invoice.account_id)
        postcode = customers_seam.premises_postcode(premises_id)
        if not postcode:
            continue
        answer = selectors.bill_lookup(
            tenant_id, bill_number=invoice.invoice_no, postcode=postcode
        )
        if answer is None or answer["status"] in found:
            continue
        found[answer["status"]] = {
            "number": answer["number"],
            "postcode": postcode,
            "display": answer["amount"]["display"],
            "stored": answer["amount"]["amount"],
            "masked_name": answer["masked_name"],
            "replaced_by": answer["replaced_by"],
            "due_on": answer["due_on"],
        }
        one = found[answer["status"]]
        print(
            f"  {answer['status']:<10} {one['number']}  postcode {one['postcode']}  "
            f"{one['display']} (stored {one['stored']})  billed to {one['masked_name']}"
        )
    for missing in wanted:
        if missing not in found:
            print(f"  {missing:<10} — NOT PRESENT in the seeded estate; the walkthrough")
            print(f"  {'':<10}   records it as a known gap rather than minting one")
    return found


tenant = _tenant()
print(f"CR-068 waves P + R fixture — tenant {tenant.name} ({tenant.subdomain})")

#: ⚠ **EVERY READ AND WRITE INSIDE ONE TENANT'S CONTEXT** (hard rule 1). The
#: seams below call `payments`' own services, which resolve the tenant from the
#: context and refuse `AUTH-003` without one — the refusal working, not a fault.
with tenant_context(tenant.pk):
    print("\nthe provider, without which every Pay control is held:")
    _connect_sandbox(tenant.pk)

    print("\nthe customer wave P signs in as:")
    customer_id, account, owing = _account_for_wave_p(tenant.pk)
    print(f"  {account.account_no} owes {owing}")
    email = _enrol(tenant.pk, account)

    print("\nthe two saved methods CWP-039 draws:")
    _instruments(tenant.pk, customer_id)

    print("\nthe bills wave R's guest looks up:")
    bills = _bills_for_the_guest(tenant.pk)

handoff = {
    "tenant": tenant.subdomain,
    "email": email,
    "password": PASSWORD,
    "account_no": account.account_no,
    "account_id": str(account.pk),
    "bills": bills,
    "instruments": {
        "bank": f"{BANK_BRAND} ••••{BANK_LAST_FOUR}",
        "card": f"{CARD_BRAND} ••••{CARD_LAST_FOUR}",
    },
}
Path(HANDOFF).parent.mkdir(parents=True, exist_ok=True)
Path(HANDOFF).write_text(json.dumps(handoff, indent=2), encoding="utf-8")
print(f"\nhanded to the walkthroughs at {HANDOFF}")
