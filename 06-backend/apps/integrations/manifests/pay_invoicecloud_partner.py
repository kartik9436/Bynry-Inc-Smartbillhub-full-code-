"""InvoiceCloud, the half that READS FROM US — and, since 2026-09-24, takes a payment (Payments · LIVE).

The TWENTY-NINTH connector, and the second row a utility sees under the name
*InvoiceCloud*. **That is a Product Owner ruling and not an accident** — PO
2026-09-17, verbatim, choosing between three options:

    "a) Two connectors — one for the reading half, live now; the card one
    stays where it is	the customer gets their key today. Two rows in the list
    with the same company name - this is correct - we ahve to issue our key
    and also save secrete given by them in bi directional Connectors"

⚠ **THIS IS AN ACCOMMODATION OF A PRODUCT LIMITATION AND NOT THE TARGET
SHAPE.** Read the second half of that ruling again: *"we ahve to issue our key
and also save secrete given by them in bi directional Connectors"*. The PO is
describing ONE connector that holds BOTH credentials — a key we issue them and
a secret they gave us — and today one connector cannot, because
`Manifest.auth` carries a single `mode` and `machine_auth._partner_manifest`
issues a key only where it reads `they_hold_ours` (`DEF-INT-5574`). **Two rows
is what unblocks a real customer today; one bidirectional connector is what is
owed.** The standing requirement is `BR-INT-077` and the reasoning is in the
decision log of 2026-09-17. **A future lane reading two rows as the design
would be reading a workaround as an intention.**

⚠ **`pay_invoicecloud` IS UNTOUCHED AND MUST STAY SO.** It keeps its four card
operations, its `we_hold_theirs` mode and its `coming_soon · W7` disposition.
Changing a connector's meaning under its own name is how a utility ends up
connected to something other than what they thought, and `BR-INT-001` /
`BR-INT-011` (no tenant-side card processor in v1) are not being reversed here
— `tests/test_us_int_017_gating.py` still refuses connect, test, patch,
credential and delete on that key with `409`, and this file does not go near
it.

THE RELATIONSHIP: THEY DIAL US
-------------------------------
`auth.mode = "they_hold_ours"` — a key WE issue, scoped to one tenant, shown
once and never again (`BR-INT-053`). Every operation is `initiative = "them"`,
so there is nothing for us to dial, no adapter exists and none is missing
(`Manifest.we_never_dial`). This is **Aclarian's exact shape** because it is
Aclarian's exact relationship: a partner reads our data with a key we issue.
The five reads are `direction = "out"` — the data moves OUT to them — and each
`served_path` is an address of OURS, the same for every partner, so this
manifest declares no host field and the registry's host check skips it by name.

⚠ **NO MERCHANT SECRET HERE.** InvoiceCloud's merchant credentials belong to
the card connector, which is the connector that presents them. A second copy
on this row would be one secret in two places with no rule about which wins —
and it would be a `secret` field on a `they_hold_ours` manifest, which is
precisely the mixed shape `DEF-INT-5574` says the model cannot express.

WHY THE KEY IS `pay_invoicecloud_partner`
------------------------------------------
`pay_invoicecloud` is taken, so this half needs a key of its own; the key is
also the catalogue stem (`integrations.provider.pay_invoicecloud_partner.*`)
and the row id on every screen, so it is chosen once and never changed.

**`partner` is this repository's own word for this quadrant** — the addresses
are `/partner/v1/…`, the guard is `machine_auth._partner_manifest`, the
refusal is `REFUSAL_NOT_A_PARTNER_CONNECTION`, and the runner's docstring says
*"a partner holding OUR key"*. Naming the row after the thing the code already
calls it means a reader meets one word rather than two.

**`erp_invoicecloud` was considered and refused.** It fits mechanically —
`erp_*` is exactly this shape — and it is a lie: InvoiceCloud is a billing
presentment and payment portal, not a finance system, and a clerk filtering the
grid on *ERP* to find their books would meet their card processor there.

WHY THE CATEGORY IS `payments` AND NOT A NEW ONE
-------------------------------------------------
This is ours to decide and not the PO's (hard-won law 13), so the reasoning is
written down rather than asked.

* **A new category costs a chip on the grid's filter row**, in eleven
  languages, for one connector — and the chips are generated from whatever
  categories exist (`Registry.categories()`), so it appears the moment this
  file does.
* **It would SPLIT the two InvoiceCloud rows across two filters.** The PO
  accepted two rows so the customer gets their key today; two rows under two
  different chips is worse than the problem it solves, because a clerk
  filtering *Payments* to find InvoiceCloud would see one of them and conclude
  the other does not exist.
* **`payments` is not a stretch and the precedent is already shipped.**
  `payments_kiosk` is `category="payments"`, `disposition=live` and
  `auth.mode="they_hold_ours"` — the same three facts as this file — so a
  live, partner-keyed connector under *Payments* is a shape this product
  already has rather than one this lane is inventing. And the data these five
  operations serve IS bills and payments: it is read so that InvoiceCloud can
  present a bill and take money for it.
* **Nothing in the code branches on `category`.** The gating that keeps card
  processors off in v1 reads `disposition.kind`, never the category, which was
  checked rather than assumed — so putting a live connector in `payments` does
  not switch anything on and does not switch anything off.

WHY THE DISPLAY NAME SAYS WHAT IT SAYS
---------------------------------------
Two rows with one company name have to be told apart **at a glance**, before a
clerk opens either. The card half reads *InvoiceCloud* / *Take card and bank
payments through InvoiceCloud.*; this half reads *InvoiceCloud (reads from
us)* / *InvoiceCloud collects your bills and payments from here.* The
parenthetical is the repo's own idiom for exactly this job (*Test payments
(sandbox)*), and the three words are deliberately the same three the grid's
own state word uses once a connection is working — **Reading from us** — so a
clerk meets one phrase in both places instead of two.

WHY `serve_document` IS HERE, AND WHAT IT CLOSES
-------------------------------------------------
`GET /api/{utility}/partner/v1/bill-download/` has been registered, routed and
covered by tests since `CR-111-BRC04` and **unreachable by every key that
exists**, because a key's scope is drawn from its own manifest's operations
and none of the twenty-eight declared `serve_document` (`DEF-INT-5586`). This
manifest declares it, so the address has a door. The hold-expiry case in
`06-backend/tests/test_cr111_invoice_cloud.py` is turned round rather than
deleted: it used to assert that NO manifest declared the operation and to name
the first one that did, and it now asserts that this one does — and, in the same
case, that every operation `partner_api.SERVED_ROUTES` names is declared by a
manifest we SHIP, which is the durable form `DEF-INT-5586`'s prevention asked
for.

⚠ **THE PATH IS DECLARED WITH ITS TRAILING SLASH, DELIBERATELY.**
`partner_urls.PARTNER_ROUTES` registers every address in both spellings
because *"Invoice Cloud's document writes `/bill-download/` with a slash"* —
and this is Invoice Cloud's connector, so the address drawn on its API row is
the one their client will actually send. The other four carry no slash for
the same reason: that is how they will be called.

⚠ **THE `pdf` CODEC NAMES THE SUCCESS SHAPE ONLY.** On success the response is
`application/pdf` bytes; every refusal is the same JSON sentence every other
partner address answers with (`BR-INT-044`). Nothing in the serve path reads
`codec` — it is checked against the registered codec names and drawn on the
screen — so this is a description a clerk can rely on, not a switch.

WHY THERE IS NO `fetch_payment`, SAID PLAINLY
----------------------------------------------
InvoiceCloud takes money on their portal, so the obvious fifth operation is a
scheduled pull that writes those payments into our books. **It is not
declared**, and leaving it out is the point: a declared operation that cannot
run is a tick on a clerk's set-up screen for a thing that will never happen.

Two things block it and only one of them is ours. `OQ-INT-12396` is OPEN —
nothing may write a payment from a scheduled pull until we know what their API
gives us to recognise a payment already taken, because without that the second
run of a nightly job records every payment twice (hard rule 4: a payment row
may not be UPDATEd or DELETEd, so a duplicate is permanent). And we do not
have their API specification, so even the shape of the answer is a guess.
**When both are settled this manifest grows one operation and nothing else
changes** — that is `BR-INT-037`.

THE CEILINGS, AND WHY EACH ONE
-------------------------------
Every figure drawn in the blueprint is an illustration (B14 rule 37, and p017
says so of itself). None was copied. ⚠ The limit is a GUARD and not a setting —
no clerk may raise it from a screen (PO 2026-09-16: *"so wecant allow clark to
reset it"*) — so a wrong number here is a support call rather than a
five-second fix.

* `serve_customer` · `serve_bill` · `serve_payment` — **60 a minute**, the
  same arithmetic Aclarian's file works out and for the same reason: a
  month-end walk of the largest tenant this product models (40,000 accounts,
  the top of T5) pages at 1,000 rows a page, so 40 calls, which finishes
  inside forty seconds at one call a second. A stolen key gets sixty tries a
  minute.
* `serve_document` — **600 a minute**, and it is the one figure here that is
  NOT Aclarian's. A document has no paging: it is **one call per bill**, so
  the month's set at the top of the ICP is 40,000 calls, not 40. At sixty a
  minute that is eleven hours and does not fit in a night; at six hundred it
  is sixty-seven minutes and does. The other half of the case is a person
  waiting — a customer pressing *View my bill* in InvoiceCloud's portal is one
  call while they watch — which is the same reasoning `deliver_card_page`
  records for its own 600.

⚠ **THE AGGREGATE IS STATED RATHER THAN LEFT TO BE NOTICED**, because a
per-operation ceiling reads like a total and is not one. The window is per
connection AND per operation (blueprint p017), so a stolen key on this
connector gets **60 + 60 + 60 + 600 = 780 calls a minute**, of which 600 are
document fetches. Every one of them is still scoped by
`serve.resolve_caller` to the tenant the key was issued for and to a bill that
tenant owns, so the ceiling bounds volume and the key bounds reach; they are
two different guards and neither substitutes for the other.

Data, not code (`BR-INT-037`). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.pay_invoicecloud_partner.*` wins on screen
when present, so a translation is a catalogue line and never an edit to this
file.
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
    key="pay_invoicecloud_partner",
    category="payments",
    display_name="InvoiceCloud (reads from us)",
    summary="InvoiceCloud collects your bills and payments from here.",
    #: LIVE, and that is the whole point of the ruling this file carries: the
    #: partner surface is built, the addresses serve today, and until this row
    #: existed no connector could issue InvoiceCloud a key to reach any of it.
    disposition=Disposition(kind="live", phase=None),
    auth=Auth(mode="they_hold_ours", placement="bearer"),
    network_allowlist=True,
    fields=(
        # ⚠ **OPTIONAL, BY PO RULING OF 2026-09-17** — verbatim: *"In fact we
        # dont want allowed_addresses - restriction - can we make it options"*.
        # `required=True` is `Field`'s own default, and a required address list
        # meant a clerk could not save the form without typing one — and
        # whatever they typed became an EXHAUSTIVE list that locked every other
        # address out. `runners/serve.allowlist_permits` has always read an
        # empty or absent list as *permit everything*, so this is a FORM
        # restriction and not an enforcement change.
        #
        # ⚠ **WHAT IT COSTS, SAID PLAINLY:** with no address listed the KEY IS
        # THE WHOLE DOOR, and anyone holding it may call from anywhere. That is
        # how most SaaS APIs work and it is the PO's call to make; it is
        # written here rather than left in a chat message.
        Field(name="allowed_addresses", label="Allowed addresses", kind="text", required=False),
        # The one credential this connector holds: the key WE issue THEM.
        # `machine_auth.issued_key_field` finds it by KIND, never by a list of
        # connectors kept somewhere else, so this row is what makes *Generate a
        # key* appear on the set-up screen.
        Field(name="issued_key", label="The key for them to use", kind="issued_secret"),
    ),
    operations=(
        # The order is the order a partner uses them in: find the account, look
        # one up, find their bills, find what they have paid, fetch the
        # document.
        #
        # ── `DEF-INT-5623` — AN ACCOUNT IS CALLED AN ACCOUNT ────────────────
        # PO 2026-09-17, looking at this connector on the live deployment:
        # *"it should be account and not customer - theya re lookung for
        # details for accounts not customer id"*. The DATA was already right —
        # PO 2026-09-16, *"Customers = accounts"*, and `seams/customers.py`
        # serves accounts — so what moved is the VOCABULARY: this label, the
        # address below, and the field names in `shapes.INVOICE_CLOUD`.
        #
        # ⚠ **THE LABEL HERE IS THE ENGLISH FALLBACK AND THE CATALOGUE WINS ON
        # SCREEN.** Changing this line alone changes NOTHING a clerk sees:
        # `integrations.provider.pay_invoicecloud_partner.operation.serve_customer`
        # is resolved in all eleven catalogues and it is what S142 draws. Both
        # moved in this commit; a lane that moves only one has fixed nothing.
        #
        # ⚠ **THE OPERATION NAME IS STILL `serve_customer` AND THAT IS
        # DELIBERATE, NOT AN OVERSIGHT.** It is declared by SIX manifests, it
        # is the catalogue key's last segment, and — the part that decides it —
        # it is STORED: `IntegrationCredential.scope` names it on every issued
        # key, `IntegrationRun.operation` on every recorded call and
        # `IntegrationRateLimit.operation` under a unique constraint. Renaming
        # it is a data migration across three tables and ~29 files, not a
        # rename, so it is recorded as owed (`OQ-INT-12405`) rather than done
        # here. Nothing a partner or a clerk reads carries it.
        Operation(
            name="serve_customer",
            served_path="/partner/v1/accounts",
            label="Read accounts",
            description="They collect the account list to match their own.",
            direction="out",
            initiative="them",
            transport="https",
            trigger="partner",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            respond_after="authenticate",
            envelope_status={"ok": 200, "refused": 404},
            rate_limit_per_minute=60,
        ),
        # ── `DEF-INT-5622` — THE ONE-ACCOUNT-AT-A-TIME API HAD NO ROW ───────
        # `GET /api/partner/v1/consumer-info` was built, routed and tested in
        # `CR-111-BRC04` and declared by NO manifest, so it drew no row: the
        # screen renders one row per operation and the PO counted **four APIs
        # where five exist**. PO 2026-09-17, on the live deployment: *"this
        # apis is not visiable in invoice cloud"*, after asking for account
        # details one account at a time. It is hard-won law 2's MIRROR — not
        # dead UI, but a live capability with no door — and an absence is
        # invisible to every check this repo has.
        #
        # ⚠ **IT IS ITS OWN OPERATION NOW, WHICH REVERSES A DELIBERATE CHOICE
        # AND THE REASONING FOR THE REVERSAL BELONGS HERE.** `CR-111-BRC04`
        # hung this address on `serve_customer` on purpose — *"a second ADDRESS
        # onto one door, not a second door"* — so that a clerk who switched
        # accounts off switched this off too. That is a real safety property
        # and it was bought with a real cost: the address could not be SEEN,
        # and a capability a partner cannot discover is one nobody uses. With
        # its own row the clerk gets the property back in a stronger form —
        # **two rows, two ticks, and the screen says which is which** — instead
        # of one tick silently governing two addresses.
        #
        # ⚠ **THE PRICE, RECORDED RATHER THAN DISCOVERED LATER:** a key scoped
        # `serve_customer` and nothing else can no longer call `consumer-info`,
        # and the five ERP manifests do not declare this operation at all, so
        # an ERP key cannot reach it. That is correct — `consumer-info` is
        # Invoice Cloud's address out of Invoice Cloud's document and appears
        # in no ERP's — and it is safe to change today because the address is
        # one day old (`6f7dabf4`, 2026-09-17) and this connector reads *Not
        # set up* with KEYS IN USE 0.
        #
        # ⚠ **IT SERVES MORE THAN THE LIST DOES, WHICH IS WHY A SEPARATE TICK
        # IS THE HONEST SHAPE.** `remote_plan_id` and `opening_balance` are on
        # this payload and on no other (`DEF-INT-5587`), so *read the account
        # list* and *look one account up* are genuinely different permissions.
        #
        # The address keeps Invoice Cloud's own word. `consumer-info` is the
        # name in THEIR document, the way `bill-download/` keeps their trailing
        # slash; `DEF-INT-5623` is about the word OUR surface uses for OUR
        # thing, and this is theirs.
        Operation(
            name="serve_consumer_info",
            served_path="/partner/v1/consumer-info",
            label="Read one account",
            description="They look one account up by its number.",
            direction="out",
            initiative="them",
            transport="https",
            trigger="partner",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            respond_after="authenticate",
            envelope_status={"ok": 200, "refused": 404},
            rate_limit_per_minute=60,
        ),
        Operation(
            name="serve_bill",
            served_path="/partner/v1/bills",
            label="Read bills",
            description="They collect the bills we issued, for a period.",
            direction="out",
            initiative="them",
            transport="https",
            trigger="partner",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            respond_after="authenticate",
            envelope_status={"ok": 200, "refused": 404},
            rate_limit_per_minute=60,
        ),
        Operation(
            name="serve_payment",
            served_path="/partner/v1/payments",
            label="Read payments",
            description="They collect the payments we took, for a date range.",
            direction="out",
            initiative="them",
            transport="https",
            trigger="partner",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            respond_after="authenticate",
            envelope_status={"ok": 200, "refused": 404},
            rate_limit_per_minute=60,
        ),
        # ── `DEF-INT-5586` — THE ADDRESS THAT HAD NO DOOR ──────────────────
        # `GET /partner/v1/bill-download/` was registered, routed, tested and
        # unreachable, because a key's scope comes from its manifest's own
        # operations and no manifest declared this one. This row is the door.
        Operation(
            name="serve_document",
            served_path="/partner/v1/bill-download/",
            label="Download a bill",
            description="They fetch one bill as a printed page, by its id.",
            direction="out",
            initiative="them",
            transport="https",
            trigger="partner",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            # The SUCCESS shape. A refusal is the same JSON sentence every
            # other partner address answers with (`BR-INT-044`).
            codec="pdf",
            respond_after="authenticate",
            envelope_status={"ok": 200, "refused": 404},
            rate_limit_per_minute=600,
        ),
        # ── THE WRITE · `POST /partner/v1/make-payment/` ────────────────────
        # ⚠⚠ **THE FIRST OPERATION ON THIS SURFACE THAT IS NOT A READ, AND
        # DECLARING IT HERE IS WHAT CREATES THE WRITE SCOPE.** A key's reach is
        # its own `scope` list and `serve.scope_permits` is check 5 of the
        # door, so this row is the ONLY thing that lets any key call the
        # address — and **every key issued before this file landed was scoped
        # from the operations that existed then, so no existing key acquires
        # the ability to create money by this row appearing.** A clerk grants
        # it by ticking a row that says *Take a payment* beside five that say
        # *Read*, and `machine_auth.issue_key` refuses an empty scope and
        # offers no default, so nothing acquires it by omission (hard-won law
        # 3 — the unsafe option is the one you type).
        #
        # ⚠ **A KEY WITHOUT IT GETS THE DOOR'S ONE REFUSAL** — `404`,
        # `REFUSED`, five words, padded to `serve.REFUSAL_FLOOR_S`,
        # indistinguishable from an unknown key. So a partner probing for a
        # write door with a read-only key learns nothing about whether one
        # exists (`BR-INT-044`).
        #
        # ⚠ **`direction="in"` AND `initiative="them"` — THE DATA MOVES IN AND
        # THEY START IT.** `Manifest.we_never_dial` reads that pair, so this
        # connector still has no adapter and none is missing: they present a
        # key we issued and post to us. It is `payments_kiosk`'s exact shape on
        # a different door.
        #
        # ⚠ **IT IS NOT `fetch_payment` AND IT DOES NOT REOPEN
        # `OQ-INT-12396`.** The section above — *WHY THERE IS NO
        # `fetch_payment`, SAID PLAINLY* — is about a SCHEDULED PULL, where the
        # second run of a nightly job has nothing to key on and records every
        # payment twice. **A PUSH HAS A KEY: their own `payment_reference`,
        # sent on every call, standing behind `uq_payments_webhook_key`.** PO
        # 2026-09-18 reversed the direction in four words — *"they post to us
        # daily"* — and the whole Make Payment design was walked with the PO
        # and confirmed on 2026-09-24. The pull question stays OPEN and this
        # row does not touch it.
        #
        # **60 a minute**, the three read collections' figure and deliberately
        # not the document route's 600. A payment is one call per payment
        # taken, and a portal serving the top of the ICP (40,000 accounts) does
        # not take sixty a minute. A stolen key holding this scope gets sixty
        # attempts a minute at creating money — every one still bounded by the
        # tenant the key was issued for, by an account and a bill number it has
        # to name correctly, and by hard rule 6, under which a repeated
        # `payment_reference` is ONE payment however many times it arrives.
        Operation(
            name="record_payment",
            served_path="/partner/v1/make-payment/",
            label="Take a payment",
            description="They send us a payment a customer made on their portal.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="partner",
            # ⚠ **`reconcile` AND NOT `refuse`, WHICH IS THE PO-CONFIRMED
            # BEHAVIOUR AND THE OPPOSITE OF THE KIOSK'S.** A second delivery of
            # the same `payment_reference` is answered `200` with the ORIGINAL
            # payment and `duplicate: true` — never an exception and never a
            # `409` — because a partner retrying after a timeout did the right
            # thing, and telling them it failed is how a retry becomes a second
            # payment. `key_field` names where their id is, so there is one
            # declared place and no guessing at three (`BR-INT-020` D). ⚠ WHICH
            # of their columns is the immutable one is `OQ-PAY-12626`, OPEN
            # with Invoice Cloud; they map whichever they confirm into this
            # field, so the answer changes their mapping and not this line.
            idempotency=Idempotency(
                mode="reconcile", source="provider_event_id", key_field="payment_reference"
            ),
            completion="immediate",
            codec="json",
            # The reply carries a payment number, and a payment number exists
            # only once the row does. `authenticate` would be a promise we had
            # not kept yet (`BR-INT-030`).
            respond_after="persist",
            # ⚠ **`duplicate` IS `200`, DECLARED HERE RATHER THAN LEFT TO BE
            # INFERRED** (decision log 2026-09-24). The kiosk's door answers
            # `409` for its duplicate; this one does not, and a reader
            # comparing the two manifests should find the difference stated.
            envelope_status={"ok": 200, "duplicate": 200, "refused": 404},
            rate_limit_per_minute=60,
        ),
    ),
)
