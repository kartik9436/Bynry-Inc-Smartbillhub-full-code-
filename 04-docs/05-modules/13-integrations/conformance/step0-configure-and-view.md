# Connectors, step 1 — the CONFIGURE screen and the VIEW screen, measured

**They are two screens, not fifty-six.** `CFG-01…28` and `VIEW-01…28` are one set-up form and
one connection page, rendered per vendor from that vendor's manifest. That is `BR-INT-037` in
the PO's own words — *"every time such integration comes we dont want to change our
integration framework"* — so the only question worth answering is **which drawn elements are
SCREEN CODE and which are MANIFEST DATA**, and that is what the last column of each table
below is for.

| | |
|---|---|
| Drawing | `05-prototype/05 Integration Blueprint.pdf` — 163 pages, **on `origin/claude/confirm-understanding-3ktufc`, not on our branch**. sha256 `c02e9518…`, 3,160,169 bytes |
| Frames read | `CFG-01` p21–22 · `VIEW-01` p22–23 · `CFG-03` p26 · `VIEW-03` p27 · `CFG-05` p31 · `VIEW-05` p32 · `CFG-06` p34–35 · `VIEW-06` p35–36 · `CFG-10` p45–46 · `VIEW-10` p47–48 · `CFG-23` p79–80 · `VIEW-23` p81. Shared law from p16–17, p154–155, p162 |
| Product | `07-frontend/src/features/integrations/ConnectModal.tsx` (871 lines) · `ConnectionDetailPage.tsx` (1,206 lines) · `06-backend/apps/integrations/` · 18 manifests · `registry.py` (1,127 lines) |
| Measured against | the running product at `localhost:8098`, signed in as Dana Whitfield on `brazosbend`, **in a browser** (hard-won law 6) — plus the live API at `localhost:8099` and the registry loaded in the backend venv |
| Version on screen | `v2.278.0` |
| Out of scope | the grid `CON-01`, mappings `MAP-01`, keys `KEY-01`, the access log `ACC-01` — another lane. Runbooks excluded by the PO |
| Status | **NOTHING BUILT.** No `.tsx`, `.py`, manifest or migration changed by this lane |

---

## ⛔ Read this before the tables — the drawing is CLIPPED and I could not read all of it

**The right-hand column of every one of the 56 connector frames is absent from the PDF.** The
frames are drawn wider than the 1008 × 612 pt page and the export clipped them rather than
scaling them. This is in the file's own content stream, not in our renderer:

* `pdfium` text-extracts page 22's table header as **`API · ENDPOINT DIRECTION WHEN RATE LIMIT T`** —
  the **TEST** column's name truncated to one letter.
* The same page's footnote comes out as **`Signing in is all there`**, mid-word.
* `VIEW-01`'s refusal reason reads **`Retry  The site refused the`** and stops.
* Re-rendering with the area extended 420 pt to the right returns **white**. The glyphs are
  not outside the box; they are not in the file.

B14 rule 42 says a screen is built from the drawing AS AN IMAGE, and for these frames the
image stops before the last column. **So the four rows below about a TEST control, a RESULT
reason or a footer footnote are taken from the blueprint's PROSE (p154, quoted in the tables)
and not from the drawing**, and each is marked `⧗`. Filed as `DEF-INT-5487`. A lane that
builds these tables from the renders alone will build them one column short and never know.

---

## THE HEADLINE — how much of 28 × 2 is screen work

**Every figure below is counted from the two tables in this file by script, not asserted.**
Re-run it by parsing the rows: front-end verdict from column 2, per-vendor answer from column 4.

| | Configure | View | **Both** |
|---|---|---|---|
| Drawn elements measured | 34 | 31 | **65** |
| Built | 5 | 12 | **17** |
| Built differently | 5 | 9 | **14** |
| Not built | 24 | 10 | **34** |
| **The gap** (different + not built) | 29 | 19 | **48** |
| — of which the CONTENT varies per vendor, from a manifest field | 20 | 15 | **35** |
| — of which it is the same for every vendor | 9 | 4 | **13** |
| Rows whose DRAWN form I could not fully read (clipped) | 2 | 2 | **4** |

⚠ **Read the two middle rows correctly, because they are easy to misread as a cost split.**
*Varies per vendor* means the VALUE comes from a manifest field, so **28 vendors cost no extra
screen code for those 35 rows** — one loop, twenty-eight manifests. It does **not** mean the
row is free: the screen still has to be built to render it once.

**Genuinely new BACK-END work, and it is four things:** a rate-limit store (a row per
connection and per operation — nothing holds one today) · a `role` column on
`integration_credential` and the constraint edit that goes with it (`DEF-INT-4118`) · an
`operation` argument on the test door · a `scope` column on an issued key (ruled 14 Sep,
**not** phase 1). **Everything else in the 48 is screen code over data the manifest already
carries or would carry.**

