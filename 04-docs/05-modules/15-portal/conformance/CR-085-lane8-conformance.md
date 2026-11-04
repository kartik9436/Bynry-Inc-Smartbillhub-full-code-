# CR-085 lane 8 — what is built, against what is drawn

**Routes:** `/usage` `CWP-033` · `/readings` `CWP-034` · `/equipment` `CWP-037` ·
`/requests` `CWP-046` · `/requests/:reference` `CWP-051` · `/ask` `CWP-010` ·
`/ask-a-question` `CWP-054`.
**Drawing quoted in:** `CR-085-lane8-drawing.md` (this folder).
**Read and measured:** 2026-09-11, worktree at `b4063d1e6`, bundle
`index-N9cg-E6T.js` on the shared stack at `http://127.0.0.1:8401`.
**Widths: 390 AND 1280, every screen, every state.** Screenshots and the
measurement JSON are in the lane's scratchpad
(`…/scratchpad/lane8/shots/{full,empty,fail}-<screen>-<width>.png`,
`report-{full,empty,fail}.json`).

---

## 0 · HOW THIS WAS READ, AND WHAT THAT DOES AND DOES NOT PROVE

**The shared stack cannot sign a customer in, and no lane can fix that from
here.** Its one tenant (`brazosbend`) holds **zero rows in `portal_credential`**,
so `POST /api/brazosbend/portal/auth/sign-in` answers `401` and
`GET /portal/session` answers `401` — visible in `/tmp/api.log` from several
lanes, not only this one. Its single account also has **no services, no reads,
no bills and no equipment**, so even a signed-in walk would exercise only empty
states. Creating a credential was not attempted: it needs the account holder's
name and the one-time code, and reading either is outside what this lane should
be doing to a shared demo database.

