# One-time bill · §04 Single bills · the three-step conversion

**Track: MAINTENANCE**, not Build. `12-governance/22-product-maintenance-process.md`'s
one question — *can a user do this task in the product today?* — answers **yes**:
`/:tenant/billing/one-time` is live, a clerk can pick an account and a window and
create a draft bill, and six write paths run behind it. That makes this the case the
process names by hand: **a live screen redrawn end to end is Maintenance**, borrowing
exactly one thing from Build — the drawing step.

**Reported by the Product Owner, 2026-09-14, verbatim:** *"one time bill also does not
match - it is 3 steps process"*.

**The drawing.** `05-prototype/04 Billing, As Built.pdf` on the DEFAULT branch —
14,363,163 bytes, sha256 `137a2a48c0398c39897f49aafa0bbb9c44ff21d6258eed78cd7558e6cc200971`,
confirmed independently — **§04 Single bills, pages 99–117**, read AS IMAGES at scale 2
per B14 rule 42.

⚠ **THE PAGE RANGE IN THE BRIEF WAS SHORT BY FIVE PAGES.** It read *"around p099–p112"*.
§04 runs **p099 to p117**: `23 Confirm and send` opens on **p114** and `24 Periods`
closes on **p117**, with §05 Budget bills starting on p118. Two of the nine drawn
entries sit entirely outside the quoted range.

---

## 0 · ⚠ THERE IS NO CARRY-OVER MAP FOR §04, AND THAT IS A FINDING

The bulk run has one — **p087–p088**, dispositions reading `UNCHANGED`, `MOVED`,
`RELABELLED`, `REMOVED` against each drawn element of §03. **§04 has none.** Searched
across p084–p124: those four words appear on p087 and p088 only.

**The document says why, in §04's own front matter (p099):** *"Every screen in this
section is **new**: the tab exists and can draft, but no kind has ever had a screen of
its own."* Every one of the nine frames carries the red `REDESIGN … NEVER BUILT`
banner. The document had nothing to carry over *from*, because it is not redrawing a
drawn predecessor — it is drawing, for the first time, a tab that was built from the
prototype.

**So the reuse specification had to be built from the PRODUCT side instead**, and §2
below is it. It is the acceptance test for this conversion: an element marked `MOVED`
that goes missing is a failed conversion, and one marked `REMOVED` that survives is the
same failure.

---

## 1 · WHAT THE DRAWING ACTUALLY SPECIFIES — nine entries, verified from the pages

**p100, verbatim:** *"All six are raised through one three-step wizard — the same rail a
clerk already learned on the bulk run, drawn once for the two shared steps and once per
kind for the middle one."* And on the split: *"It matches the engine. **Step 1 is the
request, step 2 is what gather resolves, step 3 is what pricing produced.** Nothing in
steps 1 or 2 writes anything."*

**The rail, read off p101's frame:** `1 Who and when · 2 What we bill on · 3 Confirm and
send`. The brief's reading of it was correct, character for character.

| Entry | Drawn | Pages | What it is |
|---|---|---|---|
| **21** | `Who and when` | p101–p102 | step 1, drawn ONCE, all six kinds |
| **22.1** | `Interim` | p102–p104 | step 2 · the fullest of the six |
| **22.2** | `First bill` | p104–p106 | step 2 · adds group `E What a first bill adds` |
| **22.3** | `Final bill` | p106–p108 | step 2 · adds `E The deposit, then one settlement path` + `F This customer's other accounts` |
| **22.4** | `Back-bill` | p109–p110 | step 2 · adds `E The periods, and what the grouping costs` |
| **22.5** | `Penalty` | p111–p112 | step 2 · adds `E The periods, the reason, and its evidence` |
| **22.6** | `Fee` | p113–p114 | step 2 · `E The charge`; B, C and D **greyed with their reason** |
| **23** | `Confirm and send` | p114–p116 | step 3, drawn ONCE, all six kinds |
| **24** | `Periods` | p116–p117 | the list builder, reached from 22.4 and 22.5 |

