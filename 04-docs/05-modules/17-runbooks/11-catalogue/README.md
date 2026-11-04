# Runbooks — the catalogue

**One file per runbook.** That is the whole point of this folder, and it is a Product Owner
instruction, verbatim (2026-09-06):

> *"each runbook details should be save in seperate folder or file so that later human developer can
> edit them easily"*

So a developer opens **one** file, edits **one** runbook, and touches nothing else. Each file is
self-contained: what the runbook declares, how its set is decided, its parameters, its steps in
order, its guards, what a run produces with the source's own figures, and its two screens.

## What is here, and what is not

| | Count | What each file carries |
|---|---|---|
| **Fully defined** | 22 | Scope, parameters, steps, guards, produces, and **both** screens drawn |
| **Reserved** (23–27) | 5 | Scope, parameters and steps **drafted from the catalogue**; the **result screen is not drawn** |
| **Defined by the build** (28, 33) | 2 | The source gave one sentence; **the build gave the rest, and every row it added is marked *(build)*** |
| **Named only** (29–32, 34–35) | 6 | A number, a home where one is stated, and **one sentence** saying what done looks like |
| **Total** | **35** | Numbered **1–36 with no 7** |

⚠ **RUNBOOKS 28 AND 33 MOVED OUT OF *NAMED ONLY* ON 7 SEPTEMBER 2026 AND THE
DISTINCTION MATTERS.** Their cards are no longer *"nothing below has been
inferred"*: scope, parameters, steps, guards and ports are now **this project's
judgments**, each marked *(build)* on the card and each recorded in
`12-governance/02-decision-log.md`. The commitment sentence is still the
source's own and is what the build was measured against. Both are **VERIFIED**
— a test first shown failing is what moved them (`RB-128`: 25 cases, `RB-133`:
24), which is what the *Every commitment reads UNVERIFIED* convention below
asks for. ⚠ **They are the only two cards that say VERIFIED**, and that is a
statement about the CARDS rather than about the code: several fully defined
runbooks are built and tested and their cards were never stamped.

⚠ **RUNBOOK 36 IS THE FIRST ADDED AFTER THE ORIGINAL 1–35, AND NOTHING IS RENUMBERED.** `RB-136` —
the accounting export — exists because the Product Owner's four integration areas (*accounting ·
payment provider · emails · GIS*) had a runbook for three of them and **not for accounting, which is
first on their list**. `01-overview.md` and `10-execution-plan.md` both said that gap needed a
fourteenth port; **that was superseded on 2026-09-06** and both are amended. The last two digits of a
definition id are still its runbook number.

**There is no runbook 7 and nothing is renumbered.** PO ruling, 5 September 2026: *keep the numbers as
given — 1 to 22 with no 7*. `RB-107` is unused for the same reason. The last two digits of a
definition id are its runbook number.

**An honest absence is the deliverable.** Where the source is silent — a trigger not declared, a
result not drawn, a home never written down — the file says so and stops. Nothing here has been
inferred to fill a gap.

## The index

