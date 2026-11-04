# CR-165-BRC10 — Plans & Rates › Taxes & fees redesigned end to end: list, New tax wizard, details and edit, built from 33 desktop images

**Raised:** 2026-10-02/03, by the Product Owner, in chat, over seven review rounds of the
mock-up (artifact `Gv7YJoQbydd1aj42te9cRk`, version 8), ending in a GO. The ruling is the
decision-log row of 2026-10-03 headed *"GO ON THE TAXES & FEES REDESIGN — TEN TASKS IN FOUR
ROUNDS …"* (commit `375f1e499`); nothing it settles is put back to the PO (hard-won law 13).
**The drawing:** `05-prototype/taxes-fees-2026-10-03/` — `README.md` (the eight ruled points
and the index of 33 images), `images/01…33`, `taxes-fees-mockup.html` (an index, never the
specification — B14 rule 42), `web-walk.md` (task 9).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed by `CR-156-BRC10` in
`12-governance/14-id-reservations.md`). `10-scripts/allocate.py cr` answered **165** against
the remote and `--verify 165` reported it free on every branch, twice (at allocation and
again after the worktree was brought to tip `ac38c3cca`).
**Classification:** **MAINTENANCE** (`12-governance/22-product-maintenance-process.md`) —
a live screen redrawn end to end is maintenance, borrowing only the drawing step from
Build; so REPRODUCE comes before any fix (§4 below). Where today's screen contradicts the
approved drawing it is filed as a defect (§5). The parts the product never did — a *New rate
from a date* path, an authority-accounts list — are change and are carried here.
**Touches 🔒 rating** (tax rows, versions, the billing lookup): HUMAN-REVIEW-PENDING regime;
golden tests must not move.

---

## 0 · What arrived, in the requester's words

Quoted from the decision-log row of 2026-10-03, in the PO's order:

> *"we need to revamp design of tax in plans and rate - i will give all screenshot and issues
> dont start the work yet just understand first"* · *"only active utility services on Utility
> tenant should be shown and we have to add all services as part of drop down; all customer
> class - drop down"* · *"I see this information in details view - but we did not take this
> information dueing tax creation - why - … can we take it up during creation itself and
> display it in details view; … Edit - button should be at top right"* · *"on list view show
> dates From and To seperately show Tax Version and SHow GL codes"* · *"Due and Your account -
> It should be drop down - Your account can come from settings we ahve configure accounts
> sections"* · *"what the point of so many button cant we simiplify based ona ctions"* · *"We
> dont use side panel for edit - you will need to send it back to Edit form - You can use add
> form with variation - your desgn is correct - dont use panel"* · *"You can merge Overview and
> Rate history - in audit we can have histroy - rate history is not adding uch value"* ·
> header items: *"im okay - pls update - My recommendation is to add 1–5 and leave out the
> rest."* · *"I want all screens to be created using Images in drawing and not text/content"* ·
> *"phone edit will not required; this si desktop version"* · **GO:** *"start Tax related
> execution - The 10 tasks"*.

The web walk was widened before it ran: *"I want to create Tax code for all juridictions , all
Utility Services { single or all or multple} I want to create tax for Customer class - take
menaingful pratcice scenarios ; then save these codes. then view these code see all
ifnrmation saved correctly and displayed correctely then edit those tax codes and see updates
are correctly saved - inlcuding version hisorty and it return only 1 record when billing ask
it ; the changes reflects in plans audit"*.

## 1 · Classified

**MAINTENANCE, with change carried.** The user can do this task in the product today (create,
view and correct a tax), so it is maintenance, not Build. Screen problems are defects
(`DEF-RAT-9277`, `9274`, `9272`, `9273`); *New rate from a date* and the authority-accounts
list are things the product never did and are change. Fast path does **not** apply: it
touches rating (🔒), money (rate entry, the billing lookup) and stored rows (versions).

## 2 · What signed statements it touches

* **`CR-013` part 4 (TAXES & FEES, PO verbatim 2026-08-18, `11-change-requests.md` §CR-013 ·
  PART 4).** *"Detail — Overview · Rate history (every rate with statutory date, citation, and
  amount collected under each — the primary audit artefact) · Remittance (frequency, due-date
  rule, liability GL, authority account number, last filings) · Exemptions … · Where it
  applies."* and *"TAX-02 wizard — 4 steps … 'Jurisdiction / Rate & base / Remittance / Review
  & save'"* and, shared rules, *"in-place edits of an active version are refused outright, even
  for Owner/Admin, because rate history is an audit artefact; a historic typo is fixed by a
  documented correction version with a reason."*
  → **The detail TABS are SUPERSEDED by the 2026-10-03 ruling** (*"You can merge Overview and
  Rate history - in audit we can have histroy"*): tabs become *Overview · Plans · Audit*, the
  rate history lives as a versions table on Overview and every change with its reason in
  Audit. Today's product already shows three tabs (CR-087 lane B, 2026-09-08), so this is a
  re-statement of the screen, not a removal of a live tab (P40 not reproduced).
  → **The FOUR-step wizard comes back** (*What it is · How much · Filing · Review & save*):
  part 4 drew four with *Remittance* as step 3; CR-087 B1 folded it to three and moved
  remittance to the detail page; the PO's ruling restores a filing step at creation and
  keeps it read-only on details.
  → **The shared rule STANDS and the drawing obeys it:** *Name and filing* edits the same row
  with rate and reach LOCKED; a rate change is a new row (*New rate from a date*); a typo is
  *Fix a mistake* with a required reason, old row superseded and kept.
* **`US-RAT-009`** (`04-docs/05-modules/06-rating/05-user-stories.md:15`, epic
  `EP-RAT-03`): *"a 4-step New Tax/Fee form — Jurisdiction (name, authority, reference/permit
  #, level …, applies-to services) → Rate & base (Percent of subtotal / Flat per bill / Per unit
  of usage) → Remittance (liability GL, remit-to, frequency, filing form, effective window) →
  Review & save"*. The redesign is the same four-step shape with the PO's new wording; the
  story's frontmatter and §1 must be amended in the building round (W, before building on it).
* **`BR-RAT-103`** (CONFIRMED 2026-08-21): *"A TAX HAS FOUR STATUSES, THREE OF THEM DERIVED —
  AND IT PRICES A BILL ONLY INSIDE ITS EFFECTIVE WINDOW."* Statuses Active/Draft/Scheduled/
  Expired (+ `inactive`). The drawing's More ▾ *Retire* must map onto this set, not add a
  fifth stored status (see §7 item 4).
* **`BR-RAT-104`** (CONFIRMED 2026-08-21): *"AN IN-FORCE TAX'S RATE HISTORY IS NOT EDITABLE IN
  PLACE; A TYPO IS FIXED BY A DOCUMENTED CORRECTION ROW OVER THE SAME WINDOW."* and *"WHAT IS
  REFUSED IS RATE HISTORY, NOT EVERY FIELD — `services.TAX_RATE_HISTORY_FIELDS` is the list,
  and filing detail … stays editable in place."* — *Name and filing* is exactly this boundary.
  *"Whether a correction MUST also restate [issued bills] is `OQ-310`, unruled"* — the drawing
  keeps it unruled (*"re-billing stays `OQ-310`"*).
* **`BR-RAT-1016`** (PO 2026-09-17): *"THE THREE VERBS ARE THE SAME FOR EVERY PRICED OBJECT:
  EDIT while it has priced nothing · CORRECT over the SAME window when the figure recorded was
  wrong · CHANGE over a NEW window when prices move."* — the three Edit choices are these three
  verbs. **Verb 3 (CHANGE) has no service for a tax today** (§6 g).
* **`BR-RAT-087` / `BR-RAT-092`** (store 4/6, display 2): rate typed and shown as a percent is a
  display rule; storage stays a fraction at 6 places. No ❄️ B4/B5 figure moves.
* **`CR-008` (PO 2026-08-17, "ONE EDITOR, storage stays put"):** *"Settings → Accounting is the
  only place a GL code is edited. 'editing and chaigng will be done in setting only'."* — the
  drawing's step 3 picks a **Liability account** in the wizard. That is a collision to state,
  not assume (§7 item 2).

## 3 · The ten tasks, as put to the PO

1 images · 2 rulings + reproduce every problem on today's screen and file it · 3 back end ·
4 New form · 5 list · 6 details · 7 edit · 8 eleven languages · 9 full web walk and fix ·
10 close (version, every problem marked fixed with its build). **Four rounds**, run by the
coordinator; **round 1** is tasks 1 (the 33 images, commit `375f1e499`) and 2 (this file),
plus the read-only fact-finding for task 3 (§6). Each later round appends its record here.

## 4 · Problems on today's screen (task 2 — REPRODUCED before anything is fixed)

**How:** build `2.467.27` (front end built `vite build --mode wolocal`; API `runserver` on a
private PostgreSQL 16 database `sbh_taxr1`, `migrate` + `seed_demo`, Brazos Bend, signed in as
Dana, System Admin), Chromium at 1440 wide. Script `10-scripts/cr165_taxes_fees_before_walk.mjs`;
its full printed output is `08-qa/taxes-fees-2026-10-03/before/walk-output.txt`; 22 screenshots
in `08-qa/taxes-fees-2026-10-03/before/`, each opened and checked not blank. The rating code
at that build is byte-identical to the branch tip `ac38c3cca` (`git diff --name-only` shows no
rating, tax or locale file changed in between). Brazos Bend switches on **2 of 11** services
(electric, water). The walk creates *ann arbor City* by typing **1.5** in the rate box (meaning
1.5 %), which today's box stores as **150 %**; a second tax at 62.5 %; then corrects the first.

P-numbers follow the mock-up's four arrays in order: FIXES → P1–P20 (wizard), LISTFIX →
P21–P28, DETFIX → P29–P43, EDITFIX → P44–P50. *"Today"* is the drawing's wording.
A native `<select>`'s open list is drawn by the browser and cannot be photographed headless;
where a problem is about an open list the walk gives the select a `size` for the photo and
says so.

