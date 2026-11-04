# Step 0 — connectors 11 to 19, measured against the Integration Blueprint

**Nothing here is built, fixed or decided.** This is a measurement lane's record of what
the blueprint DRAWS for nine connectors, what the repository HOLDS for them today, and
the differences between the two. Every difference is routed: it is either a build item
for a later wave, or it is in the closing **Needs a ruling** section because the drawing
and a signed rule cannot both be true.

## How this was measured

* **The drawing is the image.** B14 rule 42 — *"When you use images to create screens
  your accuracy is higher; hence dont create screens using only Text"*. Every row below
  was read off a PNG rendered from the blueprint at scale 3 with
  `10-scripts/pdf/pdf_render.py`. Extracted PDF text was used ONLY as an index, to be
  sure no region of a page was skipped; where the extracted text and the image disagree
  the image is recorded (the extractor gives `Payment kiosknetwork`, `USPayments`,
  `GlobalPayments` and `SAP—`; the image draws *Payment kiosk network*, *USPayments*,
  *GlobalPayments* and *SAP*).
* **A drawn figure is an illustration.** B14 rule 37 — every `60 / min`, `Today 04:12`,
  `••••7Q2F`, `Merchant 11f0••••308d` and `1,240 of 1,240` on these eighteen pages is a
  sample value. The SHAPE is recorded (there is a rate-limit number per operation, there
  is a masked key, there is a last-run time); the sample value is not.
* **Source pages**, verified against the image and not only the document's index —
  every one matched the index:

  | Connector | Key | CFG page | VIEW page |
  |---|---|---|---|
  | Paymentus | `pay_paymentus` | p048–p049 | p050–p051 |
  | USPayments | `pay_uspayments` | p051–p052 | p053 |
  | WorldPay | `pay_worldpay` | p054–p055 | p056 |
  | GlobalPayments | `pay_globalpayments` | p057–p058 | p059 |
  | Payment kiosk network | `payments_kiosk` | p060–p061 | p061–p062 |
  | Test payments (sandbox) | `payments_sandbox` | p062–p063 | p063–p064 |
  | Aclarian | `erp_aclarian` | p064–p065 | p066–p067 |
  | Workday | `erp_workday` | p067–p068 | p068–p069 |
  | SAP | `erp_sap` | p069–p070 | p071–p072 |

  Each screen spans a page break; the artboards are stacked two to a page, so a CFG
  screen begins at the bottom of one page and finishes at the top of the next.
* **What it was measured against**: `06-backend/apps/integrations/manifests/` (18
  manifests at the tip), `06-backend/apps/integrations/registry.py` (the closed
  vocabularies and the `Field` / `Operation` shapes) and
  `06-backend/apps/integrations/models.py` (the five tables).
* **Counting rule, stated so the numbers can be re-derived.** A field or an operation is
  **MISSING** when no manifest exists at the drawn provider key, or a manifest exists and
  has nothing of that meaning. It is **MATCHES** when the manifest at the drawn key — or,
  for *Where it runs*, the `integration_connection.environment` column that every
  connector shares — already serves it. **DIFFERS** means present in a different shape,
  label or place, and the difference is stated.

## What every one of the nine draws in common

Recorded once so the nine tables below can stay on the per-connector content. The common
regions belong to the shared-shape lane; they are here only because a field cannot be
placed in a panel that has not been named.

**The configure screen (CFG)**, top to bottom: a `← Connectors` back link · a kicker in
small caps (*PAYMENTS · WE COLLECT · WE SEND*) · the connector name as the page head · a
one-line summary · a plain note panel where a new connector says *"New connector. Nothing
is built for this vendor today — the fields below are the shape it will take."* · then
the panels. **`Connection details` is the only panel drawn with an accent** — a red rule
across its top edge, which reads as `PanelTone` **info**. Every other panel on these
screens is drawn plain. The ⚠ sentences inside the panels are drawn as an inline note
with a red left bar, which reads as tone **warning** and is not itself a panel. The
footer is `Save and test` (primary, drawn disabled) · `Cancel` · a status line at the far
right.

**The view screen (VIEW)**: back link · the word `CONNECTOR` · the name · an identity
line carrying a masked reference, an *N APIs* chip and a green working count · a second
line reading *category · direction words · environment · connected by <person>* · then
`N APIs on this connector` (accent panel, red top rule) · a credential panel whose title
and content change by connector · `Recent activity` with a support-reference search box,
an `All` chip, a `+ Filter` menu, a column chooser, a four-column table
(`WHEN` / `WHICH API` / `RESULT` / `SUPPORT REFERENCE`) and a footer reading
*1–3 of 4 · Rows per page 50* · a footer of actions.

