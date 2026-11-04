"""New World / Logos — a municipality's finance system reads our receipts (ERP · LIVE).

Tyler Technologies' New World ERP (Logos) is the **official record for ALL
municipal revenue** at the utility being onboarded on it, which is why this
connector exists and why two things below are written more loudly than a
manifest usually writes anything.

THE RELATIONSHIP: THEY DIAL US
-------------------------------
`auth.mode = "they_hold_ours"` — a key WE issue, scoped to one tenant, shown
once and never again (`BR-INT-053`). ⚠ **THIS SAID *"Every operation is
`initiative = "them"`, so there is nothing for us to dial and no adapter is
missing"* UNTIL `CR-173-BRC10` (2026-10-07), AND IT IS NO LONGER TRUE.** The
third operation, *Send receipt file*, is OURS to start — we place the day's
file in the City's SFTP folder — so `Manifest.we_never_dial` is now False and
`adapters/erp_newworld.py` is the adapter that places it. The two operations
the City dials are unchanged. The endpoint on each of THOSE rows is **ours**, and it is
`partner`, never a vendor name (PO 2026-09-16: *"why aclarian in it - we cna
make it generic - saying partner"*). **New World is a KEY, not a path.**

TWO OPERATIONS, AND THE SPLIT IS THE PO's RULING OF 2026-09-22
---------------------------------------------------------------
*"i think we shoudl create seperate enpoint - you can se the same components
that you use, dont write completely new code - what way we can keep it
sepearet"*, and, settling which of the two: *"we need seperate endpoint if we
deicde only for payemnt and not for ledge"*.

  * **`serve_receipt` → `/partner/v1/receipts` is NEW.** Their Receipt is four
    levels — header · transactions · GL distributions · payment nodes — with a
    balancing rule across two of them. Our `/partner/v1/payments` is one flat
    row per payment. That is a different PROJECTION of the same facts, not the
    same resource in another format, and bending the existing address into it
    would change a contract four other ERP manifests already consume.
  * **`serve_ledger` → `/partner/v1/ledger` is REUSED UNCHANGED.** Not one
    line of it moved. The books are the books.

⚠ **THE FORMAT WAS NOT THE REASON, AND IT IS WORTH SAYING SO HERE BECAUSE
*PARAMETERISE IT* WAS THE FIRST ANSWER OFFERED AND IT WAS WRONG.** XML has been
a supported codec since `CR-069` wave D and `codecs.py`'s own docstring names
this exact case. Reading the specification is what changed the answer: it is
the SHAPE.

⚠⚠ **THE CARD FIELDS ARE NOT BUILT. NOT BUILT AND SWITCHED OFF — NOT BUILT.**
-------------------------------------------------------------------------------
Their specification carries `ReceiptPaymentCreditCardNumber`,
`ReceiptPaymentCreditCardType`, `ReceiptPaymentCreditCardExpirationDate` and
`ReceiptPaymentCreditCardValidationNumber`. **Populating any one of them pulls
cardholder data into a file and destroys the PCI scoping that keeps card data
out of this product entirely.**

A card payment goes as `ReceiptPaymentType = 2` (Charge) with **no card
number**. **There is no field on this manifest, no flag, no setting and no
mapping entry for any of the four** — so there is nothing for a later lane to
turn on, which is the difference between *not built* and *switched off*.

⚠ **SUPERSEDED IN PART 2026-10-21 — FOR THE NAMES ONLY (`DEF-INT-10304`).**
Until then `G130` failed this file, `newworld.py` and the fixtures if one of
those names appeared at all. PO, 2026-10-21, option A: *"Always write all four
as `""`"*. The receipt document now carries the four as ATTRIBUTES on every
payment node, present and always empty, because New World's confirmed
template lists them. **Card DATA stays not built**: `G130` now fails any code
or file that could give one of them a value, and `newworld.validate` refuses a
file in which one is not empty. The same day the whole document moved to New
World's template shape — every field an attribute, on a `<ROOT>` document —
and it is validated before it is sent or served.

⚠⚠ **THE THREE WORDS NEW WORLD HAS TO ADD AT THEIR END, OR RECEIPTS BOUNCE.**
-------------------------------------------------------------------------------
PO ruling 2026-09-22, verbatim: *"we send ACH, Moenry Order and Lockbox - as
mapping from our side and wil ask them to map it at their end"*. Their five
`ReceiptPaymentType` values are Cash · Check · Charge · Other · Wire Transfer
and **none of them is ACH**, so those three tenders go as **Other** carrying a
word in `ReceiptPaymentOtherType`.

**Their specification says that word must match New World's own *Other Payment
Type* validation set — a list held on THEIR side.** Until their team adds
`ACH`, `Money order` and `Lockbox` to it, **every receipt carrying one is
rejected at their end.** The PO knows and is asking them.

**It is a dependency on another company, so it is written where somebody will
find it:** here, in `apps/integrations/mappings.py` where the three words live
as configuration, in the review-ledger row, and in the decision log. A
different spelling coming back from their team is a line in that table and a
mapping row on the connection — **never a rebuild**.

⚠ **AND IN PRACTICE THIS FEED CARRIES ONLY TWO OF THE SEVEN TENDERS.** It is
`origin = webhook` only — online money — so cash, cheque, money order and
lockbox cannot appear in it at all: those are counter and post work, and they
are `entry` or `import` origin. **This feed is ACH and Card**, which is why ACH
was the row that mattered.

⚠ **ONLINE-ONLY IS THEIRS, NOT OURS, AND THE RISK IS STATED RATHER THAN
ASSUMED AWAY.** New World is the official record for ALL municipal revenue. If
SmartBillHub sends only the online receipts, the counter and lockbox money must
reach it another way or the City's general ledger is short. That is probably
already true — a cashier system and a bank lockbox usually post to the ERP
directly — **but being wrong means the City's books do not balance and we are
the obvious suspect.** Ruled 2026-09-22 as the customer's own requirement.

⚠ **AN UNBALANCED RECEIPT IS SENT, FLAGGED AND COUNTED.** PO 2026-09-22:
*"please send receipt even if it is not balance"*. A refused receipt is money
that silently never reaches the City's books; an unbalanced one is money that
arrives wrong and can be found and fixed. Nothing is plugged and nothing is
rounded to fit — their importer enforces their rule and we let it. The counts
travel on the response headers and on the run row.

THE CEILING, AND WHY 60
------------------------
The same figure as the five other ERPs, for the reason `erp_aclarian.py` works
out in full: a month-end walk of the largest tenant this product models —
40,000 accounts, the top of T5 — pages at 1,000 rows, so 40 calls, which
finishes inside forty seconds at one call a second. The limit is a GUARD and
not a setting; no clerk may raise it (PO: *"so wecant allow clark to reset
it"*). Every drawn figure elsewhere is an illustration (B14 rule 37).

Data, not code (`BR-INT-037`). Read by `apps/integrations/registry.py` at
`AppConfig.ready()` and refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.erp_newworld.*` wins on screen when
present, so a translation is a catalogue line and never an edit to this file.
"""