| # | Name on screen | Definition title | Kind | Category | Phase | File |
|---|---|---|---|---|---|---|
| 1 | Can we bill? | Configuration check | Check | Platform | 1a | [`RB-101-configuration-check.md`](RB-101-configuration-check.md) |
| 2 | Cutover reconciliation | Ready for cutover? | Check | Onboarding & Cutover | 1d | [`RB-102-ready-for-cutover.md`](RB-102-ready-for-cutover.md) |
| 3 | Pre-bill sweep | Ready for billing? | Check | Billing | 1c | [`RB-103-ready-for-billing.md`](RB-103-ready-for-billing.md) |
| 4 | Why is this bill higher? | Why is this bill higher? | Check | Billing | 3 | [`RB-104-why-is-this-bill-higher.md`](RB-104-why-is-this-bill-higher.md) |
| 5 | Abnormal readings | Abnormal readings | Check | Reads | 3 | [`RB-105-abnormal-readings.md`](RB-105-abnormal-readings.md) |
| 6 | Why did this account not bill? | Why did this account not bill? | Check | Billing | 3 | [`RB-106-why-did-this-account-not-bill.md`](RB-106-why-did-this-account-not-bill.md) |
| 8 | Collections ladder | Dunning and notices | Action | Collections | 2a dry · 2b live | [`RB-108-dunning-and-notices.md`](RB-108-dunning-and-notices.md) |
| 9 | Books tie-out | Month-end completion | Check | Finance | 1d | [`RB-109-month-end-completion.md`](RB-109-month-end-completion.md) |
| 10 | Cash application | Cash application | Action | Payments | 2c | [`RB-110-cash-application.md`](RB-110-cash-application.md) |
| 11 | Leak and high-usage alert | Leak and high-usage alert | Action | Reads | 2c | [`RB-111-leak-and-high-usage-alert.md`](RB-111-leak-and-high-usage-alert.md) |
| 12 | Disconnect eligibility | Disconnect eligibility | Check | Collections | 3 | [`RB-112-disconnect-eligibility.md`](RB-112-disconnect-eligibility.md) |
| 13 | Payment trace | Payment trace | Check | Payments | 3 | [`RB-113-payment-trace.md`](RB-113-payment-trace.md) |
| 14 | Bank reconciliation | Bank reconciliation | Action | Finance | 2c | [`RB-114-bank-reconciliation.md`](RB-114-bank-reconciliation.md) |
| 15 | Deposit review | Deposit review | Action | Collections | 3 | [`RB-115-deposit-review.md`](RB-115-deposit-review.md) |
| 16 | Rate change preview | Rate change preview | Check | Plans & Rates | 3 | [`RB-116-rate-change-preview.md`](RB-116-rate-change-preview.md) |
| 17 | Autopay pre-notification | Autopay pre-notification | Action | Payments | 2c | [`RB-117-autopay-pre-notification.md`](RB-117-autopay-pre-notification.md) |
| 18 | Vacant premises with usage | Vacant premises with usage | Check | Service points | 3 | [`RB-118-vacant-premises-with-usage.md`](RB-118-vacant-premises-with-usage.md) |
| 19 | Data hygiene | Data hygiene | Check | Data Hygiene | 3 | [`RB-119-data-hygiene.md`](RB-119-data-hygiene.md) |
| 20 | GIS reconciliation | GIS reconciliation | Action | Data Sync | 3 | [`RB-120-gis-reconciliation.md`](RB-120-gis-reconciliation.md) |
| 21 | Read exceptions | Read validation on arrival | Action | Data Sync | 3 | [`RB-121-read-validation-on-arrival.md`](RB-121-read-validation-on-arrival.md) |
| 22 | Undeliverable contacts | Undeliverable contacts | Action | Data Sync | 2c | [`RB-122-undeliverable-contacts.md`](RB-122-undeliverable-contacts.md) |
| 23 | Test bill | Test bill · **reserved** | Check | Billing | 1b | [`RB-123-test-bill.md`](RB-123-test-bill.md) |
| 24 | Coverage grid | Coverage grid · **reserved** | Check | Billing | 1b | [`RB-124-coverage-grid.md`](RB-124-coverage-grid.md) |
| 25 | Payment plans | Payment plans · **reserved** | Action | Collections | 2c | [`RB-125-payment-plans.md`](RB-125-payment-plans.md) |
| 26 | Returned payments | Returned payments · **reserved** | Action | Payments | 2c | [`RB-126-returned-payments.md`](RB-126-returned-payments.md) |
| 27 | Move-outs | Move-outs and final bills · **reserved** | Action | Accounts | 2c | [`RB-127-move-outs-and-final-bills.md`](RB-127-move-outs-and-final-bills.md) |
| 28 | Meters past change-out age | Meters past change-out age or never tested · **defined by the build** | Check | **Assets** | later | [`RB-128-meters-past-change-out-age-or-never-tested.md`](RB-128-meters-past-change-out-age-or-never-tested.md) |
| 29 | *not stated* | Overdue field orders · **named only** | *not stated* | Work | later | [`RB-129-overdue-field-orders.md`](RB-129-overdue-field-orders.md) |
| 30 | *not stated* | Portal and autopay adoption · **named only** | *not stated* | Customer portal | later | [`RB-130-portal-and-autopay-adoption.md`](RB-130-portal-and-autopay-adoption.md) |
| 31 | *not stated* | Revenue at risk and aging trend · **named only** | *not stated* | Business | later | [`RB-131-revenue-at-risk-and-aging-trend.md`](RB-131-revenue-at-risk-and-aging-trend.md) |
| 32 | *not stated* | Flight results landed · **named only** | *not stated* | *not stated* | later | [`RB-132-flight-results-landed.md`](RB-132-flight-results-landed.md) |
| 33 | Budget billing re-level | Budget billing re-level · **defined by the build** | Action | Billing | 3 | [`RB-133-budget-billing-re-level.md`](RB-133-budget-billing-re-level.md) |
| 34 | *not stated* | Storm mass-send · **named only** | *not stated* | *not stated* | 3 | [`RB-134-storm-mass-send.md`](RB-134-storm-mass-send.md) |
| 35 | *not stated* | Service-request chase · **named only** | *not stated* | *not stated* | later | [`RB-135-service-request-chase.md`](RB-135-service-request-chase.md) |
| 36 | Month-end journal file | Accounting export | Check | Finance | 1d | [`RB-136-accounting-export.md`](RB-136-accounting-export.md) |

