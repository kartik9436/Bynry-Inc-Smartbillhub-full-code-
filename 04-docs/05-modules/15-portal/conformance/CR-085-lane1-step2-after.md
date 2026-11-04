# CR-085 step 2 lane 1 · **THE FRAME, BUILT** — every anchor measured before and after, at 390 and 1280

**This is the AFTER of `CR-085-lane1-spacing-anchors.md` and
`CR-085-lane1-frame-and-headings.md`**, which are the same lane's step-1
measurements and are the specification this work was built to. Every figure
below is `getComputedStyle` in Chromium against a bundle built from this lane's
own tree, signed in to `brazosbend` as a real portal customer. Nothing here is
read off a stylesheet and reported as though it had rendered.

⚠ **MEASURED ON THIS LANE'S OWN SERVER, NOT THE SHARED STACK.** The shared stack
on `:8401` serves `/home/user/SMARTBillHub/07-frontend/dist` and is shared with
other lanes; it was not restarted, rebuilt or re-seeded. This walk ran a second
copy of the same `server.mjs` on `:8611` over this worktree's `dist`, proxying
`/api` to the same backend — so the API, the tenant and the data are the shared
ones and only the bundle is this lane's.

---

## 1 · The anchor table — BEFORE (step 1) and AFTER (this build)

| anchor | rule 39 | BEFORE @390 / @1280 | AFTER @390 / @1280 |
|---|---|---|---|
| **label → input** | 5 | **4 / 4** | **5 / 5** ✅ |
| **input → helper** | 6 | **17 / 17** | **6 / 6** ✅ |
| **field → field** | 20 | **12–16** | **20** where the kit's `TwoUp` is the container · **still 12 / 16** where a screen stacks its own — see §5 |
| **`.input` padding** | 6 × 10 | **8 × 12** | **6px 10px** ✅ |
| **`.input` min-height** | 36 | **auto** (41px tall) | **36px** (37px tall — see §3) |
| **wizard rail margin-bottom** | 24 | **16** | **24** ✅ |
| **wizard step cell** | 16 × 20 | **8 × 8** | **16 × 20** ✅ |
| **wizard step icon gap** | 12 | **8** | **12** ✅ |
| **`--space-5`** | 20px | **not declared** | **20px**, in `tailwind.css` AND `tokens.css` ✅ |
| **`--sp-5`** | must not exist | absent | absent ✅ |

Read on `/my-details` and `/accounts/add` at 390: `labelToInput: 5`,
`fieldToField: 20`, `input { pad: "6px 10px", minH: "36px", h: 37 }`. Read on
`/my-details/preferences`, `/report` and `/track`: `inputToNext: 6`,
`nextTag: "P"`, `helperMarginTop: "6px"` — the helper's own margin, which is what
proves the paragraph reset landed and did not eat the utility.

⚠ **`fieldToField` READS NEGATIVE ON `TwoUp` AT 1280 AND THAT IS NOT A FAULT** —
−62 on `/my-details` and `/accounts/add`. `TwoUp` becomes two columns at that
width, so the second field starts above the first one's bottom edge. The 20px is
the 390 reading, which is where the two fields are actually stacked.

---

## 2 · The two heading bars

| | BEFORE @390 | BEFORE @1280 | AFTER @390 | AFTER @1280 |
|---|---|---|---|---|
| signed-in bar | **57** | **57** | **57** | **57** |
| **guest bar** | **147** — three rows | **96** — two rows | **57** ✅ | **57** ✅ |

**The guest bar now measures exactly what the signed-in bar measures, at both
widths**, which is what the blueprint's block D ratifies. The seven errand words
and the language control moved to a band of their own beneath it — the same
header → nav arrangement the PO ruled for the signed-in half on 2026-09-08.