from apps.integrations.registry import (
    Auth,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    Operation,
)

#: CR-173-BRC10 — the *Send to City folder* group and its six field names.
#: Named once here; `apps/integrations/receipt_push.py` and `file_drop.py`
#: import them rather than spelling them again.
SEND_FILE_GROUP = "send_file"
SFTP_HOST = "sftp_host"
SFTP_PORT = "sftp_port"
SFTP_USERNAME = "sftp_username"
SFTP_PASSWORD = "sftp_password"
SFTP_PATH = "sftp_path"
SFTP_HOST_KEY = "sftp_host_key"
SEND_RECEIPT_FILE = "send_receipt_file"

MANIFEST = Manifest(
    key="erp_newworld",
    category="erp",
    display_name="New World / Logos",
    summary="Your city's finance system collects the receipts we took.",
    #: LIVE. Both addresses serve today — `/partner/v1/ledger` since
    #: `CR-110-BRC04` phase 2 wave 5 and `/partner/v1/receipts` with this
    #: change. A `coming_soon` card over a working partner surface would be a
    #: refusal that is not true, which is hard-won law 2's mirror.
    disposition=Disposition(kind="live", phase=None),
    auth=Auth(mode="they_hold_ours", placement="bearer"),
    network_allowlist=True,
    fields=(
        # ⚠ **OPTIONAL, AS ON EVERY OTHER ERP SINCE 2026-09-17** — PO: *"In
        # fact we dont want allowed_addresses - restriction - can we make it
        # options"*. With no address listed the KEY IS THE WHOLE DOOR.
        Field(name="allowed_addresses", label="Allowed addresses", kind="text", required=False),
        Field(name="issued_key", label="The key for them to use", kind="issued_secret"),
        # ⚠ **THERE IS NO FIELD HERE FOR A CARD NUMBER, A CARD TYPE, AN EXPIRY
        # OR A CVV, AND THERE IS NOT GOING TO BE ONE.** See the docstring. This
        # comment exists so that a lane reading their specification beside this
        # file finds the reason here rather than concluding the fields were
        # forgotten.
        # ── CR-173-BRC10 · *Send to City folder* (PO approved 2026-10-07) ──
        # Six items, all OPTIONAL and all in one group, because they are ONE
        # utility's settings and not New World's (PO S1: *"this path is
        # specific for 1 tenant/utility and not common for everyone"*). A
        # connection with none of them sends nothing, ever: the runbook reads
        # an absent server as *not set up* and stops before building a file.
        # **No environment variable, settings file or deploy step carries any
        # of them** (PO 2026-10-07: *"this is tenant/utility data and should be
        # handled from screen itself"*). The group's own form (`file_drop`)
        # checks them as a set: server, user name and password together.
        Field(name=SFTP_HOST, label="Server", kind="host", required=False, group=SEND_FILE_GROUP),
        Field(
            name=SFTP_PORT,
            label="Port",
            kind="port",
            required=False,
            default="22",
            group=SEND_FILE_GROUP,
        ),
        Field(
            name=SFTP_USERNAME, label="User name", kind="text", required=False, group=SEND_FILE_GROUP
        ),
        # The password goes to the encrypted credential store, in the group's
        # OWN slot — never the slot that holds the key we issued the City.
        Field(
            name=SFTP_PASSWORD, label="Password", kind="secret", required=False, group=SEND_FILE_GROUP
        ),
        # `/` until the City confirms its folder; changed on this screen then.
        Field(
            name=SFTP_PATH,
            label="Folder",
            kind="text",
            required=False,
            default="/",
            group=SEND_FILE_GROUP,
        ),
        # The server's key, `SHA256:…`. Captured by **Test connection** and
        # shown, or typed from what the City sends. The nightly upload is
        # refused while it is empty — the client never accepts an unknown key
        # (decision log 2026-10-07).
        Field(
            name=SFTP_HOST_KEY,
            label="Server key",
            kind="text",
            required=False,
            group=SEND_FILE_GROUP,
        ),
    ),
    operations=(
        Operation(
            name="serve_receipt",
            served_path="/partner/v1/receipts",
            label="Read receipts",
            description="They collect the online payments we took, as their receipt file.",
            direction="out",
            initiative="them",
            transport="https",
            trigger="partner",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            # ⚠ **`xml` AND NOT `json`, AND IT IS THE ONE THING THE FORMAT
            # ARGUMENT GOT RIGHT.** The codec is already supported and already
            # fixture-backed; what it could not do alone was the four-level
            # shape. `fixtures/newworld/` records what this address actually
            # emits, byte for byte.
            codec="xml",
            respond_after="authenticate",
            envelope_status={"ok": 200, "refused": 404},
            rate_limit_per_minute=60,
        ),
        # ── REUSED UNCHANGED — the PO's ruling, as a row ────────────────────
        # ⚠ **THIS IS THE SAME ADDRESS `erp_aclarian` DECLARES AND THE SAME
        # VIEW SERVES.** Nothing about `partner_ledger` moved for this
        # connector, and adding New World to it cost exactly this row: one
        # file, no migration, no screen code — `BR-INT-037` being true rather
        # than claimed. If the ledger ever needs to differ per partner, that
        # is a new ruling and not a quiet edit here.
        Operation(
            name="serve_ledger",
            served_path="/partner/v1/ledger",
            label="Read the ledger",
            description="They collect the journal rows behind our bills and receipts.",
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
        # ── CR-173-BRC10 — WE place the day's file in the City's folder ─────
        # ⚠ **THE TWO ROWS ABOVE ARE BYTE-IDENTICAL TO WHAT THEY WERE.** This
        # is a third operation, outbound and OURS to start; the City may go on
        # pulling `/partner/v1/receipts` exactly as before.
        #
        # **What the file holds is the runbook's** (`BR-INT-054` as amended —
        # *"conenctor i a conenctor not a logic to to ETL"*): runbook *New
        # World receipt push* decides the day, builds ONE `<ROOT>` document
        # with `newworld.render` and asks this connection to place it. The
        # trigger is `scheduled` because a person sets the time in that
        # runbook's own schedule (PO Q6); a person can also run it by hand.
        #
        # `refuse` on `period_target`: one successful file per utility per
        # tenant-local day (PO Q4), enforced by
        # `integration_file_delivery`'s partial unique index — and a resend is
        # a person's deliberate act on the *Send to City folder* panel.
        Operation(
            name=SEND_RECEIPT_FILE,
            label="Send receipt file",
            description="We place the day's receipt file in the City's folder.",
            direction="out",
            initiative="us",
            transport="sftp",
            trigger="scheduled",
            idempotency=Idempotency(mode="refuse", source="period_target"),
            completion="immediate",
            codec="xml",
            host_field=SFTP_HOST,
            # One file a day; ten a minute leaves room for a person's test and
            # a resend and still refuses a runaway loop.
            rate_limit_per_minute=10,
        ),
    ),
)
