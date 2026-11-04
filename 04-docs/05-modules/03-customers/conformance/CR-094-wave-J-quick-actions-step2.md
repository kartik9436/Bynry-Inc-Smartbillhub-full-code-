# CR-094-BRC01 · step 2 wave J — `ACC-S14`, the thirteen quick actions

**Screen `S21` · `/:tenant/accounts/:accountId` · the six header actions and the
seven rail icons.** Drawn as **`R4`, pages 154–174** of the accounts blueprint;
committed by **`ACC-S14`** on page 208.

---

## 0 · THE DRAWING THIS WAS BUILT FROM, AND HOW IT WAS OBTAINED

⚠ **`05-prototype/02 Accounts Menu Blueprint.pdf` IS NOT IN THIS BRANCH'S TREE.**
`git ls-files 05-prototype/` lists four PDFs and this is not one of them. It was
uploaded to a commit that is **not an ancestor of `claude/hi-0jmv62`** —
`033981d4f` *"Add files via upload"*, 2026-09-12 05:57 −0400 — which is the same
commit the step-1 lane pinned. The blob is reachable by hash:

```
git cat-file blob 3f4d75fb74c8a0dc483692c8c21e341215c562d7 > accounts-blueprint.pdf
```

**`sha256` begins `c8d596bb505f5020ce4b9474`, which is byte-for-byte the digest
the step-1 lane recorded**, so this wave and that audit read the same 242 pages.
Filed as **`DEF-CUS-5122`** — a drawing a lane cannot open is a drawing that will
not be built, and every future accounts lane hits this.

**Pages 155–175 were read as IMAGES at scale 2** via `10-scripts/pdf/pdf_render.py`.
The text layer is unusable for anything carrying a digit (every numeral extracts
as `&`) and the wireframes are vector art absent from it entirely.

---

## 1 · THE THIRTEEN, COUNTED OFF THE DRAWING

The step-1 lane warned that this blueprint contradicts itself on counts and that a
build lane must **count the drawing**. R4's own captions number themselves
`Quick action N of 13` and carry figure ids `ACC-Q01`…`ACC-Q13`, so the thirteen
are not inferred:

| # | fig | action | where it lives in the product today |
|---|---|---|---|
| 1 | `ACC-Q01` | **Adjust** | header · **dead button** — `onClick={() => undefined}` |
| 2 | `ACC-Q02` | **Move-out** | header · navigates to the Move-out wizard |
| 3 | `ACC-Q03` | **Activate account** | header · **commits on the click, no dialog** |
| 4 | `ACC-Q04` | **Move-in** | header · navigates to the Move-in wizard |
| 5 | `ACC-Q05` | **Close out** | header · navigates to the Close-out page |
| 6 | `ACC-Q06` | **Record payment** | header primary · **modal, live** |
| 7 | `ACC-Q07` | **Send statement** | rail · disabled, typed refusal |
| 8 | `ACC-Q08` | **Print bill** | rail · navigates into **billing** |
| 9 | `ACC-Q09` | **Issue credit** | rail · navigates into **billing** |
| 10 | `ACC-Q10` | **Change plan** | rail · navigates to the Change-plan wizard |
| 11 | `ACC-Q11` | **Disconnect notice** | rail · navigates to the Disconnect wizard |
| 12 | `ACC-Q12` | **Payment plan** | rail · navigates to the Payment-plan wizard |
| 13 | `ACC-Q13` | **Add note** | rail · **modal, live** |

**Six header actions plus seven rail icons is the thirteen**, and that reconciles
with `BR-SHL-045`'s seven glyphs exactly.

