# CR-085 — The customer portal, redesigned from sixty wireframes: eleven waves, and the rule that was written and then applied to a third of the screens

**Status:** ALL ELEVEN WAVES LANDED · **shipped through `2.232.0`** · ⚠ **THEN RE-READ AGAINST THE BLUEPRINT IN TWO STEPS ON 2026-09-11 AND FIXED ACROSS EIGHT LANES — `2.236.0` and `2.237.0`, see §5** · the record below is the
CR as it was raised, then everything that happened after it.
**Moved into its own file 2026-09-08**, under the PO ruling that opens the register —
*"one file per CR from here"* — because the row had reached 4,955 characters on a single
line and the eleven waves would not fit in it. **The original cell is reproduced verbatim
in §1; nothing was rewritten in the move.**

---

## 0 · WHY THIS CR WAS REOPENED

> *"CR 85 was wrriten before , I believe we did not capture all the changes can you look at
> this document now and update the CR 85 again"*

It was right. The CR was written when the doors and the bars had landed and the screens had
not, and its own status line still read *"(c) SCREENS — next, in journey order."* **Eleven
waves have since landed and none of them was recorded here.** Re-reading the wireframes as a
blueprint then turned up three findings the CR never carried at all — §3.

---

## 1 · THE CR AS IT WAS RAISED, VERBATIM

Reproduced exactly as it stood in `11-change-requests.md`, so the move loses nothing and the
record of what was known **at the time** is still readable:

**THE CUSTOMER PORTAL, REDESIGNED FROM SIXTY WIREFRAMES — AND FOUR DOORS THAT DO NOT EXIST.** PO verbatim, 2026-09-08, after reviewing every screen: *"now start development - doors first, then the bars - please create a CR - please create all tasks and start the development - based on Customer portal wireframes"*. ⚠ **WHAT IS REVERSED IS NOT A SIGNED RULE — IT IS SIXTY SCREENS' WORTH OF LAYOUT DECISIONS THAT WERE NEVER WRITTEN DOWN**, plus four navigation facts that are simply wrong. `CR-068` built the portal (75 screens, 50 routes, 92 components, 37,664 lines) and every screen was signed off individually; **nothing signed says how they relate to each other**, which is why the heading bar differs on every screen and four screens cannot be reached at all. **THE FOUR DOOR DEFECTS ARE THE URGENT HALF AND ARE NOT COSMETIC:** `DEF-CWP-4654` — `/stop-or-restart` has **zero inbound links anywhere in the portal**, so a customer cannot stop service, which is one of the commonest reasons anybody opens a utility portal; `DEF-CWP-4655` — `/visit/:slug` likewise, so the locations list shows three addresses and opens none of them; `DEF-CWP-4652` — Past due has no door from Home, which is the screen a customer in difficulty lands on; ~~`DEF-CWP-4656` — the sign-in screen offers no way to create a sign-in~~ **WITHDRAWN 2026-09-08, marked `invalid`: `/sign-in` renders `FrontDoorView`, the SAME component the landing page renders, and it carries the enrol link at `FrontDoor.tsx:124`. The row named its own refutation — its `surface` field cites that very line while its title says the screen has none. The audit grepped for the screen's FILE and for links TO it and never asked what `SignInPage` actually RENDERS; four guest screens are thin wrappers around a shared view, so the file that owns a route is not the file that draws it.** **All four were found by the PO asking where a screen is reached from, and none of them is catchable by anything that exists**: each screen is routed, rendered and tested, and every test passes because a screen is tested at its own address — the one place a door is not needed. **WHAT MOVES, IN THE PO'S ORDER.** *(a)* **Doors first** — the four defects above, plus `DEF-CWP-4653` (budget billing reachable only through *Help paying*, a mainstream product behind a hardship screen). *(b)* **Then the bars** — two heading bars and exactly two, guest and signed-in, identical on all 50 screens: menu in the header row where a menu lives, and the account line beneath it carrying name, service address, account number and the amount due, because that is not navigation but the answer to *whose account am I looking at*. *(c)* **Then the screens**, in the journey order of the wireframes, each walked in a browser before it is called done. **WHAT IT COSTS.** The doors are a day and unblock two whole flows. The bars touch every screen and are mechanical, so the visual consistency the PO asked for lands in one pass rather than sixty. The screens are a run of sessions, not one, and that was said plainly rather than reported at 80%. ⚠ **AND ONE THIRD OF THE WIREFRAMES CANNOT BE BUILT AS DRAWN, WHICH IS STATED HERE RATHER THAN DISCOVERED LATER: 57 sentences in the portal's own wording say a figure is not there yet.** Where a drawn panel depends on one of those — *why it costs this*, *where your budget billing stands*, *reaches 3 plans / 75 accounts* — the shape is built and the content is not, and **no plausible number is invented to fill it**, which is the failure that put `{{low}} to {{high}} {{unit}}` in front of a customer this week. Which of those 57 to close is a scoping decision for the PO, not a design one. **NO ❄️ FROZEN B4/B5 FIGURE IS TOUCHED, CHECKED RATHER THAN ASSUMED** — this is navigation and layout; `04-money-math-rules.md` and `05-golden-tests.md` contain no screen vocabulary, `GT-1`..`GT-61` price no layout, and nothing here changes what any bill says or costs. **ROLLBACK:** each door is one link and reverts alone; the bars are one shared component and revert as one commit; every screen reverts independently because none of them changes a read. **Status: (a) DOORS DONE — `2.232.0`, commit `2fde39e6`; four real defects fixed and a route-reachability guard added (49 routes, two red at the pristine tip, both real). (b) BARS DONE — commit `67334768`; the account line moves out of the crowded header row into its own row under the menu, drawn by the FRAME so *consistent across every signed-in screen* is structural rather than fifty screens remembering. Walked in a browser on ten screens: same text, same y, wraps instead of clipping at 390px. The GUEST bar already was one shared component (`GuestFrame`) and needed no change — checked rather than assumed. (c) SCREENS — next, in journey order.** Wireframes: the 60-screen artifact, whose every screen now carries a *How you get here* row naming its real inbound links, read from source rather than assumed.

