# CR-094-BRC01 · step 1 lane 2 — the Account detail screen, read against its drawing

**Screen 02 · `S21` · `/:tenant/accounts/:accountId` · `AccountDetailPage.tsx`**
**Drawn at pages 6–59 of `05-prototype/02 Accounts Menu Blueprint.pdf`**, pinned at
commit `033981d4f39f4b3e703639c074df1f8df7082a6d`, `sha256` begins
`c8d596bb505f5020ce4b9474`. **Remedies §10 pages 149–191; specification register
§12 pages 207–209.**

**Step 1 classifies. It fixed nothing.** No product code was changed by this lane.

---

## 0 · HOW THIS WAS READ, AND WHAT THAT IS WORTH

**54 pages read as IMAGES at scale 2**, never from the text layer — the blueprint's
own §3a measures that layer as unsafe for anything carrying a number (every digit
extracts as `&`, 8 of 21 specification ids are dropped, the wireframes are vector art
and absent). **Prose was taken from the text layer where it is reliable; every
figure, id, label and count in this document was read off a rendered page.**

**The product was booted and driven.** PostgreSQL 16 on `:5432`, Django on
`127.0.0.1:8580`, the SPA built with `vite build` and served by `server.mjs` on
`:8581` with `API_PROXY_TARGET` pointed at the backend — the same-origin shape the
product ships. `seed_demo` then `load_sample_data --tenant brazosbend`: **1,647 rows,
73 accounts**. Signed in as `dana@brazosbendutilities.com` and driven with Chromium
at 1440×2000. **The running version badge read `v2.237.10` on every page** — the
blueprint audits `2.234.15`.

The walkthrough is **`10-scripts/cr094_lane2_account_detail_walkthrough.mjs`**. It
prints the sentence it looked for AND what it found instead on every check, because
an exit code does not distinguish a pass from a fail to a reader (hard-won law 7).
**Result: 15 pass · 9 fail · 1 not confirmed.** Screenshots and full page text under
`/tmp/cr094-lane2/`.

**What this lane did NOT do, stated rather than blurred.** It did not drive any
wizard to its write. It did not open the screen at 390px — the blueprint's own §02
says the phone drawings were cut on the PO's instruction, so there is nothing to
compare against. **And the `disconnected` status could not be tested at all**: the
tenant seeds no such account, which is the one status `Close out` exists for.

### The accounts this lane opened, and why each

| account | status | kind | balance | what it proves |
|---|---|---|---|---|
| `A-11812` Bramble Bakery | `active` | regular | `2410.000000` | the blueprint's own fixture — never billed, no meter |
| `A-12048` | `pending_activation` | regular | `0.000000` | the `Close out` gate |
| `AC-2026-00052` Ridge Property LLC | `active` | **master** | `0.000000` | the thirteenth tab that does not exist |
| `AC-2026-00043` | `closed` | regular | `0.000000` | the raw sub-type on a second account |

**The tenant holds 69 `active`, 1 `closed`, 1 `marked_disconnect`, 1
`pending_activation`, 1 `vacation_hold` and NO `disconnected` account.** Read from
the database with `app.tenant_id` set.

---

## 1 · THE DRAWING, INVENTORIED

### 1.1 · The screen's identity, read off its own header page (p6)

> `02` **Account detail** `EXISTS BEHIND` `ACC-03`
> `/:tenant/accounts/:accountId · ?tab= × 12 · ?order= · S21 · AccountDetailPage.tsx`

**The canonical A1 id is `S21`.** The screen index deliberately omits the id column
and tells each lane to read it off its own header page; this is that read.

### 1.2 · The header — chrome, drawn identically on all fifteen action drawings

| element | drawn, character for character |
|---|---|
| back link | `← Accounts` (and `← Bramble Bakery` from a wizard) |
| kicker | `ACCOUNT A-11812 · CUSTOMER — NOT LINKED` |
| title | `Bramble Bakery` |
| chips, in order | `Active` · `Billable` · `Commercial · Small commercial` · `Regular account` · `Autopay off` |
| address line | ⌂ `142 Bakers Row · Suite 1` · `Silver Creek, TX 78611` · `Since Sep 2024` |
| service chips | `ELECTRIC` `WATER` `+ 9 more ▾` |

**Header actions, in the drawn order** — `Adjust` · `Move-out` · `Activate account` ·
`Move-in` · `Close out` · `Record payment`. `Move-out` carries the drawn box;
`Record payment` is the primary.

**The rail, seven icons in order** — Send statement (envelope) · Print bill (printer)
· Issue credit (dollar) · Change plan (swap) · Disconnect notice (bolt, danger tier) ·
Payment plan (calendar) · Add note (pencil).

**The KPI strip is drawn TWICE AND DIFFERENTLY, and this matters** — see §2.2.

