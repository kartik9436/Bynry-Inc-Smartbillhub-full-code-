# CR-094-BRC01 · step 1 lane 1 — the Accounts register, read against its blueprint

**Screen 01 · `S17` · `/:tenant/accounts` · `AccountsListPage.tsx`, and the seven
sibling tabs that live on it.** Blueprint pages **3–5** (the screen), **150–152**
(remedy `R2`), **153** (finding `ACC-S11`) and **207–209** (§12, the specification
register), all read as **rendered images**; prose quoted from the text layer is
marked where it is used.

**Measured 2026-09-12 against the running product** — Django on `127.0.0.1:8570`,
the built SPA on `127.0.0.1:8571`, the seeded `brazosbend` tenant (**73 accounts**),
signed in as Dana Whitfield (System Admin), Chromium at 1440×1000.

⚠ **THE BLUEPRINT COULD NOT DO THAT, AND SAYS SO.** Screen 01's own *Walked* row
reads: ***"Not walked. The app could not be booted here (no docker daemon, no
systemd, no PostgreSQL, no node_modules). Every statement in this entry is read
from source."*** So every as-built claim it makes about this screen is a **reading**,
and `CR-092` spent two passes learning that a description is not a measurement.
**This lane booted the stack and walked all eight tabs.** Where a statement below is
a measurement it says what was measured and how; where it is a reading of source it
says that instead. The instrument is `10-scripts/cr094_lane1_register_measure.py`,
which writes nothing and can be re-run before and after step 2.

**Source of truth:** `05-prototype/02 Accounts Menu Blueprint.pdf`, pinned at commit
`033981d4f`, `sha256 c8d596bb505f5020ce4b9474…` (verified on fetch).

---

## 1 · THE DRAWING, INVENTORIED

Skill §2.1 order. **Every string below is copied character for character off a
rendered page** at scale 4–16. Nothing here is from the text layer, which renders
every digit as `&`.

### 1.1 The screen's own header block (p3)

| element | exact text |
|---|---|
| screen number and name | `01  Accounts list` |
| state chip | `EXISTS BEHIND` |
| specification chip | `ACC-01 · ACC-02` ⚠ see §5.4 — §12 mints `ACC-S1`…, not `ACC-01`… |
| route line | `/:tenant/accounts` · `?tab= × 8` · `S17` · `AccountsListPage.tsx` |
| the question | *"Someone is on the phone and all they've given me is a name, or a number off a bill, or the street. Find them — and tell me what they owe before I have to ask."* |

**`S17` is the canonical A1 id**, read off this screen's own header page as the
screen index instructs.

### 1.2 The frame (chrome)

| # | element | exact text |
|---|---|---|
| 1 | address bar | `/brazosbend/accounts?tab=accounts&sort=name&dir=asc&page=1` |
| 2 | product mark · menu | `SMARTBillHub` · `☰` |
| 3 | top-bar breadcrumb | `Accounts` |
| 4 | global search | `Search accounts, premises, meters…` |
| 5 | top-bar icons | flag · `?` |
| 6 | tenant badge | `BB  Brazos Bend Utilities` |
| 7 | sidebar, in order | `Dashboard` · `Plans & Rates` · `Premises` · `Assets` · `Accounts` · `Reads` · `Billing` · `Payments` · `Work` · `Finance` · `Runbooks` · `Reports` · `Settings` |
| 8 | version | `v2.234.15` |
| 9 | user block | `SO  Sam Ortiz` / `Billing Clerk` |

### 1.3 Page head and actions (p3)

* **Title** `Accounts`. **No kicker and no subtitle** — see §5.
* **Actions, left to right:** `Move-out` (secondary) · `Move-in` (secondary) ·
  `+ New account` (**primary**).
* **`+ New account` is the only primary**, which is `BR-SHL-044` honoured rather
  than fought — the blueprint's own words on p4: *"One slot that relabels per tab"*.

### 1.4 Tabs, in order (p3)

`Accounts` **⁷²** · `Requests` · `New connects` · `Move-ins` · `Move-outs` ·
`Transfers` · `Disconnects` · `Imports`

