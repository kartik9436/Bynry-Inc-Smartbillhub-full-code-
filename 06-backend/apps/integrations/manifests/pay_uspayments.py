"""USPayments — US Payments (Prime): they call us, and we post what they send (Payments · LIVE).

⚠ **REWRITTEN 2026-10-07 (`CR-174-BRC10`). UNTIL THEN THIS WAS ONE OF FIVE
COMING-SOON OUTWARD CARD PROCESSORS** (`CR-110-BRC04`): four operations WE
would place — take a payment, open a card page, collect a settlement, refund —
at a placeholder address, none built. PO 2026-10-07 (D4), verbatim: *"US
payment card - use it"*. US Payments never takes a call from us, so the four
outward operations left the card (the coordinator's reading, recorded in the
D4 row rather than asked); the card is now the three calls THEY make to US.
Nothing that shipped is lost: none of the four had code behind it.

THE THREE ADDRESSES A UTILITY HANDS TO US PAYMENTS (`DEF-INT-10020`)
--------------------------------------------------------------------
    GET  https://<our host>/api/partner/v1/account-lookup?accountId=00012345
    POST https://<our host>/api/partner/v1/add-payment
    POST https://<our host>/api/partner/v1/add-return

**The same three for every utility.** No utility and no vendor in any of them
(the 2026-09-16 partner-URL rule; PO ruling 2026-10-07, *"go - for USPayments
partner API URL Fix"*): the utility is the one that issued the key in the
`password` header, looked up in `integration_key_directory` before the view
runs (`partner_urls._with_utility_from_key`). Each address is declared below as
its operation's `served_path` and `partner_urls` builds the route from it, so
the address on the card and the address that answers cannot disagree.

⚠ **UNTIL 2.561.5 THESE WERE `/api/{utility}/integrations/inbound/
pay_uspayments/{payments|account_lookup|returns}`**, which US Payments cannot
call — it sends no utility and no connector name in any URL. That address now
refuses these three operations in the ordinary way and logs where they moved;
the generic kiosk connector (`payments_kiosk`) is still served there.

⚠ **IF A UTILITY'S CALLS ARE ALL REFUSED WITH A KEY THAT LOOKS RIGHT**, the key
may have no row in `integration_key_directory` (a key issued before
`integrations/0011`, or a row deleted by hand). `manage.py check_key_directory`
lists every such connection, read-only. **The repair is to issue a new key on
this card** (Settings → Integrations → USPayments → the key) and hand it to US
Payments: `services.record_credential` writes the directory row for every key
it issues, and the old key stops working at that moment.

WHAT THEY SEND, AND WHAT WE ANSWER — THE SPECIFICATION, AS DATA
---------------------------------------------------------------
    GET  /api/partner/v1/account-lookup?accountId=00012345
                                          always 200; {"accountValid": false}
                                          for an account we cannot show
    POST /api/partner/v1/add-payment   {paymentId, accountId, paymentDateTime,
                                        channel, kioskId, method, amount}
                                          200 · 409 duplicate · 400 · 500
    POST /api/partner/v1/add-return    {…the same, + returnDateTime, returnCode}
                                          200 · 409 · 400 · 503 not yet · 500

The credential is the `password` HEADER, value exactly as issued, no `Bearer` —
the key WE issue (`issued_secret`, shown once). `username` is a label and is
never checked; `enterpriseId` and
`companyId` are optional and, when sent, must match what the utility typed in
the two fields below (`Auth.identity_headers`), or the call gets the door's one
refusal. **Every field name below is THEIR spelling, declared here so the door
holds none of them** (`Operation.wire`, G77, `BR-INT-037`).

⚠ **THE THREE OPERATIONS APPLY, AND THAT IS THE PO'S RULING, NOT A WIDENING OF
THE DOOR.** `BR-INT-058` stops the kiosk door after `dedupe`. PO 2026-10-07
(D1), verbatim: *"(a). A person standing at a machine needs the live balance.
Runbooks still handle the exceptions in D2."* So each operation here replies
after `apply` and says which apply it is; `apps/payments/agent_door.py` is the
money half and says why each step is what it is.

THE CEILINGS, AND WHY EACH ONE
------------------------------
No clerk may change them (PO 2026-09-16: *"so wecant allow clark to reset
it"*). Sixty payments a minute is 3,600 an hour — far above a busy kiosk
network at the top of the ICP (40,000 accounts) — and a stolen key gets sixty
tries a minute rather than three hundred. The lookup is double that, because a
machine asks before every payment and again when a customer mistypes.

THE TENDER WORDS AND THEIR SUGGESTIONS
--------------------------------------
The specification's words, verbatim, each a row on the mapping screen for the
utility to point at ONE of its own payment methods. The suggestion is applied
once, when the connector is switched on, only for words still unmapped and
only where the utility has an active method with that code — *"Methods come
from the tenant's own payment_methods; nothing is created."* `OTHER` is the
FALLBACK: a word nobody listed lands there and adds a red row, and the
connector cannot be switched on until `OTHER` is mapped.

Data, not code (BR-INT-037). Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.pay_uspayments.*` wins on screen, so a
translation is a catalogue line and never an edit to this file.
"""

