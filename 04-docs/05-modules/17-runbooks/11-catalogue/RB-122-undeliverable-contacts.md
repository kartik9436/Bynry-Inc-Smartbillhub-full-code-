# RB-122 — Runbook 22 · Undeliverable contacts

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Data Sync |
| **Tags** | Accounts · Data Hygiene |
| **Phase** | 2c |
| **Trigger** | ⚡ `feedback.landed(provider, batch_id)` — delivery receipts and bounces land. Rolled up once a day at 07:00. |
| **Subject and unit of work** | Contact feedback |
| **Step modes** | per record |
| **Result blocks it composes** | KPIs · Breakdown · Records · Downloads |
| **Ports it holds** | `suppress_channel` (customers) · `flag_account` (customers) |
| **Proves** | US-RBS-034 |
| **Waits on** | RB-022 (feedback landed) |

## What it does

Does: when delivery feedback lands — a bounced email, a failed text, a returned letter — suppresses the dead channel, falls back to the next one on file, and flags the address for correction. Scope is the landed feedback, rolled up once a day. Runbook 19 reports the state of contact data monthly; this acts on each failure as it arrives.

## Scope — how the set is decided

The setup panel is headed **Scope runs when feedback lands**.

| Row | Value | Control |
|---|---|---|
| Runs when | ⚡ Delivery feedback lands | read-only, Settings-owned (dashed) |
| Channels | Email · Text · Post | dropdown |
| Never include | Sample | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Yesterday: 38 bounces · 6 failed texts · 4 returned letters.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Suppress after | 2 hard bounces, or 1 returned letter | dropdown | — |
| Soft bounce | Retry for 3 days, then treat as hard | dropdown | — |
| Fall back to | Next channel on file | read-only, Settings-owned (dashed) | **Settings** |
| Nothing left | Work item · account flagged | read-only, Settings-owned (dashed) | **Settings** |
| Re-enable when | Contact is updated | read-only, Settings-owned (dashed) | **Settings** |
| Runs | When feedback lands · rolled up 07:00 | read-only, Settings-owned (dashed) | **Settings** |

## Steps

Source heading: **Steps 6 · four read, two write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather the landed feedback | From the notification provider, once, pinned | `read` |
| 2 | Classify each item | Hard bounce · soft bounce · failed text · returned post | `read` |
| 3 | Apply the suppression rule | Thresholds above; one soft bounce suppresses nothing | `read` |
| 4 | Find the next channel on file | Email → text → post → none | `read` |
| 5 | Suppress and fall back | Through the customers service · the account's own preferences · dated | `writes` |
| 6 | Flag the address, raise work items | For the accounts with nothing left | `writes` |

## Guards — what it may never touch

- **One soft bounce suppresses nothing** — a soft bounce retries for 3 days and only then counts as hard.
- **Never include: Sample.**
- Suppression is written **through the customers service**, against the account's own preferences, and dated.
- **Re-enable when the contact is updated** — a suppression is not permanent.

## Produces

31 channels suppressed · 27 fell back · 4 have nothing left, listed.

### The run, with the source's own figures

**Today · 07:00 — "31 suppressed. 4 have nothing left."**

- Tiles: **31** Suppressed · **27** Fell back · **4** Nothing left · **9** Soft · retrying.
- By channel — Channel · Feedback · Suppressed · Fell back to: Email 38 · 24 · Text 18 · Post 4 · none 2; Text 6 · 3 · Email 2 · Post 1; Post 4 · 4 · Email 2 · none 2.
- Nothing left · 4, showing 1–3 — Account · Was · Now · Owed · Fix: Nunes, R. · Email · Post · — · $218.90 · 10-day notice due · Add a contact →; Sato, Y. · Email · — · $142.30 · Add a contact →; Hale, T. · Post · — · $44.10 · Add a contact →.
- Actions: ↓ Suppressed · ↓ Nothing left. *Now* reads — on every nothing-left row.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-122, status **BUILT — VERIFIED-UNRATIFIED**): At 07:00 the clerk sees "31 suppressed · 27 fell back · 4 nothing left", with where each suppressed channel fell back to and Owed on every nothing-left row.

### What engineering built, and where it differs — `CR-075` wave Q′, 2026-09-06

`06-backend/apps/runbooks/definitions/undeliverable_contacts.py`, six steps, walked in Chromium. On the
seeded utility, over five letters a clerk marked returned, the screen reads **"5 to suppress. 0 have nothing
left."** with tiles **5 · 5 would fall back · 0 nothing left · 0 soft retrying**, and a by-channel table
reading **Post · 5 · 5 · Email 5** — which is *where each suppressed channel falls back to*, the acceptance
sentence's own half.