**Two screens. The 28 vendors cost thirteen manifest files and no screen work at all** —
15 of the blueprint's 28 already map one-to-one onto a shipped manifest, and the other 13 come
out of three generic ones (`payments_card`, `meters_mdm`, `gl_partner`) being split into named
vendors. Measured: **18 manifests, 45 operations today**; the blueprint declares **28
connectors, 78 operation rows**.

⚠ **I could not reconcile the blueprint's own operation counts and I am not guessing.** p16
says *"47 rows across the 13 that do not ship"*; p17 says *"78 operation rows across 56
screens"*. Our 45 minus the 6 on the three generic manifests is 39, and 39 + 47 = 86, not 78.
I checked the 28-card index on p1–p2 against `REGISTRY.all()` name by name, and counted
operations per manifest in the backend venv; the three figures do not close. **The count to
build to should be taken from the manifests as written, not from either sentence.**

---

## SCREEN A — CONFIGURE (`CFG-01…28`)

Drawn as a **full page** at `/:tenant/settings/connectors/<key>/configure`. Today it is a
**modal** with no address, mounted from the card's button. That single fact accounts for five
rows below on its own.

| # | Drawn | Front end | Back end | Varies per vendor? |
|---|---|---|---|---|
| 1 | Its own **address**, so a connected card can reopen the form | **Not built** — it is a dialog. Routes are `settings/integrations/:key`, `:key/access`, `:key/mappings` in `App.tsx:563–582`; there is no `:key/configure` | n/a | **no** |
| 2 | The app frame — left nav, top bar, footer user | **Not built** on this surface (a modal sits over the grid) | n/a | **no** |
| 3 | Back link **← Connectors** | **Not built** here; the VIEW screen has one and it reads *← Integrations* | n/a | **no** |
| 4 | Kicker **EMAIL · WE SEND**, category + **every** direction word | **Not built** on the form. On the card it is `Manifest.kicker`, which returns the FIRST operation's pair only — so a two-door vendor shows one word (`registry.py:637`) | Built, one door | **yes** — `category` + the union over `operations[].direction/initiative` |
| 5 | Vendor **title**, 32 px (B14 rule 40) | **Built differently** — the modal title is `Connect · Microsoft 365`, dialog-sized | Built | **yes** — `display_name`. ⚠ five are generic today: *Water meter cloud*, *Card processor*, *Third-party GL*, *Text messages*, *City GIS* |
| 6 | One-sentence summary under the name | **Not built** in the modal (it is on the card) | Built | **yes** — `summary` |
| 7 | **Coming soon · v1.1 — not built yet.** on an undeclared vendor | **Built differently** — the card says *Not ready to connect yet*; the form says nothing | Built — `Disposition(kind, wave)`, refused at load without a wave (`registry.py:601`) | **yes** — `disposition` |
| 8 | **New connector. Nothing is built for this vendor today — the fields below are the shape it will take.** | **Not built** | Not built — no such string | **yes** — derivable from `disposition.kind` |
| 9 | Panel **Connection details**, accent top rule | **Built differently** — the fields are the form, deliberately unboxed (`DEF-INT-4228`, rule 32). The PO has since ruled *"use panel with acsent - where ever shown it that way"* | n/a | **no** |
| 10 | The **field slot** — every field this vendor needs | **Built** (`ConnectModal.tsx:643–695`), a closed vocabulary of kinds with no provider branch | **Built** — `Manifest.fields`, `FIELD_KINDS` | **yes** — `fields[]` |
| 11 | Secret help — *Typed once, never shown again* / *Stored encrypted. Never shown again.* | **Built** | Built — `SECRET_FIELD_KINDS`, `masked_hint` | **no** |
| 12 | *…**This key is used by all N APIs.*** | **Not built** | Not built | **yes** — count of `operations` |
| 13 | Fields laid out **two to a row** (`Merchant ID` / `Merchant secret`) | **Built differently** — one `160px 1fr` row per field. ⚠ B14 rule 38: where a drawing and our UI rules disagree about how a FORM IS BUILT, the UI rules win | n/a | **no** |
| 14 | **Where it runs** — Production / Sandbox | **Built** — labelled *Environment* | **Built** — `integration_connection` is unique on `(tenant, provider_key, environment)` (`BR-INT-026`) | **no** |
| 15 | Panel **API on this connector** + a count chip | **Not built** — the form shows no API list at all | Served: `operations[]` on the card | **yes** — `operations[]` |
| 16 | Column **API · ENDPOINT** — label over the host, with a `PROPOSED` chip | **Not built** | **Label built** (`label`). **Endpoint NOT SERVED** — see the credential/endpoint section | **yes** — `label`; host via `host_field` |
| 17 | Column **DIRECTION** — *We send* · *We collect* · *They send* | **Not built** | **Built** — `direction` + `initiative` on the wire | **yes** — `BR-INT-028`, per operation |
| 18 | Column **WHEN** — *Nightly* · *On demand* · *When queued* · *While you wait* | **Not built** | **Data exists, not served** — `Operation.trigger` (`manual/scheduled/dispatcher/webhook/partner/inline`) is on the manifest and absent from `_operation_row` (`selectors.py:194`) | **yes** — `trigger`, plus the connection's `cadence` for the word *Nightly* |
| 19 | Column **RATE LIMIT** — `120 / min` | **Not built** | **NOT SERVED AND NOT STORED.** No `rate_limit` on `Operation` or `Manifest`. The only rate limit in the module is `rate_limit_per_minute` in `serve.py:157` — the ceiling **we** impose on a partner calling **us**, the opposite direction | **no** — the blueprint rules it a row **per connection AND per operation**, which is a new table |
| 20 | Column **TEST**, per row ⧗ prose only (p154) | **Not built** — one *Test it now* for the whole connector | **Not servable** — `POST /integrations/{key}/test` takes `{recipient?}` and **no operation** (`api.py:218`). 25 of 45 operations declare a `test_action` that no caller can reach individually | **yes** — `test_action`, `test_needs_recipient` |
| 21 | **…8 more** when the list exceeds eight rows | **Not built** | n/a | **yes** — only Neptune (16) and the 13 new cards reach it today |
| 22 | **All N use the address above.** | **Not built** | Not servable — see 16 | **yes** |
| 23 | **These are the limits they allow us.** — and on a two-door vendor **Outward the limit is what they allow us; inward it is what we allow them.** | **Not built** | Not built | **yes** — one door or two, from `operations[].direction/initiative` |
| 24 | ⚠ *The API list and its rate limits are set when we configure this connector — neither is a clerk control.* | **Not built** | Not built | **no** |
| 25 | **No `+ Add an API` control** — removed by the 14 Sep ruling | **Correct by absence** — nothing ever offered it | n/a | **no** |
| 26 | Panel **Token** — *We generate one token for this connector and every API authenticates with it* | **Not built** | Partly — `Auth.token: TokenExchange(token_url, ttl_seconds, refresh_before_s)`, `oauth.py` | **yes** — `auth.mode == "token_exchange"` |
| 27 | **Token address** * and **Scope** fields | **Not built** | `token_url` is on the MANIFEST, not on the connection — a clerk cannot type it | **yes** |
| 28 | *No token yet — save this connector, then generate one.* + **Generate token** | **Not built** | Rotation exists (`POST /integrations/{key}/credential`); *generate* as a distinct act does not | **yes** |
| 29 | *One token. All N APIs use it. It is shown once and afterwards only regenerated.* | **Not built** | Built in fact — one active credential per connection | **yes** — N |
| 30 | Variant **Sign-in on this connector** — *No token here. This one signs in with the details above, on every call* (SMTP) | **Not built** | Fact exists — `auth.mode == "we_hold_theirs"`, `placement == "native"` | **yes** — `auth.mode`/`placement` |
| 31 | Panel **When it runs** — *N of M run on a clock* / *Nothing here runs on a clock* | **Built differently** — a clerk-chosen **How often: Nightly / Hourly / Manual** segmented control. The drawing says the schedule is the vendor's: *"Whether an API is scheduled is the vendor's, not yours — it ships with the connector"* | `connection.cadence` is stored and clerk-settable | **yes** — count of `trigger == "scheduled"` |
| 32 | **Time** field `01:00` + *Your time zone. The only part you choose.* | **Not built** | `connection.next_run_at` exists; no time-of-day field | **no** — shown only when ≥ 1 operation is scheduled |
| 33 | Footer **Save and test** · **Cancel**, and a footnote that varies ⧗ clipped | **Built** — `Save and test` / `Cancel`, plus `Sign in with Microsoft` / `Done` on two branches | Built | **yes** — the footnote is `test_action` / `roundTrip` / `nothingToTest` |
| 34 | **Which column is which** — *This part appears once a file has been seen* | **Built** — `mapping_editor` kind | Built | **yes** — `mapping_editor` in `fields[]` |

