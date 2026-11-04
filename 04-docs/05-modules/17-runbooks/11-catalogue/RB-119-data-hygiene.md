# RB-119 — Runbook 19 · Data hygiene

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Data Hygiene |
| **Tags** | Accounts · Service points |
| **Phase** | 3 |
| **Trigger** | Schedule |
| **Subject and unit of work** | Tenant |
| **Step modes** | set |
| **Result blocks it composes** | KPIs · Breakdown · Action (raise items) · Downloads |
| **Ports it holds** | — (a Check holds none; *Raise work items ✓* is the engine's act at run close) |
| **Proves** | US-RBS-031 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: what in our records will trip the other runbooks? Duplicate customers, premises with no meter, accounts nobody can reach. Scope is the whole utility, monthly. Everything else on this page works better when this is clean.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Records | The whole utility | read-only, Settings-owned (dashed) |
| Never include | Sample | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Checks 2,907 accounts · 2,862 premises · 2,842 meters.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Duplicate means | Same phone, or tax id, or email | dropdown | — |
| Orphan means | Premise · no meter / Meter · no premise / Account · no unit | read-only, Settings-owned (dashed) | **Settings** |
| Reachable means | At least one of email, mobile, postal | dropdown | — |
| Raise work items | on | toggle | — |
| Runs | Monthly | dropdown | — |

## Steps

Source heading: **Steps 7 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Duplicate customers | Same phone, same tax id or same email under two names | `read` |
| 2 | Premises with no meter | A service point that cannot be read | `read` |
| 3 | Meters with no premise | A meter that cannot be billed | `read` |
| 4 | Accounts with no unit | The chain break from runbook 1, re-checked | `read` |
| 5 | Accounts with no contact channel | Nobody can be told anything | `read` |
| 6 | Addresses that failed standardisation | Post will not arrive | `read` |
| 7 | Group by what each will break | Storm text · dunning · billing · cutover | `read` |

## Guards — what it may never touch

- It is a Check, so it holds no ports and writes nothing. Raising the work items is the engine's act at run close.
- **Never include: Sample.**

## Produces

212 items in six groups — and the one sentence that matters most: text can reach 1,350 of 2,907 accounts today.

### The run, with the source's own figures

**September — "212 items. 900 accounts unreachable by text."**

- Tiles: **41** Duplicate customers · **23** Orphans · **108** No contact channel · **40** Bad addresses · **1,350 of 2,907** Reachable by text.
- By what it will break — Group · Items · Will break · Fix: No mobile, or no consent · 1,557 · The storm text · leak alerts · Ask on the bill and portal →; No contact channel at all · 108 · Dunning · every notice · Add a contact →; Duplicate customers · 41 · Deposits carried twice · two logins · Merge →; Premises with no meter · 20 · Billing readiness · runbook 3 · Assign a meter →; Addresses not standardised · 40 · Post · certified letters · Fix address →; Meters with no premise · 3 · Reads land nowhere · Attach to premise →.
- Actions: ↓ All items · Raise work items ✓.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-119, status UNVERIFIED): Monthly the clerk sees "212 items · 900 accounts unreachable by text" grouped by what each will break, with Reachable by text as a tile.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R19.png` | `RBS-004-R19.md` | `…/runbooks/data-hygiene` | `S150-R19`, figure 35 |
| Result | `RBS-006-R19.png` | `RBS-006-R19.md` | `…/runbooks/data-hygiene/runs/latest` | `S152-R19`, figure 36 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R19` and `S152-R19`. This repository numbers them `RBS-004-R19` and `RBS-006-R19` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

The runbook that makes the others honest. It is grouped by consequence, not by table, because a clerk fixes "dunning will miss 108 people" and not "null contact rows".

## Design notes on the result

Reachable by text is a tile because it is the number that decides whether the storm runbook works, and a utility should see it every month rather than discover it in a storm. The groups are named by consequence — the storm text, dunning, runbook 3 — so the fix order is obvious without anyone ranking it.

## Open questions and stated absences

- **Raise work items is a button, not automatic.** Closed OUT OF SCOPE, the same ruling as runbooks 5 and 18.
- **An assumption the source relies on and never states:** phone numbers are encrypted with a blind index, so *"same phone"* here means a blind-index match. **Fuzzy phone matching is not possible on an encrypted column.**

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-119: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
