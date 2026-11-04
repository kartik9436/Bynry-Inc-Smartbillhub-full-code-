"""Water meter cloud (Neptune 360) — sixteen operations, one credential (Meters · LIVE, phase 4).

The largest single vendor in the design (`T-7`, sixteen tasks): one card,
one credential, sixteen things it does — collections that RECONCILE by natural
key (BR-INT-029: *1,240 read · 6 revised*, and a reading already billed never
moves), a billing export that is asked for, waited for and collected
(BR-INT-046), and three pushes that change THEIR world. The sixteen names are
this lane's reading of the design's task group — the COUNT is the design's, the
names are provisional.

⚠ **BOTH OF THE QUESTIONS THAT ONCE BLOCKED OPERATIONS HERE ARE NOW CLOSED, AND
THIS PARAGRAPH SAID OTHERWISE UNTIL 2026-09-06 (CLAUDE.md step W).** It read
*"Two of these are blocked to the boundary until ruled"* and named both as
OPEN; both were ruled on 2026-09-04 and the body went on describing the open
world, which is the exact rot the prime directive warns about.

  * **`OQ-INT-1484` — CLOSED, option (a), and WIDER than the question asked.**
    PO: *"not yet; We will not bring hourly internal data in this product"*.
    Hourly interval data is switched on for **no tenant** — not for a named one
    after a storage re-run either. The figure: 3,000 meters × 24 × 365 ≈ **26
    million** rows a year, about **half a billion** at the top of the range,
    not taken on. ⚠ **`collect_interval_data` STAYS DECLARED and is never
    built.** It is one of the sixteen things the vendor's own catalogue does,
    and the count is the design's; declaring it is a statement about THEIR
    product, and no runner in this repository walks it. That reading is a lane
    judgment with its reasoning in the decision log of 2026-09-06 — a later
    lane that wants the operation off the card should move it there, not here.
  * **`OQ-INT-1485` — CLOSED, option (a): we are master** of the meter-to-account
    link. The head-end's version shows as a DIFFERENCE and is never applied,
    and it may not even fill an empty link. `US-INT-036`'s write has a rule to
    implement rather than a boundary to raise at; that is wave L's, not this
    file's.

WHAT WAVE K ADDED, AND THE ONE THING IT DELIBERATELY DID NOT (2026-09-06)
-------------------------------------------------------------------------
`auth.token`, the fetch plans, the poll schedules, `result_delivery`, the four
`safety_parameters` and `mutates_partner_state` are all HERE, as data, because
`C10`, `C12`, `C18`, `C19` and `C20` are declarations and not code. **None of
those numbers appears in a runner** — changing `page_size` below changes the
request and touches nothing else, which is `BR-INT-037` and is the point.

**What the collected rows MEAN is not here and is not anywhere in this module.**
`BR-INT-054` as sharpened on 2026-09-06 gives integrations three things —
building a connection, holding keys and secrets, the lifecycle of a connection
— and `CR-069` §20.4 moves *"the readings projection — turning what was
collected into our measurement frame"* to Runbooks in as many words. The seam
it arrives through is `apps/integrations/seams/runbooks.py`, and it returns
nothing today.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.meters_neptune360.*` wins on screen when present, so a
translation is a catalogue line and never an edit to this file.
"""

from apps.integrations.registry import (
    Auth,
    Disposition,
    FetchPlan,
    Field,
    Idempotency,
    Manifest,
    Operation,
    Poll,
    TokenExchange,
)

#: ⚠ **THE FOUR PARAMETERS WHOSE DEFAULT IS UNSAFE (`C18`, `BR-INT-050`), AND
#: TWO OF THEM ARE ON THE MONEY PATH.** A run that leaves any of them unset
#: does not start, and the refusal names the one that was missing — because the
#: failure they prevent is silent: the request succeeds, the rows look like
#: readings, and a utility bills them.
#:
#:   `actual_consumption`  MONEY. Unset, the head-end answers with ESTIMATED
#:                         figures in the same shape as real reads. Nothing
#:                         downstream can tell them apart.
#:   `include_estimates`   MONEY. Defaults TRUE. Folds their estimates into the
#:                         same page as the reads we asked for.
#:   `unit_of_measure`     CLAUDE.md hard rule 3 — consumption always with an
#:                         explicit unit, never assumed. Their default varies
#:                         by site, so the same number means gallons at one
#:                         utility and cubic feet at the next.
#:   `read_time_zone`      A window boundary read in THEIR zone puts a
#:                         midnight read on the wrong day, and a wrong day is a
#:                         wrong billing period.
READING_SAFETY_PARAMETERS = (
    "actual_consumption",
    "include_estimates",
    "unit_of_measure",
    "read_time_zone",
)