---

## SCREEN B — VIEW (`VIEW-01…28`)

Live at `/:tenant/settings/integrations/<key>`, screen **S142 / INT-02**. The route **stays**
`integrations` by the ruling of 2026-09-16 (*"Changing it breaks every bookmark to buy a word
in a place nobody reads for meaning"*); the blueprint draws `/connectors/`, which is the
visible-word half and is a values change in eleven catalogues.

| # | Drawn | Front end | Back end | Varies per vendor? |
|---|---|---|---|---|
| 1 | Back link **← Connectors** | **Built differently** — reads *← Integrations*. One of the 319 catalogue values the rename moves | n/a | **no** |
| 2 | Kicker **CONNECTOR** | **Built differently** — reads *CONNECTION* | n/a | **no** |
| 3 | Vendor **title** | **Built** — `PageHeader` at `ConnectionDetailPage.tsx:1003`. Renders *Water meter cloud* where the drawing says *Neptune 360* | Built | **yes** — `display_name` |
| 4 | Identity line — *Site 4471* · *Chase operating · BAI2* · *Merchant 11f0••••308d* | **Built** — `data-describe`, monospace | **Built** — `describe_line()`, the adapter's own sentence | **yes** — the adapter's `describe()` |
| 5 | **N APIs** chip beside the name | **Not built** | Servable — `operations.length` | **yes** |
| 6 | State word with a **dot** — *● Working*, *● 4 of 4 working* | **Built differently** — *Not tested yet*, no dot, no roll-up count | **Built** — `display_state`; per-operation `state` also served | **yes** |
| 7 | Meta line **Meters · We collect · Production · connected by Alex Reed** | **Built differently** — renders `Production · connected by Dana Whitfield`. **Category and direction words absent** (`:1036`) | Served — `provider.category`, `operations[].direction/initiative` | **yes** — union of doors |
| 8 | Panel **N APIs on this connector** | **Built differently** — an unboxed `<ul>` headed *WHAT THIS CONNECTION DOES*, two facts per row (`:1069`) | Served | **yes** |
| 9 | Column **API · ENDPOINT** | **Label built**, endpoint **not built** | **Endpoint NOT SERVED** | **yes** |
| 10 | Column **DIRECTION** | **Not built** | **Served** — `direction`, `initiative` | **yes** |
| 11 | Column **WHEN** | **Not built** | On the manifest, **not serialised** — `Operation.trigger` | **yes** |
| 12 | Column **RATE LIMIT** | **Not built** | **Not stored anywhere** | **no** — needs a table |
| 13 | Column **LAST RUN** | **Not built** as a column | **Served** — `last_run_at` | **yes** |
| 14 | Column **RESULT** — *● Worked* / *● Refused* + **Retry** + the reason ⧗ reason clipped | **Built differently** — one state word per row, no colour dot, no Retry | **Served** — `last_outcome`, `trace_id`; `last_test_text` carries a reason | **yes** |
| 15 | Per-row **Test** ⧗ prose only | **Not built** | **Not servable** — the door takes no operation | **yes** — `test_action` |
| 16 | **…8 more** | **Not built** — all 16 Neptune rows render | n/a | **yes** |
| 17 | Panel **Key we hold** / **Token we hold** / **Sign-in on this connector** | **Built differently** — one panel headed *PASSWORDS ON THIS CONNECTION*, the same words whatever the credential is | **Served** — `credentials[]` with `version/hint/created_at/is_active` | **yes** — `auth.mode` picks the heading |
| 18 | Masked hint **••••7Q2F** | **Built** — `masked_hint`, never the secret | **Built** | **no** |
| 19 | **generated 12 Aug 2026 · expires 11 Nov 2026** | **Built** — `CredentialVersion`, expiry warnings (`BR-INT-042`) | **Built** | **yes** — `expiry_warning_days` |
| 20 | **In use** badge | **Built differently** — `data-credential-active`, not a badge | **Built** — `is_active` | **no** |
| 21 | *Only the last four characters are ever shown. It cannot be read back, by anyone, including us.* | **Built** — near-verbatim | Built | **no** |
| 22 | **One key. All N APIs use it.** | **Not built** | Servable | **yes** — N |
| 23 | ⚠ the no-token refusal, in this vendor's own terms | **Not built** | Not built | **yes** — `auth.mode`/`placement`. ⚠ see the drawing conflict below |
| 24 | Panel **Recent activity** | **Built** — *RECENT ACTIVITY*, with an empty state | **Built** — `GET /integrations/{key}/runs` | **no** |
| 25 | **Support reference** search box | **Built** — `FilterBar` | **Built** — `applied.q` | **no** |
| 26 | **All** chip · **+ Filter ▾** · **▦** columns | **Built** — outcome and trigger filters | **Built** — `filters` | **no** |
| 27 | Runs table **WHEN ▲ · WHICH API · RESULT · SUPPORT REFERENCE** | **Built** — the four columns, in that order, sortable on WHEN (`:516–526`) | **Built** | **no** |
| 28 | **1–2 of 2 · Rows per page 50** | **Built** — `page{page, per, count, pages}` | **Built**, server-paginated (`NFR-3`) | **no** |
| 29 | Footer **Test all** · **Replace key** \| **Regenerate token** \| **Re-authorise now** · **Disconnect** | **Built differently** — *Replace password* and *Disconnect* sit inside the credential section; *Test it now* sits in the runs section. No footer row, no **Test all**, and the middle button does not change word with the credential | Rotate, re-authorise and disconnect all exist | **yes** — the middle button is `auth.mode` |
| 30 | Footnote *Runs are kept exactly as they happened and are never edited* | **Built** — verbatim | Built — append-only (`BR-INT-039`) | **no** |
| 31 | **May call** column on the six key-issuing connectors | **Not built** | **Not built** — `issue_key()` takes a connection and a label and has nowhere to put a scope (`machine_auth.py:227`). Ruled 14 Sep; a new column and a check at the door | **yes** — the 5 ERPs + the kiosk |

---

## ⚠ THE CREDENTIAL MODEL — `DEF-INT-4118`, and what the configure screen must express

**This is the most valuable thing in this file.** The blueprint is emphatic: *"This is the
first thing to fix, not the names."*

### What the drawing asks for, measured on one frame

`CFG-10` **InvoiceCloud** (p45–46) collects **two live credentials on one connection**, and
they are drawn as two separate panels with two separate footnotes:

| | Drawn | What it is |
|---|---|---|
| **1** | **Merchant ID** * + **Merchant secret** * — *Typed once, never shown again* · *Stored encrypted. Never shown again.* · **This key is used by all 4 APIs.** | **their key, held by us** |
| **2** | **Token** panel — **Token address** *, **Scope**, *No token yet — save this connector, then generate one*, **Generate token**, **One token. All 4 APIs use it. It is shown once and afterwards only regenerated.** | **our token, generated by us** |

`CFG-05` **Twilio** draws the same pair: **Account SID** + **Auth token** *and* a Token panel
with **Generate token**.

`VIEW-10` then shows **only one of them** — *Token we hold ••••7Q2F generated 12 Aug 2026
expires 11 Nov 2026 In use* — and its footer reads **Test all · Regenerate token ·
Disconnect**. **There is no way on that screen to replace the merchant secret it just
collected.** The drawing cannot name both because the model cannot hold both.

### What the model does today, measured

| Fact | Where |
|---|---|
| `Manifest.auth` is **a single `Auth`**, not a tuple or a list | `registry.py:369`, `:510` |
| The database enforces **one active credential per connection** | `migrations/0001`, line 162: `ADD CONSTRAINT ex_integration_credential_one_active EXCLUDE USING btree (connection_id WITH =) WHERE (is_active)` — and line 166, `CREATE UNIQUE INDEX ux_integration_credential_one_active ON integration_credential (connection_id) WHERE is_active` on SQLite |
| A connection is already **per environment** | `uq_integration_connection_key_env` on `(tenant, provider_key, environment)` — `BR-INT-026`, shipped |
| The modal's credential surface is **one secret** | `ConnectModal.tsx:575` — replace mode filters `fields` to `kind === "secret"`, no role, no second group |
| The view screen's credential surface is **one list** | `ConnectionDetailPage.tsx:563` — `data-credentials`, versions of ONE secret |

⚠ **The environment split does NOT fix this and must not be conflated with it.** Live and
sandbox are two connection ROWS; this is two credentials in the SAME row. Doubling the
environments **doubles the problem**: a card processor then needs two credentials in live and
two more in sandbox.

### It is already live, and the count is bigger than five

`meters_neptune360` **ships today** holding `api_key` (a secret field) with
`auth.mode = "token_exchange"`, `placement = "bearer"` and
`TokenExchange(token_url="https://api.neptune360.example/oauth/token", ttl_seconds=600)` — **a
key we hold and a token we mint, on one connection, in a live connector.**

The blueprint's own arithmetic and its own sentence disagree about the total, and I am
recording both rather than picking one:

* **p155, the sentence:** *"the thing that blocked five payment processors now stands in front
  of **thirteen** connectors."*
* **p16, the arithmetic:** of the 13 with a *We send* operation — **8 exchange · 2 already
  OAuth · 2 protocols with no token · 1 sandbox with no credential**. On that reading **8**
  hold both an exchange credential and a generated token.

**Put to the PO as: is it eight or thirteen?** It changes nothing about the fix and everything
about how the work is sized.

⚠ **And p16's basis for excluding the meter head-ends is wrong on the one I checked.** It puts
*meters ×4* outside the ruling because they *"carry no We send operation"*. `meters_neptune360`
carries **four**: `request_billing_export`, `push_account_meter_link`, `push_route_assignment`,
`push_service_point`.

### What the configure screen would need — the measured answer

Nothing on the screen is the hard part. **The screen needs exactly four things, and three of
them are free once the model moves:**

1. **A named credential GROUP per credential, not per connection.** Today the field slot is one
   flat list and the footer has one *Replace key*. The drawing wants two headed panels — *the
   key they gave us* and *the token we generated* — each with its own state line, its own
   footnote (*This key is used by all 4 APIs* / *One token. All 4 APIs use it*) and its own
   action (*Replace key* / *Regenerate token*). **That is a loop over credentials instead of a
   single block**, and it is the whole screen change.
2. **A ROLE on each credential**, so the screen knows which panel a version belongs to and the
   footer knows which button to draw. Today `IntegrationCredential` has `version`, `is_active`,
   `masked_hint`, `expires_at` and **no role**.
3. **The constraint becomes `(connection_id, role)`** — `EXCLUDE USING btree (connection_id
   WITH =, role WITH =) WHERE (is_active)`, and the SQLite partial index gains the same column.
   This is the migration, and it is the only one.
4. **`Manifest.auth` becomes plural, and an operation names which one it uses.** The blueprint
   offers three ways and chooses none; measured against this codebase, **the second is the one
   that fits**:

| Way out (p155) | What it costs here |
|---|---|
| Make `auth` a tuple and let an operation name which one it uses | Biggest and most general. `Auth` is read in `oauth.py`, `machine_auth.py`, `runtime.py`, `page_policy.py`, `selectors.py` and both screens; `validate()` has ~8 clauses keyed on `auth.mode` |
| **A second credential row per connection with a ROLE** | **Smallest, and it fits the existing table** — one column, one constraint edit, one loop on each screen. `Manifest.auth` can stay singular if the generated token is modelled as a role rather than as a second `Auth` |
| Split the vendor into two connectors, two cards for one logo | No code at all — and it breaks *one token, all N APIs use it*, which is the sentence both drawings turn on |

⚠ **One thing the screen must NOT do:** `we_never_dial` is computed from `initiative` and not
from `auth.mode`, and `registry.py:538` says in its own words that this is *"the narrower and
therefore safer test"* precisely so it survives the 4118 fix. **A lane that "simplifies" it to
`auth.mode` while making auth plural breaks it silently.**

---

## What the PRODUCT has that the DRAWING does not

| On the screen, not in the drawing | Where | Keep it? |
|---|---|---|
| **A reason under the state word** — *Not working · the mail server is not answering* | `ConnectionDetailPage.tsx:1030`, `last_test_text` | **Yes.** `DEF-INT-4025` filed it because the server had served it since wave B and no screen drew it |
| **A run detail card** — count tiles, named items, *their words underneath ours*, an artifact link, a content hash, the collecting/poll line | `:300–465` | **Yes.** Far past the drawing; `BR-INT-040` requires items be NAMED, never a batch boolean |
| **A dash is not a zero** on an unconfirmed run | `CountTile`, `:215` | **Yes.** `BR-INT-018` — *Unconfirmed* is amber and never green |
| **A credential HISTORY with rollback** | `ManagePanel`, `:563`, `rollbackCredential` | **Yes** |
| **Disconnect behind a typed-name confirm**, danger tier | `ConnectModal.tsx:831` | **Yes.** B14 rule 6 |
| **An expiry warning box** before a credential lapses | `:829`, `BR-INT-042` | **Yes** |
| **`elsewhere` — runs on this provider's OTHER connection** | `:1129` | **Yes.** The drawing has no account of the two-environment case on this screen |
| **Browser-executed operations say so** | `:1088`, `BR-INT-048` | **Yes** |
| **The access log panel** | `AccessLogPanel` — another lane's `ACC-01` | n/a |

---

## What the DRAWING has that no manifest field could supply

**This is where the back-end work hides.** Everything else in the tables is a manifest field, a
served field nobody reads, or screen code.

| Drawn | Why no manifest field reaches it | Size |
|---|---|---|
| **RATE LIMIT**, on 78 operation rows across 56 screens | The API list is manifest code and is the same for every utility; **a ceiling is bought per contract**, so a larger utility buys a larger quota. It cannot live where the operation lives. Blueprint p17: *"a row per connection and per operation, with the manifest carrying the default that provisioning copies in."* **Nothing stores it today** | **A new table**, a manifest default, a provisioning copy, and a serialiser |
| …and the column **means two opposite things** | Outward it is the ceiling **they** allow us; inward it is the ceiling **we** allow them. Only the inward half is enforced today (`serve.py:436`). **Nine two-way connectors carry both on one table, one row apart** | The screen must say which way each row points |
| …and the **count** beside it — *Calls used this week — 4,180 of 10,000* | A limit with no consumption beside it cannot answer the only question a clerk has. Drawn, never rendered (`S141-1`) | The limit and the count are one feature |
| **`API · ENDPOINT`** — the host on each row | `Operation.host_field` names WHICH configured field holds the host, and **15 of our 18 manifests name `base_url` and do not declare it.** Only `gis_city`, `map_tiles_public` and `geocoder_census` declare the field their operations name. For the other 15 the endpoint lives inside the adapter and no connection ever holds one | **Manifest data** once each declares a host field — which is exactly the PO's phase-1 `api.vendor.example` work. **No schema change** |
| **Per-row `Test`** ⧗ | `POST /integrations/{key}/test` takes `{recipient?}` and no operation. 25 of 45 operations declare a `test_action` reachable only as one sentence about the whole connector | One body field, one selector argument |
| **`May call`** on six view screens | `issue_key()` takes a connection and a label; there is nowhere to put a scope | **A new column and a check at the door.** Ruled 14 Sep. **Not phase 1 — do not fold it in quietly** |
| **The `Generate token` act** | Rotation exists; *generate, shown once, afterwards only regenerated* does not, and it is the second half of the credential problem above | Comes with the 4118 fix |

---

## Other findings that matter

**1 · The configure screen is a dialog and the drawing is a page.** Five rows of the first
table are that one fact. The blueprint records the reason on p21: *"'Set up' action — New — the
form has an address now, so a connected card can reopen it."* Today a connected card reopens
the **manage** mode of the same modal; there is no URL to bookmark, share in a support ticket,
or link a runbook to.

**2 · The schedule control is the clerk's and the drawing says it is the vendor's.** The live
modal draws **How often: Nightly / Hourly / Manual** as an editable segmented control. `CFG-06`
draws *"13 of 16 run on a clock. The rest are started by a person, by a queue, or by them"* —
a **statement** — with one editable **Time** field beneath it and the refusal *"Whether an API
is scheduled is the vendor's, not yours."* These are opposite postures on the same control.
`connection.cadence` is per CONNECTION; `Operation.trigger` is per OPERATION; a connector with
both scheduled and manual operations cannot be described by one cadence word.

**3 · A two-door connector shows one door.** `Manifest.kicker` returns the first operation's
`(direction, initiative)` only. Measured: **4 of 18 manifests span two doors today** —
`email_bulk`, `meters_neptune360`, `sms_twilio`, `payments_sandbox` — and the blueprint says
**9 of 28** after phase 1. The card for *Bulk email service* reads `EMAIL · WE SEND` in the
running product; `CFG-04` draws `EMAIL · WE SEND · THEY SEND`. The fix is a union, not a
branch, and `BR-INT-028` already puts the fact on the operation.

**4 · The screen's premise and the drawing's sentence disagree about `Send bills from`, and
both are honest.** `ConnectModal.tsx:558` states its premise plainly: for a redirect provider
*"there is no submit on this form at all — the round trip is the save — so every character
typed into that box went nowhere"*, and `US-INT-005` §1 wants the send-from to be the
**signed-in identity** rather than something a clerk typed. That is `DEF-INT-4229`, reasoned
and deliberate. **`CFG-01` draws `Send bills from *` as a required input with the help text
*The address bills are sent from*, on the same form as the sign-in button.** I confirmed in the
browser that the live Microsoft 365 form shows **no such field** and reads *"Signing in is all
there is — nothing else to fill in."* `email_microsoft` and `email_google` both declare
`send_from` as `required: true`. **A required manifest field that no form can satisfy is worth
a ruling either way** — see below.

**5 · The drawing puts the wrong refusal on at least one card.** `VIEW-06` **Neptune 360**
draws *Key we hold* and *"⚠ No token on this one — a file goes to a folder or a download, and
neither carries a token"* — which is `VIEW-22`'s sentence, correct for the accounting export
file and false for an HTTPS meter head-end that exchanges a bearer token. p16's prose agrees
with the drawing and both disagree with the shipped manifest. **Build the sentence from
`auth.mode` and `transport`, never from the frame.**

**6 · The accented `Panel` costs nothing.** `PanelTone` is already
`"plain" | "info" | "warning" | "emergency" | "group"` (`components/Panel.tsx:60`), `emergency`
keeps the plain border and adds a left rule, `group` is a small-caps accent heading with a rule
beneath. `tone` absent is `plain`, byte-identical to the 149 existing call sites. **The PO's
ruling is satisfiable without adding one class to any stylesheet** (B14 rule 21). ⚠ It does not
replace `RefusalStrip` / `ConsequenceBox` / `WarningBox` — a refusal is not a section heading.

**7 · Count what RESOLVES before counting what to rename.** `DEF-CUS-5478` found a whole new
wizard running on English `defaultValue` fallbacks with **zero** keys in any of the eleven
catalogues, parity green. Both screens here use `defaultValue` heavily
(`integrations.provider.${key}.operation.${name}`). The *Connectors* rename is **319 keys by
the blueprint's count, not verified against this checkout**, and B14 rule 34 says all 319 move
together or none does.

---

## Needs a ruling

| # | Question | Reading A | Reading B | What each costs |
|---|---|---|---|---|
| 1 | **Eight or thirteen?** How many connectors hold two live credentials | **8** — p16's arithmetic: only the exchange group holds both a vendor key and a generated token | **13** — p155's sentence: every *We send* connector | The fix is identical either way; the number sizes the phase-2 order and the *what is still blocked* line on the card |
| 2 | **Which way out of `DEF-INT-4118`** | `auth` becomes a tuple, an operation names which one | **A second credential row with a ROLE** — one column, one constraint edit, fits the table | Measured above. B is materially smaller here; A is more general. The blueprint chooses neither on purpose |
| 3 | **Is `Send bills from` typed or derived?** | The drawing: a required input beside the sign-in button | The product: the signed-in identity, `TokenGrant.account` (`DEF-INT-4229`) | A: restores a box a clerk can fill wrongly and creates a mismatch that shows up as an undiagnosable bounce. B: `send_from` should stop being `required: true` on the two redirect manifests, because nothing can satisfy it |
| 4 | **Who owns the schedule?** | The drawing: the vendor's, per operation; the clerk chooses only a **time** | The product: a clerk-chosen **How often** per connection | A is the blueprint and the `RAN-2` refusal; it means removing a live control and moving `cadence` to a time-of-day. B is what ships. A connector with both scheduled and manual operations cannot honestly wear one cadence word |
| 5 | **Does the configure screen get an address?** | A page at `…/configure`, as drawn | Stay a modal | The 16 Sep route ruling says `settings/integrations/:key` **stays** and *"if the PO wants the address to read `connectors` too, the honest form is a new route plus a redirect"*. It did not answer whether the FORM gets an address at all |
| 6 | **`Neptune 360` or `Water meter cloud`?** Five shipped manifests carry generic display names where the blueprint names the vendor | Name the vendor, as drawn | Keep the generic name | Naming the vendor is `display_name` data on 5 manifests. It interacts with phase 1: three of those generic manifests are being **split** into 13 named cards anyway |
| 7 | **Is the rate limit's count part of phase 1?** | Limit and count land together — p17: *"they are one feature and should land together"* | Limit first, count later | The count needs a consumption store nothing has. A ceiling with no usage beside it answers no clerk question |

---

## Defects filed

| Id | What |
|---|---|
| `DEF-INT-5487` | The blueprint PDF is horizontally clipped — the right-hand column of all 56 connector frames is absent from the file |
| `DEF-INT-5488` | 15 of 18 manifests name a `host_field` they do not declare, so no connection ever holds a host and the drawn endpoint cannot be served |
| `DEF-INT-5489` | `POST /integrations/{key}/test` takes no operation, so 25 of 45 declared `test_action`s are unreachable individually |

---

## How I measured, and what I could not

| Surface | What measuring it meant | Did I? |
|---|---|---|
| The drawing | Rendered to PNG at scale 1.9–2 and **read as an image** (B14 rule 42), with `pdfium` text as the index only | **Yes** — 10 frames across 6 vendors, plus p16, p17, p154, p155 |
| The two screens | **Clicked, in a browser, at the real address**, signed in as Dana Whitfield | **Yes** — `/brazosbend/settings/integrations` and `/…/meters_neptune360`, screenshots read |
| The API | Called for real and the response read | **Yes** — `GET /integrations` (18 providers) and `GET /integrations/meters_neptune360/runs` |
| The registry | Loaded in `06-backend/.venv` and inspected | **Yes** — 18 manifests, 45 operations, every `auth`, `field` and `host_field` |
| The constraint | Read in the migration, not inferred | **Yes** — `migrations/0001` lines 162 and 166 |
| The right-hand column of any frame | — | **No.** Not in the file. Taken from prose and marked `⧗` |
| The 13 undeclared vendors' own field lists | — | **Partly.** Read for InvoiceCloud, Paymentus and Twilio; the other ten not read frame by frame |
| The blueprint's 47 / 78 operation counts | Reconciled against the registry | **No** — they do not close against each other or against our 45. Reported rather than guessed |

**Nothing was built and no product code was changed.** This file is the whole deliverable.