* **`ACC-02`, p7** (the first drawing after *The question*): `BALANCE $2,410.00` /
  *posting basis, from the ledger* · `AGEING 61–90 days past` / *61 days past due ·
  from opening buckets* · `LAST BILL Never billed` / *no bill has been issued on this
  account* · `PLAN FROM UNIT SCW-RES` / *v1 · since 06/01/2026 · Base charge* ·
  `DEPOSIT ON FILE $0.00` / *none received*.
* **`ACC-T01`, p9** (the same tab with sample data): `BALANCE $2,410.00` · `DUE DATE
  Not known yet` / *past-due is not worked out on this deployment* · `PLAN FROM UNIT
  SCW-RES` · `LAST ACTIVITY 09/11/2026` / *a payment was recorded* · `DEPOSIT ON FILE
  $450.00` / *received 09/24/2024*.

### 1.3 · The twelve tabs, in the drawn order

`Overview` · `Bills` · `Payments` · `Credits` · `Payment plan` · `Usage` · `Meters` ·
`Work` · `Adjustments` · `Documents` · `Notes` · `Audit`

**The blueprint's own note, quoted:** *"All twelve render, all twelve reflect in the
address bar, none is blank and none raised an error. One address is worth noting:
**Payment plan is `?tab=plan`, not `?tab=paymentplan`** — a link built by guessing
from the label lands on Overview."*

Figure ids: `ACC-T01`…`ACC-T12`, plus `ACC-T01E` (the Overview proposal) and
`ACC-T07R` (the Read-log dialog).

### 1.4 · Tab 1 · Overview — `ACC-T01`, p9–10 · *sample data*

**Left column, in order.** `MONEY` (Balance · Basis · Source · Oldest unpaid ·
Returned payments · Bad address) · `SERVICE` (a table: `SERVICE` / `STARTED` /
`ENDED`, with `Filter ▾`, `Search services`, `Columns ▾`, `Export`) ·
`METERS ON THIS UNIT` (`METER` / `SERVICE` / `LAST READ` / `READ ON`) ·
`PLAN — TAKEN FROM THE UNIT, NOT HELD ON THE ACCOUNT` (Plan · Code · Version · In
force since) · `RECENT BILLS` with `All bills →` (`BILL #` / `ISSUED` / `DUE` /
`TOTAL` / `STATUS`) · `USAGE TREND` with `Usage →`, a `12 months` / `24 months`
toggle and a `MONTH` / `ELECTRIC` / `WATER` table.

**Right column, in order.** `ACCOUNT` (Number · Status · Opened · Category · Sub-type
· Cycle · Tax exempt · Preferred language) · `CUSTOMER` (Full name · Kind · Email ·
Phone · Trading name · Business ID) · `MAILING ADDRESS — WHERE THE BILL GOES` ·
`CUSTOMER RECORD` · `PAYMENT METHOD` (On file · Verified · Autopay) ·
`DEPOSIT & CREDIT` (Deposit on file · Received · Interest accrued · Credit tier) ·
`PORTAL ACCESS` (Sign-in · Last sign-in · Paperless · Text reminders) ·
`ALL ACCOUNTS FOR THIS CUSTOMER` (`ACCOUNT` / `ADDRESS` / `STATUS` / `BALANCE`).

### 1.5 · Tabs 2–12, as drawn