**So the browser work was done against the real bundle with the SIGNED-IN reads
answered from fixtures** (`page.route` on `**/api/**`; fixtures shaped from
`portalClient.ts` and each screen's own `.dom.test.tsx`). Everything else —
`/portal/public/front`, `/portal/public/quick-services`,
`/portal/public/service-centres`, `/portal/public/help` — was passed **straight
through to the live server**.

**What that proves and what it does not, stated so nobody over-reads it:**

| Proven | Not proven |
|---|---|
| Layout, order, wrapping, spacing and computed style at 390 and 1280 | Anything about what the SERVER actually sends on a populated tenant |
| Which elements exist, which are absent, which are empty | That a figure is arithmetically right |
| Every state: loading, empty, failed, held, estimated, corrected | The picker on `CWP-034` (one meter in the fixture, so it correctly draws nothing) |
| Anything read off `/portal/public/*` — that IS live | The `trash`/`share` panels on `CWP-033` beyond the single sewer case |

⚠ **One reading was WRONG because of the fixture and is retracted here rather
than reported:** the Equipment table showed `$12.0000`, four decimals, which
would be a hard-rule-2 breach. It is not. `billing_seam.per_item_monthly` puts
the figure through `core.money.finalize` before it leaves the server, so the
wire carries `12.00`; the four decimals were this lane's fixture. **The screen
does no rounding of its own**, so the 2-decimal guarantee rests entirely on that
one server helper — worth knowing, not worth filing.

---

## 1 · THE FRAME — one line, as instructed

The heading bar, the menu, the account line, the page-heading gap and the
universal spacing scale are **LANE 1's**. Two observations handed over without
further work: `/ask` (`CWP-010`) renders the **GUEST** heading bar with a
`Sign in` button to a customer who is signed in, because it is a guest screen at
a signed-in address; and the diagnostic `ScreenIdTag` chip (`CWP-033` etc.) is
visible bottom-right on every screenshot here — it is the PO's own
*"for time being"* badge behind `VITE_SCREEN_ID_TAG`, not a rule-31 breach.

---

## 2 · SCREEN BY SCREEN — every difference

Legend: **MISSING** drawn and not built · **EXTRA** built and not drawn ·
**WORDS** built with different copy · **ORDER** · **STATE** · **WRONG** ·
⚖ the two drawings disagree, so B14 rule 37 applies and this is a divergence to
record rather than a defect to fix.

### `CWP-033` · `/usage` — blueprint screen 50

| # | Kind | What |
|---|---|---|
| 33-a | **MISSING** | **The screen has no page heading of any kind** — no `PageHeader`, no `<h1>`, no kicker. `document.querySelectorAll("h1,h2,h3,h4")` returns exactly one node at both widths and it is the chart panel's `H3`. *What you have used* is a `SectionTitle` inside the first card. It is the only one of this lane's seven without a head, and it is a live instance of `DEF-CWP-4000` |
| 33-b | **MISSING** | The drawing's **`WHAT THIS COST YOU` → `See the whole bill →`**. The cost panel is built (`CPB-08`) and its link to the bill is not; it names the bill in words (`From bill BL-2608-000042`) and offers no door to it |
| 33-c | **WRONG** | **The axis label repeats the panel title.** The panel head reads `Electric · kWh per month` and the line immediately under it reads `kWh per month`. Confirmed at both widths — `DEF-CWP-4175` clause (1), **still open** |
| 33-d | **WRONG** | **Five KPI tiles in a four-column grid**, so `NEXT READING DUE` sits alone on a second row at 1280 (`grid-template-columns: 253px ×4`). Filed as **`DEF-CWP-4847`** |
| 33-e | **EXTRA** | A door row — `Every reading` · `Meters and equipment` — inside the first card. The drawing has none; the code records why (they are the only inbound links `CWP-034`/`CWP-037` have). Recorded, not filed |
| 33-f | **WORDS** | The download control is an **icon alone** (`↓`, no label). Both the captured pack (`↓ CSV`) and blueprint rule **R-01** (*"Every icon carries its word — never an icon alone"*) say otherwise. R-01 is an UNRATIFIED drawn rule — see §5 |
| 33-g | ⚖ | **`MONTHLY AVERAGE` vs `DAILY AVERAGE`.** `CWP-033.png` draws *DAILY AVERAGE / 155 gal*; the blueprint draws *Average / 664 kWh*. The build is monthly and says why (`DEF-CWP-4001`: the read carries `avg_per_month` and no daily figure). **`DEF-CWP-4170` is now a divergence from the OLDER drawing only** and should be re-triaged rather than fixed |
| 33-h | ⚖ | The blueprint's `AGAINST LAST YEAR` is three rows (`Aug 2026 800 kWh` / `Aug 2025 714 kWh` / `Difference +86 kWh`). Built renders a sentence plus two year totals; the code states the reason (the read carries no same-month figure, and browser arithmetic would produce a number no clerk screen can reproduce). Recorded |
| 33-i | **STATE** | The drawing's **`NO HISTORY`** state is *"We need two reads before we can show a trend." Says when that will be.* Built has `noServices` (*Your services will appear here.*) and `noReadingsYet` (*No readings yet on this service.*) — **neither says when** |
| 33-j | **STATE** | On a failed read the whole page is replaced by one sentence in one card; `data-screen` disappears with it. Filed as **`DEF-CWP-4846`** |
| 33-k | ✅ | `CPB-06`, `CPB-07` and `CPB-08` are all **BUILT and visible**: *86 kWh more than Aug 2025* · *5.00% less than Jul 2026* under the big number · *800 kWh at $0.1150 = $92.00 / From bill BL-2608-000042* |
| 33-l | ✅ | **Every figure carries its unit** (hard rule 3), at the number, in the customer's own unit: `800 kWh`, `470 kWh`, `664 kWh`, `948 kWh`, `86 kWh more than…`, `8,402 kWh`, `7,502 kWh`, axis `kWh per month`, and each bar's `title`. **No bare number anywhere on this screen at either width.** The *"Monthly average 800"* that CR-085's history records is gone |
| 33-m | ✅ | One service at a time; the picker is the account's own services; a one-service account draws no picker (verified); an unmeasured service draws a panel and **no `<svg>`** |
| 33-n | ✅ | At 390 the KPI row stacks to one column and `document.documentElement.scrollWidth === 390`. **Nothing scrolls sideways at 390 on any of the seven screens** |
| 33-o | **WRONG (phone)** | The chart's month labels **truncate with ellipses at 390** — `Jan Feb M… Apr M… Jun Jul A… Sep Oct N… D…`. The bars are readable; the axis is half-legible. A usage chart is the hardest thing in this portal to make work on a phone and this is where it shows |

### `CWP-034` · `/readings` — blueprint screen 51

| # | Kind | What |
|---|---|---|
| 34-a | **WRONG** | **The correction sentence prints the wire's ISO date to the customer**: *"We estimated 38,700 and corrected it to 38,776 when the meter was read on **2026-05-02**."* — two lines under a `TAKEN` column reading `04/30/2026`. `correction.corrected_on` is interpolated raw while every other date on the screen goes through `usePortalDate`. **`DEF-CWP-4172`, still open**, confirmed in a browser |
| 34-b | **STATE** | **An estimate carries two of the drawing's three signals.** Every `<tr>` returns `background-color: rgba(0, 0, 0, 0)` — the estimated row included. Filed with 34-c and 37-d as **`DEF-CWP-4849`** |
| 34-c | **STATE** | `NO READS YET` is drawn as *"Your first read is due around Sep 30."*; built says *"Your first reading will appear here."* and gives no date |
| 34-d | **MISSING** | The drawing's `CUSTOMER READ` chip is *"You sent this", with the date received*. Built has `how.self_read` = *"You sent it in"* and **no date received** |
| 34-e | **MISSING** | `METER CHANGED` (old meter final read, new meter start) and `LONG RUN OF ESTIMATES` (a banner offering an appointment after three in a row) are both drawn and neither exists |
| 34-f | **EXTRA** | A `Search readings…` box and a `Rows per page 50` select. Neither drawing has either; both are staff-list furniture on a customer screen |
| 34-g | ✅ | **`CPB-09` IS BUILT** — *"Next read: Sep 30 · in 19 days"*, above the list, exactly where the blueprint puts it. The blueprint's own text says the readings data carries no next-read date; it does now, through `metering_seam.read_window_for_unit`, the same derivation the Usage tile reads |
| 34-h | ✅ | The held `Send a reading` is in the header's action slot with its reason under it (`CR-068` R3), drawn as the outline the wireframe draws |
| 34-i | ✅ | Units on every quantity: `800 kWh`, `842 kWh`, `790 kWh`, `655 kWh`, `712 kWh`. The dial figures (`41,208`) correctly carry none — a register index has no unit |
| 34-j | **WRONG** | **The dial is grouped and the quantity is not, on the same row**: `41,208` comes from the client's `formatDialFigure`, `800 kWh` from the server's `quantity_text`, which adds no grouping. `DEF-CWP-4168`, **still open**, and it is now visible on two of this lane's screens (see 33-l's `8,402 kWh` beside an ungrouped KPI) |
| 34-k | **STATE** | Failed read: same as 33-j — and here the vanished header takes **`← Usage`**, the screen's only door. **`DEF-CWP-4846`** |

