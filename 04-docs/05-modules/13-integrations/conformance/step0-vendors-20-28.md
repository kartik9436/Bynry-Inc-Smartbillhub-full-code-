# Step 0 · Connectors 20–28 — what the blueprint draws, measured against what we have

**Lane scope:** the per-connector CONTENT of connectors 20 to 28 — which fields and which
operations each one draws. The shared screen SHAPE (the common regions of a configure form
and a view screen: the page head, the *APIs on this connector* table furniture, *Recent
activity*, the footer button row, *Where it runs*) is another lane's measurement and is
NOT re-measured here.

**Source, and how it was read.** `05-prototype/05 Integration Blueprint.pdf` on the
default branch (`origin/claude/confirm-understanding-3ktufc`), 163 pages, rendered to PNG
with `10-scripts/pdf/pdf_render.py` at scale 2 and read **as images**. That is B14 rule 42
— *"When you use images to create screens your accuracy is higher; hence dont create
screens using only Text"* — so no field below was taken from extracted text. Extracted
text was used for exactly two things, both of them index work: locating pages, and
confirming that the right-hand truncation seen in the renders is the DRAWING's own clip
rather than a rendering fault (it is the drawing's: glyphs stop at the frame edge).

**B14 rule 37** — *"Treat every number drawn in a wireframe as an illustration, never a
fact to build to"* — so `1,240 of 1,240`, `Today 04:12`, `····7Q2F`, `300 / min`,
`12 Aug 2026` and `api.vendor.example` are recorded as SHAPE and never as values. Where a
rate limit or a host appears in a table below it is there because the COLUMN exists, not
because the figure is right.

**Pages, verified against the images.** The document's index was correct for all nine.
Each screen is drawn across a page boundary, so the page named is where the screen STARTS:

| # | Connector | Key | CFG page | VIEW page |
|---|---|---|---|---|
| 20 | Infor | `erp_infor` | p072 → p073 | p073 → p074 |
| 21 | Microsoft Dynamics GP | `erp_msgp` | p074 → p076 | p076 → p077 |
| 22 | Accounting export file | `accounting_file` | p077 → p078 | p078 → p079 |
| 23 | Bank & lockbox file | `bank_lockbox_file` | p079 → p081 | p081 → p082 |
| 24 | Print vendor | `print_vendor` | p082 → p083 | p083 → p084 |
| 25 | Esri ArcGIS | `gis_esri` | p084 → p086 | p086 → p087 |
| 26 | Census geocoder | `geocoder_census` | p087 → p088 | p088 → p089 |
| 27 | Public map tiles | `map_tiles_public` | p089 → p090 | p090 → p091 |
| 28 | Single sign-on | `sso` | p091 → p092 | p092 → p093 |

**What we measured against.** `06-backend/apps/integrations/manifests/*.py` (18 manifests
exist; 28 are drawn) and `06-backend/apps/integrations/models.py`.

---

## 0 · The two manifests the drawing does not name, answered first

The brief asks whether `gis_city.py` and `gl_partner.py` are connectors of mine under a
new name, or genuinely extra. **They are opposite cases, and the catalogue on p162 answers
both in its own words.**

**`gis_city` IS connector 25 under a new name.** CFG-25's frame carries the badge
**RENAMED** and the screen's own panel says *"Renamed. Ships today under a generic name.
The connector, its fields and its operations do not change."* p162's *what is already
built and is now wrong* table says of `meters_neptune360, gis_city`: *"Renamed only.
Fields, operations and adapters are untouched — the safest two in the list."* The three
fields our `gis_city.py` declares (`base_url`, `tile_url`, `api_key`) are the three CFG-25
draws, in the drawn order, with the same three required/optional marks. So `gis_city` →
`gis_esri` is a key-and-display-name change and nothing else.

**`gl_partner` is NOT one of mine under a new name — it is the SHAPE that five named ERPs
each get a copy of, two of which are mine.** p162: *"gl_partner — 'Third-party GL', live,
issues keys → Replaced by five named ERPs. Any partner already holding an issued key is on
a connector that no longer exists by that name."* p161–p162 name the five: Aclarian,
Workday, SAP, **Infor**, **Microsoft Dynamics GP**. Our `gl_partner.py` summary is
*"Your finance system collects payments and bills from here."* — the sentence CFG-20 and
CFG-21 draw under their titles, word for word. Its four fields and three operations are
what both of my ERP screens draw. So `gl_partner` is genuinely extra as a CONNECTOR and
exactly right as a TEMPLATE, and **retiring it strands whatever partner holds its issued
key** (see *Needs a ruling*, item 1).

---

## 20 · Infor — `erp_infor`

CFG-20 p072–p073 · VIEW-20 p073–p074. Frame badge on CFG: **NEW CONNECTOR**. Frame badge
on VIEW: **PROPOSED**. Kind line drawn above the title: **ERP · THEY READ**. Summary drawn:
*"Your finance system collects payments and bills from here."* Panel drawn above the form:
*"New connector. Nothing is built for this vendor today — the fields below are the shape it
will take."*

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Their client id | single-line text | yes (red ∗) | Connection details (plain, red top rule) | `gl_partner.client_id`, same label | MATCHES (as a template; no `erp_infor` manifest exists) |
| 2 | What they may read | three-option chip group — `payments` · `bills` · `customers` | yes (red ∗) | Connection details (plain) | `gl_partner.scopes`, select, same three options, same label | MATCHES (as a template) |
| 3 | Allowed addresses | single-line text | yes (red ∗) | Connection details (plain) | `gl_partner.allowed_addresses`, same label | MATCHES (as a template) |
| 4 | The key for them to use | issued-key control — help line *"No key yet — save this connector, then issue one."* + button **Issue key** | no ∗ drawn | Connection details (plain) | `gl_partner.issued_key`, kind `issued_secret`, same label, `required=True` | DIFFERS — the drawing marks it optional, the manifest marks it required |
| — | Where it runs | two-option chip group — `Production` · `Sandbox` | no ∗ | Connection details (plain) | not a manifest field; it is `IntegrationConnection.environment`, and `BR-INT-026` makes live and sandbox TWO ROWS | MATCHES — and the catalogue agrees, counting 4 fields and not 5 |

Nothing else is drawn in the form. There is no *Token* panel and no *Sign-in on this
connector* panel on this screen: the key travels the other way.

### Table B — operations on the view screen

The CFG draws the same three rows without `LAST RUN`; the VIEW adds `LAST RUN` and
`RESULT`. Header row as drawn: `API · ENDPOINT` · `DIRECTION` · `WHEN` · `RATE LIMIT` ·
`LAST RUN` · (a further column truncated by the drawing's own frame — first letters `RE…`).

| # | Operation name as drawn | Direction (we collect / we send) | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Read payments | **They read** (neither; they dial us) | row chip `PROPOSED`; connector line `3 of 3 working`; connector state `Working` | `api.vendor.example` · `300 / min` · WHEN *They call us* | **ours** — `GET /partner/v1/payments`, key `serve_payment` (p157, p158) | `gl_partner.read_payments`, label **"Payments"** | DIFFERS — our label is *Payments*, the drawing and the naming table both say **Read payments**; our op name is `read_payments`, the format says `serve_payment` |
| 2 | Read bills | They read | `PROPOSED` | `api.vendor.example` · `300 / min` · *They call us* | **ours** — `GET /partner/v1/bills`, key `serve_bill` | `gl_partner.read_bills`, label **"Bills"** | DIFFERS — label and key, as row 1 |
| 3 | Read customers | They read | `PROPOSED` | `api.vendor.example` · `300 / min` · *They call us* | **ours** — `GET /partner/v1/customers`, key `serve_customer` | `gl_partner.read_customers`, label **"Customers"** | DIFFERS — label and key, as row 1 |

Two sentences are drawn under the table — *"All 3 use the address above."* and *"These are
the limits we allow them."* — and one warning panel: *"The API list and its rate limits are
set when we configure this connector — neither is a clerk control."* A second panel below
reads *"They start this one. There is no schedule — the trigger is their call."*

The VIEW adds a **Keys we issue** table (`KEY` · `MAY CALL` · `ISSUED` · `STATE`) with a
warning *"May call is new. Today one key opens every API on the connector."* — p154 records
that as a ruling of 14 Sep 2026 that **does** cost a schema change (a scope column and a
check at the door). Footer buttons drawn: **Keys we issue** · **Disconnect**.

**Verdict line:** **No.** The form itself can be built from the drawing alone — all four
fields exist on `gl_partner` and need only a new key and display name — but the *May call*
column on the issued key cannot, because one key opens every operation today and narrowing
it is a schema change nobody has sized.

---

## 21 · Microsoft Dynamics GP — `erp_msgp`

CFG-21 p074–p076 · VIEW-21 p076–p077. Frame badges: **NEW CONNECTOR** / **PROPOSED**.
Kind line **ERP · THEY READ**.

**The two ERP screens are drawn identically.** Field for field, operation for operation,
panel for panel, sentence for sentence — the only thing that differs between CFG-20 and
CFG-21 is the title, the route (`erp_infor` → `erp_msgp`) and nothing else. That is
recorded here as a measurement rather than assumed: both images were read in full.

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Their client id | single-line text | yes (red ∗) | Connection details (plain) | `gl_partner.client_id` | MATCHES (as a template) |
| 2 | What they may read | chips `payments` · `bills` · `customers` | yes (red ∗) | Connection details (plain) | `gl_partner.scopes` | MATCHES (as a template) |
| 3 | Allowed addresses | single-line text | yes (red ∗) | Connection details (plain) | `gl_partner.allowed_addresses` | MATCHES (as a template) |
| 4 | The key for them to use | issued-key control + **Issue key** | no ∗ | Connection details (plain) | `gl_partner.issued_key`, `required=True` | DIFFERS — optional drawn, required declared |
| — | Where it runs | `Production` · `Sandbox` | no ∗ | Connection details (plain) | `IntegrationConnection.environment` | MATCHES |

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Read payments | They read | `PROPOSED` · `3 of 3 working` · `Working` | `api.vendor.example` · `300 / min` · *They call us* | **ours** — `serve_payment` | `gl_partner.read_payments` label *Payments* | DIFFERS — label and key |
| 2 | Read bills | They read | `PROPOSED` | `api.vendor.example` · `300 / min` · *They call us* | **ours** — `serve_bill` | `gl_partner.read_bills` label *Bills* | DIFFERS — label and key |
| 3 | Read customers | They read | `PROPOSED` | `api.vendor.example` · `300 / min` · *They call us* | **ours** — `serve_customer` | `gl_partner.read_customers` label *Customers* | DIFFERS — label and key |

**Verdict line:** **No**, for exactly the reason connector 20 is no — the form is buildable
from the drawing, the *May call* scoping on the issued key is not.

---

## 22 · Accounting export file — `accounting_file`

CFG-22 p077–p078 · VIEW-22 p078–p079. Frame badge on CFG: **PROPOSED FORM**. Frame badge on
VIEW: **S142, FOR THIS CONNECTOR**. Kind line **ACCOUNTING · WE SEND**. Summary drawn:
*"Hand a journal file to your accounts system."* No *new connector* panel — this one ships.

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | What to call it | single-line text | yes (red ∗) | Connection details (plain, red top rule) | `label`, kind `text`, same label | MATCHES |
| 2 | Where the file goes | two chips — `download` · `drop` | yes (red ∗) | Connection details (plain) | `destination`, select `("download","drop")`, same label | MATCHES |
| 3 | File format | four chips — `qbo` · `xero` · `csv` · `iif` | yes (red ∗) | Connection details (plain) | `file_format`, select, same four in the same order | MATCHES |
| 4 | Folder host | single-line text, sample host shown | no ∗ | Connection details (plain) | `drop_host`, kind `host`, `required=False` | MATCHES |
| 5 | Folder username | single-line text | no ∗ | Connection details (plain) | `drop_username`, `required=False` | MATCHES |
| 6 | Folder path | single-line text | no ∗ | Connection details (plain) | `drop_path`, `required=False` | MATCHES |
| 7 | Folder password | secret, placeholder *"Typed once, never shown again"*, help *"Stored encrypted. Never shown again."* | no ∗ | Connection details (plain) | `drop_password`, kind `secret`, `required=False` | MATCHES |
| — | Where it runs | `Production` · `Sandbox` | no ∗ | Connection details (plain) | `IntegrationConnection.environment` | MATCHES |

**Seven fields drawn, seven declared, in the same order.** This is the closest match of the
nine. Note the drawing puts the four folder fields in a right/left two-column arrangement
rather than the one-per-row that the field list implies; per B14 rule 38 that is
CONSTRUCTION and the UI rules decide it, not this drawing.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Journal export | **We send** | `Working`; run result `1,240 of 1,240` | `api.vendor.example` · `60 / min` · WHEN *On demand* | **ours** — key `deliver_journal` (p157) | `export_journal`, label *"Journal export"* | DIFFERS — label matches exactly; our op NAME is `export_journal` where the drawn format gives `deliver_journal` |

Three further panels are drawn on the CFG and they are content, not furniture, so they are
recorded: **Sign-in on this connector** — *"No token here. This one signs in with the
details above, on every call."*, with a warning *"A token is generated on every connector
we dial that speaks over an API. This one does not — a file goes to a folder or a download,
and neither carries a token."* That is our `auth.mode == "none"`, drawn. And **When it
runs** — *"Nothing here runs on a clock. Every API on this connector is started by a
person, by a queue, or by them."*, with the warning *"…nothing acts on the time today, see
RAN-2."*

The VIEW draws **Key we hold** instead (`····7Q2F` · a date · `In use`) with the same *no
token on this one* warning, and the header chips `Ottumwa month-end · CSV` · `1 API` ·
`Working`. Footer buttons: **Test all** · **Replace key** · **Disconnect**.

**Verdict line:** **Yes** — every drawn field exists, with the right control, the right
options and the right optionality, and the one operation exists. The only change is the
operation's name, and a name is data.

---

## 23 · Bank & lockbox file — `bank_lockbox_file`

CFG-23 p079–p081 · VIEW-23 p081–p082. Frame badges: **PROPOSED FORM** / **S142, FOR THIS
CONNECTOR**. Kind line **BANKING · WE COLLECT**. Summary drawn: *"Import a statement or
lockbox file."*

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | What to call it | single-line text | yes (red ∗) | Connection details (plain, red top rule) | `label` | MATCHES |
| 2 | File format | six chips — `bai2` · `camt053` · `csv` · `ofx` · `qbo` · `qfx` | yes (red ∗) | Connection details (plain) | `file_format`, select, the same six in the same order | MATCHES |
| 3 | Where it comes from | two chips — `upload` · `sftp` | yes (red ∗) | Connection details (plain) | `source`, select `("upload","sftp")` | MATCHES |
| 4 | Folder host | single-line text, sample host | no ∗ | Connection details (plain) | `sftp_host`, kind `host`, `required=False` | MATCHES |
| 5 | Folder username | single-line text | no ∗ | Connection details (plain) | `sftp_username`, `required=False` | MATCHES |
| 6 | Folder path | single-line text | no ∗ | Connection details (plain) | `sftp_path`, `required=False` | MATCHES |
| 7 | Folder password | secret, *"Typed once, never shown again"*, help *"Stored encrypted. Never shown again. This key is used by all 2 APIs."* | no ∗ | Connection details (plain) | `sftp_password`, kind `secret`, `required=False` | MATCHES |
| 8 | Which column is which | a SECTION rather than an input — the only body text drawn is *"This part appears once a file has been seen."* | no ∗ | Connection details (plain) | `column_mapping`, kind `mapping_editor`, `required=True` | DIFFERS — optional drawn, required declared; and the drawing shows it EMPTY with a stated absence, which our `required=True` would refuse on save |
| — | Where it runs | `Production` · `Sandbox` | no ∗ | Connection details (plain) | `IntegrationConnection.environment` | MATCHES |

**Eight fields drawn, eight declared, same order.** The drawn ordering differs from the
manifest only in that the drawing puts `File format` in the right column beside `What to
call it`, and `Where it comes from` in the left column beside `Folder host`; the manifest's
sequence is label → file_format → source → folder fields, which reads down the same list.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Bank statement | **We collect** | `Working`; run results drawn | `api.vendor.example` · `60 / min` · WHEN *On demand* | **ours** — key `fetch_statement` (p157) | `import_statement`, label *"Bank statement"* | DIFFERS — label matches; our op NAME is `import_statement` where the drawn format gives `fetch_statement` |
| 2 | Lockbox file | **We collect** | `Working` | `api.vendor.example` · `60 / min` · *On demand* | **ours** — and **the naming table on p157 does not list it** | `import_lockbox`, label *"Lockbox file"* | NEEDS A RULING — the format says `<runner>_<noun>`, `fetch_lockbox` is the obvious reading, and p157 simply does not draw a row for it |

The VIEW header chips read `Chase operating · BAI2` · `2 APIs` · `Working`, and the
**Key we hold** panel says *"One key. All 2 APIs use it."* Footer: **Test all** ·
**Replace key** · **Disconnect**.

**Verdict line:** **Yes** — all eight fields and both operations exist, with the six codecs
and two sources drawn exactly as declared. Two names move and one of them (`Lockbox file`)
has no row in the naming table to move to.

---

## 24 · Print vendor — `print_vendor`

CFG-24 p082–p083 · VIEW-24 p083–p084. Frame badge on CFG: **NEEDS A VENDOR NAME**. Frame
badge on VIEW: **PROPOSED**. Kind line **PRINT · WE SEND**. Summary drawn: *"Hand the
printed batch to a mailing house."* A panel above the form reads *"Still generic. You have
not named a vendor for this one — it keeps a category name until you do."*

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | API key | secret, *"Typed once, never shown again"*, help *"Stored encrypted. Never shown again."* | yes (red ∗) | Connection details (plain, red top rule) | `api_key`, kind `secret` | MATCHES |
| 2 | Your account with them | single-line text | yes (red ∗) | Connection details (plain) | `account_reference`, kind `text`, same label | MATCHES |
| — | Where it runs | `Production` · `Sandbox` | no ∗ | Connection details (plain) | `IntegrationConnection.environment` | MATCHES |
| 3 | Token address | single-line text, sample host | **yes (red ∗)** | **Token** (plain, its own panel below the API list) | **nothing** | **MISSING** |
| 4 | Scope | single-line text, placeholder *"Leave blank for everything the key allows"* | no ∗ | **Token** (plain) | **nothing** | **MISSING** |

The Token panel also draws a body sentence *"We generate one token for this connector and
every API authenticates with it."*, a stated absence *"No token yet — save this connector,
then generate one."*, a button **Generate token**, and a closing sentence *"One token. All
1 API use it. It is shown once and afterwards only regenerated."* The VIEW replaces it with
**Token we hold** — `····7Q2F` · *generated <date>* · *expires <date>* · `In use` — and the
footer reads **Test all** · **Regenerate token** · **Disconnect**.

**This is the largest per-connector gap in my nine, and it is a contradiction rather than
an omission.** Our manifest declares `auth = Auth(mode="we_hold_theirs", placement="header")`
— the mailing house gives us a key and we put it in a header. The drawing declares a
generated token with its own address, its own scope, its own expiry and its own regenerate
button, which is an exchange we perform, not a key they hand us. **Both cannot be true of
one connector**, and p155 says why it matters: *"A connector that holds a client secret AND
a generated token is holding two live credentials, and the table allows one — so the thing
that blocked five payment processors now stands in front of thirteen connectors."*

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Print hand-over | **We send** | `Working`; header chip `Account 88214` · `1 API` | `api.vendor.example` · `120 / min` · WHEN **When queued** | **ours** — key `deliver_print_batch` (p157) | `hand_over_batch`, label *"Print hand-over"* | DIFFERS — label matches; our op NAME is `hand_over_batch` where the format gives `deliver_print_batch` |

**Verdict line:** **No.** Two of the four drawn fields — *Token address* and *Scope* — do
not exist anywhere in our manifest, and adding them contradicts this connector's declared
credential mode and collides with the one-active-credential rule the database enforces.

---

## 25 · Esri ArcGIS — `gis_esri` (our `gis_city`)

CFG-25 p084–p086 · VIEW-25 p086–p087. Frame badge on CFG: **RENAMED**. Frame badge on
VIEW: **S142, FOR THIS CONNECTOR**. Kind line **MAPS · WE COLLECT**. Summary drawn:
*"Find an address and keep parcels in step."* Panel above the form: *"Renamed. Ships today
under a generic name. The connector, its fields and its operations do not change."*

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Service address | single-line text, sample host | yes (red ∗) | Connection details (plain, red top rule) | `gis_city.base_url`, kind `host`, same label, required | MATCHES |
| 2 | Map tile server | single-line text, sample host | no ∗ | Connection details (plain) | `gis_city.tile_url`, kind `host`, `required=False`, same label | MATCHES |
| 3 | API key | secret, *"Typed once, never shown again"*, help *"Stored encrypted. Never shown again. This key is used by all 3 APIs."* | no ∗ | Connection details (plain) | `gis_city.api_key`, kind `secret`, `required=False` | MATCHES |
| — | Where it runs | `Production` · `Sandbox` | no ∗ | Connection details (plain) | `IntegrationConnection.environment` | MATCHES |
| 4 | Time | a time input, help *"Your time zone. The only part you choose."* | no ∗ | **When it runs** (plain, its own panel) | **nothing** — `reconcile_parcels` carries `trigger="scheduled"` and no hour | **MISSING** |

The *When it runs* panel on this screen reads *"1 of 3 run on a clock. The rest are started
by a person, by a queue, or by them."* — the only one of my nine that says anything but
*nothing here runs on a clock*. It carries the same warning as the rest: *"…nothing acts on
the time today, see RAN-2."* p093 states that gap plainly: *"is accepted, validated, saved
… and nothing will ever read it."*

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Address search | **We collect** | `Refused` + a **Retry** action and a reason sentence (the only non-green result in my nine) | `gis.ottumwa.example` · `600 / min` · WHEN **While you wait** | **ours** — **not listed on p157** | `address_search`, label *"Address search"* | MATCHES on label and shape; NEEDS A RULING on the key |
| 2 | Reconcile parcels | **We collect** | `Worked` | `gis.ottumwa.example` · `10 / min` · WHEN **Nightly** | **ours** — key `fetch_parcel` (p157) | `reconcile_parcels`, label **"Nightly parcel check"** | DIFFERS — our label is *Nightly parcel check*, the drawing and the naming table both say **Reconcile parcels** |
| 3 | Map tiles | **We collect** | `Worked` | `tile.arcgisonline.example`, tagged **ITS OWN HOST** on the CFG and **2ND HOST** on the VIEW · `600 / min` · WHEN **While you wait** | **ours** — **not listed on p157** | `map_tiles`, `host_field="tile_url"` | MATCHES on shape; **the tag is drawn with two different words on the two screens** |

Under the table the CFG draws *"1 of these calls a different address. Only that one is
editable."* and *"These are the limits they allow us."* — note *they allow us*, where the
ERP screens say *we allow them*, which is the direction flipping the sentence and is drawn
correctly on both.

**The two-host flag on p155, recorded and not resolved:** *"Esri ArcGIS runs two different
hosts today. Its map-tile operation carries `host_field="tile_url"` while the rest use
`base_url` — one connector, two APIs, two addresses."* Our `gis_city.py` already does
exactly that, and its own comment records `DEF-INT-4259` as the defect that taught it. So
the flag describes the shipped state accurately and nothing about it is new.

**Verdict line:** **No.** All three fields and all three operations exist and match, but
the *Time* input in *When it runs* has nowhere to be stored on this connector and — by the
document's own words and by `RAN-2` — nothing would read it if it did.

---

## 26 · Census geocoder — `geocoder_census`

CFG-26 p087–p088 · VIEW-26 p088–p089. Frame badges: **PROPOSED FORM** / **S142, FOR THIS
CONNECTOR**. Kind line **MAPS · WE COLLECT**. Summary drawn: *"Turn an address into a
point."*

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Service address | single-line text, sample host | yes (red ∗) | Connection details (plain, red top rule) | `base_url`, kind `host`, same label | MATCHES |
| — | Where it runs | `Production` · `Sandbox` | no ∗ | Connection details (plain) | `IntegrationConnection.environment` | MATCHES |

One field drawn, one declared. There is no secret, no token and no folder.

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Geocode addresses | **We collect** | `Working`; header chip `geocoding.geo.census.gov` · `1 API` | `api.vendor.example` · `60 / min` · WHEN **On demand** | **ours** — **not listed on p157** | `geocode_address`, label *"Geocode addresses"* | MATCHES on label and shape; NEEDS A RULING on the key |

The VIEW draws **Sign-in on this connector** — *"No password is stored for this
connector."* — which is our `auth.mode == "none"`, and a footer of **Test all** ·
**Disconnect** with no key button, which is right for a connector holding no credential.

**Verdict line:** **Yes** — one field, one operation, both drawn exactly as declared. The
only open thing is the operation's key, which the naming table does not draw.

**The p146 flag, recorded and not resolved.** The document's own routing table says
*"Bulk email, print vendor, census geocoder offered as live with no connector — **Defect** —
A card a utility can press that cannot work."* Our `geocoder_census.py` says the opposite in
its docstring: the outbound call exists in `apps/metering/geocode.py` today and wave M gave
it the connection row. Two of the three named there are mine (print vendor, census
geocoder) and the third is not.

---

## 27 · Public map tiles — `map_tiles_public`

CFG-27 p089–p090 · VIEW-27 p090–p091. Frame badges: **PROPOSED FORM** / **S142, FOR THIS
CONNECTOR**. Kind line **MAPS · WE COLLECT**. Summary drawn: *"The background picture under
the map."*

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Tile server | single-line text, sample host | yes (red ∗) | Connection details (plain, red top rule) | `base_url`, kind `host`, label **"Tile server"** | MATCHES |
| — | Where it runs | `Production` · `Sandbox` | no ∗ | Connection details (plain) | `IntegrationConnection.environment` | MATCHES |

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Map tiles | **We collect** | `Working`; header chip `server.arcgisonline.com` · `1 API` | `api.vendor.example` · `600 / min` · WHEN **While you wait** | **ours** — **not listed on p157** | `map_tiles`, executor `browser` | MATCHES on label and shape; NEEDS A RULING on the key |

The VIEW draws **Sign-in on this connector** — *"No password is stored for this
connector."* — and the footer **Test all** · **Disconnect**.

**Verdict line:** **Yes** — one field, one operation, drawn as declared. Nothing on this
screen needs a decision except the operation's key.

---

## 28 · Single sign-on — `sso`

CFG-28 p091–p092 · VIEW-28 p092–p093. Frame badge on CFG: **NEEDS A VENDOR NAME**. Frame
badge on VIEW: **PROPOSED**. Kind line **SIGN-IN · THEY SEND**. Summary drawn: *"Staff sign
in with your own identity provider."* **Two** panels are drawn above the form: *"Still
generic. You have not named a vendor for this one — it keeps a category name until you
do."* and *"Coming soon · v2 — not built yet."*

### Table A — fields on the configure form

| # | Label as drawn | Control | Required | Panel it sits in (and its tone) | In our manifest today | Verdict |
|---|---|---|---|---|---|---|
| 1 | Identity provider address | single-line text, sample host | yes (red ∗) | Connection details (plain, red top rule) | `metadata_url`, kind `host`, label **"Identity provider address"** | MATCHES |
| 2 | Sign in with your identity provider | a BUTTON, under the help sentence *"You will be sent to your identity provider and brought back here. We never see or store your password."* | not applicable | Connection details (plain) | `sign_in`, kind `redirect`, label **"Sign in with your identity provider"**, `required=True` | DIFFERS — the manifest declares it a required FIELD; the drawing draws it as a control with no required mark |
| — | Where it runs | `Production` · `Sandbox` | no ∗ | Connection details (plain) | `IntegrationConnection.environment` | MATCHES |

### Table B — operations on the view screen

| # | Operation name as drawn | Direction | State word drawn | Endpoint as drawn | Ours or theirs | In our manifest today | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Sign in | **They send** | `Working`; header chip `idp.ottumwa-water.example` · `1 API` | `api.vendor.example` · `600 / min` · WHEN **While you wait** | **ours** — `/auth/saml/acs`, key `inbound_sign_in` (p158), and p158 calls it *"the one exception"* to the `/partner/v1/…` shape | `sign_in`, label *"Sign in"*, `initiative="them"`, `respond_after="authenticate"` | DIFFERS — label and direction match; our op NAME is `sign_in` where the format gives `inbound_sign_in` |

The CFG draws the same *"They start this one. There is no schedule — the trigger is their
call."* panel the two ERP screens carry, which is right for an inbound door. The VIEW draws
**Sign-in on this connector** — *"There is no password here. You sign in with the provider
and we keep only the permission they give us."* — and a footer of **Re-authorise now** ·
**Disconnect**, which is the only footer of my nine with a re-authorise button.

**Verdict line:** **Yes** — both drawn fields exist with the drawn labels and kinds, and the
one operation exists with the right direction. The screen is drawn *Coming soon · v2 — not
built yet*, so building the form is drawing a form that refuses, which is what the drawing
asks for.

---

## Our own API naming

From p156, p157 and p158, **as drawn**. The PO has already ruled we use the format we own,
so this is recorded verbatim rather than proposed.

p156 opens: *"Forty of the seventy-eight operations drawn here are ours to define, because
data leaving us is in our shape. A name is the cheapest thing to get wrong and the most
expensive to change, so it is settled before anything is built rather than after five
vendors are live on it."*

### Four artefacts

| Artefact | Shape | Examples |
|---|---|---|
| Operation key, on the manifest | `<runner>_<noun>` | `deliver_message` · `fetch_reading` · `inbound_payment` · `serve_bill` |
| Clerk label, on screen | verb first, three words or fewer | Send messages · Collect readings · Read bills |
| Partner endpoint, for the two doors where they dial us | `/partner/v1/<plural noun>` | `GET /partner/v1/bills` · `POST /partner/v1/payments` |
| Payload contract, for the two doors where we dial out | `<noun>.v<n>` | `message.v1` · `journal.v1` · `charge.v1` |

Drawn above the table: *"The verb is the runner that executes it, so an operation key tells
you which of the four doors it goes through before you open a single file."*

### The four verbs are the four runners, which already exist

| Verb | Door | Runner in the repo | Reads as |
|---|---|---|---|
| `fetch` | We collect · in · us | `runners/fetch.py` | we dial them, data comes in |
| `deliver` | We send · out · us | `runners/deliver.py` | we dial them, data goes out |
| `inbound` | They send · in · them | `inbound.py` | they dial us, data comes in |
| `serve` | They read · out · them | `runners/serve.py` | they dial us, data goes out |

And the rule under it: **"Singular in a key, plural in a URL."** A key names one record —
`serve_bill` — because that is what a step handles. A path names a collection —
`/partner/v1/bills` — because that is what a partner asks for.

### The eight outward endpoints — the whole of what we publish

Drawn above the table: *"Eight endpoints, and they are the whole of what we publish outward
today. One base URL, the same for every partner."*

| Method and path | Door | Who calls it | Operation key |
|---|---|---|---|
| `GET /partner/v1/payments` | They read | the five ERPs | `serve_payment` |
| `GET /partner/v1/bills` | They read | the five ERPs | `serve_bill` |
| `GET /partner/v1/customers` | They read | the five ERPs | `serve_customer` |
| `GET /partner/v1/accounts/{account_no}` | They read | the kiosk network | `serve_account` |
| `POST /partner/v1/payments` | They send | the kiosk network | `inbound_payment` |
| `POST /partner/v1/payment-returns` | They send | the kiosk network | `inbound_payment_return` |
| `POST /partner/v1/delivery-receipts` | They send | Bulk email · Twilio | `inbound_delivery_receipt` |
| `/auth/saml/acs` — **the one exception** | They send | the identity provider | `inbound_sign_in` |

⚠ **DATED NOTE, 2026-09-17 — `GET /partner/v1/customers` IS NOW
`GET /partner/v1/accounts` (`DEF-INT-5623`), AND THE TABLE IS LEFT AS DRAWN.**
This file records what the BLUEPRINT draws and what our manifests held when it was
audited; editing the drawn column would stop it being evidence. What changed in the
product: the PO, looking at the live deployment, ruled that the partner surface must
call an account an account — *"it should be account and not customer - theya re
lookung for details for accounts not customer id"* — and the values were already the
account's by the ruling of 2026-09-16, *"Customers = accounts"*. The old address stays
registered and answers `410` naming the new one (`partner_api.RETIRED_FOR`).

⚠ **AND THE DRAWING'S OWN ROW FOUR IS WORTH READING BESIDE IT.** The blueprint already
writes `GET /partner/v1/accounts/{account_no}` with the key `serve_account`, for one
account at a time — which is the same fact our `GET /partner/v1/consumer-info` serves,
under Invoice Cloud's word for it. `consumer-info` keeps their spelling because their
document does; that our own operation is still called `serve_customer` and not
`serve_account` is measured and owed in **`OQ-INT-12405`** — it is stored on every
issued key's scope, on every run row and under a unique constraint, so it is a data
migration rather than a rename.

⚠ **DATED NOTE, 2026-09-17 — THE THREE `POST` ROWS ABOVE ARE THE KIOSK'S AND THE BULK-EMAIL
PROVIDER'S, AND THEY ARE **NOT** A LICENCE TO BUILD A PARTNER PAYMENT POST (`CR-111-BRC04`,
`BR-INT-071`).** The Product Owner ruled that day, on a question put against Invoice Cloud's
`POST /api/partner/v1/make-payment/`: *"Can a partner post a payment at all? - I want to use batch
run  to take payment feed from Them - not online updates"*. **`POST /api/partner/v1/make-payment/`
is not built and the payment feed arrives as a BATCH on a schedule.**

**THE TABLE ABOVE IS NOT CORRECTED, BECAUSE IT IS A MEASUREMENT OF A DRAWING AND CORRECTING A
MEASUREMENT IS FALSIFYING IT.** It records what the Integration Blueprint draws, and the blueprint
draws those three `POST` rows for a DIFFERENT RELATIONSHIP: the kiosk network and the bulk-email
provider, the `inbound_*` shape governed by `BR-INT-058` (*they push: the door and the work are two
separate acts*), ruled by `OQ-INT-1729` option (a) on 2026-09-06 and **already BUILT** at
`POST /api/{utility}/integrations/inbound/{key}/{operation}` since `2.202.0` — a different address
from the one drawn here.

**A signature covers only what was shown.** The Product Owner was shown Invoice Cloud's
`make-payment` and was not asked again about a door they ruled eleven days earlier, so the
2026-09-17 ruling does not retire the kiosk's door. **What it does settle is that the five
`/api/partner/v1/…` addresses stay five and stay `GET`.** A lane reading this table as a plan for
the partner surface would build the one thing that ruling refuses.

**Three of the eight belong to my nine** — the first three, which Infor and Microsoft
Dynamics GP both call — **and a fourth is connector 28's**, `/auth/saml/acs`. The drawing
explains why sign-in sits outside `/partner`: *"It is a browser redirect carrying an
assertion, not a machine calling an API with a key, so putting it on the partner surface
would be a shape it does not have."*

**Rule 1 as drawn: the tenant never appears in a partner URL.** *"Three hops, all on the
server, none of them from the request: the partner presents a key, the key belongs to one
connection, and the connection belongs to one tenant."*

### What the naming table gives my nine, and what it leaves out

| Connector | Drawn operation | Key on p157 | Our manifest's name today |
|---|---|---|---|
| Infor · MS Dynamics GP | Read payments | `serve_payment` | `read_payments` |
| Infor · MS Dynamics GP | Read bills | `serve_bill` | `read_bills` |
| Infor · MS Dynamics GP | Read customers | `serve_customer` | `read_customers` |
| Accounting export file | Journal export | `deliver_journal` | `export_journal` |
| Bank & lockbox file | Bank statement | `fetch_statement` | `import_statement` |
| Bank & lockbox file | Lockbox file | **not drawn** | `import_lockbox` |
| Print vendor | Print hand-over | `deliver_print_batch` | `hand_over_batch` |
| Esri ArcGIS | Reconcile parcels | `fetch_parcel` | `reconcile_parcels` |
| Esri ArcGIS | Address search | **not drawn** | `address_search` |
| Esri ArcGIS | Map tiles | **not drawn** | `map_tiles` |
| Census geocoder | Geocode addresses | **not drawn** | `geocode_address` |
| Public map tiles | Map tiles | **not drawn** | `map_tiles` |
| Single sign-on | Sign in | `inbound_sign_in` (from the endpoint table) | `sign_in` |

**Thirteen operations across my nine. Eight have a key drawn for them; five do not** — and
all five of the missing ones are `fetch` calls that dial out to a map or address service.

---

## Cross-check against the document's own catalogue (p161–p162)

Used only as a check on my own count. **Where they disagree, the image wins and the
disagreement is reported.**

| # | Connector | Key | Catalogue status | Catalogue count | Counted from the CFG image | Agrees? |
|---|---|---|---|---|---|---|
| 20 | Infor | `erp_infor` | **New** | 4 fields · 3 ops | 4 fields · 3 ops | yes |
| 21 | Microsoft Dynamics GP | `erp_msgp` | **New** | 4 fields · 3 ops | 4 fields · 3 ops | yes |
| 22 | Accounting export file | `accounting_file` | **Ships today** | 7 fields · 1 ops | 7 fields · 1 op | yes |
| 23 | Bank & lockbox file | `bank_lockbox_file` | **Ships today** | 8 fields · 2 ops | 8 fields · 2 ops | yes |
| 24 | Print vendor | `print_vendor` | **Needs a name** | 2 fields · 1 ops | **4 fields** · 1 op | **NO** |
| 25 | Esri ArcGIS | `gis_esri` | **Renamed** | 3 fields · 3 ops | **4 fields** · 3 ops | **NO** |
| 26 | Census geocoder | `geocoder_census` | **Ships today** | 1 fields · 1 ops | 1 field · 1 op | yes |
| 27 | Public map tiles | `map_tiles_public` | **Ships today** | 1 fields · 1 ops | 1 field · 1 op | yes |
| 28 | Single sign-on | `sso` | **Needs a name** | 2 fields · 1 ops | 2 fields · 1 op | yes |

**Two disagreements, and both are the same mistake in the same place: the catalogue counts
only the *Connection details* panel, and the drawing puts real inputs OUTSIDE it.**

- **Print vendor.** The catalogue counts 2 — `API key` and `Your account with them`, both in
  Connection details. CFG-24 also draws **Token address** (required) and **Scope** in a
  *Token* panel further down the same form, which a clerk must fill in before the connector
  works. Four inputs, not two.
- **Esri ArcGIS.** The catalogue counts 3 — `Service address`, `Map tile server`, `API key`.
  CFG-25 also draws a **Time** input in the *When it runs* panel. Four inputs, not three.

The catalogue is right about every count where the whole form sits in one panel, and wrong
for exactly the two connectors that draw an input anywhere else. It agrees with the image on
all nine operation counts.

One further note on the catalogue's own words, recorded because it bears on connector 25:
*"Ships today = a manifest exists at 2.261.3 and its name does not change."* Under that
definition `gis_esri` is correctly marked **Renamed** rather than *Ships today*, and
`accounting_file`, `bank_lockbox_file`, `geocoder_census` and `map_tiles_public` are
correctly marked **Ships today** — all four have manifests in our tree today.

---

## The three flags in the document, recorded and NOT resolved

**p155 — Esri ArcGIS runs two different hosts.** Verbatim: *"Esri ArcGIS runs two different
hosts today. Its map-tile operation carries `host_field="tile_url"` while the rest use
`base_url` — one connector, two APIs, two addresses."* Our `gis_city.py` already declares
exactly this, and records `DEF-INT-4259` in its own comment as the defect that caused it —
the generated page policy was permitting the address service instead of the tile server.
The same page carries the harder half: *"The real limit is the credential, not the API …
Manifest.auth is a single Auth, and the database enforces one active credential per
connection."* That is the thing print vendor's drawn Token panel walks into.

**p146 — bulk email, print vendor and census geocoder offered as live with no vendor
named.** The document's own routing table classifies it **Defect**, with the reason
*"A card a utility can press that cannot work."* Two of the three are mine. Our tree
disagrees on one of them: `geocoder_census.py` says the outbound call already exists in
`apps/metering/geocode.py` and that wave M gave it the connection row. It does not disagree
on print vendor, whose frame badge is **NEEDS A VENDOR NAME** on the drawing and whose
`test_action` is `None` in our manifest — a card with no safe test and no named vendor.

**p154, p156, p157, p158 — nomenclature.** Recorded above in full, verbatim as drawn. The
one thing p154 adds that belongs here: of the three rulings of 14 Sep 2026, two cost
nothing but drawing and the third — *should an issued key name the APIs it may call?*,
ruled **Yes** — *"costs a schema change: a scope column and a check at the door."* That is
the *May call* column on both my ERP screens.

---

## Needs a ruling

Eight items. Each says what the drawing shows, what the repo says, why they cannot both be
true, and the smallest question that settles it — in plain English, with a figure, and with
no IDs, because that is what a ruling has to be readable as.

**1 · The print vendor's screen asks for a login the connector cannot hold.**

*What the drawing shows.* The print vendor set-up page has four boxes to fill in: the key
the mailing house gave you, your account number with them, **the address we go to for a
token**, and **how much that token is allowed to do**. Below them is a button that says
*Generate token*, and the connection page afterwards shows a token with a generated date
and an expiry date and a *Regenerate token* button.

*What the repo says.* The print vendor connector holds ONE thing — the key the mailing
house gave you — and puts it in a header on every call. There is no token, no token
address, no expiry and no regenerate.

*Why they cannot both be true.* The database allows **one live credential per connection**.
A key they gave us plus a token we generated is two, so the row will not store both. This
is the same wall that is already holding up five payment processors.

*The smallest question that settles it.* **For the print vendor, is the login one key the
mailing house gives you and nothing else — or do we also fetch a token from them that
expires every ninety days and has to be renewed?** If it is the token, the same answer has
to hold for about thirteen connectors, not just this one.

---

**2 · The time box on the Esri map connector is a promise nothing keeps.**

*What the drawing shows.* The Esri ArcGIS set-up page has a *When it runs* section that
says *"1 of 3 run on a clock"* and offers a time box — drawn showing `01:00` — with the
help line *"Your time zone. The only part you choose."*

*What the repo says.* The nightly parcel check is marked as scheduled and there is nowhere
to put an hour. The document says so itself, on another page: the choice *"is accepted,
validated, saved … and nothing will ever read it."*

*Why they cannot both be true.* A utility that sets this to 1 a.m. and waits will wait
forever, and nothing on the screen tells them so.

*The smallest question that settles it.* **Do we build the time box now and make the
nightly parcel check actually run at the hour a utility picks — or do we leave the box off
the screen entirely until the scheduler exists?** Showing a box that does nothing is the
one option that is worse than either.

---

**3 · Five of my thirteen operations have no agreed name.**

*What the drawing shows.* A naming scheme we own: every operation is a verb and a noun —
`fetch_statement`, `deliver_journal`, `serve_bill`. The table of worked examples names
eight of my thirteen operations.

*What the repo says.* Our five unnamed ones are called `address_search`, `map_tiles`
(twice, on two different connectors), `geocode_address` and `import_lockbox` — none of which
starts with one of the four agreed verbs.

*Why they cannot both be true.* The scheme's whole point is that the first word tells you
which of four doors the call goes through. Five operations that do not follow it are five
places where that stops being true.

*The smallest question that settles it.* **Nothing — this is ours to decide and write down,
not yours.** It is listed here only so nobody thinks it was overlooked: the four verbs are
already ruled, the five names follow from them mechanically, and the decision will be
recorded with its reasoning rather than put to you.

---

**4 · Retiring the third-party GL connector strands whoever holds its key.**

*What the drawing shows.* The old *Third-party GL* connector is replaced by five named ERP
connectors — Aclarian, Workday, SAP, Infor and Microsoft Dynamics GP. The document's own
words: *"Any partner already holding an issued key is on a connector that no longer exists
by that name."*

*What the repo says.* The third-party GL connector is live, issues keys, and each key
belongs to one connection row.

*Why they cannot both be true.* On the day the old connector stops existing, every key
issued against it stops working, and nothing on our side knows which of the five new
connectors that partner actually is.

*The smallest question that settles it.* **When we split the one finance-system connector
into five, does a utility that already has a partner connected re-issue that partner a new
key — or do we keep the old connector working alongside the five for a period, say ninety
days, so nobody's month-end breaks on the day we ship?**

---

**5 · One issued key opens every operation, and the screen says otherwise.**

*What the drawing shows.* Both ERP connection pages list the keys we issue with a column
headed **May call**, showing a key limited to *Read payments, Read bills +1*. A warning
beside it says *"May call is new. Today one key opens every API on the connector."*

*What the repo says.* One key, no scope, opens all three reads.

*Why they cannot both be true.* The screen promises a limit the key does not have — and
building the limit needs a new column on the keys table and a check at the door.

*The smallest question that settles it.* **Is limiting a partner's key to particular
operations part of this work, or does it wait?** It is one column and one check, roughly a
day. If it waits, the *May call* column has to come off the drawing, because a column that
always reads *all three* is worse than no column.

---

**6 · Two words for the same thing on two halves of one screen pair.**

*What the drawing shows.* On the Esri set-up page the map-tiles row is tagged **ITS OWN
HOST**. On the Esri connection page the same row is tagged **2ND HOST**.

*What the repo says.* One flag on one operation, naming which of the two addresses it calls.

*Why they cannot both be true.* They can both be true of the connector; they cannot both be
what a clerk reads, because the same fact must not have two names across two screens a
clerk moves between. Our own UI rules already settled this shape once — one pair of words,
everywhere.

*The smallest question that settles it.* **Nothing — ours to decide and write down.** Noted
here so it is not lost: one of the two wins and both screens use it.

---

**7 · "Which column is which" is drawn empty and declared mandatory.**

*What the drawing shows.* On the bank and lockbox set-up page, *Which column is which* is a
section with no inputs in it and one sentence: *"This part appears once a file has been
seen."* It has no required mark.

*What the repo says.* That field is mandatory. A connection saved without it is refused.

*Why they cannot both be true.* A utility connecting a bank folder for the first time has
not uploaded a file yet, so the mapping cannot exist, so the save is refused — and the
screen gives them no way to satisfy it.

*The smallest question that settles it.* **Can a utility save a bank connection before the
first file has ever arrived, and fill in the column mapping afterwards — yes or no?** If
yes, the field stops being mandatory. If no, the screen needs to say so before they start
typing.

---

**8 · Three cards say a vendor is connected when no vendor has been named.**

*What the drawing shows.* The document's own list of what to fix classifies this as a
defect, in these words: *"Bulk email, print vendor, census geocoder offered as live with no
connector — A card a utility can press that cannot work."* The print vendor and single
sign-on pages both carry the badge **NEEDS A VENDOR NAME**, and both draw a panel reading
*"Still generic. You have not named a vendor for this one — it keeps a category name until
you do."*

*What the repo says.* The census geocoder is genuinely live and already makes its call —
our own file says so and names the wave that wired it. The print vendor is live in the
catalogue and has no safe test at all: the mailing house has no zero-page job to accept.

*Why they cannot both be true.* Two of the three named are mine and they are in opposite
states, so one blanket answer will be wrong for one of them.

*The smallest question that settles it.* **For the print vendor specifically: which mailing
house are we going live with?** Until there is a name there is no document, no test job and
no way to know whether the hand-over takes one minute or one hour — and that is a fact only
you hold. The census geocoder needs no ruling; it works today and the document's note about
it is out of date.

---

## Counts

- **Field slots drawn across the nine forms: 35** (4 · 4 · 7 · 8 · 4 · 4 · 1 · 1 · 2),
  counting every input a clerk fills in wherever on the form it is drawn, and NOT counting
  *Where it runs*, which is the environment and is two connection rows rather than a field.
  **31 of them are distinct** — the two ERP forms draw the same four.
- **Fields MISSING — drawn, and we have nothing: 3.** Print vendor *Token address*, print
  vendor *Scope*, Esri ArcGIS *Time*.
- **Fields EXTRA — we have it, the drawing does not: 0.**
- **Fields whose required mark differs from what we declare: 4.** The issued key on each of
  the two ERP forms, *Which column is which* on the bank file, and the sign-in control on
  single sign-on — all four are drawn optional and declared required.
- **Operation rows drawn across the nine screens: 16** (3 · 3 · 1 · 2 · 1 · 3 · 1 · 1 · 1).
  **13 of them are distinct** — the two ERP screens draw the same three.
- **Operations MISSING — drawn, and we have nothing: 0.** Every drawn operation exists in a
  manifest today, either on its own connector or on the `gl_partner` template that the two
  ERP connectors copy.
- **Operations whose NAME or LABEL differs from the drawing: 8 of the 13.** The three ERP
  reads (label *and* key), `export_journal`, `import_statement`, `hand_over_batch`,
  `reconcile_parcels` (label *and* key) and `sign_in` (key).
- **Operations with no key drawn anywhere in the naming table: 5 of the 13.**
  `address_search`, `map_tiles` (Esri), `map_tiles` (public), `geocode_address`,
  `import_lockbox`. 8 + 5 = 13, so every operation of my nine either has a name to move to
  or has no name drawn at all; none is already correct.
- **Connectors buildable from the drawing alone today: 5 of 9** — accounting export file,
  bank and lockbox file, census geocoder, public map tiles, single sign-on.
