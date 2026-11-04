# Step 0 — connectors 01 to 10, measured against the Integration Blueprint

<!-- ── Trace ──────────────────────────────────────────────
Blueprint: `05-prototype/05 Integration Blueprint.pdf` on the DEFAULT branch
           (`origin/claude/confirm-understanding-3ktufc`), 163 pages.
           Frames CFG-01/VIEW-01 … CFG-10/VIEW-10, pages p021–p047, and the
           28-connector catalogue on p161–p162.
Method:    B14 rule 42 — every field and every operation below was read from a
           PNG of the page, rendered by `10-scripts/pdf/pdf_render.py` at
           scale 2. Extracted PDF text was used ONLY to locate frames on pages
           and is quoted nowhere as a specification.
           B14 rule 37 — the drawn figures (120/min, 1,240 of 1,240, Today
           04:12, Site 4471, ••••7Q2F, 11f0••••308d) are ILLUSTRATIONS. What
           is recorded below is the SHAPE: that the column exists, that the
           operation carries a limit, that the value is masked.
Measured
against:   `06-backend/apps/integrations/manifests/*.py` (18 manifests) and
           `06-backend/apps/integrations/registry.py` (the closed
           vocabularies) and `models.py` (the 5 tables), at tip `fb3ca0aa`.
Rules:     BR-INT-026 (live and sandbox are two connection rows) · BR-INT-028
           (direction lives on the operation) · BR-INT-037 (adding an API is
           data, not code) · CLAUDE.md hard-won law 2 · CLAUDE.md prime
           directive (nothing below resolves an open question by choosing).
Scope:     Connectors 01–10 ONLY, and only their per-connector CONTENT — which
           fields and which operations each one draws. The common regions of a
           configure form and a view screen belong to the shared-shape lane;
           11–19 and 20–28 belong to two other lanes.
Builds:    NOTHING. Fixes NOTHING. Decides NOTHING the Product Owner should
           decide. This file is measurements and a list of questions.
─────────────────────────────────────────────────────── -->

**Nothing here is built and nothing here is fixed.** This is what the drawing
shows, what the code holds today, and where the two cannot both be true.

---

## How to read the two tables

**Table A** lists the fields on the **configure** form (`CFG-nn`), in the order
they are drawn, top to bottom and then left to right within a row.

**Table B** lists the operations on the **view** screen (`VIEW-nn`), in the
order the API table draws them.

Verdicts: **MATCHES** · **MISSING** (drawn, we have nothing) · **EXTRA** (we
have it, the drawing does not) · **DIFFERS** (how is stated) · **NEEDS A
RULING**.

### Three things the drawing does the same way on all ten, recorded once

1. **The `Connection details` panel is drawn with a solid accent rule across its
   top edge** on every one of the ten configure forms, and the same rule appears
   on the first panel of every view screen. Every later panel on both screens is
   drawn plain. Which `PanelTone` token that accent rule is belongs to the
   shared-shape lane; this file records only that the drawing shows it there and
   nowhere else.
2. **`Where it runs` — a two-segment control reading `Production` · `Sandbox` —
   is drawn inside `Connection details` on all ten forms.** It is listed as a
   row in every Table A because it is drawn, but it is **not a manifest field**:
   it is `integration_connection.environment`, whose vocabulary
   (`ENVIRONMENTS = ("production", "sandbox")`) already exists and already sits
   inside the unique key that `BR-INT-026` describes.
3. **The API table's right-hand column is clipped off the page in the source
   PDF, on every frame.** On a configure form the header reads
   `API · ENDPOINT | DIRECTION | WHEN | RATE LIMIT | T…`; on a view screen it
   reads `… | RATE LIMIT | LAST RUN | RESULT`, and `RESULT` itself is cut on
   several pages. The clipped configure column is measurable as beginning `TE`
   on p034 and `T` everywhere else, and its content is nowhere visible. **No
   verdict below is given for that column**, on any connector — it cannot be
   measured from the image, which is the only place rule 42 permits it to be
   measured from. See *Needs a ruling* item 7.

---

## 01 · Microsoft 365 — `email_microsoft`

Frames **CFG-01** (p021 foot → p022) and **VIEW-01** (p022 foot → p023).
Kicker drawn: `EMAIL · WE SEND`. Summary drawn: *Send bills from your own
mailbox.* Badge drawn on the configure frame: `PROPOSED FORM`.

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Sign in with Microsoft | Button; the sentence above it reads *You will be sent to Microsoft and brought back here. We never see or store your password.* | — (it is the act, not a value) | Connection details · accent rule on top edge | `Field(name="sign_in", label="Sign in with Microsoft", kind="redirect")` | MATCHES |
| 2 | Send bills from | Single-line text, help beneath: *The address bills are sent from.* | Yes (red asterisk) | Connection details · accent | `Field(name="send_from", label="Send bills from", kind="email")` | MATCHES |
| 3 | Where it runs | Two segments, `Production` · `Sandbox` | not marked | Connection details · accent | `integration_connection.environment` | MATCHES (shared, not a manifest field) |

No `Token address` and no `Scope` are drawn on this form. The third panel is
headed **Token** and contains only prose — *Signing in above gives us the token.
We generate it once and it refreshes itself.* / *One token. All 1 API use it.*
That agrees with the manifest's `mode="token_exchange", placement="redirect"`.

