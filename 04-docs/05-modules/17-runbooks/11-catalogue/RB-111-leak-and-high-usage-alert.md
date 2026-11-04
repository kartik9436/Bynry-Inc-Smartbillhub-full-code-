# RB-111 — Runbook 11 · Leak and high-usage alert

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Reads |
| **Tags** | Customer portal · Service points |
| **Phase** | 2c |
| **Trigger** | ⚡ `batch.landed` — intervals landed (specification B2b). The card's own `Runs` parameter reads *Daily 07:30*; see the note below. |
| **Subject and unit of work** | Meter-day (specification B2b). The card's scope reads *Meters with interval data*. |
| **Step modes** | set (own normal) · per record |
| **Result blocks it composes** | KPIs · Records · Sentence · Downloads |
| **Ports it holds** | `queue_notice` (notifications) · `flag_meter` (metering) |
| **Proves** | US-RBS-023 |
| **Waits on** | RB-022 · a delivery provider · ~~**OPEN decision 4** before any unattended run~~ — **ruled 2026-09-06 (`BR-RBS-041`); what it now waits on is wave `L3`, which builds the switch** |
| **Status** | **BUILT — `06-backend/apps/runbooks/definitions/leak_alert.py`** (`CR-075` wave R′, 2026-09-07). Four stamped divergences; see that file's docstring |

## What it does

Does: from interval reads landed overnight, finds meters running continuously or far above their own normal, and tells the customer before the bill does. Scope is the meters with interval data; the guards are what make it safe to run unattended.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Meters with | Interval data | read-only, Settings-owned (dashed) |
| Service | Water | dropdown |
| Window | Last 48 hours | dropdown |
| Never include | Opted out · Dispute · Told this week · Sample | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Matches 1,840 meters today.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Continuous flow for | 24 hours | input | — |
| Above own normal | 3× the 90-day average | input | — |
| Ignore below | 200 gal / day | input | — |
| Channel | Text, then email | dropdown | — |
| Once per meter every | 7 days | input | — |
| Quiet hours | From Settings · 20:00–08:00 | read-only, Settings-owned (dashed) | **Settings** |
| Unattended after — ⚠ **RULED 2026-09-06, AND NOT AS THIS ROW SAYS** | Permission granted **up front, per runbook** (`BR-RBS-041`) · every run still approved until wave `L3` builds the switch | read-only, Settings-owned (dashed) | **Settings** |
| Runs | Daily 07:30 | dropdown | — |

⚠ **THIS SENTENCE READ *"The Unattended after row is drawn read-only because open decision 4 is unruled. Until it is ruled, every run is approved."* UNTIL 2026-09-07, AND BOTH HALVES OF IT ARE NOW WRONG IN DIFFERENT WAYS** (`CR-075` wave R′, `US-RBS-023`; CLAUDE.md's status-column law — *a closed question's body goes on describing the open world, and the body is what a lane actually reads*).

**Open decision 4 is `OQ-RBS-1733` and it CLOSED on 2026-09-06.** The Product Owner answered with a **fourth option nobody offered** — verbatim, *"ask for permission from user upfront - if they are okay we complete the run and action, otherwise not"*, confirmed on the reading put back to them with *"you are correct"*. It is now **`BR-RBS-041`**: permission is granted **up front, per runbook**; with it on a run goes plan → act in ONE pass, with it off it stops at Review. **The plan is computed and stored either way — the switch removes the WAIT, never the plan** — so `BR-RBS-004` survives.

**So the three-clean-run ratchet this card describes is NOT built and is not going to be.** The lane that recommended it was overruled, in the safe direction.

**The row is still drawn read-only, for a different reason**: the switch `BR-RBS-041` describes is wave `L3`'s, `runbooks.gate_mode` holds one value today (`approve_each_run`) and its second value has no writer, no screen and no migration. **Every run is still approved by a person** — which is what this card's guard list says, and that half remains true.

## Steps