**Eight, and `Accounts` is the default and the only one carrying a count.** The
blueprint's p4 *Tabs* row says so in as many words: *"**Eight**, all in the URL as
`?tab=` and all with a real body — none renders a note about itself."*

### 1.5 The KPI strip — five tiles (p4)

| # | label | value | detail line |
|---|---|---|---|
| 1 | `ACCOUNTS` | `72` | `live and closed` |
| 2 | `OUTSTANDING` `POSTING DATE` | `$24,992.65` | `across all ageing` |
| 3 | `PAST-DUE 60+` | `Not counted yet` | `accounts owing money 60 days or more overdue` |
| 4 | `CLOSED THIS YEAR` | `Not counted yet` | *(no detail line)* |
| 5 | `PENDING ACTIVATION` | `1` | `no bill can be raised yet` |

`POSTING DATE` is set in the muted tier beside `OUTSTANDING` and wraps to a second
line. It is **not a second label**: it is `BR-REP-001`'s required date-basis tag on
a money KPI, which is why it is there and why it may not be deleted.

### 1.6 The table toolbar (p4)

`[ Account #, customer #, name, address, or meter #… ]` · `All` · `+ Filter ▾` ·
——— · `[▦]` (icon only, no label) · ——— · `Columns ▾` · `⇩ Export`

### 1.7 The table (p4)

| # | column | sort glyph drawn | alignment |
|---|---|---|---|
| 1 | `ACCOUNT` | `⇅` | left |
| 2 | `NAME` | `⇅` | left |
| 3 | `PREMISE` | — | left |
| 4 | `SERVICES` | — | centred chips |
| 5 | `BALANCE` | `⇅` | right-ish, tabular |
| 6 | `LAST BILL` | — | left |
| 7 | `STATUS` | `⇅` | left |
| 8 | `AGEING` | — | left |

**No select column, no row-action cell.** Three drawn rows:

| ACCOUNT | NAME | PREMISE | SERVICES | BALANCE | LAST BILL | STATUS | AGEING |
|---|---|---|---|---|---|---|---|
| `AC-2026-00001` | `Ana Alvarez` | `101 Silver Creek Rd · Unit 1` | `E` `W` | `$158.10` | `08/02/2026` | `Active` | `—` |
| `A-11812` | `Bramble Bakery` | `142 Bakers Row · Suite 1` | `E` `W` | `$2,410.00` | `Awaits billing` | `Active` | `61–90 days past` |
| `A-11721` | `Calloway, Brett` | `9 Tanner Street · Unit 1` | `E` `W` | `$1,204.50` | `Awaits billing` | `Active` | `Over 90 days past` |

⚠ **The account number is the LINK to screen 02** and is the only link in a row.
⚠ **The drawn rows are Alvarez, Bramble, Calloway — the alphabet.** That ordering is
what `BR-CUS-1046` supersedes; the drawing is an *as-built* frame, not a target.
⚠ **Every figure in this table is an ILLUSTRATION (B14 rule 37)** — `72`,
`$24,992.65`, `$158.10` and the dates say *a figure goes here and looks like this*
and nothing about any real row.

### 1.8 The footer (p4)

`1–50 of 72` · `Rows per page` `[50 ▾]` · `‹` · `›`

### 1.9 The states, verbatim from the blueprint's own *States* row (p4–5)

* **Loading** — *"skeleton rows at table height; the KPI tiles render –, not 0."*
* **Empty** — *"the shared empty state with `+ New account` as its CTA."*
* **Failed** — *"a permission failure renders `PermissionDenied` with a way back to
  the dashboard; the surface is not drawn at all."*
* **Nothing can be owed yet** — *"a pending-activation row reads* Awaiting *in
  Balance, never `$0.00` — the domain state this screen exists to get right."*

### 1.10 The words it chose and the words it refused (p5)

> **Chosen: `Awaiting`** over a dash or a zero, everywhere a figure is absent
> rather than nil. **Refused: `Current`** as a fallback for a null ageing band —
> that would be a claim about a customer's money. **Refused: a `Plan` column**,
> because the snapshot has no DDL and an always-empty column is a worse answer than
> none.