### `CWP-037` · `/equipment` — blueprint screen 52

| # | Kind | What |
|---|---|---|
| 37-a | **MISSING** | **`size_class` is never drawn.** The drawing writes it into the equipment cell on both widths and says why. On a fire line the size class *picks the price*, so the one row carrying a monthly charge is the one row whose charge cannot be checked. Filed as **`DEF-CWP-4848`** |
| 37-b | **WRONG** | The equipment cell is composed unconditionally as `{{service}} {{kind}}`, so a device the registry already names after its service stutters: `Fire Fire line`, `Trash Refuse cart`. Same row, **`DEF-CWP-4848`** |
| 37-c | **MISSING** | The drawing puts the **service address** under the title on both widths (`1841 Quarry Hill Ct, Silver Creek, TX 78611`). Built shows it only in the frame's account line — handed to lane 1 |
| 37-d | **STATE** | The empty state is one sentence and **no control**: the safety callout and `Report a problem` live inside the non-empty branch, so *"With a way to ask"* is unbuilt. **`DEF-CWP-4849`** |
| 37-e | **MISSING** | `BEING REPLACED` and `MULTIPLE ADDRESSES` (an address picker) are drawn states with no implementation |
| 37-f | **MISSING** | `CHARGED ITEM` is drawn as *"The monthly charge links to the bill line it produces."* The bill NUMBER is on the wire (`monthly_charge_bill`) and the cell renders **no link** |
| 37-g | ✅ | **`CPB-10` IS BUILT.** `WHOSE` (`Ours` / `Yours`) and `MONTHLY` are both columns, `No charge` is a stated FACT and `Not on your last bill` a stated GAP — the distinction the drawing needs and the one a `null` would have destroyed |
| 37-h | ✅ | The `WHOSE IS WHAT` sentence and the safety callout with its live `Report a problem` door are present and correct |
| 37-i | ⚖ | Columns follow the **blueprint** (`Equipment · Reference · Installed · Whose · Monthly`) plus `Status`; the captured pack's `WHERE` and `LAST READ` are deliberately gone on a PO ruling quoted in the source |

### `CWP-046` · `/requests` — blueprint screen 55

| # | Kind | What |
|---|---|---|
| 46-a | ⚖ | **The two drawings are different screens.** The blueprint draws *Your requests* — a list of everything asked for, with a `1 open · 2 finished` count line and an `Ask for something else` button. The captured pack draws *What do you need?* — six errand cards over an `OPEN REQUESTS` panel. **The product is the captured pack.** Nothing here is filed |
| 46-b | **MISSING** | The drawing's **`NEXT` column** (*"We reply by Aug 15"*) — `CPB-11`, and the blueprint's own argument for the whole screen. Not built, because no promised reply date exists in the data |
| 46-c | **MISSING** | The drawing's **`1 open · 2 finished`** count line. Built offers a `Still open / All of them` switch instead, absent until something has closed. The decision and its reason are in the source and the decision log of 2026-09-08 |
| 46-d | **WRONG** | **An errand the tenant configures without a label renders a blank card** — an empty `<h2>`, an empty `<p>` and a `Start →`. `words(t, null)` returns `""` and `selectors.request_errands` passes a configured row's `label` through unchanged. The six defaults all carry one, so this bites only a utility that configures its own cards |
| 46-e | **WRONG** | `t(\`portal.requests.held.${code}\`)` has no fallback. One such key exists (`not_online_yet`); a second server-side hold code would reach the customer as a raw dotted path. Recorded as a hazard rather than filed — no second code exists today |
| 46-f | ✅ | The status chip DOES fall back (`known ? … : "With us"`), so an unmapped state renders a word. This is the half `CWP-051` is missing — see 51-b |
| 46-g | ✅ | Columns `WHAT · REFERENCE · RAISED · STATUS · ACTIONS`, `SR-` reference rather than a row id, the row action an icon, and the honest scope sentence *"This list is what you have asked for online."* |

