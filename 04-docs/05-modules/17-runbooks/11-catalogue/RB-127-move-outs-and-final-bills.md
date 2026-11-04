# RB-127 — Runbook 27 · Move-outs and final bills

**On screen a clerk sees “Move-outs.”** The definition title above is the name on its card; the screen name is the display name in the templates library and on every wireframe.

> **RESERVED.** Scope, parameters and steps below are **drafted from the catalogue**; the **result screen is not drawn**.
>
> Until it is drawn, nothing here is a finished definition — the source says so in those words, and this file does not invent a result to fill the gap.

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Accounts |
| **Tags** | Not stated. The source's tag table covers runbooks 1–22 only. |
| **Phase** | 2c |
| **Trigger** | Not declared on the contract coverage table. The card's `Runs` parameter reads **Daily 07:00**. |
| **Subject and unit of work** | Not declared on the contract coverage table. The card's scope is **closing accounts with a move-out date inside the window**. |
| **Step modes** | Not declared. Steps are marked 3 read, 3 write. |
| **Result blocks it composes** | Not declared on the contract coverage table. |
| **Ports it holds** | Not declared on the contract coverage table. Step 4 issues **through the billing service**, on the ordinary bill-run path. |
| **Proves** | US-RBS-037 |
| **Waits on** | — |
| **Status** | **BUILT — `06-backend/apps/runbooks/definitions/move_outs.py`** (`CR-075` wave R′, 2026-09-07). The result screen is still **not drawn** and the build invents none: it composes the twelve blocks around this card's own *done looks like* sentence. Three stamped divergences; see that file's docstring |

## What it does

Does: walks every closing account: the closing read due, the final bill issued, the deposit refunded or carried, the forwarding address captured. The gap E.ON Next paid £14.5 million for.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Accounts | Closing · move-out date inside the window | value, not editable on this screen |
| Window | Next 14 days, and any closed without a final bill | value, not editable on this screen |
| Never include | Sample | value, not editable on this screen |

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Closing read due | From Settings · days before move-out | read-only, Settings-owned (dashed) | **Settings** |
| Deposit | Refund, or carry to the new account | input | — |
| Channel | Email, then post | input | — |
| Runs | Daily 07:00 | input | — |

## Steps

Source heading: **Steps 6 · 3 read, 3 write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather closing accounts | And any closed account with no final bill, however old | `read` |
| 2 | Check the closing read | Present, inside the window, or estimated by policy | `read` |
| 3 | Check the forwarding address | Captured, standardised | `read` |
| 4 | Issue the final bill | Through the billing service · the ordinary bill run path. ⚠ **THE BUILD PLANS AND HANDS BILLING A SCOPE; IT ISSUES NOTHING, AND THIS IS NOT A GAP TO BE FILLED LATER** (`CR-075` wave R′, 2026-09-07). `apps/runbooks/ports/billing_ports.py`, verbatim: *"THERE IS NO PORT THAT ISSUES A BILL, AND THERE WILL NOT BE. A runbook says what would stop a bill run and hands billing a scope at most; the bill run is billing's own act … it is hard rule 4 read forward, since an issued invoice is append-only and a module that could re-run one would be writing corrections nobody asked for."* Pointing the ordinary bill run at the scope satisfies this step's own words; a second implementation of issuing would not. **The step therefore declares `writes=False`** — a step claiming a write the capability does not exist for is a claim nothing can keep | ~~`writes`~~ **`read`** |
| 5 | Settle the deposit | Refund behind the second approval, or carry forward | `writes` |
| 6 | Queue the final notice | Bill and deposit letter · after approval | `writes` |

## Guards — what it may never touch

- **Never include: Sample.**
- A **refund** sits behind the second approval; a carry-forward does not.
- The final bill is issued **on the ordinary bill run path**, through the billing service — not a second implementation.
- The window reaches backwards as well as forwards: *any closed account with no final bill, however old*.

## Produces

Final bills issued, deposits settled, and the list of closing accounts still missing a read or an address, each with its fix.

**Done looks like** (the commitment's own sentence, RB-127, status UNVERIFIED): A clerk sees every closing account with its closing read due, its final bill issued or waiting, its deposit refunded or carried, and the forwarding address captured.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R27.png` | `RBS-004-R27.md` | `…/runbooks/move-outs` | `S150-R27`, figure 47 |
| Result | **not drawn** | **not drawn** | — | `S152-R27` — reserved, not designed |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

**The result screen is reserved and not designed.** This file does not describe one.

> The source document numbers these screens `S150-R27` and `S152-R27`. This repository numbers them `RBS-004-R27` and `RBS-006-R27` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Open questions and stated absences

- **The result screen is not drawn.** That is part of the commitment `RB-127`, and until it is drawn nothing here is a finished definition. ⚠ **The build does not invent one** (`CR-075` wave R′): `move_outs.py` composes `Verdict · KPIs · Breakdown · Records · Facts · Downloads` — all twelve-block names, no thirteenth — around this card's own *done looks like* sentence, which is a table with five facts per row. **A frame drawn later governs; nothing in the code has to be undone for it to.**
- ⚠ **THE CARD DECLARES NO TRIGGER, NO UNIT OF WORK, NO BLOCK LIST AND NO PORTS**, and the build chose each rather than guessing silently: **manual + schedule** (the card's *Runs · Daily 07:00* is the schedule half), **one subject per closing ACCOUNT**, the six blocks above, and the ports `raise_refund` · `post_credit` · `queue_notice` — **and deliberately NOT a bill-issuing port, because there is none.** Every one is recorded in `12-governance/02-decision-log.md`, 2026-09-07.
- **Why this card exists:** named in the catalogue (C11) with an estimate of **about 5 hours a month**, and defined nowhere until this pass.
- **It is also the first runbook of the empty Accounts category** — the source names it as that category's first tenant.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-127: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