**The kind count and the kind names are confirmed from the drawing, six, and they are
the brief's six:** Interim · First bill · Final bill · Back-bill · Penalty · **Fee**.
Read off screen 21's own `WHAT EACH KIND WILL ASK YOU NEXT` table on p102, which lists
all six with what each asks for, and again off §04's front matter on p099 (*"five of the
six step-2 kinds"* + *"Fee — here, step 2 as screen 22.6"*).

**Step 2's shared spine, p101:** *"the same lettered spine on all six kinds — **A**
where, **B** what, **C** readings, **D** how it prices, then the kind's own group, and
last, always, the ⚠ block of what could still refuse. A kind that does not need a group
**keeps it and greys it with the reason on its face**; a step that changes shape between
kinds teaches nothing, and a group that vanishes looks like a bug."*

⚠ **p104's annotation says the other five kinds are this screen *"with groups removed"*,
and the FRAME on p113 greys them instead.** Both are the document's. The frame wins
(B14 rule 42 — build from the image): 22.6 draws `B`, `C` and `D` present and greyed,
each carrying *"Not asked, and that is not an omission. A fee has no usage, so there is
nothing to read and no plan to price it on."* p114's annotation settles it in words —
*"Three of the five groups are greyed with their reason on the face of them"*.

### The one rule this section obeys — and the product already honours it

**p100, verbatim:** *"There is no amount field, no description field and no line editor
— and the enforcement is that there is nowhere to put one."* The request object carries
no `amount`, `description` or `lines` member. *"The prototype drew step 2 with an
editable description, an editable amount and a `+ Add line` button; that is superseded
in writing."*

**The product is already right about this and it is NOT touched by this conversion.**
`OneTimeBody` has no such member, `api._one_time_request` does not read one, and the
docstring says so. The drawing restates it on step 3 as a sentence under group 1: *"The
lines are the kind's. There is no amount field and no parameter to pass one to."*

---

## 2 · THE CARRY-OVER MAP — built from the live screen, element by element

Every element `OneTimeBillTab.tsx` rendered before 2026-09-14, and its disposition.
**24 elements.**

| # | Element as it shipped | Disposition | Where it is now |
|---|---|---|---|
| 1 | `Search for the customer` + its helper | **UNCHANGED** | step 1 |
| 2 | `Customer account*` select | **UNCHANGED** | step 1 |
| 3 | `What kind of bill*` select, 5 options | **UNCHANGED** | step 1 (the drawn sixth is `DEF-BIL-5253`) |
| 4 | per-kind help under the kind select | **UNCHANGED** | step 1 |
| 5 | `Bill date (shows on the statement)` + helper | **UNCHANGED** | step 1 |
| 6 | `Period from*` / `Period to*` | **UNCHANGED** | step 1 |
| 7 | sub-period rows (back-bill · penalty) | **UNCHANGED** | step 1 |
| 8 | `Add another period` | **UNCHANGED** | step 1 |
| 9 | `Reason code*` + helper | **UNCHANGED** | step 1 |
| 10 | the read-only/RBAC courtesy banner | **UNCHANGED** | above the rail |
| 11 | the lede sentence | **UNCHANGED** | above the rail |
| 12 | the failure paragraph (`role="alert"`) | **UNCHANGED** | above the rail |
| 13 | `<h3>` *"Who is this bill for?"* | **RELABELLED** | the rail's step 1, `Who and when` |
| 14 | `See what they'd owe` button | **MOVED** | step 1's `Continue` — it runs the preview |
| 15 | `Create the draft bill` button | **MOVED** | step 3's commit, through `WizardFrame` |
| 16 | `OneTimePreviewPanel` whole | **MOVED** | step 2 |
| 17 | `<h3>` *"What they would owe"* | **MOVED** | step 2's heading |
| 18 | `OneTimeDraftPanel` whole | **MOVED** | step 3 |
| 19 | `GapNotes` (server-reported gaps) | **MOVED** | step 2 |
| 20 | `Sending the bill` absence panel | **MOVED** | step 3 — and it is **STALE**, `DEF-BIL-5252` |
| 21 | `Editing the charge lines` absence panel | **MOVED** | step 3 — **NEVER REMOVE** |
| 22 | `oneTimeAccountLabel` | **UNCHANGED** | same export, same call site |
| 23 | `oneTimeBodyFrom` | **UNCHANGED** | same export, one body for preview and draft |
| 24 | `subPeriodsComplete` | **UNCHANGED** | same export |

