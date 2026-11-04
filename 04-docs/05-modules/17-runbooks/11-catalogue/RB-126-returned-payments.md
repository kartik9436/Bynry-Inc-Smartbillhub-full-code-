# RB-126 — Runbook 26 · Returned payments

> **RESERVED.** Scope, parameters and steps below are **drafted from the catalogue**; the **result screen is not drawn**.
>
> Until it is drawn, nothing here is a finished definition — the source says so in those words, and this file does not invent a result to fill the gap.

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Payments |
| **Tags** | Not stated. The source's tag table covers runbooks 1–22 only. |
| **Phase** | 2c |
| **Trigger** | Not declared on the contract coverage table. The card's `Runs` parameter reads **When returns land · rolled up 07:00**. |
| **Subject and unit of work** | Not declared on the contract coverage table. The card's scope is **returned items landed from the bank connection**. |
| **Step modes** | Not declared. Steps are marked 3 read, 3 write. |
| **Result blocks it composes** | Not declared on the contract coverage table. |
| **Ports it holds** | Not declared on the contract coverage table. Steps 4 and 5 write **through the payments service** and step 6 **through the customers service**. |
| **Proves** | US-RBS-036 |
| **Waits on** | RB-014 |

## What it does

Does: takes each payment the bank returned, reverses it, applies the returned-payment fee by rule behind the second approval, tells the customer, and removes the payment privilege after the configured number of returns.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Returned items | Landed from the bank connection | value, not editable on this screen |
| Never include | Already reversed · Sample | value, not editable on this screen |

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Fee | From Settings · returned-payment fee | read-only, Settings-owned (dashed) | **Settings** |
| Remove privilege after | From Settings · returns | read-only, Settings-owned (dashed) | **Settings** |
| Channel | Email, then post | input | — |
| Runs | When returns land · rolled up 07:00 | input | — |

## Steps

Source heading: **Steps 6 · 3 read, 3 write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather the returned items | From the bank connection, once, pinned | `read` |
| 2 | Match each to its payment | By reference, amount and date | `read` |
| 3 | Count prior returns | Against the privilege limit | `read` |
| 4 | Reverse the payment | Through the payments service · **a new row, never an edit** | `writes` |
| 5 | Apply the fee and queue the notice | Fee behind the second approval · notice after the batch approval | `writes` |
| 6 | Remove the privilege after N | Through the customers service · dated · the account flagged | `writes` |

## Guards — what it may never touch

- **A reversal is a new row, never an edit** — the platform's financial-immutability rule.
- **Never include: Already reversed · Sample.**
- The fee sits **behind the second approval** (`RB-014`); the notice goes after the batch approval.
- The fee amount and the privilege limit are **read-only, from Settings**.

## Produces

Reversed, fee applied, notified, and the privilege removed where the limit was reached, each with its rule; a second return hands the account to the ladder.

**Done looks like** (the commitment's own sentence, RB-126, status UNVERIFIED): A clerk sees returned items reversed, the fee applied by rule behind the second approval, the customer notified, and the privilege removed after N returns, each with its rule.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R26.png` | `RBS-004-R26.md` | `…/runbooks/returned-payments` | `S150-R26`, figure 46 |
| Result | **not drawn** | **not drawn** | — | `S152-R26` — reserved, not designed |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

**The result screen is reserved and not designed.** This file does not describe one.

> The source document numbers these screens `S150-R26` and `S152-R26`. This repository numbers them `RBS-004-R26` and `RBS-006-R26` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Open questions and stated absences

- **The result screen is not drawn.** That is part of the commitment `RB-126`, and until it is drawn nothing here is a finished definition.
- **Why this card exists:** named in the catalogue (C9) with an estimate of **about 3 hours a month**, and defined nowhere until this pass.
- **Runbook 17 hands a twice-failed debit here.**
- **`RB-014`, the second approval, waits on open decision 3** — which actions, and above what amount. That decision is open.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-126: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
