# RB-113 — Runbook 13 · Payment trace

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Payments |
| **Tags** | Customer portal |
| **Phase** | 3 |
| **Trigger** | Manual |
| **Subject and unit of work** | Account or payment · one |
| **Step modes** | per record (1) |
| **Result blocks it composes** | Verdict · Chain · Facts · Action (route to move) |
| **Ports it holds** | — (a Check holds none; moving a payment is a payments-module act with its own audit, and *Add to notes ✓* is the clerk's act, performed by the customers module) |
| **Proves** | US-RBS-025 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: "I paid, and you say I didn't" — where did that payment go? Scope is one account, or a search by amount and date when the caller does not know which account it landed on. The second most common call a utility takes, after "why is my bill higher".

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Account | 🔍 Okonkwo, D. · 2 Mill Rd | value, not editable on this screen |
| Or amount | $182.40 | input |
| Around | 12 Sep ± 3 days | dropdown |
| Last four of cheque or card | 4471 | input |

Searches this account, then every account for the same amount and date.

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Look back | 90 days | dropdown | — |
| Amount tolerance | $0.01 | input | — |
| Search other accounts | on | toggle | — |
| Include reversed and returned | on | toggle | — |
| Include today's unapplied batch | on | toggle | — |

## Steps

Source heading: **Steps 6 · all read · stops when found**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Payments on this account in the window | Applied, pending, reversed | `read` |
| 2 | Same amount and date anywhere | Every account in the tenant — this is where mis-keyed payments hide | `read` |
| 3 | Reversed or returned items | A payment that came and went again | `read` |
| 4 | Unapplied cash matching | Money we hold and have not placed | `read` |
| 5 | Today's landed batch | Arrived, not yet applied — it is real, just early | `read` |
| 6 | Build the trace | One sentence, and the move if it is on the wrong account | `read` |

## Guards — what it may never touch

- It is a Check: **it finds, and the person moves the payment.** Moving a payment is a payments-module act with its own approval and its own audit.
- *Add to notes ✓* is the clerk's act, performed by the customers module. The Check itself writes nothing (`RBR-16`).
- The chain **stops when found** — steps 3 to 5 read *Not needed*.

## Produces

One sentence: "Found: $182.40 on 12 Sep, applied to account ending 4471 — Alvarez, not Okonkwo. Same last four." With Move payment → beside it.

### The run, with the source's own figures

**Okonkwo, D. · 2 Mill Rd — "Found it · Applied to the wrong account."**

- Found banner: **$182.40 · 12 Sep · lockbox** — applied to Alvarez, M. — account ending 4471 · same last four as this account.
- A five-cell chain: 1 This account *Nothing on 12 Sep* · 2 Elsewhere **Match on 4471** · 3 Reversed *Not needed* · 4 Unapplied *Not needed* · 5 Today's batch *Not needed*.
- Facts: Landed 12 Sep 06:30 · Lockbox · ref 88213; Amount $182.40; Applied to Alvarez, M. · 14 Cedar St · ending 4471; This account ends 4471 — the same four digits; Likely cause — Remittance slip carried the wrong account number. The first header of that table is blank by design.
- Actions: Move payment → (primary) · Add to notes ✓.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-113, status UNVERIFIED): A clerk enters $182.40 around 12 Sep and reads "Found · applied to Alvarez, M. · account ending 4471 · same last four", with Move payment → beside it.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R13.png` | `RBS-004-R13.md` | `…/runbooks/payment-trace` | `S150-R13`, figure 23 |
| Result | `RBS-006-R13.png` | `RBS-006-R13.md` | `…/runbooks/payment-trace/runs/latest` | `S152-R13`, figure 24 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R13` and `S152-R13`. This repository numbers them `RBS-004-R13` and `RBS-006-R13` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

Runbook 4's sibling, for money instead of usage. Same shape: one account, one question, one sentence, and a route to the fix. Fifteen minutes of digging becomes one screen.

## Design notes on the result

The chain stops at step 2 and says so — steps 3 to 5 read *Not needed*, which is the same honesty as "Never reached" in runbook 6. Likely cause is written for the phone: a clerk can say it to the customer as it stands. The move itself is a payments-module screen with its own approval, one click away.

## Open questions and stated absences

- **Payment trace finds; the person moves the payment.** Closed OUT OF SCOPE — *"Ruled by this specification, 4 September 2026; Product Owner not asked; moving a payment is a payments-module act with its own audit."*
- A *write to account notes* switch was drawn on runbooks 4 and 13 and withdrawn to keep `BR-RBS-002` intact; **open decision 11** asks whether an automatic note is ever wanted, and it is open.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-113: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