**The arithmetic: 24 = 20 UNCHANGED-or-MOVED-intact + 1 RELABELLED + 3 MOVED-and-recast
+ 0 REMOVED.** Nothing was deleted and nothing was rewritten. Both API calls, all seven
state hooks, both mutations, the validation predicate `canAsk`, every refusal and every
surviving locale key are the same objects in the same file.

**Two locale keys are orphaned by the relabel and the move, and neither is deleted in
this wave:** `billing.oneTime.step1` (*"Who is this bill for?"*, now the rail's label)
and `billing.oneTime.previewAction` (*"See what they'd owe"*, now what Continue does).
Retiring them is `i18n_fanin.retire`'s job and belongs with step 1's own rebuild, not
with the rail.

---

## 3 · REPRODUCE · LOCATE · BLAST RADIUS

**REPRODUCE.** ⚠ **The pre-change screen could not be re-captured from the running
stack, and the reason is this lane's own sequencing error:** the rail was written before
the track was corrected from Build to Maintenance, and a sibling lane rebuilt
`07-frontend/dist` at 11:27 with that change already in it. **Stated rather than
presented as captured.** The flat form's own measurement exists and is cited instead —
`CR-100-BRC03-diff-03-08.md` §04 walked it in a browser: 16 elements compared, **3
match · 4 differ · 9 absent**, and `CR-100-BRC03-walk.md:134` records the address
rendering with 0 console errors.

**LOCATE.** `App.tsx:1066` mounts `BillsListPage` at `billing/:tab`;
`BillsListPage.tsx:1211` renders `<OneTimeBillTab>` when `active === "one-time"`. One
mount, one file. The static `billing/pending`, `billing/print` and `billing/bills/:id`
routes are declared above it and never reach this tab.

**BLAST RADIUS, both directions.**
* **Inbound — one non-test consumer.** `BillsListPage.tsx:109` is the only import of
  `OneTimeBillTab` in the product. None of its five exported helpers is imported
  anywhere else; `features/customers/accountFinder.tsx:80` only *mentions*
  `oneTimeAccountLabel` in a comment, deliberately not importing it.
* **Outbound — what else uses what could have been removed.** `ArrivesWith` has 12+
  call sites across tenancy, assets and metering, so the stale `Sending the bill` panel
  is moved and filed, **never** fixed by touching the shared component. `GapNotes` is
  billing-local. `WizardFrame` is shared by 15 other wizards and is **used, not
  changed** — no prop added, no kit edit.

---

## 4 · PROVED IN A BROWSER

`reproduce-one-time.mjs`, Chromium, tenant `brazosbend`, at **1440 and 1280**.

* the rail renders three steps in the drawn order and the drawn words — `1 Who and when
  · 2 What we bill on · 3 Confirm and send`;
* Continue on step 1 issues `POST /billing/one-time/preview` and advances; the rail's
  step 1 turns `done` and step 2 `active`;
* step 2 renders the preview and the server's gap list; step 3 renders the draft panel,
  `Back`, and the commit;
* **the refusal path was exercised, not assumed.** An account with no unit returns
  **422 BIZ-COMPLETENESS** (*"account 'AC-2026-00051' has no unit"*) and the wizard
  **refuses to advance** — the rail stays on step 1. That is the correct behaviour and
  is the reason the first walk read as a failure;
* 0 page errors at either width.

Screenshots: `SCRATCH/one-time/step1-who-and-when-1440.png`,
`step2-what-we-bill-on-1440.png`, `step3-confirm-and-send-1440.png`.

---

## 5 · DIVERGENCES FROM THE DRAWING, RECORDED RATHER THAN BUILT

| # | The drawing | What is built | Why |
|---|---|---|---|
| D1 | page head `One-time bill`, sub-line `Nothing has been created yet`, action `Past one-time bills` | `h1` is `Billing`; no per-tab title, no such action | The page head is **shared by all seven tabs** and owned by `BillsListPage`. B14 rule 2 allows ONE page header per screen; a second one drawn inside the tab body would break it. Changing the shared head is a seven-tab change and is not this journey's to make |
| D2 | rail label `What we bill on` — four words | built as drawn | B14 rule 33 caps a LABEL at **3 words**. B14 rule 41 says the drawing is the scope and a drawn element contradicting a signed rule is the one thing that goes to the PO. **This is that one thing** — recorded here, not silently reworded |
| D3 | footer prose on the same line as `← Back` / `Continue →` | prose renders above the action row | `DEF-1083`: the PO said *"UI is broken at Park"* when a paragraph shared a line with the footer buttons, and the frame was fixed to put prose on its own line. B14 rule 38 — form construction is the UI rules' to decide |
| D4 | `← Back`, `Continue →` with arrows | `Back`, `Continue` | The kit's own labels, shared by 15 wizards. B14 rule 38 — a kit change is never local |
| D5 | 22.5's helper *"Edit the list on screen 24."* | not built (step 2 is a later wave) | B14 rule 31 — an internal screen number is never visible to a utility user. 22.4 draws the same affordance as a button, `Edit the period list →`, and that is the form to build |
| D6 | 23's group-3 footer *"…same guarantee as sign-off in §03"* | not built (step 3 is a later wave) | B14 rule 31, same reason — a document section reference is internal |
| D7 | group footer sentences that explain WHY (*"The address is walked to from the premises, never stored on the account."*, *"Shown here because these refuse at pricing"*) | to be dropped when those groups are built | B14 rule 33 — **rationale is ZERO words on screen**, and it is removed rather than shortened. PO, 2026-09-14: *"reduce the content to 5 to 6 meaningful words"* |

⚠ **D2 is the only one worth the PO's time**, and it is a four-word rail label against a
three-word cap. Everything else is rule 38 doing its job.

---

## 6 · WHAT REMAINS, AND WHAT BLOCKS IT

| Wave | Entry | State |
|---|---|---|
| 1 | the rail + routing | **DONE**, this record |
| 2 | `21 Who and when` — groups ①②③, read-only `Billed from`, the span helper, **`Days to pay`**, the six-kind table | **NOT BUILT.** `Days to pay` is blocked on `DEF-BIL-5251` — the field has nowhere to go until `api._one_time_request` reads `due_days` |
| 3 | `22.1`–`22.6` — the lettered spine, one screen per kind, greyed groups on `Fee` | **NOT BUILT.** `22.6 Fee` additionally needs `DEF-BIL-5253` — the kind does not exist in `ONE_TIME_KINDS` on either side |
| 4 | `23 Confirm and send` — the four groups, the specimen, the send options | **NOT BUILT.** The `Sending the bill` panel is removed *here*, with the drawn Send group in its place — `DEF-BIL-5252` |
| — | `24 Periods` — the list builder | **NOT BUILT.** Reached from 22.4 and 22.5, so it follows wave 3 |

**Nothing in waves 2–4 may reintroduce an amount field, a description field or a line
editor.** §04's one rule, and the product already honours it.