⚠ **THE LANE BRIEF SAID ONE OF THE THIRTEEN WAS BLOCKED ON `OQ-CUS-1769`. IT IS
NOT, TWICE OVER.** *Change the unit this account is on* is **`R5`'s sixth EDIT
dialog (`ACC-E07`)**, not one of R4's thirteen — the question's own body says so
(*"`R5`'s sixth edit dialog … and nothing else. The other five `R5` surfaces,
`R4`, `R6` and `R7` are all untouched by this"*) and so does step 1's finding
`F13`. **And the question reads CLOSED** — 2026-09-12, PO option (a), recorded as
`BR-CUS-1047`. Read per the prime directive: the **status column**, not the body.
**Nothing in this wave is stubbed on an open question.**

---

## 2 · WHAT `ACC-S14` ACTUALLY COMMITS TO — quoted from the card, p208

> **"Every quick action on an account opens as a form over the account, with all
> of its fields and a recap before it commits."** Waits on nothing server-side for
> nine of the thirteen. Adjust waits on a billing endpoint to post to; Send
> statement waits on statements; the Record payment additions wait on an
> open-bills call that already exists and on a late-fee figure that does not. R4
> in §10 draws all thirteen.

> **Acceptance:** "A clerk on the phone presses any of the thirteen, fills the
> form **without losing sight of the balance behind it**, reads back a recap, and
> commits — or reads why it cannot be committed, on the button itself."

---

## 3 · MODAL OR PAGE — THE JUDGMENT, AND WHY IT IS NOT A NEW RULE

**The container is settled by the COMMITMENT CARD, not by the drawing.** R4 is
stamped `NO COMMITMENT` and says so itself; `ACC-S14` is the card, and its
acceptance sentence contains the phrase **"without losing sight of the balance
behind it"**. A page replaces the balance. A dialog does not. So the dialog is the
committed behaviour, and no rule had to be invented to get there.

**The skill's §5 test was applied anyway, honestly, because several of the
thirteen fail it:**

| §5 says SCREEN when… | which of the thirteen |
|---|---|
| more than one step | six of them are multi-step |
| it holds a table of its own | Move-in, Record payment, Change plan, Payment plan |
| it must survive a refresh | the long ones — a 20-field move-in is real work to lose |

**So these do NOT resemble the estimate precedent, and §5 says say so rather than
decide it quietly — this section is that.** What resolves it is that §5 is a
guide to an unruled question while `ACC-S14` is a commitment with an acceptance
sentence, and the specific beats the general.

⚠ **`AST-B-12` (2026-09-12, *"this should be form and not modal"*) DOES NOT REACH
THESE THIRTEEN, and the reason is in its own decision row.** That ruling is about
**correcting an asset** — *"A clerk can correct an asset from the asset, **at an
address they can come back to**"*. The value there is the **bookmarkable address**,
and there is no context behind the dialog worth preserving: the clerk came from a
registry row. Here the requirement is the exact opposite and is written down —
the context behind the form **is half of what the clerk is being asked about**.
Two instances, two answers, one principle: **what is behind the form decides.**

**Neither ruling is generalised. Neither is re-raised with the PO** (law 13).

---

## 4 · WHERE THE DRAWING LOSES — B14 RULE 38, APPLIED

Rule 38 names four of these **verbatim** as form CONSTRUCTION, where the UI rules
win and *"nothing is built for it"*:

| R4 draws | built as | rule |
|---|---|---|
| **two fields side by side**, every section a 2-column grid | **one column**, `FieldStack` | 38 — named verbatim |
| footer with **`Save & exit` on the LEFT** (`ACC-Q02`, `ACC-Q04`) | kit footer: Cancel + commit | 38 — named verbatim |
| header sub-line under the title | `FormModal`'s `kicker` | 38 — the kit already has it |
| `✕` close control | `ModalShell`'s own | 38 |
| helper under its input | **agrees** with rule 39 | — |
| field → field spacing | **20px**, `--space-5` | 39, as amended 2026-09-12 |

**What the drawing still decides, and what was taken from it unchanged:** which
fields, in which order, under which headings, with which helper sentence and which
recap rows. That is rule 38's own last clause.

---

## 5 · THE FORMS, QUOTED — every label, helper and section, in the drawn order

Read off the rendered pages. `*` marks the drawn required mark.

### `ACC-Q01` · Adjust — *"Adjust this account"* · p155–156
Kicker: `Bramble Bakery · A-11812 · balance $2,410.00`

* **WHAT IS BEING ADJUSTED** — `Adjust what *` *(This account's balance · A specific bill · One line of a bill.)* · `Which bill` *(There are no bills on this account to adjust.)*
* **THE MONEY** — `Which way *` *(A credit reduces what they owe; a debit increases it.)* · `Amount *` *(Cannot exceed the balance of $2,410.00.)* · `Tax` *(Follow the original line · No tax · Tax at today's rate.)* · `Effective date *` *(The day this counts from.)*
* **WHY** — `Reason *` *(The opening balance was wrong · Billed in error · Meter fault · Goodwill · Leak allowance · Rate applied wrongly · Missed charge · Theft restated)* · `Case or reference number` *(Whatever the customer can quote back.)* · `Note to the file` *(Kept with the adjustment and read by anyone asking why later.)*
* **APPROVAL** — `Raised by` *(read-only)* · `Approved by` *(An adjustment over $100.00 cannot be posted by the clerk who raised it.)*
* **Recap — "What this does to the account":** Balance now · Where it came from · This adjustment · Days past due · **Balance after this adjustment**
* Footer note: `Every money action writes the audit log.` · commit **`Post adjustment`, DISABLED**

### `ACC-Q03` · Activate account — *"Activate this account"* · p158–159
Kicker: `Kwan, Michael · A-12048 · 88 Pine Vista · Unit 2`
Lead: `Today this commits the moment it is clicked, with no dialog and no way back.`

* **WHEN SERVICE STARTS** — `Activation date *` *(The day the account starts being billable.)* · `Opening read` *(Use the last read on the meter · Enter one now · No read needed)* · `Electric starts` · `Water starts`
* **THE PLAN** — `The unit's plan` *(In force at this unit since 06/01/2026.)* · `Base charge` *(There is nothing to pick here: a plan belongs to the unit, and the account inherits it.)*
* **THE DEPOSIT** — `Deposit` *(Charge the scheduled amount · Charge a different amount · Waive it (needs a supervisor))* · `Amount` *(From the plan's deposit schedule.)* · `Due` *(Falls on the first bill's due date.)* · `Billing cycle` *(Taken from the unit; change it only if this account bills on another round.)*
* **TELLING THE CUSTOMER** — ☑ `Send the welcome pack` · ☐ `Send the deposit notice separately` *(Both are recorded whether or not they can be delivered yet.)*
* **REVIEW — "What pressing the button will do":** Status · Service starts · Opening read · Plan · Deposit · Cycle
* Caveat block: **"Two things the server will not manage, and says so now rather than after."** — *No plan snapshot is recorded…* · *No deposit is applied…*
* commit **`Activate account`**

### `ACC-Q07` · Send statement — *"Send a statement"* · p165–166
* **WHAT PERIOD** — `Period *` *(The last 12 months · This year · Since the account opened · Between two dates)* · `Covers` *(read-only)* · `From` · `To`
* **WHAT TO INCLUDE** — ☑ `Bills issued` · ☑ `Payments received` · ☑ `Credits and adjustments` · ☑ `The opening balance` · ☐ `Usage for each period`
* **HOW IT GOES OUT** — `Send it *` *(By email · By post · Download it now)* · `To` *(read-only)* · `Message to put on it` *(Appears above the first line.)*
* **REVIEW — "What pressing the button will do":** Period · Opening balance · Bills · Payments · Delivery · **Closing balance on the statement**
* commit **`Send statement`, DISABLED**

*(The remaining ten forms are inventoried in the same detail in §5 of the lane's
scratch notes and are carried into `accountQuickActions.ts`'s configuration as
each is built; the three above are the three this wave WIRES — see §7.)*

---

## 6 · WHICH ENDPOINT EACH OF THE THIRTEEN LANDS ON — measured, not assumed

| action | the write | exists? |
|---|---|---|
| Adjust | an adjustment row on **billing** | ❌ **NO.** `services.ACTION_UNAVAILABLE["adjust"]`: *"billing publishes no writer for it — `apps.billing.services` exports the late fee and nothing else"* |
| Activate account | `POST /accounts/{id}/activate` | ✔ served, wrapped, called |
| Send statement | a statement renderer | ❌ **NO.** Nothing in the product renders a statement |
| Record payment | `POST /accounts/{id}/payments` | ✔ live |
| Add note | `POST /accounts/{id}/notes` | ✔ live |
| Move-out | `POST /accounts/{id}/move-out` | ✔ live, behind its wizard |
| Move-in | `POST /accounts/{id}/move-in` | ✔ live, behind its wizard |
| Close out | close-out write | ✔ live, behind its page |
| Change plan · Disconnect · Payment plan | each wizard's own write | ✔ live, behind their wizards |
| Print bill | `GET /invoices/{id}/document` | ✔ mounted, in **billing** |
| Issue credit | `execute_credit_only` | ✔ built, in **billing** |

**So two of the thirteen have no write at all** — Adjust and Send statement — and
both are drawn deliberately as *"the form the product needs before the endpoint
exists — commit disabled, with the reason on it"*. That is `BR-SHL-025` and it is
what is built for them. **No endpoint was invented.**

---

## 7 · WHAT THIS WAVE BUILDS, AND WHAT IT DELIBERATELY LEAVES

**BUILT — one component, one configuration, one action wired.**

1. **`accountQuickActions.ts`** — ONE configuration declaring all thirteen: the
   figure id, the destination (`form` · `route` · `held`), and for a wired action
   its sections, its fields in the drawn order, its recap rows and its commit.
2. **`AccountQuickActionForm.tsx`** — ONE component that renders any of those
   configurations and knows none of them by name. Thirteen forms, one
   implementation.
3. **Kit additions, opt-in, nothing existing moves** (rule 38's own remedy when
   the kit lacks a piece the drawing needs): **`RecapBox`**, and
   **`FormModal.commitBlocked`** so a form with no write behind it can refuse on
   its own commit rather than at the server.
4. **Wired: `ACC-Q03` Activate account.**

### Why Activate, and why only Activate

**It was the unsafe one.** The header button called `activate.mutate()` on the
click: no dialog, no date, no recap and **no way back**, on an act that starts
billing. R4's caption for this figure says exactly that — *"the confirmation the
product is missing, and it names the partial failure BEFORE the click"*.

**It also has a live endpoint and needed no server work**, which the other two
form-shaped candidates do not: `Adjust` has no adjustment writer in billing at
all, and `Send statement` has no statement renderer. Both are declared `held`
with their reason and both keep their refusal.

⚠ **AND THE FORM IS NOT THE DRAWN FORM, FOR A REASON THAT IS THE LARGER FINDING
OF THIS WAVE** — see §6 and `DEF-CUS-5121`. `POST /accounts/{id}/activate`
accepts `opened_at` and `status` and **refuses every other field by name**. R4
draws ten. So the built form asks for the one writable field, shows the plan and
the status it can read, and **states the other three as absences** rather than
drawing inputs that would collect values the server rejects.

**LEFT, and this is the reason rather than an apology.** The other twelve already
open a complete, live, tested surface — six wizards, a page and two modals
totalling **~7,300 lines** with park-and-resume behind them. R4 asks for those
forms to be re-housed over the account. **Re-authoring them as dialogs is the
duplicate code the PO's standing instruction forbids** (*"Do all changes based on
actual code — also don't create duplicate code"*), and it would throw away
park/resume, their tests and their server wiring. Moving the CONTAINER without
copying the FORM is a wave of its own, and `accountQuickActions.ts` is the file
that wave edits: a destination changes and no form is re-typed.

⚠ **THAT WAVE IS `CR-094-BRC01` WAVE L, AND IT LANDED 2026-09-13 (`BR-CUS-1051`,
product `2.242.0`) — SO THE TABLE IN §1 ABOVE AND THE WORD *LEFT* HERE ARE BOTH
SUPERSEDED FOR EIGHT OF THE TWELVE.** PO ruling of that day, verbatim: ***"Yes
move the eight quick actions over the account"***. Move-out, Move-in, Close out,
Print bill, Issue credit, Change plan, Disconnect notice and Payment plan are
**child routes of `/accounts/:accountId`** now, rendered in a dialog over the
account; §1's *"navigates to…"* cells describe the product up to 2026-09-12 and
no longer describe it. **This lane's reasoning was not overturned — it was
completed**: the prediction in the sentence above is exactly what happened, and
the measured total is **8,838 lines mounted, none of it copied.** `Adjust` and
`Send statement` stay HELD with their reason; the ruling named eight. Wave L's
own conformance file is `CR-094-wave-L-quick-actions-over-the-account.md`.

**Out of scope and NOT touched, as the brief requires:** documents on an account
(`ACC-S8`, wave I) and the communication action (`ACC-S16`/`R6`, wave K) are two
other waves, both in flight in this same tree. Neither was changed.

---

## 8 · WHAT WAS PROVED, AND HOW

**Every guard was shown RED first, against the PRODUCT code, then green.**

| what was broken | what went red |
|---|---|
| the recap made to ignore live form state | *"reads back a recap, and the recap MOVES when the date does"* |
| `commitBlocked` made not to disable the commit | two `BR-SHL-025` cases, including *"cannot be submitted"* |
| a field the endpoint refuses added to the config | *"asks ONLY for fields POST /accounts/{id}/activate accepts"* |

Each planted fault was restored and the restore verified byte-identical with
`git diff --stat` before the suite was trusted green.

⚠ **`tsc` WAS ITSELF PROVED.** `npx tsc --noEmit` printed nothing, which is
indistinguishable from the false pass hard-won law 7 names (*"`npx tsc` in a
worktree with no local install fetches a newer TypeScript, aborts on a config
error, and reports no type errors at all"*). A type error was injected and the
LOCAL binary — `./node_modules/.bin/tsc`, version 5.5.4 — named it at its line.

**Counts: 38 new cases across three files, all green** — 17 census · 8 `RecapBox`
· 13 form. The suites this wave's kit change could have moved were run too and
are unchanged: `FormModal.test.tsx` 26, `FormModal.dom.test.tsx` 2,
`AccountActions.test.tsx` 29.

⚠ **NOT PROVED, AND SAID RATHER THAN IMPLIED: no pixel is asserted.** jsdom
computes no layout, so B14 rule 39's 5 / 6 / 20 figures have no check here and
none anywhere in this repo. What the form tests assert is ORDER, PRESENCE and
BEHAVIOUR. **And this wave did not drive the running product in a browser** —
hard-won law 6's diff against the prototype is NOT done, and that is the gap a
reader should hold against it.

---

## 9 · THE REDS THIS WAVE DID NOT CAUSE, DATED

Law 7's first habit, and every one of these was dated rather than asserted.

| red | dated how | verdict |
|---|---|---|
| `AccountDetailPage.test.tsx` — Meters tab, `43,148` | **fails at `fa2298b11`, this wave's parent**, proved in a `git worktree` pinned there | **not ours.** Filed `DEF-CUS-5124`; `formatQuantity("43148")` measured returning `"43,148"`, so the formatter is NOT the fault |
| `AccountDetailPage.test.tsx` — two Documents cases | caused by wave I's **untracked** `AccountDocumentsTab.tsx`, written into the shared tree at 21:17 and on no branch | **not ours, and not on the branch** — they pass at the parent |
| `AccountDocumentsTab.tsx` — three `tsc` errors | same untracked file; `git status` reports `??` and `git cat-file -e` on the tip says it is absent | **wave I's, in flight** |
| `routing/screenIds.test.tsx` · `ConfirmDialogTier.dom.test.tsx` | named in the lane brief as known | **not ours** (`DEF-SHL-5116`, `DEF-SHL-5101`) |

⚠ **AND ONE NEAR-MISS THIS WAVE CAUGHT ON ITSELF, WORTH MORE THAN THE REDS.**
After pushing, `AccountDetailPage.tsx` in the shared working tree picked up wave
I's **uncommitted** edit (13 insertions, 2 deletions, re-pointing the Documents
tab). Re-pushing that path would have published a sibling's in-flight work with a
correct file count and correct-looking hunks — law 11 mechanism five, `DEF-168`
exactly. It was caught by reading `git diff --numstat <my own commit>` on a file
this wave had already pushed, and **that path was named in no later push.**

⚠ **AND ONE THIS WAVE GOT WRONG.** Four defect ids were written into source and
into this document **before** they were allocated. Two of them — `5119` and
`5120` — were already taken by `DEF-SHL-5119` and `DEF-NOT-5120`, so the
citations were phantom and would have pointed a reader at other lanes' defects.
`10-scripts/file_defect.py --id-module CUS` was then run for each and every
citation corrected to the number it actually returned. **That is `DEF-1787`'s
trap — an allocated id is a blob too — and the rule it teaches is to allocate
BEFORE citing, never after.**
