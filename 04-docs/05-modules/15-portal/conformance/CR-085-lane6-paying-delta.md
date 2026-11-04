# CR-085 · step 1 · lane 6 — PAYING · WHAT IS BUILT, AGAINST THE DRAWING

**IDENTIFY ONLY. Not one line of product code was changed by this lane.**

**Read `CR-085-lane6-paying-drawing.md` first** — it carries the drawing quoted
verbatim, and §0 of it reconciles the blueprint's addresses with the router's.

**Walked:** 2026-09-11, worktree detached at `b4063d1e6`, against the shared stack
at `http://127.0.0.1:8401`, tenant `brazosbend`, **at 1280 AND 390, every screen,
both widths**, with `playwright-core` resolved from `07-frontend`. Three passes:
the seven routes; then the states; then a `getComputedStyle` measurement pass.
Raw output, per-screen text dumps and full-page screenshots are in the lane's
scratchpad (`lane6/walk2.log`, `walk3.log`, `out/`, `out2/`).

## ⚠ HOW THE SCREENS WERE FED, SAID PLAINLY BEFORE ANY FINDING IS READ

**The shared stack's only tenant has ONE account, NO portal credential and NO
bills.** Measured, not assumed: `select count(*) from accounts` with
`app.tenant_id` set answers **1**, of which **0** are `is_sample`; `portal_credential`
holds **0 rows**. So there is no signed-in portal session to be had on it and the
guest bill lookup has nothing to find.

**Nothing was seeded and nothing was restarted** — seven sibling lanes are on this
stack. Instead every `/api/**/portal/**` read was **fulfilled inside the browser**
by `page.route`, from fixtures shaped by the client's own TypeScript types
(`payNowClient.ts`, `portalClient.ts`, `methodsApi.ts`, `guestClient.ts`). The
front-page read was left to pass through to the real server and did.

**What that proves and what it cannot.** It proves everything about RENDERED
OUTPUT — the real bundle, the real CSS, the real components, at both widths, in
every state — which is the only thing no gate in this repo reads. It proves
**nothing** about the server's half of any contract. Wherever a finding below
could be an artefact of my own fixture, it says so and it was checked against the
selector; two candidate findings were **withdrawn** that way and are recorded in
§7 rather than deleted.

---

## 1 · THE SEVEN ROUTES, AND WHICH DRAWING EACH ANSWERS

| route | screen id | blueprint screen | verdict |
|---|---|---|---|
| `/pay` | `CWP-002` | **06** *Pay without signing in* | built, guest, **two steps on one screen** |
| `/pay/check` | `CWP-003` | (no blueprint screen — the guest check step) | built, guest |
| `/pay/done` | `CWP-004` | **07** *Your payment · without an account · done* | built, guest |
| `/pay-now` | `CWP-038` | **35 + 36 + 37** *Pay now · Check before you pay · Payment made* | built, signed in, **all three drawings collapsed into one screen** |
| `/payments` | `CWP-041` | **38** *Payments* | built |
| `/payment-methods` | `CWP-039` | **39** *Payment methods* | built |
| `/autopay` | `CWP-040` | **40** *Autopay* | built |

**All seven render. None shows a holding screen. No JS error on any screen at
either width. No page scrolls sideways at 390.** Money renders at **two decimals
everywhere** (hard rule 2 / `R-16`) — scanned for `$n.nnn+` on every state of
every screen, **zero hits**. **No uuid and no internal id reaches the glass**
(rule 31 / `R-12`) — scanned likewise, zero hits.

---

## 2 · `L6-38.A` — THE STRUCTURAL DIVERGENCE, AND IT IS THE BIGGEST THING IN SECTION 06

**The blueprint gives a signed-in customer three screens; the product gives one.**

| blueprint | product |
|---|---|
| **35** choose — how much, from where, **and what it costs** | `/pay-now` step 1+2, one card |
| **36** *Check before you pay* — *"The last screen at which anything can be changed"*, its own address, the total re-read deliberately | **does not exist.** `/pay/check` is the GUEST screen |
| **37** *Payment made* — a receipt page with download, email, balance-after and the disconnection panel | an **in-place panel** that replaces the form; no address, no download, no email |

**This is not filed as a defect.** `08-screen-layouts.md` numbers `CWP-038` as one
screen and the product is built to that; the three-step **stepper** inside
`/pay-now` is that decision rendered. It is recorded because it is the fact that
makes every row in §3 below read differently, and because the blueprint's own
argument for splitting 35 from 36 — *"the pay screen is a form; this is a
confirmation… the total, the fee and the date are read once, deliberately, rather
than glanced at while choosing a card"* — is a product decision that nobody has
ruled on since the blueprint was drawn.

---

## 3 · `/pay-now` · `CWP-038` — against blueprint 35 · 36 · 37

**What is there, in order, at 1280 and at 390 (identical content, stacked):**
stepper `✓ How much · 2 How you are paying · 3 Confirm` → `AMOUNT` (three radios)
→ `HOW YOU ARE PAYING` (method radios) → `WHAT THIS WILL DO` (four bullets) →
`Pay $191.00 ✓` + `Back` → rail `WHERE IT WILL GO` (BILL · OWING · PAYING · LEFT
OWING) + `You are paying $191.00` + *"Payments settle the oldest bill first."* +
a `TESTING` panel when the tenant is in sandbox.