| tab | figure | toolbar, verbatim | columns, in order |
|---|---|---|---|
| **Bills** | `ACC-T02` | `All` `Outstanding` `Settled` `Filter ▾` `Search` · `All bills →` `Columns ▾` `Export` | `BILL #` · `CYCLE` · `ISSUE DATE ▼` · `DUE DATE` · `SUBTOTAL` · `TAX` · `TOTAL` · `STATUS` · row actions |
| **Payments** | `ACC-T03` | `All` `Cleared` `Processing` `Filter ▾` `Search` · `Columns ▾` `Export` | expander · `PAYMENT #` · `POSTED ▼` · `TYPE` · `METHOD` · `REFERENCE` · `APPLIED TO` · `AMOUNT` · `STATUS` · `…` |
| **Credits** | `ACC-T04` | `All` `Applied` `Open` `Filter ▾` `Search` · `Columns ▾` `Export` | `CREDIT NOTE #` · `ISSUED ▼` · `REASON` · `AGAINST BILL` · `AMOUNT` · `STATUS` |
| **Payment plan** | `ACC-T05` | — | a `No plan is running` `None live` card (Arrears now · Oldest unpaid · Dunning so far) + `Propose a payment plan`, then `Earlier plans on this account`: `PLAN #` · `OPENED` · `SPREAD` · `INSTALMENTS` · `OUTCOME`, expanding to `#` · `DUE` · `INSTALMENT` · `PAID ON` · `STATUS` |
| **Usage** | `ACC-T06` | `Electric` `Water` `All` · `12 months` `24 months` | a chart, then `Average` / `Highest` / `Lowest` / `This month vs last`, then `MONTH` · `ELECTRIC` · `WATER` · `READ ON` · `SOURCE` |
| **Meters** | `ACC-T07` | `All` `Electric` `Water` `Installed` `Removed` `Filter ▾` `Search by meter number or serial` · `Sort: Meter # ▼` `Columns ▾` `Export` | `METER #` · `SERVICE` · `METER TYPE` · `READ METHOD` · `INSTALLED` · `MULTIPLIER` · `LAST READ` · `READ ON` · `STATUS` · `ACTIONS` (`☰ Read log`, `…`) |
| **Meters → Read log** | `ACC-T07R` | `12 months` `24 months` `All` `Estimated only` `Filter ▾` `Search by date or reading` | `THE METER` facts, then `DATE ▼` · `CHANNEL` · `READING` · `USAGE` · `EXPORT` · `HOW IT WAS COLLECTED` · `STATUS`; footer `Export the log` / `Close` |
| **Work** | `ACC-T08` | `All` `Open` `Scheduled` `Closed` `Filter ▾` `Search by order number, type or technician` · `Columns ▾` `Export` | `ORDER #` · `TYPE` · `PRIORITY` · `TECHNICIAN` · `DUE` · `STATUS` · `RAISED BY` · `…` |
| **Adjustments** | `ACC-T09` | `All` `Filter ▾` `Search` · `New adjustment` *(disabled)* `Columns ▾` `Export` | `DATE` · `ADJUSTMENT #` · `REASON` · `APPLIED TO` · `AMOUNT` · `APPROVED BY` |
| **Documents** | `ACC-T10` | `All` `Correspondence` `Evidence` `Filter ▾` `Search` · `Upload document` *(disabled)* `Columns ▾` `Export` | `DOCUMENT` · `TYPE` · `DATE` · `UPLOADED BY` · `SIZE` |
| **Notes** | `ACC-T11` | `All` `Pinned` `Collections` `Customer-visible` `Search` · `Add note` | a pinned card, then `WHEN ▼` · `WHO` · `KIND` · `NOTE` · row actions (pin, `…`) |
| **Audit** | `ACC-T12` | `All` `Money` `Status` `Collections` `Filter ▾` `Search` · `Columns ▾` `Export` | expander · `WHEN ▼` · `WHO` · `WHAT HAPPENED` |

### 1.6 · The fifteen action drawings, `ACC-A01`…`ACC-A15`

**Thirteen controls in fifteen drawings**, because Change plan has three steps. The
blueprint's own framing, quoted: *"Every refusal sentence is the product's own
wording, taken from the control itself rather than from the code that writes it."*

| # | control | figure | what is drawn |
|---|---|---|---|
| 1 | `Adjust` | `ACC-A01` | **`Adjust is disabled here.` / `Adjustments are billing rows, and billing is not built. There is no endpoint to post one to.`** plus a table showing the same sentence in three places |
| 2 | `Move-out` step 1 of 6 | `ACC-A02` | `Close an account and free the unit.` · rail `Find account` · `Date & final read` · `Final bill & deposit` · `The shortfall` · `What happens next` · `Review & close` |
| 3 | `Activate account` | `ACC-A03` | drawn on `A-12048`: **`There is no wizard and no confirmation.`** — it commits on the click |
| 4 | `Move-in` step 1 of 5 | `ACC-A04` | drawn on a closed account; **`THERE IS NO UNIT PICKER ON THIS STEP`** |
| 5 | `Close out` | `ACC-A05` | **`Close out is disabled here.` / `Only an account whose service has been cut is closed out. An occupant leaves by moving out, and a closed account is already finished.`** plus a six-row truth table |
| 6 | `Record payment` | `ACC-A06` | the modal — eight fields, and **three faults drawn as they are** |
| 7 | `Send statement` | `ACC-A07` | **`Send statement is disabled here.` / `Statements are not built yet.`** |
| 8 | `Print bill` | `ACC-A08` | **`Print bill is disabled here.` / `No bill has been issued yet.`** |
| 9 | `Issue credit` | `ACC-A09` | **`Issue credit is disabled here.` / `A credit needs an issued bill.`** and *"where it is live, it drops the account on the way"* |
| 10–12 | `Change plan` 1–3 of 3 | `ACC-A10`–`A12` | six plans priced, the quote, the recap. **`There is no step rail on this wizard.`** |
| 13 | `Disconnect notice` step 1 of 5 | `ACC-A13` | `Account & reason` · `Protections` · `Notice & date` · `Fees & consequences` · `Review` |
| 14 | `Payment plan` | `ACC-A14` | `BALANCE OWED $2,410.00` · `HOW OLD 62 days` · `PLANS ON THIS ACCOUNT None` |
| 15 | `Add note` | `ACC-A15` | `Title` · `Note` · `Pin to the top` · `Visible to the customer` · `Cancel` / `Save note` |