from apps.integrations.registry import (
    APPLY_ACCOUNT_LOOKUP,
    APPLY_RECORD_PAYMENT,
    APPLY_REVERSE_PAYMENT,
    Auth,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    Operation,
    Vocabulary,
)

#: The specification's method words, verbatim.
USPAYMENTS_TENDER_WORDS = (
    "CASH",
    "CHECK",
    "ACHCHECK",
    "ACHSAVINGS",
    "CREDIT",
    "DEBIT",
    "GOOGLEPAY",
    "APPLEPAY",
    "PAYPAL",
    "VENMO",
    "CASHAPP",
    "ZELLE",
    "CRYPTO",
    "OTHER",
)

#: Their word → the code BR-PAY-026 seeds for the matching method of ours.
#: Wallets pay by card. PAYPAL, VENMO, CASHAPP, ZELLE and CRYPTO are absent on
#: purpose: they are the utility's *Other*, which it maps itself.
USPAYMENTS_SUGGESTED = {
    "CASH": "cash",
    "CHECK": "check",
    "ACHCHECK": "ach",
    "ACHSAVINGS": "ach",
    "CREDIT": "card",
    "DEBIT": "card",
    "GOOGLEPAY": "card",
    "APPLEPAY": "card",
}

#: Their field names for the message bodies, verbatim from the specification.
_MESSAGE_WIRE = {
    "account": "accountId",
    "amount": "amount",
    "method": "method",
    "channel": "channel",
    "terminal": "kioskId",
}

MANIFEST = Manifest(
    key="pay_uspayments",
    category="payments",
    display_name="USPayments",
    summary="Take payments at their kiosks, phone lines and web pages.",
    disposition=Disposition(kind="live", phase=5),
    auth=Auth(
        mode="they_hold_ours",
        placement="header",
        header="password",
        identity_headers={"enterpriseId": "enterprise_id", "companyId": "company_id"},
    ),
    network_allowlist=True,
    vocabularies=(
        Vocabulary(
            entity_type="tender",
            label="How they pay",
            summary="Which of your payment methods each of their words means.",
            values=USPAYMENTS_TENDER_WORDS,
            fallback="OTHER",
            suggested=USPAYMENTS_SUGGESTED,
        ),
    ),
    fields=(
        Field(name="issued_key", label="The key for them to use", kind="issued_secret"),
        Field(name="allowed_addresses", label="Allowed addresses", kind="text", required=False),
        Field(name="enterprise_id", label="Their enterprise ID", kind="text", required=False),
        Field(name="company_id", label="Their company ID", kind="text", required=False),
    ),
    operations=(
        Operation(
            name="payments",
            label="Payments",
            description="They send us each payment a customer made.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            idempotency=Idempotency(
                mode="refuse", source="provider_event_id", key_field="paymentId"
            ),
            completion="immediate",
            codec="json",
            respond_after="apply",
            applies=APPLY_RECORD_PAYMENT,
            envelope_status={
                "ok": 200,
                "duplicate": 409,
                "refused": 401,
                "invalid": 400,
                "failed": 500,
            },
            wire={**_MESSAGE_WIRE, "occurred_at": "paymentDateTime"},
            rate_limit_per_minute=60,
            served_path="/partner/v1/add-payment",
        ),
        Operation(
            name="account_lookup",
            label="Account lookup",
            description="They ask what is owed before taking money.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            respond_after="apply",
            applies=APPLY_ACCOUNT_LOOKUP,
            http_method="GET",
            # ⚠ ALWAYS 200, NEVER 404 OR 204 — the specification's own words,
            # and `DEF-INT-4257`'s lesson on the kiosk: a machine reads a 404 as
            # *the endpoint is gone*. An account we cannot show is
            # `{"accountValid": false}` with a 200.
            envelope_status={"ok": 200, "refused": 401},
            wire={
                "account": "accountId",
                "found": "accountValid",
                "balance": "amountDue",
                "past_due": "pastDue",
                "allow_payments": "allowPayments",
                "allow_check": "allowCheck",
                "allow_credit": "allowCredit",
                "allow_debit": "allowDebit",
                "display_credit": "displayCredit",
                "residential": "isResidential",
            },
            rate_limit_per_minute=120,
            served_path="/partner/v1/account-lookup",
        ),
        Operation(
            name="returns",
            label="Returns",
            description="They tell us when a payment comes back.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            idempotency=Idempotency(
                mode="refuse",
                source="provider_event_id",
                natural_key="event_id+reversal",
                key_field="paymentId",
            ),
            completion="immediate",
            codec="json",
            respond_after="apply",
            applies=APPLY_REVERSE_PAYMENT,
            # `not_yet` is 503 — chosen and recorded (decision log 2026-10-07,
            # J5): a return that overtook its payment is not OUR fault (500)
            # and not THEIR mistake (400); it is *come back shortly*, which is
            # what 503 means, and any non-200 makes them resend the same body.
            envelope_status={
                "ok": 200,
                "duplicate": 409,
                "refused": 401,
                "invalid": 400,
                "failed": 500,
                "not_yet": 503,
            },
            wire={
                **_MESSAGE_WIRE,
                "occurred_at": "returnDateTime",
                "return_code": "returnCode",
            },
            rate_limit_per_minute=60,
            served_path="/partner/v1/add-return",
        ),
    ),
)