| # | kind | finding |
|---|---|---|
| **L6-38.1** | **CONTROL · filed `DEF-CWP-4866`** | ⚠ **THE PAY BUTTON IS DISABLED AND THE REASON IS INVISIBLE — CONFIRMED IN A BROWSER, AND THE CAUSE IS IN THE KIT.** `CommitButton` renders a refusal **only as `title=`**. Measured on `/pay`: the disabled control carries `title="Fill in both boxes first."`, `aria-label` **null**, `aria-describedby` **null**, and the sentence appears **nowhere in the page text**. On `/pay-now` with `held_reason` `no_payment_provider_connected` and again with `account_is_cash_only`, the whole rendered body was captured and contains no refusal at all. A `title` tooltip needs a mouse and a second of hover: on the phone the PO named as the primary case it does not exist. **`HeldButton`, in the same file, renders the identical kind of sentence as a visible `<span>`** — so one screen (`/autopay`) says *We cannot draft payments yet* out loud while the screen that takes the money says nothing. **This is the standing cause of `DEF-CWP-4152`, which is therefore STILL TRUE as a user-visible fact.** Blueprint 35 is explicit that the button *"is the last thing read before money moves"*; `CR-068` R3 and `BR-CWP-056` both require *visible, disabled, **carrying its reason*** |
| **L6-38.2** | **COPY · filed `DEF-CWP-4867`** | ⚠ **`WHAT THIS WILL DO` GOES ON PROMISING THE PAYMENT OVER A DEAD BUTTON.** With `can_pay: false` the box still read *"Takes $191.00 from Bank account ····4417. Clears bill BL-2608-0141 in full. Emails you a receipt."* It is drawn on `panel !== null` alone and never asks whether the payment can happen. With L6-38.1 the screen reads: a confident promise, a dead button, and no explanation |
| **L6-38.3** | **CONTROL · filed `DEF-CWP-4868`** | ⚠ **A DECLINED OR REFUSED PAYMENT IS A DEAD END — ZERO CONTROLS ON THE SCREEN.** Measured: `declined` → `controls: []`; `refused` → `controls: []`. The screen says *"No money was taken. **Try another card or bank account.**"* and offers no way to do either — no `Back`, no retry, no door to `/payment-methods`. `Try again` is rendered for `no_answer` **only**. Blueprint 35's DECLINED state: *"Says the bank declined it and what to try; **the amount and method stay selected**."* This is `DEF-CWP-3972`'s shape — a refusal naming an action that is unreachable from where the person is standing — on the outcome a real processor will produce most often |
| **L6-38.4** | **DATA · filed `DEF-CWP-4869`** | ⚠ **THE COMMIT STAYS LIVE WHILE THE PRICED PANEL DESCRIBES A DIFFERENT PAYMENT.** Typing into *Another amount* changes the button label immediately (it is computed locally: `formatMoney(amount)`), while `panel` keeps the PREVIOUS preview — the effect never clears it — and `ready = … && panel !== null` stays true. Observed on screen simultaneously: button `Pay $40.00 ✓`, `WHAT THIS WILL DO` *"Takes $191.00 … Clears bill BL-2608-0141 in full"*, rail `PAYING $191.00 / LEFT OWING $0.00`, total `You are paying $191.00`. The window is at least `PRICE_AFTER_MS` (250 ms) plus a round trip, every time. ⚠ **The file's own docstring says *"NOT ONE FIGURE ON THIS SCREEN IS COMPUTED HERE"* and the button label is the exception.** ⚠ **And the commit carries the PREVIOUS amount's `idempotency_key`**, which is the one string hard rule 6 makes load-bearing |
| **L6-38.5** | **STRUCTURE** | **THERE IS NO FEE ANYWHERE ON THIS SCREEN.** Blueprint 35 draws `WHAT YOU WILL PAY / Your bill $191.00 / Card fee $0.00 / Total $191.00`, a `NO FEE` badge on the bank row, `+$2.95 fee` on the card row, and says of itself *"**The fee must be visible before the button, not after**"* and *"The fee is a line in the total, not a footnote."* Built: no fee line, no per-method badge, no total panel. **Honest rather than missing** — `PortalCardFee.priced` is `false` for every tenant because pricing a surcharge needs a processor's fee schedule and there is no processor (`OQ-1394`) — but the customer is told nothing here at all; the stance is stated one screen away on `/payment-methods`. **Recorded, not filed: it becomes a defect the day a processor lands** |
| **L6-38.6** | **STRUCTURE** | **THE PAST-DUE AMOUNT OPTION IS ABSENT.** Blueprint 35 desktop draws three amount radios — *The full amount due* · **_The past-due part only_** · *Another amount*. Built draws *Everything you owe* · *Just bill `BL-…`* · *Another amount*. `PortalPayNow` carries no past-due figure, so this needs a served field |
| **L6-38.7** | **COPY** | **`Just bill BL-2608-0141` puts a bill NUMBER where the drawing puts a MONTH** (*"Just the August bill"*) — `13-wireframe-delta.md` row `38.7`, **confirmed still open**. Likewise `38.6` (money **bold** inside each option) — still open, and its two-line hunk in `primitives.tsx` is still unclaimed |
| **L6-38.8** | **STRUCTURE** | **No page head** — no kicker, no title. Delta `38.11`/`38.13` already argue this both ways; the BLUEPRINT settles it in favour of a head: screen 35 draws `‹ Payments` over `Pay your bill`. Confirmed absent |
| **L6-38.9** | **STRUCTURE** | **The receipt half of blueprint 37 is absent from the paid panel:** no `↓ Download receipt`, no `↗ Email it to me`, no *"A copy is in Payments whenever you need it."*, no balance-after in words, no `Set up autopay so this is automatic`, and **no disconnection panel** (*"Your disconnection notice is cancelled"* / *"$56.30 is still past due — the notice stands until Aug 20"*), which the drawing calls *the question the customer came in with*. What IS there: `Reference PMT-2608-0311`, `Amount paid`, the lands-on table, `See it on your payments` |
| **L6-38.10** | **COPY** | Title reads *Thank you — that is paid*; blueprint 37's WORDS block says ***"Payment made", not "Transaction complete"***. Both plain; recorded as a wording divergence, not a defect |
| **L6-38.11** | **STATE** | **NOTHING DUE draws an empty form with a `$0.00` button.** Blueprint 35: *"You have nothing to pay right now." Offers to pay ahead rather than showing an empty form.* Observed: `Everything you owe — $0.00` as a live radio and `Pay $0.00 ✓` disabled and silent (L6-38.1 again) |
| **L6-38.12** | **STATE** | ✅ **PROCESSING · idempotent.** Two simultaneous presses produced **one** commit call, measured. The label becomes `Working…`; the drawing asks for *"Taking your payment…"* — a wording divergence only |
| **L6-38.13** | **STATE** | ✅ **CARD EXPIRED is flagged on the method before they press** — the row renders *"Visa ····8102 · This card has expired."* Blueprint 35's CARD EXPIRED state is MET |
| **L6-38.14** | **STATE** | ✅ **NO SAVED METHOD** pre-selects *A different card or bank account* and draws a live `Add a card or bank account` door to `CWP-039`. `DEF-CWP-3972`'s fix confirmed still in place |
| **L6-38.15** | **CONTROL** | `38.14` (the drawing lists the BANK first and pre-selects it; live pre-selects whichever instrument is first `selectable`) — **confirmed still open**: with both instruments selectable the bank was first and pre-selected in this fixture, so the ORDER fault is fixture-dependent and is not re-confirmed here. `38.8` (a green `VERIFIED` **chip** on the bank row) — **confirmed still open**: it renders as the inline text `· Verified` |