Catalogue cross-check (p161): **2 fields · 1 ops**. My count from the image is
**2 connector fields** (rows 1–2; row 3 is the shared environment control) and
**1 operation**. Agrees.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction (we collect / we send) | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Send messages | We send | none | `api.vendor.example` | Ours (we start it) | `Operation(name="send_message", label="Send messages", direction="out", initiative="us", trigger="dispatcher")` | MATCHES on name, direction and initiative. **DIFFERS on the endpoint** — see below. |

The drawn `WHEN` for this row is *When queued*, which is `trigger="dispatcher"`.
The drawn `RATE LIMIT` cell carries a figure; **the manifest has nowhere to put
one** (`Operation` declares no rate limit). The drawn endpoint
`api.vendor.example` sits under the operation name, and the panel's footnote
reads *All 1 use the address above* — **but no address is drawn above it on this
form.** Both of those are ruling items 2 and 3.

**Verdict line: NO.** Two of the three things the drawing shows for this
connector's one operation — the address it calls and the limit it runs under —
have no home in a manifest and no source on the form, so the API panel cannot be
filled from the drawing alone. Everything else on the form is buildable today.

---

## 02 · Google Workspace — `email_google`

Frames **CFG-02** (p023 foot → p024) and **VIEW-02** (p025 → p026).
Kicker drawn: `EMAIL · WE SEND`. Summary drawn: *Send bills from your own
mailbox.* Badge: `PROPOSED FORM`.

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Sign in with Google | Button; sentence above reads *You will be sent to Google and brought back here. We never see or store your password.* | — | Connection details · accent | `Field(name="sign_in", label="Sign in with Google", kind="redirect")` | MATCHES |
| 2 | Send bills from | Single-line text, help *The address bills are sent from.* | Yes | Connection details · accent | `Field(name="send_from", label="Send bills from", kind="email")` | MATCHES |
| 3 | Where it runs | `Production` · `Sandbox` | not marked | Connection details · accent | `integration_connection.environment` | MATCHES (shared) |

Catalogue cross-check: **2 fields · 1 ops**. Agrees.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Send messages | We send | none | `api.vendor.example` | Ours | `send_message`, label *Send messages*, out / us / dispatcher | MATCHES; endpoint and rate limit DIFFER as for 01 |

**Verdict line: NO**, for exactly the same two reasons as 01 — the endpoint and
the rate limit. The form itself is buildable today, field for field.

---

## 03 · Custom SMTP — `email_smtp`

Frames **CFG-03** (p026 foot → p027) and **VIEW-03** (p027 foot → p028).
Kicker drawn: `EMAIL · WE SEND`. Summary drawn: *Any mail server with a host and
a password.* Badge: `PROPOSED FORM`.

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Mail server | Single-line text (drawn left of Port, same row) | Yes | Connection details · accent | `Field(name="host", label="Mail server", kind="host")` | MATCHES |
| 2 | Port | Single-line text (drawn right of Mail server) | Yes | Connection details · accent | `Field(name="port", label="Port", kind="port")` | MATCHES |
| 3 | Username | Single-line text (drawn left of Password) | Yes | Connection details · accent | `Field(name="username", label="Username", kind="text")` | MATCHES |
| 4 | Password | Masked; placeholder *Typed once, never shown again*; help *Stored encrypted. Never shown again.* | Yes | Connection details · accent | `Field(name="password", label="Password", kind="secret")` | MATCHES |
| 5 | Send bills from | Single-line text, help *The address bills are sent from.* | Yes | Connection details · accent | `Field(name="send_from", label="Send bills from", kind="email")` | MATCHES |
| 6 | Where it runs | `Production` · `Sandbox` | not marked | Connection details · accent | `integration_connection.environment` | MATCHES (shared) |

Catalogue cross-check: **5 fields · 1 ops**. Agrees exactly — rows 1–5.

The drawing pairs fields side by side (1 with 2, 3 with 4). **B14 rule 38 says
the UI rules decide how a form is built, not the drawing**, so that pairing is
the shared-shape lane's to settle and is recorded here only as measured.

The third panel on this form is headed **Sign-in on this connector**, not
*Token*, and reads *No token here. This one signs in with the details above, on
every call.* That is the only one of my ten whose third panel carries that
heading, and it agrees with `auth=Auth(mode="we_hold_theirs",
placement="native")`.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Send messages | We send | none | `api.vendor.example` | Ours | `send_message`, label *Send messages*, out / us / dispatcher, `transport="smtp"` | MATCHES on name and direction. **DIFFERS on the endpoint**, and worse than on 01–02: this connector already collects its address in field 1, and the drawing shows a different, `api.`-prefixed one instead. |

`VIEW-03` draws a **Key we hold** panel holding one masked value and a **Replace
key** action, over a form that collects a username *and* a password. One masked
value is right — the manifest has exactly one field of kind `secret` — but the
panel is headed *key* where the form says *password*. Recorded as a wording
difference for the shared-shape lane, not a ruling.

**Verdict line: NO.** The five fields are buildable today, exactly as drawn. The
one operation is not, because the drawing gives it an address that contradicts
the address the same screen collects, and gives it a rate limit with nowhere to
live.