### 1.11 The seven sibling tabs, as the blueprint describes them (p4, prose)

*"accounts → this table · requests → `ServiceRequestsListPage urlState={false}` ·
new-connects → `ParkedDraftsPanel` + `NewConnectsTab` · move-ins / move-outs /
transfers / disconnects → the same pairing · imports → `AccountImportsTab`. An
unknown `?tab=` falls back to accounts rather than erroring."*

**The primary action per tab, as drawn (p4):** `"+ New account"` · `"+ New request"`
· `"+ New connect"` · `"Move-in"` · `"Move-out"` · `"+ New transfer"` ·
**`"+ New disconnect"`** · `"↑ New import"`.

---

## 2 · AS BUILT VERSUS DRAWN

`=` matches · `≠` differs · `∅` drawn and not built · `+` built and not drawn.

### 2.1 Head, tabs, toolbar, table, footer

| element | drawn | as built (measured) | |
|---|---|---|---|
| title | `Accounts` | `Accounts`, `<h1 class="text-h2">`, computed **32px** | `=` — B14 rule 40, ratified this morning |
| kicker / subtitle | none | none | `=` |
| actions | `Move-out` · `Move-in` · `+ New account` | identical, in that order, `+ New account` carries `data-variant="primary"` | `=` |
| tabs | eight, `Accounts ⁷²` default | eight `role="tab"` buttons, `Accounts 73` selected | `=` (72→73: an illustration, rule 37) |
| KPI tiles | five, labels as §1.5 | five, labels identical, values `73` / `$24,992.65` / `Not counted yet` / `Not counted yet` / `1` | `=` |
| search | `Account #, customer #, name, address, or meter #…` | identical (`customers.accounts.searchPlaceholder`) | `=` |
| `All` | outlined | filled dark (active segment) | `=` — styling, an illustration |
| `+ Filter ▾` | present | present, a `<details>` | `=` |
| `[▦]` icon-only | present, mid-toolbar | present, at the toolbar's right edge, `aria-label="Show or hide columns"`, `title="Columns · show / hide · ↑↓ reorder"` | `=` in function, position differs |
| `Columns ▾` (labelled) | present | **absent** | `∅` — see §3.7, and B14 rule 12 settles it |
| `⇩ Export` | present | **absent** — `DataTable`'s `downloadSlot` is not passed | `∅` — a registered refusal, §3.8 |
| columns | 8, in the drawn order | 8, in the drawn order | `=` |
| sortable columns | `⇅` on `ACCOUNT` `NAME` `BALANCE` `STATUS` | those four are `<button class="table-sort">`; **no glyph is drawn on any of them until it is the active sort** | `≠` — **`DEF-SHL-5062`** |
| row link | account number → screen 02 | `<a>` on the account number, and nothing else in the row | `=` |
| row actions | none | none | `=` |
| footer | `1–50 of 72 · Rows per page [50 ▾] · ‹ ›` | `1–50 of 73 · Rows per page 50/100/200/500/1000 · ‹ ›` | `=` to the drawing, `≠` to **B14 rule 16** — see §3.9 |

### 2.2 What each tab opens on — the measurement this lane exists for

Server ordering read at source; the sentence in the third column read **in a
browser**, under the pager of the running tab.

| tab | server ordering | the sentence the tab prints | newest first? |
|---|---|---|---|
| `accounts` | `list(qs.order_by("id"))` then `rows.sort()` in Python; default `ACCOUNT_DEFAULT_SORT = "name"` | *(none)* | **no** — name A→Z |
| `requests` | `.order_by("received_at", "id")` | *"Sorted by age, oldest first — the oldest thing waiting is the thing to look at."* | **no** — oldest first |
| `new-connects` | `.order_by(F("target_activation").asc(nulls_last=True), "id")` | *"Sorted by target date, soonest first — the next thing due is at the top."* | **no** |
| `move-ins` | `.order_by("opened_at", "account_no")` | *"Sorted by move-in date, soonest first. A move-in with no start date is listed first — it cannot open until one is set."* | **no** |
| `move-outs` | `.order_by("closed_at", "account_no")` | *"Sorted by move-out date, soonest first."* | **no** |
| `transfers` | `.order_by("-created_at", "-id")` | *"Newest job first — the one started last is the one still in hand."* | **YES** |
| `disconnects` | `.order_by("account_no", "id")` | *"Sorted by account number. The ladder stops by itself when a customer pays or agrees a plan, and the row leaves this list."* | **no** — alphabetical |
| `imports` | `.order_by("-created_at")[:200]` | *(none)* | **YES** |

