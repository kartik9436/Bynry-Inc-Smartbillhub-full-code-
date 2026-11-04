# CR-085 step 2 · lane 4 — HOME AND ACCOUNTS, **FIXED**: what moved, what did not, and why

<!-- ── Trace ──────────────────────────────────────────────
     Change:  CR-085 step 2 lane 4 — the FIX step for the six routes
              `/home` `/accounts` `/accounts/add` `/account` `/my-details`
              `/my-details/preferences`.
     Before:  CR-085-lane4-02-as-built-and-deltas.md (the same lane's step 1),
              CR-085-lane4-03-defects-specs-and-rules.md,
              CR-085-lane4-04-spacing-rule-39.md. Every delta id below
              (`H-nn`, `A-nn`, `O-nn`, `D-nn`, `M-nn`, `P-nn`, `X-nn`) is that
              document's, so a reader can go from either direction.
     Built on: 56ddf02fa, which carries CR-085 step 2 lane 1's frame
              (`portal/components/states.tsx`) and its rule-39 kit repairs.
     Rules:   R-10 · R-22 (PO 2026-09-11) · B14 rule 21 · 31 · 32 · 35 · 36 ·
              37 · 39 · CLAUDE.md hard-won law 1, 2, 7, 11
     ───────────────────────────────────────────────────── -->

## 0 · The two findings this step was sent to fix, and both are fixed

**THIRTY THINGS A CUSTOMER READS ON THESE SCREENS HAD NO ENTRY IN ANY OF THE
ELEVEN LANGUAGE FILES** (`X-01`, `DEF-CWP-4899`) — twenty-six of them on Home,
including the label on the biggest number on the page. They were hardcoded
English behind `t("key", { defaultValue: "English words" })`, so a German,
Japanese or Korean customer read English and nothing went red.

**All thirty now resolve.** Twenty-five keys were written into all eleven
catalogues through `10-scripts/i18n_fanin.py` — which writes eleven or writes
nothing — and the other **seven were not minted at all**, because the product
already ships those words:

| The call site said | It now reads | Why not a new key |
|---|---|---|
| `portal.home.balance` | `portal.accounts.colBalance` | *Balance* in eleven, the same figure's heading on `CWP-023` |
| `portal.home.colBill` | `portal.bills.colBill` | the bills screen's own five words for the same object |
| `portal.home.colPeriod` | `portal.bills.colPeriod` | ” |
| `portal.home.colUsage` | `portal.bills.colUsage` | ” |
| `portal.home.colAmount` | `portal.bills.colAmount` | ” |
| `portal.home.period` | `portal.bills.period` | `{{from}} – {{to}}`, already in eleven |
| `portal.home.usageDoor` | `portal.tab.usage` + `→` in JSX | the frame's own nav word; an arrow is not language |
| `portal.home.service.paperlessOff` | `portal.documents.channel.pdf_print` | *Post* in eleven, the same delivery channel one screen over |

⚠ **EVERY `defaultValue` ON A STATIC KEY IS GONE FROM THESE SIX FILES, AND THAT
IS THE PART THAT STOPS IT COMING BACK.** `G18`'s own docstring says why the
thirty were invisible, in as many words:

> *"A `t()` call carrying `defaultValue` is excluded and that is not a courtesy:
> i18next renders the default, so the author has stated in code that a missing
> key is the expected path."*

So the gate that exists to catch *a call site whose key is in no catalogue* had
an opt-out, and thirty user-visible strings were sitting in it. Four
`defaultValue`s remain in `Home.tsx` and all four are on COMPUTED keys
(`rating.service.${code}`, `portal.home.attention.${kind}`,
`settings.cycles.frequency.${word}`) where the fallback is a real data value
rather than a hidden English string.

⚠ **THE ELEVEN CATALOGUE LINES ARE `NATIVE-REVIEW-OWED`** (B14 rule 35). One
author wrote them, not eleven fluent ones. They were written per language rather
than translated — the register was taken from the neighbouring keys already in
each file (`de`/`es`/`fr-FR` formal, `es-MX`/`it-IT`/`pt-BR` informal, `ja-JP`
and `ko-KR` as polite noun labels, `hi` keeping the office loanwords) — and a
native reader may still overturn any of them.

**A SIGNED-IN CUSTOMER WHO OPENED `/{tenant}/portal` WAS SHOWN THE GUEST FRONT
PAGE WITH A *Sign in* BAR ON IT** (`H-01`, `DEF-CWP-4900`) — at the address a
utility prints on its bills and puts in its emails. The blueprint spends a page
on it (screen 26: *"They must render the same screen, not two that drift."*).

**Fixed in `guest/FrontPage.tsx`, and NOT in the route table.** `portalRoutes.tsx`
is one file four lanes share and its own comment says no lane touches it
(hard-won law 11). One route entry still points at one component; what changed is
what that component decides: it reads `GET /portal/session` on the same query key
`HomePage` already uses, and redirects to `/home` when one comes back. A guest
gets one 401 and the guest page, exactly as before.

---

## 1 · Every delta this step closed, with the evidence

| Delta | Defect | What it was | What it is now |
|---|---|---|---|
| `X-01` | `DEF-CWP-4899` | 30 strings in no catalogue | 25 keys in eleven languages, 7 pointed at existing keys, every static `defaultValue` removed |
| `H-01` | `DEF-CWP-4900` | `/portal` served the guest page to a signed-in customer | it redirects to `CWP-022` |
| `H-07` · `A-04` | `DEF-CWP-4901` | `CWP-065` had **one** inbound link in the whole portal, and it was not the drawn one | **three**: Home's account card (`→ Everything about this account`, the drawn door), the accounts table's row eye, and `My details` |
| `H-08` | `DEF-CWP-4906` (part) | `$0.00` with no sub-line, which reads as a failed read | *You are all paid up.* — the drawn `NOTHING DUE` state |
| `H-16` | `R-22` | one bare `Card` for loading, empty **and** failed, with nothing in the DOM saying which | `PortalState kind=…`, so the state is readable; and the loading and failed branches now carry `data-screen="CWP-022"`, which they did not |
| `H-17` | `R-10` | *We could not read your balance.* and nothing to do about it | a **Try again** that re-reads, beside the message |
| — | `R-10` | *Add an account and your balance appears here.* — a dead sentence | the same sentence with **Add another account** beside it |
| `A-02` | `DEF-CWP-4905` | at 390 the accounts table was 492px in a 350px column, so `BALANCE` and `STATUS` were off the right edge | a stack of cards below `md`, carrying the money large and labelled, the status chip, and doors **with their words on them** |
| `A-07` | `DEF-CWP-4905` | `+ Add an account` drawn once and built twice | once |
| `O-02` | `DEF-CWP-4910` (part) | `/account` had no back-link, though the drawing gives it `← Accounts` at both widths | `← All my accounts`, under the bar, the same word `/accounts/add` already goes back with |
| `P-09` | `DEF-CWP-4935` | *"Your bills and letters use the language above; this site follows it."* — **false** | *"We send bills in English today; this site follows the language above."* |

### The two rulings written back

**(1) BILL LANGUAGE AND WEBSITE LANGUAGE MAY DIFFER.** PO 2026-09-11, verbatim:
***"(b) Allow them to differ - currently bills are offered only in english"***.

Step 1 deliberately did **not** file `P-09` as a defect, on the reasoning that
the product's sentence and blueprint screen 59 were two deliberate positions
needing a ruling rather than a fix. **The second half of the ruling is a fact
this repository did not hold, and it changes the shape:** the website ships in
ELEVEN languages and the bill in ONE, so the two ALREADY differ for every
customer reading the portal in anything but English — which makes the screen's
old sentence **false as well as unwanted**, i.e. a defect. It is `DEF-CWP-4935`
and the sentence is fixed in all eleven catalogues.

⚠ **WHAT IS STILL NOT BUILT, AND IT IS NOT A SENTENCE.** The drawing's screen 59
wants a SECOND PICKER and a *make my bills Spanish too* banner. `BR-CWP-105`
(PO 2026-09-07) still stands: the account's preference is re-applied on every
render, so a website picker offered today would revert under the customer's hand.
The 2026-09-11 ruling permits the two to differ; it does not reverse the ORDER
ruling, so screen 59 needs a place to hold a website choice that survives —
**a build, and this step does not attempt it.**

**(2) BILL DELIVERY'S *ONE OF THESE MUST STAY ON* IS DROPPED.** PO 2026-09-11:
our rule wins — **every bill is printed regardless**.

**Nothing was built for this and nothing needed to be**, which is worth saying
plainly rather than leaving a reader to wonder. Delta `P-03` recorded that the
drawing's constraint and the product's print floor (`R-19`, `BR-BIL-036`) were
incompatible and that the built one is the one the business has. The screen
already says the true thing — *"Turning these off stops the email or the text,
never the letter. **We post everything, always.**"* — so the ruling CLOSES the
delta by confirming the build. **The drawing is now the stale half**, and a lane
re-reading blueprint screen 58 should not implement `ONE OF THESE MUST STAY ON`.

---

## 2 · What this step did NOT do, and why — read this before re-filing any of it

### Home is still headless, **and that is the drawing's decision, not an omission**

The step-2 brief asked for a heading on Home, citing `DEF-CWP-4000`. **It is not
built, deliberately, and the reasoning is already in the repo in two places.**

* The blueprint's screen 25 opens on the account line and then **AMOUNT DUE**, at
  both widths. There is no page title in either frame.
* `07-frontend/src/portal/components/pageHeadCensus.test.ts` records `CWP-022` in
  `CORRECTLY_HEADLESS` with the reason: *"the drawing opens PortalShell → KpiRow,
  no PageHead"*, and *"a title above it would push the one figure the page exists
  for below the fold."* Its `AWAITING_ANOTHER_LANE` comment says Home **was**
  listed as awaiting a head and that *"listing it as awaiting a head would have
  had the next lane ADD one and break the drawing."*

So `H-02` as step 1 wrote it — *"every drawn screen opens with its name"* — was
an over-generalisation taken from `DEF-CWP-4000`'s census rather than from the
drawing, and this file corrects it. **What was genuinely missing on Home is the
`data-screen` mark on the loading and failed branches**, which every rendered
check in this repo selects on, and that is fixed. `PortalScreen` is composed with
`head={null}`.

### Four things the kit owns, which this lane is forbidden to touch

| Finding | Where the fix lives | Status |
|---|---|---|
| `DEF-CWP-4903` — KPI cell side padding **16**, anchor **20**; row gap **16**, anchor **8** (amended 2026-09-11) | `primitives.tsx` `KpiTile` `p-4` → `py-4 px-5`, `KpiRow` `gap-4` → `gap-2` | **OPEN.** It moves four screens at once (`CWP-022`, `CWP-033`, `CWP-065`, `CWP-066`) |
| `DEF-CWP-4904` — `KpiRow` is `grid-cols-4` unconditionally, so a one-account customer's balance sits in the left quarter of a 1,060px row with three empty columns | `primitives.tsx` `KpiRow` | **OPEN.** Same file, same reason |
| `X-02` — the portal's own standard A (*every icon carries its word; on a phone there is no hover*) is reversed by every portal table's row icons | `components/RowActions.tsx` + `listTable.tsx` | **OPEN.** A kit change to every portal list. ⚠ **The 390 CARDS added here DO carry their words**, which is where the no-hover argument actually bites |
| `DEF-CWP-4902` — the field anatomy | lane 1's, and **done** — see §3 | verified |

### `DEF-CWP-4909` — *YOUR SIGN-IN* states three facts and offers no control

⚠ **UPGRADED WITH EVIDENCE RATHER THAN FIXED, AND THE EVIDENCE IS WORSE THAN THE
ROW SAID.** `POST /api/{tenant}/portal/sessions/revoke-all` **exists, works, and
its own docstring names this screen** — `06-backend/apps/portal/api.py:426`:

> `"""`POST sessions/revoke-all` — *sign out everywhere* (`CWP-024`)."""`

`grep -rn "revoke-all\|revokeAll" 07-frontend/src` returns **nothing**. So the
panel that says *Devices signed in · 2* has a live endpoint built for it and no
caller: hard-won law 2 in its classic form, on the screen the backend docstring
names.

**Why this lane did not wire it, stated rather than glossed:** the control ends
every session for this credential, and `elena@example.test` on the shared stack
is **six sibling lanes' login as well as this one's**. Pressing it to prove it
works would have signed all of them out mid-walk. A control proved only by
reading the code is the thing law 7 exists to refuse, so the finding is recorded
and the wiring is left to a lane that can exercise it.

### `DEF-CWP-4908` — the portal asks a North American customer for their *Postcode*

**Not fixed, deliberately.** `portal.addAccount.postcode` and
`portal.myDetails.postcode` are read only by this lane's two screens, so they
COULD have been reworded here — and the other three (`portal.postcodeHelper` on
`/enrol` and `/pay`, and `portal.track.secondFact`) belong to other lanes.
**Fixing two of five manufactures an inconsistency that reads as a bug**: the
product would say *ZIP code* on two screens and *Postcode* on three. It is one
vocabulary and it wants one lane. The row stays open naming all five sites.

### The rest of `DEF-CWP-4906`, `4907` and `4910`

* **`4906`** — `NOTHING DUE` is built. **`FAILED TO LOAD` still does not offer
  the telephone number**: `getHome` does not carry one and the frame's front
  payload is not threaded into `HomeView`, so it is not invented (R-23). The
  drawn **LOADING skeleton is deliberately not built** — the PO's R-22 ruling
  (*"differntiate it using text message"*) replaced *three pictures* with *three
  sentences*, and `states.tsx` says so about itself.
* **`4907`** — `CWP-025` is still grouped by CHANNEL where its drawing groups by
  SUBJECT, and `P-02`, `P-04`, `P-05`, `P-06` are untouched. That is a redrawn
  screen, not a fix.
* **`4910`** — the back-link is built. The heading is still *Your account* where
  the drawing makes it the ADDRESS, `THIS ACCOUNT` is still one row of eight with
  no consequence sentences, `RECENT` is not built, and the `GO TO` list still
  carries no counts.

### One latent fault found on the way and NOT filed as live

`Home.tsx` renders a non-`pay` attention item as
`` t(`portal.home.attention.${item.kind}`, { defaultValue: item.kind }) `` and no
`portal.home.attention.*` sub-key exists in any catalogue. **It cannot fire
today**: `06-backend/apps/portal/selectors.py:1504` builds `attention` with
exactly one kind, `"pay"`. The day a second kind is added, a customer reads a raw
enum code on their home page (B14 rule 32). Recorded here rather than filed,
because a defect row for a branch no server can reach would be a row nobody can
reproduce.

---

## 3 · Measured in a browser, at 390 AND 1280

⚠ **ON THIS LANE'S OWN SERVER, NOT THE SHARED STACK.** `:8401` serves
`/home/user/SMARTBillHub/07-frontend/dist` and is shared with six siblings; it
was not restarted, rebuilt or re-seeded. This walk ran a second copy of the same
`server.mjs` on **`:8414`** over this worktree's `dist`, proxying `/api` to the
same backend — so the API, the tenant and the data are the shared ones and only
the bundle is this lane's. Signed in as `elena@example.test`.

⚠ **WHAT THE FIXTURE CANNOT SHOW, SAID UP FRONT.** `brazosbend` holds **one**
account, **zero** invoices and **zero** payments. So the 390 CARD LIST was walked
with **one** card and not four; the `PAST DUE` chip, the *Pay* door on a card,
the account switcher, the month chooser and the multi-account table were **not
seen with real data** and are asserted in `MyAccounts.dom.test.tsx` against the
four-row `LANDLORD` fixture instead. Every figure below is `getComputedStyle` or
`getBoundingClientRect` on a real Chromium.

### 3.1 · The fixes, seen

| What | 1280 | 390 |
|---|---|---|
| `/{tenant}/portal` signed in | lands on `/brazosbend/portal/home`, `data-screen="CWP-022"`, **0** `[data-errand]`, **no** *Sign in* on the page | — (the redirect is width-independent) |
| Home, nothing owed | `Balance` · `$0.00` · **You are all paid up.** | same |
| Home, the drawn door | `Everything about this account → /brazosbend/portal/account` | same |
| `/account` back-link | `← All my accounts` | `← All my accounts` |
| `/accounts` phone half | `[data-accounts-cards]` `display: none` | **`display: flex`**, 1 card |
| `/accounts` table half | `display: block`, table **1026px** in a **1026px** box | **`display: none`** |
| `+ Add an account` | **1** door | **1** door |
| `/my-details/preferences` language line | *We send bills in English today; this site follows the language above.* | same |
| Home `<h1>` | **none**, as the drawing draws it | **none** |
| page body sideways scroll | `scrollWidth 1280 == clientWidth 1280` on all six | `scrollWidth 390 == clientWidth 390` on all six |
| JavaScript errors · 4xx | **none** on any route, either width | — |

### 3.2 · The rule-39 anchors these screens still miss, re-measured

Lane 1's kit repairs LANDED and this lane confirms them rather than repeating
them: `.input` is **6px 10px** with `min-height: 36px` on `/accounts/add` and
`/my-details`, `label → input` is **5**, and `input → helper` is **6** on
`/my-details/preferences` — all four were 8×12 / auto / 4 / 17 at step 1.

**What still diverges, and none of it is inside this lane's six files:**

| Anchor | Rule 39 | Measured | Owner |
|---|---|---|---|
| KPI cell side padding | **20** | **16** (Home and `/account`, both widths) | `primitives.tsx` `KpiTile` — `DEF-CWP-4903` |
| KPI row gap | **8** (amended 2026-09-11) | **16** | `primitives.tsx` `KpiRow` — `DEF-CWP-4903` |
| KPI columns with ONE tile | — | `253px 253px 253px 253px` at 1280 | `primitives.tsx` `KpiRow` — `DEF-CWP-4904` |
| page padding | **24 / 16 / 32** | **24 / 20 / 24 / 20**, identical on all six routes and both widths | the frame — lane 1's `DEF-CWP-4922` |

⚠ **AND ONE READING THAT LOOKS LIKE A MISS AND IS NOT.** `/accounts` reports
`label → input: 0` at both widths. That is the TABLE TOOLBAR's search box, whose
label is `sr-only` and therefore has no height — the rule's field anatomy is
about a form field, and this screen has no form. Recorded so the next reader does
not re-file it.

---

## 4 · ONE DEFECT THIS LANE CAUSED AND CAUGHT THE SAME DAY — `DEF-CWP-4940`

**What a customer saw.** The recent-bills panel on Home drew two column headings
reading, literally, `portal.bills.colPeriod` and `portal.bills.colUsage`.

**How it happened, and it is worth more than the fix.** §1 of this record says
Home borrows five of its headings from other screens' catalogue entries rather
than minting a `portal.home.*` family, on B14 rule 35's own instruction — *reuse
the word the product already ships.* That is still right. **The cost of borrowing
is that another lane's rename lands on your screen**, and it did: the bills lane
renamed `portal.bills.colPeriod` to `colCovers` and deleted `colUsage` in
`448776e5a`.

⚠ **AND THE COMMIT THAT BROKE IT IS THE COMMIT THIS LANE PINNED AS ITS TIP.**
`448776e5a` is the exact SHA `land.sh` pinned on its first attempt and re-derived
all eleven catalogues from — law 11's blob re-derivation working precisely as
written, taking the tip's catalogues, which no longer held two keys this lane's
code asks for. **Re-deriving a blob protects the FILE and says nothing about the
RELATIONSHIP between two files.** There is no command for that half; what finds
it is asking, after a re-derivation, *what did my code expect of the file I just
replaced?*

**Why nothing went red.** i18next renders the KEY when a key is missing, which is
a fallback that cannot fail loudly: `tsc` cannot see inside a string; the browser
walk was green because it ran against a bundle built BEFORE the catalogues were
re-derived — **a walkthrough proves the bundle you built, not the branch you
pushed**; and `G18` does catch exactly this (its *"renders raw to a user"* count)
and **was already red on 21 other keys**, which is hard-won law 7's *a true red
hides in a suite that is already failing*, live.

**Fixed** by pointing the two rows at `portal.bills.colCovers` and
`portal.tab.usage` — both present in all eleven catalogues, both the word this
product already uses for that column. **Guarded** by a case in
`Home.dom.test.tsx` that asserts of the SHAPE rather than of a key: no heading on
Home starts with `portal.`, and no text anywhere on the screen matches
`/portal\.[a-zA-Z]+\.[a-zA-Z]/`. Shown RED against the two broken keys first —
it named both — then green, 37/37.

---

## 5 · AND THE INSTRUMENT ITSELF WAS THE SECOND DEFECT — `DEF-CWP-4941`

Re-running this lane's own committed walkthrough against a **freshly built** bundle
reported **five failures** naming a phone-layout fault and a missing account door.
Neither exists. Every failing check reads the page **body**; every passing one reads
the **head** — which is the whole diagnosis.

**Waiting for `[data-screen="CWP-0xx"]` used to mean *this screen has its data*,
because the mark was only on the success branch.** R-10 and R-22 changed that, and
changed it correctly — a screen must keep its identity while it is READING and when
it has FAILED, which is exactly what §1 of this record did to `Home.tsx` and
`MyAccounts.tsx`. **The same edit silently turned the readiness gate of every
committed render-check into a wait that can return before a row is drawn.**
`33` files under `10-scripts/` wait on that mark; `22` portal screens now carry it
more than once.

⚠ **IT IS THE MIRROR OF THE DEFECT THE WALK EXISTS TO CATCH.** A wait that returns
too early reports a layout fault that is not there, so the next lane's honest
response is to go and "fix" a screen that is already correct. And it does not fail
honestly: the same five checks **passed at 08:54** on a quiet machine and **failed at
12:20** on a busy one, with the product byte-identical between the two runs. A check
whose answer depends on the load average is law 7's *what would make this pass
wrongly* with both answers yes.

**Fixed for this file.** Each route names a third value — a mark only the success
branch draws (`[data-testid='home-account']` on Home, the card list or the table on
Accounts) — waited for after the id. Where a screen has no such branch the id is
still conclusive and the column is `null`, so the file states which screens it is
making a claim about.

⚠ **AND THE FIRST FIX WAS ITSELF A WAIT THAT COULD NEVER SUCCEED**, which is worth
more than the fix. `waitForSelector` defaults to `state: "visible"`, and this screen
draws BOTH halves of the 390/1280 split and hides one with `max-md:`. A comma
selector resolved to two elements, playwright *"proceeded with the first one"* — the
card list, `display: none` at 1280 — and waited 30 seconds for a thing that is
hidden on purpose. `state: "attached"` is the right question, because what the wait
actually asks is *has the data been drawn*.

**Proof, and it is a clean pair:** the five FAILs and the same five PASSes come from
two runs of the same walkthrough against **the same bundle**, with only the wait
changed. Final: **24 of 24 checks passed**, against the 18 of 23 the same file reported on the same bundle twenty minutes earlier.
