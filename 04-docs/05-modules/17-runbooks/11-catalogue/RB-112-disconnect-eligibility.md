# RB-112 — Runbook 12 · Disconnect eligibility

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Collections |
| **Tags** | Work |
| **Phase** | 3 |
| **Trigger** | Manual |
| **Subject and unit of work** | Account · last tier |
| **Step modes** | per record |
| **Result blocks it composes** | Verdict · KPIs · Records · Action (approve list) · Downloads |
| **Ports it holds** | — (a Check holds none; the approval is engine-owned, and a crew acts through the Work module) |
| **Proves** | US-RBS-024 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: who is actually eligible for disconnection today — and who must not be on the list. Scope is the accounts at the last tier of the ladder. This is a Check: it produces a field list a person signs. Nothing here disconnects anyone.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Accounts at | Last tier · certified letter sent | read-only, Settings-owned (dashed) |
| Service | Water | dropdown |
| Never include | Medical · Dispute · Plan in good standing · Sample | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Matches 23 accounts today.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Notice period | From Settings · 48 h after certified | read-only, Settings-owned (dashed) | **Settings** |
| Weather moratorium | From Settings · below 32°F · above 100°F | read-only, Settings-owned (dashed) | **Settings** |
| Check payments to | 06:00 today | input | — |
| Minimum balance | $50.00 | input | — |
| Working days only | on | toggle | — |
| Produce a field list | on | toggle | — |
| Runs | Manual | dropdown | — |

## Steps

Source heading: **Steps 8 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather accounts at the last tier | The ladder's end, from the dunning runbook's own records | `read` |
| 2 | Confirm the letter was sent and delivered | A returned letter is not a served notice | `read` |
| 3 | Confirm the notice period has passed | Working hours, in the tenant's timezone | `read` |
| 4 | Check for a payment overnight | Anything landed since the letter, applied or not | `read` |
| 5 | Check protections and disputes again | Today, not when the letter went | `read` |
| 6 | Check the weather moratorium | Forecast for the service area today | `read` |
| 7 | Check it is a working day | No disconnect into a weekend or holiday | `read` |
| 8 | Build the field list | Address, meter, balance, crew notes | `read` |

## Guards — what it may never touch

- **Nothing here disconnects anyone and the runbook writes nothing.** A person approves a list, a crew acts on it through the Work module (`RB-049` when it exists).
- **Never include: Medical · Dispute · Plan in good standing · Sample.**
- **Every protection is re-checked on the morning, not carried over from the letter** — step 5 checks protections and disputes again *today*.
- **A returned letter is not a served notice** (`RBR-13`).
- The weather moratorium and the working-day check both stop the list.
- **Minimum balance $50.00.**

## Produces

14 eligible · 9 removed, each with why — a field list a person approves and signs, never a disconnection.

### The run, with the source's own figures

**Today · 06:15 — "14 eligible. 9 removed."**

- Verdict band: **14 eligible** · 9 removed since the letter · 4 paid overnight · 3 protected · 2 under minimum · moratorium not in effect.
- Tiles: **14** Eligible today · **4** Paid overnight · **3** Protected · **2** Under $50 · **No** Moratorium.
- Chips: All 23 · Eligible 14 · Removed 9.
- Table — Account · Address · Balance · Letter delivered · Today · Why, showing 1–5 of 23: Fielding, K. · 5 Vine St · $2,880.00 · 1 Sep · Eligible · Notice period passed · no payment; Okonkwo, D. · 2 Mill Rd · $1,204.05 · 1 Sep · Eligible · Notice period passed · no payment; Pace, J. · 7 Oak Ct · $540.77 · 1 Sep · Removed · Medical protection added 3 Sep; Vance, L. · 18 Elm St · $318.20 · 1 Sep · Removed · Paid $318.20 at 22:14 yesterday; Hale, T. · 40 Birch Rd · $44.10 · 1 Sep · Removed · Under $50.00 minimum.
- Actions: ↓ Field list · Approve field list ✓ — the danger tier, and it approves a **list**, never a disconnection.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-112, status UNVERIFIED): The morning of, a person sees "14 eligible · 9 removed since the letter" with why each was removed, and signs a field list; nothing is disconnected by the product.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R12.png` | `RBS-004-R12.md` | `…/runbooks/disconnect-eligibility` | `S150-R12`, figure 21 |
| Result | `RBS-006-R12.png` | `RBS-006-R12.md` | `…/runbooks/disconnect-eligibility/runs/latest` | `S152-R12`, figure 22 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R12` and `S152-R12`. This repository numbers them `RBS-004-R12` and `RBS-006-R12` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

The most expensive error a utility makes is a wrongful disconnect, and this runbook exists to make it impossible by accident. Every reason an account should not be on the list is checked again on the morning, not carried over from the letter. The output is a list with a signature line.

## Design notes on the result

The removed rows are shown with the eligible ones on purpose — the person signing wants to see who was taken off and why, because that is the list that would have been wrong. The commit is the danger tier and it approves a list, not a disconnection; what happens next is a crew and a work order in another module.

## Open questions and stated absences

- **Disconnect eligibility disconnects nobody and writes nothing.** Closed OUT OF SCOPE — *"Ruled by this specification, 4 September 2026; Product Owner not asked; a person signs, a crew acts through the Work module (RB-049 when it exists)."*
- **An assumption the source relies on and never states:** a weather forecast source exists for the service area. **No such integration is specified anywhere; without it step 6 cannot run.**
- **A second unstated assumption:** delivery of a certified letter can be confirmed. That needs postal delivery feedback — runbook 22's feed — to include post.
- **A third:** an account carries a *medical protection* flag and an *open dispute* state the guards can read. If the customers module has no such flags, the guards have nothing to read.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-112: VERIFIED** — `CR-075` wave S, 2026-09-07.
`apps/runbooks/definitions/disconnect_eligibility.py` · 38 cases in
`tests/test_us_rbs_024_disconnect_eligibility.py`, three of them shown RED
first · run on the seeded utility against real PostgreSQL
(`10-scripts/render-checks/rbs_s_seed_checks.py`) and walked in a browser
(`rbs-s-two-checks.mjs`, 26 assertions).

**Two of the card's own figures could not be produced and the run says so
rather than drawing them.**
* **The weather moratorium is `OQ-RBS-1757` and the tile reads *Not checked*,
  never the card's green *No*.** The parameter here is a TEMPERATURE rule over
  a service area; what this product holds is a per-ACCOUNT date window a person
  records (B18 §5.8.3). The per-account half runs and removes; nothing anywhere
  holds a forecast.
* **Step 2 reads `BR-CUS-100`'s PROOF OF SERVICE, not a delivery flag.**
  `delivered` and `bounced` are provider facts and no adapter exists on any
  channel, print included — so *a returned letter is not a served notice* is
  enforced by a person's attestation, which is also what `assert_service_proved`
  gates a real cut on. The blind spot is counted on the run rather than left
  silent.

**On the seeded utility, 2026-09-07:** 3 cases at the last tier · 2 removed by
the sample guard · 1 checked · **0 eligible, 1 removed** — R-0003, 2203 Cane
Island Parkway, `$368.40`, letter served 4 September, removed because *today is
a holiday on this tenant's calendar*. The address is walked to on `premises`
(hard rule 8) and no account carries one.
