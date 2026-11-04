"""WorldPay — take card and bank payments (Payments · COMING SOON W7).

One of the **five named card processors** that replace the generic
`payments_card` card (`CR-110-BRC04`, blueprint p162: *"Replaced by five named
processors"*). CFG-13 and VIEW-13 are drawn identically to the other four —
measured image by image, not inferred — so the five are one build and five
files, which is `BR-INT-037` working as intended: a sixth processor next year
is one more file here and no table, no column and no migration.

WHAT THIS CONNECTOR OWNS, AND WHAT IT DELIBERATELY DOES NOT
-----------------------------------------------------------
PO ruling 2026-09-16, verbatim: *"connector is a conector and it control access
and limits"*. So this file carries **the address, the key, the shape of the
payload, who may call and how often**. It carries no decision.

⚠ **THE TWO OUTWARD MONEY OPERATIONS DECLARE NO DUPLICATE GUARD, AND THAT IS A
RULING RATHER THAN AN OMISSION.** `deliver_charge` and `deliver_refund` were
going to ship `Idempotency(mode="refuse", source="request_key")` — a key we
mint and store BEFORE the request leaves, because the dangerous case is not a
clerk double-clicking but a reply that never arrives and a retry that follows.
The PO moved that guard to Runbooks: *"again we will build a runbok with logic
to ensure there no twice."* The answer — never charge twice, never refund
twice — is unchanged; its home moved. **This absence is written down because
nothing in this repository can see an absence** (`DEF-CUS-3653`'s lesson), and
because the consequence has to be stated rather than discovered: **until that
Runbook exists, a real refund cannot ship.** No lane may wire a live outbound
money call in phase 1 on the grounds that the guard is somebody else's.

⚠ **NO `Card page` FIELD.** The drawing offers *hosted by them* · *embedded* on
all five forms. PO ruling 2026-09-16: *"A · their page only — toggle comes off 4
forms, costs nothing."* Embedded would put this whole product inside the card
industry's annual audit on one screen's authority, and that cost is not
reversible. There is no select with two options and no hidden default: **the
field does not exist**, so a tenant cannot reach the embedded journey at all.
`deliver_card_page` is `browser_credentialed` for the same reason — the page is
theirs, the credential on it is theirs, and ours never travels (`BR-INT-048`).

⚠ **NO `Token address`, NO `Scope`, NO EXPIRY.** The drawing puts a *Token*
panel on this form. PO ruling 2026-09-16: *"i only want to issue a key per
conenction … i dont understand the differnt between key and token."* One key per
connection, and the word *token* is off every screen. The merchant secret is
that one key.

⚠ **NO MAPPING AND NO VOCABULARY.** PO: *"we dont need mapping at connector
level it will be in runbook with business logic."* What a processor's own words
MEAN at a utility is judgment about that utility's books.

⚠ **NO TIME OF DAY.** The drawing puts a clock in a *When it runs* panel. PO:
*"conenctor i a conenctor not a logic to to ETL"* — scheduling is Runbooks'.
`fetch_settlement` says it runs on a clock; it does not say which hour.

THE FOUR CEILINGS, AND WHY EACH ONE
------------------------------------
Every figure drawn in the blueprint is an illustration (B14 rule 37, and p017
says so of itself: *"No value here was read from anything"*). These are ours,
chosen deliberately because **no clerk may correct them from a screen** — the
limit is a guard, not a setting (PO: *"so wecant allow clark to reset it"*).

* `deliver_charge` · `deliver_refund` — **60 a minute.** A utility of at most
  40,000 accounts (T5, the top of the ICP) never charges sixty cards in a
  second; the ceiling exists to stop a runaway retry inside one minute rather
  than to pace normal work.
* `deliver_card_page` — **600 a minute.** One call per customer starting a
  payment, and it happens while a person waits. Ten a second is a busy
  afternoon at the top of the ICP and still refuses a scripted flood.
* `fetch_settlement` — **10 a minute.** It runs once per settlement. Anything
  above that is a retry storm, which is exactly what should be refused.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.pay_worldpay.*` wins on screen when present, so a
translation is a catalogue line and never an edit to this file.
"""

from apps.integrations.registry import (
    Auth,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    Operation,
)

MANIFEST = Manifest(
    key="pay_worldpay",
    category="payments",
    display_name="WorldPay",
    summary="Take card and bank payments through WorldPay.",
    #: `BR-INT-001` — no tenant-side payment processor in v1; the payment rails
    #: are W7. The card reads *Coming soon · W7* and the server refuses a
    #: connect, which is what keeps it honest while phase 2 is written.
    disposition=Disposition(kind="coming_soon", wave="W7", phase=5),
    auth=Auth(mode="we_hold_theirs", placement="header"),
    fields=(
        #: The PO's phase-1 dummy API: a placeholder address seeded as data, so
        #: every operation below has a host that resolves the day this file is
        #: written rather than the day a contract is signed (`DEF-INT-5488`).
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            default="https://api.worldpay.example",
        ),
        Field(name="merchant_id", label="Merchant ID", kind="text"),
        Field(name="merchant_secret", label="Merchant secret", kind="secret"),
        Field(name="client_id", label="Client ID", kind="text"),
    ),
    operations=(
        Operation(
            name="deliver_charge",
            label="Take a payment",
            description="We ask them to charge a card and record the answer.",
            direction="out",
            initiative="us",
            transport="https",
            trigger="manual",
            # ⚠ NOT a duplicate guard. `none` is this repository's word for
            # *this door deduplicates nothing*, and the reason is in the
            # docstring above: the PO put never-twice in a Runbook.
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            rate_limit_per_minute=60,
            test_action=None,
        ),
        Operation(
            name="deliver_card_page",
            label="Open card page",
            description="The customer types the card number on a page they host.",
            direction="out",
            initiative="us",
            transport="browser",
            trigger="inline",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            # Their page, their credential, so no secret of ours travels and
            # the validator's browser rule is satisfied by the third word
            # rather than by an exception (`BR-INT-048`).
            executor="browser_credentialed",
            rate_limit_per_minute=600,
        ),
        Operation(
            name="fetch_settlement",
            label="Collect settlement",
            description="We collect what they settled, once a settlement is cut.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            rate_limit_per_minute=10,
        ),
        Operation(
            name="deliver_refund",
            label="Refund a payment",
            description="We ask them to return money to a card we charged.",
            direction="out",
            initiative="us",
            transport="https",
            trigger="manual",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            rate_limit_per_minute=60,
            test_action=None,
        ),
    ),
)