---

## 2 · WHAT ACTUALLY LANDED — ELEVEN WAVES, EACH WITH WHAT IT FOUND

Every wave was walked in a browser before it was called done, at 1280 and at 390. The
finding column is what the wave found that no test, no gate and no review had caught —
because that is the part worth keeping.

| Wave | Commit | What it found |
|---|---|---|
| **Doors** | `2fde39e6` · `299274fb` | **Four screens a customer could not reach**, and a route-reachability guard so it cannot recur. One filed defect was WITHDRAWN as invalid on evidence — `/sign-in` renders the same component as the landing page and carries the enrol link at `FrontDoor.tsx:124`; the register row named its own refutation in its `surface` field. |
| **Bars** | `67334768` · `eb3b3a1a` | The account line moved out of the crowded header into its own row, drawn by the FRAME so *consistent on every signed-in screen* is structural rather than fifty screens remembering. The GUEST bar already was one shared component and needed no change — checked rather than assumed. |
| **A · the guest entrance** | `be0e1f32` | The emergency number, the missing doors, and the phone. |
| **B · guest errands** | `fb84216b` | **The times on Track were wrong by five hours** — a report made at 09:40 read 04:40. |
| **C · start and stop service** | `1a95f31c` | **Every stop request was being refused.** |
| **D · home and accounts** | `632c77d6` | Who this is, before any money. |
| **E · bills** | `a2aa63cf` | A phone-shaped list, and **the bill that never said what to pay**. |
| **F · paying** | `e83971d5` | **A phone could not see whether a payment went through.** |
| **G · when money is tight** | `5fb49b4d` | **Past due had no Pay button at all** — the wireframe promises three ways out and the screen offered two, neither of them the obvious one. A link reading *"Something is holding this"* said the opposite of the truth on an ordinary account. **"Level pay" appeared in eight customer-facing messages** though it is our internal name. And nothing said what budget billing does NOT do — now *"This spreads your bills — it does not lower them."* |
| **H · usage and equipment** | `7daff01d` | **A summary reading "Monthly average 800" that never said of what**, between an electricity chart in kWh and a water chart in thousands of gallons. One service at a time now. **A test that could never fail** was found here: a case named *"no comparison is offered against nothing"* looked for an attribute that has never existed in the product, so it passed whether the screen was right or wrong. |
| **I · requests and your details** | `a678768d` | **Every signed-in page overflowed a phone** — the menu measured 461px inside a 390px window and could not wrap. **"What we have told you" printed over nothing** on every request ever raised, and the customer's own message was in the data and on no screen. *"Saved on 1 accounts."* in all eleven languages. And a utility with no text messaging still offered a text-reminder switch. |