---

## 4 · `/payments` · `CWP-041` — against blueprint 38

**What is there:** head `PAYMENTS / What you have paid` + `Download CSV` (held,
*"Downloads arrive later this year"*, visible) → toolbar `Search payments…` ·
`WHICH PAYMENTS: All | This year` → table `DATE ⇅ · HOW · REFERENCE · APPLIED TO ·
AMOUNT ⇅ · STATUS · ACTIONS` → pager `1–4 of 4 · Page 1 of 1 · Rows per page
50/100/200/500/1000` → eight errand cards.

| # | kind | finding |
|---|---|---|
| **L6-41.1** | **STRUCTURE** | **The columns are not the drawing's, in name or in order.** Blueprint 38: `DATE · AMOUNT · PAID FROM · WENT AGAINST · STATUS`. Built: `DATE · HOW · REFERENCE · APPLIED TO · AMOUNT · STATUS · ACTIONS`. **`AMOUNT` has moved from second to fifth** — on a list whose whole job is *"did my payment go through"* the figure is now the fifth thing read. `REFERENCE` is an extra column the drawing does not have (and is a good one — it is the cheque number a customer finds in their own bank statement) |
| **L6-41.2** | **STRUCTURE** | **No twelve-month total.** Blueprint draws the sub-line ***"3 payments · $536.14 in the last 12 months"***; built shows the shared caption and a pager count |
| **L6-41.3** | **STRUCTURE** | **No retention sentence.** Blueprint's footer reads ***"↓ Download all as a spreadsheet · Payments are kept for seven years"***. The download is there (held); the seven years are not. Note `CPB-15` asks for exactly this sentence on `CWP-060` — so the fact exists as a commitment, on another screen |
| **L6-41.4** | **STRUCTURE** | **A `Rows per page 50 / 100 / 200 / 500 / 1000` control on a customer's payment list.** That is staff-table furniture; the drawing has a plain pager. Recorded for the frame/list lane rather than filed here, since it is `PortalListTable`'s and reaches every portal list |
| **L6-41.5** | **—** | ✅ **`DEF-CWP-4705` IS FIXED.** *See what this paid* is refused with *"No single bill to open."*, not with a sentence about a receipt. `portal.money.noReceipt` is retired from all eleven catalogues |
| **L6-41.6** | **—** | ✅ **Delta row `41.11` IS FIXED.** The receipt is a **row icon** now, not a loose button under the table, with all three states: present · disabled with *"We kept no copy of this."* · **absent** on rows that mint no payment number. Both row icons carry `title` **and** `aria-label` (*Download this receipt* · *See what this paid*), so `R-01` — *every icon carries its word* — is met by accessible name |
| **L6-41.7** | **—** | ✅ **PENDING · RETURNED · NONE YET all render.** `processing` → `PROCESSING`; a bounced reversal renders `—` for HOW and REFERENCE and *"Returned by the bank"* in the applied-to cell over a red `BOUNCED` chip; empty → *"Your payments will appear here."* over the eight errand cards. ⚠ **REFUNDED was not seen** — no `refunded` value exists in the served `state` union, so blueprint 38's REFUNDED state has no input in this build |
| **L6-41.8** | **FORMAT** | ✅ Dates render in the tenant's own `MM/DD/YYYY` (`08/13/2026`). `DEF-CWP-4197`'s family is clean on this screen |

---

## 5 · `/payment-methods` · `CWP-039` — against blueprint 39

**What is there:** head `PAYMENTS / Cards and bank accounts` + `Add a method`
(brand primary, 141px, beside the title) → `SAVED METHODS` table `METHOD · ADDED ·
USED FOR · STATUS · ACTION` → the token notice → rail `AUTOPAY` (standing sentence
+ `Set up autopay`, held) and `CARD FEES`.

