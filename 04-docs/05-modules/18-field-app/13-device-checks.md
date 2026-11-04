# 13 · Device checks — the two proofs a test cannot run (T-51, T-52)

**Change:** CR-187-BRC10 · Phase 14 (Proof) · lane PROOF, 2026-10-21
**For:** the PO's tester, with a real handset, real gloves and real daylight.
**Why this page exists:** every other Phase 14 proof is a permanent test in
`field-app/tests/proof/` and runs on every change. These two cannot: a
fingertip in a work glove and the noon sun on a driveway are not in a test
runner. What the code CAN check is already checked (every control's size in
the screen sweeps, contrast in all three themes and text at 200% in
`tests/proof/a11y.test.tsx`) — this page is the part that needs a person.

Rules being checked (signed): **R39** *"Built for gloves and weather: primary
action 56pt, any interactive control 48pt, icon-only button 48pt, 8pt clear
between adjacent targets"* (PO ruled) · **AD-09 / T-08** *"Sunlight (maximum
contrast: pure white, black text, 2–3px borders, one size up)"* · **E2E-24**
*"Walked in sunlight, outdoors, with gloves, on the cheapest handset the
utility issues"*.

---

## 0 · Before you start (both checks)

| What | How |
|---|---|
| The handset | **The cheapest handset the utility issues to its crews** — not a developer's phone. Write down make, model, screen size (inches) and Android/iOS version. |
| The build | Open the menu (FF-09): the version is on screen (R40). Write it down — every result below is for that build and no other. |
| Sign in | A test technician on the test utility, with at least **one job of each kind** on the day (a meter exchange, a disconnect, a reconnect) and **one reading route**. |
| Text size | The handset's own text size at its **default**. (200% is proved in the test suite; this is the size crews actually use.) |
| Where to write | One row per screen in the results table at the end of this page, in a copy of this file named `13-device-checks-<build>-<date>.md` beside it, committed. A defect goes in the defect register with the screen id and the build (the change process's step 7: *"tell the reporter which build to look in"*). |

---

## 1 · T-51 — Touch and reach, gloved (R39)

**Gloves:** the utility's own issue work glove (write down the make). If crews
wear two kinds (summer, winter), do the walk in the **thicker** one.

**Walk these screens, in this order** — they are the ones a technician touches
most with gloves on: FF-10 Today · FF-15 the job · FF-16 Safety · FF-17 Tasks ·
FF-20 Readings (the keypad) · FF-21 Photos · FF-23 Materials (the quantity
stepper — the most-tapped control in the app, *"hit a hundred times with gloves
on"*) · FF-33 Signature · FF-34 Close · RW-05 The walk · RW-09 Read entry ·
RW-17 Can't read · FF-50 Sync.

### What to measure

| # | Check | How to measure | Pass | Fail |
|---|---|---|---|---|
| T51-1 | **Every control hits first time, gloved** | Tap each button, row, chip, tab and stepper on the screen once, gloved, at arm's length, standing. Count taps that miss or hit the wrong thing. | 0 misses on the screen | Any miss — write the control's words and the screen id |
| T51-2 | **Neighbours do not steal the tap** | For every pair of controls that touch or nearly touch (stepper − and +, two buttons in a footer, two rows of a list), tap the left/top one 10 times, gloved. | 10 of 10 on the intended control | Any tap lands on the neighbour |
| T51-3 | **Primary action is the big one** | On each screen with a primary (orange) button, measure its height on the glass with a ruler. | ≥ **8.9 mm** on a typical 400–460 ppi handset (56pt ≈ 8.9 mm at 160pt per inch) | Smaller — record the mm |
| T51-4 | **Every other control** | Measure the smallest control on the screen (usually an icon button). | ≥ **7.6 mm** (48pt) | Smaller — record the mm |
| T51-5 | **Clear space between targets** | Measure the gap between the two closest controls. | ≥ **1.3 mm** (8pt) | Smaller — record the mm |
| T51-6 | **Reach, one hand** | Holding the handset in the working hand, thumb only: can the primary action and *Back* be reached without regrip? | Yes on every screen | Regrip needed — screen id |
| T51-7 | **The keypad, wet** | FF-20 and RW-09: type a 5-digit reading with a gloved finger, then with a damp glove. | The figure on screen matches what was typed, both times | Any wrong digit |

> ℹ Points to millimetres: 1pt = 1/160 inch on the platforms' own scale, so
> 48pt ≈ 7.6 mm and 56pt ≈ 8.9 mm whatever the handset's pixel density. If a
> measurement is borderline, write the mm and let the reviewer decide.

---

## 2 · T-52 — Sunlight, outdoors, at noon (AD-09)

**When and where:** a clear day, **between 11:30 and 13:30**, outside, the sun
behind the tester's shoulder (the worst case: glare on the glass). Screen
brightness on **automatic** (what crews leave it on), then repeat the failures
at **maximum**.

**Theme:** switch to **Sunlight** on FF-51 *Settings*. Do the whole walk in
Sunlight, then repeat T52-1 in **Light** for comparison.

**Walk:** FF-63 Home · FF-10 Today · FF-15 the job · FF-16 Safety (the lock
notice) · FF-20 Readings (a reading out of range — the warning) · FF-27 Money
(the "balance not checked" line) · FF-34 Close · FF-50 Sync (a refused item if
the test utility has one) · RW-05 The walk · RW-15 High or low (the warning).

### What to check

| # | Check | How | Pass | Fail |
|---|---|---|---|---|
| T52-1 | **Read the screen at arm's length** | Read every line of text aloud, handset at arm's length, without shading it with a hand. | Every word read correctly | Any word misread or unreadable — screen id and the words |
| T52-2 | **Warnings are seen first** | On FF-16, FF-20, RW-15: before reading anything, say what the screen is warning about. | The warning is the first thing named | The warning is missed or read after other text |
| T52-3 | **Where the edges are** | On FF-20 and FF-23: point to each input box's edge and each button's edge. | Every edge found (Sunlight draws 2–3px borders) | An edge cannot be found |
| T52-4 | **Status colour is not the only signal** | On FF-50 and FF-10: say which items are sent, waiting and refused **without** relying on colour. | Each state named from its words/icon | A state only distinguishable by colour |
| T52-5 | **Light vs Sunlight** | Repeat T52-1 in Light on FF-10 and FF-15. | Sunlight is readable where Light is not, or both are | Sunlight is NOT better than Light — a theme defect |
| T52-6 | **The photo and signature** | Take one photo (FF-21) and capture one signature (FF-33) in the sun. | The preview and the pad are visible enough to confirm | Cannot tell whether the photo/ink took |

---

## 3 · The eight portal accessibility questions, as they apply to this app

The customer portal is held to **WCAG 2.1 AA** (PO ruling 2026-09-10,
`12-governance/22-product-maintenance-process.md` §6). The field app is
staff-facing, but the same eight questions are the cheapest honest check:

| # | Question | Field app | Where it is answered |
|---|---|---|---|
| 1 | Everything without a mouse? | **Partly** — a handset with a switch control or a keyboard: every control is a native accessible element with a role, so it is reachable; **not walked on a device yet**. | Tester: one walk of FF-10 → FF-15 → FF-34 with the platform's switch access on. |
| 2 | Always see where you are? | **Needs a person** — the platform draws the focus. | Same walk as 1. |
| 3 | Every box has a label? | **Automated** — every text box has an accessibility label, on every screen. | `tests/proof/a11y.test.tsx` |
| 4 | One main heading? | **Automated** — every screen names itself with a header, its own or the navigation header's. **FF-01 (the splash) has none** — reported. | `tests/proof/a11y.test.tsx` |
| 5 | Text dark enough? | **Automated** — every piece of text measured against what it sits on, in all three themes. Brand-orange labels are held to 3:1 as MARKS under R100 — reported, see the lane report. | `tests/proof/a11y.test.tsx`, `tests/theme/contrast.test.ts` |
| 6 | Narrow window, enlarged text? | **Automated (static)** — every screen at 390pt wide with text at 200%: nothing refuses to scale, no words in a box too short for them, controls reachable. Icon glyphs and initials in fixed circles outgrow the circle — reported. **On a device:** walk FF-10, FF-15, FF-20 with the handset's largest text size. | `tests/proof/a11y.test.tsx` + tester |
| 7 | Things announced, not just shown? | **Partly** — toasts are a live region; danger notices are alerts; **warning and info notices that appear after an act are not announced** (e.g. *"Camera not available yet."*). Needs a person with the screen reader on. | Tester: TalkBack/VoiceOver on, FF-20 out-of-range reading, FF-21 take a photo, FF-50 send. |
| 8 | Check or undo before money moves? | **Does not apply** — the field app never moves money (R16). | — |

---

## Results (copy this table into `13-device-checks-<build>-<date>.md`)

| Check | Screen | Handset · build | Glove / light | Result (pass / fail + measurement) | Defect id |
|---|---|---|---|---|---|
| T51-1 | FF-10 | | | | |
| … | | | | | |
