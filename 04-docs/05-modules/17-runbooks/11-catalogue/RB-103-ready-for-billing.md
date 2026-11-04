# RB-103 — Runbook 3 · Ready for billing?

**On screen a clerk sees “Pre-bill sweep.”** The definition title above is the name on its card; the screen name is the display name in the templates library and on every wireframe.

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Billing |
| **Tags** | Reads |
| **Phase** | 1c |
| **Trigger** | Schedule |
| **Subject and unit of work** | Account · one cycle |
| **Step modes** | per record |
| **Result blocks it composes** | Verdict · KPIs · Records · Downloads |
| **Ports it holds** | — (a Check holds none) |
| **Proves** | US-RBS-007 |
| **Waits on** | RB-036 |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: if we ran this cycle now, which accounts would fail and why? Scheduled daily in the days before a bill run, so problems arrive early instead of mid-run.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Cycle | Monthly A | value, not editable on this screen |
| Period | September 2026 | value, not editable on this screen |
| Services | All enabled | dropdown |
| Include held accounts | off | toggle |

The scope function also answers the count on the screen: **Matches 1,410 accounts due on 20 Sep.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Run each day from | 5 days before | input | — |
| Estimate missing reads | Per your read rules | read-only, Settings-owned (dashed) | **Settings** |
| Treat estimates as | Warning | dropdown | — |
| Prior period must be closed | on | toggle | — |

## Steps

Source heading: **Steps 8 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Every meter has a read | For the period, inside the read window | `read` |
| 2 | Reads pass validation | High, low, rollover, zero — by your rules | `read` |
| 3 | A plan in force | For every account, for the whole period | `read` |
| 4 | Rates cover usage | Every block needed this period exists | `read` |
| 5 | Prorations resolvable | Move-ins and move-outs have their dates and reads | `read` |
| 6 | No open corrections | Nothing pending that would block issue | `read` |
| 7 | Prior period closed | Last run issued or cancelled | `read` |
| 8 | Price a sample | One account per plan, through the real engine | `read` |

## Guards — what it may never touch

- It is a Check, so it holds no ports and writes nothing — step 8 prices real accounts through the real engine and keeps nothing.
- `Estimate missing reads` is read-only: whether a missing read may be estimated, and how, is already decided in Settings.

## Produces

Ready, or N accounts will fail — each with its step, its reason and the screen that fixes it. Estimates are listed separately as warnings.

### The run, with the source's own figures

**Monthly A · September — "14 accounts will fail. 5 days left."**

- Verdict band, warning tone: **Not ready** · 1,396 of 1,410 will bill · 14 will fail · 38 will be estimated · bill day 20 Sep.
- Tiles: **1,358** Will bill clean · **38** Will be estimated · **14** Will fail · **$3,102.40** Billing at risk.
- Chips: Will fail 14 · Estimated 38 · No read 9 · No plan 3 · No rate 2.
- Table — Account · Service · Stops at · Why · Fix, showing 1–5 of 14: Okonkwo, D. · Sewer · Step 1 · Read · No read since 18 Aug · Add a read →; Brant, H. · Water · Step 1 · Read · Read outside window · Re-date or re-read →; Vance, L. · Water · Sewer · Step 3 · Plan · Plan ended 31 Aug · Assign a plan →; Marsh Farms · Water · Step 4 · Rate · 28,400 gal · no block above 20,000 · Add a block →; Pace, J. · Water · Step 5 · Proration · Move-out 12 Sep, no closing read · Add closing read →.
- Actions: ↓ Will fail · ↓ Estimated · Run again ▶; each Fix → enabled.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-103, status UNVERIFIED): Five days before bill day the clerk sees "14 accounts will fail" with Stops at, Why and Fix on each, and "$3,102.40 billing at risk".

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R3.png` | `RBS-004-R3.md` | `…/runbooks/billing-readiness` | `S150-R3`, figure 5 |
| Result | `RBS-006-R3.png` | `RBS-006-R3.md` | `…/runbooks/billing-readiness/runs/today` | `S152-R3`, figure 6 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R3` and `S152-R3`. This repository numbers them `RBS-004-R3` and `RBS-006-R3` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

The read-rules parameter is dashed on purpose. Whether a missing read may be estimated, and how, is already decided in Settings; this runbook obeys it and says so rather than offering a second place to change it. Step 8 is what makes this more than a checklist — it prices real accounts through the real engine, so the sentence a clerk sees is the engine's own refusal, not a prediction of it.

## Design notes on the result

Stops at names the step so a clerk fixing five failures does them in chain order. Billing at risk is the sum of last month's bills for the 14 — the number that tells a utility whether this is fourteen small accounts or one large one. Estimated accounts are a separate download because they are not failures: they will bill, and the clerk may want to chase actual reads first.

## Open questions and stated absences

- **The read-rules parameter is read-only on purpose; there is no second place to change policy.** Closed OUT OF SCOPE: *"Ruled by this specification, 4 September 2026; Product Owner not asked; see RB-021."*
- **Corrected in this pass.** The tiles summed to 1,448 against 1,410 accounts; "Will bill clean" is now **1,358**. The verdict band still reads *1,396 of 1,410 will bill*, which is the source's own text.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-103: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