| P | Area | Today (drawing's words) | Result | Evidence and what was seen |
|---|---|---|---|---|
| P1 | Wizard s1 | Services lists all 11 services | **REPRODUCED** | `w02-services-list.png` — Electric … Fire, 11 options; the utility runs 2 |
| P2 | Wizard s1 | Services: a text line plus a separate add box | **REPRODUCED** | `w01-step1-empty.png` — grey *All services* line, then *Add a service…* box |
| P3 | Wizard s1 | Customer classes: same two-part control | **REPRODUCED** | `w01` — *Every customer class* line + *Add a customer class…* box |
| P4 | Wizard s1 | Class list opens over "Named place" | **NOT REPRODUCED** | `w03` — *Named place* sits ABOVE Services and Classes, so a list opening downward from the class box cannot cover it; the browser-drawn popup itself cannot be photographed |
| P5 | Wizard s1 | Red capital headings beside normal labels | **REPRODUCED** | `w01` — red *SERVICES*, *CUSTOMER CLASSES* beside plain *Boundary* |
| P6 | Wizard s1 | "Recorded City limits decide first…" is unclear | **REPRODUCED** | `w03`/`w04` — *"Recorded City limits decide first. This name covers the rest."* |
| P7 | Wizard s1 | "78 of 84 match" and a run-on list of codes | **REPRODUCED** | `w04` — *"6 of 6 premises match. 0 by recorded City limits. 6 more by name."* then *P-00001 · 1408 Bluestem Ln — P-00002 · … — P-00003 · …* on one line |
| P8 | Wizard s2 | Rate typed as a fraction | **REPRODUCED** | `w05`/`w07` — help *"Enter a fraction: 6.25% is 0.0625."*; 1.5 typed |
| P9 | Wizard s2 | No warning for a very high rate | **REPRODUCED** | `w07` → `w08` — 1.5 passes step 2 and Review with no warning; saved as **150.00 %** (`l01`) |
| P10 | Wizard s2 | Basis list opens over the Rate box | **REPRODUCED** (layout) | `w06` — Basis stacked directly above Rate, list expanded for the photo covers the Rate box's place; the drawing sets them side by side |
| P11 | Wizard s2 | Tick boxes jammed together | **REPRODUCED** | `w05` — *Usage charges* box touches *Base service charges* box |
| P12 | Wizard s2 | "Only these two can be taxed." | **REPRODUCED** | `w05` — the sentence under the ticks |
| P13 | Wizard s2 | Confusing discount example | **REPRODUCED** | `w05` — *"Example: $1.00 credit, 2% tax. After discounts $3.78, before $3.80."* |
| P14 | Wizard s2 | Rounding says "leave blank", but has no blank | **REPRODUCED** | `w05` — help *"Leave blank to use standard rounding."*; six options, none blank |
| P15 | Wizard s2 | Subtitle repeats the heading | **REPRODUCED** | `w05` — *"Set the rate and what it is charged on."* / *"Set the rate, dates and rounding."* |
| P16 | Wizard s2 | "Exemptions are on the Exemptions tab." as text | **REPRODUCED** | `w05` — plain text; and today's details have NO Exemptions tab (Overview · Plans · Audit), so it points nowhere |
| P17 | Wizard rev. | Review shows the raw "0.625" | **REPRODUCED** | `w08` — Rate **1.5**; `e03` — Rate **0.015** |
| P18 | Wizard rev. | Dates as 2026-10-01; no example | **REPRODUCED** (half) | `w08` — no example bill anywhere on Review. The ISO date was not seen: the walk left dates blank and the boxes read mm/dd/yyyy (`w05`) |
| P19 | Wizard | Code, bill label and filing only on the details page | **REPRODUCED** | `w01`–`w08` ask none of them; `d01` *"These can be changed at any time, so the wizard no longer asks for them."* |
| P20 | Wizard | Due date and authority account typed as free text | **REPRODUCED** | `d01` — *Due-date rule* and *Your account number with the authority* are text boxes |
| P21 | List | Long paragraph above the table | **REPRODUCED** · **FIXED 2.471.0** | `l01` — *"Taxes and franchise fees are computed per bill line, not per bill — …"* |
| P22 | List | Name repeats the authority | **REPRODUCED** · **FIXED 2.471.0** | `l01` — *ann arbor City · City*, *Local · Bexar County · Local* |
| P23 | List | "150.00% of the taxable amount" wraps | **REPRODUCED** · **FIXED 2.471.0** | `l01` — *150.00% of the / taxable amount* on two lines |
| P24 | List | No warning that two taxes charge over 20 % | **REPRODUCED** · **FIXED 2.471.0** | `l01` — 62.50 % and 150.00 % rows, no banner, no pill |
| P25 | List | No reach in the list | **REPRODUCED** · **FIXED 2.471.0** | `l01` — columns: Tax or fee, Applies to, Rate, Remittance, Liability GL account, Status, Actions |
| P26 | List | Long GL account text wraps | **REPRODUCED** · **FIXED 2.471.0** | `l01` — *2520 — Current portion of / long-term debt* |
| P27 | List | One "Dates" cell; no version | **REPRODUCED** (worse) · **FIXED 2.471.0** | `l01` — no date column at all, no version; `l02` — after one correction the superseded **150 %** row and its **1.50 %** correction both read *ann arbor City · Active*, nothing tells them apart |
| P28 | List | Pencil edits a live tax's rate | **REPRODUCED** · **FIXED 2.471.0** | row pencil → `/…/edit` (`TaxesFeesTab.tsx:359`), the correction form with the rate box enabled (`e02`) |
| P29 | Details | Kicker "TAX · CITY · CITY" repeats itself | **REPRODUCED** | `d01` — *TAX · CITY · CITY* |
| P30 | Details | Header says little | **REPRODUCED** | `d01` — name and *Active* only; no code, version, Over 20 %, filing due |
| P31 | Details | Long sentence under the title | **REPRODUCED** | `d01` — *"Effective from: — · Liability GL account: 2520 — … · Live taxes are corrected, never edited. Issued bills keep their rate."* |
| P32 | Details | "Not worked out yet" band | **REPRODUCED** | `d01` — *NOT WORKED OUT YET* band on every tab |
| P33 | Details | Every section opens with an explanation | **REPRODUCED** | `d01` — a sentence under each of What is taxed, Who it reaches, On the bill, Remittance |
| P34 | Details | Rate tile shows 150 % without a warning | **REPRODUCED** | `d01` — *150.00% of the taxable amount*, no warning, no $60.00 effect |
| P35 | Details | Four buttons for one job | **REPRODUCED** | `d01` — Duplicate, Edit, Retire + *Save filing details*; Duplicate and Retire are greyed (no route — `DefinitionDetailPage.tsx:643`) |
| P36 | Details | Edits happen in a side panel | **NOT REPRODUCED** | `e01` — Edit opens the full-page form at `/…/edit`; no side panel anywhere |
| P37 | Details | Filing typed in on details only | **REPRODUCED** | `d01` — the whole Remittance & filings form is on details (same fact as P19) |
| P38 | Details | Plans and Audit tabs empty | **NOT REPRODUCED** | `d02`/`d04` — Plans lists 3 plans (Industrial 1, Residential Standard 7, Small Commercial 2 — **UNITS**, not accounts); `d03` — Audit lists the rate row |
| P39 | Details | No rate history | **NOT REPRODUCED** | `e06` — Audit shows 1.50 % (reason, Dana Whitfield) over 150.00 % (*First recorded*). What IS missing is the versions table on Overview |
| P40 | Details | Rate history tab repeats Overview and Audit | **NOT REPRODUCED** | `d01` — tabs are already Overview · Plans · Audit (CR-087 lane B removed Rate history 2026-09-08) |
| P41 | Details | Filing section: 12 fields and long help | **REPRODUCED** | `d01` + `walk-output.txt` — 13 fields, a help sentence under most |
| P42 | Details | Due and authority account typed by hand | **REPRODUCED** | `d01` — both text boxes |
| P43 | Details | Allowance and penalty typed as fractions | **REPRODUCED** | `d01` — *"as a fraction — enter 0.005 for 0.5%"*, *"enter 0.015 for 1.5%"* |
| P44 | Edit | A side panel for edits | **NOT REPRODUCED** | `e01` — full-page form |
| P45 | Edit | One form for every kind of edit | **REPRODUCED** | `e01` — always *"Filing a correction"*; no choice of what to change |
| P46 | Edit | Rate and reach editable on a live tax | **REPRODUCED** | `e01`/`e02` — boundary, services, classes, basis and rate all editable; saved as a correction |
| P47 | Edit | New rate: old row's end typed by hand | **REPRODUCED** (in substance) | there is no *new rate from a date* path at all; on Edit the dates are locked (*"A correction keeps these dates."*, `e02`); the only route is a new tax with hand-typed From/To (`w05`), and a live row's end date cannot be set by any screen or service (§6 g) |
| P48 | Edit | Fix a mistake with no reason | **NOT REPRODUCED** | `e04` — Save refused: *"Say why this rate is being corrected, in a sentence someone will still understand in a year."* |
| P49 | Edit | Saving gives no picture of the rows | **REPRODUCED** | `e03` — Review lists fields only; no before → after, no bill example, no versions |
| P50 | Edit | Issued bills silently keep the wrong rate | **NOT REPRODUCED** | `e01` banner *"Issued bills keep their rate."*; `e03` *"Saving supersedes this rate now. Issued bills are untouched."* |

**Count: 42 reproduced (P10 as layout, P18 half, P27 worse than drawn, P47 in substance) ·
8 not reproduced (P4, P36, P38, P39, P40, P44, P48, P50) · 0 not a screen problem.** The
eight not reproduced are already the drawn behaviour or were fixed by CR-087; the build still
follows the drawing for them, but no defect claims them.

### Found while reproducing, outside the fifty (filed, not fixed)

* **`DEF-RAT-9275` — *Save draft & exit* on a NEW tax puts the tax in force.** The walk filled a
  1 % fee to step 2 and pressed it: the tax was stored `status: active, in_force: true`
  (`w09`, `w10`, `walk-output.txt`). `save()` sends no `draft` key; `POST /taxes` would create a
  Draft if asked. Worked case: a clerk half-way through a 150 % typo who presses *Save draft &
  exit* starts charging $90.00 on a $60.00 bill at the next run. Web-walk step 1.8 depends on it.
* **`DEF-RAT-9276` — *Fix a mistake* is refused on any tax that has a code.** `PATCH` code
  `TX-SUT` onto TX State Utility Tax, then `POST /taxes/{id}/corrections` → **422
  `rating.taxes.duplicate_code`**. `correct_tax` re-validates the row as a new tax
  (`services.py:7905`) and its own code counts as the duplicate; the DB's
  `uq_taxes_tenant_code_ci` would refuse the second row anyway. The drawing asks for a code on
  every tax at creation, so after the redesign every correction would fail.

## 5 · Defects filed (before anything is fixed)

| Defect | Area | Problems |
|---|---|---|
| `DEF-RAT-9277` | New tax wizard | P1–P20 |
| `DEF-RAT-9274` | List | P21–P28 |
| `DEF-RAT-9272` | Details | P29–P43 |
| `DEF-RAT-9273` | Edit | P44–P50 |
| `DEF-RAT-9275` | Wizard, Save draft & exit | outside the fifty |
| `DEF-RAT-9276` | Correction of a coded tax (server) | outside the fifty |

(The wizard row was first allocated `DEF-RAT-9270`; at push time `allocate.py defect --verify`
reported 9270 TAKEN — `DEF-PAY-9270` had been pushed by a sibling — so it was renumbered
`DEF-RAT-9277` before commit. `DEF-RAT-9271`'s number was taken the same way (`DEF-PAY-9271`)
while the list row was being filed, and the allocator refused and re-allocated. Hence the
four area rows are not consecutive.)

## 6 · Back end: what exists and what is missing (task 3 fact-finding, read only)

| | Question | What exists (file:line, branch tip `ac38c3cca`) | What is missing |
|---|---|---|---|
| a | A list of this utility's switched-on services | `GET /settings/services` (`apps/tenancy/api.py:461`) → `selectors.services_overview` (`apps/tenancy/selectors.py:1195`) returns every ACTIVE platform service (11) with `"enabled"` per row (`:1228`). The wizard already fetches it and maps **every** row (`TaxWizard.tsx:1332`), which is P1. Customer classes are a front-end constant `TAX_CUSTOMER_CLASSES` (`TaxWizard.tsx:1356`). | Nothing on the server: filter on `enabled`. The server's `_validate_tax` does not refuse a service the utility has switched off — worth adding so the dropdown is not the only guard. |
| b | `due_date_rule` | Free text, `models.Tax.due_date_rule` (`apps/rating/models.py:1529`, docstring *"Free text until the remittance worksheet needs to compute from it"*), validated only as text ≤ 120 chars (`services.py:7521`). | The six drawn choices fit as stored values, but **nothing computes a date from them**, and the header's *Filing due* (ruled item) needs a date. Task 3 must choose stored codes (e.g. the mock-up's `15n/20n/25n/lastn/q30/y31`) plus one evaluator; existing free-text values (none on the demo tenant) need a read-only fallback. |
| c | *Account with the authority* from Settings › Accounting | Settings › Accounting has a **Tax authorities** section that edits the **liability GL** on each tax row (`SettingsAccountingTab.tsx:700–735`; it writes `taxes.liability_gl_account_id`, `models.py:1672`), fed by the ledger chart (`GET /ledger/accounts`). The utility's account number WITH the authority is stored per tax as free text `taxes.remit_reference` (`models.py:1530–1535`, *"r10's 'TX Taxpayer #1-74-1234567-8'"*) and per authority as `tax_jurisdictions.reference_no` (`models.py:1300`). | **No authority-accounts list exists** — no table, no endpoint, no Settings screen holding *name + account number with the authority* (the mock-up's *"TX Comptroller · 32-1180455"*, *"Add one" → Settings › Accounting › Authority accounts*). Only GL accounts exist. See §7 item 1. |
| d | A tax version number | None stored (no `version_no` on `taxes`). Corrections are linked `corrects` / `superseded_by` (`models.py:1621–1643`) and walked by `tax_correction_chain` (`selectors.py:4956`, served as `GET /taxes/{id}/versions`, `api.py:897`). | A **new-rate** row has no link to the row it follows, so *v1 → v2* cannot be derived for a rate change; and a new row cannot carry the same code (`uq_taxes_tenant_code_ci`, `DEF-RAT-9276`). Task 3 needs a link between successive rows (or a series id) and a code rule for versions. The versions read also reports a superseded row's `status` as `active` (seen in `walk-output.txt`), because `tax_status` (`selectors.py:4645`) does not look at `superseded_by`. |
| e | Plans using a tax, with counts; an audit read | `GET /taxes/{id}/plans` (`api.py:882` → `selectors.tax_plans`, `:4865`) returns plan, *reached by* and **UNITS** — its docstring cites blueprint p35, *"The count is units, not accounts."* Audit: `GET /taxes/{id}/versions` (corrections only) and the general `GET /audit-log` filterable by `entity_type`/`entity_id` (`apps/audit/selectors.py:310–323`). | The drawing's Plans tab says *accounts*; the read counts units (judgment for task 6, §7 item 5). The drawn Audit (*who, what, when, why* for EVERY change, including name-and-filing edits) has no single read: name/filing edits write only `audit_log` `tax.updated` (`services.py` `update_tax`), which is pruned on retention (hard rule 4), and an audit filter by one row id misses the other version rows. |
| f | The billing lookup that picks a tax for a date | `selectors.plan_tax_rules` (`selectors.py:7884`) → `_authority_tax(jurisdiction, kind, service_date)` (`:7749`): rows of ONE authority and ONE form; the row whose window contains the date wins (`:7829`); **two in force on one date REFUSE** with `AmbiguousAuthorityTax` (`:7701`), never pick; superseded rows never price (`tax_in_force`, `:4694`). Explicit plan attachments follow `superseded_by` to the correction (`:8215`). | (1) It can return at most one row per authority and form, or refuse — so **two different taxes of one authority in the same form** (a State sales tax and a State utility tax, both %) refuse the bill. (2) No DB constraint stops overlapping windows; only the refusal at billing does. (3) An **attached** tax given a new rate from a date stops pricing when its old row ends, because attachments follow corrections, not dated successors. (4) **Per-meter is priced nowhere** (`plan_tax_rules` docstring) — web-walk tax 1.5 would bill $0.00. (5) A **deactivated** (`deleted_at`) tax still prices — a question the code explicitly declines (`tax_in_force` docstring; decision log *"stays declined"*), which the drawn *Retire* must not inherit. |
| g | How *New rate from a date* is saved today | **It is not.** `create_tax` (`services.py:7618`) makes an unlinked new row; `correct_tax` (`:7837`) copies the old window verbatim; `effective_to` is in `TAX_RATE_HISTORY_FIELDS` (`:7760`), so `update_tax` refuses it on a live tax. | **No path ends a live tax the day before a new rate.** Adding a dated new row beside an open-ended old one makes both in force on the new date and the bill refuses (f-2). Task 3 needs one service: lock the row, set `effective_to = new_from − 1 day`, create the new row linked to it, audit both, in one transaction — `BR-RAT-1016`'s verb 3 for a tax. |

