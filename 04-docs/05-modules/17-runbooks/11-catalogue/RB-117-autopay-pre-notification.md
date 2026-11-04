# RB-117 — Runbook 17 · Autopay pre-notification

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Payments |
| **Tags** | Accounts · notices |
| **Phase** | 2c |
| **Trigger** | Schedule |
| **Subject and unit of work** | Account · autopay |
| **Step modes** | per record |
| **Result blocks it composes** | KPIs · Records · Downloads |
| **Ports it holds** | `queue_notice` (notifications) · `flag_account` (customers) · `schedule_retry` (payments) |
| **Proves** | US-RBS-029 |
| **Waits on** | a delivery provider |

## What it does

Does: tells every autopay customer the amount before it is debited, as bank rules require for a variable amount, and handles the debits that failed yesterday. Scope is autopay accounts with a bill issued and a debit due inside the notice window.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Accounts on | Autopay · active | read-only, Settings-owned (dashed) |
| Debit due within | 10 days | dropdown |
| Never include | Autopay paused · Sample | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Matches 862 accounts · 11 failed debits yesterday.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Notify | From Settings · 10 days before | read-only, Settings-owned (dashed) | **Settings** |
| Only when amount changed | on | toggle | — |
| Channel | Email, then text | dropdown | — |
| Failed debit | Retry once after 3 days, then tell and flag | dropdown | — |
| Runs | Daily 08:00 | dropdown | — |

## Steps

Source heading: **Steps 6 · four read, two write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather autopay accounts with a bill issued | And a debit date inside the window | `read` |
| 2 | Work out the debit date and amount | Bill total less any payment since | `read` |
| 3 | Check whether the amount changed | A fixed amount needs no notice; a variable one does | `read` |
| 4 | Check yesterday's failed debits | Returned by the bank, with the reason code | `read` |
| 5 | Queue the notices | One per account per bill · after approval or unattended | `writes` |
| 6 | Flag failed debits and schedule the retry | Through the payments service; a second failure needs a person | `writes` |

## Guards — what it may never touch

- **Never include: Autopay paused · Sample.**
- **Only when the amount changed** — a fixed amount needs no notice; a variable one does, which is what the bank rule requires.
- **A debit that fails twice is not retried a third time; it goes to the ladder** (`RBR-12`).
- *Bank said* is the bank's reason translated into words — insufficient funds, never the return code.
- The word is **Queued**: nothing leaves the building until a delivery provider is connected.

## Produces

851 notices queued · 11 failed debits, $1,480.20 — 9 retrying, 2 need a person.

### The run, with the source's own figures

**Today · 08:00 — "851 queued. 2 debits need you."**

- Tiles: **851** Notices queued · **11** Failed debits · **$1,480.20** Failed value · **9** Retrying · **2** Need a person.
- Failed debits · 11, showing 1–3 — Account · Amount · Bank said · Attempt · Next · Fix: Brant, H. · $96.10 · Insufficient funds · 1 of 2 · Retry 7 Sep · —; Sato, Y. · $142.30 · Account closed · 1 of 2 · Needs a person · Ask for new details →; Vance, L. · $318.20 · Insufficient funds · 2 of 2 · To the ladder · Open account →.
- Actions: ↓ Notices · ↓ Failed debits. Fix reads — on a debit that is simply retrying; the notices themselves are a download, not a table.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-117, status UNVERIFIED): At 08:00 the clerk sees "851 queued · 2 debits need you", and each failed debit reads the bank's reason in words with Retry 7 Sep or To the ladder.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R17.png` | `RBS-004-R17.md` | `…/runbooks/autopay-prenotice` | `S150-R17`, figure 31 |
| Result | `RBS-006-R17.png` | `RBS-006-R17.md` | `…/runbooks/autopay-prenotice/runs/latest` | `S152-R17`, figure 32 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R17` and `S152-R17`. This repository numbers them `RBS-004-R17` and `RBS-006-R17` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

Compliance disguised as convenience. A bank debit of a variable amount must be pre-notified, and 850 notices a month is not a job a person should have. The failed-debit half is where the money is: a debit that bounces twice is a returned payment, and it should land on runbook 8's ladder rather than be forgotten.

## Design notes on the result

Bank said is the bank's reason translated — insufficient funds, never the return code. The second failure is not retried a third time; it hands the account to the dunning runbook, and the row says so.

## Open questions and stated absences

- **Autopay notices are a download, not a table.** Closed OUT OF SCOPE — *"851 rows a clerk will never read belong in a file."*
- **Waits on a delivery provider.** Until one is connected the queue fills and nothing is sent (PO ruling, 17 August 2026).

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-117: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