Source heading: **Steps 6 · four read, two write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather 48 hours of intervals | Landed by the meter connection; this only reads them | `read` |
| 2 | Work out each meter's own normal | Its 90-day average, not a fleet number | `read` |
| 3 | Flag continuous flow or a spike | Both thresholds above; the larger of the two wins | `read` |
| 4 | Apply guards and once-a-week | Opted out, in dispute, already told — skipped, not sent | `read` |
| 5 | Queue the alert | After approval, or unattended once trusted | `writes` |
| 6 | Record it against the meter | So next week's run knows | `writes` |

## Guards — what it may never touch

- **Never include: Opted out · Dispute · Told this week · Sample.** Guards are evaluated before any step.
- **Once per meter every 7 days.**
- **Quiet hours from Settings, 20:00–08:00.**
- **The leak text names the utility, the address and the hours — never the account or a dollar figure** (`RBR-15`), because a customer cannot act on either.
- Under the AI data ruling nothing here leaves the building except through the tenant's own notification provider.
- **Every run is approved until open decision 4 is ruled.**

## Produces

9 alerts queued · 2 skipped, told this week · 1 no channel — and the text each customer receives, shown in full before it goes.

### The run, with the source's own figures

**Today · 07:30 — "9 alerts queued."**

- Tiles: **9** Alerts queued · **2** Told this week · **1** No channel · **~11,000 gal** Water at stake.
- Table — Meter · Account · Pattern · Gal / day · Channel · Sent, showing 1–4 of 12: WM-04471 · Alvarez, M. · 14 Cedar St · Continuous · 26 h · 1,140 · Text · Queued; WM-01128 · Riverside Apts · 4.2× normal · 3,900 · Email · Queued; WM-02871 · Brant, H. · 91 Ridge Ln · Continuous · 31 h · 860 · Text · Queued; WM-03390 · Nunes, R. · 33 Bell Ave · 3.1× normal · 640 · — · No channel.
- What the customer receives, in full: *"Silver Creek Water: water has been running at 14 Cedar St for 26 hours. If nobody is using it, please check for a leak. Reply STOP to opt out."*
- Action: ↓ Alerts. Channel reads — on the row with no channel.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-111, status UNVERIFIED): The clerk sees "9 alerts queued" and reads the exact text a customer receives, naming the address and hours and never a dollar figure; the row with no channel says so.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R11.png` | `RBS-004-R11.md` | `…/runbooks/leak-alert` | `S150-R11`, figure 19 |
| Result | `RBS-006-R11.png` | `RBS-006-R11.md` | `…/runbooks/leak-alert/runs/latest` | `S152-R11`, figure 20 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R11` and `S152-R11`. This repository numbers them `RBS-004-R11` and `RBS-006-R11` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

The one Action to let run unattended first, once open decision 4 allows any unattended run at all. It is informational, it cannot cost a customer money, and every guard is a fact about the account. Its value is the call it prevents: a customer told on Tuesday that water has been running for 26 hours does not ring on the 20th about a $600 bill.

## Design notes on the result

The message is on the result screen in full, because a clerk approving nine texts wants to read one. It names the utility, the address and the hours — never the account or a figure in dollars, which a customer cannot act on.

## Open questions and stated absences

- ~~**Open decision 4 is unruled.**~~ ✅ **CLOSED 2026-09-06 as `OQ-RBS-1733` → `BR-RBS-041`, and stamped here on 2026-09-07** rather than left as a body that describes the open world. Permission is granted **up front, per runbook**; the three-clean-run ratchet is not built. The parameter stays read-only because wave `L3` has not built the switch, not because anything is unruled. See the Parameters section above for the ruling in full.
- **A trigger disagreement between the two source documents.** The specification's coverage table gives this runbook *⚡ Intervals landed*; the card's `Runs` parameter reads *Daily 07:30*. Both are recorded here; neither has been reconciled by a ruling.
- **An assumption the source relies on and never states:** text-message consent is a single boolean on the account (`sms_reminders`) and it is enough for a leak alert. A separate consent per message kind would change this runbook's guard.
- The row with no channel is the data-hygiene runbook's problem, and it says so.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-111: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