### 1.7 · The two proposed tabs nobody has undertaken to build

The blueprint draws **two further tabs of this screen** and marks each
`NEW BUILD` · **`NO COMMITMENT`**:

* **`18 Complaints`** — `/:tenant/accounts/{id}?tab=complaints`, **no screen id**,
  six drawings (the table, a four-step form, the detail view). *"This tab does not
  exist, and everything behind it does"* — a complaint is already a work order of
  type `Consumer Complaint`.
* **`19 Services`** — `/:tenant/accounts/{id}?tab=services`, **no screen id**, nine
  drawings. Type `Consumer Services`. *"`Consumer Services` is what a customer ASKED
  FOR; `Consumer Complaint` is what went wrong."*

**Both say in their own words that no door exists: `How you get here — Nowhere.`**
Two gaps are named on the Services side and neither is drawn away: *"A job carries no
price"* and *"nothing connects a container size to the plan that bills for it"*.

---

## 2 · AS-BUILT VERSUS DRAWN

### 2.1 · What matches, measured

| claim | measured on the running product |
|---|---|
| twelve tabs, in the drawn order | ✅ `ACCOUNT_TAB_IDS` is exactly the drawn list; all twelve render |
| Payment plan is `?tab=plan` | ✅ confirmed — `plan`, not `paymentplan` |
| six header actions in the drawn order | ✅ `Adjust` `Move-out` `Activate account` `Move-in` `Close out` `Record payment` |
| seven rail icons | ✅ envelope · printer · dollar · swap · bolt · calendar · pencil |
| the Documents tab draws headings over an absence | ✅ `Upload document` disabled, five column heads, the absence stated |
| the mailing address states its absence rather than repeating the service address | ✅ *"Same as the service address. No separate mailing address is on file."* |
| the Portal panel on the Overview no longer denies the portal | ✅ `DEF-CUS-4625` is fixed — it reads `Nobody has signed up` / `Never signed in` |
| the Payment method panel carries a disabled control with its reason | ✅ `Update method`, the one place R5 says the product already agrees |
| money on the Overview is 2 decimals | ✅ `$2,410.00`, `$0.00` — `MoneyCell` throughout |
| a master account is an ordinary row with `kind='master'` | ✅ header shows the `Master` pill; no `parent_account_id` anywhere |

### 2.2 · Where the drawing and the product differ

⚠ **THE BLUEPRINT DRAWS THIS SCREEN'S HEADER AND OVERVIEW TWICE AND THE TWO ARE NOT
THE SAME SCREEN**, and neither is what the product renders. Under **B14 rule 37** a
figure drawn in a wireframe is an illustration, never a fact to build to; that rule
settles the NUMBERS and it does not settle a tile that is present in one frame and
absent in the other. **So this is reported, not resolved.**

| drawn | as built at 2.237.10 |
|---|---|
| header chips `Active` · `Billable` · `Commercial · Small commercial` · `Regular account` · `Autopay off` | **only `Active`** (plus `Master` on a master, plus `Autopay on` when autopay is on) |
| kicker `ACCOUNT A-11812 · CUSTOMER — NOT LINKED` | `ACCOUNT A-11812` — the customer half appears only when one is linked (`ACCOUNT AC-2026-00052 · CUSTOMER C-00050`) |
| five KPI tiles | **four**: `BALANCE` (with the due-date line beneath it) · `PLAN FROM UNIT` · `LAST ACTIVITY` · `DEPOSIT ON FILE` |
| a `DUE DATE` tile of its own | the due date is a **sub-line of Balance** — `Due date not known yet` |
| an `AGEING` tile (`ACC-02` only) | **nothing.** The words *past due* appear nowhere on the detail, while the LIST shows an Ageing column |
| eleven-to-fourteen named groups | **eight**: `Recent bills` · `Usage trend` · `Account` · `Customer` · `MAILING ADDRESS` · `Payment method` · `Deposit & credit` · `Portal access` |
| a `SERVICE` group, a `METERS ON THIS UNIT` group, a `PLAN` group on the Overview | **none of the three exists** — the plan is in the KPI tile, the meters are their own tab |

⚠ **ONE OF THOSE DRAWN CHIPS COLLIDES WITH A RATIFIED RULE AND THE RULE WINS.**
`Autopay off` as a grey pill is refused by `B18 §5.2.3` — *"no `Autopay on` pill
(absence is not a grey pill)"* — and the code says so at the pill. **B14 rule 38**
puts the UI rules above a drawing on how a control is CONSTRUCTED, so a build lane
must not add it back on this drawing's authority.