### `CWP-051` · `/requests/:reference` — blueprint screen 56

| # | Kind | What |
|---|---|---|
| 51-a | ⚖ | **The two drawings disagree completely.** The captured pack draws a six-step PROGRESS ladder and a DETAILS rail and **no thread**; the blueprint draws a thread (`WHAT HAS HAPPENED`, newest first) and **no ladder**. The product draws **both**, which is the union rather than the shape they agree on. Recorded under B14 rule 37 |
| 51-b | **WRONG** | **The status chip has no fallback.** `t(\`portal.request.state.${request.status}\`)` is rendered raw, so a state the catalogue does not carry prints as a dotted path in caps under the `<h1>` — observed as `PORTAL.REQUEST.STATE.IN_PROGRESS`. **The eleven catalogue keys do match the server's eleven states today**, so this is a live hazard rather than a live defect, and it is the concrete cost of `DEF-CWP-4709` (two catalogues for one vocabulary): the list is guarded and the detail page is not |
| 51-c | **WRONG** | Any read failure renders *"We cannot find that reference."* — a `500` and an offline network tell the customer their reference does not exist. The one-sentence answer is right for the three 404 shapes (`BR-CWP-024`); it is not right for a server error |
| 51-d | **MISSING** | `We will reply by Aug 15, 2026` (`CPB-11`) · `WHILE THIS IS OPEN — the disputed $47.50 is not due… the remaining $143.50 is still due on Aug 22` (`CPB-13`) · the attachment on a thread entry (`📷 meter.jpg`) |
| 51-e | **ORDER** | The drawing puts `Add something / Type here… / Send` **under the thread**; built puts it in the right-hand rail as `TELL US MORE` |
| 51-f | ✅ | `DEF-CWP-4201` is largely answered: the `<h1>` now says what the request IS (*A bill you queried — BL-2608-000042*), the kicker carries the reference, and the rail carries `Reference · Raised · Open for` plus *"Nothing is waiting on you."* |
| 51-g | ✅ | `DEF-CWP-4708`'s fix is present — `threadOf` drops the opener when the server composed a title, so the clerk's sentence no longer appears under **You** |
| 51-h | ✅ | `DEF-CWP-4707` is fixed where it mattered: `draw()` mounts under `/:tenant/portal/requests/:reference`. One residual bare `MemoryRouter` remains at the not-found case, which builds no address and asserts only absences |

### `CWP-054` · `/ask-a-question` and `CWP-010` · `/ask` — blueprint screens 53 and 54

| # | Kind | What |
|---|---|---|
| 54-a | **WRONG** | **`OR RING` renders as an empty card** on the live tenant, at both widths — the heading with nothing under it. The two phone lines are correctly conditional; the card that holds them is not. `BR-CWP-093` (*nothing empty ever appears*), and the file's own docstring states that rule about the suggestions panel one block above |
| 54-b | **MISSING** | The attachment control has **no field label**. The drawing labels it (*Attach something, if it helps* / *Attach a photo*); built renders only the held box carrying its reason |
| 54-c | **MISSING** | The reply-time promise — *"We reply within 1 working day"* on the phone, *"A question sent here is answered within one working day"* in the rail — and the **office hours** (*Mon–Fri 8 AM – 5 PM*). `CPB-11` again |
| 54-d | **MISSING** | The drawing's live suggestions (*"The suggestions appear as they type, from what they have written — not a static list"*). Built shows a fixed top three — `CPB-16`, correctly not built, and correctly ABSENT rather than empty when nothing is published |
| 54-e | **WRONG** | The bill chooser reads `BL-2608-000042 · 08/02/2026` — the **issue date**. Both drawings put the **amount** there (`BL-2608-0141 · August · $142.18`). `DEF-CWP-4202` names exactly this and is **still open** |
| 54-f | ⚖ | The blueprint has **no bill field at all** (*"The account is attached automatically"*); the captured pack has one and the build follows the captured pack |
| 54-g | **WORDS** | Title `Ask us something` (captured pack) vs `Ask us a question` (blueprint); `Tell us` vs `Your question`; `Send ✓` vs `Send my question`; `Might answer it now` vs `THIS MAY ALREADY BE ANSWERED`. All illustration-level under rule 37 |
| 54-h | **WRONG** | **`/ask` is not this screen.** It is `CWP-010`, the guest quick-service cards. The blueprint says both addresses render screen 40. Filed as **`DEF-CWP-4850`** |
| 10-a | **WRONG** | On `/ask`, the two cards the live server sends with `hint: null` (`low_pressure`, `other`) render an **empty `<p>`** — zero height between 15px margins, 30px of dead band. Filed with the field-anatomy half as **`DEF-CWP-4845`** |
| 54-i | ✅ | The photo box is HELD with its reason and there is **no `<input type="file">`** — the signed deferral observed exactly |
| 54-j | ✅ | Sent state, refusal state, `Send ✓` disabled with its reason, and the suggestions panel absent-not-empty all behave as drawn |

