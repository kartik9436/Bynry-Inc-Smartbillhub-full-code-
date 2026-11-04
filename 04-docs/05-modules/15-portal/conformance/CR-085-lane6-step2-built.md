# CR-085 · step 2 · lane 6 — PAYING · WHAT WAS BUILT

**Read `CR-085-lane6-paying-drawing.md` and `CR-085-lane6-paying-delta.md` first.**
Those two are step 1 — the drawing quoted, and what the product did against it.
This file is the FIX step: what changed, what was proved, and the four things
this lane deliberately did **not** do.

**Worktree** `cr085/lane6-paying`, detached at `56ddf02fa`. **Seven routes:**
`/pay` · `/pay/check` · `/pay/done` · `/pay-now` · `/payments` ·
`/payment-methods` · `/autopay`.

---

## 0 · THE ONE THING THIS LANE CANNOT FINISH ON ITS OWN

⚠ **THE TWO NEW ADDRESSES ARE NOT REGISTERED, AND THAT IS DELIBERATE.**
`07-frontend/src/portal/routing/portalRoutes.tsx` is off limits to every lane —
its own header records why: six routes were registered there ONCE, before four
lanes started, because two lanes committing one file means the second silently
reverts the first with a correct file count and its own hunks present
(hard-won law 11). The screens, their pages, their tests and their `CWP` ids are
all built and landed; **the four lines that mount them are the merge lane's**,
and they are written out verbatim in §6 below.

Until those four lines land, `/pay-now/check` and `/pay-now/done` answer the
router's fallback and the `Check this — $40.00 →` control on `CWP-038` leads
nowhere. **Nothing else in this lane depends on them.**

---

## 1 · THE BIG ONE — THE SIGNED-IN PAY FLOW IS THREE SCREENS

> PO 2026-09-11: ***"it should be 3 screens - confirmed"***
> PO 2026-09-11: ***"ii). Your ruling was about the shape, not the addresses."***

| blueprint | screen id | address | file |
|---|---|---|---|
| **35** `Pay now` | `CWP-038` | `/:tenant/portal/pay-now` | `payments/PayNow.tsx` |
| **36** `Check before you pay` | **`CWP-076`** | `/:tenant/portal/pay-now/check` | `payments/PayNowCheck.tsx` |
| **37** `Payment made` | **`CWP-077`** | `/:tenant/portal/pay-now/done` | `payments/PayNowDone.tsx` |

**The guest flow did not move.** `/pay`, `/pay/check` and `/pay/done` still serve
`QuickPay`, `QuickPayCheck` and `QuickPayDone`. ⚠ **The blueprint draws screens
35–37 at those three guest addresses and the guest screens at `/pay-now`. That
crossing is RULED and is recorded in the decision log of 2026-09-11 — a later
lane must not "correct" the router from the drawing.**

**`CWP-076` and `CWP-077` were allocated in `CR-068` §9** (the authority; PO
2026-09-03: *"You can assign number CWP-nnn - Assig all unqie numbers"*). §9's
heading moved from *seventy-five* to *seventy-seven* **in the same commit as the
rows** — the lesson CLAUDE.md's B14 rule-count line has recorded five times.
Their `blueprint` label column reads `P55`/`P56`, which continues the portal
series and names **no r10 frame**; §9 says so in as many words, because every
other label in that column does name one.

### What each screen is, and the three judgments inside the split

**`CWP-038` chooses.** Amount radios, method radios, the standing `WHERE IT WILL
GO` rail, and one control onward. It gained a **page head** (`‹ What you have
paid` over *Pay your bill*) — it had none at all, and blueprint 35 draws one.

⚠ **JUDGMENT 1 — THE BUTTON ON SCREEN 35 DOES NOT SAY *Pay*.** The drawing puts
`Pay $191.00` on 35 AND on 36. Once 36 exists, the first of those is a button
that says it takes money and does not. The drawing's own rule is kept — *"one
button, and it names the figure… never a bare Continue"* — so it reads
**`Check this — $191.00 →`**: the figure stays on the control and the verb is
what the control does. **The word *Pay* is now reserved for the one control in
this product that takes money.**