⚠ **AND THE MISSING AGEING IS NOT A STYLE DIFFERENCE — IT IS THE BLUEPRINT'S OWN
RULE 4**, and that rule is a PO ruling of 2026-09-10 that is in no file of this
repository. See finding **F5**.

### 2.3 · The truth tables, re-measured

The blueprint measured each control on one account per status. This lane re-measured
the two rows that carry a finding.

| control | status measured | drawn | as built |
|---|---|---|---|
| `Close out` | `pending_activation` (`A-12048`) | *live — wrong* | **LIVE** — confirmed on screen |
| `Close out` | `disconnected` | *no account* | **NOT CONFIRMED — the tenant seeds none** |

---

## 3 · FINDINGS, EACH ROUTED

**The routing question is `22-product-maintenance-process.md`'s, and it is about the
USER, not the code: _can a user do this task in the product today?_ No → BUILD.
Yes → MAINTENANCE.** Where it was ambiguous it went to DEFECT, per
`13-change-process.md` §1.

> ⚠ **STAMPED 2026-09-12 — FIVE OF THESE ROWS ARE NOW CLOSED AND THIS TABLE STILL
> READS AS OPEN.** `CR-094-BRC01` step 2 wave B repaired `DEF-CUS-4998` (F1),
> `DEF-CUS-4999` (F2), `DEF-CUS-5000` (F3), `DEF-CUS-5005` (F4) and
> `DEF-CUS-5004` (F7), shipped as **`2.237.11`**. `DEF-CUS-5008` — lane 5's row
> for the same two lines as F2 — is closed **`duplicate`**. The repair, its four
> judgments and what it could not prove are
> **`CR-094-wave-b-step2.md`** in this folder; the ruling row is
> `12-governance/02-decision-log.md`, 2026-09-12.
> **F5, F6 and F8–F13 are UNTOUCHED by that wave** and stand as written.
> This stamp exists because a register row's STATUS is authoritative and its
> BODY is what a lane actually reads (`DEF-WRK-4030`) — and the same is true of
> a findings table.