**Every wave carried its wording into all eleven catalogues**, written natively rather than
translated. The portal suite grew from 789 to **864 tests across 69 files**, green, with
`tsc` clean at every landing.

---

## 3 · WHAT THE CR DID NOT CAPTURE, FOUND BY RE-READING THE WIREFRAMES AS A BLUEPRINT

Three findings, none of which is in §1, and the first is the one that matters.

### 3.1 · The rule this CR produced was applied to a third of the screens

The doors audit produced a rule, and §1 states it: *"Every screen's spec now carries a `How
you get here` row naming its real inbound links, read from the source rather than assumed."*

**Twenty-three of the sixty do. Thirty-seven name no door at all.**

That is not a drawing problem. **The rule was written because nine back-links turned out to
be fiction and two whole flows had no door**, and it was then applied to 38% of the screens —
so the same audit could find the same class of fault again on any of the other 37. The
route-reachability guard this CR added checks that a registered route is linked from
somewhere; it does not check that a screen's own document says where from.

### 3.2 · Every route label in the wireframes omits the tenant segment — 81 of them

The document draws `/bills`, `/pay-now`, `/usage`. `App.tsx` mounts `portal/*` under the
tenant root — PO ruling R11, *"/{utility-name}/portal/…"* — so the real address is
`/:tenant/portal/bills`. **Not one of the 81 carried it.** Corrected in the blueprint, with
the old value printed under each screen. It is a documentation defect rather than a product
one, and it is exactly the failure the wireframe grammar warns about: a route inferred from a
screen name is a guess, and the router is the fact.

### 3.3 · The wireframes state no product absences at all

§1 says *"57 sentences in the portal's own wording say a figure is not there yet"*, and that
count came from the PRODUCT. Scanning all 78 sections of the wireframe document itself for a
sentence saying something does not exist returns **zero** in any spec row or note.

**Re-counted from the product on 2026-09-08 the figure is 80**, of which **12 hold a control
a customer can see and cannot use**: card payments, autopay drafts, fee payment, downloads on
two screens, sending a meter reading, and three errand cards reading *"Not online yet — ring
us."* The 57 and the 80 are two different scans, not a drift — but the honest figure today is
80, and the twelve held controls are the half that costs a support call.

The blueprint resolves all of them: **24 specifications and 9 out-of-scope rulings**, in the
`CPB-` namespace, proposed and never allocated.

### 3.4 · Two statements in §1 have since become false, and are corrected here rather than deleted

* ~~*"`/stop-or-restart` has zero inbound links anywhere in the portal"*~~ → **ANSWERED.**
  `YourAccount.tsx` links to it. Fixed by this CR's own doors wave, `DEF-CWP-4654`.
* ~~*"`/visit/:slug` likewise"*~~ → **ANSWERED.** `CentresPage.tsx` links each centre to it.
  `DEF-CWP-4655`.

Both were true when written. A struck line with the answer under it teaches; a deleted line
invites the same finding again.

---

## 4 · WHAT IS STILL OPEN

| # | What | Why it is not decided |
|---|---|---|
| **1** | **`/ask` versus `/ask-a-question`** | The wireframes make them one screen. `/ask` today is a different LIVE page — the six-card guest errand list — and it is that page's only address and its only door from the guest menu. Repointing it deletes a shipped screen. **A PO decision, not a design one.** |
| **2** | **The 37 screens naming no door** | `CPB-23`. Mechanical to fix and nobody has scheduled it. |
| **3** | **The five standards blocks render A · B · E · D · C** | Reported and deliberately NOT re-sorted: the document refers to them by letter, so moving them changes what every existing reference points at. **A decision, not a repair.** |
| **4** | **Which of the 24 specifications to build** | A scoping decision. The blueprint states what each one would let a person do, so they can be picked by outcome rather than by size. |

---

## 5 · VERSION

Shipped through **`2.232.0`**. The doors wave cut it; every wave after rode it, because the
`<change>` digit moves at merge time and not in a lane's own branch — PO ruling 2026-08-26.

⚠ **AND THE TWO-STEP RE-READ OF 2026-09-11 SHIPPED THROUGH `2.237.0`, IN TWO CUTS.**
The eleven waves above built the screens; the PO then asked for the whole portal to be
read against the blueprint in **two steps — identify everything, then fix it** — and
that produced two releases rather than one:

| version | what it carried |
|---|---|
| **`2.236.0`** | the shared frame wave: the page head drawn on every branch, and the two new pay screens BUILT |
| **`2.237.0`** | the eight fix lanes, **and the two pay addresses switched on** |

**`2.236.0` shipped the two pay screens unreachable and said so in its own changelog
entry.** `portalRoutes.tsx` and `screenIds.ts` are one file each with four lanes in the
portal at once, so no lane may add a route (law 11); the lane that built the screens
reported the exact six lines and the merge lane added them in `6f4701b34`. **A screen
built in one release and switched on in the next is a hold with a clock in it** — hard-won
law 2's own failure shape — which is why the release note carried the warning rather than
leaving it to be discovered.

**Step 1 produced 22 conformance documents and 65 defects with no duplicate ids; step 2
closed roughly 60 of them across eight lanes.** What each lane left open, and why, is in
its own conformance file under `04-docs/05-modules/15-portal/conformance/`.

---

## 6 · ROLLBACK, RESTATED NOW THAT EVERYTHING HAS LANDED

**Each door is one link and reverts alone.** **The bars are one shared component and revert
as one commit.** **Every screen reverts independently, because not one of the eleven waves
changed a read** — the whole of this CR is layout, wording and navigation on top of reads
that already existed.

**Nothing is refunded and no issued bill changes.** No ❄️ FROZEN B4/B5 figure was touched,
checked rather than assumed at the time and again now: `04-money-math-rules.md` and
`05-golden-tests.md` contain no screen vocabulary, and `GT-1`..`GT-61` price no layout.

**The one thing that does not revert with a commit** is the wording: eleven catalogues gained
keys across eleven waves, and a revert of a screen leaves its keys behind. That is harmless —
an unused key renders nothing — and it is named here so nobody treats a leftover key as a
live promise.


---

## 5 · THE BLUEPRINT'S SPECIFICATIONS — WAVE 2, *what a customer is trying to find out*

§4 row 4 asked *"which of the 24 specifications to build"* and called it a
scoping decision. Wave 2 took six of them, cut by what a customer is trying to
DO rather than by screen: **what they used, what it cost, and what is installed
at their address.** Five landed; the sixth is named below with its reason.

| Spec | What a customer can now find out that they could not before |
|---|---|
| **`CPB-07`** | *How does this month compare with last month?* — **"The same as Jul 2026"** on the live demo, or **"5.00% less than Jul 2026"** where it moved. The arithmetic is `metering.monthly_usage`, which the staff Usage tab reads too, so a clerk sees the same figure |
| **`CPB-06`** | *How does it compare with the same month last year?* — **"86 gal more than Aug 2025"**, or **"No Aug 2025 to compare with."**, which names the month we are missing where the old blanket sentence named nothing |
| **`CPB-08`** | *Why does it cost this?* — **"500 kWh at $0.1100 = $55.00"** and **"300 kWh at $0.1350 = $40.50"**, total **$95.50**, from bill `BL-2608-000052`. Every figure is the bill's own; **nothing on this path prices anything**, which is what keeps it clear of B4 |
| **`CPB-09`** | *When is somebody coming to read the meter?* — **"Next read: Sep 14 · in 6 days"** |
| **`CPB-10`** | *Whose is this, and what am I paying for it?* — **Ours** / **Yours** and **No charge** / the bill's own monthly rate, with one sentence defining the two words |
| ~~`CPB-04`~~ | **NOT IN THIS WAVE, deliberately** — see below |

### 5.1 · Three faults found that no test could have

* **`DEF-MET-4684` — `CWP-033`'s *NEXT READING DUE* tile has never rendered for
  anybody, on any tenant.** The read asks for a window with `read_on IS NULL`
  and the only `ReadWindow` writer in the product sets `read_on` at creation, so
  an OPEN window is unreachable **by construction**. Nothing caught it because
  `None` is ALSO the right answer on a quiet day — the dead lookup and the quiet
  day are the same output. Now derived from the route's cycle schedule.
* **`DEF-CWP-4685` — and the tile woke up broken.** Its first render printed
  `2026-09-14–2026-09-14` in the big KPI font over three lines. Its test was
  green on `toContain("09")`, which an ISO date satisfies either way.
* **`CPB-08`'s join answered `None` on every account in the product** while every
  unit test passed, because the fixtures were shapes the lane invented rather
  than shapes a bill produces. Found by running it over live data.

### 5.2 · One correction to the blueprint itself

**The blueprint draws ONE charge line and this product bills TWO.** Ana's July
electric is a tiered tariff — `500 kWh at $0.1100` **and** `300 kWh at $0.1350`.
Serving only the first, as drawn, would have shown a customer **$55.00** for a
month that cost **$95.50** and called it an explanation. `CPB-08`'s panel serves
every line the bill wrote plus the bill's own total. **The bill's shape decides
the panel's shape.**

### 5.3 · Why `CPB-04` is not here

*"A customer can send us a meter reading"* is not a specification, it is a wave:
it is `US-CWP-042` (already scoped as **wave 3**), an unbuilt screen `CWP-035`,
`BR-CWP-074`'s accept-then-validate path with two flags, a **fourth value on
B2's signed `meter_source`**, two GAP columns on `meter_reads`, and the one
portal switch that is OFF for a new tenant. It is a **WRITE into the billing
chain**, where `apps/portal/api.py` already records that *"a WRITE with no screen
is worse: it is a route into billing nobody clicked."* Its hold on `CWP-034` is
honest and — checked rather than assumed — **its expiry test asserts both the
address and the screen id**, so the day `CWP-035` lands the suite goes red and
names the control still refusing over it. Decision log, 2026-09-08.

---

## 6 · THE BLUEPRINT'S SPECIFICATIONS — WAVE 3, *"I need a copy of something"*

§4 row 4 asked *"which of the 24 specifications to build"*. Wave 3 took the four
the wave-cut decision sets aside as **documents** and judged itself by one job:
*a customer needs a copy of a bill, a year of bills, a receipt or a plan
agreement, and can get it.*

⚠ **THE FOUR IDS HAD TO BE DEFINED BEFORE THEY COULD BE BUILT.** The `CPB-`
series is proposed and never allocated (§4), the blueprint is not in this
repository, and a full-text search of the tree returns `CPB-14`, `15`, `19` and
`20` **once** — in the sentence that sets them aside. Each was derived by
walking the screen it belongs to, and the derivation and its evidence are
written out in the decision log of 2026-09-08 rather than left to be inferred.

| Spec | What a customer can now do that they could not before |
|---|---|
| **`CPB-14`** | *Take a copy of ANY document we sent — not only a bill.* `CWP-031` listed receipts and letters, named them, dated them and refused to hand any of them over with the words *"We kept no copy of this."*, **which is false about every one whose copy we did keep**. On the live demo the receipt now answers **62 bytes beginning `%PDF`**, named `PMT-2608-W3KEPT.pdf`. `CWP-043`'s SIGNED plan agreement comes with it — the twin of the hold `CPB-03` released one screen over and left standing here |
| **`CPB-15`** | *Take a year of them in one go.* `Download a year ↓` was held with *"Downloads are not ready yet"* over a store that has served the bill PDF since `US-CWP-034`. It answers a **5,835-byte** archive carrying **4 of the 5** documents listed, each frozen file byte for byte — no merge, no cover page, nothing composed (`BR-CWP-045`) |
| **`CPB-19`** | *Press "view my bill" and never meet a server error.* Two faults, both of them two reads disagreeing — see below |
| **`CPB-20`** | *Take the receipt from the screen you are already on.* `CWP-041` carried ONE held button under the table, *"Receipts arrive later this year"*, which could not have said WHICH receipt even if it had worked. It is a row control now, on the desk table and on the phone card, addressed by the payment's own `PMT-` number |

### 6.1 · Four faults found that no test could have

* **`DEF-CWP-4658` — the screen said we still had the file while the download
  refused it.** `…/document` answered `available: true` and `…/document.pdf`
  answered **409** for the same bill in the same second. **It was already
  filed** — by the test written for `DEF-CWP-4657`, which asserted the wrong
  answer on purpose so that it would go RED the day somebody fixed it. It did,
  and that red is what closed the row. Hard-won law 2's mirror clause working
  exactly as written.
* **`DEF-CWP-4699` — a bill whose stored bytes no longer match reached the
  customer as a raw 500.** `ContentHashMismatch` was left uncaught **on
  purpose**, in three files, to keep `BR-NOT-027`'s distinction between *missing*
  and *tampered*. The distinction is right; nobody had measured where the raise
  came out. There is a third verdict now, with its own sentence.
* **`DEF-CWP-4697` — a refusal that was simply not true.** The row control's
  condition was written for a bill with no kept copy and applied to every
  receipt and every letter. Its own test asserted the control was HELD, so the
  assertion agreed with the defect; **no gate here asks whether a refusal is
  TRUE**, only whether it is present, which is `G103`'s own stated blind spot.
* **`DEF-CWP-4698` — the Documents test could not tell a working link from a
  broken one.** It mounted the screen inside a bare `MemoryRouter` with no
  matching route, so `useParams().tenant` was `undefined`. Harmless only while
  the screen built no address; the moment it built one every `href` would have
  come out `/api//portal/…`.

### 6.2 · Three `unwatched` holds retired, and the shape that replaced them

`portal.documents.downloadHeld`, `portal.money.receiptHeld` and
`portal.yourPlan.agreementHeld` were all `unwatched` in `holds.ts` — the kind
`G103` says in as many words it cannot see — and every one of them had been true
when written and false since `US-CWP-034` shipped a file-serving route on the
portal edge. Each is replaced by a refusal of kind **`fact`**, answered by the
store on every draw.

**A refusal about THIS ACCOUNT cannot rot; a refusal about the WORLD can.** That
is the durable part of this wave, and it is worth more than the four downloads.

### 6.3 · What wave 3 did NOT build, and why

* **`CWP-032`, the final bill, was not touched.** The 41 words the audit counted
  are its EMPTY STATE, on an account that is not leaving; the screen behind it
  is 250 lines and already opens `/bills/{number}/document`.
* **`CWP-004`'s guest receipt stays held** — a guest payment freezes no
  document, and the guest receipt is `CPB-01`, which is wave 1's and has not
  landed.
* **The CSV export stays held and is honest** — nothing in this product writes a
  customer CSV.

---

## 7 · THE BLUEPRINT'S SPECIFICATIONS — WAVE 4, *"I asked you for something; what is happening with it?"*

§4 row 4 asked *"which of the 24 specifications to build"*. Wave 4 took the four
the wave-cut decision sets aside as **requests** and **the dispute**, and judged
itself by one job: *a customer raises a request, can find it afterwards, can see
what is happening to it, and can question a bill knowing what they are
questioning.*

⚠ **THE FOUR IDS HAD TO BE DEFINED BEFORE THEY COULD BE BUILT, AGAIN.** As with
wave 3: the `CPB-` series is proposed and never allocated (§4), the blueprint is
not in this repository, and a full-text search returns `CPB-05`, `11`, `12` and
`13` **once** — in the sentence that sets them aside. Each was derived by walking
the screen it belongs to against the register rows that already describe those
screens' faults, and **the derivation, its evidence and the admission that the
NUMBER-to-outcome assignment is this lane's** are written out in the decision log
of 2026-09-08 rather than left to be inferred.

| Spec | What a customer can now do that they could not before |
|---|---|
| **`CPB-05`** | *Read their own request in their own terms.* Ana's list printed **271 characters** of a clerk's worklist sentence — *"Queried through the customer portal bill BL-2608-000044 (2026-07-01 to 2026-07-31, 843.36 USD): … **Their reason:** …"*, two ISO dates and herself in the third person. It reads **`A bill you queried — BL-2608-000044`** now, and what she actually typed is kept as her own entry on the thread |
| **`CPB-11`** | *Find a request that is finished.* A query she raised and withdrew left `open_requests` **empty** with the row still on file — no list, no link, no way back to the reference we had given her. A **Still open / All of them** switch appears the day a request finishes and is absent until then |
| **`CPB-12`** | *See what is happening to it.* Every request in the product was headed *"Track your request"*. It is headed **`SR-26-0011` / *A bill you queried — BL-2607-000003*** with **`Raised 09/08/2026`** under it, and the ladder says ***through this website*** and ***We are waiting for: …*** rather than a date alone |
| **`CPB-13`** | *Question a bill and see the money.* **The one screen where a customer disputes money never stated the money** — walked at 1280 and 390, not one figure on either step. It reads **`You are querying bill BL-2608-000044, $843.36.`**, the check-and-send row is **`BL-2608-000044 · $843.36`** with its period, the consequence box moved into the commit's own column, and step 2 has a `Back` |

### 7.1 · Five faults found that no test could have, and one is this wave's own

* **`DEF-CWP-4708` — `CWP-051` printed the clerk's sentence in the thread under
  *You*.** `DEF-CWP-4198`'s `surface` field names ONE file, `Requests.tsx`, and
  the same string was rendered in a second place the register never mentions.
  **Found by walking this wave's own fix**, and only because the fix made it
  visible: the customer's own words appeared BESIDE the clerk sentence, the same
  claim twice. **When a defect names a surface, grep for the FIELD, not for the
  screen.**
* **`DEF-CWP-6442` — a withdrawn request ticks every step of the ladder.**
  `progress_steps` marks every step before the current one *done*, and a
  terminal state indexes to the last, so a request the customer withdrew from
  `submitted` draws *We picked it up · We need something from you · We decide ·
  We are on it* all ticked. **It was unreachable before this wave**, because the
  hub filtered terminal states out and `CWP-051`'s only door was that hub. Not
  fixed here: it is a change to the shared six-step projection and needs its own
  eleven-state matrix.
* **`DEF-CWP-4709` — the list and the detail kept two catalogues for the same
  eleven states and they disagreed.** `submitted` read *With us* in the list and
  *Sent* on the page, `approved` *Agreed* then *Approved*. A customer clicking a
  row watched the state of their own request change words on the way in. G15
  compares key SETS across languages; nothing compares two namespaces.
* **`DEF-CWP-4706` — the list's state map held SEVEN of the eleven states**, so a
  withdrawn request would have read *With us*. Unreachable by construction until
  `CPB-11` widened the read — hard-won law 7's *structurally incapable of
  failing* in its quietest form: not a broken check, an absent case.
* **`DEF-CWP-4707` — `CWP-051`'s own test mounted the screen with no
  `/:tenant/portal` route**, so every address it builds came out `//portal/…`.
  The same shape `DEF-CWP-4698` recorded on the Documents screen one wave
  earlier, in a file where the one assertion that could catch it could not be
  written.

### 7.2 · One correction to the delta file, and it is the same shape as wave 3's

**Row 55.3 asks for a sentence the product cannot say.** *"A disputed reading is
marked on the reading itself"* is true EVENTUALLY — `OQ-CWP-1681` is OPEN and
what ships is option (a), *a clerk raises the marker after reading the request*
— and printing it at the moment a customer presses send is hard-won law 1 on a
customer's money. **That is exactly what row 55.5 one line down already says
about the collection hold. Two rows of that table describe the same unbuildable
class and only one of them was marked.** Corrected in place.

### 7.3 · What wave 4 did NOT build, and why

* **`CPB-16` and `CPB-17` were not approached at all.** §4 item 1 records that
  `/ask` versus `/ask-a-question` is an OPEN question the Product Owner has not
  ruled on, and the wave cut puts those two specifications in no wave for that
  reason. `DEF-CWP-4202` covers **two** screens and only the `CWP-055` half was
  built: rows **54.1, 54.3 and 54.4 stay open** and are named here so they are
  not read as missed. Nothing was added, removed or repointed on either address.
* **Delta row 51.3** — *Add a note* and *Withdraw* as head actions. Pure layout
  with a real regression surface on two live controls; the head naming the
  request and the ladder saying what happened were judged worth more.
* **`All requests →` as a second SCREEN.** `08-screen-layouts.md` allocates no
  `CWP-###` for it and `G82` refuses a route whose id nobody issued. A switch
  delivers the outcome and invents nothing; the day that id is allocated, the
  switch becomes a link and the read behind it does not change.

### 6.2 · WAVE 3 STATUS — **DONE**, verified by a second lane · `2.234.0` (build) · `2.234.3` (verification and fix)

The building lane pushed and the container restarted before it could report, so
everything in §6 above was on the branch **unverified**. A second lane rebuilt a
Pine Hill and a document store from nothing and walked it. Recorded here because
a wave that nobody confirmed is not a wave that landed.

**Confirmed working, measured:** the receipt hands over **62 bytes of PDF** named
`PMT-2608-W3KEPT.pdf`; `Download a year ↓` answers a **6,038-byte** archive
carrying **5 of the 6** documents listed, with the shortfall on the response
rather than quietly in the file; `CWP-031`, `CWP-041`, `CWP-032`, `CWP-043` and
`CWP-029` all draw at **1280px and 390px with 0px overflow**, no unresolved
catalogue key on screen and **no 5xx response anywhere in the walk**. Backend
suites 30/30, `tsc` clean, the portal front-end suite **69 files / 937 tests**.

**Both `CPB-19` faults confirmed fixed by running the old code against the same
database**, so the only variable is the code: `DEF-CWP-4658`'s `available: true`
over a file the server refuses is now `available: false` /
`document_not_stored`, and `DEF-CWP-4699`'s **500 `SYS-INTERNAL`** is now
**409 `portal.document.notTrusted`**.

⚠ **THE TWO 500s THIS WAVE WAS HANDED WERE NOT A FAULT.** `BL-2608-000052` is on
`AC-2026-00013` and `BL-2607-000001` on `AC-2026-00001`; the login they were
reported against holds `AC-2026-00004`. **404 is the correct answer** and
`BR-CWP-010` is doing its job.

⚠ **ONE CONTROL IN §6 ABOVE HAD NEVER BEEN PRESSED WHEN IT WAS WRITTEN.**
`CWP-043`'s *↓ Agreement* is listed under `CPB-14`, and the walkthrough proving
the wave printed *"SKIPPED: this login holds no live plan"* on every run and then
GREEN — the demo customer has no plan, so the skip could never stop being one.
It is walked now: the fixture plants a live plan (**`$172.20` = `$40.00` +
5 × `$22.03` + `$22.05`**, `US-CWP-052` §7's own invariant), the control is
followed rather than counted, and the step **refuses** where it skipped.

⚠ **AND THE WHOLE FRONT END OF THIS WAVE IS IN TWO OTHER LANES' COMMITS.** The
building lane's two commits carry backend files only; `85486fee` (a CR-089
metering commit) carries all eleven front-end files and `84834a4a` (a DEF-MET
row) carries both render checks and this section. Nothing was lost — every
law-11 check passes on both — but this wave's front end has never been reviewed
under its own name and `2.234.0` is recorded against CR-089. The full account is
in the decision log of 2026-09-08; no history rewrite is proposed.

**Also fixed in `2.234.3`:** `DEF-CWP-4705` — `CWP-041`'s *See what this paid*
was refused with *"No receipt for this row."*, a sentence about a different
document, beside a receipt that on those rows is a live download. It reads
*"No single bill to open."* now, in all eleven catalogues.

**Filed, not fixed:** `DEF-CWP-4711` (`G107` red on four portal screens, unread,
with a baseline line that matches nothing) and `DEF-CWP-4712` (wave 4 added a
second eslint error to an already-red `G98`). Both are other lanes' live files.

**Review:** the §6 row is `PENDING`, and a **second row** was added because that
one lists `plan_agreement_current` among its files while its plain-English
statement never mentions a payment plan — a signature covers only what was shown.
