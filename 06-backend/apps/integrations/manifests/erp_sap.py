"""SAP — a finance system reads our payments and bills (ERP · LIVE).

One of the **five named ERPs** that replace the generic `gl_partner` card
(`CR-110-BRC04`, blueprint p162: *"Replaced by five named ERPs"*). CFG-19 and
VIEW-19 are drawn identically to the other four — measured image by image —
so the five are one build and five files (`BR-INT-037`).

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
(`Manifest.we_never_dial`). The three reads are `direction = "out"`: the data
moves OUT to them. The endpoint on each row is **ours** — `/partner/v1/payments`,
`/partner/v1/bills`, `/partner/v1/customers` — the same address for every
partner, so this manifest declares no host field and the registry's host check
skips it by name (`_validate_hosts`, and `Registry.host_coverage()` prints how
many were skipped beside how many were checked).

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
product models (40,000 accounts, the top of T5) pages at 500 rows a page, so 80
calls, which finishes inside 80 seconds at one call a second. A stolen key gets
sixty tries a minute rather than three hundred. ⚠ The limit is a guard and not a
setting — no clerk may raise it — so a wrong number here is a support call
rather than a five-second fix (PO: *"so wecant allow clark to reset it"*).

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.erp_sap.*` wins on screen when present, so a
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
    key="erp_sap",
    category="erp",
    display_name="SAP",
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
            name="serve_customer",
            label="Read customers",
            description="They collect the customer list to match their own.",
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
