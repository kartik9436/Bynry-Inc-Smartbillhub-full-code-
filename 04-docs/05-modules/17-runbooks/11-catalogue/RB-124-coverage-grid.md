# RB-124 — Runbook 24 · Coverage grid

> **RESERVED.** Scope, parameters and steps below are **drafted from the catalogue**; the **result screen is not drawn**.
>
> Until it is drawn, nothing here is a finished definition — the source says so in those words, and this file does not invent a result to fill the gap.

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Billing |
| **Tags** | Not stated. The source's tag table covers runbooks 1–22 only. |
| **Phase** | 1b |
| **Trigger** | Not declared on the contract coverage table. The catalogue row C3 says who runs it: **implementation, before go-live**. |
| **Subject and unit of work** | Not declared on the contract coverage table. The card's scope is **25 accounts, one per plan · service mix · cycle**. |
| **Step modes** | Not declared. All three steps are marked `read`. |
| **Result blocks it composes** | Not declared on the contract coverage table. The blocks table notes that the **Records** block's *grid* display mode is what draws the coverage grid. |
| **Ports it holds** | **None** — it is a Check, so it is constructed with no ports. |
| **Proves** | US-RBS-005 · J-RBS-2 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: price twenty-five accounts, one per plan, service mix and cycle, and show the whole estate as a grid of billed clean, billed with an estimate or default, and refused. The go-live artefact.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Accounts | 25, one per plan · service mix · cycle, chosen automatically | value, not editable on this screen |
| Period | The next cycle | value, not editable on this screen |
| Never include | Sample | value, not editable on this screen |

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Cells | One per plan × cycle | input | — |
| Refusals | Open the account's test bill | input | — |
| Re-pick accounts | Each run | input | — |

## Steps

Source heading: **Steps 3 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Pick one account per plan, service mix and cycle | Deterministic pick, so two runs compare | `read` |
| 2 | Price each one through the real engine | Runbook 23 on each cell | `read` |
| 3 | Group by outcome | Clean · estimated or defaulted · refused, with the refusal sentence | `read` |

## Guards — what it may never touch

- It is a Check, so it is constructed with no ports and writes nothing.
- **Never include: Sample.**
- The pick is **deterministic**, so two runs compare.

## Produces

A grid: 21 clean · 2 estimated · 2 refused, each cell opening that account's test bill with the engine's own refusal sentence.

**Done looks like** (the commitment's own sentence, RB-124, status UNVERIFIED): An implementer sees 25 cells, one account per plan, service mix and cycle: 21 clean, 2 estimated, 2 refused, and a red cell opens that account's test bill with the engine's own refusal.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R24.png` | `RBS-004-R24.md` | `…/runbooks/coverage-grid` | `S150-R24`, figure 44 |
| Result | **not drawn** | **not drawn** | — | `S152-R24` — reserved, not designed |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

**The result screen is reserved and not designed.** This file does not describe one.

> The source document numbers these screens `S150-R24` and `S152-R24`. This repository numbers them `RBS-004-R24` and `RBS-006-R24` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Open questions and stated absences

- **The result screen is not drawn.** That is part of the commitment `RB-124`, and until it is drawn nothing here is a finished definition.
- **Why this card exists:** named in the catalogue (C3), story `US-RBS-005`, journey `J-RBS-2`, phase 1b and the wireframes on `RBS-001`, `RBS-002`, `RBS-003` and `RBS-007` (the source's `S147`, `S148`, `S149` and `S153`) — **and defined nowhere** until this pass.
- Runbook 2 step 8 depends on this one: *Coverage grid green — last grid run had no refusals.*

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-124: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