MANIFEST = Manifest(
    key="meters_neptune360",
    category="meters",
    #: ⚠ RENAMED FROM *Water meter cloud* (`CR-110-BRC04`). CFG-06 draws the page
    #: head as **Neptune 360** and the frame's own note says so: *"Renamed. Ships
    #: today under a generic name. The connector, its fields and its operations
    #: do not change."* p162 calls this and Esri ArcGIS *"the safest two in the
    #: list"*.
    display_name="Neptune 360",
    summary="Collect readings and keep the meter list in step.",
    disposition=Disposition(kind="live", phase=4),
    auth=Auth(
        mode="token_exchange",
        placement="bearer",
        # `US-INT-028` decision 6 — **the window is THEIRS, not ours.** Ten
        # minutes is what Neptune issues; a manifest that wrote 3600 here would
        # not make the token live an hour, it would make the walk fail at
        # minute eleven with a token we believed in.
        token=TokenExchange(
            token_url="https://api.neptune360.example/oauth/token",
            ttl_seconds=600,
            refresh_before_s=30,
        ),
    ),
    fields=(
        #: The PO's phase-1 dummy API, seeded as data so all sixteen operations
        #: below have an address that resolves today (`DEF-INT-5488`).
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            default="https://api.neptune360.example",
        ),
        Field(name="site_id", label="Site ID", kind="text"),
        Field(name="api_key", label="API key", kind="secret"),
    ),
    operations=(
        Operation(
            name="collect_readings",
            label="Meter readings",
            description="We collect last night's readings for every meter.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            test_action="Read one meter's last reading.",
            # `C12` — two years of history in SEVEN-DAY windows, 5,000 records
            # to a page. A two-year backfill is 731 ÷ 7 = **105 windows**.
            fetch_plan=FetchPlan(window_days=7, page_size=5000),
            safety_parameters=READING_SAFETY_PARAMETERS,
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="collect_readings_by_route",
            label="Readings by route",
            description="We collect a route's readings when a route is billed.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            test_action="Read one meter's last reading.",
            fetch_plan=FetchPlan(window_days=7, page_size=5000),
            safety_parameters=READING_SAFETY_PARAMETERS,
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="collect_billing_export",
            label="Billing export",
            description="We collect the billing file they built for us.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="submit_poll_collect",
            codec="json",
            test_action="Read one meter's last reading.",
            # `C10` — they build the file while we wait: ask every 30 seconds,
            # up to 40 times. **Twenty minutes**, and then the run is
            # `unconfirmed` — *they never finished the file* — never
            # `succeeded` and never silently `failed` (BR-INT-018).
            poll=Poll(every_seconds=30, max_attempts=40),
            # `C20` — their v2 answers with an IDENTIFIER we collect by. The v1
            # operation below answers with a LINK. **One runner reads this
            # value and serves both**; nothing branches on the provider.
            result_delivery="handle",
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="collect_interval_data",
            label="Hourly interval data",
            description="We collect hourly readings where the meter records them.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            test_action="Read one meter's last reading.",
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="collect_alerts",
            label="Meter alerts",
            description="We collect leak, tamper and reverse-flow alerts.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            test_action="Read one meter's last reading.",
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="collect_register_replacements",
            label="Register replacements",
            description="We collect which meters had a register replaced yesterday.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            test_action="Read one meter's last reading.",
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="collect_meter_inventory",
            label="Meter inventory",
            description="We keep our meter list in step with theirs.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            test_action="Read one meter's last reading.",
            # `C12` — the register pages at **150**, not 5,000. A meter record
            # is fat (size, type, route, endpoint) where a reading is four
            # fields, and asking for 5,000 of them times out on their side.
            fetch_plan=FetchPlan(window_days=7, page_size=150),
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="collect_endpoint_inventory",
            label="Endpoint inventory",
            description="We keep the radio endpoint list in step with theirs.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            test_action="Read one meter's last reading.",
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="collect_service_points",
            label="Service points",
            description="We keep the service point list in step with theirs.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            test_action="Read one meter's last reading.",
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="collect_accounts",
            label="Accounts",
            description="We read which account they hold against each meter.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            test_action="Read one meter's last reading.",
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="collect_routes",
            label="Routes",
            description="We keep the reading routes in step with theirs.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            test_action="Read one meter's last reading.",
            # `C12` — routes page at **100**. Three services, three numbers,
            # and `US-INT-028` TC-2 asserts the runner asks for exactly these.
            fetch_plan=FetchPlan(window_days=7, page_size=100),
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="collect_usage_summary",
            label="Usage summary",
            description="We collect the month's usage summary per meter.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            test_action="Read one meter's last reading.",
            # Sixty a minute — OUTWARD, so the number is what Neptune allow
            # us, and one call a second is polite to any head-end while
            # never making a paged walk wait on our own throttle. The
            # drawn `10 / min` is an illustration (B14 rule 37) and would
            # cost ten minutes of pure waiting on a 105-window walk.
            rate_limit_per_minute=60,
        ),
        Operation(
            name="request_billing_export",
            label="Request billing export",
            description="We ask them to build the billing file for a route.",
            direction="out",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="refuse", source="request_key"),
            completion="submit_poll_collect",
            codec="json",
            poll=Poll(every_seconds=30, max_attempts=40),
            # `C20` — their v1 answers with a URL we store as the run's
            # artifact. Same runner, other value.
            result_delivery="link",
            # `C19` — ⚠ **THIS REQUEST CARRIES `CloseOnExport` AND CLOSES
            # BILLING ROUTES ON THEIR SIDE.** It is not a read that happens to
            # write; it changes the partner's world, so the key is minted and
            # the receipt written BEFORE the call, and the retry of the same
            # period is refused rather than closing the routes a second time
            # (BR-INT-050, BR-INT-020). The registry refuses this flag on any
            # idempotency source but `request_key`, because a key computed
            # from the answer cannot exist before the question.
            mutates_partner_state=True,
            # Ten a minute. It runs on demand, once per export or per push;
            # anything faster is a retry storm, and this one changes
            # Neptune's own world, so a storm is expensive there too.
            rate_limit_per_minute=10,
        ),
        Operation(
            name="push_account_meter_link",
            label="Account to meter link",
            description="We tell them which account a meter belongs to.",
            direction="out",
            initiative="us",
            transport="https",
            trigger="manual",
            idempotency=Idempotency(mode="refuse", source="request_key"),
            completion="immediate",
            codec="json",
            # Ten a minute. It runs on demand, once per export or per push;
            # anything faster is a retry storm, and this one changes
            # Neptune's own world, so a storm is expensive there too.
            rate_limit_per_minute=10,
        ),
        Operation(
            name="push_route_assignment",
            label="Route assignment",
            description="We tell them which route a meter is read on.",
            direction="out",
            initiative="us",
            transport="https",
            trigger="manual",
            idempotency=Idempotency(mode="refuse", source="request_key"),
            completion="immediate",
            codec="json",
            # Ten a minute. It runs on demand, once per export or per push;
            # anything faster is a retry storm, and this one changes
            # Neptune's own world, so a storm is expensive there too.
            rate_limit_per_minute=10,
        ),
        Operation(
            name="push_service_point",
            label="Service point",
            description="We tell them about a new or moved service point.",
            direction="out",
            initiative="us",
            transport="https",
            trigger="manual",
            idempotency=Idempotency(mode="refuse", source="request_key"),
            completion="immediate",
            codec="json",
            # Ten a minute. It runs on demand, once per export or per push;
            # anything faster is a retry storm, and this one changes
            # Neptune's own world, so a storm is expensive there too.
            rate_limit_per_minute=10,
        ),
    ),
)
