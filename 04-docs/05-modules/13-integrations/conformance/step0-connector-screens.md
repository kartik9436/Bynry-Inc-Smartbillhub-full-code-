<!-- ── Trace ──────────────────────────────────────────────────────────────
     What:    STEP 0 / STEP 1 MEASUREMENT. Five drawn connector screens of the
              Integration Blueprint, element by element, against the product on
              branch `claude/gifted-johnson-top7zn` at `fb3ca0aa`.
     Source:  `05-prototype/05 Integration Blueprint.pdf` — 163 pages,
              3,160,169 bytes, sha256 `c02e9518…`. It is NOT on this branch; it
              lives on `origin/claude/confirm-understanding-3ktufc`. Pages were
              RENDERED and READ AS IMAGES (B14 rule 42); the text layer was used
              only to find them.
     Rules:   B14 rule 42 (a screen is built from the drawing AS AN IMAGE) ·
              rule 37 (a figure drawn in a wireframe is an ILLUSTRATION) ·
              hard-won law 6 (no gate reads rendered output — so this was read
              in a browser) · law 2 and its mirror.
     Scope:   CON-01 · MAP-01 · MAP-02 · KEY-01 · ACC-01. NOT the 28 connectors'
              configure and view screens, and NOT Runbooks — the PO excluded
              runbooks entirely.
     Builds:  NOTHING. This file is the whole deliverable.
     ───────────────────────────────────────────────────────────────────── -->

# The five connector screens, drawn against built

**Measured 2026-09-16, product build `2.278.0`, branch tip `fb3ca0aa`.**

## How this was measured, so a reader can repeat it

1. The blueprint was fetched from the branch that holds it and rendered at
   scale 2 with `10-scripts/pdf/pdf_render.py`. **Every element below was read
   off the rendered image**, never off the extracted text (B14 rule 42).
   Drawing pages: **CON-01** p11–p14 + the carry-over on p20–p21 · **MAP-01**
   p94–p95 · **MAP-02** p95–p97 · **KEY-01** p98–p99 · **ACC-01** p99–p101.
2. The front end was read in `07-frontend/src/features/integrations/`, with
   line numbers as they stand at `fb3ca0aa`.
3. The back end was **measured, not assumed** — `06-backend/apps/integrations/`,
   plus the registry enumerated at runtime and `GET /api/{tenant}/integrations`
   read off the wire in the browser.
4. The five screens were opened in a browser at `localhost:8098`, signed in as
   a System Admin on `brazosbend`. Screens that could not be reached from a
   card were reached by typing the address.

**The three rulings of 2026-09-16 are applied**, so "correct" below means: the
visible word is **Connectors**; 28 connectors declared with `api.vendor.example`
placeholders; the accented `Panel` where the drawing shows it; mappings per
connector; an issued key names the APIs it may call.

---

## The counts, first

| Screen | Drawn elements | Built | Built differently | Not built |
|---|---:|---:|---:|---:|
| `CON-01` The grid | **21** | 12 | 4 | 5 |
| `MAP-01` + `MAP-02` Mappings — **one screen** | **14** | 6 | 5 | 3 |
| `KEY-01` Issue a key | **6** + 1 annotation | 4 | 1 | 1 |
| `ACC-01` Access log | **12** | 4 | 2 | 5 + 1 deliberate |
| **Total** | **53** | **26** | **12** | **14** + 1 deliberate |

**These are MY counts, one row per element as the tables below enumerate them,
and they are not the blueprint's.** The blueprint's carry-over boxes count 16
for `CON-01`, 12 for the mappings screen and 10 for `ACC-01`; they treat the
page head and the intro sentence as shell rather than as elements, and they do
not reconcile with their own tables either (see below). Where a drawn element
exists on the screen it is counted here, and the arithmetic is shown so the
next reader can disagree with a specific row rather than with a number.

*"Not built" on `ACC-01` includes one element — the* Revoke the key *button —
that is deliberately not on this screen and IS built on `KEY-01`. It is
separated out rather than folded in, because an absence with a reason and an
absence without one are different facts.*

⚠ **The blueprint's own arithmetic boxes do not reconcile with its own
carry-over tables, by one or two elements on each of the three screens that
have one.** CON-01's box reads `As-built 12 = unchanged 10 + relabelled 2`
while its table lists 14; MAP's reads `10 = 7 + 1 + 2` while its table lists 11;
ACC's reads `6 = 5 + 1` and its legend lists 6, which is the one that agrees.
**The tables were counted, not the boxes** — a table names elements and a box
names a number. This is an observation about the document, not a defect in the
product, and it is written down because the next lane will otherwise recount it.

