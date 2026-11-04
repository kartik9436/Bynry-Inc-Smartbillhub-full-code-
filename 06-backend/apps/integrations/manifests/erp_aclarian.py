"""Aclarian — a finance system reads our payments and bills (ERP · LIVE).

One of the **five named ERPs** that replace the generic `gl_partner` card
(`CR-110-BRC04`, blueprint p162: *"Replaced by five named ERPs"*). CFG-17 and
VIEW-17 are drawn identically to the other four — measured image by image —
so the five are one build and five files (`BR-INT-037`).

⚠ **ACLARIAN IS A REAL ERP COMPANY, AND THIS LANE WAS ABOUT TO RULE OTHERWISE.**
The blueprint doubts its own fixture name on p143 — *"When you said 'Aclarian',
did you mean Aclara, the meter vendor? Here that word is a partner we made up
for worked examples"* — and the same afternoon the PO had ruled that two
unnamed vendors ship as placeholders. It was a plausible argument, and it was
wrong. PO, 2026-09-16, verbatim: **"this is erp company aclarian"**. So this is
connector 17 of 28, built like Workday and SAP: a real vendor with a real form,
never a card that says coming soon. **The lesson is law 13's mirror image** —
that law says never ask the PO twice, and it does not say decide anything you
can construct an argument for. The only thing that could tell this case apart
from the genuine placeholders was a fact the PO holds.

⚠ **SPLITTING STRANDED NOBODY, AND THAT WAS RE-MEASURED RATHER THAN QUOTED.**
`CR-110-BRC04` records that no partner holds a live key, and it says in the same
breath that the claim *"stands on TODAY's checkout and nothing keeps it true"*.
Re-measured on 2026-09-16 against the development database, under RLS, tenant by
tenant: **12 connection rows across 4 tenants, and not one of them is
`gl_partner`** (they are `bank_lockbox_file`, `email_smtp` and
`meters_neptune360`, three per tenant), and **0 rows in
`integration_credential`.** So no key had to be moved and no migration was
needed. ⚠ A count of zero read WITHOUT setting `app.tenant_id` is not evidence —
row-level security hides rows from an aggregate exactly as it hides them from a
SELECT, and the first read of `integration_connection` returned `(0 rows)` over
twelve real ones.

THE RELATIONSHIP: THEY DIAL US
-------------------------------
`auth.mode = "they_hold_ours"` — a key WE issue, scoped to one tenant, shown
once and never again (`BR-INT-053`). Every operation is `initiative = "them"`,
so there is nothing for us to dial, no adapter exists and none is missing
(`Manifest.we_never_dial`). The FOUR reads are `direction = "out"`: the data
moves OUT to them. The endpoint on each row is **ours** — `/partner/v1/payments`,
`/partner/v1/bills`, `/partner/v1/customers`, `/partner/v1/ledger` — the same
address for every partner, so this manifest declares no host field and the
registry's host check skips it by name (`_validate_hosts`, and
`Registry.host_coverage()` prints how many were skipped beside how many were
checked).

⚠ **AND THOSE FOUR ADDRESSES ARE NOW DECLARED RATHER THAN DESCRIBED
(`CR-110-BRC04` phase 2).** They were written in this paragraph and nowhere a
screen could read them, so the connection screen's ENDPOINT column drew a dash
on all three rows — a column structurally incapable of showing anything for
this whole quadrant (hard-won law 7). `Operation.served_path` carries each one
now, and this paragraph is the prose beside the data instead of the only copy
of it. **What a partner dials is `/api/{utility}/partner/v1/bills`**; the
manifest holds the half that is the same for every utility, because a manifest
is shared by every tenant and cannot hold one utility's slug.

⚠ **`partner`, NEVER `aclarian`.** PO 2026-09-16, verbatim: *"why aclarian in
it - we cna make it generic - saying partner - so that we can give it to anyone
who needs bills for any csutomer if autherised"*. The supplied specification
wrote `/api/ix/aclarian/…`, which would have made one vendor a URL segment and
broken *one base URL for every partner*: SAP, Workday, Infor and MSGP dial the
same four addresses with their own keys. **Aclarian is a KEY, not a path.**

⚠ **A BLANK SCOPE GRANTS NOTHING, AND THE CHOICE IS NOW ON THE API ROWS.** The
drawing puts *"Leave blank for everything the key allows"* under its scope box,
which makes the widest permission the default a clerk gets by reading nothing.
That is hard-won law 3 inverted, and the PO ruled with the law: a key with
nothing named cannot be issued (`machine_auth._validated_scope`).

⚠ **THE `scopes` FIELD IS RETIRED — SUPERSEDED 2026-09-16, NOT SOFTENED.** It
was declared `kind="select"`, which is SINGLE-VALUE, so a clerk could grant one
of four. PO, verbatim: *"we need to allow all apis to be read - all 4 currently
i can select only 1 or you remove it and put selection on off directly on
apis"*, and they named the fix they wanted. **Each operation below now carries
its own switch on the set-up screen**, and the switches ARE the key's scope. One
place instead of two, so the field and the API list can never disagree — and one
vocabulary instead of two (`DEF-INT-5504`), because what the clerk switches on
is the operation name the door already enforces.

⚠ **NO MAPPING, NO VOCABULARY, NO TIME OF DAY.** PO 2026-09-16: *"we dont need
mapping at connector level it will be in runbook with business logic"* and
*"conenctor i a conenctor not a logic to to ETL"*.

THE NAMES ARE THE FORMAT WE OWN
--------------------------------
`<runner>_<noun>`, and the verb is the runner that executes it, so the key says
which of the four doors a call goes through before you open a file. `serve` is
*they read · out · them*, which is `runners/serve.py`. Singular in a key, plural
in a URL: `serve_bill` → `GET /partner/v1/bills`. The labels are verb-first and
three words or fewer.

THE CEILING, AND WHY 60
------------------------
Every drawn figure is an illustration (B14 rule 37); the drawing shows
`300 / min` and none of it was copied. **60 a minute** is ours, and it is the
INWARD half — *what we allow them* — which is the half `serve.check_rate_limit`
actually enforces and the half the PO's *"if somone hack we will not have a
control"* is about. The reasoning: a month-end walk of the largest tenant this
product models (40,000 accounts, the top of T5) pages at **1,000 rows a page**
(PO 2026-09-16, *"make this as 1000 per page"*), so **40 calls**, which finishes
inside forty seconds at one call a second. A stolen key gets sixty tries a
minute rather than three hundred. ⚠ The limit is a guard and not a setting — no
clerk may raise it — so a wrong number here is a support call rather than a
five-second fix (PO: *"so wecant allow clark to reset it"*).

⚠ **THE FOURTH OPERATION IS 60 TOO, AND THE AGGREGATE IT MAKES IS STATED
RATHER THAN LEFT TO BE NOTICED.** The window is per connection AND per
operation (blueprint p017), so four operations at sixty is **240 calls a minute
against a stolen key**, where three were 180. That is p017's design and not
this lane's to change; it is written down because a per-operation ceiling reads
like a total and is not one. Sixty is kept uniform across the four because the
ledger is the largest set and therefore the one the arithmetic was computed
for: a 200,000-row ledger month is 200 pages, which is three and a half minutes
at sixty a minute. A partner that cannot finish a month-end pull in that time
would be the reason to move the number — not a guess made now.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.erp_aclarian.*` wins on screen when present, so a
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
    key="erp_aclarian",
    category="erp",
    display_name="Aclarian",
    summary="Your finance system collects payments and bills from here.",
    #: LIVE, exactly as `gl_partner` was. The capability is built and shipped —
    #: `partner_api.py` serves these three reads today; only the vendor's NAME
    #: is new. Marking the five coming-soon would take a working partner
    #: surface off the product to record that a name changed.
    disposition=Disposition(kind="live", phase=None),
    auth=Auth(mode="they_hold_ours", placement="bearer"),
    network_allowlist=True,
    fields=(
        # ── CR-110-BRC04 phase 2 · `DEF-INT-5534` and `DEF-INT-5537` ────────
        # ⚠ **`client_id` IS GONE AND `scopes` IS GONE, AND NEITHER IS A
        # TIDY-UP.** PO 2026-09-16, verbatim: *"why we need client id - they
        # read our data - why we need client id here - also we need to allow
        # all apis to be read - all 4 currently i can select only 1 or you
        # remove it and put selection on off directly on apis"*.
        #
        #   * `client_id` was REQUIRED and read by NOTHING. The only
        #     `client_id` in this module is `oauth.py`'s, which is OUR
        #     registration with a vendor WE dial — the opposite direction. It
        #     came in with the `gl_partner` template these five were split out
        #     of. **For a partner who reads from us, the KEY identifies them**,
        #     and the door proves it: `serve.resolve_caller` goes key →
        #     credential → connection → tenant and consults no other input
        #     (`BR-TEN-003`). A required field nothing reads is a door a clerk
        #     cannot get through: Save refused, so `Generate a key` could never
        #     be reached, which is exactly what the PO reported.
        #   * `scopes` was `kind="select"`, which is SINGLE-VALUE, so a clerk
        #     could grant one of four. **The choice moved onto the API rows
        #     themselves** — the four operations below are already drawn there,
        #     so one place instead of two and they cannot disagree. That also
        #     closes `DEF-INT-5504`: the clerk's ticks and the key's scope are
        #     now the SAME vocabulary, the operation names, instead of
        #     `payments` here and `serve_payment` at the door.
        # ⚠ **OPTIONAL SINCE 2026-09-17, BY PO RULING** — verbatim: *"In fact we
        # dont want allowed_addresses - restriction - can we make it options"*.
        # `required=True` was `Field`'s own default and every ERP manifest took
        # it bare, so a clerk could not save the form without typing an address
        # — and whatever they typed became an EXHAUSTIVE list that locked every
        # other address out. `runners/serve.allowlist_permits` has always read
        # an empty or absent list as *permit everything*, so this is a FORM
        # restriction being lifted and not an enforcement change; that function
        # is deliberately untouched.
        #
        # ⚠ **WHAT IT COSTS, SAID PLAINLY:** with no address listed the KEY IS
        # THE WHOLE DOOR, and anyone holding it may call from anywhere. That is
        # how most SaaS APIs work and it is the PO's call to make; it is written
        # here and in the decision log rather than left in a chat message.
        Field(name="allowed_addresses", label="Allowed addresses", kind="text", required=False),
        Field(name="issued_key", label="The key for them to use", kind="issued_secret"),
    ),
    operations=(
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
        # ── `DEF-INT-5623` — AN ACCOUNT IS CALLED AN ACCOUNT ────────────────
        # The address moved with the vocabulary, because THERE IS ONE ADDRESS
        # AND EVERY PARTNER SHARES IT: `partner_urls.PARTNER_ROUTES` is a
        # single route table, so `/partner/v1/accounts` could not be renamed
        # for InvoiceCloud and left as `/partner/v1/customers` here without
        # giving one thing two names (`DEF-014`) or pointing this row at a
        # route that answers nothing. The old address is RETIRED rather than
        # deleted — `partner_api.RETIRED_FOR` — so a partner holding it is told
        # where to go instead of meeting the refusal a stolen key gets.
        #
        # The label follows for the same reason the InvoiceCloud one did: the
        # values are accounts (PO 2026-09-16, *"Customers = accounts"*) and
        # `seams/customers.py` has served accounts since wave 2.
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
        # ── CR-110-BRC04 phase 2 wave 0 · THE FOURTH ROW ─────────────────
        # A finance system posts our bills and our receipts into its own books,
        # and the thing it reconciles against is the JOURNAL. Without this a
        # partner holds the two documents and has no way to check that what it
        # posted equals what we posted.
        #
        # ⚠ **ADDING IT IS ONE FILE AND NO MIGRATION**, which is `BR-INT-037`
        # being true rather than claimed: the connection screen grows a fourth
        # API row with no screen code, exactly as SAP appeared mid-build.
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
    ),
)