| # | finding | routing | register row |
|---|---|---|---|
| **F1** | Two surfaces of this screen still tell a clerk the customer portal does not exist — the Add note dialog's *Visible to the customer* hint and the Audit tab's portal-actor hover. **And `AccountActions.test.tsx:295` asserts the false sentence is present**, so the suite defends it. | **MAINTENANCE** — a clerk reads the note screen today and it lies | `DEF-CUS-4998` |
| **F2** | The Record payment modal shows `2410.000000 USD` and pre-fills `#amount` with `2410.000000`. Hard rule 2 says money displays 2. The shared formatter exists and the same balance renders `$2,410.00` two inches away. | **MAINTENANCE** — money, on the screen that takes money | `DEF-CUS-4999` |
| **F3** | `Sub-type` prints the raw enum `small_commercial`. B14 rule 32 forbids an internal code in clerk-facing copy; the Category cell beside it resolves its catalogue correctly. | **MAINTENANCE** | `DEF-CUS-5000` |
| **F4** | `Close out` renders LIVE on a `pending_activation` account and disabled on all four statuses it could be for. The gate names the two states that refuse and lets everything else through. | **MAINTENANCE** | `DEF-CUS-5005` |
| **F5** | **Four PO rulings of 2026-09-10 exist only in the blueprint and in no file of this repository** — *"keep all buttons on screen"*, *"keep all icon only disable them"*, *"i will keep all header info and manage it"*, *"we should have all these details captured on screen"*, *"logically group the information, give group a heading…"*. Same class as `DEF-CUS-4996` / `BR-CUS-1046`, which `CR-094` §0 already landed two days late. | **MAINTENANCE** (record) — recorded in the decision log by this lane; **no `BR-` id minted** | `DEF-GOV-5006` |
| **F6** | `08-screen-layouts.md` and this CR both say §12 lists **21** rows. **It lists 17.** `ACC-S11`–`S13` are §10 FINDING ids with no register row and `ACC-S19` appears nowhere; the register's own explainer says the series is `S1…S10`. | **MAINTENANCE** (record) — both documents corrected, dated | `DEF-GOV-5007` |
| **F7** | Three `customers.account.arrives.*` sentences are in the catalogue and on no screen (`customer`, `customerTitle`, `usage`). Five of eight are rendered. | **MAINTENANCE** | `DEF-CUS-5004` |
| **F8** | **An account cannot be corrected from anywhere in the product.** `PATCH /accounts/{id}` is mounted, handled, audited and tested; `endpoints.ts:9012` records that it *"still has no caller and is still not wrapped"*. No Overview group carries an Edit control except the disabled `Update method`. | **BUILD** — `ACC-S1` + `ACC-S15`, `R5` draws six surfaces. **No defect row: nobody ever built it.** | — |
| **F9** | **A master account has no Accounts tab.** Twelve tabs on `AC-2026-00052`, and `?tab=accounts` falls through to Overview. | **BUILD** — `ACC-S17`, `R7`. Hard rule 8 is SATISFIED by the remedy: *"there is no `parent_account_id`, no child accounts and no rolled-up balance… an account list with a premises filter and a status column"* — it stores no address of its own. | — |
| **F10** | ✅ **BUILT 2026-09-12 (step 2 wave I, `2.239.10`).** This read: *"An account can hold no document. `BR-CUS-036` is CONFIRMED and names an `account_documents` table; neither the table nor an upload endpoint exists, and the tab draws five column heads over the stated absence."* **Every clause of that was true and none of it is now.** `customers/0042` creates `account_documents`, `0043` puts RLS `FORCE` on it, `GET|POST /accounts/{id}/documents` are served and the tab is a real list — search, the five confirmed type filters, sortable columns, the pagination footer, an empty state and an upload form. The two sentences that stated the absence are **deleted from all eleven catalogues** in the same commit (hard-won law 1). ⚠ **ONE DIVERGENCE FROM THE DRAWING IS RECORDED RATHER THAN BUILT:** `ACC-T10`'s toolbar draws the chips `All` · `Correspondence` · `Evidence`, and **`Evidence` is not one of `BR-CUS-036`'s five CONFIRMED values** (System · Contract · KYC · Payment · Correspondence). A wireframe cannot amend signed law, so the filter offers the five and a test asserts the word `Evidence` appears NOWHERE on the tab. ⚠ **AND `Export` IS NOT DRAWN:** nothing registers this resource with `POST /exports`, and `BR-SHL-010` keeps an undeclared capability unrendered — not drawn disabled either, which is `BR-SHL-025`'s posture for a control this ROLE cannot use, not one the PRODUCT does not have. | **BUILD** — `ACC-S8`, **done**. **No defect row**, as classified: the screen was honest about it, and a confirmed rule that was never implemented is unbuilt work. | — |
| **F11** | ~~**There is no way to write to the customer from this screen.** Seven icons and six buttons and not one sends a word; `R6` adds an eighth icon in two views.~~ ⚠ **BUILT 2026-09-12, `2.241.0` — wave K.** An eighth glyph opens a Communication dialog in `R6`'s two views. It **queues** and never sends (`BR-NOT-013`), and every channel row says whether it will actually leave. The history half is `GET /outbound` with `f.account_id` — **no new server read**. Four of the drawing's five kinds are refused by name with the rule that owns them. `CR-094-wave-k-step2.md` in this folder. | **BUILD** — `ACC-S16` ✅ | — |
| **F12** | Thirteen quick actions, and nine of them take the clerk off the account. `R4` draws all thirteen as dialogs over it. | **BUILD** — `ACC-S14` | — |
| **F13** | **`R5`'s sixth dialog, *Change the unit this account is on*, collides with a signed rule and needs a ruling before anything is built.** `services.update_account:3223` refuses `unit` by name — *create-only, never patched* — citing `BR-CUS-017`, which is CONFIRMED. | **QUESTION** — minted as **`OQ-CUS-1769`** | — |

### 3.1 · Three things this lane deliberately did NOT file

* **`?tab=paymentplan` silently renders Overview.** No link in the product builds
  that address; a tolerant fallback on an unknown tab value is a design choice, and
  the blueprint reports it as a fact rather than putting it in §12. **Reported, not
  filed** — but a stale bookmark lands a clerk on the wrong tab with no sign, and
  that is worth a sentence in step 2's scoping.
* **Every disabled control carrying its reason.** `Adjust`, `Send statement`,
  `Print bill`, `Issue credit`, `New adjustment`, `Upload document` and
  `Update method` are all **registered refusals under `BR-SHL-025`**, each with its
  sentence on screen. *A held control and a broken control look identical on screen*
  — these were checked against the rule and the code before being left alone.
* **The blueprint's own internal contradictions** beyond F6 — `R5`'s prose says
  *"Twelve groups, twelve controls… Six are live"* while its own caption says
  *"eleven groups, eleven controls — five live"*, and the drawing shows twelve
  headings. That is the prototype disagreeing with itself; it is recorded here so a
  build lane counts the drawing rather than either sentence, and it is not a product
  defect.

---

## 4 · EVERY STATED ABSENCE ON THIS SCREEN, QUOTED

**An absence is a decision.** These are the product's own words where the product
speaks, and the drawing's where only the drawing does.