| # | kind | finding |
|---|---|---|
| **L6-39.1** | **COPY · filed `DEF-CWP-4873`** | ⚠ **`1 bounced payments block autopay.`** — a plural noun after `1`, on screen, reproduced with `bounces: 1`. `13-wireframe-delta.md` row `39.7` records it and no defect row ever carried it; **confirmed still live** |
| **L6-39.2** | **STRUCTURE** | **No per-method fee.** Blueprint 39 puts `NO FEE` on the bank row and `+$2.95 a payment` on the card row and says why: *"The fee sits on the method, so choosing later on the pay screen needs no memory."* Built states one tenant-level stance in a `CARD FEES` rail panel with no figure. Same root as `L6-38.5` — `card_fee.priced` is false for everybody |
| **L6-39.3** | **STRUCTURE** | **No `BEFORE YOU REMOVE ONE` panel.** Blueprint: *"Your bank account is the one autopay uses. Removing it turns autopay off, and your bill would need paying by hand."* The `USED FOR` column does say `Autopay`, which carries half the fact |
| **L6-39.4** | **STATE** | **EXPIRED does not say autopay will fail.** With `status: "expired"` the row renders an `EXPIRED` chip and the `AUTOPAY` panel goes on citing the bounce count. Blueprint 39: *"Red, **and autopay says it will fail** — stated here rather than discovered on the due date."* There is also no `EXPIRING SOON` amber at 60 days — the served type has `expires` but nothing derives a warning window |
| **L6-39.5** | **CONTROL** | **`REMOVING THE LAST ONE` could not be reached.** The drawing refuses it *"with the reason if autopay is on; offers to turn autopay off first."* `removePaymentMethod` answers a `reason` code and the catalogue has no key for that case — `portal.methods.refused.*` is `code_needed · wrong · expired · locked · not_a_reference · unknown`, so this refusal would land on `unknown` = *"That did not work."* **Recorded as a gap, not filed**: whether the server ever produces it is a server question this lane could not reach |
| **L6-39.6** | **—** | ✅ **`Add a method` is a brand primary beside the title** — delta `39.2` confirmed still fixed, 141px. ✅ **`BR-CWP-057` holds**: no run of five or more digits anywhere in the DOM. ✅ Row icons carry `title` and `aria-label` (`Edit` held with *"Changing one is not ready."*, `Remove`) |
| **L6-39.7** | **STATE** | ✅ `NONE ON FILE` reads *"Save a card and it appears here."* with one button and no empty table — blueprint's NONE ON FILE met. ✅ The step-up (`CONFIRM IT IS YOU` · *"This is the one thing that changes where your money goes, so we send a fresh code first."* · `Code sent to ••• ••• 0144`) renders, and `BR-CWP-040` is visible to the customer as a reason |

---

## 6 · `/autopay` · `CWP-040` — against blueprint 40

**What is there:** head `PAYMENTS / Autopay` → the standing sentence → `Take it
from` (a 175px link to `/payment-methods` inside a 701px card) · `How much` ·
`When` → `WHAT HAPPENS` (three bullets) → `Turn autopay on|off` (held, **reason
visible**) → rail `NEXT FEW` table `DATE · EXPECTED · STATUS`.

| # | kind | finding |
|---|---|---|
| **L6-40.1** | **FORMAT · filed `DEF-CWP-4870`** | ⚠ **`NEXT FEW` PRINTS A RAW ISO DATE TO A CUSTOMER — `2026-08-22`** — on the one screen that tells somebody WHEN money will leave their account, while `/payments` two clicks away renders `08/13/2026` and `/payment-methods` renders `06/02/2026`. It is `DEF-CWP-4197`'s family exactly, on a screen that was not in that grep — the fourth occurrence, and `DEF-CWP-4131`'s own prevention note says *"grep every sibling screen that renders the same KIND of value"* |
| **L6-40.2** | **COPY · filed `DEF-CWP-4871`** | ⚠ **THE `How much` HELPER OFFERS A CEILING THE SCREEN DOES NOT HAVE.** It reads *"Or set a ceiling and we will ring you above it."* There is no ceiling control on the screen, and `PortalAutopay.ceiling`'s own type comment reads *"⚠ Always `null`: `accounts` has no column for a ceiling."* Blueprint 40 draws `Never take more than ▾` as a real setting with its own helper; the product has neither, and its copy says it does. Hard-won law 1 in customer-facing prose |
| **L6-40.3** | **DATA** | **`WHAT HAPPENS` says *"We email you three days before."*; the blueprint says ***five*** (twice — phone and desktop).** ⚠ **B14 rule 37 makes a wireframe figure an illustration, so this is NOT automatically a defect** — but one of the two numbers is the one a customer will hold us to, and nothing in the repo states which. **Raised for a ruling, not filed** |
| **L6-40.4** | **STRUCTURE** | **Two of the blueprint's three trust promises are absent:** *"You can turn it off at any time, including after the email"* (and it is currently contradicted — the off control is held) and *"A disputed amount is never taken"*. The blueprint calls these *"the three objections to autopay, answered on the screen where the decision is made"* |
| **L6-40.5** | **STRUCTURE** | **None of blueprint 40's four SETTINGS is settable.** `Take` · `When` · `From` · `Never take more than` are drawn as four selects; built, `How much` and `When` are static text with helpers and `Take it from` is a link away. **Honest** — `getAutopay` has no write and `BR-PAY-015` records an intent rather than a mandate — and `When`'s helper says so out loud (*"Always the due date. It cannot be changed."*). Recorded so the divergence is not read as drift |
| **L6-40.6** | **STATE** | **The OFF state draws an empty `NEXT FEW` table — headers over nothing, with only the footnote beneath.** Blueprint's OFF state: *"Explains what it would do with the customer's real figures, then one button."* B14 rule 17 wants an empty state that says what fills it |
| **L6-40.7** | **—** | ✅ **`DEF-CWP-4683` IS NOW HALF FIXED AND SHOULD BE RE-STATUSED.** Its title is *"The autopay screen never says whether autopay is ON, and offers no way to stop it"*. It **does** say so now — *"Autopay is on. We take each bill on its due date."* / *"Autopay is off for this account."* / the stopped sentence — and a `Turn autopay off` control exists, **held with a visible reason** *"Ring us to stop autopay"* pending `OQ-CWP-1568`. The remaining half is the ruling, not the screen |
| **L6-40.8** | **—** | ✅ **`DEF-CWP-4133` IS FIXED.** *Take it from* measures **175px inside a 701px card** — the exact figures the delta's row `40.4` records. ✅ Delta `40.3` re-confirmed: `Turn autopay on` is held with *"We cannot draft payments yet"*, five words, **visible** |
| **L6-40.9** | **COPY** | Title reads `Autopay`. Wireframe `P26` writes *Pay automatically each month* (delta `40.1`); **the blueprint agrees with the product** and it is the newer drawing (8 Sep). **Delta row `40.1` should be closed as answered by the blueprint** rather than left as an open copy fault |