⚠ **NOTHING IS SUPPRESSED AND NO ACCOUNT IS FLAGGED, AND THE REASON IS NOT THAT A WAVE HAS NOT GOT TO IT.**
`suppress_channel` and `flag_account` bind **no writer at all**: `customers.Contact` has no
undeliverable-channel column and no date for one, and `Account` carries only `cash_only`, whose own rule is
that nothing auto-clears it (`DEF-RBS-4331`). `BR-RBS-040` forbids the obvious substitute — a note is an
ENGINE act, never a fourteenth port. Both ports are called anyway and each refusal is recorded as the
outcome, because `BR-RBS-003` makes dry and live one code path.

**Four stamped divergences:**

1. **The trigger is manual and schedule, not ⚡ `feedback.landed`** — that event is emitted by nothing and is
   `CR-069`'s work, scoped to nobody. The card's *rolled up 07:00* is the schedule half and is already true.
2. **A `window` parameter was ADDED, default one day.** `notifications` holds every bounce it has ever been
   told about, so an unwindowed read plans the same suppression every morning and *"31 suppressed"* climbs
   without a customer's situation changing. The card's own count line reads **Yesterday**, so the window is
   the card's rather than an invention.
3. **The soft-bounce window is counted in ATTEMPTS, not days.** `outbound_messages` has an attempt count and
   no age column, and `BR-TEN-043` makes the business date an input rather than a clock a runbook may read —
   so *still being retried* is `BR-NOT-005`'s retry ×3, in the unit this product actually holds.
4. **`Re-enable when the contact is updated` is declared and has nothing to re-enable**, because no column
   records a suppression. Declared because the card declares it, and because a parameter that appears the day
   the column does is a smaller change than one nobody remembered.

⚠ **ONE THING NOBODY IS LISTENING FOR, AND THE RUN SAYS SO RATHER THAN SHOWING A NOUGHT.** No adapter on this
deployment writes `bounced` or `failed` on any channel — `notifications.delivery_ops.queue_health` records
the reason: *"delivery is out of this release by PO ruling (2026-08-15) … their counts are structurally zero
here and must be rendered as NOT REPORTED, never as zero."* The run carries those two statuses by name in its
own `not_reported`. **Which means the *nothing left* row — the one carrying Owed — cannot be produced with
real data at all** (every account with print traffic on the seeded tenant has an email and a phone on file);
it is proved in `06-backend/tests/test_us_rbs_034_undeliverable_contacts.py` and nowhere else.

**Two stops:** *"Nothing has come back."* (no provider, no returned letters) and *"Nothing has come back
yet."* (a provider connected and reporting nothing). Each draws one red chain cell, five reading **Never
reached**, a WHAT TO DO box, and **no KPI strip**.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R22.png` | `RBS-004-R22.md` | `…/runbooks/undeliverable-contacts` | `S150-R22`, figure 41 |
| Result | `RBS-006-R22.png` | `RBS-006-R22.md` | `…/runbooks/undeliverable-contacts/runs/latest` | `S152-R22`, figure 42 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R22` and `S152-R22`. This repository numbers them `RBS-004-R22` and `RBS-006-R22` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

Invisible work that quietly breaks collections. A notice sent to a dead address is a notice that was never served, and the dunning runbook cannot know unless someone acts on the bounce. Today nobody does.

## Design notes on the result

Fell back to is written as a sentence per channel rather than a matrix, because a clerk wants to know where the 24 suppressed emails went. The nothing-left table carries Owed and the notice that is due, because an account nobody can reach with money outstanding is the dunning runbook's next problem — the row says so before it becomes one.

## Open questions and stated absences

- **Nobody acts on a bounce today.** Already specified: this runbook, `RB-122`, is the daily act.
- **Corrected in this pass.** The fall-backs summed to 28 against a tile of 27, and nothing-left to 3 against 4; the channel table now agrees.
- **Waits on postal delivery feedback if runbook 12 is to trust it.** Runbook 12 step 2 says *"a returned letter is not a served notice"*, and that needs this feed to include post.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-122: BUILT, VERIFIED-UNRATIFIED** (`CR-075` wave Q′, 2026-09-06) — 35 cases in `06-backend/tests/test_us_rbs_034_undeliverable_contacts.py` plus its share of the 12 PostgreSQL cases in `test_rbs_sync_runbooks_pg.py`, three of them first shown failing on the specific wrong build they were written for. The figures above are the SOURCE's illustrative fixture and are not what the seeded utility produces; what it produces is in the section above and in `12-governance/02-decision-log.md`.