**Two things are drawn cut off by the artboard and are recorded as unreadable, not as
absent.** On the CFG screens of the kiosk and the sandbox the API table has a fifth
column whose header begins `T` and whose cells hold a control — the artboard ends before
the word does. On the VIEW screens the `RESULT` column and the run-status dot are the
right-most thing that survives. The blueprint's own catalogue page (p163) is cut off in
the same way, mid-sentence after *"The five ERPs need none at all"*.

---

## 11 · Paymentus — `pay_paymentus`

CFG-11 p048–p049 (badge **NEW CONNECTOR**) · VIEW-11 p050–p051 (badge **PROPOSED**).
Kicker as drawn: **PAYMENTS · WE COLLECT · WE SEND**. Summary as drawn: *"Take card and
bank payments through Paymentus."*

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Merchant ID | single-line text | yes (red asterisk) | Connection details · accent (info) | no manifest at `pay_paymentus`; `payments_card` has `merchant_id` "Merchant ID" | MISSING |
| 2 | Merchant secret | secret, placeholder *"Typed once, never shown again"*, help *"Stored encrypted. Never shown again. This key is used by all 4 APIs."* | yes | Connection details · accent (info) | no manifest at key; `payments_card` has `merchant_secret` | MISSING |
| 3 | Client ID | single-line text | yes | Connection details · accent (info) | no manifest at key; `payments_card` has `client_id` labelled **"x-client-id"** | MISSING |
| 4 | Card page | two-choice segmented control: *hosted by them* \| *embedded* | yes | Connection details · accent (info) | nothing anywhere | MISSING |
| 5 | Where it runs | two-choice segmented control: *Production* \| *Sandbox* | no asterisk drawn | Connection details · accent (info) | `integration_connection.environment`, two rows per connector (`BR-INT-026`) | MATCHES |
| 6 | Token address | single-line text, sample value shown | yes | Token · plain | nothing; `Operation.host_field` names `base_url` but no manifest declares one here | MISSING |
| 7 | Scope | single-line text, placeholder *"Leave blank for everything the key allows"* | no | Token · plain | nothing | MISSING |
| 8 | Time | time, sample `01:00`, help *"Your time zone. The only part you choose."* | no | When it runs · plain | `integration_connection.cadence` + `next_run_at` — a cadence word and an absolute timestamp, not a daily clock time and no time zone | MISSING |