Runbook 33's kind and category are not in the definitions document at all — they are read off the
Templates wireframe (`RBS-002`, region 9: *pills: Action (danger), Unavailable (neutral) · Action
Billing*), and that is the only place either is written down.

Runbook 28's kind was **conditional** and is now resolved: the source says it *"waits on `RB-049`
for a field order, and is a Check without it"*, `RB-049` does not exist, so it is built as a Check —
holding no ports at all. `RB-128`'s own docstring writes out what it becomes the day a field order
arrives, so the next lane does not have to re-derive it.

**Checks 13 · Actions 9** among the twenty-two defined — runbook 36 is the thirteenth Check.
With runbooks 28 and 33 defined by the build (2026-09-07) that becomes **Checks 14 · Actions 10**
across the twenty-four cards that carry steps.

## The catalogue display names — C1 to C12

The specification's catalogue numbered twelve runbooks 1 to 12 while the rest of the work numbers
twenty-one 1 to 22. The catalogue rows are now **C1 to C12 with no wording changed**. The catalogue
name is the **display name a clerk sees** on the templates library and in every wireframe; the
definition title is the runbook's name on its card. Both are kept, and this is the one table where
they meet.

| Catalogue row | Display name on screen | Runbook | Definition title | Spec id |
|---|---|---|---|---|
| C1 | Can we bill? | 1 | Configuration check | `RB-101` |
| C2 | Test bill | 23 | Test bill · new definition reserved | `RB-123` |
| C3 | Coverage grid | 24 | Coverage grid · new definition reserved | `RB-124` |
| C4 | Pre-bill sweep | 3 | Ready for billing? | `RB-103` |
| C5 | Cutover reconciliation | 2 | Ready for cutover? | `RB-102` |
| C6 | Books tie-out | 9 | Month-end completion | `RB-109` |
| C7 | Collections ladder | 8 | Dunning and notices | `RB-108` |
| C8 | Payment plans | 25 | Payment plans · new definition reserved | `RB-125` |
| C9 | Returned payments | 26 | Returned payments · new definition reserved | `RB-126` |
| C10 | Undeliverable contacts | 22 | Undeliverable contacts | `RB-122` |
| C11 | Move-outs and final bills | 27 | Move-outs and final bills · new definition reserved | `RB-127` |
| C12 | Read exceptions | 21 | Read validation on arrival (the scheduled variant for a utility without interval meters) | `RB-121` |

Phase 1 is C1–C6, all six of them Checks that cannot write. Phase 2 is C7–C12, all six of them
Actions, every one gated. **1 to 35 stays canonical**; C1–C12 is a display-name block, not a second
numbering.

## Categories — sixteen, eleven in use

A runbook has **exactly one** home category, taken from a fixed list held in code, never free text.
Anything else it touches is a **tag**. Three things read the home: the template library filters by
it, role visibility defaults from it, and it names the **owning module whose ports the runbook may
call**. That third use is what makes a category an engineering fact rather than a label.