**Six of eight do not open on creation order. Two already do.**

**The worked figure, measured rather than described:** opening `/brazosbend/accounts`
issues `GET /accounts?sort=name&dir=asc&page=1&per=50` **before the clerk touches a
control**, and the most recently created account on the tenant —
`AC-2026-00052`, *Ridge Property LLC* — comes back at **position 58 of 73**. At the
page size the screen uses, that is **page 2**.

⚠ **The address bar does NOT carry the sort until the clerk clicks a header.** The
drawing shows `?tab=accounts&sort=name&dir=asc&page=1` in the URL; live the bar
reads `/brazosbend/accounts` and the parameters are on the REQUEST. After one click
on `ACCOUNT` the bar reads `?sort=account_no&dir=asc&tab=accounts`. The blueprint's
`ACC-S11` says *"sends `?sort=name&dir=asc`"*, which is true of the request and is
the thing that matters.

### 2.3 The primary action, per tab

| tab | drawn | as built (measured) | |
|---|---|---|---|
| accounts | `+ New account` | `+ New account` | `=` |
| requests | `+ New request` | `+ New request` | `=` |
| new-connects | `+ New connect` | `+ New connect` | `=` |
| move-ins | `Move-in` | `Move-in` | `=` |
| move-outs | `Move-out` | `Move-out` | `=` |
| transfers | `+ New transfer` | `+ New transfer` | `=` |
| **disconnects** | **`+ New disconnect`** | **`Start a disconnect`** | `≠` — **`DEF-CUS-5063`** |
| imports | `↑ New import` | `↑ New import` | `=` |

Seven of eight match character for character.

### 2.4 The response envelope, per tab

| tab | envelope | server-paged? |
|---|---|---|
| accounts | `count` / `next` / `previous` / `results` | yes |
| requests | `count` / `next` / `previous` / `results` | yes |
| new-connects | `count` / `next` / `previous` / `results` | yes |
| move-ins · move-outs · transfers · disconnects | `rows` / `page` / `per` / `total` / `pages` | yes |
| **imports** | **`rows` only — no `count`, no `page`, no `per`** | **no** — the browser pages a capped array |

The request the Imports tab actually issues is `GET /imports?f.target=accounts`,
with **no `page` and no `per`**. `DEF-CUS-5061`.

---

## 3 · FINDINGS, EACH ROUTED

The one question (`22-product-maintenance-process.md`): ***can a user do this task
in the product today?*** All eight tabs are live, reachable and used, so every
finding below is **MAINTENANCE**. Where intake was ambiguous it is a **DEFECT**
(`13-change-process.md` §1).

### 3.1 · `DEF-CUS-5060` — six of the eight lists open on something other than creation order · **MAINTENANCE**

The table in §2.2 is the finding. `BR-CUS-1046` names the seven sibling tabs
explicitly, so this is one ruling measured across a whole screen rather than a
second defect about the accounts list. `DEF-CUS-4996` already carries the accounts
tab; this row carries the other five that need work and records the two that do not.

**And the ordering must move with the default.** `account_list` materialises every
matching row (`selectors.py:2747`) and sorts in memory (`:2803-2814`). **Measured:**
`GET /accounts?per=1` costs **0.107 s** and `?per=50` costs **0.102 s** — asking for
one row costs the same as asking for fifty, which is the `O(tenant)` proof in one
line. At 73 accounts that is 0.107 s; T5's ceiling is 40,000, about **548×** the
rows built to render the same page. A new default alone is one more in-memory
branch and makes the fifth `NFR-3` breach worse while hiding it behind a feature.