### 4.1 · On the running product, read off the screen

| where | the sentence, verbatim |
|---|---|
| Overview · Balance tile | `Due date not known yet` |
| Overview · Recent bills | `No bill has been issued on this account yet.` |
| Overview · Usage trend | `No readings have been recorded for this account yet, so there is nothing to chart.` |
| Overview · Account | `Returned payments and the bad-address flag are written by the returned-mail workflow, which is not built — both read as their column default today.` |
| Overview · Mailing address | `Same as the service address. No separate mailing address is on file.` |
| Overview · Customer record | `This is one contact on one account. When the account is linked to a customer record, the customer's other accounts are listed further down.` |
| Overview · Payment method | `The stored payment method and its verification state belong to the payments module. Autopay is recorded on the account, and nothing collects on it in this version.` |
| Overview · Deposit & credit | `a deposit reaches this register when a deposit payment clears` · `Not accrued` · `Not computed` |
| Overview · Portal access | `Nobody has signed up` · `Never signed in` |
| Documents tab | ~~`Account documents have no table and no upload endpoint. Nothing here can be listed, and nothing can be uploaded yet.`~~ — **RETIRED 2026-09-12 (wave I, `ACC-S8`)**: the string is deleted from all eleven catalogues and the tab is a real list. |
| Add note dialog | ⚠ `This flag is recorded and does nothing yet: there is no customer portal in this version, so no customer can read the note either way.` — **THIS ONE IS FALSE.** `DEF-CUS-4998` |
| Audit tab (hover) | ⚠ `The log records who acted, not the channel they acted through. An automation records its own name and version. There is no customer portal in this version, so no entry can come from a customer.` — **THE LAST CLAUSE IS FALSE.** `DEF-CUS-4998` |
| Payment method | `There is no stored payment method to update. The method and its verification state belong to payments, which keeps none for an account in this version.` |

### 4.2 · On the drawing, where the product has no words of its own

| where | the sentence, verbatim |
|---|---|
| Overview (`ACC-02`) | `NO METER IS ASSIGNED` — *"This account holds two service agreements and no measuring asset. Consumption cannot be read and a metered bill cannot be raised until one is assigned."* |
| Overview (`ACC-02`) | `NO BILL HAS BEEN ISSUED` — *"No bill has been raised on this account yet. The balance above was carried in as an opening figure, which is why the ageing is counted from that rather than from a bill's due date."* |
| Overview (`ACC-02`) | `NO MAILING ADDRESS OF ITS OWN` — *"The bill goes to the service address above. A mailing address is a SEPARATE fact and is shown here only when it differs — two identical addresses on one screen teach a clerk to skip the second."* |
| Overview (`ACC-T01`) | `NOT LINKED TO A CUSTOMER RECORD` — *"This is one contact on one account. Until it is linked, the panel below can only list the account you are on."* |
| Bills | `Three of these are unpaid and not one says so.` and `USAGE BEHIND EACH BILL` — *"Usage is summed from meter reads and that summary is not built, so no number is drawn rather than a zero that would read as 'they used nothing'."* |
| Payments | `THE DEPOSIT ROW IS DRAWN HERE AND THE PRODUCT WOULD NOT LIST IT` — *"Nothing writes the deposit register yet, and whether a held deposit belongs in this list has not been settled."* |
| Credits | `A credit is raised from the bill it corrects, never from this tab.` |
| Read log | `NO READER AND NO NOTE` — *"a 'side gate locked' belongs to the work order, not to the read."* |
| Read log | `EXPORT IS EMPTY ON THIS METER` — *"every row is a dash rather than a zero, which would read as 'it exported nothing'."* |
| Work | `This list is not in date order and the footer has to say so.` |
| Adjustments | `These rows are the shape, not the state.` — *"no endpoint lists an adjustment and none posts one, so this table cannot be filled from anywhere today."* |
| Documents | **RETIRED 2026-09-12 (wave I, `ACC-S8`)** — the tab draws real rows now, so neither sentence is shown. |
| Notes | `A NOTE CANNOT BE CORRECTED ONCE IT IS SAVED` — *"there is no ruling yet on whether the original wording stays visible to the next person who reads it."* |
| Audit | `LINKS BACK TO THE RECORD ARE NOT SHOWN` — *"a clerk cannot open the disconnect case from the line that announces it, or the bill from the line that issued it."* |
| Move-in | `THERE IS NO UNIT PICKER ON THIS STEP` |
| Change plan | `There is no step rail on this wizard.` |
| Activate account | `There is no wizard and no confirmation.` |

### 4.3 · What this lane believes is missing from the drawing — said, not added

