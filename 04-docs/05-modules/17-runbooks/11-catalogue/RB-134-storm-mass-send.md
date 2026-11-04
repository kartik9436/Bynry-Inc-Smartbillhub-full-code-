# RB-134 — Runbook 34 · Storm mass-send

> **NAMED, NOT DEFINED.** The source gives this runbook a number, a home where one is stated, and **one sentence saying what done looks like — and nothing else**.
>
> Scope, parameters, steps, guards, ports and both screens are **not yet defined**. *"A card like the ones above is the next act."* Nothing below has been inferred to fill the gap.
>
> ⚠ **PARKED BY THE PRODUCT OWNER, 2026-09-07 — DO NOT DESIGN THIS.** Verbatim:
> *"Please park those runbook - we will handle them later … I will give you full
> list what needs to be done, they are not yet design"*.
>
> **The line above is not an invitation.** *"A card like the ones above is the
> next act"* is true, and that act is the Product Owner's, not a lane's. Six
> runbooks are in this state and three of them would SEND MESSAGES TO CUSTOMERS
> if they turned out to be Actions — who they write to, what they say and when
> they fire are facts only the utility holds, so a lane inferring them would be
> writing the customer's requirement on their behalf. That is exactly what the
> change process means by filing our misunderstanding as a "change".
>
> **What a lane should do if it lands here:** nothing. Do not write the card, do
> not mint an open question for it, and do not build a stub — the parking IS the
> answer until the list arrives. `CR-075`'s buildable scope closed at **28 of 34
> runbooks** on this date, and these six are the six.

## What it declares

| | |
|---|---|
| **Kind** | Not stated. The done sentence has a send **queued behind approval and the cap**, which is what an Action does; the source does not say so, and this file does not decide it. |
| **Category** (one home, from the fixed list of sixteen) | Not stated in the source. The reserved-definitions section says each of these eight *"has a number, a home, a sentence saying what done looks like, and nothing else"*, but no home is written down for this one. |
| **Tags** | Not stated. |
| **Phase** | 3 |
| **Trigger** | Not yet defined. |
| **Subject and unit of work** | Not yet defined. |
| **Step modes** | Not yet defined. |
| **Result blocks it composes** | Not yet defined. |
| **Ports it holds** | Not yet defined. |
| **Proves** | — |
| **Waits on** | a delivery provider · RB-044 |

## What the source says about it

The source gives one sentence and no more. **Done looks like:** Before a storm a clerk sees how many accounts a text, an email and a letter would reach, the exact message, and the send queued behind approval and the cap.

## Scope — how the set is decided

Not yet defined.

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

*The source names no parameters for this runbook.*

## Steps

*Not yet defined. The source carries no steps for this runbook.*

## Guards — what it may never touch

*Not yet defined. The source names no guards for this runbook.*

## Produces

*Not yet defined.*

**Done looks like** (the commitment's own sentence, RB-134, status UNVERIFIED): Before a storm a clerk sees how many accounts a text, an email and a letter would reach, the exact message, and the send queued behind approval and the cap.

## Its screens

**Neither frame is drawn.** The source's screen table stops at runbook 27, so there is no `RBS-004-R34` and no `RBS-006-R34` in `04-docs/05-modules/17-runbooks/wireframes/` and no build sheet to check a build against.

The commitment card names the renderers rather than frames: **`RBS-002` card · `RBS-004` renderer · `RBS-006` result** (the source writes them `S148`, `S150`, `S152`). Both are renderers over the definition and the report, so this runbook needs **no new screen** when it is defined — it needs a card, and then its two instances drawn.

## Open questions and stated absences

- **No card, no wireframes, no build sheets.** The setup and result screens for this runbook are not drawn; the source's screen table stops at runbook 27.
- **Runbook 19 already reports the number this one depends on.** *Reachable by text* is a tile on the data-hygiene result — **1,350 of 2,907** accounts today, with **900 unreachable** — and the source says that tile exists *"because it is the number that decides whether the storm runbook works, and a utility should see it every month rather than discover it in a storm."*
- **Waits on a delivery provider.** Until one is connected the word is *Queued*, never *Sent* (PO ruling, 17 August 2026). `RB-044` is notice throughput per channel and a *still sending* state.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-134: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
