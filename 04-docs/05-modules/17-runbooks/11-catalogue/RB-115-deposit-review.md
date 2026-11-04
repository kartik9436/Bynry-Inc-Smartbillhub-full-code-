# RB-115 — Runbook 15 · Deposit review

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Collections |
| **Tags** | Finance · Accounts |
| **Phase** | 3 |
| **Trigger** | Schedule |
| **Subject and unit of work** | Deposit |
| **Step modes** | per record |
| **Result blocks it composes** | KPIs · Records · Action (approve refunds) · Downloads |
| **Ports it holds** | `post_credit` (payments) · `raise_refund` (payments) · `queue_notice` (notifications) |
| **Proves** | US-RBS-027 |
| **Waits on** | RB-014 (second approval) |

## What it does

Does: finds deposits a utility owes back after the customer's good-payment period, works out the interest the state requires, and either credits the account or raises a refund — the refund behind a second approval. Scope is every deposit held longer than the policy period.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Deposits held longer than | 12 months | read-only, Settings-owned (dashed) |
| Services | All | dropdown |
| Never include | Past due now · Plan voided in 12 months · Sample | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Matches 70 deposits · $17,890.00 held.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Good-payment months | From Settings · 12 | read-only, Settings-owned (dashed) | **Settings** |
| Interest | From Settings · 2.0% simple · state rule | read-only, Settings-owned (dashed) | **Settings** |
| Settle by | Credit to account | dropdown | — |
| Refund instead when | Account closed, or over $250.00 | input | — |
| Refunds need second approval | on | toggle | — |
| Most per run | 100 | input | — |
| Runs | Monthly · 1st | dropdown | — |

## Steps

Source heading: **Steps 7 · five read, two write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather deposits held past the period | Twelve months from the date held | `read` |
| 2 | Check twelve months of on-time payment | Every bill paid by its due date | `read` |
| 3 | Check nothing is past due today | The morning of, not the month of | `read` |
| 4 | Work out the interest owed | Your state's rate and method, to four decimals | `read` |
| 5 | Decide credit or refund | Open account under the limit → credit; otherwise refund | `read` |
| 6 | Post the credit, or raise the refund | Through the payments service · refunds wait for approval | `writes` |
| 7 | Queue the letter | "Your deposit of $250.00 has been returned" | `writes` |

## Guards — what it may never touch

- **Never include: Past due now · Plan voided in 12 months · Sample.**
- Step 3 re-checks that nothing is past due **the morning of, not the month of**.
- **Interest is worked out to four decimals**, on the state's rate and method held in Settings.
- **Every refund waits for a second approval** (`RB-014`), separate from the batch approval. A credit to an open account is reversible in practice; a cheque is not.
- Credits and refunds go through the payments service, through `post_credit` and `raise_refund`.

## Produces

48 credited, $9,312.00 · 13 refunds, $6,140.00, waiting for a second approval · 9 not yet eligible, each with the reason.

### The run, with the source's own figures

**1 Sep — "48 credited. 13 refunds await approval."**

- Tiles: **48** Credited · **$9,312.00** Credited value · **13** Refunds awaiting · **$6,140.00** Refund value · **$296.40** Interest paid.
- Refunds awaiting second approval · 13, showing 1–3 — Account · Deposit · Interest · Total · Why a refund · Approve: Reyes, P. · closed 14 Aug · $250.00 · $5.00 · $255.00 · Account closed · Waiting; Marsh Farms · $1,000.00 · $20.00 · $1,020.00 · Over the $250.00 limit · Waiting; Hale, T. · closed 2 Aug · $150.00 · $3.00 · $153.00 · Account closed · Waiting.
- Actions: ↓ Credited · Approve 13 refunds ✓ (the second approval).
- Credits already posted are in the download, not on screen: they need no decision.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-115, status UNVERIFIED): On the 1st the clerk sees "48 credited · 13 refunds await approval · $296.40 interest", and each refund row says Account closed or Over the $250.00 limit.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R15.png` | `RBS-004-R15.md` | `…/runbooks/deposit-review` | `S150-R15`, figure 27 |
| Result | `RBS-006-R15.png` | `RBS-006-R15.md` | `…/runbooks/deposit-review/runs/latest` | `S152-R15`, figure 28 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R15` and `S152-R15`. This repository numbers them `RBS-004-R15` and `RBS-006-R15` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

Money going the other way, so the gate is heavier. Utilities routinely hold deposits they owe back — in several states that is a compliance failure — and the reason is that nobody has the afternoon to find them.

## Design notes on the result

Interest is its own tile because it is the figure a regulator asks about and the one utilities most often get wrong. Why a refund is always one of two sentences, so the approver is not reading policy — they are confirming a fact.

## Open questions and stated absences

- **Credits already posted are in the download, not on screen.** Closed OUT OF SCOPE — *"they need no decision."*
- **`RB-014`, the second approval, waits on open decision 3** — which actions, and above what amount. That decision is open, so the threshold this card assumes is not yet ruled.
- **Corrected in this pass.** The scope said 61 deposits while the result counted 70; the scope now says **70 and $17,890.00 held** (previously 61 and $15,452.00).
- **An assumption the source relies on and never states:** the deposit interest rate and method are held in Settings per state. If Settings has no such value, the parameter has nothing to read.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-115: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
