# CR-094 · Lane E — the two CREATION wizards, measured against their drawings

**Scope:** `S18` New account wizard (`/:tenant/accounts/new`) and `S87` New connect
wizard (`/:tenant/connections/new`). Both CREATE something rather than acting on an
existing account, which is why neither fell inside the 22 account actions already
walked.

**Excluded, and said so rather than left to be inferred:** the New connects TAB, the
build record `/:tenant/connections/cx-…`, its two dialogs (*Activate units*, *Add a
work order*) and the service-request capture page. All four are drawn inside
`07-new-connect-wizard.md` and none of them lives in this lane's two files.

**Source of the drawing.** PO ruling 2026-09-13, verbatim: *"When you use images to
create screens your accuracy is higher; hence dont create screens using only Text"*.
Measured from the rendered PAGE IMAGES at scale 2 (2448×1584) —
`accounts.pdf` pages **60–65** (new account) and **86–97** (new connect) — with the
extracted markdown used only as an index. Three facts below are visible in the image
and absent from the text layer: the two-column form grid on step 1, the two-column
review on step 5, and `Save & exit` sitting in the PAGE HEAD rather than the footer.

**As-built measured** in a browser against the booted stack at **1280 and 1440**,
`v2.261.0`, walkthrough `10-scripts/render-checks/creation-wizards-conformance.mjs`.

---

## 1 · The drawing, quoted

### New account — the ruling that shapes the whole screen

> **Five steps, not six — the plan step is gone**
>
> The product draws a whole step for the plan, and its own copy explains why it
> should not: *"the plan is read from the unit and is not stored on the account"*,
> *"shown, not stored"*, and then the warning *"pick a unit first if this reads
> empty"*. A step of a six-step wizard carrying no input, whose only value is
> derived from the step before it.
>
> PO ruling: *"there should not be any step to select a plan as plan is already
> attached on the unit itself. So whenever the unit is selected, show all the
> details."* So the unit step now carries the unit's whole record — its plan,
> version, lock and base charge among it — and the clerk sees what the account will
> inherit **before** committing to the unit rather than two clicks later. **Every
> drawing below is the wizard as it should be, not as it is.**

Five screens, each with a kicker `NEW ACCOUNT`, its own H1, a step line, a
`Save & exit` button top-right, and a five-cell rail:

| Step | H1 (drawn) | Step line (drawn) | Rail cell (drawn) |
|---|---|---|---|
| 1 | Create a first-time customer account. | `Step 1 of 5 · Customer` | 1 Customer |
| 2 | Which unit? | `Step 2 of 5 · Unit` | 2 Service address |
| 3 | Account preferences | `Step 3 of 5 · Account preferences` | 3 Account preferences |
| 4 | Deposit | `Step 4 of 5 · Deposit` | 4 Deposit |
| 5 | Review | `Step 5 of 5 · Review` | 5 Review |

⚠ **The rail cell and the step line disagree on step 2 — `Service address` against
`Unit` — and BOTH are drawn.** The rail spells `Service address` identically on all
five frames; the step line spells `Unit` on the one frame that names step 2, and the
review block heading reads `SERVICE ADDRESS AND UNIT · STEP 2`. Rule 37 settles two
frames disagreeing about a FIGURE and this is a LABEL, so it does not apply. Built as
drawn, both of them, and recorded here so the next lane does not read one as a typo
for the other.

**Step 2, the panel that replaces the deleted step** — `Unit A, 1408 Elm Street —
everything this unit carries`, two columns of label/value rows, closing with
*"Nothing on this panel is an input."*

| Left | Right |
|---|---|
| Unit number `U-000912` | Parcel `—` |
| Label `Unit A` | Plan `SCW-RES · Sample — Residential · v1` |
| Unit type `Duplex — half` | Plan in force since `06/01/2026` |
| Floor `Ground` | Plan locked `No` |
| Floor area `1,120 sq ft` | Base charge `$20.00 a month` |
| Premises `1408 Elm Street · PR-0402` | Bill the owner when vacant `No` |
| Service address `1408 Elm Street, Silver Creek, TX 78611` | Meters `M-4021 · M-4022` |
| Map point `Reads the building's` | Services available `ELECTRIC WATER` |

Beside the picker, above the panel: `Services  Electric · Water`, `Meters at unit
M-4021 · M-4022`, and a dashed `INITIAL READS / Not captured here — reads commit
through metering's own batch path.`