### 3.2 · `OQ-CUS-1790` — six of those lists have no sort control, so there is nothing for a clerk's choice to win · **OPEN, NOT RESOLVED HERE**

`BR-CUS-1046`'s second clause is *"a clerk's chosen sort must still win and still
survive a refresh"*. **Measured: only the accounts tab declares sortable columns.**
The other six declare none, because each server accepts no `sort` parameter — so on
them *newest first* is not a default a clerk can override, it **replaces** the
ordering outright, and four of the six are ordered by urgency and say so on screen.
Putting a collections ladder in creation order changes what a collections clerk can
do, which is the maintenance process's own test for what returns to the PO.
**Three answers are stated with their costs in the register row. None is chosen
here** (prime directive). ⚠ **The accounts tab is NOT blocked by this** — it has a
sort control, so the ruling applies to it literally and `DEF-CUS-4996` can be fixed
without the answer.

### 3.3 · `DEF-CUS-5061` — the Imports tab pages in the browser over a hard 200-row cap · **MAINTENANCE**

`run_list` ends `rows.order_by("-created_at")[:200]` and returns `{"rows": […]}`
with no envelope. `NFR-3` (universal server pagination) and `NFR-5` (no hard caps
anywhere) are the T4/T3 flexibility `CLAUDE.md` rules load-bearing. **The cap is
recorded and has never been reconciled with either rule:** the decision log of
2026-08-27 (`DEF-1702`) reasons carefully about where a filter runs *relative to*
the cap and never asks whether the cap may exist. At the 201st accounts import the
tab draws a complete-looking history that is not complete.

### 3.4 · `DEF-SHL-5062` — B14 rule 13's sort glyph is never drawn on an unsorted column · **MAINTENANCE, and it belongs to `CR-093-BRC01`'s batch**

`DataTable.tsx:846-851` puts the glyph inside `{sorted && …}`. **Measured:** the
live `ACCOUNT` header is `<button type="button" class="table-sort">Account</button>`
with no child at all, while `NAME` renders `<span class="table-sort-arrow">▲</span>`.
`.table-sort` (`DataTable.css:151`) declares `cursor: pointer` and nothing visible.
So four sortable columns and four unsortable ones are identical on screen.
**The drawing and the rule agree with each other and the screen matches neither** —
the blueprint draws `⇅` on exactly those four. Shared component: it is every list
table in the product, and it is a **fifth** row of the family `CR-093` carries, not
one of its five. The two rule-13 defects already filed (`DEF-SHL-4946`,
`DEF-MET-4957`) are both about the **third click**; the clause before it was never
filed.

### 3.5 · `DEF-CUS-5063` — the disconnects tab's primary reads `Start a disconnect` · **MAINTENANCE**

In none of B14 rule 4's three grammars (`+ Noun` creates, `Verb →` navigates,
`Verb ✓` commits), and the control navigates to `/:tenant/disconnects/new`, a
creator. Three documents spell it three ways: the blueprint `+ New disconnect`, B18
§414 `+ Start a disconnect`, the product `Start a disconnect`. **And the caution in
the wording has expired** — `EP-CUS-08` TC-22 held this CTA disabled because the
flow had no route (*"a live button onto nothing is bad; a danger one is worse"*);
`/disconnects/new` shipped 2026-08-25 and the button is live. That is hard-won law
2's mirror: the copy written under a hold outlived the hold.

### 3.6 · `CR-093-BRC01`'s rows, measured on this screen — **STATED, NOT FILED, NOT BUILT**