---

## 04 · Bulk email service — `email_bulk`

Frames **CFG-04** (p028 foot → p029 → p030) and **VIEW-04** (p030 → p031).
Kicker drawn: `EMAIL · WE SEND · THEY SEND` — **two directions on one
connector**, which is `BR-INT-028` drawn. Badge on the configure frame: `NEEDS A
VENDOR NAME`; on the view frame: `PROPOSED`. A note under the title reads *Still
generic. You have not named a vendor for this one — it keeps a category name
until you do.*

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | API key | Masked; placeholder *Typed once, never shown again*; help *Stored encrypted. Never shown again. This key is used by all 2 APIs.* | Yes | Connection details · accent | `Field(name="api_key", label="API key", kind="secret")` | MATCHES |
| 2 | Sending domain | Single-line text (drawn right of API key) | Yes | Connection details · accent | `Field(name="sending_domain", label="Sending domain", kind="host")` | MATCHES |
| 3 | Send bills from | Single-line text, help *The address bills are sent from.* | Yes | Connection details · accent | `Field(name="send_from", label="Send bills from", kind="email")` | MATCHES |
| 4 | Where it runs | `Production` · `Sandbox` | not marked | Connection details · accent | `integration_connection.environment` | MATCHES (shared) |
| 5 | Token address | Single-line text | Yes (red asterisk) | **Token** · plain | nothing — the manifest declares no `TokenExchange` at all | **NEEDS A RULING** (item 1) |
| 6 | Scope | Single-line text; placeholder *Leave blank for everything the key allows* | No | **Token** · plain | nothing | **NEEDS A RULING** (item 1) |
| 7 | Generate token | Button; sentence above reads *No token yet — save this connector, then generate one.* | — | **Token** · plain | nothing | **NEEDS A RULING** (item 1) |

Catalogue cross-check: **3 fields · 2 ops**. The catalogue counts rows 1–3 and
counts rows 5–7 as not-fields. **The image shows rows 5 and 6 as labelled inputs
on the configure form, one of them required.** Reported, image wins: this form
draws **five things a clerk types or presses beyond the environment control**,
and the catalogue's "3" describes only the `Connection details` panel.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Send messages | We send | none | `api.vendor.example` | Ours | `send_message`, out / us / dispatcher | MATCHES; endpoint and rate limit DIFFER |
| 2 | Delivery feedback | They send | none | `api.vendor.example` | **Theirs** (drawn `WHEN` = *They call us*) | `receive_feedback`, label *Delivery feedback*, in / them / webhook, `respond_after="persist"` | MATCHES |

The panel footnote reads *Outward the limit is what they allow us; inward it is
what we allow them* — so the rate limit is **two different facts in one column**
depending on direction. Nothing in the code holds either.

`VIEW-04` draws a **Token we hold** panel — one masked value, a generated date,
an expiry date, and an `In use` chip — and its footer action is **Regenerate
token** (not *Replace key*).

**Verdict line: NO.** Both operations match by name and direction, but the whole
`Token` panel — a required address, a scope and a Generate action — describes a
token exchange this connector's manifest does not have, and no ruling has been
put on which of the two is right.

---

## 05 · Twilio — `sms_twilio`

Frames **CFG-05** (p031 foot → p032) and **VIEW-05** (p032 foot → p033 → p034).
Kicker drawn: `MESSAGING · WE SEND · THEY SEND`. Badge: `PROPOSED FORM` /
`PROPOSED`. A note under the title reads *Coming soon · v1.1 — not built yet.*