* **Nothing on any drawing shows this screen below 1280px.** The blueprint says the
  phone drawings were cut on the PO's instruction and calls that *"a real gap rather
  than a tidy-up"*. It is repeated here because the header is the part that grows
  without a ceiling — eleven services is three rows of chips by the blueprint's own
  measurement — and the account detail is opened twenty times a day.
* **No drawing shows the screen in its LOADING or FAILED state.** The code has both
  (`FailedWithRetry` with a cancel back to the list; panel skeletons that hold money
  cells' height). A drawing that shows only the default state is a third of a screen
  by the build skill's own §2.
* **No drawing shows the `?order=` work-order drawer** over the Work tab, although
  the screen's own header line declares it.

---

## 5 · THE SPECIFICATION REGISTER, SETTLED

**§3b of the CR asked step 1 to settle this by reading §12 end to end. This is that
reading, taken from the rendered rows and not from the id list.**

**§12 lists SEVENTEEN rows.** `ACC-S1` `S2` `S3` `S4` `S5` `S6` `S7` `S8` `S9` `S10`
`S14` `S15` `S16` `S17` `S18` `S20` `S21`.

* **`ACC-S11`, `ACC-S12`, `ACC-S13` are §10 FINDING ids**, not commitments — the
  alphabetical default, the missing `/`, the six decimals of money. They carry no
  register row.
* **`ACC-S19` appears nowhere in the document this lane could find.**
* **The register's own explainer box is a third figure and it is wrong too:**
  *"`ACC-S1`…`ACC-S10` is a series minted for this document"*, above a table that
  runs to `S21`.
* The cover's **10** is therefore not the register's count either. **The three
  figures in the document are 10, "S1…S10", and a table of 17 whose highest id is
  21.** Quote **17 rows, ids running to `ACC-S21`**, and say it came from counting
  §12's rows on pages 207–209.

### 5.1 · The ten commitments that name screen 02 — **ten, not seven**

| id | what it commits to |
|---|---|
| `ACC-S1` | A clerk can correct an account's details without a wizard |
| `ACC-S3` | No screen tells a clerk the customer portal does not exist — *Notes tab and Audit tab* |
| `ACC-S5` | The catalogue stops carrying sentences no screen shows (`01 · 02`) |
| `ACC-S6` | A hold that has expired goes red instead of going stale (`01 · 02 · 03 · 04 · 08 · 12 · 14`) |
| `ACC-S8` | An account can hold a document — ✅ **BUILT 2026-09-12, step 2 wave I, `2.239.10`** |
| `ACC-S14` | Every quick action opens as a form over the account, with all of its fields and a recap |
| `ACC-S15` | Every group on the Overview carries an edit control, disabled with its reason |
| `ACC-S16` | A clerk can write to the customer from the account, and see what has already been sent — **BUILT 2026-09-12, `2.241.0`, wave K** |
| `ACC-S17` | A master account lists every account at its address, with each one's status |
| `ACC-S21` | Each queued record opens onto its own page (`01 · 02`) |

⚠ **`ACC-S4` — every date field behaves the same way — names screens
`03 · 04 · 08 · 10 · 11 · 12 · 13 · 14` AND NOT `02`.** The lane brief's list of
seven is a subset; the three it did not name are `ACC-S5`, `ACC-S6` and `ACC-S21`.

### 5.2 · The remedies that draw this screen

`R1` (`ACC-S1`, p150–151) · `R4` (thirteen dialogs, p154–174) · `R5` (six edit
surfaces, p175–183) · `R6` (the communication action in two views, p186–188) ·
`R7` (the master account's Accounts tab, p189–191). **Every one carries the chip
`NO COMMITMENT` on its heading, and each explains why in its own last paragraph:**
*"A drawing is not a commitment. These are descriptions until they appear in a
commitment card in §12."*

---

## 6 · WHAT STEP 2 SHOULD KNOW BEFORE IT STARTS

1. **`OQ-CUS-1769` blocks `R5`'s `E07` and nothing else.** The other five edit
   dialogs need no ruling; two of the six need no server work at all.
2. **`CR-093-BRC01` owns the shared-component items** that reach this screen — the
   sort's third click, the pager, the row-action cap, the KPI gap. **Neither CR may
   fix the other's rows.**
3. **F5's four rulings must be in `02-decision-log.md` and the module's
   `02-business-rules.md` before anything is built to them** — that is step W's
   timing rule and it is what `DEF-CUS-4996` cost last time.
4. **A `disconnected` account must be seeded** before `Close out` can be proved to
   work at all, in either direction.
5. **The six-decimal fix is two lines and the guard is worth more than the fix** —
   a check that no money-carrying JSX interpolates an amount outside the shared
   formatter, proved RED on `AccountActions.tsx:321` first.

---

*Read the drawings, not this document, where the two disagree — this is a map of
what was measured, and every figure in it says where it came from.*