---

## 7 · `/pay` · `/pay/check` · `/pay/done` — `CWP-002/003/004`, against blueprint 06 · 07

| # | kind | finding |
|---|---|---|
| **L6-02.1** | ⛔ **DO NOT BUILD** | **Blueprint 06's *WHAT THE FOUND BILL SHOWS* — seven facts including account number, name, service address and bill period — CONTRADICTS `BR-CWP-019`, WHICH IS CONFIRMED**, and blueprint 06's own *WHAT IT MUST NOT EXPOSE* block contradicts it two paragraphs later. Built shows five: bill number, masked name, status, owing, due. **That is right.** Same for blueprint 07's `Account 4417-0092 / Balance now / Past due / Against … August 2026 bill`. Building either would put a stranger's address and account number behind a bill number taken off a doormat. Same conflict as `13-wireframe-delta.md` row `3.2` |
| **L6-02.2** | **STATE** | **Four of blueprint 06's five states have no input in this build.** `NO MATCH` ✅ renders (*"We cannot find that bill."*, one sentence for the pair). `ALREADY PAID` renders as *Paid in full* + *"There is nothing to pay on this bill."* — but **not** the drawing's *"This bill was paid on Aug 19."* and **not** its *"Offers to pay the account's current balance instead"*, which leaves a customer holding a stale bill at a dead end. `NEWER BILL EXISTS`, `PAST DUE` and `CLOSED ACCOUNT` **do not exist at all** — `BillLookupView` has no field for any of them (and each would need weighing against `BR-CWP-019` first) |
| **L6-02.3** | **—** | ✅ `replaced` renders *"Pay BL-2609-0155 instead — it replaced this one."* ✅ `cancelled` renders correctly **in the screen** — `DEF-CWP-4196` is about no endpoint being able to produce it, and that half stands |
| **L6-04.1** | **STRUCTURE** | **Blueprint 07 makes the reference *"the loudest thing after the amount"* with `WRITE THIS DOWN` above it and *"Your reference. You have no account to look this up in, so keep it."* beneath.** Built renders `Reference PAY-26-08841` as a plain `KVList` row, the same weight as `Against` and `Paid with`. The whole argument of screen 07 is that a guest has nowhere to come back to |
| **L6-04.2** | **—** | ✅ **`DEF-CWP-4197` IS FIXED ON BOTH GUEST SCREENS.** `/pay/check` renders `Due 08/22/2026`; `/pay/done` rendered `Paid 08/13/2026 09:41` from a fixture of `2026-08-13T14:41:00.123456+00:00` — i.e. converted to `America/Chicago` and formatted in the tenant's own pattern. ✅ `↓ Receipt` is held with a **visible** reason (`HeldButton`), and `Set up a login →` is a live link |
| **L6-04.3** | **—** | ✅ `/pay/done` opened with no router state (the refresh case) draws *"We cannot show that receipt here"* with two doors — `Look it up →` and `Find my bill →`. That is `CPB-22` stated honestly on the screen |
| **L6-03.1** | **STRUCTURE** | `/pay/check` renders the four facts, the three card fields, `WHEN YOU PRESS PAY` and the commit. **`L6-38.1` applies here too**: before the card boxes are filled, `Pay $191.00 ✓` is disabled with `title="Fill in the card boxes first."` and nothing on screen |

### ⚠ TWO CANDIDATE FINDINGS WITHDRAWN — recorded rather than deleted

1. *"A settled bill shows `Owing $191.00` beside `Paid in full`."* **Withdrawn.**
   That was **my fixture**. `selectors.bill_lookup` computes
   `payable = Decimal("0") if state in (CANCELLED, REPLACED) else still_owed`,
   and `still_owed <= 0` is what makes a bill `settled` — so the server cannot
   produce it. Checked at the source before reporting.
2. *"The row-action icons have no accessible name."* **Withdrawn.** My first
   selector queried before the table had rendered. Re-measured: every row icon on
   `/payments` and `/payment-methods` carries both `title` and `aria-label`.

---

## 8 · B14 RULE 39 — MEASURED, NOT ESTIMATED

`getComputedStyle` on the running app, 1280 and 390, on `/pay` (two fields) and on
`/payment-methods`'s add-a-method form (two fields). **The portal has exactly one
form primitive pair — `FormField` + `TextInput` in `portal/components/primitives.tsx`
— so one measurement covers every form on this journey.**

| rule 39 anchor | ratified | measured | |
|---|---|---|---|
| `.input` padding | **6 × 10** | **8 × 12** (`py-2 px-3`) | ✗ |
| `.input` min-height | **36** | **0** — rendered height **41** | ✗ |
| label → input | **5px** | **4px** (`gap-1`) | ≈ |
| **input → helper** | **6px** | **17px** (4px gap **+ 13px** paragraph margin) | ✗ **4× over** |
| field → field | **20px** | **12px** on `/pay`, **16px** on the add form | ✗ |
| the ratio | **≈ 1 : 1 : 4** | **4 : 17 : 12 ≈ 1 : 4.3 : 3** | ✗ **inverted** |

