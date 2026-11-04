"""Itron — collect readings from the Itron head-end (Meters · COMING SOON v2).

**Split out of `meters_mdm`, the one card that read *Itron / Sensus* and gave
each vendor half a name** (`CR-110-BRC04`, blueprint p162: *"splits into two
connectors"*). CFG-08 and VIEW-08 are its drawing.

⚠ **NOBODY HAD TO BE MIGRATED, AND THAT WAS MEASURED RATHER THAN ASSUMED.**
p162 warns that *"a tenant who connected it has to be migrated to whichever
vendor they actually use — the row cannot say which"*, and it cannot: a
`meters_mdm` connection row records the shared key and nothing that names a
vendor. Measured on 2026-09-16 against the development database, under RLS,
tenant by tenant: **12 connection rows across 4 tenants and not one is
`meters_mdm`** — they are `bank_lockbox_file`, `email_smtp` and
`meters_neptune360`, three per tenant — and **0 rows in
`integration_credential`.** So there was nothing to split and no question to
ask. ⚠ A count read WITHOUT setting `app.tenant_id` is not evidence: row-level
security hides rows from an aggregate exactly as it hides them from a SELECT,
and the first read returned `(0 rows)` over twelve real ones. **If this ever
has to be done on a live database, mint the question rather than choosing a
vendor for somebody** — the row cannot say, and only the utility can.

⚠ **COMING SOON, AND THE REASON IS A SIGNED RULE RATHER THAN AN UNFINISHED
FILE.** `BR-INT-012`: enabling interval/AMI ingestion for ANY tenant requires
re-running the B6 capacity math and an Eng-Lead partition sign-off first
(`NFR-27`); v1 read intake is CSV. That rule bound `meters_mdm` and it binds
each of the connectors it became. The card reads *Coming soon · v2*, the server
refuses a connect, and the registry refuses to bind an adapter to a coming-soon
provider — which is the hold enforcing itself rather than a comment promising
it (hard-won law 1).

⚠ **CONNECTORS 07, 08 AND 09 ARE DRAWN IDENTICALLY** — measured frame by frame,
field for field and operation for operation; only the title, the one-line
summary and the badge differ. Three head-ends, one shape. `BR-INT-037` says
that is exactly right, and it is recorded here so nobody building the second
one goes hunting for a difference the drawing does not have.

⚠ **NO TIME OF DAY.** CFG-07, CFG-08 and CFG-09 each draw a clock in a *When it
runs* panel with the words *"Your time zone. The only part you choose."* PO
ruling 2026-09-16, verbatim: *"we are going to use runbooks to run the scheduled
job … conenctor i a conenctor not a logic to to ETL."* Scheduling is Runbooks';
a connector says an operation runs on a clock and never says which hour. The
drawn box is recorded as *drawn, deliberately not built*.

⚠ **`fetch_billing_export` IS DECLARED AS DRAWN — INWARD, AND WITHOUT
`mutates_partner_state` — AND THE DIFFERENCE FROM NEPTUNE IS DELIBERATE.**
`meters_neptune360` holds the same idea as TWO operations, because asking
Neptune for an export **closes billing routes on their side**
(`mutates_partner_state=True`, keyed on a `request_key` we mint before the
request leaves). CFG-08 draws Itron's as a single row marked *We collect*,
and **nothing measured says this vendor's export changes anything of theirs.**
Guessing either way would be wrong: claiming it mutates would force a
duplicate guard the PO has just moved to Runbooks, and claiming Neptune's
two-operation shape would invent a row the drawing does not have. It is
declared as drawn and flagged here for whoever reads Itron's real
specification in phase 2.

THE CEILINGS, AND WHY
----------------------
Every drawn figure is an illustration (B14 rule 37; the blueprint says of
itself *"No value here was read from anything … A builder taking `10 / min` off
a meter row as the real ceiling would be doing exactly what that rule exists to
stop"*). These are ours.

* The three collections — **60 a minute.** These are OUTWARD, so the number is
  *what they allow us*, and until a contract says otherwise the honest default
  is one call a second: polite to any head-end, and fast enough that a paged
  walk of a nightly window is never waiting on our own throttle. The drawn
  `10 / min` would make a 105-window walk take ten minutes of pure waiting.
* `fetch_billing_export` — **10 a minute.** It runs on demand, once per export.
  Anything faster is a retry storm.

⚠ The limit is a guard, not a setting: no clerk may change it (PO: *"so wecant
allow clark to reset it"*), so a wrong number here is a support call.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.meters_itron.*` wins on screen when present, so a
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
    key="meters_itron",
    category="meters",
    display_name="Itron",
    summary="Collect readings from the Itron head-end.",
    disposition=Disposition(kind="coming_soon", wave="v2"),
    auth=Auth(mode="we_hold_theirs", placement="header"),
    fields=(
        #: The PO's phase-1 dummy API, seeded as data so every operation below
        #: has an address that resolves today (`DEF-INT-5488`). CFG-08 draws
        #: this box and labels it *Service address*; the panel's own footnote
        #: — *"All 4 use the address above"* — is true on this form because
        #: the address really is above it.
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            default="https://api.itron.example",
        ),
        Field(name="site_id", label="Site / account ID", kind="text"),
        Field(name="api_key", label="API key", kind="secret"),
    ),
    operations=(
        Operation(
            name="fetch_reading",
            label="Collect readings",
            description="We collect readings from the head-end.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            #: A reading's own identity is the meter and the moment, so a
            #: second sight of one is the same reading and not a duplicate
            #: event. This is NOT the money-duplicate judgment the PO moved to
            #: Runbooks — it is a fact about the reading.
            idempotency=Idempotency(
                mode="reconcile", source="natural_key", natural_key="meter + read_at"
            ),
            completion="immediate",
            codec="json",
            rate_limit_per_minute=60,
        ),
        Operation(
            name="fetch_meter_inventory",
            label="Collect meters",
            description="We collect the head-end's list of meters.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(
                mode="reconcile", source="natural_key", natural_key="meter serial"
            ),
            completion="immediate",
            codec="json",
            rate_limit_per_minute=60,
        ),
        Operation(
            name="fetch_alert",
            label="Collect alerts",
            description="We collect the alerts the head-end raised.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(
                mode="reconcile", source="natural_key", natural_key="meter + raised_at"
            ),
            completion="immediate",
            codec="json",
            rate_limit_per_minute=60,
        ),
        Operation(
            name="fetch_billing_export",
            label="Request billing export",
            description="We ask the head-end for the billing export and collect it.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="manual",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            rate_limit_per_minute=10,
        ),
    ),
)