| CR-093 row | measured here | applies? |
|---|---|---|
| `DEF-SHL-4946` the sort's third click | clicked `ACCOUNT` three times: `asc` → `desc` → **`asc`**. It never clears. | **yes** |
| `DEF-449` / `DEF-MET-4958` the pager | footer renders `1–50 of 73 · Rows per page … · ‹ ›`. No `Showing`, no `⇤`/`⇥`, no `Page x of y`. | **yes, on all eight tabs** |
| `DEF-SHL-4949` the KPI gap | `.kpi-grid` computed `gap: normal`; tiles step exactly 224px with no gutter. B14 rule 39's anchor is `16/20 gap 8`. | **yes** |
| `DEF-SHL-4948` / `DEF-2453` rule 15's row-action cap | at most **one** icon in a row on every tab of this screen (`Open this request`, `Open this connection`, `Roll back this run`); the accounts tab has none. | **NO — this screen does not breach it** |

### 3.7 · `Columns ▾` drawn twice · **NOT A DEFECT — B14 rule 12 settles it in the product's favour**

The drawn toolbar carries an icon-only `[▦]` *and* a labelled `Columns ▾`. The
product has one control, icon-only, doing the job. **B14 rule 12 is RATIFIED and
spells the toolbar out:** `[Search…] [All | filter chips ×] [+ Filter ▾] … [▦ Columns]`
— the product **is** the rule. Under B14 rules 36 and 38 the drawing loses on
construction and the divergence is recorded rather than built. §09 of the blueprint
independently grades `UI-RULES 14` **PASS** on this control.

### 3.8 · `⇩ Export` drawn and absent · **NOT A DEFECT — a registered refusal**

`DataTable` exposes `downloadSlot` and `AccountsListPage` does not pass it; the
component's own comment reads *"Absent slot = no export"*, and the screen's header
records why: *"`/exports` has no `accounts` resource registered, and BR-SHL-010 says
an undeclared capability does not render."* A held control and a broken control look
identical on screen; this one is held, and the register says so.

### 3.9 · The search placeholder's grammar · **NOT A DEFECT — `OQ-600`, OPEN**

`Account #, customer #, name, address, or meter #…` has no leading verb, where B14
rule 19 reads *"Search {entities}…"*. `OQ-600` is **OPEN** and covers exactly this:
five of the tabs' prompts are B18's own text and the server serves the identical
string as `search.hint`, so rewriting one side would put the drawn prompt and the
served hint into disagreement about one box. The blueprint's §09 lists screen 01
under **Exempt — not violations** for the same reason. **Not resolved here.**

### 3.10 · The second `GET /accounts` on every open · **RECORDED, NOT FILED**

Opening the screen issues a second request,
`?sort=name&dir=asc&page=1&per=50&f.status=pending_activation`, whose rows are
discarded for the envelope `count` that fills the *Pending activation* tile (the
blueprint grades that field `DERIVED`). **Measured at 0.065 s against the list's
0.107 s**, because `f.status` is a real SQL filter — so it is `O(pending)` and not a
second `O(tenant)` build. Worth knowing when `DEF-CUS-5060`'s fix is designed;
**not worth a row on its own, and this lane declines to overclaim it.**

---

## 4 · WHAT THE DRAWING SAYS IS **ABSENT**

Skill §2.5 — an absence is a decision. Each of these is drawn as missing **on
purpose**, and a step-2 lane must not fill any of them in.

1. **No `Plan` column and no `Plan` filter.** The blueprint's *Words* row: *"Refused:
   a **Plan** column, because the snapshot has no DDL and an always-empty column is
   a worse answer than none."* `BR-CUS-029`.
2. **No ageing pill inside `Status`.** *"Refused: **Current** as a fallback for a
   null ageing band — that would be a claim about a customer's money."*
3. **No figure on `PAST-DUE 60+` and none on `CLOSED THIS YEAR`.** Both read
   `Not counted yet`. The blueprint grades this `HONEST, STILL uncounted` and the
   product's own copy explains each; `null` and `0` are different claims.
4. **No select column and no row-action cell** on the accounts table. One link per
   row, on the account number.
5. **No status segments beyond `All`.**
6. **No `Showing`, no first/last, no `Page x of y`** in the drawn footer — the
   drawing agrees with the product here and both disagree with B14 rule 16. That is
   `DEF-449`, and it is `CR-093`'s to fix, not this screen's to redraw.