**The title drawn is `Twilio`. The manifest's `display_name` is `Text
messages`.** The p161 catalogue marks this row **Ships today**, and that page
defines *ships today* as *a manifest exists at 2.261.3 **and its name does not
change***. The name does change. Reported as a catalogue disagreement; the image
wins, and the rename is real work.

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Account SID | Single-line text (drawn left of Auth token) | Yes | Connection details · accent | `Field(name="account_sid", label="Account SID", kind="text")` | MATCHES |
| 2 | Auth token | Masked; placeholder *Typed once, never shown again*; help *Stored encrypted. Never shown again. This key is used by all 2 APIs.* | Yes | Connection details · accent | `Field(name="auth_token", label="Auth token", kind="secret")` | MATCHES |
| 3 | Send from number | Single-line text | Yes | Connection details · accent | `Field(name="from_number", label="Send from number", kind="text")` | MATCHES |
| 4 | Where it runs | `Production` · `Sandbox` | not marked | Connection details · accent | `integration_connection.environment` | MATCHES (shared) |
| 5 | Token address | Single-line text | Yes | **Token** · plain | nothing | **NEEDS A RULING** (item 1) |
| 6 | Scope | Single-line text; placeholder *Leave blank for everything the key allows* | No | **Token** · plain | nothing | **NEEDS A RULING** (item 1) |
| 7 | Generate token | Button | — | **Token** · plain | nothing | **NEEDS A RULING** (item 1) |

Catalogue cross-check: **3 fields · 2 ops**. Same arithmetic as 04 — the
catalogue counts the `Connection details` panel and not the `Token` panel.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Send texts | We send | none | `api.twilio.example` | Ours | `send_message`, label *Send texts*, out / us / dispatcher | MATCHES on name and direction. Endpoint DIFFERS (see below) |
| 2 | Delivery status | They send | none | `api.twilio.example` | **Theirs** (drawn `WHEN` = *They call us*) | `receive_status`, label *Delivery status*, in / them / webhook, `respond_after="persist"` | MATCHES |

**This is the only one of my ten whose drawn endpoint names the real vendor**
(`api.twilio.example`) rather than `api.vendor.example`. Under B14 rule 37 the
value is an illustration either way; it is recorded because it is the one place
the drawing shows the endpoint is meant to be vendor-specific rather than a
placeholder, which bears on ruling item 3.

`VIEW-05` draws a **Token we hold** panel and a **Regenerate token** footer
action, the same as 04.

Operation 2 is inbound and the registry already notes, in `Auth.header`, that a
provider-called door needs a named header and that `sms_twilio` declares none.
That is already written down in the code and is not re-raised here.

**Verdict line: NO.** Three fields, two operations and both directions match. The
`Token` panel does not, the display name has to change, and the endpoint and rate
limit have no home.

---

## 06 · Neptune 360 — `meters_neptune360`

Frames **CFG-06** (p034 → p035) and **VIEW-06** (p035 foot → p036 → p037).
Kicker drawn: `METERS · WE COLLECT`. Summary drawn: *Collect readings and keep
the meter list in step.* Badge: `RENAMED`. A note under the title reads
*Renamed. Ships today under a generic name. The connector, its fields and its
operations do not change.*

**The title drawn is `Neptune 360`. The manifest's `display_name` is `Water
meter cloud`.** The note above says so in as many words, and p162 confirms
*Renamed only. Fields, operations and adapters are untouched — the safest two in
the list.*

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Site ID | Single-line text (drawn left of API key) | Yes | Connection details · accent | `Field(name="site_id", label="Site ID", kind="text")` | MATCHES |
| 2 | API key | Masked; placeholder *Typed once, never shown again*; help *Stored encrypted. Never shown again. This key is used by all 16 APIs.* | Yes | Connection details · accent | `Field(name="api_key", label="API key", kind="secret")` | MATCHES |
| 3 | Where it runs | `Production` · `Sandbox` | not marked | Connection details · accent | `integration_connection.environment` | MATCHES (shared) |
| 4 | Time | Single-line text drawn as a clock time; help *Your time zone. The only part you choose.* | not marked | **When it runs** · plain | nothing on the manifest; `integration_connection.next_run_at` and `cadence` are the nearest tables | **NEEDS A RULING** (item 5) |

Catalogue cross-check: **2 fields · 16 ops**. Agrees on rows 1–2. Row 4 is drawn
and is counted by nobody.

**This form draws no `Token` panel at all**, and `VIEW-06` draws **Key we hold**
with the sentence *No token on this one*. The manifest declares
`mode="token_exchange", placement="bearer"` with a `TokenExchange` whose token
lives 600 seconds. **The drawing and the manifest contradict each other about
whether this connector exchanges a token.** Ruling item 1.

### Table B — operations on the view screen

The panel header reads **16 APIs on this connector**. **Eight rows are drawn by
name; the ninth line of the table reads `…8 more`.** All eight drawn rows carry
`We collect` · `Nightly` · a rate-limit figure.

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Meter readings | We collect | none | `api.neptune360.example` | Ours | `collect_readings`, in / us / scheduled | MATCHES |
| 2 | Readings by route | We collect | none | `api.neptune360.example` | Ours | `collect_readings_by_route` | MATCHES |
| 3 | Billing export | We collect | none | `api.neptune360.example` | Ours | `collect_billing_export` | MATCHES |
| 4 | Hourly interval data | We collect | none | `api.neptune360.example` | Ours | `collect_interval_data` | MATCHES — and see the note below |
| 5 | Meter alerts | We collect | none | `api.neptune360.example` | Ours | `collect_alerts` | MATCHES |
| 6 | Register replacements | We collect | none | `api.neptune360.example` | Ours | `collect_register_replacements` | MATCHES |
| 7 | Meter inventory | We collect | none | `api.neptune360.example` | Ours | `collect_meter_inventory` | MATCHES |
| 8 | Endpoint inventory | We collect | none | `api.neptune360.example` | Ours | `collect_endpoint_inventory` | MATCHES |
| 9–16 | **not drawn** — the table's last line reads `…8 more` | — | — | — | — | `collect_service_points`, `collect_accounts`, `collect_routes`, `collect_usage_summary`, `request_billing_export`, `push_account_meter_link`, `push_route_assignment`, `push_service_point` | **EXTRA** — we hold eight operations the drawing does not draw |

The eight drawn names match the manifest's first eight labels **exactly and in
the manifest's own order**, which is strong evidence the drawing was made from
this manifest and elided the tail rather than disagreeing with it.

The `When it runs` panel reads *13 of 16 run on a clock.* The manifest declares
`trigger="scheduled"` on thirteen operations and `trigger="manual"` on the three
`push_*` operations. **That arithmetic agrees exactly**, and it is the second
piece of evidence that the eight undrawn rows are the eight in the manifest.

⚠ **Row 4 is drawn as an ordinary operation and it is switched off for every
tenant.** `OQ-INT-1484` is CLOSED, option (a), PO: *"not yet; We will not bring
hourly internal data in this product"*, and the manifest's own docstring records
that `collect_interval_data` **stays declared and is never built**. The drawing
gives it a nightly clock and a rate limit like the other seven. A lane reading
the picture alone would build a nightly collection the Product Owner has already
refused. This is not a ruling item — it is already ruled — it is a note that the
drawing does not show the ruling.

**Verdict line: NO.** The two fields match and eight of sixteen operations match
by name, direction and schedule. It cannot be built from the drawing alone
because eight operation names are simply not on the page, because the drawing
denies this connector a token the code gives it, and because `Time` in the
`When it runs` panel is a control nothing in the code holds.

---

## 07 · Badger BEACON — `meters_badger`

Frames **CFG-07** (p037 foot → p038) and **VIEW-07** (p038 foot → p039).
Kicker drawn: `METERS · WE COLLECT`. Summary drawn: *Collect readings from the
BEACON head-end.* Badge: `NEW CONNECTOR` / `PROPOSED`. A note under the title
reads *New connector. Nothing is built for this vendor today — the fields below
are the shape it will take.*

**There is no `manifests/meters_badger.py`. The string `meters_badger` appears
nowhere in the repository outside the front-end test and hold files.** Every row
below is therefore MISSING.

> `VIEW-07`'s frame caption is drawn on p038 and is readable in the image, but
> the page's text layer is split character by character, so a text search for
> `VIEW-07` returns nothing. A lane that looked for this frame by grepping the
> PDF would conclude it does not exist. It does. Rule 42 again.

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Service address | Single-line text (drawn left of Site / account ID) | Yes | Connection details · accent | nothing | **MISSING** |
| 2 | Site / account ID | Single-line text (drawn right of Service address) | Yes | Connection details · accent | nothing | **MISSING** |
| 3 | API key | Masked; placeholder *Typed once, never shown again*; help *Stored encrypted. Never shown again. This key is used by all 4 APIs.* | Yes | Connection details · accent | nothing | **MISSING** |
| 4 | Where it runs | `Production` · `Sandbox` | not marked | Connection details · accent | `integration_connection.environment` | MATCHES (shared) |
| 5 | Time | Clock time; help *Your time zone. The only part you choose.* | not marked | **When it runs** · plain | nothing | **NEEDS A RULING** (item 5) |

Catalogue cross-check: **3 fields · 4 ops**. Agrees on rows 1–3.

**Field 1 is the one thing that makes this connector's API panel legible.** The
panel footnote reads *All 4 use the address above*, and here — unlike 01 to 05 —
there genuinely is an address above. See ruling item 3.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Collect readings | We collect | **PROPOSED** (a chip drawn beside the endpoint) | `api.vendor.example` | Ours (drawn `WHEN` = *Nightly*) | nothing | **MISSING** |
| 2 | Collect meter inventory | We collect | **PROPOSED** | `api.vendor.example` | Ours (*Nightly*) | nothing | **MISSING** |
| 3 | Collect alerts | We collect | **PROPOSED** | `api.vendor.example` | Ours (*Nightly*) | nothing | **MISSING** |
| 4 | Request billing export | We collect | **PROPOSED** | `api.vendor.example` | Ours (drawn `WHEN` = *On demand*) | nothing | **MISSING** |

`When it runs` reads *3 of 4 run on a clock.* Three `Nightly` plus one `On
demand` — the arithmetic is internally consistent.

⚠ **Row 4 is drawn `We collect` and named `Request billing export`.** Neptune's
manifest holds the same thing as **two** operations — a `request_billing_export`
that is `direction="out"` and *changes the partner's world*
(`mutates_partner_state=True`, because it closes billing routes on their side),
and a separate `collect_billing_export` that is `direction="in"`. The drawing
gives Badger one row and calls it inward. Ruling item 4.

⚠ `VIEW-07`'s `Key we hold` panel carries the sentence *No token on this one — a
file goes to a folder or a download, and neither carries a token.* **This
connector is neither a folder nor a download** — every one of its four
operations is drawn against an `api.` address. The same sentence appears on
VIEW-06, VIEW-08 and VIEW-09. Recorded as a copy defect for the shared-shape
lane, since the same sentence is drawn on four screens and is wrong on all four.

**Verdict line: NO.** Nothing at all exists for this vendor. Three fields and
four operations are drawn and must be written, and before they can be, ruling
items 1, 3, 4 and 5 have to be settled.

---

## 08 · Itron — `meters_itron`

Frames **CFG-08** (p039 foot → p040 → p041) and **VIEW-08** (p041 → p042).
Kicker drawn: `METERS · WE COLLECT`. Summary drawn: *Collect readings from the
Itron head-end.* Badge: `NEW · SPLIT OUT` / `PROPOSED`. A note under the title
reads *New · split out. Itron and Sensus share one card today. This gives each
its own connector.*

**There is no `manifests/meters_itron.py`.** `manifests/meters_mdm.py` is the
one card the note refers to; p162 records that it *splits into two connectors.
One manifest becomes two, and a tenant who connected it has to be migrated to
whichever vendor they actually use — the row cannot say which.*

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Service address | Single-line text (drawn left of Site / account ID) | Yes | Connection details · accent | nothing under this key | **MISSING** |
| 2 | Site / account ID | Single-line text | Yes | Connection details · accent | nothing under this key | **MISSING** |
| 3 | API key | Masked; help *Stored encrypted. Never shown again. This key is used by all 4 APIs.* | Yes | Connection details · accent | nothing under this key | **MISSING** |
| 4 | Where it runs | `Production` · `Sandbox` | not marked | Connection details · accent | `integration_connection.environment` | MATCHES (shared) |
| 5 | Time | Clock time; help *Your time zone. The only part you choose.* | not marked | **When it runs** · plain | nothing | **NEEDS A RULING** (item 5) |

Catalogue cross-check: **3 fields · 4 ops**. Agrees on rows 1–3.

**The three drawn fields are byte-for-byte the same three drawn on CFG-07 and
CFG-09** — same labels, same order, same side-by-side pairing, same help
sentence.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Collect readings | We collect | **PROPOSED** | `api.vendor.example` | Ours (*Nightly*) | nothing under this key | **MISSING** |
| 2 | Collect meter inventory | We collect | **PROPOSED** | `api.vendor.example` | Ours (*Nightly*) | nothing under this key | **MISSING** |
| 3 | Collect alerts | We collect | **PROPOSED** | `api.vendor.example` | Ours (*Nightly*) | nothing under this key | **MISSING** |
| 4 | Request billing export | We collect | **PROPOSED** | `api.vendor.example` | Ours (*On demand*) | nothing under this key | **MISSING** |

`When it runs` reads *3 of 4 run on a clock.* Consistent.

**Verdict line: NO.** Nothing exists under `meters_itron`. Beyond the four
MISSING operations and three MISSING fields, this connector carries a migration
the drawing cannot settle: a tenant connected to `meters_mdm` today has to be
moved to Itron or to Sensus, and no screen in these frames shows a person being
asked which.

---

## 09 · Sensus — `meters_sensus`

Frames **CFG-09** (p042 foot → p043 → p044) and **VIEW-09** (p044 → p045).
Kicker drawn: `METERS · WE COLLECT`. Summary drawn: *Collect readings from the
Sensus head-end.* Badge: `NEW · SPLIT OUT` / `PROPOSED`. Same note as 08.

**There is no `manifests/meters_sensus.py`.**

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Service address | Single-line text (drawn left of Site / account ID) | Yes | Connection details · accent | nothing under this key | **MISSING** |
| 2 | Site / account ID | Single-line text | Yes | Connection details · accent | nothing under this key | **MISSING** |
| 3 | API key | Masked; help *Stored encrypted. Never shown again. This key is used by all 4 APIs.* | Yes | Connection details · accent | nothing under this key | **MISSING** |
| 4 | Where it runs | `Production` · `Sandbox` | not marked | Connection details · accent | `integration_connection.environment` | MATCHES (shared) |
| 5 | Time | Clock time; help *Your time zone. The only part you choose.* | not marked | **When it runs** · plain | nothing | **NEEDS A RULING** (item 5) |

Catalogue cross-check: **3 fields · 4 ops**. Agrees on rows 1–3.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Collect readings | We collect | **PROPOSED** | `api.vendor.example` | Ours (*Nightly*) | nothing under this key | **MISSING** |
| 2 | Collect meter inventory | We collect | **PROPOSED** | `api.vendor.example` | Ours (*Nightly*) | nothing under this key | **MISSING** |
| 3 | Collect alerts | We collect | **PROPOSED** | `api.vendor.example` | Ours (*Nightly*) | nothing under this key | **MISSING** |
| 4 | Request billing export | We collect | **PROPOSED** | `api.vendor.example` | Ours (*On demand*) | nothing under this key | **MISSING** |

`When it runs` reads *3 of 4 run on a clock.* Consistent.

**Verdict line: NO**, and for the same reasons as 08 — nothing exists, and the
`meters_mdm` migration has no screen.

⚠ **07, 08 and 09 are drawn identically, field for field and operation for
operation.** The only thing that differs between the three frames is the title,
the one-line summary and the badge. Badger BEACON, Itron and Sensus are three
head-ends with, in the drawing, one shape. `BR-INT-037` says that is exactly
right — three manifests, one adapter — and it is recorded here so that nobody
building the second one goes looking for a difference that is not drawn.

---

## 10 · InvoiceCloud — `pay_invoicecloud`

Frames **CFG-10** (p045 foot → p046 → p047) and **VIEW-10** (p047 → p048).
Kicker drawn: `PAYMENTS · WE COLLECT · WE SEND` — **two directions, both ours**,
which is different again from 04 and 05 (*we send · they send*). Summary drawn:
*Take card and bank payments through InvoiceCloud.* Badge: `NEW CONNECTOR` /
`PROPOSED`. Note: *New connector. Nothing is built for this vendor today — the
fields below are the shape it will take.*

**There is no `manifests/pay_invoicecloud.py`.** `manifests/payments_card.py`
is the generic card processor p162 says is *replaced by five named processors*.

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Merchant ID | Single-line text (drawn left of Merchant secret) | Yes | Connection details · accent | nothing | **MISSING** |
| 2 | Merchant secret | Masked; placeholder *Typed once, never shown again*; help *Stored encrypted. Never shown again. This key is used by all 4 APIs.* | Yes | Connection details · accent | nothing | **MISSING** |
| 3 | Client ID | Single-line text (drawn left of Card page) | Yes | Connection details · accent | nothing | **MISSING** |
| 4 | Card page | **Two segments**, `hosted by them` · `embedded` | Yes | Connection details · accent | nothing | **MISSING** — expressible as `Field(kind="select", options=…)`, which the registry already allows |
| 5 | Where it runs | `Production` · `Sandbox` | not marked | Connection details · accent | `integration_connection.environment` | MATCHES (shared) |
| 6 | Token address | Single-line text | Yes | **Token** · plain | nothing | **NEEDS A RULING** (item 1) |
| 7 | Scope | Single-line text; placeholder *Leave blank for everything the key allows* | No | **Token** · plain | nothing | **NEEDS A RULING** (item 1) |
| 8 | Generate token | Button | — | **Token** · plain | nothing | **NEEDS A RULING** (item 1) |
| 9 | Time | Clock time; help *Your time zone. The only part you choose.* | not marked | **When it runs** · plain | nothing | **NEEDS A RULING** (item 5) |

Catalogue cross-check: **4 fields · 4 ops**. Agrees on rows 1–4.

**Row 4 is the only drawn field on any of my ten connectors that changes what
the product DOES rather than how it reaches a vendor.** *Hosted by them* and
*embedded* are two different journeys for a customer paying a bill, and the
drawing makes it a two-segment control with no consequence line. Ruling item 6.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Charge a card | **We send** | **PROPOSED** | `api.vendor.example` | Ours (drawn `WHEN` = *On demand*) | nothing | **MISSING** |
| 2 | Hosted card page | **We send** | **PROPOSED** | `api.vendor.example` | Ours (drawn `WHEN` = **While you wait**) | nothing | **MISSING** |
| 3 | Settlement report | **We collect** | **PROPOSED** | `api.vendor.example` | Ours (drawn `WHEN` = *Nightly*) | nothing | **MISSING** |
| 4 | Refund a payment | **We send** | **PROPOSED** | `api.vendor.example` | Ours (drawn `WHEN` = *On demand*) | nothing | **MISSING** |

`When it runs` reads *1 of 4 run on a clock.* One `Nightly` against three that
are not — consistent.

⚠ **Row 2 is the only operation across all ten connectors drawn `While you
wait`.** In the registry that is `trigger="inline"`, and the `Operation`
dataclass **requires** `latency_budget_ms` on a server-executed inline operation
we initiate, and **refuses it** on a browser-executed one. The drawing declares
neither a budget nor who runs it. Ruling item 6 covers this with the card-page
choice, because *hosted by them* and *embedded* is plausibly the same question:
whose browser holds the socket.

⚠ **Rows 1 and 4 are money.** *Charge a card* and *Refund a payment* both move
money at a customer's expense, and neither is drawn with an idempotency story,
a consequence line, or the `mutates_partner_state` flag Neptune's export
carries for merely closing a route. Ruling item 4 covers this together with
Badger's export, because both are the same unanswered question: which of these
operations may not safely run twice.

⚠ **p162 names this connector as the reason to change the model first.**
`DEF-INT-4118`, in the blueprint's own words: *the model cannot hold
InvoiceCloud… A manifest holds a single Auth and the database enforces one
active credential per connection; a processor that holds our key and has an
operation we start does not fit.* **This is the first thing to fix, not the
names.** Recorded, not acted on.

**Verdict line: NO**, and this is the furthest from buildable of my ten. Four
fields and four operations are drawn and none exists; the card-page choice
changes a customer journey and has no ruling; one operation runs while a person
waits and declares no budget; two operations move money and declare no
idempotency; and the blueprint itself says the data model refuses this connector
in its present shape.

---

## Totals

| | Count |
|---|---|
| Connectors measured | **10** |
| Connectors whose form can be built from the drawing alone today | **0** |
| Manifests that exist | **6** (01 · 02 · 03 · 04 · 05 · 06) |
| Manifests that do not exist | **4** (07 `meters_badger` · 08 `meters_itron` · 09 `meters_sensus` · 10 `pay_invoicecloud`) |
| **MISSING fields** (drawn in `Connection details`, we have nothing) | **13** — 3 + 3 + 3 + 4 across connectors 07–10 |
| **MISSING operations** (drawn, we have nothing) | **16** — 4 each across connectors 07–10 |
| Fields drawn outside `Connection details` with no home in any manifest | **6** `Token address` / `Scope` on 04, 05 and 10 — plus **4** `Time` controls on 06, 07, 08, 09. Counted separately because the blueprint's own catalogue does not count them. Adding them makes it **23 fields**. |
| EXTRA operations (we hold them, the drawing does not draw them) | **8** — Neptune 360's `…8 more` |
| Operations drawn with a rate limit the code cannot hold | **31** — every drawn operation on all ten (1+1+1+2+2+8+4+4+4+4) |
| Operations drawn with an endpoint the code cannot hold | **31** — every drawn operation on all ten |
| Connectors whose display name must change | **2** — Twilio (from *Text messages*) and Neptune 360 (from *Water meter cloud*) |

### Where the blueprint's own catalogue disagrees with what I measured

The p161 table was used only as a cross-check. Three disagreements, and in each
one **the image wins**:

1. **`sms_twilio` is marked `Ships today`**, which that page defines as *a
   manifest exists at 2.261.3 and its name does not change*. The manifest
   exists; **the name does change** — the drawing titles the screen `Twilio`
   and the manifest says `Text messages`. It belongs with `Renamed`.
2. **`email_bulk` (3 fields), `sms_twilio` (3 fields) and `pay_invoicecloud`
   (4 fields)** each draw **two further labelled inputs** in the `Token`
   panel, one of them required, which the catalogue's count does not include.
3. **`meters_neptune360` is marked `2 fields · 16 ops`**, and the drawing shows
   **eight** operation rows and the line `…8 more`. The count is right about
   what exists; it is not right about what the page shows a builder.

---

## Needs a ruling

Each item is written the way a ruling is asked for — plain sentences, a real
figure, and no identifiers to go and look up.

**1 · Does a bulk email service, a text-message service and a card processor
hand us a password we swap for a pass, or just a password?**
The drawing gives three of these ten connectors a panel called *Token*, with a
box for an address, a box for a scope, and a *Generate token* button — and it
gives the water-meter connector no such panel at all. Our code says the exact
opposite on both counts: the three have no such thing, and the water-meter one
does, with a pass that lasts ten minutes and renews itself. So on four of ten
connectors the picture and the code disagree about whether a clerk sees three
more boxes on the set-up screen. **The question: when a utility connects a bulk
email service, does the clerk type one secret, or one secret plus an address and
a scope — three boxes instead of one?**

**2 · Every operation is drawn with a speed limit and we have nowhere to keep
one.**
All thirty-one operations drawn across these ten connectors carry a limit
beside them — the picture shows things like *120 a minute* for sending mail and
*10 a minute* for collecting meter readings. There is no place in our connector
records to write that number down, so today it would be a figure on a screen
that nothing enforces and nothing can change. The picture also says the limit
means two different things: going out it is what the vendor allows us, coming in
it is what we allow them. **The question: is the speed limit a real setting we
keep per operation — so that a utility whose vendor allows 300 a minute instead
of 120 can have that — or is it decoration we should not draw?**

**3 · Four of these ten connectors are drawn calling an address the set-up
screen never asks for.**
The meter connectors and the card processor each ask the clerk for a *Service
address*, and their screens then say *All 4 use the address above* — which
reads correctly. The four email connectors and the text-message one say *All 1
use the address above* and *All 2 use the address above*, but **there is no
address above on those screens**. The mail-server connector is the sharpest
case: it asks for a mail server on line one, and then draws its one operation
against a different, made-up web address. **The question: for sending mail from
a Microsoft or Google mailbox, is the address ours to fix once for everybody, or
is it a box the clerk has to fill — and if it is ours, should that sentence be
on the screen at all?**

**4 · Three operations move something that cannot be undone, and none of them
is drawn as such.**
Badger, Itron and Sensus each draw one operation called *Request billing
export*, drawn as though it only reads. On the water-meter connector we already
have that same thing split in two, because asking for the export **closes
billing routes on the vendor's side** and running it twice would close them
twice. Separately, InvoiceCloud draws *Charge a card* and *Refund a payment* —
both of which move real money — with nothing to say what happens if the button
is pressed twice. **The question: if a clerk presses *Request billing export*
twice in one minute, should the second press be refused, or should it run again?
And the same question for *Refund a payment* on a $142.50 refund.**

**5 · One box on four screens decides what time the night's work starts, and it
is drawn without an owner.**
The meter connectors and the card processor each draw a box under *When it runs*
holding a clock time, with the words *Your time zone. The only part you choose.*
Our connector records hold *nightly*, *hourly* or *manual* and a next-run
moment, but no clerk-set hour. The same screens also say, in red, that nothing
acts on the time today. **The question: if a utility sets that box to 03:00
because their meter vendor is slow at 01:00, does the night's collection then
start at 03:00 — or is the box there to show a fact the utility cannot change?**

**6 · InvoiceCloud draws a two-way choice that changes what a customer paying a
bill actually sees, and it is drawn as a plain toggle.**
The set-up screen offers *hosted by them* or *embedded*. One of those sends a
customer away to the processor's own payment page; the other keeps them on our
page. The same connector draws one operation marked *While you wait*, which is
the only operation across all ten that runs with a person watching, and our code
requires such an operation to declare how long a person may be kept waiting —
the drawing declares nothing. **The question: does the utility get to pick
between sending the customer to InvoiceCloud's page and keeping them on ours,
and if they pick *embedded*, how many seconds may the customer sit on a spinner
before we tell them to try again — five, or fifteen?**

**7 · The drawing runs off the edge of the page on every one of these twenty
frames, and one whole column is unreadable.**
On every configure form the operations table has a column after the speed limit
that is cut off by the page edge; only its first letter or two survives. On every
view screen the last column is cut the same way. Nobody can build that column
from this document, because nobody can see it. **The question: is there a
further column after the speed limit on the set-up screen — a Test button, say —
or does the table end there and the page is simply drawn too wide?**

---

<!-- Measured 2026-09-16 · connectors 01–10 · nothing built, nothing fixed,
     nothing decided. Seven questions above go to the Product Owner. -->