---

## 3 · THE 82 OPEN / PARTIALLY-FIXED `DEF-CWP` ROWS — this lane's slice, re-verified

The audits are dated 2026-09-05 and say *"before citing a row here as current,
open the screen."* Opened.

| Row | Register says | **What the screen says on 2026-09-11** |
|---|---|---|
| **`DEF-CWP-3986`** | partially-fixed — *"KpiRow/KpiTile (Home, Usage) … never been built"* | **THAT HALF IS BUILT AND THE ROW ALREADY SAYS SO.** `Usage.tsx` imports `KpiRow`/`KpiTile` from the kit and composes five tiles; the register's own `prevention` records the part-fix. The tiles are real, they carry `data-kpi`, and `getComputedStyle` reads `padding: 16px` / `gap: 4px` on each. **The five components still named by that row — `DocumentPreview`, `WarningBar`, `DialInput`, `ToggleChips`, `Panel.Emergency` — are not on these seven screens** |
| **`DEF-CWP-3945`** | partially-fixed — *"a clerk can pin a help answer to a screen and the customer never sees it"* | **STILL DEAD ON THE ONE SCREEN THAT IS MINE.** `published_content.ALSO_SHOW_SCREENS` is `("bill", "usage", "overdue")`. `bill` is wired (`BillDetail.tsx`) and `overdue` is wired (`Overdue.tsx`). **`usage` is not:** `selectors.account_usage` never calls `tenancy_seam.attached_answer`, `PortalUsage` has no `attached_answer` field, and `Usage.tsx` has no `AttachedAnswerCard`. So a clerk who ticks *also show this on the Usage screen* still publishes into nothing. The row's own `prevention` predicted exactly this (*"the bill and usage placements remain"*) and only the bill half has since landed |
| `DEF-CWP-4168` | open — two quantity formats on one screen | **STILL OPEN, and now on two screens.** `CWP-034` prints a client-grouped `41,208` beside a server-ungrouped `800 kWh`; `CWP-033` prints a client-grouped `8,402 kWh` in the year card beside server strings in the KPIs. Two code paths, `formatDialFigure`/`formatQuantity` vs `quantity_text` |
| `DEF-CWP-4169` | open — *"the third tile, NEXT READING DUE, is not built"* | **FIXED — CLOSE IT.** The tile renders at both widths: `NEXT READING DUE / Sep 30 – Oct 2 / Send your own, or we will call`. It is now the fifth tile and brings `DEF-CWP-4847` with it |
| `DEF-CWP-4170` | open — monthly average where the wireframe says daily | **UNCHANGED, AND NOW A DIVERGENCE FROM THE OLDER DRAWING ONLY.** The blueprint labels this tile *Average*; `CWP-033.png` labels it *DAILY AVERAGE*. B14 rule 37 makes both figures illustrations, and `DEF-CWP-4001` records the deliberate choice. **Re-triage rather than fix** |
| `DEF-CWP-4175` | open — three CWP-033 divergences | **ONE OF THREE STILL OPEN.** (1) the axis label still duplicates the panel title, both widths — open. (2) the service panel ORDER is moot: the row of per-service cards no longer exists (`CR-085` s50, one service at a time). (3) the trash basis now reads from `portal.usage.billedOnCart` = *"Your {{size}}"*, so the service name is no longer interpolated — fixed at the catalogue; not exercised in a browser because the shared tenant has no trash service |
| `DEF-CWP-4685` | open — a raw ISO date pair in the KPI number font | **FIXED.** Renders `Sep 30 – Oct 2` through `Intl`, and collapses a single-day window. **The wrap it also describes survives**: at 253px the value still breaks over two lines, which is `DEF-CWP-4847`'s second clause |
| `DEF-CWP-4510` | open — the usage tip asks for `portal_usage`, a screen a tip can never be aimed at | **FIXED IN CODE, ROW NOT MOVED.** `selectors.py` now asks for `"usage"` and carries the whole reasoning in a comment naming this row. Close it |
| `DEF-CWP-4000` | partially-fixed — 28 signed-in portal screens carry no heading | **`CWP-033` IS A SURVIVOR.** Six of this lane's seven screens have an `<h1>`; `/usage` has none at either width |
| `DEF-CWP-4201` | open — Track your request never says what the request is | **LARGELY ANSWERED** (51-f). What remains of it is `CPB-11`'s reply-by date, which is a commitment rather than a defect |
| `DEF-CWP-4202` | open — a bill is queried without showing what it is for | **STILL OPEN ON `CWP-054`** (54-e): the chooser shows the issue date where both drawings show the amount |
| `DEF-CWP-4203` | open — the requests hub has no door to the full list | **ANSWERED BY DESIGN on the half that is mine.** The `Still open / All of them` switch reaches finished requests at this screen's own address; the decision and its reason are recorded in the source and the decision log of 2026-09-08. The stop-or-restart half of that row is another lane's |
| `DEF-CWP-4706` / `DEF-CWP-4709` | open — two state maps that disagree | **STILL OPEN, AND 51-b IS THE COST.** The list falls back to *With us*; the detail page renders the key |
| `DEF-CWP-4707` | open — `CWP-051`'s test mounted with no `/:tenant` route | **FIXED where it mattered** (51-h) |
| `DEF-CWP-4198` / `DEF-CWP-4708` | open / open — a clerk's composed sentence reaching the customer | **NOT REPRODUCIBLE HERE.** `CWP-046`'s `WHAT` column renders the derived kind (*A bill you queried — BL-2608-000042*) and `CWP-051`'s thread drops the opener when a title exists. Both need a bill query raised through a live portal session, which this stack cannot do |
| `DEF-CWP-3880`, `4171`, `4173`, `4176` | open | **SERVER-SIDE OR FIXTURE-SIDE; not decidable from a screen.** `4171` (a correction's reason written to one row and read from the other) is consistent with 34-a: the sentence has no reason clause at all today |

---

## 4 · THE 24 SPECIFICATIONS — which touch these seven screens

| Spec | Screens | Verdict on 2026-09-11 |
|---|---|---|
| **`CPB-04`** A customer can send us a meter reading | 51 | **NOT BUILT, correctly held.** `Send a reading` is disabled in `CWP-034`'s header carrying *Sending readings is not ready yet*, drawn as the outline the wireframe draws, with the hold's expiry written as data (`CWP-035` gaining an address turns a test red) |
| **`CPB-05`** the errand cards work online | 55 | **PART-BUILT.** Three of six default errands lead somewhere (`stop_for_a_while`, `report_problem`, `something_else`); the other three are held with one reason. The card-level half this lane found is 46-d |
| **`CPB-06`** compare against the same month last year | 50 | **BUILT.** *86 kWh more than Aug 2025*, and the absence names the month it wanted (*No Aug 2025 to compare with.*) rather than the blanket sentence the spec quotes |
| **`CPB-07`** compare against last month | 50 | **BUILT**, in the slot the spec names — *"under the big number"*: `5.00% less than Jul 2026` as the first tile's sub-line, computed by the server and walked back to the nearest month that HAS a figure |
| **`CPB-08`** a usage month says what it cost | 50 · 32 | **BUILT ON MY SIDE, AND IT STRADDLES LANE 5.** `WHAT AUG 2026 COST / 800 kWh at $0.1150 = $92.00 / From bill BL-2608-000042`, one row per bill line, the total the server's own sum, `Not billed yet.` said out loud, and `=` is not an operator — every figure is the bill's own. **What MY side still needs is the DOOR:** the panel names the bill in words and does not link to it, where the drawing reads `→ See the whole bill →`. That link lands on lane 5's `CWP-028` at `/bills/{number}`, so the address and the anchor text are a joint decision. Nothing else on this screen is waiting on lane 5 |
| **`CPB-09`** readings say when the next read is due | 51 | **BUILT — and the spec's own premise has moved.** The spec says *"The readings data carries no next-read date. The usage data does"*; `account_readings` now serves `next_read` from `metering_seam.read_window_for_unit`, the same derivation the Usage tile reads, so the two screens cannot disagree about one date. Renders *Next read: Sep 30 · in 19 days* above the list. **The residual is the EMPTY case** (34-c): with no reads at all the screen still says nothing about when the first one is due, which is the sentence the drawing puts there |
| **`CPB-10`** equipment says whose it is and what it costs | 52 | **BUILT.** `WHOSE` and `MONTHLY` are columns; the fact/gap distinction is kept. Two things the spec does not name are missing anyway: the size (`DEF-CWP-4848`) and the link from the charge to its bill line (37-f) |
| **`CPB-11`** a request says when we will reply | 55 · 56 | **NOT BUILT.** No `NEXT` column on `CWP-046`, no *We will reply by* on `CWP-051`, no reply-time promise on `CWP-054`. Three surfaces, one absent datum |
| **`CPB-12`** finished requests can be seen and counted | 55 | **PART-BUILT.** `closed_requests` is on the wire and reachable through the scope switch; a finished request opens. **The COUNT the spec quotes (*1 open · 2 finished*) is not stated anywhere** |
| **`CPB-13`** a disputed amount is split out on the request | 34 · 56 | **NOT BUILT** on `CWP-051`: no money travels with a request, so the `WHILE THIS IS OPEN` panel cannot be drawn |
| **`CPB-16`** help suggests answers as somebody types | 53 | **NOT BUILT**, and correctly so: the form shows a fixed top three and the panel is ABSENT rather than empty when nothing is published |
| **`CPB-17`** a signed-out visitor is offered a sign-in | 53 · 54 | **NOT VERIFIABLE FROM HERE** — it needs a session to not have, and this stack cannot create one to compare against. Its screen list also assumes 54-h's false premise |
| **`CPB-23`** every screen carries its How-you-get-here row | all | **NOT BUILT as a document row.** In the product, four of this lane's seven name a door in code (`CWP-034`/`CWP-037` from `CWP-033`; `CWP-051` from the hub; `CWP-054` from the hub's *something else*). `/usage` itself is reached from the frame's `Usage` tab |
| `CPB-01`,`02`,`03`,`14`,`15`,`18`,`19`,`20`,`21`,`22`,`24` | — | **Do not touch these seven screens** |