**Step 3** is four titled sections — `How the bill is delivered` · `Paying` · `Tax` ·
`Language` — opening with a red banner: *"A bill is always printed. Paperless and text
reminders are extra channels on top of the paper, not instead of it — neither of them
switches the printed bill off."* Then `✓ Paperless billing — email a copy of every
bill`, `Text reminders — when a bill is issued, and before it falls due`, `Autopay`,
`✓ Tax exempt` + `Tax-exempt reference` + `Expires`, `Preferred language`.

**Step 5** is two columns of review blocks, each headed `NAME · STEP n` with an
`Edit →` on the right: CUSTOMER·1, SERVICE ADDRESS AND UNIT·2 (left); ACCOUNT
PREFERENCES·3, DEPOSIT·4, DEPOSIT PAYMENT·4 (right). Then a full-width box *"What
will be on the account the moment it is created"*, then *"What goes out to the
customer"* (a six-column send table + a template picker), then *"And how should it be
saved?"*.

### New connect

> `/:tenant/connections/new · S87 · eight steps — the longest flow in the product`
>
> **Two steps, merged, because they are one question.** Who is asking and what they
> are building were never separable: the scope decides how many units the next steps
> ask for, and the owner is who they are created against.

| Step | H1 (drawn) | Rail cell (drawn) |
|---|---|---|
| 1 | Who is asking, and what for? | Owner & scope |
| 2 | The premise | Premise |
| 3 | The units | Units |
| 4 | Which services per unit | Map services |
| 5 | Plans & work orders | Plans & work orders |
| 6 | Charges | Charges |
| 7 | Telling the customer | Communication |
| 8 | What will be created | Review & confirm |

---

## 2 · The as-built, censused

**New account — six steps.** Rail: `1 Customer · 2 Service address · 3 Plan ·
4 Billing prefs · 5 Deposit · 6 Review`. One H1 on every step
(*"Create a first-time customer account."*, 32px, correct per rule 40). No step line.
No `Save & exit`. Subtitle: *"Six steps. Someone moving into a unit whose last tenant
has already moved out has a guided page of its own — use Move-in on that closed
account."* — 30 words in one sentence, with the count written out in English.

Step 2 renders the picker, the start date, two fact rows and the initial-reads note —
and **none** of the unit record. Step 3 (Plan) renders two fact rows and an
`ArrivesWith`. Step 4 offers Autopay, Preferred language, Tax exempt, and a block
headed *"Preferences this account cannot hold"*. Step 6 is a flat list of eight rows
with no block, no step attribution and no `Edit →`.

**New connect — nine steps.** Rail: `Owner & build · Scope & mode · Premise · Units ·
Map services · Plans & work orders · Charges · Communication · Review & confirm`. One
H1 on every step (*"Establish service at a new address"*). The line under the title
reads `Step N of 9 · nothing is written until step 9. Everything below is a draft
until you press Create connection.` — the step's NAME replaced by a 20-word
instruction.

---

## 3 · Diff, both directions, and how each is routed

### Drawn and absent — BUILT this wave

| # | What | Where |
|---|---|---|
| B1 | Six steps → five; the Plan step deleted, its check moved into step 2 | account |
| B2 | Rail cell 4 `Billing prefs` → `Account preferences` | account |
| B3 | A per-step H1, all five drawn titles | account |
| B4 | `Step N of 5 · <name>`, derived from the step list, shared key | account |
| B5 | The 30-word hardcoded-count subtitle removed | account |
| B6 | Step 2's `everything this unit carries` panel, 16 drawn rows | account |
| B7 | `Government ID` → `Government id`; `Person or company` → `Customer kind` | account |
| B8 | Step 3's four section headings + the printed-bill fact | account |
| B9 | **Paperless billing** and **Text reminders** — real, writable, wired | account |
| B10 | Step 5's five review blocks, each with `· STEP n` and `Edit →` | account |
| B11 | `Step N of 9 · <name>`, derived; the instruction moved off the line | connect |
| B12 | A per-step H1, all nine | connect |

### Drawn and absent — ROUTED, not built

| id | What | Why not here |
|---|---|---|
| `DEF-CUS-5186` | Connect draws 8 steps; product has 9 | `NEW_CONNECT_STEPS` lives in `newConnectShared.tsx`, read by 13 files. Outside this lane's file set; half-doing it would make the rail and the parked-draft row disagree |
| `DEF-CUS-5190` | `Save &amp; exit` on all five account screens | The park registry is `wizardPark.ts` + `parkedDrafts.tsx`; `new_account` is not in it |
| `DEF-CUS-5191` | Step 2 `Parcel` row | Not served: the unit payload carries no parcel. Stated as an absence rather than invented |
| `DEF-CUS-5192` | Review's *What goes out to the customer* table + template picker; connect step 6's quote, payer and payment | No endpoint serves either from a wizard draft |
| `DEF-CUS-5193` | Connect step 4's per-unit services grid | The drawing says *"Per unit is not an alternative shape — it is the shape"*; the product offers apply-to-all and says per-unit *"is not built yet"* |

### On screen and NOT drawn

Step 3's *"Preferences this account cannot hold"* block named **paperless** and
**SMS** among four unbuilt columns. Two of the four have been built and writable since
**2026-08-31** (`CR-052` task 14, migration `customers/0034`, both in `CREATE_FIELDS`).
The sentence was true when written, expired thirteen days ago, and nothing re-read it —
hard-won law 2's mirror, a live door behind a dead refusal. `DEF-CUS-5184`. The block
now names only `budget billing` and `statement language`, which are still PROPOSED-SCHEMA.

---

## 4 · Rules this was built under

* **41** — the product UI matches the blueprint exactly. Nothing here contradicts a
  signed rule, so nothing goes to the PO.
* **38** — the drawing's two-column form grid on step 1 and its `Save as` SELECT are
  CONSTRUCTION; the UI rules win and the kit's one-per-row fields stand. What the form
  CONTAINS is the drawing's and is built.
* **37** — no drawn figure asserted. `U-000912`, `$20.00`, `1,120 sq ft`,
  `M-4021` are illustrations; every test reads what the fixture served.
* **33** — the account subtitle (30 words, one sentence) and the connect step line
  (20 words) both broke the six-word instruction cap and both are gone. `Plan in force
  since` is four words and is the drawing's own; kept, and recorded here.
* **31** — checked every field of both wizards: `rate_plan_id` is a UUID and is
  **never** rendered. The panel's Plan row reads `code · name · v{version}` from
  `GET /units/{id}/pricing`.
* **21** — `NewAccountWizard.tsx` is **NOT** on `route-b-migrated.txt`, so G31 owns it
  and every class it names is one `customers.css` already declares; no utility, no new
  class, no migration as a side effect. `NewConnectWizard.tsx` **IS** listed, so its
  new markup is Tailwind utilities only.
* **36** — `Panel`, `FactList`, `Fact`, `ServiceTags`, `CheckboxField`, `Note`,
  `RefusalStrip` and `WizardFrame` were already imported by these files. Nothing new
  was written that the kit had.
* **hard rule 8** — the unit panel walks to the premises for its address
  (`premise_address`, `premise_no`) and declares none of its own. `Map point` names
  which of the two points it is showing, per `BR-MET-1162`.

---

## 5 · What was BUILT, measured after — step 2 of the process

`v2.261.3`. Walked end to end in a browser at **1280 and 1440** against the
booted stack — step 1, pick a unit, tick both channels, through the deposit to
the review — not deep-linked, because a deep link never exercises the panel that
only appears once a unit is chosen.

| # | Built | Proof |
|---|---|---|
| B1 | Five steps; the Plan step deleted | rail reads `Customer · Service address · Account preferences · Deposit · Review` |
| B2 | Rail cell 3 `Billing prefs` → `Account preferences` | all eleven catalogues |
| B3 | A per-step H1 on every screen of both wizards | `Which unit?` · `Who is asking?` · `The premise` · … |
| B4 | `Step N of 5 · <name>`, derived | `Step 2 of 5 · Unit`, and `Step 1 of 9 · Owner & build` on the connect |
| B5 | The 30-word hardcoded-count subtitle removed | page head is kicker + title + step line |
| B6 | Step 2's unit panel, fourteen rows, two columns | screenshot at 1440; plan read through `GET /units/{id}/pricing` |
| B9 | Paperless + text reminders, wired both ways | review reads `Paperless billing · On, to lane.e@example.test` |
| B10 | Five review blocks with `· STEP n` and `Edit →` | `CUSTOMER · STEP 1 · Edit →` … |
| B11/B12 | The connect wizard's step line and nine titles | every step names itself |

### Three defects I put on the screen myself, found by looking at it

Every one passed `tsc`, every test and every gate, because **no check in this
repo reads rendered output** (hard-won law 6).

1. **`Base charge` rendered `20.000000`** — six decimals of a monthly charge.
   Hard rule 2 is four stored, **two displayed**. Fixed through the kit's
   `formatMoneyInput`, which is the one of the money pair that does not demand a
   currency this wizard has not got (`DEF-CUS-5114`). **No symbol is invented.**
2. **`Unit type` rendered `residential_submetered`** — a database code in
   clerk-facing copy, which B14 rule 32 forbids by name. Reads through
   `metering.units.type.*`, the map `AddPremisesWizard` already uses; an
   unmapped code still falls back to the CODE and never to an invented word
   (`DEF-684`).
3. **Two rows on one step were both labelled `Services`.** The panel's row took
   the drawing's fuller `Services available`.

### Two stale sentences the first commit did not reach

Wiring paperless corrected the **code comment** above the controls and left the
**sentence a clerk reads** saying both "were never built", in eleven languages,
under two working controls. And the review promised the create "does not write
… a deposit", which it has written since the shared deposit step landed. Both
rewritten. **The lesson is the shape:** a refusal lives in a catalogue, not in
the file that renders it, so correcting the code is half the fix.

### Three headings this pass had to REMOVE

Giving each step its own title left `Which unit?` above *"Pick the unit they'll
be billed for"* — the same sentence twice, on steps 2, 3 and 5. **A per-step
title is not additive; it replaces something**, and the cost has to be paid in
the same commit or the screen gets worse rather than better.

## 6 · Knowingly LEFT, with the reason

| What | Why |
|---|---|
| `Government ID` → the drawn `Government id`, and `Person or company` → the drawn `Customer kind` | Both are SHARED catalogue values. `field.govId` is the account detail screen's; `field.customerKind` is read by the move-in and transfer wizards, and a sibling lane is in one of them right now. Changing a shared value to match one drawing changes three screens on one screen's authority |
| `Save & exit` on the account wizard | Needs a `new_account` entry in `wizardPark.ts` / `parkedDrafts.tsx` — `DEF-CUS-5190` |
| The paperless control DISABLED with no email | `CheckboxField` takes no `disabled` prop, so `BR-SHL-025` cannot be honoured on ANY checkbox in the product — `DEF-CUS-5197`. The election is refused where the payload is BUILT instead, and the reason is said under the control |
| `$20.00 **a month**` | The base charge's PERIOD is not served. `UnitPricingPanel`'s own note says no period is invented, and this panel keeps that rule |
| The drawn `Service address` row (full address with locality) | The unit payload carries `premise_address` — line 1 only. `Premises` shows what is served |
| `Meters at unit` (drawn) vs `Meters at this unit` (built) | An existing key, one word longer, read by nothing else that would break. Recorded rather than churned |
| The connect wizard merged to eight steps | `DEF-CUS-5186` — the step list is a shared file |

## 7 · Reds NOT caused by this lane, each dated

* **`screenVoice.guard.test.tsx`** fails `tsc`: `dateFormat` missing on the
  transfer step. **Not on the branch at all** — the tip's copy of that test has
  ZERO occurrences of `dateFormat`, and `TransferWizard.tsx` carries **+759/−103
  uncommitted lines** from a sibling lane in this shared tree. A sibling's
  in-flight edit, today (2026-09-13); `git diff --numstat <tip> -- TransferWizard.tsx`
  is the evidence.
* **`TransferWizard.test.tsx`** errored on `categoryName` during the same window
  and stopped erroring twenty minutes later without anyone touching it — the
  same lane saving. Same cause, same date.
* Everything the brief listed as pre-existing —
  `AccountDetailPage.test.tsx`, `accountRailHoldExpiry.test.ts`,
  `regionalReachesTheScreen.dom.test.tsx`, `G15`, `G18`, `G33` — was **not
  re-verified by this lane**, and that is said rather than implied: the four
  checks this lane was asked to keep green were run and are green, and a red
  nobody re-read is exactly what hard-won law 7 warns about.

## 8 · The four required checks, after

```
npx tsc --noEmit                                    0 errors in either of this lane's files
TAB=overview acc02-tab-conformance.mjs              0 divergence(s)
account-dialog-fit.mjs                              26 frame(s), 0 finding(s)
g27_translation_keys.py                             every key resolves in en.json
```