Two panel-level controls are drawn beside the fields and are not fields: **`Generate
token`** (a button, under the state line *"No token yet — save this connector, then
generate one."*) and the footer's **`Save and test`**. The Token panel's own sentence is
*"We generate one token for this connector and every API authenticates with it"*, and its
closing line is *"One token. All 4 APIs use it. It is shown once and afterwards only
regenerated."*

### Table B — operations on the view screen

| # | Operation name as drawn | Direction (we collect / we send) | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Charge a card | We send | *On demand* · rate limit per minute · a last-run time | one shared host, badged **PROPOSED** | theirs — we dial them | no manifest at key; `payments_card` has `charge` labelled "Take a card payment" | MISSING |
| 2 | Hosted card page | We send | *While you wait* · rate limit per minute · a last-run time | same host, **PROPOSED** | theirs | no manifest at key; `payments_card` has `card_page` "Card page" | MISSING |
| 3 | Settlement report | We collect | *Nightly* · rate limit per minute · a last-run time | same host, **PROPOSED** | theirs | nothing anywhere | MISSING |
| 4 | Refund a payment | We send | *On demand* · rate limit per minute · a last-run time | same host, **PROPOSED** | theirs | nothing anywhere | MISSING |

The panel's closing lines are *"All 4 use the address above."* and *"These are the limits
they allow us."*, then the ⚠ note *"The API list and its rate limits are set when we
configure this connector — neither is a clerk control."* The credential panel on VIEW-11
is titled **`Token we hold`** and draws a masked value, a generated date, an expiry date
and an `In use` chip, over the sentence *"Only the last four characters are ever shown. It
cannot be read back, by anyone, including us."* The footer actions are `Test all` ·
`Regenerate token` · `Disconnect`.

**Verdict line:** **No.** Nothing exists at `pay_paymentus`, so all four operations and
seven of the eight controls have to be built from nothing; and two of them cannot be
built from the drawing alone — the rate limit has no place to live on an operation, and
the merchant secret plus the generated token are two live secrets on a connector the
database allows exactly one of.

---

## 12 · USPayments — `pay_uspayments`

CFG-12 p051–p052 (**NEW CONNECTOR**) · VIEW-12 p053 (**PROPOSED**). Kicker **PAYMENTS ·
WE COLLECT · WE SEND**. Summary as drawn: *"Take card and bank payments through US
Payments."* The page head draws **USPayments** as one word while the summary sentence and
the catalogue table both write **US Payments** as two.

### Table A — fields on the configure form

Measured field by field from the image: **identical to Paymentus, all eight rows, in the
same order, with the same controls, the same required marks and the same panels.** Rather
than repeat the table, the differences are stated — **there are none**. Every verdict in
Table A of connector 11 applies here unchanged, against the same absent manifest at
`pay_uspayments`.

### Table B — operations on the view screen

Identical to Paymentus: **Charge a card** (We send · *On demand*), **Hosted card page**
(We send · *While you wait*), **Settlement report** (We collect · *Nightly*), **Refund a
payment** (We send · *On demand*), all four on one shared host, all four badged
**PROPOSED**, all four **MISSING**. Credential panel `Token we hold`; footer `Test all` ·
`Regenerate token` · `Disconnect`.

**Verdict line:** **No** — same as Paymentus, and for the same three reasons: no manifest
at the key, no home for a rate limit, and two live secrets where the database allows one.

---

## 13 · WorldPay — `pay_worldpay`

CFG-13 p054–p055 (**NEW CONNECTOR**) · VIEW-13 p056 (**PROPOSED**). Kicker **PAYMENTS ·
WE COLLECT · WE SEND**. Summary: *"Take card and bank payments through WorldPay."*

### Table A — fields on the configure form

Read from the image and compared row by row against connector 11: **identical, all eight
rows, same order, same controls, same required marks, same panels.** All verdicts carry
over against the absent manifest at `pay_worldpay`.

### Table B — operations on the view screen

Identical to Paymentus — the same four operations with the same direction words, the same
state words, one shared host and a **PROPOSED** badge on each. All four **MISSING**.

**Verdict line:** **No**, for the same three reasons as Paymentus.

---

## 14 · GlobalPayments — `pay_globalpayments`

CFG-14 p057–p058 (**NEW CONNECTOR**) · VIEW-14 p059 (**PROPOSED**). Kicker **PAYMENTS ·
WE COLLECT · WE SEND**. Summary: *"Take card and bank payments through Global Payments."*
The page head draws **GlobalPayments** as one word; the summary and the catalogue write
**Global Payments** as two.

### Table A — fields on the configure form

Identical to connector 11, all eight rows. All verdicts carry over against the absent
manifest at `pay_globalpayments`.

### Table B — operations on the view screen

Identical to Paymentus — four operations, same words, one shared host, **PROPOSED** on
each. All four **MISSING**.

**Verdict line:** **No**, for the same three reasons as Paymentus.

> **The four card processors are one drawing repeated.** Measured from the images and not
> inferred: the only things that change across CFG-11, CFG-12, CFG-13 and CFG-14 are the
> page head, the vendor's name inside the summary sentence and the route in the header
> chip. Not one field, control, required mark, panel, operation, direction word, state
> word or footer action differs. That is worth recording because it is what makes them a
> single build with four manifest files, which is `BR-INT-037` working as intended.

---

## 15 · Payment kiosk network — `payments_kiosk`

CFG-15 p060–p061 (badge **PROPOSED FORM**) · VIEW-15 p061–p062 (badge **S142, FOR THIS
CONNECTOR**). Kicker as drawn: **PAYMENTS · THEY SEND · THEY READ**. Summary: *"Take
payments at a machine, and hear when one bounces."* This one **ships today** — there is a
manifest at the drawn key, and the CFG screen carries no *"New connector"* note.

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | The key for them to use | a state line *"No key yet — save this connector, then issue one."* over an **`Issue key`** button — no input box | no asterisk drawn | Connection details · accent (info) | `issued_key`, label *"The key for them to use"*, kind `issued_secret` | MATCHES |
| 2 | Allowed addresses | single-line text | no asterisk drawn | Connection details · accent (info) | `allowed_addresses`, label *"Allowed addresses"*, kind `text`, **`required=False`** | MATCHES |
| 3 | Where it runs | segmented *Production* \| *Sandbox* | no asterisk drawn | Connection details · accent (info) | `integration_connection.environment` (`BR-INT-026`) | MATCHES |

There is **no Token panel and no When it runs panel** on this screen. In their place the
drawing puts a plain panel holding one sentence: *"They start this one. There is no
schedule — the trigger is their call."*

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Payments | They send | *They call us* · rate limit per minute · a last-run time and a status dot | one shared host, **no** PROPOSED badge | **ours** — they call an address we publish | `payments`, label *"Payments"*, `direction="in"`, `initiative="them"`, `trigger="webhook"` | MATCHES |
| 2 | Account lookup | They read | *They call us* · rate limit per minute · last-run time and dot | same host, no badge | ours | `account_lookup`, label *"Account lookup"*, `direction="in"`, `initiative="them"` | DIFFERS — see below |
| 3 | Returns | They send | *They call us* · rate limit per minute · last-run time and dot | same host, no badge | ours | `returns`, label *"Returns"*, `direction="in"`, `initiative="them"` | MATCHES |

The closing lines are *"All 3 use the address above."* and — note the reversal against the
card processors — *"These are the limits **we allow them**."*

**The DIFFERS on row 2, stated precisely.** The drawing uses **They read** for this
operation and **They read** again for all nine finance-system reads on connectors 17, 18
and 19. Our two manifests record that same drawn word two different ways: the kiosk's
account lookup is `direction="in"`, while `gl_partner`'s three reads are
`direction="out"` with the same `initiative="them"`. One of the two is wrong and the
drawing cannot say which, because *direction* in our model is *which way the data moves*
and both readings are defensible from the words alone. **Routed as a defect candidate for
the triage lane, not as a question for the Product Owner** — the change process says an
ambiguous case is a defect, and this is our own inconsistency rather than a change to
what was agreed. It is not cosmetic: `Manifest.kicker` reads the first operation's
direction and initiative, so it decides what the card and the page head say.

The credential panel on VIEW-15 is **`Keys we issue`** — a table of `KEY` / `MAY CALL` /
`ISSUED` / `STATE`, with the ⚠ note *"May call is new. Today one key opens every API on
the connector."* The identity line draws the masked key, an *N addresses allowed* count
and an *N APIs* chip. The footer actions are `Keys we issue` · `Disconnect` — **no
`Test all`**, which is consistent: every operation here is theirs to start.

**Verdict line:** **Yes** for the form itself — all three controls and all three
operations already exist at the drawn key and match the drawing including the two
not-required marks. What cannot be built from the drawing alone is the per-key **May
call** column, which has no column in `integration_credential`, and the rate limit, which
has no place on an `Operation`.

---

## 16 · Test payments (sandbox) — `payments_sandbox`

CFG-16 p062–p063 (badge **PROPOSED FORM**) · VIEW-16 p063–p064 (badge **S142, FOR THIS
CONNECTOR**). Kicker as drawn: **PAYMENTS · WE SEND · THEY SEND**. Summary: *"A test
processor for the whole payment journey."* Also **ships today**.

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | How every charge answers | three-choice segmented control: *approve* \| *decline* \| *timeout* | yes (red asterisk) | Connection details · accent (info) | `behaviour`, label *"How every charge answers"*, kind `select`, options `approve` / `decline` / `timeout` | MATCHES |
| 2 | Where it runs | segmented *Production* \| *Sandbox* | no asterisk drawn | Connection details · accent (info) | `integration_connection.environment` | MATCHES |

The Token panel IS drawn here, holding one sentence and no field: *"No token. The sandbox
answers without one."* The When it runs panel is drawn the same way: *"Nothing here runs
on a clock. Every API on this connector is started by a person, by a queue, or by them."*
Both agree with the manifest, which declares `Auth(mode="none", placement="none")`.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Take a payment | We send | *On demand* · rate limit per minute · a last-run time | one shared host, **no** PROPOSED badge | theirs (the sandbox's) | `charge`, label *"Take a payment"*, `direction="out"`, `initiative="us"`, `trigger="manual"` | MATCHES |
| 2 | Card page | We send | *While you wait* · rate limit per minute · a last-run time | same host, no badge | theirs | `card_page`, label *"Card page"*, `direction="out"`, `initiative="us"`, `trigger="inline"` | MATCHES |
| 3 | Payment confirmed | They send | *They call us* · rate limit per minute · a last-run time | same host, no badge | ours | `settlement`, label *"Payment confirmed"*, `direction="in"`, `initiative="them"`, `trigger="webhook"` | MATCHES |

The closing lines are *"All 3 use the address above."* and *"Outward the limit is what
they allow us; inward it is what we allow them."* — the only connector of the nine whose
sentence carries both halves, and the only one that mixes the two initiatives in one
table.

The credential panel on VIEW-16 is titled **`Sign-in on this connector`** and holds one
sentence: *"No password is stored for this connector."* The footer actions are `Test all`
· `Disconnect` — no `Regenerate token`, consistent with there being no credential.

**Verdict line:** **Yes** — every control, every operation, every direction word, every
state word and the absence of a credential all match the manifest at the drawn key. The
rate limit is the only drawn thing with no home, and this is the one connector where a
wrong rate limit costs nothing.

---

## 17 · Aclarian — `erp_aclarian`

CFG-17 p064–p065 (badge **NEW CONNECTOR**) · VIEW-17 p066–p067 (badge **PROPOSED**).
Kicker as drawn: **ERP · THEY READ**. Summary: *"Your finance system collects payments and
bills from here."*

⚠ **This connector's NAME is an open question the blueprint itself raises** — see the
closing section, item 1. The shape below is recorded regardless, because the shape is the
same whatever the partner ends up being called.

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Their client id | single-line text | yes (red asterisk) | Connection details · accent (info) | no manifest at `erp_aclarian`; `gl_partner` has `client_id` labelled *"Their client id"* | MISSING |
| 2 | What they may read | three chips drawn side by side: *payments* · *bills* · *customers* — drawn as a multiple choice, not a single pick | yes | Connection details · accent (info) | no manifest at key; `gl_partner` has `scopes` kind **`select`** with exactly those three options — a **single**-value kind | MISSING (and the kind differs) |
| 3 | Allowed addresses | single-line text | yes | Connection details · accent (info) | no manifest at key; `gl_partner` has `allowed_addresses` and `network_allowlist=True` | MISSING |
| 4 | The key for them to use | state line *"No key yet — save this connector, then issue one."* over an **`Issue key`** button | **no asterisk drawn** | Connection details · accent (info) | no manifest at key; `gl_partner` has `issued_key` kind `issued_secret`, **`required` left at its default of `True`** | MISSING (and the required mark differs) |
| 5 | Where it runs | segmented *Production* \| *Sandbox* | no asterisk drawn | Connection details · accent (info) | `integration_connection.environment` | MATCHES |

No Token panel and no When it runs panel; in their place the same plain one-sentence
panel as the kiosk: *"They start this one. There is no schedule — the trigger is their
call."*

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Read payments | They read | *They call us* · rate limit per minute · a last-run time · a `RESULT` of *Worked* | one shared host, badged **PROPOSED** | **ours** — they call an address we publish | no manifest at key; `gl_partner` has `read_payments` labelled **"Payments"**, `direction="out"`, `initiative="them"`, `trigger="partner"` | MISSING (label differs from the nearest thing we have) |
| 2 | Read bills | They read | *They call us* · rate limit per minute · last-run time · *Worked* | same host, **PROPOSED** | ours | `gl_partner` has `read_bills` labelled **"Bills"** | MISSING (label differs) |
| 3 | Read customers | They read | *They call us* · rate limit per minute · last-run time · **`Refused`** in red, with a **`Retry`** link and the words *"The site refused"* drawn beneath it inside the row | same host, **PROPOSED** | ours | `gl_partner` has `read_customers` labelled **"Customers"** | MISSING (label differs) |

The closing lines are *"All 3 use the address above."* and *"These are the limits we allow
them."* The credential panel is **`Keys we issue`** — `KEY` / `MAY CALL` / `ISSUED` /
`STATE`, with the ⚠ note *"May call is new. Today one key opens every API on the
connector."* The identity line draws a masked key beside the words *reads payments, bills*
and an *N of N working* count. The footer actions are `Keys we issue` · `Disconnect` — no
`Test all`, consistent with every operation being theirs to start.

**Verdict line:** **No.** Nothing exists at `erp_aclarian`; four of the five controls and
all three operations have to be built. Three things additionally cannot be built from the
drawing alone: the connector's NAME is an open question the blueprint raises itself, the
*What they may read* chips are a multiple choice where our field kind holds one value, and
the `MAY CALL` column has no column behind it.

---

## 18 · Workday — `erp_workday`

CFG-18 p067–p068 (**NEW CONNECTOR**) · VIEW-18 p068–p069 (**PROPOSED**). Kicker **ERP ·
THEY READ**. Summary: *"Your finance system collects payments and bills from here."*

### Table A — fields on the configure form

Read from the image and compared row by row against connector 17: **identical, all five
rows, same order, same controls, same required marks (including the missing asterisk on
*The key for them to use*), same single accent panel.** All verdicts carry over against
the absent manifest at `erp_workday`.

### Table B — operations on the view screen

Identical to Aclarian — **Read payments**, **Read bills**, **Read customers**, all three
*They read* · *They call us*, one shared host, **PROPOSED** on each, and the same
`RESULT` column. All three **MISSING**, and all three carry the same label difference
against `gl_partner`'s *Payments* / *Bills* / *Customers*. Credential panel `Keys we
issue`; footer `Keys we issue` · `Disconnect`.

**Verdict line:** **No** — nothing at `erp_workday`, and the same two build-blockers as
Aclarian (a multiple-choice scope field our kind cannot hold, and a `MAY CALL` column with
no column behind it). The name, unlike Aclarian's, is not in doubt.

---

## 19 · SAP — `erp_sap`

CFG-19 p069–p070 (**NEW CONNECTOR**) · VIEW-19 p071–p072 (**PROPOSED**). Kicker **ERP ·
THEY READ**. Summary: *"Your finance system collects payments and bills from here."*

### Table A — fields on the configure form

Identical to connector 17, all five rows. All verdicts carry over against the absent
manifest at `erp_sap`.

### Table B — operations on the view screen

Identical to Aclarian — three reads, *They read* · *They call us*, one shared host,
**PROPOSED** on each. All three **MISSING** with the same label difference. Credential
panel `Keys we issue`; footer `Keys we issue` · `Disconnect`.

**Verdict line:** **No** — nothing at `erp_sap`, same two build-blockers as Aclarian.

> **The three finance systems are one drawing repeated**, exactly as the four card
> processors are. Measured from the images: only the page head and the route chip change
> across CFG-17, CFG-18 and CFG-19. Not one field, control, required mark, panel,
> operation, direction word or footer action differs.

---

## The blueprint's own catalogue, used as a cross-check

Pages p161–p162 carry a table of all 28 connectors under the heading *"28 connectors.
Ships today = a manifest exists at 2.261.3 and its name does not change."* For my nine it
says:

| Catalogue row | Key | Status | Shape it claims | What I measured from the CFG image | Agrees? |
|---|---|---|---|---|---|
| Paymentus | `pay_paymentus` | New | 4 fields · 4 ops | 4 Connection-details fields · 4 ops | yes |
| US Payments | `pay_uspayments` | New | 4 fields · 4 ops | 4 · 4 | yes |
| WorldPay | `pay_worldpay` | New | 4 fields · 4 ops | 4 · 4 | yes |
| Global Payments | `pay_globalpayments` | New | 4 fields · 4 ops | 4 · 4 | yes |
| Payment kiosk network | `payments_kiosk` | Ships today | 2 fields · 3 ops | 2 · 3 | yes |
| Test payments (sandbox) | `payments_sandbox` | Ships today | 1 fields · 3 ops | 1 · 3 | yes |
| Aclarian | `erp_aclarian` | New | 4 fields · 3 ops | 4 · 3 | yes |
| Workday | `erp_workday` | New | 4 fields · 3 ops | 4 · 3 | yes |
| SAP | `erp_sap` | New | 4 fields · 3 ops | 4 · 3 | yes |

**Every count agrees**, on one reading of *field* that the catalogue never states and that
this document therefore states for it: **the catalogue counts the `Connection details`
panel and nothing else.** It excludes *Where it runs*, which every one of the 28 draws, and
for the four card processors it also excludes *Token address*, *Scope* and *Time*. So a
lane that builds *"4 fields"* for Paymentus and stops will be **four controls short of the
drawing**: the form draws eight. That is the one place the catalogue would mislead, and
the image wins.

Two disagreements of WORDING between the catalogue and the screens, both minor and both
resolved in the screen's favour because the screen is what a clerk reads:

* The catalogue writes **US Payments** and **Global Payments** as two words each; the page
  heads on CFG-12/VIEW-12 and CFG-14/VIEW-14 draw **USPayments** and **GlobalPayments** as
  one. The summary sentence under each head uses the two-word form, so one screen draws
  both spellings of its own vendor's name.
* The sandbox row reads *"1 fields · 3 ops"*.

Two disagreements of STATUS, recorded against the repository rather than against the
image, and both in the catalogue's favour — its claim holds:

* `payments_kiosk` and `payments_sandbox` are marked *Ships today* and both manifests do
  exist at those exact keys.
* The other seven are marked *New* and no manifest exists at any of those seven keys. The
  repository has 18 manifests; none of them is `pay_paymentus`, `pay_uspayments`,
  `pay_worldpay`, `pay_globalpayments`, `erp_aclarian`, `erp_workday` or `erp_sap`.

## The totals for these nine

* **31 operations drawn.** 6 exist in a manifest at the drawn key (the kiosk's three and
  the sandbox's three). **25 operations are MISSING.**
* **40 fields MISSING.** 28 across the four card processors (seven each: Merchant ID,
  Merchant secret, Client ID, Card page, Token address, Scope, Time) and 12 across the
  three finance systems (four each: Their client id, What they may read, Allowed
  addresses, The key for them to use).
* **0 fields and 0 operations are MISSING on the kiosk and the sandbox.** Those two match
  the drawing control for control and operation for operation, including two not-required
  marks and three direction words.
* **0 EXTRA.** Nothing in `payments_kiosk` or `payments_sandbox` is absent from its
  drawing.
* **31 of 31 drawn operations carry a rate limit with nowhere to store it.**
  `registry.Operation` has 23 attributes and not one of them is a rate limit.
* Adding these seven connectors is **seven files and seven names** in
  `06-backend/apps/integrations/manifests/__init__.py`, no migration and no screen —
  `BR-INT-037` holds for every one of them. A new `category` value of `erp` needs no code
  either; `Manifest.category` is free text and the filter chips are generated from it.

---

# Needs a ruling

Eight items. Each says what the drawing shows, what the repository says, why they cannot
both be true, and the smallest question that settles it. The questions are written to be
read aloud.

### 1 · Is the finance partner called Aclarian a real company?

**What the drawing shows.** Connector 17 of 28 is called *Aclarian*, with its own set-up
screen, its own view screen and its own key, `erp_aclarian`.

**What the repo says.** Page 143 of the same blueprint raises this against itself, in
these words: *"When you said 'Aclarian', did you mean Aclara, the meter vendor? Here that
word is a partner we made up for worked examples. If a fixture name has drifted into the
build list, better caught now. If you did mean Aclara, it is an eighth integration and we
have nothing."* The name appears in our own worked examples as an invented finance
partner; Aclara is a real meter-reading vendor.

**Why they cannot both be true.** A connector on the build list is a real company a real
utility connects to. A name we invented for a worked example is not, and building it costs
a manifest, a set-up screen and a place in the catalogue for a partner that does not
exist.

**The question.** One of the 28 connectors on the list is called Aclarian. We invented
that name ourselves, for examples — no such finance company exists. There is a real meter
company called Aclara with a very similar name. Did you mean the meter company, or should
that connector come off the list and leave 27?

### 2 · May one connector hold two live secrets?

**What the drawing shows.** On all four card processors the clerk types a *Merchant
secret* — *"Typed once, never shown again. Stored encrypted."* — and then, further down
the same form, presses *Generate token* and we hold a token as well. Both are live at
once: the view screen shows the token with a generated date and an expiry three months
later, while the merchant secret is still what proves who we are.

**What the repo says.** A connection may hold exactly **one** live secret, and that is
enforced by the database, not by our code — one active credential per connection, with
rotation writing the next version and switching the old one off.

**Why they cannot both be true.** Two secrets alive on one connector is precisely the
thing the database refuses. Nothing can be saved on any of the four screens as drawn.

**The question.** Each of the four card companies needs two secrets at the same time: a
password you type, and a token we then ask them for. Our system allows one per connection.
Do we allow two, or do we throw the typed password away the moment we have the token?

### 3 · Do we enforce the call limits we show, or only display them?

**What the drawing shows.** Every operation on every one of the nine — 31 of them — shows
a cap in calls per minute. The card processors say *"These are the limits they allow us"*.
The kiosk and the three finance systems say the opposite: *"These are the limits we allow
them."* The sandbox says both at once.

**What the repo says.** There is nowhere to put the number. An operation in our registry
declares 23 things and a rate limit is not one of them, and no code path anywhere counts
calls.

**Why they cannot both be true.** A limit *we allow them* is a promise to refuse. Showing
a number on screen that nothing enforces is a check that cannot fail — the single failure
shape this repository has filed more defects against than any other.

**The question.** The screens promise a finance system it may read from us 300 times a
minute. Do we actually refuse the 301st call in a minute, or is the number only there to
tell them what we expect?

### 4 · May a customer type a card number on our page?

**What the drawing shows.** Every one of the four card processors draws a required choice
labelled *Card page* with exactly two options: *hosted by them* or *embedded*. *Embedded*
means the card number is typed into our page rather than the vendor's.

**What the repo says.** Nothing. No field, rule or decision anywhere in the repository
mentions this choice, and no signed rule says which side of the card-industry audit
boundary we intend to sit on.

**Why they cannot both be true.** They are not in conflict — this is the third kind of
thing that legitimately reaches you: a fact only you hold. The choice changes what an
auditor asks of the whole product, not only of this screen, and it is offered to a clerk
on four screens as a two-click toggle.

**The question.** Each card company's set-up screen lets a clerk choose where the customer
types their card number: on the card company's page, or on ours. Choosing ours puts this
whole product inside the card-industry audit. Do we offer both choices, or only the card
company's page?

### 5 · Does a blank permission box mean everything?

**What the drawing shows.** On all four card processors the *Scope* box sits empty, under
the words *"Leave blank for everything the key allows"*.

**What the repo says.** A signed law of this repository, learned from two blocked live
deployments: the unsafe option must be the one you type. Blank means the widest possible
permission here, and blank is what a clerk who reads nothing will leave.

**Why they cannot both be true.** The drawing's default is the widest permission; the law
says the default must be the narrowest.

**The question.** On each card company's set-up screen there is a box that says what we
are allowed to ask them for. Leaving it empty asks for everything. Should empty mean
everything, or should a clerk have to name what we need before they can save?

### 6 · What happens to a key already issued on the connector these five replace?

**What the drawing shows.** Three of my nine — Aclarian, Workday and SAP — are finance
systems, and the blueprint's own change list says the five finance systems replace one
existing connector called *Third-party GL*, adding: *"Any partner already holding an
issued key is on a connector that no longer exists by that name."*

**What the repo says.** *Third-party GL* is **live today** — it is one of the 18 manifests,
it is the one connector that issues keys to partners, and the key is issued against the
connection row, which carries the old key `gl_partner`.

**Why they cannot both be true.** The five new connectors are five new keys, so every key
already issued belongs to a connector that will not be in the list. The row cannot say
which of the five the utility actually uses; only the utility can.

**The question.** Five named finance systems replace the one connector we call Third-party
GL today. If a utility has already given a key to their finance system on the old one, do
we move that key across to whichever of the five they name, or do we switch it off and
make them issue a new one?

### 7 · Do we show a nightly time that nothing acts on?

**What the drawing shows.** Each of the four card processors draws a *When it runs* panel
with a time box showing 01:00 and the words *"Your time zone. The only part you choose."*
The drawing then warns, in its own red note: *"nothing acts on the time today."*

**What the repo says.** The same — a connection stores a cadence word and a next-run
timestamp, and the blueprint's own evidence section records that no job ever fires a
connection on its schedule.

**Why they cannot both be true.** They agree about the fact and disagree about the screen.
A clerk who sets 01:00 on a live product has been told something will happen at one in the
morning, and nothing will.

**The question.** Each card company's set-up screen lets a clerk pick a nightly time, and
it shows one in the morning. Nothing in the product will act on it. Do we show the box and
say plainly that it does nothing yet, or leave the box out until the nightly run works?

### 8 · Does one key open every call, or one call each?

**What the drawing shows.** The view screens of the kiosk and of all three finance systems
draw a *Keys we issue* table with a column headed *MAY CALL*, whose one drawn row lists
two of the three calls and a *+1*. Beside it the drawing's own warning reads: *"May call is
new. Today one key opens every API on the connector."*

**What the repo says.** The same — a credential belongs to a connection, and there is no
column anywhere recording which calls a given key may make. One key opens all of them.

**Why they cannot both be true.** The column is drawn on four of my nine screens with real
content in it. Building the screen as drawn means building the per-key restriction behind
it; building only the screen means drawing a promise nothing keeps.

**The question.** The finance-system screens show a key that may make two of the three
calls we offer. Today any key we issue opens all three. Do we build keys that open only
the calls you choose, or do we keep one key per connector and say so on the screen?

---

## Two things routed elsewhere, deliberately not put to the Product Owner

1. **The same drawn word, two different recordings.** *They read* is drawn on the kiosk's
   account lookup and on all nine finance-system reads. The kiosk's manifest records it as
   data moving IN; `gl_partner`'s three reads record it as data moving OUT, with the same
   initiative. One is wrong. This is our own inconsistency, not a change to anything
   agreed, so the change process makes it a **defect**, and it matters beyond tidiness
   because the first operation's direction is what the card and the page head display.
   **For the triage lane.**
2. **A multiple choice in a single-value field.** *What they may read* is drawn as three
   chips a clerk picks among on all three finance systems; the nearest field we have is a
   single-value kind holding exactly those three options. Whether the field kind gains a
   multiple-choice variant is a build decision inside our own closed vocabulary of field
   kinds, with no money, no rule and no data behind it — the change process's fast path.
   **For the build lane.**

---

*Measured 2026-09-16 from `05-prototype/05 Integration Blueprint.pdf` (163 pages, on the
default branch) against the repository at `fb3ca0aa`. Nothing in this document was built,
fixed or decided.*
