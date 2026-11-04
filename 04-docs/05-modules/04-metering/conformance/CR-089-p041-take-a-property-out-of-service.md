# P11 · Take a property out of service — THE DRAWN SPECIFICATION

**Source:** *Premises & Units Blueprint 2*, **pages 41–44** (plate header p41,
screen p41–p44). Extracted 2026-09-10 from
`origin/claude/confirm-understanding-3ktufc:05-prototype/Premises & Units Blueprint 2.pdf`
(md5 `f034d6e42c0caad658fadfdf6e4704eb`), read with `10-scripts/pdf/pdf_text.py`
**and looked at** as rendered PNGs at scale 1.6.

**State chip:** `NEW BUILD` · **Commitment:** `PUJ-21`
**Screen ids:** `P11` — `PRM-02 · PRM-03`
**CR-089 task row:** **`D1`** (wave D — a property can be taken out of service,
`PUJ-21`, `BR-MET-1164`)

⚠ **`NEW BUILD` MEANT *DOES NOT EXIST* WHEN THE BLUEPRINT WAS DRAWN.** It exists
now: `07-frontend/src/features/metering/StatusChangeDialog.tsx`, landed by
CR-089 wave D. The chip is recorded as drawn, and the screen's existence is a
fact about today, not a correction to the blueprint.

⚠ **EVERYTHING BELOW IS FROM THE BORDERED GREY FRAME ONLY.** The amber block on
page 41 (*"There is no way to do this…"*) is the problem, not the target; the
teal *WHAT CHANGED* block on page 42 is rationale.

---

## Header

**Kicker** `PREMISE`
**Title** `Change status`
**Sub-line** `Currently Active.`

## Actions, in the order drawn

| # | label | tier | where |
|---|---|---|---|
| 1 | `Cancel` | secondary | top right of the frame, on the title row |
| 2 | `Show them →` | inline link | once per blocked row, right-aligned (×3) |
| 3 | `Cancel` | secondary | footer, left |
| 4 | `Deactivate premise` | **danger** | footer, right |

**Primary action:** `Deactivate premise`, `in the danger tier — outlined, filling
on hover, never the standard primary.`

## Tabs

**None.**

## Tiles

**None.** `COGNITIVE LOAD`: *"Three inputs, one refusal panel, two buttons.
Nothing else is on the screen."*

## Fields — three inputs, in this order

| # | label | control | drawn value | width |
|---|---|---|---|---|
| 1 | `New status` **\*** | select | Inactive — no longer takes service | 1 of 2 |
| 2 | `From` **\*** | date | 09/30/2026 | 2 of 2 |
| 3 | `Why` **\*** | text | Demolished — permit 2026-1184 | full row |

All three carry a required asterisk.

## The refusal panel

Amber, drawn BELOW the three inputs, inside the frame.

**Panel heading:** `NOT WHILE THESE ARE LIVE`

**Table** — a plain two-column table, one row per blocker, in this order:

| # | left column (text, left-aligned) | right column (link, right-aligned) |
|---|---|---|
| 1 | `3 units are still active` | `Show them →` |
| 2 | `2 accounts are still open` | `Show them →` |
| 3 | `4 meters are still on this property` | `Show them →` |

**Helper beneath the table, verbatim:**
`Close the accounts, remove the meters and deactivate the units first. Then this can be done.`

⚠ **THE ROW ORDER IS `units · accounts · meters`, AS DRAWN.** `PUJ-21` on page 50
names a different order and a different word — *"4 active units · 9 attached
assets · 3 open accounts"*. The frame draws **meters**, third. The drawing wins
(§16); the conflict is recorded, not resolved.

## Footer

`Cancel` *(secondary, left)* · `Deactivate premise` *(danger, outlined, right)*.

**Beneath the footer, left-aligned:** the held line — `Held: 3 units still active.`

## States — exact sentences

| state | drawn sentence |
|---|---|
| **Blocked** | `The three counts, each linked. The commit is held and the held line names the first blocker in five words.` |
| **Clear** | `The refusal panel is replaced by the consequence: what stops billing, what happens to the meters, and what the record will read afterwards.` |
| **Already inactive** | `The control offers reactivation instead, with the same date and reason.` |
| **Read-only role** | `The button is absent, not greyed. A control a person may never press is not a control.` |

⚠ **THE CONSEQUENCE AND THE REFUSAL ARE ALTERNATIVES, NOT NEIGHBOURS.** The
*Clear* state says the refusal panel is **replaced by** the consequence. The
drawn frame is the blocked state and carries **no consequence box at all**.

## Frame metadata

* **FOR** — `A clerk closing a record — a demolished building, a flat merged into its neighbour, a property sold out of the service area. Rare, consequential, and irreversible enough to be worth a screen of its own.`
* **HOW YOU GET HERE** — `The property's page or the unit's page → Change status. There is no other route, deliberately: this is not something to stumble into from a list.`
* **COGNITIVE LOAD** — `Three inputs, one refusal panel, two buttons. Nothing else is on the screen.`
* **COMPONENTS** — `ConfirmDialog` `FormModal` `PlainTable` `StatusPill` `RefusalStrip` `InlineLinkTo`
* **RULES** — `The danger tier for destructive commits. A refusal caps at five or six words. A consequence preview before the commit. Every money-or-service action is recorded with who, when and what.`

## The unit's version

Drawn as one sentence in the teal block, recorded here because it is the whole
specification for `U12`'s relationship to this screen:

> `A unit's version is the same screen with one row: whether an account is open on it.`

**ONE row.** Diffing `U12` is outside this file's page range.

## Commitment this screen carries

| id | statement | done looks like (verbatim) |
|---|---|---|
| `PUJ-21` | A property can be taken out of service | `A clerk presses Change status, sees 4 active units · 9 attached assets · 3 open accounts each linked, and the commit is held reading Close the accounts first; with all three clear, the date and reason are required and the property goes inactive.` |