---

## 5 · THE 12 UNRATIFIED DRAWN RULES — which of them these screens lean on

Appendix A marks 12 of its 24 rules `NO HOME — stated only here`. **They are
proposals, not law.** Six bear on this lane:

| Rule | Stated as | Where this lane leans on it |
|---|---|---|
| **R-01** *(EXTENDS, not NO HOME — listed because it reverses a B14 rule)* | "Every icon carries its word — never an icon alone." Overturns the staff rule *because a phone has no hover* | `CWP-033`'s CSV download is an icon alone (33-f). **B14's own rule is the opposite** (*row actions are ICONS with tooltips*), so a lane cannot obey both and today obeys B14 |
| **R-06** | "Never ask a customer to compute — show the difference, not two numbers." | `CWP-033` obeys it (*86 kWh more than Aug 2025*, *5.00% less than Jul 2026*) and then shows the two year totals underneath as well |
| **R-07** | "One filled button per screen." | `CWP-051` draws `Send ✓` and `Withdraw the request`; `CWP-046` draws three `Start →`. Nothing enforces it and nothing in the repo states it |
| **R-10** | "Bad news never appears without the way out beside it." *(the appendix calls it the strongest rule on the page)* | **This is the rule `DEF-CWP-4846` breaks.** A failed read on `CWP-034`/`CWP-037` removes the only door out along with the header. The defect stands on `BR-CWP-093` and the drawing's own back-link, not on R-10 |
| **R-13** | "A route existing is not a door." | `CWP-033` is the only door to `CWP-034` and `CWP-037`, which is why its door row is EXTRA against the drawing (33-e) and must not be "tidied away" |
| **R-22** | "Three states — loading, empty, failed — can never render as the same picture." | On `CWP-033` all three are **one sentence in one identical card**; only the words differ. If R-22 is meant literally, this screen fails it; if it means *the words must differ*, it passes. **Unratified, so this lane records it and builds nothing** |

