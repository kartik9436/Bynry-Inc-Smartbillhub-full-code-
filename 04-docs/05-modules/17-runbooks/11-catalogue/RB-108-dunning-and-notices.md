# RB-108 — Runbook 8 · Dunning and notices

**On screen a clerk sees “Collections ladder.”** The definition title above is the name on its card; the screen name is the display name in the templates library and on every wireframe.

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Collections |
| **Tags** | Payments · notices |
| **Phase** | 2a dry · 2b live |
| **Trigger** | Schedule |
| **Subject and unit of work** | Account · past due |
| **Step modes** | per record |
| **Result blocks it composes** | KPIs · Breakdown · Records · Downloads |
| **Ports it holds** | `queue_notice` (notifications) · `apply_fee` (billing) |
| **Proves** | US-RBS-010 · US-RBS-013 · J-RBS-3 |
| **Waits on** | RB-011 · a delivery provider before anything is sent |

## What it does

Does: walks accounts past due, works out which tier of the ladder each is owed, and queues the notice — after a dry run and a batch approval. The first Action on this page, and the one that returns the most hours.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Past due more than | $5.00 | input |
| Services | Water · Sewer | dropdown |
| Cycles | All | dropdown |
| Account types | All except Municipal | dropdown |
| Never include | Medical · Dispute · Sample | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Matches 1,004 accounts today.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Ladder tiers | From Settings · 5 tiers | read-only, Settings-owned (dashed) | **Settings** |
| Grace days | From Settings · 3 | read-only, Settings-owned (dashed) | **Settings** |
| Most per run | 400 | input | — |
| Channels | Email, then post | dropdown | — |
| Quiet hours | From Settings · 20:00–08:00 | read-only, Settings-owned (dashed) | **Settings** |
| Fees need second approval | on | toggle | — |
| Runs | Mondays 07:00 | dropdown | — |

Four of the seven parameters are read-only — tiers, grace days, quiet hours and the protected list already live in Settings. The three this runbook owns are about the run, not the policy: how many at once, on which channels, on which day.

## Steps

Source heading: **Steps 6 · four read, two write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Find accounts past due | Scope above, resolved once and pinned | `read` |
| 2 | Remove protected accounts | Guards win over everything below | `read` |
| 3 | Work out the tier due | Days past due against your ladder; nothing sent twice | `read` |
| 4 | Check the address works | A dead channel is skipped, never sent to | `read` |
| 5 | Queue the notice | After approval · one per account per run · capped | `writes` |
| 6 | Record what was sent | Audit row names this runbook and its version | `writes` |

## Guards — what it may never touch

- **Never include: Medical · Dispute · Sample.** Guards are absolute skips, evaluated before any step, and they win over everything below them.
- A dead channel is skipped, never sent to.
- Nothing is sent twice: step 3 works out the tier due against the ladder and one notice goes per account per run, capped at 400.
- Fees need a **second approval**, separate from the batch approval (`RB-014`).
- The word on the result is **Queued**, never *Sent* — nothing leaves the building until a delivery provider is connected (`RBR-07`, PO ruling 17 August 2026).

## Produces

A plan first — 812 to send · 97 skipped · 95 need a person, each with its rule. Then, after approval, notices queued and two files: what was queued and what was not, each row with its reason and fix.

### The run, with the source's own figures

**Run · 8 Sep 07:00 — "398 queued. 2 need you." (the result, after approval)**

- Tiles: **398** Queued · **97** Skipped · **2** Failed · **412** Left for next run · **$0.00** Fees charged.
- By tier — Tier · Planned · Queued · Failed: Reminder 96 · 96 · 0; 10-day notice 214 · 212 · 2; 5-day notice 78 · 78 · 0; Certified letter 12 · 12 · 0; **Total 400 · 398 · 2**.
- By channel: Email 268 · Post 130. Approved by Dana Whitfield · 07:14. Took 4m 02s.
- Failed · 2: Nunes, R. · 10-day notice · No deliverable address · Add an address →; Sato, Y. · 10-day notice · No email or postal address · Add a contact →.
- Actions: ↓ Queued · ↓ Not queued · Needs a person 95 →; each Fix → enabled.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-108, status UNVERIFIED): After approval the clerk sees "398 queued · 2 need you · 412 left for next run · $0.00 fees", the tier table with planned, queued and failed, and the two failed rows with their fix.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R8.png` | `RBS-004-R8.md` | `…/runbooks/collections-ladder` | `S150-R8`, figure 13 |
| Result | `RBS-006-R8.png` | `RBS-006-R8.md` | `…/runbooks/collections-ladder/runs/8-sep` | `S152-R8`, figure 14 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R8` and `S152-R8`. This repository numbers them `RBS-004-R8` and `RBS-006-R8` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

The five tiers and the grace days are `BR-PAY-017` in the repository — due+3 reminder, late fee, 10-day, 5-day, 48-hour certified — and they are held in Settings.

## Design notes on the result

The tier table has planned · queued · failed side by side because the approval was of a plan, and this is the plan reconciled against what happened — the same three-column honesty as the cutover totals. Fees charged: $0.00 is a tile even when zero, because a clerk who approved a run wants to see that figure without hunting. The word throughout is queued: nothing leaves the building until a provider is connected.

## Open questions and stated absences

- **Nothing leaves the building**: no delivery provider is connected, so the word is Queued, never Sent. OUT OF SCOPE of this change request — ruled by the Product Owner on 17 August 2026; a vendor decision gates phase 2b and `RB-044`.
- **Corrected in this pass.** The card said this was *"the only Action on this page"*; it is **the first of nine**.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-108: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