⚠ **JUDGMENT 2 — WHAT IS HANDED ON IS THE CHOICE, NEVER THE ANSWER.** Step one
hands `{ amount, instrumentId, idempotencyKey }` **in router state, never in the
address** (an amount and an instrument id in a URL reach access logs, history and
a `Referer` header; an instrument id in an address bar is a database id on
screen, B14 rule 31). `CWP-076` then **re-reads both** `GET pay-now` and
`POST pay-now/preview` before it draws a figure. That is the guest flow's own
discipline (`QuickPayCheck`: *"what step 1 hands on is the PAIR, not the
answer"*) and it is what makes blueprint 36's `AMOUNT CHANGED` state real.
**The idempotency key is PRESENTED, never re-minted** — the preview seam answers
`key or mint()`, so one string covers the re-price, the commit and every retry
(hard rule 6, `US-CWP-045` TC-7).

⚠ **JUDGMENT 3 — ONLY `paid` REACHES `CWP-077`, AND ITS PARSER IS WHAT ENFORCES
IT.** This is the trap the ruling named in the same breath: `/pay`'s route
comment records that *the lookup ships and the payment does not — no gateway
exists*, so **a screen called *Payment made* must not imply money moved on a
tenant with no gateway.** `paidResultFrom` reads any outcome but `paid` as NO
receipt at all and the screen draws its wrong-turn card; `declined`, `no_answer`
and `refused` all stay on `CWP-076`, where the ways out are. Three test cases,
one per outcome, and they were each proved red. **And a sandbox tenant's receipt
says so** — *"This utility is still testing. No real money moves."* — because a
sandbox tenant CAN answer `paid`.

---

## 2 · THE TWO RULES THE PO RATIFIED, APPLIED

### R-10 — *"the thing they can do about it must be on that same screen, next to the message"*

| where it was broken | what it does now |
|---|---|
| **A declined payment rendered ZERO controls** (`DEF-CWP-4868`; measured `controls: []` at 390 and 1280) | the outcome is drawn **on `CWP-076`, with the amount and the method still chosen** — blueprint 35's own DECLINED state — over a `RefusalStrip`, with `Use another card →` (to `/payment-methods`, asserted **by address**) and `Go back and change something` **inside the same block**, asserted by CONTAINMENT so a test cannot pass with them in a page head |
| **`Try again` was offered on every outcome** | it is offered on `no_answer` only. Re-trying the same declined card is the one thing that cannot work, and offering it is how a refusal starts naming an action that leads nowhere (`DEF-CWP-3972`'s lesson) |
| **A failed read on `CWP-038` was a card with a sentence and nothing else** | `PortalState kind="failed"` with **two ways out**: `Try again`, wired to a real re-read (not `EmptyList`'s `onCta: () => undefined`, `DEF-MET-4764`), and the payments list by address |

### R-22 — *"differntiate it using text message"*

Every state card on the three pay screens is lane 1's `PortalState`, with its
own sentence and its `data-portal-state` kind in the DOM:

* `CWP-038` — `loading` *Reading what you owe…* · `failed` *We could not read this. Please try again.*
* `CWP-076` — `loading` *Working out what you will pay…* · `failed` **“We could not check this. Nothing has been taken.”** · `empty` (the wrong turn) *This page needs the amount and the card you chose…*
* `CWP-077` — `empty` (the wrong turn) *This page only shows a payment you have just made. Your payments list has every one of them.*
* **`/payments` gained a THIRD sentence** — a search that matches nothing now says so instead of borrowing *"Your payments will appear here."*, which is the R-22 failure the ruling cites on two other screens.
* **`/autopay`'s empty `NEXT FEW`** was headers over nothing; it is a sentence now — *Nothing is scheduled yet. A payment appears here when a bill is issued.*

**30 new catalogue keys in all eleven languages** through
`10-scripts/i18n_fanin.py`, five retired, one re-worded. Every catalogue holds
**15,449**.

---

## 3 · THE NINE DEFECTS

| id | what it was | what closed it |
|---|---|---|
| `DEF-CWP-4866` | a `CommitButton` refusal is a `title=` tooltip and **nothing else** — `aria-label` null, `aria-describedby` null, the sentence nowhere in the page text, on the width where a tooltip cannot exist | **`portal/components/heldCommit.tsx`** — `HeldCommit` composes the kit's disabled `CommitButton` with `HeldButton`'s own visible `text-base text-neutral-500` sentence. Four call sites: `CWP-038`, `CWP-076`, `CWP-002`, `CWP-003`. ⚠ **THE KIT IS NOT FIXED AND THIS IS NOT THE FIX** — `primitives.tsx` belongs to one lane this wave (law 11), so `CommitButton` still says nothing on its own and **every other call site in the product still has this defect**. The row stays OPEN for the kit; the four paying screens are closed |
| `DEF-CWP-4867` | *WHAT THIS WILL DO* promised the payment over a dead button | the box is drawn on `panel !== null && screen.can_pay`. The PANEL still draws — `BR-CWP-058` is about telling somebody where their money would go, true whether or not we can take it — the PROMISE does not |
| `DEF-CWP-4868` | declined and refused rendered zero controls | §2 above |
| `DEF-CWP-4869` | the commit stayed live while the priced panel described another payment, carrying the **previous amount's idempotency key** | the panel is cleared the instant the amount moves, before the new price is asked for. ⚠ **The first version of this test passed against the bug** and was caught by mutating the code — see §5 |
| `DEF-CWP-4870` | `NEXT FEW` printed `2026-08-22`, a raw ISO date, on the one screen that says when money leaves a bank account | `usePortalDate()`, the published formatter. The server's string stays on `data-slot-on`; the customer reads `09/14/2026` |
| `DEF-CWP-4871` | the `How much` helper offered a ceiling the product cannot store | re-worded in eleven languages: *"Always the whole balance. There is no limit to set."* — the same shape as `whenHelper` beside it |
| `DEF-CWP-4872` | B14 rule 39: the portal's field anatomy at 4 / 17 / 12 against a ratified 5 / 6 / 20, inverted | **not this lane's, and it is already fixed** — lane 1 scoped `p { margin-block }` out of the portal and gave `FormField` two gaps. Re-measure it in a browser before closing the row |
| `DEF-CWP-4873` | *"1 bounced payments block autopay."* | plural forms (`_one`/`_other`) in eleven languages, and the bare key retired. ⚠ **AND THE SAME FAULT WAS FOUND ON `/autopay`** — `portal.autopay.held.cash_only` read *"1 payments bounced — cash only"* and was not in the row. Both are fixed; the row's title names only `/payment-methods`, so the sibling has its own row — **`DEF-CWP-4939`** |
| `DEF-CWP-4879` | on a phone the payments list had **no search and no filter** — both lived inside the table, which is inside `max-md:hidden`, so they were not hidden but absent | the toolbar is lifted above the width split and serves both halves from one needle. A search that matches nothing gets its own sentence |

⚠ **`DEF-CWP-4152` — *the Pay button is disabled and says nothing* — IS NOW TRUE
OF NO SCREEN ON THIS JOURNEY** and was the user-visible face of `DEF-CWP-4866`.
⚠ **`DEF-CWP-4683` should be re-statused to partially-fixed** — step 1 already
recorded why, and the remaining half is now an ENDPOINT rather than a ruling
(§4).

---

## 4 · `OQ-CWP-1568` CLOSED — AND THE CONTROL IT RELEASES IS STILL HELD

The question is CLOSED (2026-09-11): a signed-in customer **may** turn autopay
off. PO verbatim: ***"a). A customer who has to ring to accept a payment plan
often doesn't ring. These are the people you've twice told me to prioritise."***

**The control did not go live, and that is the honest answer rather than a
missed one.** Measured on 2026-09-11: `apps/portal/api.py` serves autopay as
`GET accounts/{id}/autopay` **and nothing else**, and `apps/portal/write_points.py`
has no row for it — a file that says in its own words that adding one *"is a
ruling and not an edit"*, with `G81` failing the build until one is recorded.
**So what held this control has changed from PERMISSION to a missing write
path**, and `holds.ts`'s row now says exactly that, with the measurement in it.
The customer-facing sentence *Ring us to stop autopay* stays TRUE and stays five
words (B14 rule 33).

**What the ruling explicitly left open, and what this lane did not invent:** the
audit row every money action must write (CLAUDE.md hard rule 7), whether the
change is reversible, and the write-point count. Those are design, not
permission, and they belong to the wave that builds the endpoint.

---

## 5 · PROOF

**Every new assertion was mutated and watched fail before it was trusted**
(hard-won law 7), through `vitest`, which is the harness that will run it:

| what was broken | what the suite said |
|---|---|
| `HeldCommit`'s visible sentence removed | `expected undefined to be 'We cannot take card payments yet.'` — and `'This card has expired.'` on `CWP-076` |
| the consequence box drawn on `panel` alone | `expected <div …><p …></p> … to be null` |
| `setPanel(null)` moved back inside the `!priceable` branch | `expected <span class="tabular-nums" …></span> to be null` |
| the outcome's ways-out row removed | `expected null not to be null` |
| `paidResultFrom`'s `outcome !== "paid"` guard removed | **3 failed** — one per outcome |
| the handoff's key replaced with a fresh string | `expected { amount: '40', …(2) } to deeply equal { amount: '40', …(2) }` |
| `asDate(...)` reverted to the raw string | `expected '2026-09-14' to be '09/14/2026'` |
| the empty `NEXT FEW` early return disabled | `expected <table …>…</table> to be null` |

⚠ **ONE OF THE EIGHT STAYED GREEN UNDER MUTATION AND HAD TO BE REWRITTEN, WHICH
IS THE POINT OF DOING THIS AT ALL.** The first `DEF-CWP-4869` case clicked
*Another amount* — an empty box, so the amount is not priceable — and typed into
it; the OLD code cleared the panel on that empty step by itself, so the case
passed against the bug it was written for. The window the customer actually
stood in is **`$40.00` → `$400.00`**, where the amount never stops being
priceable. Rewritten, it fails on the mutation and passes on the fix. *"Ask what
would make this check pass wrongly"* found it; nothing else could have.

**Suites:** `npx tsc --noEmit` clean · `src/portal` vitest green ·
`npm run lint` clean · `g82` PASS (77 allocated, 50 routed).
**Browser at 390 AND 1280:** recorded in §7.

---

## 6 · ⚠ THE FOUR LINES THE MERGE LANE NEEDS

**`07-frontend/src/portal/routing/portalRoutes.tsx`** — two imports beside the
existing `PayNowPage` import:

```tsx
import { PayNowCheckPage } from "../payments/PayNowCheck";
import { PayNowDonePage } from "../payments/PayNowDone";
```

and two route rows, **immediately after `{ path: "/pay-now", element: <PayNowPage /> }`**:

```tsx
  // CR-085 step 2 lane 6 — the signed-in pay journey is THREE screens (PO
  // 2026-09-11: *"it should be 3 screens - confirmed"*), split IN PLACE
  // (*"ii). Your ruling was about the shape, not the addresses."*). ⚠ The
  // GUEST flow keeps `/pay`, `/pay/check`, `/pay/done`; the blueprint draws
  // these two at those addresses and the crossing is RULED, not a defect.
  // ⚠ Declared AFTER `/pay-now`, for a reader rather than for the matcher:
  // `matchPath` is exact, so `/pay-now` cannot swallow a second segment.
  { path: "/pay-now/check", element: <PayNowCheckPage /> },
  { path: "/pay-now/done", element: <PayNowDonePage /> },
```

**`07-frontend/src/portal/routing/screenIds.ts`** — two rows in the SAME ORDER,
immediately after the `/pay-now` row. `screenIds.test.ts` asserts the two lists
are equal **including order**, and `G82` fails a route with no row and a row with
no route, so **these must land in the same commit as the routes above**:

```ts
  { path: "/pay-now/check", id: "CWP-076", blueprint: "P55", title: "Check before you pay" },
  { path: "/pay-now/done", id: "CWP-077", blueprint: "P56", title: "Payment made" },
```

Both ids are already allocated in `CR-068` §9 by this lane's commit, so `G82`
is green the moment the four lines land. `everyRouteHasADoor.test.ts` is
satisfied without an exemption: both are reached by `navigate(path("…"))`, which
is the third door form that file already knows, and the check screen is also
linked by address from the receipt's wrong-turn card.

---

## 7 · THE BROWSER WALK

**Walked on 2026-09-11, in Chromium, at 390 AND 1280, against a bundle built
from THIS worktree** (`vite build`, 12m22s, exit 0) and served by the repo's own
`07-frontend/server.mjs` on port **8503** with `STATIC_DIR` pointed at that
`dist`. Every signed-in portal read was stubbed in the browser so each state
could be reached deliberately; the shared stack on `:8401` was neither restarted
nor re-seeded. The script is `walk.mjs` and its log is `walk6.log`.

⚠ **THE SLEEPS CAME OUT OF IT FIRST, AND THAT IS PART OF THE PROOF.** The first
two runs waited a fixed 3.5s after `domcontentloaded` and failed on a box at
load 130 — *"page.goto: Timeout 30000ms exceeded"*. A fixed sleep is law 7's own
shape: it cannot fail on a fast box and cannot pass on a loaded one. It now
waits for the SCREEN (`[data-screen="CWP-076"]`) and for a control to be
**pressable** (`waitForFunction` on `!el.disabled`), so what the walk asserts is
the product rather than the clock.

**Both widths produced the SAME results on all eleven checks below — the table
is one column because there was nothing to split.**

| what was opened | what the browser showed at 390 and at 1280 |
|---|---|
| `/pay-now`, no provider | `CWP-038`; commit disabled, label *"Check this — $191.00 →"*; **the refusal is in the page text** — *"We cannot take card payments yet."* (`DEF-CWP-4866` at the call site); **`consequence: false`** — the *WHAT THIS WILL DO* box is gone (`DEF-CWP-4867`); the allocation panel still draws |
| `/pay-now`, payable | commit live; *WHAT THIS WILL DO / Takes $191.00 from Bank account ····4417. / Clears bill BL-2608-0141 in full. / Emails you a receipt. / A payment cannot be changed afterwards, only reversed.*; *"You are paying $191.00"* |
| press it | lands on **`/brazosbend/portal/pay-now/check`**, `CWP-076`, h1 *"Check this, then pay"*, total `$191.00`, left owing `$0.00`, method *Bank account ····4417*, commit *"Pay $191.00 ✓"*, and a *change something* door |
| press *Pay* | lands on **`/brazosbend/portal/pay-now/done`**, `CWP-077`, h1 **"Payment made"**, reference `PMT-2608-0311`, `$191.00`, balance after `$0.00`, and a link to `/brazosbend/portal/payments` |
| the same journey, `outcome: "declined"` | **stays on `/pay-now/check`** — `data-pay-outcome="declined"`, *"Your payment was declined"*, *"No money was taken. Try another card or bank account."* — with TWO ways out beside it, *Use another card →* to `/payment-methods` and *Go back and change something* to `/pay-now`, and the amount and the method **still shown** (`DEF-CWP-4868`, and R-10) |
| `/payments` | search box *"Search payments…"* and the `All` / `This year` filter **visible at BOTH widths**; at 390 the rows are cards (1 visible, table hidden), at 1280 the table (0 cards). The control sets are equal — which is the check `DEF-CWP-4879` asked for |
| `/autopay` | the `NEXT FEW` date reads **`08/22/2026`** with the server's `2026-08-22` kept on `data-slot-on`, and **no ISO string anywhere in the body** (`DEF-CWP-4870`) |
| `/autopay`, `How much` helper | *"The whole balance on each bill"* — the ceiling clause is gone (`DEF-CWP-4871`) |
| `/autopay`, nothing scheduled | no table at all; *"Nothing is scheduled yet. A payment appears here when a bill is issued."*, and the hold still reads *"We cannot draft payments yet"* |
| `/pay` (guest) | *"Fill in both boxes first."* **rendered on the page**, not in a `title=` (`DEF-CWP-4866`), over a disabled *Find* |
| `/pay-now/check` opened COLD | `data-portal-state="empty"`, *"This page needs the amount and the card you chose. Choose them once more and we will bring you straight back here."*, one live door to `/pay-now` |
| `/pay-now/done` opened COLD | ⚠ **the h1 is NOT "Payment made"** — it is *"We cannot show that receipt here"*, with *"This page only shows a payment you have just made. Your payments list has every one of them."* and two live doors, `/payments` and `/pay-now`. **This is the trap the brief named**, answered by building the title from the result rather than from the route |

**`document.documentElement.scrollWidth > innerWidth` was FALSE on every screen
at both widths** — 22 measurements, no sideways scroll. **Zero `pageerror`
events** across the whole run.

⚠ **WHAT THE WALK DID NOT COVER, STATED RATHER THAN IMPLIED.** The three-screen
journey was walked against STUBBED reads, so it proves the screens, the handoff,
the refusals and the addresses — it does not prove the Django endpoints, which
step 1 walked live on `:8401` and which this step did not change. `no_answer`
and `refused` were exercised in `vitest` and not in the browser; `declined` was
chosen for the walk because it is the outcome an acquirer produces most often
and the one `DEF-CWP-4868` was filed for.

⚠ **AND THE TWO ROUTES BELOW EXIST ONLY IN THE BUILD THE WALK USED.** To walk
them at all, `portalRoutes.tsx` and `screenIds.ts` were patched **locally, in
this worktree, for the build alone**, and both were then restored from the
pinned tip's bytes and re-proved byte-identical (`git hash-object` against
`git rev-parse <tip>:<path>`) before anything was pushed. **Neither file is in
either of this lane's commits.** §6 is what the merge lane must add.

## 8 · WHAT THIS LANE DID NOT DO, AND WHY

* **The kit's `CommitButton`** — `primitives.tsx` is one lane's this wave.
  `HeldCommit` is a wrapper that is DELETED when the kit learns to say its own
  reason, and every call site keeps working.
* **The card fee** (`L6-38.5`, blueprint 35's `WHAT YOU WILL PAY` panel, and
  blueprint 39's per-method badge). `PortalCardFee.priced` is `false` for every
  tenant because pricing a surcharge needs a processor's fee schedule and there
  is no processor. Building the panel would mean showing `$0.00` as a fact.
  **It becomes a defect the day a processor lands.**
* **The disconnection panel on the receipt** — blueprint 37 calls *"does this
  clear my shut-off notice"* the question the customer came in with. No field on
  `PortalPayResult` says whether a notice existed or whether this cleared it, and
  a sentence about somebody's supply is the last place to guess. Needs a served
  fact.
* **`Download receipt` / `Email it to me` on `CWP-077`.** The drawing puts both
  there. Two more held controls with no expiry test is exactly the debt
  `DEF-CWP-3925` cost a week; `/payments` already carries a LIVE receipt icon on
  every row whose document was kept, so the door to it is the honest control.
* **The past-due amount radio** (blueprint 35's second option) — `PortalPayNow`
  carries no past-due figure. Needs a served field.
* **`CPB-17`'s signed-out panel on my four signed-in routes.** All four still
  render `FailedWithRetry`, which offers a customer a *Download error report*
  button — R-22's own example of a staff control on a customer screen. It is
  identical in ~20 portal pages, so it is the frame lane's single change and not
  three copies of a different one here. The shell is now ONE function
  (`PayNowShell`) rather than three, which makes that change cheaper.
* **Five plural-less `{{count}}` keys on OTHER lanes' screens**, found while
  fixing `DEF-CWP-4873`: `portal.accounts.stateOverdue`, `portal.home.inDays`,
  `portal.readings.nextReadInDays`, `portal.enrol.minLength`,
  `portal.preferences.languageHelper`. Each will read *"1 days"* or *"1
  characters"*. Not filed by this lane — reported, because they are somebody
  else's screens this wave and a defect filed against a screen nobody is looking
  at is a row that ages.
