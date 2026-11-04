# RB-125 — Runbook 25 · Payment plans

> **RESERVED.** Scope, parameters and steps below are **drafted from the catalogue**; the **result screen is not drawn**.
>
> Until it is drawn, nothing here is a finished definition — the source says so in those words, and this file does not invent a result to fill the gap.

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Collections |
| **Tags** | Not stated. The source's tag table covers runbooks 1–22 only. |
| **Phase** | 2c |
| **Trigger** | Not declared on the contract coverage table. The card's `Runs` parameter reads **Weekly · Mondays**. |
| **Subject and unit of work** | Not declared on the contract coverage table. The card's scope is **plans in flight**. |
| **Step modes** | Not declared. Steps are marked 3 read, 3 write. |
| **Result blocks it composes** | Not declared on the contract coverage table. |
| **Ports it holds** | Not declared on the contract coverage table. Step 5 voids a plan **through the payments service**, and step 4 queues a warning. |
| **Proves** | US-RBS-035 |
| **Waits on** | — |

## What it does

Does: walks every payment plan in flight, warns on a missed instalment, and voids a plan after the configured number of misses, each act with its rule and behind the batch approval.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Plans | In flight | value, not editable on this screen |
| Services | All | value, not editable on this screen |
| Never include | Dispute · Sample | value, not editable on this screen |

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Missed instalment | From Settings · grace days | read-only, Settings-owned (dashed) | **Settings** |
| Void after | From Settings · misses | read-only, Settings-owned (dashed) | **Settings** |
| Channel | Email, then post | input | — |
| Most per run | 200 | input | — |
| Runs | Weekly · Mondays | input | — |

## Steps

Source heading: **Steps 6 · 3 read, 3 write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather plans in flight | With their schedule and payments to date | `read` |
| 2 | Find missed instalments | Due date passed, no payment inside the grace days | `read` |
| 3 | Count the misses | Against the configured limit | `read` |
| 4 | Queue the warning | After approval · one per plan per run | `writes` |
| 5 | Void the plan | After the configured misses · through the payments service · the balance returns to the ladder | `writes` |
| 6 | Record it | Audit row names this runbook | `writes` |

## Guards — what it may never touch

- **Never include: Dispute · Sample.**
- The grace days and the miss limit are **read-only, from Settings**.
- Voiding goes **through the payments service**; the balance returns to the ladder.
- **Most per run: 200.**
- Warnings are queued **after approval**, one per plan per run.

## Produces

Warnings queued and plans voided, each with its rule; a voided plan's account appears on the next dunning run.

**Done looks like** (the commitment's own sentence, RB-125, status UNVERIFIED): A clerk sees plans in flight, the instalments missed this cycle, and which plans were voided after the configured misses, each with its rule.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R25.png` | `RBS-004-R25.md` | `…/runbooks/payment-plans` | `S150-R25`, figure 45 |
| Result | **not drawn** | **not drawn** | — | `S152-R25` — reserved, not designed |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

**The result screen is reserved and not designed.** This file does not describe one.

> The source document numbers these screens `S150-R25` and `S152-R25`. This repository numbers them `RBS-004-R25` and `RBS-006-R25` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Open questions and stated absences

- **The result screen is not drawn.** That is part of the commitment `RB-125`, and until it is drawn nothing here is a finished definition.
- **Why this card exists:** named in the catalogue (C8) with an estimate of **about 4 hours a month**, and defined nowhere until this pass.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-125: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