7. **No kicker above the `Accounts` title.** Remedy `R2`'s frame draws one
   (`CUSTOMERS`); see §5.1 — it is illustration, not a commitment.
8. **No bulk actions, no export, no saved views, no density control.**

⚠ **Two things this lane believes are missing and is NOT adding** (skill §2.5 —
*say so, do not add it*): the drawing offers no way to reach an account's **work
queue** after a wizard commits, and no **sort control** on any of the seven sibling
tabs. The first is `ACC-S20`'s own finding (*"this document never drew where a clerk
goes after pressing Submit"*); the second is `OQ-CUS-1790`.

---

## 5 · THE REMEDY, AND WHAT THE BLUEPRINT GETS WRONG ABOUT ITSELF

### 5.1 · `R2 · A list footer that is honest about what it sorted` (`ACC-S2`, p151–152)

**Two elements, and only one is new:**

1. **⑧ Pagination footer** · `count` from the DRF envelope · `UI-RULES 16` ·
   **UNCHANGED**.
2. **⑨ Sort scope line** · *"states whether the ordering is over the whole result
   set or only the page"* · drawn as `Sorted by Balance across all 40,000 accounts`
   · *"no rule covers this — it is stated only in this document"* · **NEW**.

The remedy's own closing sentence: ***"⑨ is the only element this remedy adds."***
And its reasoning, which a step-2 lane must read before touching this screen:
*"Drawing a new toolbar here would be a redesign wearing a fix's clothes — the
maintenance process names that case explicitly, and it has already gone wrong once
on the property Overview."*

⚠ **`R2`'S FRAME DIFFERS FROM THE AS-BUILT FRAME IN SIX WAYS AND EVERY ONE OF THEM
IS ILLUSTRATION (B14 rule 37).** It draws a `CUSTOMERS` kicker, puts `Filter ▾`
*before* the search, uses a different placeholder (`Search by account, name or
address`), shows **four** columns instead of eight, drops the KPI strip, and drops
`Move-out` / `Move-in`. **Two frames of one blueprint drawing the same screen
differently is exactly the case rule 37 exists for — build the shape they agree on
and ignore both sets of figures — and here the remedy settles it in one sentence of
its own.** Nothing in `R2`'s frame is a commitment except ⑨.

### 5.2 · `ACC-S11` (p153) — the finding this CR already acted on

The card that produced `BR-CUS-1046`, recorded before this CR existed. Read as an
image; its ruling quotation and its *"It is not one list"* paragraph are the
authority for §2.2 and §3.1. Its own closing warning — *"⚠ This ruling is not in
the repository"* — is now false and stays true as history: it was landed as
`7dbd15d82`.

### 5.3 · Three places the blueprint contradicts itself, each of which would mislead a step-2 lane

**(a) THE TAB COUNT. It says both eight and ten.** p4's *Tabs* row says
*"**Eight**, all in the URL as `?tab=`"* and the drawing draws eight. **p149 §09**
says *"All **ten** tabs render a real list with an empty state and a CTA"* and
**p209 `ACC-S20`** says *"the register's **ten** tabs are where they land"*. Both
were read off rendered pages. **The product has eight** (`ACCOUNTS_TAB_IDS`, and
eight `role="tab"` buttons measured in the DOM). **Eight is right; ten is wrong in
two places.** `ACC-S20`'s own body then lists **seven** worklists, which with
`accounts` is eight — so the sentence contradicts itself inside one row.

**(b) §09 GRADES `UI-RULES 16` PASS OVER A DEFECT OPEN SINCE 2026-08-21.** Its
evidence is *"On the response. `core/pagination.py:34`"* — but rule 16 is about what
the **footer renders**, and the footer renders neither `Showing`, nor `⇤`/`⇥`, nor
`Page x of y` (`DEF-449`, re-found as `DEF-MET-4958`). A lane reading §09 would
conclude the footer is fine.