⚠ **AND THE TRADE IS STATED RATHER THAN LEFT TO BE DISCOVERED.** Moving the
errands out did not delete them. The band measures **124px at 390** and **61px at
1280**, so the guest side's TOTAL chrome went **147 → 181** on a phone and
**96 → 118** on a desktop. A reader who saw only *147 → 57* would draw the wrong
conclusion.

**Why that is still the right trade, and why the band was NOT shaved to win the
difference back.** What the blueprint ratifies is the BAR — *"a third bar would
mean a customer could not tell at a glance whether they are signed in"* — and the
bar is now identical on both sides of the product at both widths, which is the
thing that was broken. The band's `py-3` is `--space-3`, a step of the very scale
this commit exists to enforce; dropping it to `py-2` would buy 8px by doing the
exact thing rule 39 was ratified to stop (*"the components are too much close"*).
**The real lever is the number of destinations** — seven errand words plus a
language control in one band — and that is an information-architecture question
for the Product Owner, not a padding shave for a lane to take on its own.

---

## 3 · The one figure that does not hit its anchor, and why

The portal input measures **37px** tall against the anchor's 36. Its padding is
exactly 6 × 10 and its `min-height` is exactly 36px; the extra pixel is the type.
The staff `.input` reaches 36 because it is `--text-md` (14px); the portal runs
on `--text-body` (15px) because a customer reads this on a phone, and
15 × 1.55 + 12 + 2 ≈ 37. **The rule ratifies the padding and the minimum and both
are now exact.** Changing the portal's body type to hit 36 would be a type
decision made to satisfy a spacing rule, which is the wrong trade and is not
this lane's to make.

---

## 4 · Titles, headings and chrome

* **One title size.** 40px / 800 on every portal screen measured, the three T7
  card screens included — `Welcome back`, `Find your account`, `Send me a reset
  link` all computed **25px / 700** before this build.
* **A failed read keeps its heading.** Walked at both widths on a bill number
  that does not exist: `CWP-028` draws *Your bills* at 40/800 with
  `data-screen="CWP-028"`, `data-portal-state="failed"`, the sentence *"We could
  not read this bill."* and the back link *← Bills*. Before this build that
  branch rendered one grey sentence in a bare card — no heading, no screen mark,
  no door.
* **No horizontal overflow at either width on any address walked.**

---

## 5 · What this lane did NOT do, said plainly

* **`usage/Usage.tsx` (CWP-033) still draws no page head.** It is not the
  ten-screen pattern — it composes no `PageHeader` anywhere — and it is
  `pageHeadCensus.test.ts`'s one remaining `AWAITING_ANOTHER_LANE` entry.
* **No screen was given a WAY OUT of its failed state.** `PortalState` can carry
  them and its test proves it; which control belongs on which screen is the
  owning lane's work, and a *Try again* wired to nothing would have been worse
  than none (`DEF-MET-4764`).
* **FIELD → FIELD IS NOT 20 EVERYWHERE, AND THIS IS THE ONE ANCHOR THIS LANE
  DID NOT FULLY CLOSE.** The kit's own field container (`TwoUp`) is `gap-5` and
  measures 20. Five screens stack their fields in a container of their own —
  `flex flex-col gap-3` on `/sign-in`, `/enrol` and `/pay`, `gap-4` on `/report`
  and `/start-service` — and those still measure **12** and **16** at both
  widths. That class is per screen and belongs to the lane that owns it, so it
  is recorded here and on `DEF-CWP-4856` (**partially-fixed**, not fixed) rather
  than swept. The two figures a shared component CAN own — 5 and 6 — are
  measured and exact.
* **`DEF-CWP-4922` stays open.** 32px is still unused in the portal and the
  distribution of the seven steps is still lopsided; this lane moved the shared
  anchors and not the fifty screens.
* **The staff app was not touched.** `DEF-SHL-4921` — the staff form kit renders
  the helper BETWEEN the label and the input, in all five field variants across
  28 files — is the same rule broken on the other side of the product and is
  still open.