**Also met while reading, for task 3 and task 9:** only `city_limits` and `state` boundaries
resolve (`PREMISES_SCOPE_KINDS_RESOLVABLE`, `selectors.py:8563`); *county*, *taxing district*
and *named list* reach nobody and are disabled in the wizard. The web walk's *Outside city
limits* boundary (taxes 1.4 and 1.7) does not exist on a tax at all — `BR-RAT-102` puts the
outside-city surcharge on the PLAN. Both are inputs to round 2's scoping, not decided here.

## 7 · Open items (not asked by this lane; each written so it can be put in one sentence)

1. **Where the authority accounts live (needs the PO — a fact only they hold, and it touches
   `CR-008`).** The drawing fills *Account with the authority* from *"Settings › Accounting ›
   Authority accounts"*, a list that does not exist. *Question:* "Should Settings › Accounting
   get a short list of the accounts you hold with each authority — a name and the number they
   know you by — that every tax picks from?" *Worked example:* the utility files with the TX
   Comptroller as **32-1180455**; today that number is typed again on each of its three State
   taxes, and a typo on one of them (32-1180544) sends one return under the wrong account with
   nothing flagging it. With a list it is typed once.
2. **The wizard picks the liability account (collision with `CR-008`, stated not assumed).**
   `CR-008` (PO 2026-08-17): *"Settings → Accounting is the only place a GL code is edited."*
   Image 13 makes *Liability account* a required dropdown on step 3. *Recommended reading for
   the coordinator to confirm:* the 2026-10-03 GO supersedes CR-008's one-editor rule for the
   moment of creation only — choosing an existing account in the wizard, still changing it
   afterwards only in Settings. *Worked example:* a new County tax created without an account
   is refused at its first bill (`BR-BIL-010`); picked at creation (2200-03 · Tax payable ·
   County), it bills.
3. **Due-date codes and the *Filing due* date** — our judgment (task 3): store the six as
   codes, compute the next due date from the tenant's today; e.g. *20th of the next month* on
   10/03/2026 → **11/20/2026**; *30 days after the quarter ends* → **10/30/2026** for Q3.