---

## `CON-01` · The grid

⚠⚠ **STAMPED DIVERGENCE, 2026-09-17 — `CON-01` IS NO LONGER A GRID, AND EVERY
ROW OF THE TABLE BELOW IS MEASURED AGAINST A DRAWING THE PRODUCT OWNER HAS
OVERRIDDEN.** PO ruling of that date, verbatim: *"we are overriding the deciion
and converting it form Grid -> Table - table only"*. **"Table only" means there
is no grid/table toggle** — the cards are gone, not hidden behind a control.

**This overrides B14 rule 41** (RATIFIED — the product matches the blueprint
exactly), and under `CLAUDE.md` law 13 a supersession is **STATED, never
assumed**, which is what this block is. The blueprint did not merely omit a
table: **it considered one and declined to draw it**, on p014, in its own words
(read as an image, B14 rule 42) —

> *"If you would rather have a real table view behind a grid/table toggle, that
> is a different and larger change. Say so and I will draw it."*

The PO has said so. Two further rulings of the same date settle its shape: the
actions cell is **four icons — Connect · View · Edit · Keys — present on every
row, with the STATUS changing which are enabled and never which are drawn**
(*"Action im looking for - Connect, View, Edit, Keys- based on this status will
chnage"*, ratified over the full seven-row matrix as *"this is good - please add
it"*), and **ten columns** the PO approved as *"Im good with these columes -
please implment it"*. **The whole chain, with the matrix, the ten columns, the
paging judgment and what a row cannot carry that a card did, is
`12-governance/02-decision-log.md` under *`CON-01` BECOMES A TABLE*,
2026-09-17.**

**How to read the table below now that it is superseded**: it remains an
accurate measurement of the GRID against its drawing at `fb3ca0aa`, and it is
left standing rather than rewritten, because a measurement is a dated fact. But
three of its rows are answered by the override rather than by a build —
**② `+ Filter ▾` and ③ `▦ Columns`, both recorded "Not built", arrive for free
with `DataTable` and are live**, and **the per-operation status lines and the
card's summary sentence have no row to live on**. p014's argument for the column
selector (*"Neptune's card is sixteen operation lines tall beside neighbours
four lines tall … hiding the per-API lines is the one thing that makes the grid
scannable again"*) is not refuted, it is **answered by the shape**: a table row
is one line tall by construction.

**Drawn at** `/:tenant/settings/connectors` (p11–p13), legend p14, carry-over
p20–p21. **Built at** `07-frontend/src/features/integrations/IntegrationsTab.tsx`,
mounted from `SettingsPage.tsx` at `/:tenant/settings/integrations`.
**Served by** `GET /integrations` → `apps/integrations/selectors.grid`.

| Drawn | Front end | Back end | Note |
|---|---|---|---|
| Page head **Connectors** | **Built differently** — `IntegrationsTab.tsx:565`, `integrations.title` = **"Integrations"** | n/a | The 2026-09-16 ruling. `integrations.*` in `en.json` is **exactly 319 keys**, which is the blueprint's own number — so the rename really is 319 values, verified against this checkout rather than quoted. |
| Intro sentence | **Built** — `:570`, `integrations.intro` | n/a | Reads "Connect the **services** you already use." Same word to change. |
| ① Search box, name + summary, client filter, no `?q=` | **Built** — `:571–579`; placeholder `integrations.search` = "Search **services**…" | n/a (deliberately) | The drawing says "Search connectors...". The blueprint's own note records the `?q=` debt against `NFR-3` and says to write it down rather than tidy it. |
| ④ Category chips, generated from the registry, **eleven** | **Built** — `:580–592`, the kit's `ChipRow`/`ChipToggle`, generated from `payload.categories` | **Built** — `selectors.py:444`, `registry.categories()` | **Ten chips render today, not eleven.** The registry returns 9 categories (`email · banking · accounting · print · payments · meters · maps · messaging · identity`) plus **All**. The drawn eleventh is **ERP**, which no manifest declares. Generated, so it follows the manifests. |
| ② **+ Filter ▾** — direction · state · environment | **Not built** — `IntegrationsTab.tsx:600–608` states the absence in a comment and argues it | **Built** — all three are already on the wire: `kicker.direction`, `display_state`, `connection.environment` (confirmed in the live payload) | The blueprint is right that it costs no read. The file's stated reason is *"this is a card grid, not a list table"*, written when there were 18 cards. |
| ③ **▦ Columns** — which facts each card shows | **Not built** — same comment | n/a — per-viewer, asks the server nothing | On a card grid this chooses which FACTS a card carries. It is what collapses Neptune's 16 operation lines. |
| Category · direction kicker | **Built** — `:277` (`Kicker`, `:122–130`) | **Built** — `kicker.{direction,initiative}` | |
| Provider name (the vendor's real name) | **Built differently** — `:282` | **Built** — `display_name` on the manifest | The NAMES differ: today `meters_neptune360` is **"Water meter cloud"**, drawn as **Neptune 360**; `sms_twilio` is **"Text messages"**, drawn as **Twilio**; `gis_city` is **"City GIS"**, drawn as **Esri ArcGIS**; `meters_mdm` is **"Itron / Sensus"**, drawn as two separate connectors; `payments_card` is **"Card processor"**, drawn as five named processors; `gl_partner` is **"Third-party GL"**, drawn as five named ERPs. |
| Summary sentence | **Built** — `:286` | **Built** — `summary` | |
| Status word | **Built** — `StateWord`, `:99–114`; a single-operation card only | **Built** — `display_state`, `selectors.py:397` | ⚠ **A multi-operation card carries NO status word today, by rule.** `BR-INT-028` and `IntegrationsTab.tsx:297–307`. The drawing gives every card one. See *needs a ruling* #1. |
| Failure reason | **Built** — `:314–322`, only when `last_test_ok === false` | **Built** — `connection.last_test_text` | |
| Environment line | **Built** — `:325–333` | **Built** — `connection.environment` + `describe` | |
| Per-operation status lines | **Built** — `:297–307`, `OperationLine` at `:133–145` | **Built** — `operations[].state` | Drawn as HIDEABLE behind ▦ Columns; today always on. Neptune's card is 16 lines tall beside four-line neighbours — confirmed in the browser. |
| **"N APIs · M working"** count line | **Not built** — no such line anywhere in the file | **Built** (the ingredients) — `operations[].state` is served per operation | The drawing puts it on every card. Deriving it is client-side arithmetic over data already fetched. See *needs a ruling* #1. |
| The one state-driven action button | **Built** — the `ACTION` map at `:151–159`, rendered `:375–390` | **Built** — `POST …/connect`, `POST …/test`, `PATCH …/{key}` | Labels today: Connect · Test it now · Manage · Fix it · Turn on. The drawing's connected card leads with **View**. |
| **"View"** (relabelled from *Recent activity*) | **Built differently** — `:400–408`, `integrations.activityLink` = **"Recent activity"** | **Built** — the S142 screen exists at `/settings/integrations/:key` | The blueprint's own reasoning for the relabel is on p21. The door is the same door. |
| **"Set up"** action → `…/configure` | **Not built** | **Not built** — no `configure` route in `apps/integrations/api.py`'s urlpatterns | Confirmed in a browser: `/brazosbend/settings/integrations/email_smtp/configure` renders the product's **"This screen is not built yet"** page. Honest, and the door does not exist. |
| "Mappings" link | **Built** — `:410–418`, drawn when `card.vocabularies.length > 0` | **Built** — `vocabularies` on the manifest | **3 of 18 cards** carry it today (`bank_lockbox_file`, `accounting_file`, `payments_kiosk`). |
| "Keys we issue" link | **Built** — `:420–428`, drawn when the manifest has an `issued_secret` field **AND `card.connection !== null`** | **Built** — `POST/DELETE /integrations/{key}/key` | **0 of 18 cards carry it in this tenant**, because neither key-issuing connector (`payments_kiosk`, `gl_partner`) is connected here. The screen is live and routed and reachable only by typing the address. The condition is defensible — see *needs a ruling* #4. |
| **New-connector flag** (`NEW CONNECTOR` · `RENAMED` · `NEW · SPLIT OUT` · `NEEDS A VENDOR NAME`) | **Not built** | **Not built** — no such field anywhere in the card payload (19 keys, none of them a provenance flag) | Marks the 13 that do not ship. |
| Footnote — **"28 connectors · 11 connected. Showing every category."** | **Built differently** — `:625–627`, `integrations.footnote` = "{{count}} **services** you can connect."; renders **"18 services you can connect."** | **Built** — `counts.providers` **and `counts.connected`** are both served (`selectors.py:446–449`); the live payload reads `{providers: 18, connected: 3}` | **The second number is served and unread** — the same dead-data shape as `adapter_registered` before `DEF-INT-4224`. The third fact ("Showing every category") is not served and is client state. |

### What the product has that the drawing does not

* **A *Coming soon · wave* line and a disabled Connect** (`:290–295`, `:339–350`),
  and `POST …/connect` refuses it server-side too. 4 of 18 cards are in this
  state today. This is exactly the phase-1 mechanism the PO ruled for.
* **A held offer with its reason as a LINE OF TEXT** — *"Not ready to connect
  yet."* (`:355–374`), drawn when no adapter can dial the provider. 4 of 18
  cards. `DEF-INT-4224`'s remedy; the drawing has no equivalent.
* **A zero-results state** (`ZeroResults`, `:602–610`) for a filter that matches
  nothing, with the way back. The drawing does not show one.
* **A loading skeleton and a failure frame with Retry** (`:525–545`).
* **A read-only role path** — every control disabled with the ROLE's reason
  (`BR-SHL-025`), which the drawing does not show a state for.

### And one thing the drawing shows that the product's own component refuses to draw

The cards are **not** the kit's `Panel`. `IntegrationsTab.tsx:272–275` writes
`<article className="flex flex-col gap-3 border border-neutral-200 bg-bg p-4">`
by hand. The drawing gives every card a **red accent rule across the top**, which
is `Panel`'s `accent` prop, and the PO ruled on 2026-09-16 *"i want you to use
panel with acsent - where ever shown it that way"*. Confirmed in the browser:
today's cards have a plain grey border and no accent anywhere on the grid. This
is the blueprint's `S8-3`.

---

## `MAP-01` and `MAP-02` · Mappings

**One screen, two vocabularies.** `MAP-01` is a CLOSED vocabulary the connector
ships (p94–p95, `payments_kiosk` · *How they pay*); `MAP-02` is an OPEN one only
the utility can answer (p95–p96, `erp_aclarian` · *Their account codes*).
**Built at** `ValueMappingPage.tsx`, routed `/:tenant/settings/integrations/:key/mappings`.
**Served by** `GET/PUT /integrations/{key}/mappings` → `mappings_api.py` → `mappings.py`.

| Drawn | Front end | Back end | Note |
|---|---|---|---|
| Back link **← Connectors** | **Built differently** — `:317–321`, `integrations.mappings.backTo` = **"Integrations"** | n/a | |
| Kicker **MAPPINGS** | **Built** — `:320`, `integrations.mappings.title` | n/a | |
| Title — the connector's name | **Built** — `:317` | **Built** — `provider.display_name` | |
| Intro — *"Their words, and what each means here."* | **Built** — `:323` | n/a | Byte-for-byte the drawing's sentence. |
| ① **Kind selector — PILLS**, one per vocabulary | **Built differently, and it renders on NO connector today** — `:325–348`, guarded by `kinds.length > 1` | **Built** — `payload.types` | ⚠ **No connector in the registry declares more than one vocabulary**, so the control is never drawn. Confirmed in the browser: 0 pills on both screens. **And it is hand-rolled `rounded-full`** (`:339–340`) in a product whose `--radius-*` tokens are all `0px` — the blueprint's `S143-1`, and the only two `rounded-*` uses in the whole of `features/integrations/`. |
| The shipped-answers note — *"14 of 14 mapped. Shipped with this connector. Change one only if your vendor differs."* | **Built differently, and it states the opposite** — `:352–372` renders **"14 of 14 not mapped. Each records as Other until mapped."** | **Correct** — the server counts what is there | ⚠ **THE DRAWING'S PREMISE IS FALSE.** See the finding below. |
| **"These words are shared by all 3 APIs on this connector."** | **Not built** — no such sentence in the file or in `en.json` | **Not built** — the mappings payload carries no operation count | The 14 September ruling *mappings are per connector, not per API*, said on the screen. The number is one field away: the grid payload already carries `operations.length` for every connector. |
| ② Search box, in the toolbar | **Built** — `:375–386`, client filter over the loaded page | n/a | Placeholder matches the drawing exactly. |
| ③ **Unmapped as a CHIP with a count** (`All 24` · `Unmapped 9`) | **Built differently** — `:387–394` is a bare `<input type="checkbox">` labelled *"Unmapped only"*, with **no count on it** | **Built** — `counts.unmapped` and `counts.rows` are served and used by the alert | The counts exist; the chip does not. |
| Mapping rows, `their word → ours` | **Built** — `:398–433`, `data-mapping-rows` | **Built** — `payload.rows` | ⚠ Drawn as a **hairline table**; built as **one bordered card per row**, each with a red left rule when unset. A real visual divergence, confirmed in the browser. |
| Row edit control — an icon only (✎) | **Built** — `RowAction` + `PencilIcon` | **Built** — `PUT …/mappings` | Matches B14 rule 15 and the drawing. |
| Footer note — *"A word they send that is not on this list still lands — it appears here unmapped, in red."* | **Built differently** — `:435`, `integrations.mappings.foot` = *"Their new words appear here unmapped."* | n/a | Shorter, and B14 rule 33 is why. Same fact. |
| ④ **Column selector** | **Not built** | n/a — per-viewer | |
| ⑤ **Pager** (`1–5 of 14 · Rows per page 50`) | **Not built** | **Not built, and the blueprint says so** — `mappings_api.py` reads no `page` and no `per`; `mappings.view()` returns every row | The blueprint calls this *"a back-end change wearing a wireframe"*. Confirmed: the endpoint takes `target` and nothing else. |

### What the product has that the drawing does not

* **A green success line** — *"Every word is mapped."* (`:367–370`) for the
  all-mapped case. The drawing's closed vocabulary shows the same fact as a
  neutral count instead.
* **A ledger note** — *"Your chart of accounts is unchanged."* (`:374`), drawn
  only for a vocabulary flagged `beside_the_chart`. Confirmed live on
  `accounting_file`.
* **Per-row refusal text** and a save/cancel inline editor with a *Leave
  unmapped* choice.
* **A loading skeleton and a failure frame with Retry.**

### ⚠ The finding that matters most on this screen

**The drawing states a premise about the product that the product does not
keep.** `MAP-01`'s own red note reads:

> *"The answers ship with the connector. Our seven tenders are seeded
> identically into every tenant, so `ACHCHECK → Bank transfer` is the same at
> every utility."*

**Nothing seeds them.** The only writers of `integration_target_reference` are
the clerk's `PUT` (`mappings.py:448`) and an arrival-time `get_or_create`
(`:497`); no provisioning path, no fixture and no migration writes a default.
Opened in a browser on a provisioned tenant, `payments_kiosk` reads **"14 of 14
not mapped. Each records as Other until mapped."** and every one of the fourteen
rows says *Not set · records as Other*.

So the sentence the blueprint draws is the opposite of what a utility sees on
day one, and the consequence is a money one: **until a clerk maps them by hand,
every kiosk payment records as `Other`.** This is the shape the measuring
instruction names — a screen's stated premise is a claim about the product, and
this one is honest, specific and wrong.

---

## `KEY-01` · Issue a key

**Drawn at** `/:tenant/settings/connectors/:key/access` (p98–p99).
**Built at** `MachineKeysPage.tsx`, routed `/:tenant/settings/integrations/:key/access`
(screen `INT-04` / S144). **Served by** `POST` / `DELETE /integrations/{key}/key`.

| Drawn | Front end | Back end | Note |
|---|---|---|---|
| Kicker — the connector's name | **Built** — `:270–276` (`PageHeader kicker`) | **Built** | |
| Title **"Issue a key"** | **Built differently** — `:271`, `integrations.keys.title` = **"Keys we issue"** | n/a | The drawing titles the ACT; the product titles the LIST. Both are ≤ 3 words. |
| Intro — *"A key is shown once when it is issued, and afterwards only replaced."* | **Built** — `:303`, `integrations.keys.note`, byte-for-byte | n/a | |
| Panel **"What this key may call"** — one tick per API, with *"Tick only what they need. A key with nothing ticked cannot be issued."* | **NOT BUILT** | **NOT BUILT** — `machine_auth.issue_key(actor, connection, registry)` takes a connection and nothing else (`:227–232`); there is no scope column on `integration_credential` | The 14 September ruling. This is the one item with a security shape and the one that costs a migration: a scope column **and a check at the door** in `runners/serve.resolve_caller()`. |
| Panel **"The key for them to use"** — the key once, `Copy`, *"Copy it now. This is the only time it is shown."* | **Built** — `IssuedKeyPanel`, `:82–120`; the key lives in component state and is never cached | **Built** — `issue_key` returns the only copy and writes it nowhere | Matches the drawing element for element. |
| **Done** | **Built** — `:117` | n/a | |
| The red note — *"Today a key carries no scope — one key opens every API on the connector."* | n/a — this is the blueprint's annotation of the gap, not a screen element | | Counted as drawn because the drawing shows it; it is satisfied by building the panel above. |

### What the product has that the drawing does not

The drawing shows only the issuing moment. The product has a whole screen
around it, and none of it is drawn:

* **The key table** — `DataTable` at `:314–333`, five columns: *Key* (the
  `••••7Q2F` hint plus a version suffix), *What it reaches*, *Issued*,
  *Last used*, *State*.
* **A *What it reaches* column that answers a different question.** It renders
  a constant, `integrations.keys.scopeThisUtility` = **"This utility only"**
  (`:249`) — the TENANT scope. The ruling asks for a **May call** column naming
  APIs. The column exists; its content is not the ruled content.
* **A state filter** (active · revoked) through `FilterBar`.
* **Revoke**, danger tier, behind a `ConfirmDialog` whose consequence is spelled
  out; and **Replace key**, which is a revoke and an issue in one transaction.
* **An empty state** — *"No key issued yet / Issue a key and hand it to the
  partner. It is shown once."* with the CTA. Confirmed live.
* **A back link to the Connection**, and a refusal line.
* **"Last used" derived from the access log**, not stored — so a replaced key
  can still answer honestly.

---

## `ACC-01` · Access log

**Drawn as a panel inside the connection view** (p99–p101). **Built at**
`AccessLogPanel.tsx`, mounted **only** by `ConnectionDetailPage.tsx` — the
blueprint's `S144-1` is right, and I confirmed it in a browser: the panel is on
`/settings/integrations/gl_partner` and is **not** on the keys screen.
**Served by** `GET /integrations/{key}/access-log` → `partner_api.py:398`.

| Drawn | Front end | Back end | Note |
|---|---|---|---|
| Panel title **"Who has been reading"** | **Built** — `:186–188` | n/a | |
| Subtitle **"An access log, not a run history"** | ✅ **BUILT TO THE DRAWING 2026-09-16 (`2.287.3`)** — plain grey text under the heading, `data-access-subtitle`. It had been a bordered warning-tone TAG floated right of the title, which on a security panel reads as a badge rather than as the sentence it is. | n/a | Finding ⑥. |
| ① **LOADING** state | ✅ **BUILT 2026-09-16 (`2.287.3`)** — `logQuery.isPending` draws the kit's `LoadingSkeleton variant="table"`, which is the component the blueprint's own legend names | **n/a** — the field was always there, simply unread | **`DEF-INT-5484` CLOSED.** Proved in a browser by holding the response six seconds. |
| ② **EMPTY** — *"Nobody has read anything / This partner has a key and has not used it."* | ✅ **BUILT 2026-09-16 (`2.287.3`)** — the kit's `EmptyList`, both of the drawing's lines, and **only when the read succeeded**. `integrations.access.empty` is retired; `…empty.title` and `…empty.helper` are in all eleven catalogues | **Built** | Was one sentence covering all three states. Confirmed live on `erp_workday`, a connected connector with zero reads. |
| ③ **FAILED** — *"The access log did not load / We cannot say whether anybody has read anything."* + **Retry** | ✅ **BUILT 2026-09-16 (`2.287.3`)** — `logQuery.isError` draws both sentences and ONE `Retry`, `role="alert"`, behind a red left rule | **n/a** — the field was always there, simply unread | **`DEF-INT-5484` CLOSED.** ⚠ The block is composed in the panel rather than the kit's `FailedWithRetry`, which requires two further handlers 98 of its 102 call sites wire to `() => undefined` — `DEF-INT-5562`. |
| ⑤ Table column **WHEN** | **Built** — `:201–204` | **Built** — `items[].when` | |
| ⑤ Table column **WHICH API** | **Not built** — `:205–207` draws *"What they took"*, a summary substring | **Not built on the wire** — `partner_api.py:435` sends `"what": (row.summary or "").split(" · ")[0]`. **`IntegrationRun.operation` holds the real answer** (`models.py:296`) and is simply not serialised | **One field on the response**, not a schema change. The fact is already stored. |
| ⑤ Table column **ROWS** | **Built** — `:208–210`, right-aligned, tabular | **Built** — `items[].rows` | |
| ⑤ Table column **RESULT** (`Worked` / `Refused`) | **Not built** — nothing in the component reads it | **BUILT AND SERVED** — `partner_api.py:450` sends `"outcome": row.outcome` | ⚠ **Dead data**: the column the drawing calls new is already on the wire and no screen asks for it. The same shape as `adapter_registered`. |
| ④ Button **"Allowed addresses"** | **Not built, and the absence is now STATED rather than inherited** — the panel's header says why | **NOT BUILT** — there is no `POST …/access/allowlist` in any URLconf | Filed 2026-09-16 as **`DEF-INT-5564`**: the control has no endpoint and no screen behind it, so drawing it would be law 2's mirror. Either build the editor or take the button out of the drawing. |
| ④ Button **"Revoke the key"** | **Not built here, RULED 2026-09-16** — and the reason moved from *another wave owns it* to *this page already has that door* | **Built** — `DELETE /integrations/{key}/key` | `ConnectionDetailPage`'s `ManagePanel` draws the keys table and a `Keys` link a few hundred pixels ABOVE this panel, where revoke carries its `ConfirmDialog` and lets a clerk choose WHICH key. A danger-tier control here would be two destructive doors onto one act on one screen (B14 rule 4). Judgment recorded in `02-decision-log.md`, not filed as a defect. |
| **WATCH** box — *"Why this screen exists / Nothing else in the product would show a partner taking two years of history at two in the morning."* | ✅ **REDRAWN 2026-09-16 (`2.287.3`)** — a `<blockquote>` with a grey left rule, which is the shape ACC-01 draws; it had been the filled amber `ConsequenceBox tone="check"` | n/a | Byte-for-byte the drawing's sentence. ⚠ It is RATIONALE, which **B14 rule 33 puts at zero words on screen**, and the blueprint draws it on a page stamped DRAWN TO THE RULES. Shipped as drawn and the collision is **`OQ-INT-12394`** — rule 41's own named case. |

### What the product has that the drawing does not

* **The subprocessor register** — *"Who else has this data"* (`RegisterRows`,
  `:134–154`), the inward-pointing rows as sentences. Nothing in the drawing.
* **Unusual rows kept whatever their age** — `visibleRows` (`:75–79`) takes the
  newest 20 **union** every unusual one, and the server does the same
  (`partner_api.py:415–428`) so a partner cannot bury one 48,000-row collection
  under a hundred small reads. This is the reason the screen exists and the
  drawing does not show it.
* **"and N more reads"** (`:225–229`), a count rather than a silence.
* **The key HINT under what they took** (`:110–116`) — the *who* of *who has
  been reading*.
* **The panel draws itself only where something points inward** — `readsFromUs`
  reads the SERVE quadrant off `operations`, never a provider key.

---

## Defects

| Id | What | State |
|---|---|---|
| **`DEF-INT-5484`** | The access log cannot tell *still loading* from *nobody has read anything* from *the fetch failed*: one reassuring sentence covers all three, on the one screen whose job is to show unusual access. | ✅ **fixed 2026-09-16, `2.287.3`** — three branches, three sentences, proved RED first in `vitest` and then in a browser on all four states. |
| **`DEF-INT-5562`** | **NEW, filed 2026-09-16 by the access-log build lane.** `FailedWithRetry` cannot draw a single-action failure: `onDownloadReport` and `onCancel` are required, and **98 of its 102 call sites** pass `() => undefined` to the first — a live *Download error report* button that downloads nothing. Law 2's mirror at 98 instances; G13 passes because a no-op handler IS a caller. | open |
| **`DEF-INT-5564`** | **NEW, filed 2026-09-16 by the access-log build lane.** A System Admin cannot see or change the addresses a partner key may call from. `ACC-01` draws the button; there is no endpoint, no screen and no field for it anywhere. | open |
| `DEF-INT-4233` | The mappings screen says *"Every word is mapped."* and *"Nothing recorded yet."* at the same time. **Reproduced live** on `accounting_file`, whose open vocabulary has zero rows: the green success line and the empty state render together. Already filed 2026-09-06 and still open; not duplicated. | open |
| `DEF-INT-4224` | The held Connect offer. **Verified fixed and live** — 4 of 18 cards draw *"Not ready to connect yet."* as a line of text beside a disabled control. | fixed |

Two more the blueprint routes as defects were checked and are **not filed by
this lane**, with reasons: `S143-1` (the hand-rolled `rounded-full` pills) is a
one-line token fix inside a screen that is about to be redrawn for the pills
ruling, and filing it separately would split one change in two; `S8-3` (the
cards are not the kit's `Panel`) is now covered by the PO's own accent ruling of
2026-09-16 and belongs to that work.

---

## Needs a ruling

These are where the drawing and the product disagree and the answer is a
judgment, not a measurement. Each gives the two readings and what each costs.

### 1 · Does a multi-operation card get one status word and an API count?

* **The drawing** gives every card a state word and a count line — *"Not
  working · 16 APIs · 14 working · Meter alerts is refusing"* — four lines.
* **The product** gives a multi-operation card **no word of its own** and lists
  every operation with its own state. `BR-INT-028` is the signed rule and
  `IntegrationsTab.tsx:297–307` quotes it: *"three of three running is a claim
  about a thing that is not a thing"*. **The blueprint agrees with the product**
  in its own prose on p9 — *"deliberately shows no aggregate — correctly,
  because averaging three operations into one word would hide a broken one"* —
  and then draws the aggregate anyway.
* **Cost of the drawing's reading:** `BR-INT-028` is amended, and a card can say
  *Working* over a broken operation. **Cost of the product's reading:** Neptune's
  card is 16 rows tall beside four-row neighbours, which is why ▦ Columns exists.
* **A third reading nobody has put:** keep the rule, build ▦ Columns, and let the
  count line be **a count and never a word** — *"16 APIs · 14 working"* is
  arithmetic a clerk can check, where *"Working"* is a claim. This costs no rule
  change and solves the height. **It needs the PO to say so, because a count of
  how many work is arguably the aggregate the rule forbids.**

### 2 · Do we keep the connectors' present names, or take the vendors' real ones?

Six of today's eighteen carry a generic name where the drawing carries a
vendor's: *Water meter cloud* → **Neptune 360**, *Text messages* → **Twilio**,
*City GIS* → **Esri ArcGIS**, *Card processor* → five named processors,
*Third-party GL* → five named ERPs, *Itron / Sensus* → two connectors.

* **The drawing's reading:** a clerk who has bought Neptune looks for Neptune.
* **The other reading:** a generic name survives a vendor change and does not
  claim a partnership we do not have.
* **Cost either way is eleven catalogues**, and it lands in the same 319-key
  change as *Integrations → Connectors*, so **it is cheapest to decide now and
  dearest to decide after.** It also interacts with the phase-1 split of
  `payments_card` into five and `gl_partner` into five.

### 3 · Does the mappings screen page, and does the endpoint learn to?

The drawing shows a pager; the endpoint returns every row and takes no `page`.
At 14 rows and 24 rows this is invisible. At a utility's full chart of accounts
it is not, and `NFR-3` (universal server pagination) says it must page.

* **Cost of building it:** `GET /integrations/{key}/mappings` learns `page` and
  `per` and orders in SQL, plus the control. **Cost of not:** one more
  unpaginated list on the `NFR-3` list, on a screen whose row count is TENANT
  data rather than bounded by our code — which is the distinction the CON-01
  search debt turns on, and this one falls the other way.

### 4 · Should the *Keys we issue* door need a connection?

`IntegrationsTab.tsx:420` draws the link only when the connector issues keys
**and** a connection exists. In this tenant that is 0 of 18 cards, while the
screen is live, routed and reachable by typing the address.

* **The reading that is built:** a key belongs to a connection, so there is
  nothing to issue against until one exists.
* **The other reading:** the drawing puts *Mappings* and *Keys we issue* side by
  side on the kiosk card, and a System Admin setting a partner up wants to see
  the door before they finish. **The screen itself does not refuse** — it offers
  *Issue key* — so today a person who guesses the address gets an offer the grid
  never showed them.
* **Cost:** one boolean. It is on this list because it is the difference between
  *deliberate* and *forgotten*, and only the PO can say which.

### 5 · Does the connector ship its own mapping answers?

Raised by finding MAP-01 above, and it is a money question rather than a
drawing one. The blueprint asserts the closed vocabularies ship seeded; nothing
seeds them; a new utility's kiosk payments all record as `Other` until a clerk
maps fourteen words by hand.

* **Seed them** — the fourteen tender words have obvious answers and
  `CR-6` in the blueprint argues they are the same at every utility. Cost: a
  data migration plus a rule about what happens when a vendor genuinely differs.
* **Leave them unmapped and say so louder** — the screen already says *14 of 14
  not mapped* in red, and go-live could refuse until they are answered, which is
  what `MAP-02`'s drawing says for the OPEN vocabulary (*"Go-live is not done
  while any of these is unset."*).
* **Either way the blueprint's sentence must change**, because it describes a
  product we do not have.

---

## What this lane did not do

Built nothing, changed no product code, and decided nothing on the list above.
One defect was filed (`DEF-INT-5484`) and one confirmed still reproducing
(`DEF-INT-4233`). The 28 connectors' configure and view screens and everything
under Runbooks were out of scope and were not measured.