⚠ **THE INVERSION IS THE MONEY-RELEVANT PART, AND IT IS THE EXACT FAILURE RULE 39
NAMES.** On `/pay`, *"Just the postcode, not the whole address."* sits **17px**
under the input it explains and its own block ends **12px** above the next block —
so the gap that should be the SMALL one is larger than the gap that should be the
LARGE one. Rule 39: *"the helper must READ as attached to the input above it,
never to the label below it, and a 3/3/9 rhythm destroys that even with correct
markup. That is why the three gaps are ratified as FIGURES and not as an
ordering."* The rhythm here is 4 / 17 / 12.

**The cause is named and it is one line:** `07-frontend/src/styles/global.css`
sets `p { margin-block: 1em }`, which at the helper's 13px font size is **13px**,
added on top of `FormField`'s `gap-1`. The helper's classes set no margin at all —
`text-base text-neutral-600` — so nothing in the component says what is happening
to it. **That is a stylesheet silently defeating the kit**, which is the class of
fault B14 rule 21 exists to prevent, and no test, `tsc` or gate can see it.

**Filed as `DEF-CWP-4872`.** Blast radius stated rather than guessed: `FormField`
is the portal's only field wrapper and every `<p>` in the app takes the same
margin, so a fix belongs to whoever owns the kit, not to this journey.

⚠ **AND RULE 39 CONTRADICTS ITSELF ONCE, WHICH IS WORTH SAYING BEFORE ANYBODY
BUILDS TO IT:** its scale reads *"`--sp-4` 16px **between fields**, between
blocks"* and its field anatomy reads *"field → field **20px**"*. Both are in the
same ratified cell. Not this lane's to resolve — raised.

---

## 9 · THE 24 SPECIFICATIONS — WHICH TOUCH THESE SEVEN SCREENS

| spec | screens it names | touches my routes | as built today |
|---|---|---|---|
| **`CPB-01`** A customer can pay by card | 35 · 36 · 37 · 6 · 8 | `/pay-now` `/pay` `/pay/check` `/pay/done` | **PART-BUILT.** The screens, the preview, the commit, the four outcomes and the receipt **all exist and were walked end to end**. What does not exist is a real acquirer: `apps/integrations/adapters/payments_sandbox.py` is the settlement behind the guest flow and `tokeniseCard` is a browser stand-in that drops the number on the floor. ⚠ **The spec's *waits on* line is now STALE IN ITS DETAIL** — it says *"Five separate pieces of copy say so"* and names *"We cannot take fees online yet"* and *"Online payment arrives later this year"*, which are other screens' words; on MY seven the live refusals are `portal.payNow.held.*` (six codes) and `portal.quickPay.*`. **What done looks like** — *"the receipt reads Paid $191.00 · Aug 14 · reference PMT-2608-0311 with the balance underneath reading $0.00"* — is **two-thirds true today**: the reference and the amount render, the **balance underneath does not** (`L6-38.9`) |
| **`CPB-02`** Autopay can actually draft a payment | 40 | `/autopay` | **NOT BUILT, and correctly held.** `Turn autopay on` is disabled with *"We cannot draft payments yet"*, visible. **What done looks like** — *"the Autopay screen reading 'Next: $191.00 on Aug 22'"* — the screen ALREADY draws that row when the server sends one; what is missing is upstream, `apps/billing/issue.py` never calling `record_intent_at_issue` (delta `40.6`) |
| **`CPB-17`** A signed-out visitor at a signed-in address is offered a sign-in | 53 · 54, and its own text says *"True of every signed-in screen, not just one"* | `/pay-now` `/payments` `/payment-methods` `/autopay` | **NOT BUILT on my four.** Each renders `FailedWithRetry` — *"We could not open this page… Download error report"* — when the session read fails. ⚠ **NOT RE-VERIFIED IN A BROWSER BY THIS LANE**, because the session read was stubbed to make the screens visible at all; read from `PayNowPage.tsx` / `PaymentsPage.tsx` / `MethodsPage.tsx` / `AutopayPage.tsx`, which are four copies of the same block. Said rather than claimed |
| **`CPB-20`** Delivery is confirmed, not just dispatch | 60 | `/payments` (the code cites `CR-085 CPB-20` on `PortalMoneyRow.receipt_available`) | **PART-BUILT on my screen.** `receipt_available` is the *did we keep a copy* fact and the row draws all three states. The spec's own screen is `CWP-060` |
| **`CPB-22`** A guest can see their own receipt again | 7 · 37 | `/pay/done` | **NOT BUILT, and stated on the screen.** Re-opening `/pay/done` without router state draws *"We cannot show that receipt here"* with two live doors. That is the absence declared rather than hidden |
| **`CPB-23`** Every screen carries its How-you-get-here row | all | all seven | **NOT BUILT.** Blueprint screens **36, 37 and 38** carry the red *"No door named"* callout; screens 06 and 07 carry it too. Five of my seven are among the 37 |
| **`CPB-24`** The two dead hold sentences are retired | 1 · 3 | — (adjacent) | ⚠ **HALF OF IT IS NO LONGER TRUE.** Measured today: `portal.held.card` now has **2 call sites** in the front end, so it is not dead; `portal.held.signIn` is still in all eleven catalogues with **0** call sites anywhere. The spec should be narrowed to one key |

**The other seventeen (`CPB-03`…`CPB-16`, `CPB-18`, `CPB-19`, `CPB-21`) name no
screen in this journey.**

---

## 10 · THE 12 UNRATIFIED `NO HOME` RULES — WHICH THIS JOURNEY LEANS ON

**Proposals, not law.** Verdicts below are observations against a proposal, and
none of them is a rule breach until somebody rules it in.