| Category | Runbooks | Count | Owning module | Also touched by, or its first runbook |
|---|---|---|---|---|
| Platform | 1 | 1 | tenancy | 2 |
| Onboarding & Cutover *(added)* | 2 | 1 | tenancy · the cutover plan in operations | — |
| Data Hygiene | 19 | 1 | customers · metering, read only | 22 |
| Service points | 18 | 1 | metering — premises and units | 1, 11, 19, 20 |
| Plans & Rates | 16 | 1 | rating | 1 |
| Assets | **28** | 1 | metering — assets | touched by 5 — and runbook 28 is the first, landed 2026-09-07, so the chip is drawn |
| **Accounts** | **none yet** | 0 | customers | touched by 6 · 15 · 17 · 19 · 22 · first runbook: *Move-outs and final bills* |
| Reads | 5 · 11 | 2 | metering | 3, 18, 21 |
| Billing | 3 · 4 · 6 · 33 | 4 | billing | 2, 9, 16 |
| Collections *(added)* | 8 · 12 · 15 | 3 | payments — the ladder lives in its settings | — |
| Payments | 10 · 13 · 17 | 3 | payments | 8, 9, 14 |
| Finance | 9 · 14 | 2 | ledger | 10, 15 |
| **Work** | **none yet** | 0 | work | touched by 12 · first runbook: *Field orders overdue* |
| **Customer portal** | **none yet** | 0 | customers — the portal | touched by 4 · 11 · 13 · first runbook: *Paperless and autopay adoption* |
| **Business** | **none yet** | 0 | reports | touched by 18 · first runbook: *Revenue at risk, and the aging trend* |
| Data Sync | 20 · 21 · 22 | 3 | integrations | — |

**FOUR categories are empty — Accounts, Work, Customer portal and Business — and an empty
category is never drawn.** A chip that filters to nothing is dead UI. A new category needs three
runbooks that fit nowhere else; a runbook that fits nowhere is filed under its nearest neighbour and
tagged.

⚠ **THAT SENTENCE SAID *FIVE* AND NAMED ASSETS UNTIL 2026-09-07**, when runbook 28 landed as that
category's first. The chip row is built from the templates PRESENT (`BR-RBS-025`), so Assets draws
one now and this line had to move with it — landing a runbook and updating the count of empty
categories are two acts, and only the first feels like the work.

Two categories were **added** to the fourteen we were given. *Onboarding & Cutover* runs once per
utility and should sort first before go-live and last after it; nothing else behaves that way.
*Collections* holds three runbooks that share the collections ladder and the same gate on money owed,
and a collections clerk is not a cashier. *Communications* was **declined**: runbooks 8, 17 and 22 all
queue notices, but a notice is the channel a runbook uses, not the question it answers — so it stays
a tag.

**Note on authorship.** The sixteen-category ruling is split: the Product Owner supplied fourteen
category names on 5 September 2026; the two additions, the declined third, and the rules (one home,
tags for the rest, three runbooks for a new category, an empty category never drawn) are **the
specification's own decisions, not the PO's**, recorded so they are visible to overrule.

## Every runbook's home and its tags

The source's tag table covers **runbooks 1–22 only**. For 23–35 the tags are not stated.

| # | Home | Also touches |
|---|---|---|
| 1 | Platform | Plans & Rates · Service points |
| 2 | Onboarding & Cutover | Platform · Billing |
| 3 | Billing | Reads |
| 4 | Billing | Customer portal |
| 5 | Reads | Assets |
| 6 | Billing | Accounts |
| 8 | Collections | Payments · notices |
| 9 | Finance | Billing · Payments |
| 10 | Payments | Finance |
| 11 | Reads | Customer portal · Service points |
| 12 | Collections | Work |
| 13 | Payments | Customer portal |
| 14 | Finance | Payments |
| 15 | Collections | Finance · Accounts |
| 16 | Plans & Rates | Billing |
| 17 | Payments | Accounts · notices |
| 18 | Service points | Reads · Business |
| 19 | Data Hygiene | Accounts · Service points |
| 20 | Data Sync | Service points |
| 21 | Data Sync | Reads |
| 22 | Data Sync | Accounts · Data Hygiene |

## The screens, and how the codes map

Every runbook is **two instances of two renderers**, not two pages of its own:

| Screen | Renderer | Per-runbook instance | Frames drawn |
|---|---|---|---|
| Runbook detail / setup | `RBS-004` | `RBS-004-Rn` | 26 — runbooks 1–27, no 7 |
| Run result | `RBS-006` | `RBS-006-Rn` | 21 — runbooks 1–22, no 7 |

Both live in [`../wireframes/`](../wireframes/), each `.png` beside its `.md` build sheet. **The build
sheet is the acceptance check**: regions in order, copy verbatim, component, size, state and tone. A
region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or
layout*, filed with the screen code and the region number.

Runbooks 23–27 have a setup frame and **no result frame**. Runbooks 28–35 have **neither** —
including 28 and 33, which are built and need none: both screens are RENDERERS over the
definition and the report, so neither runbook shipped a line of frontend code.