4. ***Retire* in More ▾** — our judgment (task 3/6): retire by ending the window (status
   *Expired* from the chosen date, `BR-RAT-103`'s own vocabulary) rather than `deleted_at`,
   which still prices (§6 f-5). *Example:* retire the 2 % Bexar tax on 12/31/2026 → a January
   bill carries no Bexar line.
5. **Plans tab counts units, the drawing says accounts** — our judgment (task 6): blueprint
   p35 ruled *units*; a unit carries at most one occupying account, so the two differ only for
   vacant units. Record the choice in the decision log when task 6 builds it.
6. **A version shares its code** — our judgment (task 3, closes `DEF-RAT-9276`): make
   `uq_taxes_tenant_code_ci` hold among rows that are not superseded and not ended, so v1 and
   v2 of *TX-STATE* both read *TX-STATE*.

## 8 · Version and rollback

Round 1 ships **no product code** — this file, the reproduction script, 22 screenshots and
six defect rows — so it carries no version. **Rollback for round 1:** none needed (records
only). Each later round states its version (`allocate.py version --bump change`) and its
rollback before shipping: redeploy the previous build; any migration added by task 3 must
name its down path and what happens to rows written under it.

## 9 · Round 2 API contract

Copied verbatim from the round-2 coordinator brief (2026-10-03). Task 3 implements it; tasks 4 and 5 consume it. **Field names are fixed — never renamed.** A field added later is added HERE in a pushed commit, marked *(added by task N)*.

- `GET /settings/services` — exists; the wizard shows only rows with `enabled: true`.
- `GET /taxes/form-options` (NEW) → `{ boundaries: [{value,label}], due_rules: [{value,label}], bases: [{value,label}], filing_frequencies: [{value,label}] }`. The form renders these lists from the server; it never hard-codes them. `due_rules` values: `20th_next_month` style codes for the six drawn choices (15th / 20th / 25th / last day of next month, 30 days after the quarter ends, January 31 of next year). `boundaries` returns ONLY boundaries that actually bill today (see the PO question below — the answer may add more later without a screen change).
- `GET /settings/authority-accounts`, `POST /settings/authority-accounts`, `PATCH /settings/authority-accounts/{id}` (NEW) → `{id, authority_name, account_number, jurisdiction_id|null, active}`; paged like every list (NFR-3).
- Tax read (list rows and `GET /taxes/{id}`) ADDS: `version` (int, 1-based within the tax's chain), `authority_account` (`{id,label}`|null), `next_filing_due` (ISO date|null — the due date of the latest ended filing period, e.g. monthly + 20th of next month on 2026-10-03 → 2026-10-20), `scheduled_next` (`{rate_display, effective_from}`|null), `premises_reached` (int), `premises_total` (int), `status` (`draft|active|scheduled|ended|superseded`).
- Tax write ADDS `authority_account_id`; `due_date_rule` takes a code from `due_rules`.
- `POST /taxes` with `as_draft: true` saves a draft that does NOT price (DEF-RAT-9275 — the screen must send it).
- `POST /taxes/{id}/new-rate` (NEW) `{rate fields…, effective_from, effective_to?}` → ends the live row the day before `effective_from` and creates the next version in ONE transaction; refuses `effective_from <= ` the live row's start by name.
- `POST /taxes/{id}/corrections` — exists; must stop refusing its own code (DEF-RAT-9276); reason required.
- `PATCH /taxes/{id}` — name and filing fields only on a live tax (rate, reach, dates refused by name, as today).
- `POST /taxes/{id}/retire` (NEW) `{effective_to}` → ends the window; a retired tax never prices after that date.
- `GET /taxes/{id}/plans` → rows add `accounts` (open accounts) beside `units`.
- `GET /taxes/{id}/audit` (NEW) → every change to this tax and its versions: `{at, actor, action, before, after, reason}`, newest first, paged.
- *(added by task 4)* `GET /taxes/form-options` → a `boundaries` row MAY carry `needs_place: true` when choosing it asks for a place name (image 07, *A named place* → *Place name*). Absent means false; the form then offers no place box for that boundary.


### §9 · additions (task 3, 2026-10-03) — no contract field was renamed

* *(added by task 3)* `POST /taxes/{id}/new-rate` answers the new version's row plus
  `ended_version: {id, version, effective_to}` (what v1 became, for the Review step) and
  `issued_bills_unchanged: true`.
* *(added by task 3)* `GET /taxes/{id}/versions` rows add `version` and `amount_display`
  (the figure in any form — `6.50%`, `1.25`); `is_current` now marks the version in force
  TODAY (it marked every non-superseded row).
* *(asked for by the list lane, added by task 3)* `GET /taxes` carries **`over_20_count`**
  beside `count` — the percentage taxes above 20% that are active or scheduled, over the
  WHOLE filtered set, never the page — and accepts **`f.over_20=1`** (the banner's *Show
  them*). `f.status` takes the contract's words; `ended` is served and filtered as `ended`
  (there is no `expired` any more). List rows carry `version`, `premises_reached` and
  `premises_total`.
* *(added by task 3)* `GET /taxes` lists **one row per tax** — the version current today;
  `f.versions=all` lists every row.
* *(PO 2026-10-03, decision log "THREE PO ANSWERS")* `form-options.boundaries` serves ONLY
  what bills today — `everywhere` and `city_limits` — and **no boundary carries
  `needs_place: true`** (the field the New-form lane added is served, `false` on both).
  *Outside city limits* and *a named place* are not built for taxes; *In a state* is not
  served because without a typed state it reaches nobody. `everywhere` is accepted by the
  write as `premises_scope_kind` and stored as no boundary.
* *(PO 2026-10-03 on CR-008, added by task 3)* `PATCH /taxes/{id}` refuses
  `liability_gl_account_id` on a live tax by name (`rating.taxes.liability_edit_in_settings`);
  Settings › Accounting re-points it with `PATCH /taxes/{id}/gl-account`
  `{liability_gl_account_id}`. `POST /taxes` accepts it at creation as before.
* *(for the New form's "Add one" link)* the Authority accounts screen is
  **`/{tenant}/settings/accounting/authorities`** (Settings › Accounting, fourth sub-tab). `due_rules` values are
  `15th_next_month · 20th_next_month · 25th_next_month · last_day_next_month ·
  30_days_after_quarter · jan_31_next_year`; `bases` are the four `kind` values. Labels
  are English fallbacks — screens render catalogue words keyed on `value` (rule 35).
* *(clarification)* `status` values are exactly `draft · active · scheduled · ended ·
  superseded`; a deactivated row reads `ended`. `GET /taxes/{id}/audit` is paged
  (`{count,next,previous,results}`); `actor` is the audit module's own shape
  (`{id,name}` for a person — render the name only, rule 31). New audit actions the FE
  may meet: `tax.new_rate_created`, `tax.ended_for_new_rate`, `tax.retired`,
  `tax.attached_to_plan`, `tax.detached_from_plan`, `tax_authority_account.created`,
  `tax_authority_account.updated`.
* New refusal keys (all eleven catalogues): `rating.taxes.liability_edit_in_settings`, `rating.taxes.new_rate_too_early`
  (`{{starts}}`), `rating.taxes.retire_not_in_force` (`{{date}}`),
  `rating.taxes.retire_scheduled_version` (`{{starts}}`),
  `rating.taxes.unknown_authority_account`, `rating.authorityAccounts.duplicate`.

## 10 · Round 2 · back end (task 3) — what shipped, version 2.472.0

| What | Where | Proof |
|---|---|---|
| The tax CHAIN: `chain_id`, `version_no`, `follows_tax_id`; one code per chain | `rating/0056`–`0058`, `models.Tax` | PG: `ex_taxes_code_one_chain` refuses a second chain's code |
| Billing lookup returns EXACTLY ONE row per tax per date; two taxes of one authority both price | `selectors._authority_taxes`, `_chain_in_force`, `plan_tax_rules` | PG phase-5 table below |
| No two live rows of one tax overlap (deferred exclusion) | `rating/0058` `ex_taxes_chain_no_overlap` | PG: refused with the constraint's name |
| New rate from a date (one transaction, refuses an early start by name) | `services.new_tax_rate`, `POST /taxes/{id}/new-rate` | v1 ends 10/31/2026, v2 from 11/01 |
| Retire ends the window; a deactivated tax prices nothing | `services.retire_tax`, `POST /taxes/{id}/retire`, `tax_in_force` | Dec $1.20, Jan none |
| Attachments follow the chain | `selectors.tax_version_on` | November $3.90 (was $0.00) |
| Per-meter priced | `compute_tax._meters_in_scope`; seam `per_meter_amount` | $1.25 one meter, $2.50 two |
| Corrections of a coded tax keep the code; `correct_tax` stamps v+1 | `services.correct_tax` | 150% → 3%: $1.80, never $90.00 |
| Filing due from six codes | `selectors.next_filing_due`, `GET /taxes/form-options` | monthly + 20th, 10/03/2026 → 10/20/2026 |
| Tax read adds `version`, `authority_account`, `next_filing_due`, `scheduled_next`, `premises_reached`, `premises_total`, contract `status` | `selectors.tax_row`, `tax_read_row` | `test_cr165_tax_versions.py` |
| Plans tab `accounts` beside `units` | `selectors.tax_plans` | vacant unit: units 1, accounts 0 |
| Audit tab: every change to every version, paged | `GET /taxes/{id}/audit`, `seams.tax_audit_queryset` | rename shows only `name` before → after |
| `over_20_count` beside `count`, `f.over_20=1`, `f.status=ended` | `selectors.tax_over_20_count`, `_over_20_q` | 150% counts 1; corrected to 3% counts 0 |
| `as_draft: true` on `POST /taxes` | `api.taxes` (DEF-RAT-9275 server half) | stored Draft, prices nothing |
| Authority accounts: table + RLS + 3 endpoints + Settings screen | `TaxAuthorityAccount`, `/settings/authority-accounts`, `SettingsAuthorityAccounts.tsx` (4th sub-tab of Settings › Accounting) | RLS under `sbh_rls_probe`; DOM test |

**The PostgreSQL proof of "one row per date"** (`tests/test_cr165_tax_versions_pg.py::
test_phase5…`, PostgreSQL 16, real constraints, a $60.00 bill; State sales tax 6.25% given
6.5% from 11/01/2026, County 2% renamed in place, City 150% corrected to 3%):

| Date | Sales rate returned (one row) | Sales tax | Whole bill's tax |
|---|---|---|---|
| 10/15/2026 | 6.25% | $3.75 | $6.75 |
| 10/31/2026 | 6.25% | $3.75 | $6.75 |
| 11/01/2026 | 6.5% | $3.90 | $6.90 |
| 11/15/2026 | 6.5% | $3.90 | $6.90 |

On every date the lookup returned three rows — one per tax — and never the superseded 150%
row; the renamed County tax is the same row as before.

**Red first** (the money cases run on the pre-fix tip `2a842fafc`, same harness): per-meter
`assert [] == ['…']` (no row at all); deactivated `tax_in_force(…) is True`; two taxes of
one authority `AmbiguousAuthorityTax: R7: 2 'percent' taxes … are in force on 2026-10-15`;
new rate / attachment `AttributeError` (no such service); overlap — stored without a word.

**Golden** (`06-backend/tests/golden`): before **25 passed, 1 xfailed**; after
**25 passed, 1 xfailed**. No ❄️ figure moved.

**The PO's two answers (2026-10-03), built:** boundaries = Everywhere and Inside city
limits only, no place box; a live tax's liability account is refused on `PATCH /taxes/{id}`
and changed only through Settings › Accounting (`PATCH /taxes/{id}/gl-account`).

**Not done here, named:** the R1–R7 ruled path's R7 fork (`resolution_switch.
_taxes_from_chain`) carries neither per-unit nor per-meter — R7 is not served
(`SBH_BILLING_RESOLUTION_STEPS` = R3,R4), so no bill is affected; it must carry both before
R7 is switched on. `DEF-RAT-8060` (an `AmbiguousAuthorityTax` fails the RUN, not the
account) stays open — the shape can now arise only from a broken chain, which PostgreSQL
refuses to store. Web walk 1.5's storm fee prices $0.00 where storm water is unmetered —
the rule working (decision log 2026-10-03).

**Rollback:** see `CHANGELOG.md` [2.472.0] — reverse `rating/0058` → `0057` → `0056`.

## 11 · Round 2 task 4 — the New tax or fee form (built from images 04–17)

**Built:** `07-frontend/src/features/rating/taxForm/` — the page `NewTaxWizard.tsx` and one
component per step (`WhatItIsStep`, `HowMuchStep`, `FilingStep`, `ReviewStep`), the right-hand
`TaxSummaryPanel`, the saved state `TaxSavedPanel`, the pure rules `taxFormModel.ts`
(percent ⇄ fraction, the over-20 % warning, the $60.00 example bill, step validation, the
payload) and `taxFormShared.tsx` (the `StepProps` contract: draft, patch, lists, and a set of
LOCKED fields, so round 3's three edit variations mount the same steps with boxes greyed and a
different `steps` array). Two kit pieces were added under B14 rule 36:
`components/CheckDropdown.tsx` (one box, a tick per option, the "all" row first) and
`components/AffixField.tsx` (a box carrying its unit: `%`, `$`, `% / month`). The reads it needs
from round 2's new routes are in `07-frontend/src/api/taxFormEndpoints.ts`.
**Wired:** `App.tsx` mounts `NewTaxWizard` at `TAX_WIZARD_NEW_ROUTE`; the EDIT door
(`TAX_WIZARD_EDIT_PATTERN`) stays on `TaxWizard.tsx` until round 3 rebuilds edit from these
components. `TaxWizard.tsx` is therefore NOT deleted yet: the edit route and
`DefinitionDetailPage.tsx` (`TaxRemittanceFields`, `draftFromTax`, `taxPayload`) still import it.
⚠ **Its new-tax half is now unmounted, and three test files still exercise it**
(`TaxWizard.test.tsx`'s step-1/step-2 blocks, `def_rat_5804_tax_wizard_refusal.dom.test.tsx`,
`cr087TaxScreens.dom.test.tsx`'s review cases): they pass, and they test a screen no clerk can
reach. Round 3 retires them with `TaxWizard.tsx`; until then a red there is not a red on the
New form. `NewTaxWizard.dom.test.tsx` asserts App mounts the new form at the new door.
**Version:** 2.470.0.

**Rate entry and storage.** The API stores a rate (and the allowance and late-interest
percents) as a FRACTION (`0.062500`); the clerk types and reads a PERCENT. The conversion is a
decimal-point shift on the string at the payload boundary, never a float division.
*6.25 typed → `rate: "0.0625"` on the wire → "6.25% of the bill" on Review → $3.75 on the
$60.00 example bill*; *150 typed → "150% is high. Check the rate."* (warns, does not refuse).
Proved RED first against today's `TaxWizard.taxPayload`: `Expected "0.0625", Received "6.25"`.

**Judgment recorded, not asked (law 13): B14 rule 9 and the two dropdowns.** Rule 9 renders a
multi-select as chips + an add control. The PO's ruling of 2026-10-03 (README point 1, P2/P3)
names these two fields as ONE dropdown with ticks and the "all" row first. A later ruling about
two named fields wins for those two fields only; rule 9 still governs every other multi-select.
It is a kit component (`CheckDropdown`), shut until opened, so it is not the "wall of
checkboxes" rule 9 forbids.

**The server's lists in the clerk's language (rule 35).** Boundary, *Charged as*, *Due* and
*Filed* options render the catalogue word keyed on each `value`
(`rating.taxForm.option.*`, all eleven catalogues, for the codes task 3 named); a value the
catalogue does not know shows the server's English `label`, so a boundary added later appears
without a screen change.

(Numbered §11 because task 3 writes its own round-2 record as §10.)

**Contract addition (task 4):** a `boundaries` row of `GET /taxes/form-options` may carry
`needs_place: true` when the boundary needs a place name typed (image 07's *A named place*). A
server that does not send it offers no boundary asking for a place; nothing breaks.

| P | Problem (drawing's words) | Fixed in | How |
|---|---|---|---|
| P1 | Services lists all 11 services | 2.470.0 | only `enabled: true` rows of `GET /settings/services` |
| P2 | Services: a text line plus a separate add box | 2.470.0 | one `CheckDropdown`, *All services* first |
| P3 | Customer classes: same two-part control | 2.470.0 | one `CheckDropdown`, *Every customer class* first |
| P4 | Class list opens over "Named place" | not reproduced | the list opens below its own box; Place name sits beside Boundary above it |
| P5 | Red capital headings beside normal labels | 2.470.0 | section headings in the panel heading style; every label in the kit's label style |
| P6 | "Recorded City limits decide first…" | 2.470.0 | sentence removed (rule 33: rationale is zero words) |
| P7 | "78 of 84 match" and a run-on list | 2.470.0 | count *N of M premises*, a pill, and a table of the sampled premises |
| P8 | Rate typed as a fraction | 2.470.0 | typed as a percent with a `%` box; converted at the payload |
| P9 | No warning for a very high rate | 2.470.0 | over 20 % warns on step 2, on the summary pill and on Review with the $60.00 effect |
| P10 | Basis list opens over the Rate box | 2.470.0 | *Charged as* and *Rate* side by side |
| P11 | Tick boxes jammed together | 2.470.0 | the two ticks spaced on one row |
| P12 | "Only these two can be taxed." | 2.470.0 | removed |
| P13 | Confusing discount example | 2.470.0 | a table of one $60.00 bill, full amount vs after a $5.00 discount |
| P14 | Rounding says "leave blank", but has no blank | 2.470.0 | *Use what your authority requires.*; *Standard (half up)* chosen |
| P15 | Subtitle repeats the heading | 2.470.0 | no subtitle |
| P16 | "Exemptions are on the Exemptions tab." as text | **half** | the sentence is gone; the drawn *Set exemptions ↗* link is NOT built — a new, unsaved tax has no exemptions page to open, and details have no Exemptions tab. Remains open |
| P17 | Review shows the raw "0.625" | 2.470.0 | Review reads *6.25% of the bill* |
| P18 | Dates as 2026-10-01; no example | 2.470.0 | dates in the tenant's format; *On an example bill* section |
| P19 | Code, bill label and filing only on details | 2.470.0 | step 3 *Filing* takes them at creation |
| P20 | Due date and authority account typed as free text | 2.470.0 | both dropdowns; the lists come from `GET /taxes/form-options` and `GET /settings/authority-accounts` and are EMPTY until task 3's routes land |

**Also fixed:** `DEF-RAT-9275` on the front end — *Save draft & exit* sends `as_draft: true`
(and *Save tax* does not send the key). It needs task 3's server half to price nothing; until
then today's server refuses `as_draft` as an unknown key.

**`DEF-RAT-9277` stays OPEN:** P16 (the exemptions link) remains, and P20's two lists are empty
until task 3 lands. Everything else in P1–P20 is fixed or was not reproduced.

**Not wired yet because the back end has not landed (at push):** boundary, *Charged as*, *Due*
and *Filed* lists (`/taxes/form-options`), *Account with the authority* (`/settings/authority-accounts`),
`as_draft`, `authority_account_id`, the place-name boundary (`needs_place`). The reach table
shows Premises · Address · City — the drawn *City limits* and *Class* columns are not in the
`matched-premises` sample, and *See all N* has no destination, so neither is drawn.

**Photographs:** `08-qa/taxes-fees-2026-10-03/after/04…17-*.png`, one per drawing, taken by
`10-scripts/cr165_new_tax_form_walk.mjs` at 1440.

**Rollback:** redeploy the previous build; this change adds no migration and writes no row
shape the old screen cannot read.

## 12 · Round 2 task 5 — the list, built (2.471.0)

Built from images 01–03 (B14 rule 42): `07-frontend/src/features/rating/TaxesFeesTab.tsx`
and the new list-only component file `taxListParts.tsx` (B14 rule 43, both on
`route-b-migrated.txt`). P21–P28 are **FIXED in 2.471.0** and `DEF-RAT-9274` is closed.

* **P21** the explainer is gone from the tab strip and `rating.explainer.taxesFees` is
  retired from all eleven catalogues (G14's list amended in the same commit).
* **P22** name, with the authority's level under it · **P23** the rate is the server's
  display figure alone · **P24** an `Over 20%` pill on any percentage above twenty, and a
  banner `N taxes charge over 20%.` with `Show them` · **P25** `Premises` as `N of M` ·
  **P26** GL code bold, name under · **P27** `Version`, `From`, `To` (`No end`) ·
  **P28** the pencil and the deactivate toggle are gone; the row's one action opens the
  details page.
* **Superseded in the drawing, by PO ruling 2026-10-03** (*"on list view of Tax - ensure
  you ahve filter and not button for filters- follow our toolkkit standard"*): the drawn
  `All · Active · Draft · Ended` buttons are NOT built. The toolbar is the kit's —
  search, `+ Filter ▾` with removable chips, `Download CSV`, `▦` — and the filters are
  Status, Service and Authority (level), each narrowed by the server (NFR-3). Customer
  class is not offered: `GET /taxes` cannot filter by it.
* **Waiting on the back end (task 3):** `version`, `premises_reached`/`premises_total`
  render `—` until served; the `Ended` status option sends `f.status=ended`, the
  contract's word, which today's server calls `expired`.
* **ASKED OF THE BACK END, NOT IN THE ROUND-2 CONTRACT:** the banner's count. It must be
  the server's count over the utility's taxes (the drawing shows the same number over
  All, Active and a search with no match), never the page's. Requested: `over_20_count`
  on the `GET /taxes` reply beside `count`, and `f.over_20=1` to list them. Until both
  exist the banner renders nothing; the per-row pill already marks every such tax on
  the page.
* **Proof:** `taxesFeesList.dom.test.tsx` (13 cases; 12 red on the old screen first),
  `ChargesTaxes.test.tsx` and `DefinitionDetail.test.tsx` restated; screenshots and
  side-by-side pairs in `08-qa/taxes-fees-2026-10-03/after/` from
  `10-scripts/cr165_taxes_fees_list_after_walk.mjs`.
* **Measured, not hidden:** at 1440 the ten columns fit the 1120px table exactly; at the
  1280 laptop minimum the table is 995px in a 960px box and scrolls 35px sideways inside
  its own box (the page does not). A long GL name is cut with an ellipsis and shown whole
  on hover. The drawing's `$` before a flat fee is not drawn: a tax row carries no
  currency, and the screen never assumes one.
* **Rollback:** redeploy 2.471.0's predecessor; no data or migration is involved.

## 13 · Round 3 task 6 — the details page, built (2.474.0)

Built from images 18–23 (B14 rule 42; our kit for spacing and type, rule 44) as components
under `07-frontend/src/features/rating/taxDetail/` (rule 43, all on `route-b-migrated.txt`):
`TaxDetailPage` (the page), `TaxDetailHeader`, `TaxMoreMenu`, `RetireTaxDialog`,
`TaxOverviewTab`, `TaxPlansTab`, `TaxAuditTab` and the pure `taxDetailModel.ts`. The reads and
writes not in `endpoints.ts` are in `07-frontend/src/api/taxDetailEndpoints.ts`.
`DefinitionDetailPage.tsx` now mounts `TaxDetailPage` for the tax kind and keeps its shell for
the charge and discount kinds unchanged; it no longer imports `TaxWizard.tsx` (one fewer
importer for round 3 to retire). `taxDetailTabs.tsx` is deleted; its two tab bodies and the
*Not worked out yet* bar are replaced. 76 catalogue keys added in all eleven languages, 21
orphaned keys retired (`i18n_fanin.py`).

**The edit door, agreed with task 7:** `/plans-rates/taxes-fees/:id/edit?change=info|change|correct`
— header *Edit* opens `change=info`, the over-20% band's *Fix the rate* opens `change=correct`.
`taxDetail.dom.test.tsx` asserts both literal addresses and that `App.tsx` still mounts
`TAX_WIZARD_EDIT_PATTERN`; the walk followed both doors to those addresses.

| P | Problem (drawing's words) | Result | How |
|---|---|---|---|
| P29 | Kicker "TAX · CITY · CITY" repeats itself | **FIXED 2.474.0** | no kicker; the authority is named once in the facts line |
| P30 | Header says little | **FIXED 2.474.0** | name + code · status · version · Over 20% · authority · dates · *Filing due* (active only, `next_filing_due`) · *Next: 6.50% from 01/01/2027* (only with `scheduled_next`) |
| P31 | Long sentence under the title | **FIXED 2.474.0** | facts only, no sentence |
| P32 | "Not worked out yet" band | **FIXED 2.474.0** | gone; *Collected* is a tile reading `—` / *Not counted yet* (see below) |
| P33 | Every section opens with an explanation | **FIXED 2.474.0** | two sections, heading and facts, no sentence |
| P34 | Rate tile shows 150% without a warning | **FIXED 2.474.0** | *62.50% is high. On a $60.00 bill this adds $37.50. Fix the rate* — the New form's own `exampleBill` arithmetic |
| P35 | Four buttons for one job | **FIXED 2.474.0** | ONE Edit + More ▾ (Duplicate, Retire). Retire asks for the last day it charges and calls `POST /taxes/{id}/retire`. **Duplicate is drawn and HELD** — see below |
| P36 | Edits happen in a side panel | not reproduced | Edit is a full-page door |
| P37 | Filing typed in on details only | **FIXED 2.474.0** | *On the bill and filing* is read-only; the 13-box form and *Save filing details* are removed |
| P38 | Plans and Audit tabs empty | not reproduced · **rebuilt** | Plans: Plan · Reached by · **Accounts** · Units · × (attachments only) · totals · *+ Add to a plan* (server search, `POST /plans/{id}/taxes`). Audit: `GET /taxes/{id}/audit`, When · Who · What · Change (before → after) · Reason, names never ids, paged |
| P39 | No rate history | not reproduced · **rebuilt** | versions table at the foot of *Rate and scope* + *See every change in Audit* (PO round 6) |
| P40 | Rate history tab repeats Overview and Audit | not reproduced | tabs are Overview · Plans · Audit |
| P41 | Filing section: 12 fields and long help | **FIXED 2.474.0** | nine facts in a 3 × 3 grid, no help text |
| P42 | Due and authority account typed by hand | **FIXED 2.474.0** | *Due* read from the six codes; *Account with the authority* is `authority_account.label` |
| P43 | Allowance and penalty typed as fractions | **FIXED 2.474.0** | `0.50%`, `1.50% / month` — the server's display strings |

**`DEF-RAT-9272` is CLOSED:** every reproduced row is fixed; P36, P38, P39, P40 were not
reproduced and are built as drawn anyway. **`DEF-RAT-9275` stays OPEN in this lane's hands:**
this walk staged taxes through the API and did not press *Save draft & exit* end to end, so it
is not confirmed here.

**Judgments recorded, not asked (law 13):**
* **Collected has no read.** Nothing on the server totals what one tax collected in a month
  (searched rating, billing and ledger). The tile reads `—` with *Not counted yet*; the
  drawing's `$0.00`/`$3,015.60` are illustrations (rule 37) and a `$0.00` would be a confident
  wrong number. Filed as an open item, not built here.
* **Duplicate is held.** It means *open the New form filled from this tax*, and the New form
  (`taxForm/NewTaxWizard.tsx`, another lane's file) reads no source tax. Pressing it would
  open an empty form under a Duplicate label — law 2's mirror. Drawn disabled with its reason;
  a hold-expiry test fails the day the New form learns a `duplicate` parameter. Filed as
  `DEF-RAT-9299`.
* **Accounts beside Units** (§7 item 5): the drawn column is Accounts; Units stays beside it so
  a plan whose units are all vacant does not read as a plan nobody is on.
* **Audit is `audit_log` now, deliberately.** CR-087's note forbade an audit read on this tab
  when the tab WAS the rate history; PO round 6 split the two — versions on Overview, every
  change with its reason in Audit — so each record is where the drawing puts it.
* The drawn download icon on Audit is **not built**: no export route serves it.

**Not built here, named:** `presentTax` in `definitionDetail.tsx` (shared file) is no longer
reached by any screen; its tests in `DefinitionDetail.test.tsx` and `cr087TaxScreens.dom.test.tsx`
§4 test a presenter no clerk sees. Retire it with `TaxWizard.tsx` in round 3's close.

**Pre-existing red, dated, not caused here:** `usEnglishCatalogue.test.ts` fails on
`rating.taxForm.gap.taxed = "Tick at least one."` — the British *tick* — red since `17e0be69d`
(task 4, 2.470.0). The key is the New form's (not this lane's file). Filed as `DEF-RAT-9300`.

**Proof.** `taxDetail/taxDetail.dom.test.tsx`, 24 cases; run against the OLD page first
(`DefinitionDetailPage.tsx` and `taxDetailTabs.tsx` from `8494f0ef8`): **19 failed, 5 passed**
(the five are pure helpers and a hold that are true either way). On the new page 24/24.
`tsc` clean, `eslint` clean, `src/features/rating` + `src/i18n` + `src/styles`: 1107 passed,
1 failed (the pre-existing British-spelling red above). `vite build --mode wolocal` clean.
Gates through `run()`: G31 PASS; G15 — none of the 804 fresh untranslated values is this
lane's (the 11 values equal to English are G15-allowlisted loanwords: *Status*, *Audit*,
*Plan*, *System*, *Actions*); G18 — none of its missing or dead keys is this lane's.
**Photographs:** `08-qa/taxes-fees-2026-10-03/after/18…23-*.png` and each `-side-by-side.png`,
from `10-scripts/cr165_tax_detail_walk.mjs` at 1440 on PostgreSQL 16 (`seed_demo`), each opened
and checked; the walk's printed output is `after/detail-walk-output.txt`.

**Version:** 2.474.0. **Rollback:** redeploy 2.472.0; no migration and no new data shape.
## 14 · Round 3 task 7 — Edit, the same form with a variation (built from images 24–33, 2.476.0)

PO, verbatim: *"We dont use side panel for edit - you will need to send it back to Edit form -
You can use add form with variation"*. **Built:** `07-frontend/src/features/rating/taxForm/EditTaxForm.tsx`
at `/{tenant}/plans-rates/taxes-fees/{id}/edit?change=info|change|correct` (the address the details
page links to; `taxEditPath(id, mode)` in `taxEditModel.ts` spells it once). *What to change* sits on
top (`EditChoiceCards`, a radio group of three cards); the chosen card picks a step list
(`EDIT_INFO_STEPS` · `EDIT_CHANGE_STEPS` · `EDIT_CORRECT_STEPS`, beside `NEW_TAX_STEPS`) and a set of
locked fields, and the New form's own step components (`FilingStep`, `HowMuchStep`) and summary
render over the tax read back into the New form's draft (`taxFormDraftFromRow`). New pieces:
`EditNameStep` (name + *Rate and reach* read and locked), `EditReviewStep` (*What changes* before →
after, *On a $60.00 bill* before → after, *How it is saved*), `EditSavedPanel` (*Back to tax*).
The New form's reads moved into one hook both forms use (`useTaxFormLists.tsx`).

| Choice | Steps | Saves with | Locked |
|---|---|---|---|
| Name and filing | Name · Filing · Review | `PATCH /taxes/{id}` — the CHANGED name/filing keys only, never `liability_gl_account_id` | rate, reach, dates, liability account |
| New rate from a date | New rate · Review | `POST /taxes/{id}/new-rate` — form, figure, `effective_from`, `effective_to` | reach, what is taxed, discounts, rounding (see judgment 1) |
| Fix a mistake | Fix the rate · Review | `POST /taxes/{id}/corrections` — the changed rate fields + `reason`; never the window | dates (read, *Same dates as today.*) |

| P | Problem | Fixed in | How |
|---|---|---|---|
| P44 | A side panel for edits | not reproduced; kept | Edit is the full-page New form with a variation; no dialog anywhere |
| P45 | One form for every kind of edit | 2.476.0 | three cards, three flows, each its own steps and save |
| P46 | Rate and reach editable on a live tax | 2.476.0 | *Name and filing* reads them locked with *Change with a new rate.* |
| P47 | New rate: old row's end typed by hand | 2.476.0 | *New rate starts* only; *Today's rate ends 10/31/2026.*; a start not after 09/01/2026 is refused on the box (*Must be after 09/01/2026.*) before the server's own `new_rate_too_early` |
| P48 | Fix a mistake with no reason | not reproduced; kept | *Why it was wrong* is required (*Enter the reason.*) and the server's 10-character rule still applies |
| P49 | Saving gives no picture of the rows | 2.476.0 | Review: before → after per field, the $60.00 bill ($90.00 → $3.75), the versions table |
| P50 | Issued bills silently keep the wrong rate | not reproduced; kept and said where it is decided | *Issued bills keep 150%. Correct those bills separately.* on Fix a mistake; *Bills before 11/01/2026 keep 150%.* on a new rate |

**`DEF-RAT-9273` is closed** — every row P44–P50 is fixed or was not reproduced and is kept.

**PostgreSQL proof** — the three saves made THROUGH THE SCREEN (`10-scripts/cr165_edit_tax_walk.mjs`)
against the real API on PostgreSQL 16 (`seed_demo`, Dana), three copies of the drawn 150 % tax,
then read straight from `taxes`:

| Save | Row(s) in `taxes` |
|---|---|
| Name and filing (reminder → `tax@ottumwawater.example`) | the SAME row, `version_no` 1, reminder changed in place, no second row |
| New rate 6.25 % from 11/01/2026 | v1 `1.500000` 2026-09-01 → **2026-10-31**; v2 `0.062500` **2026-11-01** → 2027-11-10, `follows_tax_id` → v1, same code |
| Fix a mistake 150 % → 6.25 % | v1 `1.500000` kept, `superseded_by_tax_id` → v2; v2 `0.062500` same window 2026-09-01 → 2027-11-10, `corrects_tax_id` → v1, reason *Rate typed as 150%.* |

**Red first:** `EditTaxForm.dom.test.tsx` run against `TaxWizard` mounted at the same route —
**13 of 14 red** (the 14th is the pure path helper); against `EditTaxForm`, 14/14 green.
`taxEditModel.test.ts` 15 cases.

**Retired:** `TaxWizard.tsx`, `TaxWizard.test.tsx`, `def_rat_5804_tax_wizard_refusal.dom.test.tsx`,
and `cr087TaxScreens.dom.test.tsx`'s three wizard sections (its KPI-strip section stays).
`ChargesTaxes.test.tsx`'s three cases that read `TaxWizard` are restated on the mounted form
(one figure per computation form; BR-TEN-037 held by Settings › Reference data; the liability
account locked on every edit variation and absent from the PATCH).
`DefinitionDetailPage.tsx` no longer imports the wizard (task 6 removed its filing form in
2.474.0), so nothing is moved and nothing is left behind: `grep -rn TaxWizard 07-frontend/src`
finds only comments recording history.

**Judgments (decision log 2026-10-03, *"EDIT A TAX IS THE NEW FORM WITH A VARIATION"*):** (1) New
rate locks what is taxed, discounts and rounding — the server's `NEW_RATE_FIELDS` would refuse
them; (2) the liability account is a locked box on Filing (image 25 draws a dropdown; the PO's
CR-008 ruling of the same day wins); (3) switching cards restarts that flow from the saved tax;
(4) Save is held until something changed. Also fixed in passing: `rating.taxForm.gap.taxed` read
the British *"Tick at least one."* (red in `usEnglishCatalogue.test.ts` since `17e0be69d`, filed by task 6 as `DEF-RAT-9300`) →
*"Check at least one."* — `DEF-RAT-9300` is closed; the unused `Bold` in `taxFormShared.tsx` (G40) is removed.

**Photographs:** `08-qa/taxes-fees-2026-10-03/after/24…33-*.png` (+ `30b`, `33b`, the two saved
states), one per drawing, at 1440 — each looked at beside its drawing. Differences kept on purpose:
the liability box is locked (ruling); *What is taxed* / discounts / rounding are greyed on New rate
(judgment 1); the kit draws an error under the help line rather than in its place; a changed start
date adds a *Starts* row to *What changes*.

**Version:** 2.476.0. **Rollback:** redeploy 2.472.0 — front end only, no migration; every save
went through 2.472.0's endpoints.

## 15 · Round 3 task 8 — the eleven languages on the four tax screens (2.477.1 → 2.477.3)

**Scope.** Every key the four screen lanes added or changed (`17e0be69d` New, `c77b9eb5e` list,
`347e81c89` details, `b71588e74` Edit) plus the back end's refusals and Settings › Accounting keys
(`17c2e4ea4`): **326 keys × 10 catalogues**. The screenshots then showed **41 older keys** that
these screens also render (the Plans & Rates tab bar and roll-up line, the list's + button and
columns, customer classes and boundary kinds, the details page's Edit/Overview/Plans, the form's
Continue). Those were reviewed and fixed too, because each one put English or a wrong word on these
four screens. Every change went through `10-scripts/i18n_fanin.py`; no catalogue was round-tripped.
Defect `DEF-RAT-9302`.

**The rule applied (B14 rule 35).** One word per idea per catalogue, taken from the word that
catalogue already uses most. Premises: es *inmueble*, fr *site*, id *properti*, ja 物件, ko 건물.
Version: de *Fassung*. Rate: es *tasa*. Bill: pt *fatura*. Authority: pt *órgão*. Plan: fr *forfait*.
Every "see it in Audit" sentence names the tab the way the tab itself reads: de *Prüfspur*, fr *Suivi*,
it *Storico*, id *Jejak audit*, ja 履歴, ko 이력. The back link matches its tab (de, es-MX, it, ja).
Literal phrases were rewritten (*in place*, *half to even*, *no end*, *Allowance* written as
*discount* in fr, hi and id). Rule 34's *Recorded* / *In the books* pair is not used in the ledger
sense on these screens. Where *recorded* appears (*No changes recorded*, *already recorded*), each
catalogue uses its rule-34 word.

| Language | Keys reviewed | Changed (in scope) | Changed (older, on these screens) | Could not resolve |
|---|---|---|---|---|
| de | 326 + 41 | 26 | 1 | — |
| es | 326 + 41 | 47 | 2 | List *Hasta* column wraps *Sin fecha final* onto two lines at 1440 (wraps, not cut off) |
| es-MX | 326 + 41 | 20 | 18 | — |
| fr-FR | 326 + 41 | 56 | 10 | Shell nav *Lit* for Reads (shell, not this CR) |
| hi | 326 + 41 | 17 | 17 | — |
| id-ID | 326 + 41 | 28 | 27 | — |
| it-IT | 326 + 41 | 17 | 11 | Shell nav *Legge* for Reads (shell, not this CR) |
| ja-JP | 326 + 41 | 26 | 27 | — |
| ko-KR | 326 + 41 | 23 | 28 | — |
| pt-BR | 326 + 41 | 23 | 6 | Shell nav *Lê* for Reads (shell, not this CR) |

**Left as they are, on purpose.**
- English *"Every premises"* (`rating.taxForm.reach.every`). It is awkward English, but the same
  phrase is the product's wording on other screens and in the back end. Changing one screen would
  make two wordings, so it is reported here rather than changed.
- The authority names (*Special district*), the service badges (*Electric*, *Water*), the tax names
  and the *Local* authority under the title are tenant data, not catalogue text.
- The browser's date-field placeholder `mm/dd/yyyy` belongs to Chromium, not the catalogue.
- The shell sidebar's *Work* is English in every catalogue, and *Lit* / *Legge* / *Lê* are literal
  translations of "Reads". Both are shell copy, outside these four screens.
- Orphans left behind by the old wizard: `rating.taxWiz.create`, `.kicker`, `.kickerEdit` and
  `rating.taxes.form.*` have no static caller, and two of them are machine-translated howlers
  (fr *Économisez des taxes*, it *Risparmia tasse*). They are not retired here, because a key built
  dynamically would then print as a raw key. Retiring them needs a check of who calls them.

**Checks.**
- Placeholders (`{{…}}`) are identical to English in all 326 × 10 values, and every `_one` has its
  `_other`.
- G15 scoped to these keys: **0 fresh** untranslated values. The two found (de *Version*,
  fr *v{{v}} · correction*) are fixed, and the identical values that remain are on G15's loanword
  list (de *Status*/*System*/*Name*, es *Plan*, fr *Audit*/*Actions*/*Code*/*Version*, id *Status*/*Audit*).
- G15 overall: red before and after (811 → 810 fresh, all outside this scope; 1,653 stale baseline
  lines predate this lane).
- G33: none of these keys is among its 10 failures.
- `usEnglishCatalogue.test.ts` green.
- `vitest src/i18n src/styles`: 98 passed. `src/features/rating` + `src/components`: 1,877 passed,
  1 red. That red is `ConfirmDialogTier.dom.test.tsx`'s census, red since `8b7aee258` (2.467.19,
  BulkRunPage), not this lane.

**Photographs.** `08-qa/taxes-fees-2026-10-03/i18n/{list,new,detail,edit}-<lang>.png`, 44 at 1440
on a scratch PostgreSQL 16 (`seed_demo`, Dana). Each one was opened and looked at. No English is
left in any catalogue string, nothing is cut off and nothing overflows; the page never scrolls
sideways.

**Version:** 2.477.1 (first pass, `1488fe073`), 2.477.2 (screenshot pass, `90cb28552`), 2.477.3
(this record and pt *Classes*). **Rollback:** redeploy 2.477.0. These are catalogue text changes
only: no migration and no data.

## 16 · Round 4 task 9 — the full web walk, and what it fixed (2.477.0, 2.479.0)

PO, verbatim: *"I want to create Tax code for all juridictions, all Utility Services {single or
all or multple} I want to create tax for Customer class - take menaingful pratcice scenarios;
then save these codes. then view these code see all ifnrmation saved correctly and displayed
correctely then edit those tax codes and see updates are correctly saved - inlcuding version
hisorty and it return only 1 record when billing ask it; the changes reflects in plans audit"*.

Walked on PostgreSQL 16 through the built screens at 1440 (`10-scripts/cr165_taxwalk.mjs`), with
the world, the billing lookup and two REAL bill runs from `10-scripts/cr165_taxwalk_world.py`.
**79 checks, 79 pass** after the fixes below. The record, with every check, every screenshot and
the bill lines as stored: `08-qa/taxes-fees-2026-10-03/walk-report.md`.

**The figures the PO asked for, as billed:** October run (10/15/2026, before any edit) — State
sales tax **$3.75** on the $60.00 bill, City **$90.00** at the typed 150%. November run
(11/15/2026, after the edits) — State **$3.90** (v2, 6.5% from 11/01/2026), County **$1.20** on the
same, renamed row, City **$1.80** (the 3% correction). October still reads $3.75 and $90.00. The
billing lookup returned **exactly one row per tax** on 10/15, 10/31, 11/01 and 11/15/2026, never
the superseded 150% row and never the draft.

| Defect | Found at | Result |
|---|---|---|
| `DEF-RAT-9301` New rate locks what is taxed, discounts, rounding | 4.2 (known) | **fixed 2.477.0** — `NEW_RATE_FIELDS` takes the four keys; the form sends them only when changed |
| `DEF-RAT-9275` Save draft & exit | 1.8 (known) | **confirmed and closed** — stored Draft, never priced |
| `DEF-RAT-9299` Duplicate held | 3 (known) | **fixed 2.477.0** — `?duplicate=<id>`, code cleared |
| `DEF-RAT-9305` a draft can never be finished | 1.8 | **fixed 2.479.0** — a draft's Edit opens the New form filled (`?draft=<id>`); Save tax PATCHes and activates |
| `DEF-RAT-9306` panel says $0.00 for per-unit / per-meter | 1.5, 1.6 | **fixed 2.479.0** — a dash |
| `DEF-RAT-9304` Plans 9 over 7 plans | 6.2 | **fixed 2.479.0** — `used_by_plans` counts plans |
| `DEF-RAT-9307` Bill label never reaches the bill | 5.4 | **NOT fixed by the walk — put to the PO**, who ruled *"Okay"*; **fixed 2.481.2** in task 10 (§17) |

**Golden** (`06-backend/tests/golden`): before **25 passed, 1 xfailed**, after **25 passed, 1 xfailed**.
No ❄️ figure, signed rule or RLS file was touched.

**Version:** 2.477.0 (a, c), 2.479.0 (the walk's own finds). **Rollback:** redeploy 2.476.0 /
2.478.0 respectively; no migration in either.

## 17 · Round 4 task 10 — the bill label, and the close (2.481.2)

### The last fix: a tax line reads its Bill label (`DEF-RAT-9307`)

PO, verbatim, to *"yes, print the bill label"*: *"Okay"* (decision log 2026-10-03, *"A TAX PRINTS
ITS BILL LABEL ON THE BILL"*). Built in the 🔒 money-path files under HUMAN-REVIEW-PENDING with a
review-ledger row: `rating/selectors.py` (`plan_tax_rules` and `_attached_row` serve `bill_label`),
`billing/gather.py` (`_taxes_for` carries it), the seam `billing/rating_seam.TaxRule` and the engine's
`pricing/contracts.TaxRuleSpec` (one field each), `pricing/stages/normalize.py`, and
`pricing/stages/compute_tax._printed_description` (the label, else `"Tax " + name`, as every bill has
read). The R1–R7 switch (`billing/resolution_switch._taxes_from_chain`) takes the label from the live
rule, as it takes `discount_treatment`. **Words only — no amount can move**: the amount is computed
from the rate fields before and apart from the description, and the authority travels as `tax_id`.

| | Before | After |
|---|---|---|
| Test, red first (`tests/test_def_rat_9307_tax_bill_label.py`) | 3 failed: `'Tax County utility tax' != 'County tax'`, `'Tax Walkland County' != 'County tax'`, `TaxRule` had no `bill_label` | 5 passed |
| Golden `06-backend/tests/golden` | 25 passed, 1 xfailed | 25 passed, 1 xfailed |
| `10-scripts/03-golden-verify.py` | 33 PASS | 33 PASS |
| A real bill, PostgreSQL 16 (`BL-2611-000002`, 10/16–11/15/2026, $60.00) | *(walk, 2.479.0)* `Tax County utility tax 1.20` | `County tax 1.20`, total **$61.20** |

**Screenshot:** `08-qa/taxes-fees-2026-10-03/task10/bill-charges-county-tax.png` — Billing › the bill ›
Charges: *Taxes & fees* row **County tax · $1.20**, and the Tax box *Wapello County · County tax ·
$1.20*. Opened and looked at; not blank. Already-issued bills keep their wording (hard rule 4).
**No front-end change:** nothing in `07-frontend` composes `"Tax "` — the screens and the bill
document print the stored line description.

**Related suites:** 342 passed and 7 failed across the 25 tax, gather and switch files. The 7
(`test_br_bil_870_resolution_switch` ×2, `test_def_273…class_vocabulary…`, `test_step3_shadow_panel`
×4) **fail identically on the pre-fix tip `e43441c49`** (re-run there on an untouched copy), so they
predate this task and are not caused by it; they are reported, not fixed here.

### The close (change process step 8)

**The ten tasks, each with its build:**

| Task | What | Version / commit |
|---|---|---|
| 1 | the 33 images | records only, `375f1e499` |
| 2 | rulings + 50 problems reproduced, defects filed | records only (round 1) |
| 3 | back end — chain, one row per date, new rate, retire, per-meter, authority accounts | **2.472.0** |
| 4 | the New tax or fee form | **2.470.0** |
| 5 | the list | **2.471.0** |
| 6 | the details page | **2.474.0** |
| 7 | Edit — the New form with a variation | **2.476.0** |
| 8 | eleven languages | **2.477.1 → 2.477.3** |
| 9 | the full web walk (79 of 79) and its fixes | **2.477.0**, **2.479.0** |
| 10 | the bill label, and this close | **2.481.2** |

**Every defect this CR filed:**

| Defect | State |
|---|---|
| `DEF-RAT-9272` details · `9273` edit · `9274` list | fixed (2.474.0 · 2.476.0 · 2.471.0) |
| `DEF-RAT-9275` save draft · `9276` correcting a coded tax | fixed (2.470.0/2.472.0 · 2.472.0) |
| `DEF-RAT-9278`–`9283` per-meter, deactivated tax, two taxes of one authority, overlap, attachments, new rate | fixed 2.472.0 |
| `DEF-RAT-9298` sample data plants no rating records | fixed (`6b4655fc9`) |
| `DEF-RAT-9299`, `9301` duplicate, new rate locked fields | fixed 2.477.0 |
| `DEF-RAT-9300` British *Tick* · `9302` ten catalogues | fixed (`b71588e74` · 2.477.2) |
| `DEF-RAT-9304`, `9305`, `9306` | fixed 2.479.0 |
| `DEF-RAT-9307` bill label | **fixed 2.481.2** (this task) |
| `DEF-RAT-9277` New tax form P1–P20 | **CARRIED OPEN, with its reason.** Every row is fixed or not reproduced except **P16**, the drawn *Set exemptions ↗* link: exemption is ACCOUNT-level (`BR-RAT-006`) and no tax has an Exemptions page, so the link would be a live control over no screen (hard-won law 2's mirror). It does not block the close: the CR's requirement is the form, and the form saves every tax the walk made. |
| `DEF-BIL-9317` (filed by this task) | **open, low, not blocking** — a 2 % tax line's RATE column on the Charges tab reads **$0.02**; seen in the screenshot above; display only, the Billing screen, not a sentence of this CR |

**The 33-image comparison.** All 33 drawings have an after-photograph at 1440
(`08-qa/taxes-fees-2026-10-03/after/01…33`, plus `30b`, `33b`), and each round compared its own
images problem by problem: 01–03 in §12, 04–17 in §11, 18–23 in §13 (with side-by-side pairs for
01–03 and 18–23), 24–33 in §14. Not repeated in this task; nothing drawn changed after those rounds
except what §16 fixed and walked.

**Surface debt:** this CR added and removed no story, so no `surface_debt.txt` line moves; the
`rating` line there is about `US-RAT-012..015` (the pricing engine) and was checked, not changed.

**Carried, not blocking — each written so a later lane can pick it up:**
1. **P16 exemptions link** — `DEF-RAT-9277`, above.
2. **The R7 fork carries neither per-unit nor per-meter** (§10) — R7 is not served
   (`SBH_BILLING_RESOLUTION_STEPS` = R3,R4), so no bill is affected; it must carry both before R7
   is switched on. It now carries the bill label.
3. **`DEF-RAT-8060`** (an `AmbiguousAuthorityTax` fails the RUN, not the account) — open, predates
   this CR; the shape can now arise only from a broken chain, which PostgreSQL refuses to store.
4. **Collected has no read** (§13) — the details tile reads `—`; nothing totals what one tax
   collected in a month.
5. **An attachment folded into an authority binding has no ×** (walk, *Noticed*) — our judgment,
   decision log 2026-10-03: deliberate in `selectors.tax_plans`, no bill moves; not a defect.
6. **Every demo plan binds all seven authorities**, so a new tax reaches most demo plans the day it
   is saved — our judgment: a property of the demo data and true to `BR-RAT-113`, not the product.
7. **Orphan catalogue keys of the retired wizard** — `rating.taxWiz.create`, `.kicker`,
   `.kickerEdit` have no static or dynamic caller now that `TaxWizard.tsx` is deleted (checked
   2026-10-03); `rating.taxes.form.*` is already parked dead under `DEF-2602`. Not retired here
   because eleven catalogues are being edited by the discounts lane this hour; retire through
   `10-scripts/i18n_fanin.py` (its `retire` list) with the G15 baseline lines in one commit.
8. **The 7 pre-existing reds** above (switch, class vocabulary, shadow panel).
9. **`DEF-BIL-9317`**, above.

**Harden (step 9):** the escape for `DEF-RAT-9307` was *"no test reads a bill line for it"*. The new
test reads the line through the bill run's own projection (`gather._taxes_for`), not a hand-built
seam rule, so the next field the form stores and the seam drops goes red the same way.

**Rollback:** redeploy **2.481.1**. No migration and no data shape change; bills issued under
2.481.2 keep the label wording they were issued with (an issued line is never reworded), and
bills issued after a rollback print `"Tax " + name` again. Every earlier round's rollback stands
as stated in its own section.

**`CR-165-BRC10` is CLOSED** at 2.481.2, with `DEF-RAT-9277` (P16) and `DEF-BIL-9317` open
against this surface.
