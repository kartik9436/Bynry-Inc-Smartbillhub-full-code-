# RB-104 — Runbook 4 · Why is this bill higher?

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Billing |
| **Tags** | Customer portal |
| **Phase** | 3 |
| **Trigger** | Manual |
| **Subject and unit of work** | Account · one |
| **Step modes** | per record (1) |
| **Result blocks it composes** | KPIs · Ranked · Reconciled · Sentence · Facts |
| **Ports it holds** | — (a Check holds none; *Add to notes ✓* on the result is the clerk's act, performed by the customers module) |
| **Proves** | US-RBS-019 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: the most common call a small utility takes, in one screen. Scope is one account and two bills; the output is an explanation ranked by how much each cause contributed.

## Scope — how the set is decided

The setup panel is headed **Scope one account**.

| Row | Value | Control |
|---|---|---|
| Account | 🔍 Alvarez, M. · 14 Cedar St | value, not editable on this screen |
| This bill * | Sep 2026 · $214.60 | dropdown |
| Compared with | Previous · Aug · $132.40 | dropdown |

Also offered: same month last year and 12-month average.

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Show causes above | $2.00 | input | — |
| Normalise for days | on | toggle | — |
| Include one-off items | on | toggle | — |
| Write to account notes — **WITHDRAWN** | Clerk's act · Add to notes ✓ | read-only · **WITHDRAWN, do not build** | — |

The fourth row is drawn **WITHDRAWN, do not build** — it is not read-only because it lives in Settings, it is withdrawn. It stays visible on the build sheet so a builder does not build it and a reader can see it was there.

## Steps

Source heading: **Steps 7 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Fetch both bills | Line by line, as issued | `read` |
| 2 | Compare usage | Days in period, units used, daily average | `read` |
| 3 | Compare rates | Did a rate version change between the two? | `read` |
| 4 | Compare charges | Base, each block, taxes, fees, adjustments | `read` |
| 5 | Find one-offs | Catch-up read, corrected estimate, back-bill, late fee | `read` |
| 6 | Check the meter | Multiplier change, exchange, rollover | `read` |
| 7 | Rank the causes | By dollars contributed, largest first | `read` |

## Guards — what it may never touch

- **This Check writes nothing.** A *write to account notes* switch was drawn here and withdrawn, because `BR-RBS-002` builds a Check with no writer.
- Adding the explanation to the account's notes is the **clerk's act** from the result screen (*Add to notes ✓*), performed by the customers module.

## Produces

An explanation a clerk can read aloud: "Up $82.20. Usage +38% (+$46.40) over 4 more days; tier 2 reached (+$14.80); late fee added (+$12.00). Rate unchanged. Meter unchanged."

### The run, with the source's own figures

**Alvarez, M. · 14 Cedar St — "Up $82.20 · $132.40 in August → $214.60 in September."**

- Tiles: **+$82.20** Change · **+38%** Usage · **34 vs 30** Days · **Same** Rate.
- What caused it · largest first: More water used (7,240 gal vs 5,250 gal · 4 more days) **+$46.40**; Reached tier 2 (usage above 5,000 gal priced higher) **+$14.80**; Late fee (August paid 12 days late) **+$12.00**; Tax on the above (follows the charges) **+$9.00**; Rate change (none between the two bills) **$0.00**; Meter (same meter, same multiplier) **$0.00**.
- Read this aloud: *"Your September bill is $82.20 higher. You used 38% more water over 4 more days, which also took you into the higher price tier. A $12.00 late fee was added for August. Your rate did not change."*
- Side by side — Line · Aug · Sep · Change: Water base $18.00 · $18.00 · —; Water 0–5,000 gal $42.00 · $40.00 · −$2.00; Water over 5,000 gal $2.75 · $24.60 · +$21.85; Sewer $58.10 · $99.45 · +$41.35; Late fee — · $12.00 · +$12.00; Tax $11.55 · $20.55 · +$9.00; Total $132.40 · $214.60 · **+$82.20**.
- Actions: Copy explanation · Add to notes ✓ (enabled; the clerk's act).

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-104, status UNVERIFIED): A clerk picks an account and two bills and reads aloud "Up $82.20 · usage +38% over 4 more days · tier 2 reached · late fee $12.00 · rate unchanged", with the two bills side by side.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R4.png` | `RBS-004-R4.md` | `…/runbooks/why-higher` | `S150-R4`, figure 7 |
| Result | `RBS-006-R4.png` | `RBS-006-R4.md` | `…/runbooks/why-higher/runs/alvarez-sep` | `S152-R4`, figure 8 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R4` and `S152-R4`. This repository numbers them `RBS-004-R4` and `RBS-006-R4` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

Normalise for days matters more than it looks: a 34-day period against a 28-day one explains a surprising share of "my bill went up" calls on its own.

## Design notes on the result

Two views of one answer. The left is ranked by dollars because a caller wants the biggest reason first; the bars are one hue and thin, and the figure beside each is the label — no legend, no colour meaning. The right is the two bills line by line for the clerk who wants to check. "Read this aloud" is the deliverable: it is written for the phone, in the customer's own units, and it can be copied straight into a note or a reply.

## Open questions and stated absences

- **The withdrawn switch.** Corrected in place: *"Ruled by this specification, 4 September 2026; Product Owner not asked, to keep BR-RBS-002 intact; raised to the Product Owner as open decision 11 in case a note is wanted automatically."* **Open decision 11 is open.**
- **The ranked-causes bars have no legend and no colour meaning.** Closed OUT OF SCOPE — one hue, and the figure beside each bar is the label.
- **Corrected in this pass.** The ranked causes summed to $92.20 against a change of $82.20; they now sum to $82.20 and agree with the side-by-side table.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-104: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