> **The source documents number these screens `S150-Rn` and `S152-Rn`.** This repository numbers them
> `RBS-004-Rn` and `RBS-006-Rn` — PO ruling 2026-09-06, verbatim: *"Screens S147–S154 - this should be
> RBS-nnn"*. Nothing in the source documents is renamed, so each catalogue file records the source's
> own code beside the repository's and the cross-reference survives. The full mapping: `S147`→`RBS-001`
> Runbooks home · `S148`→`RBS-002` Templates · `S149`→`RBS-003` My runbooks · `S150`→`RBS-004` Runbook
> detail · `S151`→`RBS-005` Run wizard · `S152`→`RBS-006` Run result · `S153`→`RBS-007` Work list ·
> `S154`→`RBS-008` Run history.
>
> **Searching for a screen code needs a lookbehind as well as a lookahead.** The module code is also
> `RBS`, so a screen is `RBS-001` while a rule is `BR-RBS-001`, a story `US-RBS-001` and a test
> `TC-RBS-001`. The pattern is `(?<![A-Z]-)RBS-\d{3,5}(?!\d)` and **both** assertions are load-bearing.

## Conventions every file obeys

- **A Check cannot write.** It is constructed with **no ports**, so a write is not refused at runtime —
  it is unavailable (`BR-RBS-002`, `TC-RBS-1`). An Action holds an allow-list drawn from the thirteen
  named ports, each one service function in its owning module.
- **Two things the engine does that no runbook may:** raising work items and writing audit rows. That
  is how a Check populates the work list and still has no writer.
- **Policy lives in Settings and is never duplicated on a card.** A Settings-owned parameter is drawn
  dashed and read-only with *"Open settings →"*. A runbook owns only what is about *this run*: how
  many, which channel, how strict, when.
- **Money is stored to 4 decimals and shown to 2. Percentages are stored to 6 and shown to 2. Rates
  carry 4 decimals.** `CHAR(3)` currency, never float, never cents.
- **The word is *Queued*, never *Sent*** — no delivery provider is connected (PO ruling, 17 August
  2026). Nothing leaves the building today.
- **Every figure in these files is an illustrative fixture**, not a finance-signed number. None is
  frozen. But the tables on the screens add up to them, so moving one is still an error.
- **Every commitment reads UNVERIFIED** until a test that was *first shown failing* proves it. A green
  with no red behind it is a defect in the test.

## Two places the two source documents disagree

Recorded here rather than resolved, because resolving either is a ruling and not a transcription.

**1 · Four ports, or thirteen — and is *raise a work item* one of them?** The specification's
write-routes callout (section B2, route 2) says an Action reaches its owning module through *"four
named calls into the owning module's service: queue a notice, flag an account, raise a work item,
apply a fee"*, and five further places repeat *"the four port seams"* — including story `US-RBS-041`
and commitment `RB-052`. But section B2b's own table is headed **"Ports — the allow-list, thirteen
today"** and lists thirteen, `RB-017` commits to *"thirteen ports"*, and **none of the thirteen is
`raise_work_item`** — because B2b states in the opposite direction that *"raising work items and
writing audit rows are **engine acts, not ports**"*, which is exactly how a Check populates the work
list and still has no writer. **These catalogue files follow the thirteen-port table**, name each
runbook's ports from it, and treat raising work items as the engine's act. If four is right, every
`Ports it holds` row here is wrong.

**2 · An event trigger, or a daily schedule — runbooks 10, 11 and 14.** The specification's coverage
table gives cash application *⚡ Payments landed*, the leak alert *⚡ Intervals landed* and bank
reconciliation *⚡ Statement landed*, and its trigger table lists all three under `batch.landed`. Each
runbook's own definition card carries a `Runs` parameter reading **Daily 06:30**, **Daily 07:30** and
**Daily 07:00** instead. Runbooks 20, 21 and 22 agree across both documents (*when the batch lands*),
so the disagreement is confined to these three. **Both readings are recorded in each of the three
files**, neither is chosen here.

## Where the rest of it lives

| | |
|---|---|
| Wireframes and build sheets | [`../wireframes/`](../wireframes/) — 75 frames, 75 sheets |
| The four rulings of 2026-09-06 | `12-governance/02-decision-log.md`, the newest rows |
| The change request | `CR-075` |
| The module's screens, contract and phases | the Runbooks specification (sections A2, A3, B2b, B10) |

---

Built from the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026;
build sheets added 6 September 2026) and the Runbooks specification. Every figure is the source's own.
Where a source says nothing, these files say nothing — and say that they say nothing.
