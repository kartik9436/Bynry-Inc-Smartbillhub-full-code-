# RB-130 — Runbook 30 · Portal and autopay adoption

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
| **Kind** | Not stated. The done sentence has an invitation **queued behind approval**, which is what an Action does; the source does not say so, and this file does not decide it. |
| **Category** (one home, from the fixed list of sixteen) | Customer portal — the source names this as the empty Customer portal category's first runbook: *"Paperless and autopay adoption, and customers who never opened the portal."* |
| **Tags** | Not stated. |
| **Phase** | later |
| **Trigger** | Not yet defined. |
| **Subject and unit of work** | Not yet defined. |
| **Step modes** | Not yet defined. |
| **Result blocks it composes** | Not yet defined. |
| **Ports it holds** | Not yet defined. |
| **Proves** | — |
| **Waits on** | — |

## What the source says about it

The source gives one sentence and no more. **Done looks like:** A manager sees paperless, autopay and portal sign-up as percentages of accounts, and the customers who never opened the portal, with the invitation queued behind approval.

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

**Done looks like** (the commitment's own sentence, RB-130, status UNVERIFIED): A manager sees paperless, autopay and portal sign-up as percentages of accounts, and the customers who never opened the portal, with the invitation queued behind approval.

## Its screens

**Neither frame is drawn.** The source's screen table stops at runbook 27, so there is no `RBS-004-R30` and no `RBS-006-R30` in `04-docs/05-modules/17-runbooks/wireframes/` and no build sheet to check a build against.

The commitment card names the renderers rather than frames: **`RBS-002` card · `RBS-004` renderer · `RBS-006` result** (the source writes them `S148`, `S150`, `S152`). Both are renderers over the definition and the report, so this runbook needs **no new screen** when it is defined — it needs a card, and then its two instances drawn.

## Open questions and stated absences

- **No card, no wireframes, no build sheets.** The setup and result screens for this runbook are not drawn; the source's screen table stops at runbook 27.
- **Customer portal is one of the five empty categories**, and is not drawn as a chip until a runbook arrives.
- Runbooks 4, 11 and 13 already **touch** Customer portal as a tag.
- The portal itself is `CR-068`, and its languages are **English and Spanish only** (PO ruling, 5 September 2026).

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-130: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
