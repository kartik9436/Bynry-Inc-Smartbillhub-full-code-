"""Badger BEACON — collect readings from the BEACON head-end (Meters · COMING SOON v2).

**The one connector on the list of 28 that is new from nothing.** The other
thirteen without a file came out of splitting four we already had; this vendor
had no row, no manifest and no string anywhere in the repository outside a
front-end hold file. CFG-07 and VIEW-07 are its drawing.

⚠ VIEW-07's frame caption is drawn on p038 and is readable in the image, but
that page's text layer is split character by character, so a text search for
`VIEW-07` returns nothing and a lane grepping the PDF would conclude the frame
does not exist. It does. That is B14 rule 42 earning its place: a screen is
built from the drawing AS AN IMAGE.

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
request leaves). CFG-07 draws BEACON's as a single row marked *We collect*,
and **nothing measured says this vendor's export changes anything of theirs.**
Guessing either way would be wrong: claiming it mutates would force a
duplicate guard the PO has just moved to Runbooks, and claiming Neptune's
two-operation shape would invent a row the drawing does not have. It is
declared as drawn and flagged here for whoever reads BEACON's real
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
catalogue key `integrations.provider.meters_badger.*` wins on screen when present, so a
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
    key="meters_badger",
    category="meters",
    display_name="Badger BEACON",
    summary="Collect readings from the BEACON head-end.",
    disposition=Disposition(kind="coming_soon", wave="v2"),
    auth=Auth(mode="we_hold_theirs", placement="header"),
    fields=(
        #: The PO's phase-1 dummy API, seeded as data so every operation below
        #: has an address that resolves today (`DEF-INT-5488`). CFG-07 draws
        #: this box and labels it *Service address*; the panel's own footnote
        #: — *"All 4 use the address above"* — is true on this form because
        #: the address really is above it.
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            default="https://api.badgerbeacon.example",
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