**(c) THE SCREEN-01 CHIP NAMES TWO SPECIFICATIONS AND §12 GIVES IT FIVE.** The chip
reads `ACC-01 · ACC-02` — a spelling §12 never uses. By §12's own *Screens* column,
screen 01 is named by **`ACC-S2`, `ACC-S5`, `ACC-S6`, `ACC-S20` and `ACC-S21`**; and
`ACC-S11`, which carries the ruling that started this CR, names **no screen at all**
because it is a §10 card rather than a register row.

**(d) The field table's own tally is one row short of its own table.** It reads
*"9 SERVED · 1 DERIVED · 3 HARDCODED/DEAD · 2 NOT SERVED · 0 untraced"* = 15, over
**16** rows, of which **10** carry a `SERVED` badge (① Account # … ⑩ KPI · Outstanding).

### 5.4 · §12's own count, independently confirmed — and one correction to it

Counted from the rendered ID column of pages 207–209: **seventeen rows** —
`ACC-S1` `S2` `S3` `S4` `S5` `S6` `S7` `S8` `S9` `S10` `S14` `S15` `S16` `S17` `S18`
`S20` `S21`. **This lane reached the same figure as step 1 lane 2 independently**,
which is the settlement `CR-094` §3b asked for, and `DEF-GOV-5007` carries it.

⚠ **ONE CORRECTION, AND IT IS FILED AGAINST THAT SAME ROW RATHER THAN A NEW ONE.**
The settlement says *"`ACC-S19` appears nowhere in the document"*. **It does:** it is
the tag beside remedy `R9`'s heading on **page 198** — `R9 · The customer you already
have, flagged where the details are typed  (ACC-S19)` — read off the rendered page,
not the text layer. So all four numbers absent from the register have a home in §10:
`S11` `S12` `S13` are **finding** ids and `S19` is a **remedy** tag. That is a tidier
rule than *three findings plus one that does not exist*, and it matters because a
lane sent looking for `ACC-S19` and told it is not there stops looking.
`08-screen-layouts.md` is corrected in the same commit as this document.

---

## 6 · WHAT THIS LANE COULD NOT CONFIRM, AND WHAT WOULD SETTLE IT

1. **Where the newest record lands on five of the seven sibling tabs.** The seeded
   `brazosbend` tenant holds 6 requests, 8 connections, 1 move-in, 1 move-out,
   **0 transfers**, 6 disconnects and 4 accounts imports. With one row or none there
   is no position to measure, so §2.2's verdict for those tabs rests on the single
   `.order_by(...)` each server applies — read at source, unambiguous, and not
   walked. **Seeding a dozen rows per worklist would settle it**; step 1 did not,
   because the ordering is not in doubt and a seed is state a step-2 lane would
   inherit.
2. **Whether the `[▦]` control sits where the drawing puts it.** Live it is at the
   toolbar's right edge behind a `table-toolbar-spacer`; the drawing puts a square
   icon mid-toolbar and a labelled `Columns ▾` at the right. Whether those are one
   control drawn twice or two controls is not answerable from the frame. **B14 rule
   12 makes it moot** — the ruled toolbar ends at `[▦ Columns]` — which is why §3.7
   records it rather than filing it.
3. **The empty, loading and failed states.** The tenant has data, so the drawn
   `Empty` / `Loading` / `Failed` states of §1.9 were **not** reproduced. The
   transfers tab was the one genuine empty state walked, and it renders its KPI
   strip, its lede and `No transfers yet` with the header's `+ New transfer` above
   it. **Settling the rest needs a tenant with no accounts and a forced 403**, which
   is step 2's reproduce step rather than step 1's.
4. **The eleven catalogues.** Every string quoted here is the English one. Whether
   the ten other locales carry the same labels was not checked, and B14 rule 35
   (*a catalogue is written in its own language*) has no gate.

---

## 7 · WHAT THIS LANE DID NOT DO

No product code was changed — not one line. The only files this lane writes are this
document, four register rows, one open question, one correction to
`08-screen-layouts.md`, one id-reservation row, one decision-log row, and
`10-scripts/cr094_lane1_register_measure.py`, which reads eight endpoints and writes
nothing. **Nothing was seeded**; the `brazosbend` tenant is exactly as it was found.