| rule | on my seven screens |
|---|---|
| ⚠ **`R-05` amount due and due date appear in the same place on every screen** | **NOT HELD.** `/pay` shows `Owing` + `Due` inside the found-bill block; `/pay/check` shows `Due` then `Owing`; `/pay-now` shows neither as a standing fact — the amount is inside a radio label and there is **no due date on the screen at all**; `/payments`, `/payment-methods` and `/autopay` show neither. The frame's account line carries the account, not the amount. ⚠ **`/pay-now` is the one to weigh:** a customer decides how much to pay with no due date in front of them |
| ⚠ **`R-07` one filled button per screen** | **HELD on six of seven, and the seventh is the interesting one.** Measured `data-variant="primary"` counts: `/pay` **1** (`Continue →`) — but once a bill is found it is **2** (`Continue →` and `Pay $191.00 ✓`), both filled, both live, on one screen. `/pay/check` 1 · `/pay/done` 0 · `/pay-now` 1 · `/payments` **0** · `/payment-methods` 1 · `/autopay` **0**. ⚠ **`/payments` and `/autopay` have NO filled button at all**, which is the rule's other edge |
| ⚠ **`R-09` never make a customer remember an account number to do something** | **HELD, and deliberately.** `/pay` asks for a BILL number and a postcode, both printed on the paper — the blueprint's own *IT STARTS WITH THE BILL NUMBER* argument, built. No screen in this journey asks for an account number. No account id appears in any address (`portalRoutes.tsx` records the reasoning) |
| `R-04` no emoji as a section marker | **HELD.** The blueprint draws 🏦 💳 🔒 on screens 35/37/39; the product uses none as a marker |
| `R-06` never ask a customer to compute | **HELD on `/pay-now`** — `LEFT OWING` is served, never subtracted in the browser. **NOT HELD on the fee**, which is simply absent (`L6-38.5`) |
| `R-10` bad news never appears without the way out beside it | **BREACHED on `/pay-now`** — `L6-38.3`, a declined payment with zero controls. This is the rule the blueprint calls *"the strongest rule on the page"* |
| `R-13` a route existing is not a door | **RELEVANT AND UNRESOLVED.** Blueprint 36, 37 and 38 name no door; `/pay/check` and `/pay/done` are reachable only by walking `/pay`, which is correct for a flow. `CPB-23` is where this belongs |
| `R-15` position, order and wording never move; a back-link sits under the bar | **Frame — LANE 1's.** Not assessed here |
| `R-18` assistance is a first-class path | **Not on these screens.** `/payments`' errand grid offers eight doors and none is help-paying; `/overdue` is another lane's |
| `R-19` the portal is a second channel | Not observable on these screens |
| `R-22` loading, empty and failed can never render as the same picture | **HELD.** `/pay-now` has three distinct cards (`pay-now-reading` · `pay-now-failed` · `pay-now`), and the file's own comment records why they carry three different test ids |
| `R-23` no sentence states a fact it does not derive | **BREACHED twice:** `L6-40.2` (a ceiling that does not exist) and `L6-38.2` (a promise over a dead button) |

---

## 11 · THE `DEF-CWP` SLICE, RE-VERIFIED — *"before citing a row here as current, open the screen"*

Of the 82 open/partially-fixed `DEF-CWP` rows, **fourteen** mention paying; **seven**
land on my seven routes. Every one below was opened in a browser today.

| row | register status | what the screen says today |
|---|---|---|
| `DEF-CWP-4152` Pay button disabled and says nothing | open | ⚠ **STILL TRUE, AND THE CAUSE IS NOW NAMED.** Not per-account and not a missing distinction — `CommitButton` renders every refusal as `title=` and nothing else. See `L6-38.1` / `DEF-CWP-4866` |
| `DEF-CWP-4683` autopay never says whether it is on, no way to stop | open | ⚠ **HALF FIXED — re-status to partially-fixed.** The state IS said and a held `Turn autopay off` exists with a visible reason. The remaining half is `OQ-CWP-1568` |
| `DEF-CWP-4133` autopay's *Take it from* is a full-width bar | open | ✅ **FIXED.** Measured 175px inside a 701px card |
| `DEF-CWP-4705` *See what this paid* refused with a receipt sentence | open | ✅ **FIXED.** Reads *"No single bill to open."*; the wrong key is retired |
| `DEF-CWP-4197` raw UTC instant on the guest receipt | open | ✅ **FIXED on the two guest screens** — `08/13/2026 09:41`, tenant time zone and format. ⚠ **BUT THE FAMILY IS NOT CLOSED: `/autopay` still prints `2026-08-22`** (`L6-40.1` / `DEF-CWP-4870`) |
| `DEF-CWP-4196` the guest lookup's `cancelled` branch is unreachable | open | **STILL OPEN as written** (no endpoint voids a bill). ⚠ **The SCREEN half is proved good** — stubbed to `cancelled`, `/pay` renders *Cancelled* + *"There is nothing to pay on this bill."* correctly |
| `DEF-CWP-3943` 36 dead catalogue keys, 22 of them the portal's | partially-fixed | ⚠ **THE PORTAL COUNT IS AT LEAST TWO SHORT ON THIS JOURNEY.** Re-scanned my five key groups (284 keys) against every non-test source file **and** the backend's `message_key`s: three are dead, and only one of the three (`portal.quickPay.payHeld`) is in the row. The other two are **`portal.money.printRow`** (*Print this receipt*) and **`portal.quickPay.receiptEmailHint`** (*Optional. We use it only for this receipt.*, orphaned when delta `3.3` removed the email box). ⚠ **Three keys I first read as dead are ALIVE** — `cannotPayHere`, `notOffered`, `surchargeNotPriced` are served by the backend as `message_key`s, which a front-end-only grep cannot see. Corrected before reporting |
| `DEF-CWP-4377` no password field can be read back | open | **NOT ON MY SCREENS** (sign-in and enrol). ⚠ Recorded because the fix landed in `TextInput`, which IS my screens' primitive: a reveal button now ships with every `type="password"` field, so the row looks fixed from this side |
| `DEF-CWP-4143` · `4181` · `4131` · `4168` · `4172` · `4187` | open | **Other lanes' screens** (`/overdue`, `/plan`, `/money-back`, `/usage`, `/readings`, `holds.ts`). Not re-verified here |