Also relevant and NOT leaned on, recorded so the next reader does not have to
re-derive it: **R-17** (*usage in the customer's own unit — never raw, never
converted*) is INHERITED from CLAUDE.md hard rule 3 and is **fully observed on
both `CWP-033` and `CWP-034`** — see 33-l and 34-i.

---

## 6 · B14 RULE 39 — measured, not assumed

Rule 39 was ratified 2026-09-11 and its own status cell says it is
**UNENFORCED** and that **no `--sp-N` token exists in `tokens.css`**, so it is
unbuilt at ratification. Everything below is `getComputedStyle` on the running
app, printed beside the ratified figure.

### 6.1 The KPI anchor — `KPI 16/20 gap 6`, on `/usage`

**The KPI row is genuinely BUILT** (item 4's premise that it was never built is
out of date — see `DEF-CWP-3986` above), so it is measured rather than
substituted for.

| What | Ratified | Measured (390 and 1280, identical) |
|---|---|---|
| KPI tile padding, block | 16 | **16px** ✅ |
| KPI tile padding, inline | 20 (`--sp-5`, *KPI cell side padding*) | **16px** ✗ — `KpiTile` is `p-4`, one value on all four sides |
| KPI tile internal gap | 6 | **4px** ✗ — `gap-1` |
| Row gap between tiles | (not anchored; `--sp-4` = 16 is *between blocks*) | **16px** (`gap-4`), row and column |
| Grid at 1280 | — | `253px 253px 253px 253px` with **five** tiles → `DEF-CWP-4847` |
| Grid at 390 | — | `350px` — one column ✅ |