---

## 12 · WHAT THIS LANE COULD NOT SEE

* **The server's half of every contract.** Every portal read was stubbed. Nothing
  here says whether a figure is right, only what a screen does with it.
* **`CPB-17` in a browser** — the session read had to be stubbed for the screens to
  render at all, so the signed-out-at-a-signed-in-address panel was read from four
  identical source blocks instead.
* **A real card charge.** No acquirer exists; the guest flow's sandbox settlement
  was not exercised against a live server.
* **A landlord.** One account in the fixture, so the account switcher never drew,
  and `13-wireframe-delta.md` row `41.12`'s per-account-scope question is untouched.
* **`REMOVING THE LAST ONE`, `EXPIRING SOON`, `REFUNDED`, `LAST ONE FAILED`** — four
  drawn states with no reachable input in this build.
* **Colour and tier by eye.** Screenshots were taken at both widths and are in the
  scratchpad; no colour claim is made from them.
* **The eight accessibility questions.** `R-01`'s accessible-name half was measured
  on every row icon and every disabled commit; a keyboard walk was not done.

---

## 13 · THE 390 PASS, SEPARATELY — BECAUSE IT IS THE WIDTH THE PO NAMED

A third walk at **390 only**, because *"A phone could not see whether a payment
went through"* is a finding from this CR's own history and a 1280 screenshot
cannot answer it.

| what | at 390 |
|---|---|
| **`/pay-now` PAID** | ✅ **A phone CAN see it.** *THANK YOU — THAT IS PAID* · chip `PAID` · *Keep this page or the reference below for your records.* · `Reference PMT-2608-0311` · `Amount paid $191.00` · the lands-on table · `See it on your payments`. **That finding is still fixed** |
| **`/pay/done` GUEST RECEIPT** | ✅ `PAID` · *$191.00 received, thank you* · Reference · **`Paid 08/13/2026 09:41`** (tenant time zone and format, from a `…T14:41:00.123456+00:00` fixture) · Against · Paid with · `↓ Receipt` and `✉ Email it to me` **both held with visible reasons** |
| **`/pay-now` DECLINED** | ⚠ **zero controls, at 390 as at 1280** (`DEF-CWP-4868`) |
| **`/pay-now` HELD, no provider** | ⚠ **the refusal is not in the page text** — measured, `false` — at the width where a tooltip cannot exist at all (`DEF-CWP-4866`) |
| **`/payments`** | ✅ the table **restacks into cards, amount first then the status chip**, which is exactly the blueprint's phone column. ⚠ **This corrects `L6-41.1`: the amount-is-fifth divergence is DESKTOP-ONLY** |
| **`/payments` toolbar** | ⚠ **filed `DEF-CWP-4879` — the search box and the `All \| This year` filter DO NOT EXIST at 390.** Measured: zero visible inputs, zero segment buttons, zero selects in `main`, against one of each at 1280 |
| **every screen** | ✅ **nothing scrolls sideways**, at any state, on any of the seven. ✅ **no JS error** on any screen at either width |

**Touch targets, measured and recorded rather than filed.** The kit's `sm`
buttons render **28px** tall on a phone — `Back`, `See it on your payments`,
`↓ Receipt`, `Find my bill →` — beside the commit's 35px. The skill's responsive
section asks for *"finger-sized, not mouse-sized"* and **no ratified figure
exists anywhere in B14**, so this is an observation with a number attached and
not a rule breach. It is the same `sm` size on every portal screen, so it belongs
to whoever owns the kit's two button sizes.

---

## 14 · THE NINE ROWS FILED, AND A NEAR-MISS WORTH RECORDING

| id | severity | screen | what |
|---|---|---|---|
| `DEF-CWP-4866` | high | the kit, through `CWP-038/002/003/039` | a `CommitButton` refusal is a `title=` tooltip and nothing else |
| `DEF-CWP-4867` | high | `CWP-038` | `WHAT THIS WILL DO` promises the payment over a dead button |
| `DEF-CWP-4868` | high | `CWP-038` | declined and refused render **zero** controls |
| `DEF-CWP-4869` | medium | `CWP-038` | the commit stays live while the priced panel is stale |
| `DEF-CWP-4870` | medium | `CWP-040` | `NEXT FEW` prints `2026-08-22`, a raw ISO date |
| `DEF-CWP-4871` | medium | `CWP-040` | the `How much` helper offers a ceiling that does not exist |
| `DEF-CWP-4872` | medium | the kit, every portal form | B14 rule 39: 4 / 17 / 12 against 5 / 6 / 20, and inverted |
| `DEF-CWP-4873` | low | `CWP-039` | *"1 bounced payments block autopay."* |
| `DEF-CWP-4879` | medium | `CWP-041` at 390 | the search box and the filter exist only when wide |

⚠ **THE FIRST EIGHT WERE ALLOCATED AS `4851`–`4859` AND EVERY ONE OF THOSE NUMBERS WAS
TAKEN BY A SIBLING BEFORE THIS LANE PUSHED.** `file_defect.py` allocates against
the remote and was right each time it ran; between the first call and the push,
sibling lanes pushed **fifteen** rows — `DEF-CWP-4851` … `DEF-CWP-4865` — so all
eight collided by NUMBER. Caught at push time by doing what CLAUDE.md law 11
prescribes and not by any check: **re-derive both the file content and the ids
from the pinned tip.** The register was rebuilt as *the tip's bytes plus my eight
rows, renumbered* — the first 5,200,438 bytes proved byte-identical to the tip,
`git diff --numstat` against the tip reads **8 insertions, 0 deletions**, and no
id appears twice in the whole 2,501-row file. **Nothing was lost and nothing was
published that was not mine; it is recorded because the allocator's own printed
line was accurate on every call and would still have produced eight duplicates.**