⚠ **AND THE ANCHOR IS NOT ON THE RULE'S OWN SCALE.** The ratified scale is
`4 · 8 · 12 · 16 · 20 · 24 · 32` and the rule says *"no ad-hoc 3 / 7 / 9 / 14
anywhere"*. **`gap 6` is not a step of that scale.** A lane implementing rule 39
will have to choose between the scale and the anchor, and that choice is the
PO's, not a lane's. **Recorded, not decided.**

### 6.2 The form anatomy — `label→input 5 · input→helper 6 · field→field 20`, on `/ask-a-question`

Measured on the three fields of `CWP-054`, identical at 390 and 1280:

| Gap | Ratified | Measured | |
|---|---|---|---|
| label → input | **5px** | **4px** | `FormField` is `flex flex-col gap-1` |
| input → helper | **6px** | **17px** | the 4px gap **plus a 13px `margin-top` on the helper `<p>`** |
| field → field (no helper) | **20px** | **16px** | the card's own `gap-4` |
| field → field (after a helper) | **20px** | **29px** | 16px plus the helper's own 13px `margin-bottom` |

**Ratio: ratified 5 : 6 : 20 ≈ 1 : 1 : 4. Measured 4 : 17 : 16 ≈ 1 : 4.25 : 4.**

⚠ **THE MIDDLE NUMBER IS THE WHOLE POINT AND IT IS FOUR TIMES TOO BIG.** Rule 39
says in as many words that DOM order alone is not enough — *"the helper must
READ as attached to the input above it, never to the label below it, and a 3/3/9
rhythm destroys that even with correct markup"*. Here the helper is **17px** from
its own input and the next field's label is **16px** from the field above it:
**the two gaps are within a pixel of each other**, which is precisely the
reading failure the rule was ratified to prevent. Only the helper's own 13px
`margin-bottom` keeps it visually on the right side of the line.

**The cause is one line and it is deliberate:** `07-frontend/src/styles/global.css`
restores `p { margin-block: 1em }` (2026-08-20, CR-018 phase 5 — *"84 `<p>`
elements in this product have no margin rule of their own, and without this
their text runs together"*). Screen-level portal code writes `m-0` by hand; **the
KIT does not** — 8 of the 11 `<p>` elements in `primitives.tsx` have no `m-0`.
And because the margin is `1em` it is **a different number at every font size**:
13px on `FormField`'s `text-base` helper, **15px** on `ErrandCard`'s `text-body`
hint. **No fixed spacing scale can contain a rule expressed in `em`**, so rule 39
cannot be met anywhere the kit's own `<p>` appears until that is settled.
Filed as **`DEF-CWP-4845`**, with the empty-hint half it also causes.

### 6.3 Other anchors seen in passing

* `.input` is anchored at `6×10, min-height 36`. The portal's own `SelectInput`
  measures **`padding: 8px 12px`, `min-height: auto`** — a different control from
  the staff app's `.input`, and the anchor does not say which one it governs.
* `ErrandCard` is `p-4` with `gap-2`; the empty hint `<p>` inside it contributes
  **30px** of margin and zero content.

---

## 7 · WIDTHS

`document.documentElement.scrollWidth === window.innerWidth` on **all seven
screens, at 390 and at 1280, in all three data variants**. Nothing scrolls
sideways. The KPI row, the two-column `TwoCol` and the errand grid all stack to
one column at 390, and both tables swap to a card list (`max-md:flex`).

**The one thing that does not survive the phone is the chart's axis** (33-o):
twelve month labels in 350px truncate to `Jan Feb M… Apr M… Jun Jul A… Sep Oct
N… D…`. The bars, the legend and the estimate note are all fine. Recorded rather
than filed, because what a twelve-month axis should do at 390 — fewer ticks,
rotated labels, or a shorter default window — is a design decision and not a
repair.

---

## 8 · WHAT THIS LANE FILED

| Id | Severity | One line |
|---|---|---|
| `DEF-CWP-4845` | medium | the kit's `<p>` margins make B14 rule 39's field anatomy unbuildable, and print a 30px empty band on `/ask` |
| `DEF-CWP-4846` | medium | a failed read on the three usage screens takes the title, the screen id and the only door out with it |
| `DEF-CWP-4847` | low | five KPI tiles into a four-column row |
| `DEF-CWP-4848` | medium | `CWP-037` never draws `size_class`, and the equipment name stutters |
| `DEF-CWP-4849` | low | three drawn states on `CWP-034`/`CWP-037` are short of the drawing |
| `DEF-CWP-4850` | low | the blueprint says `/ask` and `/ask-a-question` are one screen; the router serves two |

**And three rows that should MOVE rather than stay open:** `DEF-CWP-4169` and
`DEF-CWP-4685` are fixed on screen; `DEF-CWP-4510` is fixed in code. This lane
did not close them — it changes no product code and no other lane's row.
