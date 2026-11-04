# CR-085 lane 1 · B14 rule 39 measured — every anchor, at 390 and at 1280

**Rule 39 was ratified on 2026-09-11 and this is a measurement of it, not a reading of it.**
Every figure below comes from `getComputedStyle` in a real browser against the bundle the
shared stack is serving (`07-frontend/dist`, built 04:52 on 2026-09-11 from tip `b4063d1e6` —
the commit this lane started from). Nothing here is read off a stylesheet and reported as
though it had rendered.

**Two applications are measured, because rule 39's ten anchors describe two different
things.** `.sidebar`, the topbar, `.kpi`, `th`/`td`, the wizard rail, the step and `.input`
are **staff classes** — `grep` finds not one of them anywhere under
`07-frontend/src/portal/`. The customer portal is a second front end written in Tailwind
utilities with no sidebar, no `.kpi` and no `.input`. So:

* **the staff app** was signed into on the shared stack and measured at **1280**, which is
  where the anchors as stated can be checked at all;
* **the portal** was walked at **390 and 1280**, all 50 addresses at each, with the two frame
  reads (`portal/public/front`, `portal/session`) stubbed live. The shared stack's
  `brazosbend` tenant has **0 customers and 0 `portal_settings` rows**, so without that stub
  the portal answers its holding page and no signed-in screen renders at all. **The CSS, the
  layout and every computed value are the real bundle's; only two JSON payloads are
  fixtures**, and every screen's own read was left to fail so the numbers below are the
  frame's rather than a fixture's.

---

## 0 · The headline, in four sentences

1. **A spacing scale already exists and it is not called `--sp-N`.** `tailwind.css`'s
   `@theme` block declares `--space-1 4 · --space-2 8 · --space-3 12 · --space-4 16 ·
   --space-6 24 · --space-8 32` — **six tokens**, confirmed live by
   `getComputedStyle(document.documentElement)`. Rule 39 asks for **seven**. The missing one
   is **20px**: `--space-5` resolves to nothing, and `p-5`/`gap-5` reach 20px through
   Tailwind's `--spacing: .25rem` multiplier rather than through a named token. `--sp-1` and
   `--sp-5` resolve to nothing either — no `--sp-N` property exists anywhere.
2. **The staff app matches most of the anchors, because the anchors were measured off it.**
   Sidebar 240, topbar 56, title 40/800, tabs 16/16, KPI 16/20 gap 6, th/td 8×12 and
   `.input` 6×10 min-h 36 are all exactly what the running staff app computes today.
3. **The portal matches almost none of them, because it was never built from them.** Page
   padding 24/20/24 against an anchor of 24/16/32; an input 8×12 and 41px tall against the
   product's 6×10 and 36px; a wizard rail at 16 against 24; a step cell at 8×8 gap 8 against
   16×20 gap 12 — and **32px does not appear in the portal at all**: `p-8`, `py-8`, `gap-8`,
   `mb-8`, zero uses.
4. **The field anatomy is wrong in both halves, in opposite directions.** The portal has the
   ORDER right and the rhythm flat. The staff form kit has the rhythm closer and **the ORDER
   wrong** — `FormModal.tsx` renders the helper **between the label and the input**, in all
   five field variants, which is the exact thing the PO ruled against.

⚠ **A SIBLING LANE MEASURED RULE 39 TOO AND THE TWO PASSES DO NOT OVERLAP —
`CR-085-lane4-04-spacing-rule-39.md`.** That one walks its own SCREENS signed in as a real
portal customer; this one walks the FRAME across all fifty addresses and the STAFF app, which
is the only place seven of the ten anchors exist. **They agree where they touch** (no
`--sp-N`; the scale is Tailwind's multiplier; the figures are identical at 390 and 1280) and
each found what the other could not — lane 4 found the `<p>` margin that explains the 17px
helper gap measured here, and this pass found the staff form kit's ORDER and the arbitrary
values below. Read both.

---

## 1 · The anchor table

`drawn` is rule 39 as ratified. `staff` is the running staff app at 1280. The two portal
columns are the running portal at those widths, with the modal value across all 50 addresses
and the count of addresses it held on.

| anchor | drawn (rule 39) | staff @1280 | portal @390 | portal @1280 | verdict |
|---|---|---|---|---|---|
| **page** top / side / bottom | 24 / 16 / 32 | `main` **24 / 24 / 56** | `main` **24 / 20 / 24** (47 addresses) | `main` **24 / 20 / 24** (47) | **neither matches.** Staff side 24 not 16, bottom 56 not 32; portal side 20 not 16, bottom 24 not 32 |
| **sidebar 240** | 240 | **240**, every screen | — no sidebar | — no sidebar | ✅ staff · n/a portal |
| **topbar 56** | 56 | **56**, padding 0/24, gap 16 | signed-in header **57** (34) · guest header **147** (13) | signed-in **57** (34) · guest **96** (13) | ✅ signed-in at both widths (57 = 56 + a 1px rule). ❌ **the guest bar is two rows at 1280 and three on a phone** |
| **title 40 / 800** | 40px, weight 800 | **40 / 800** on 5 of 6 screens · **32 / 800** on Settings | **40 / 800** (30) · **25 / 700** (3) | **40 / 800** (30) · **25 / 700** (3) | ⚠ two title treatments in the portal — 40/800 on the page head, **25/700** on the three T7 card screens (`/sign-in`, `/enrol`, `/forgot-password`). Documented as a different template, and it is still a second size |
| **tabs margin 16 gap 16** | mt/mb 16, gap 16 | **mt 16 · mb 16 · gap 16** on Plans & Rates and Payments · **mb 24 · gap 0** on Settings | portal tab strip **100px** tall, gap-x 24 / gap-y 0 | **50px** tall, same gaps | ❌ the staff app disagrees with itself; the portal's strip is not a `.tabs` and uses 24 |
| **KPI 16 / 20 gap 6** | padding 16 20, gap 6 | **pt/pb 16 · pr 20 · pl 0 · gap 6** | portal `KpiTile` is Tailwind, not `.kpi` | same | ✅ staff. The portal has its own tile |
| **th / td 8×12** | 8 vertical, 12 horizontal | **th 8/12 · td 8/12** | `MiniTable` (source): **td `px-3 py-2` = 8/12** ✓ · **th `px-3 pb-2` = 12 horizontal, 8 bottom, 0 top** | same | ⚠ the portal's header cell has no top padding, so a header row sits 8px shallower than the anchor |
| **rail margin-bottom 24** | 24 | no wizard open on any measured staff screen | `Stepper` **margin-bottom 16**, gap 8 (9 addresses) | **16**, gap 8 (9) | ❌ the portal rail is **16**, not 24 |
| **step 16×20 gap 12** | 16 vertical, 20 horizontal, icon gap 12 | not measured (no wizard open) | step cell `p-2` = **8×8**, icon `gap-2` = **8** | same | ❌ **all three are half the anchor** |
| **`.input` 6×10 min-h 36** | padding 6/10, min-height 36 | **6 / 10, min-height 36px** | portal `TextInput` **8×12, height 41** (10 addresses) · 8×12, height 38 (2) | identical at 1280 | ❌ **two input shapes in one product** |

**Two input shapes, filed as `DEF-CWP-4923`.**

**Horizontal overflow, all 50 addresses, both widths:** **none.**
`document.documentElement.scrollWidth` equals `clientWidth` everywhere — the `flex-wrap` fix
recorded in `PortalShell.tsx` after the 2026-09-08 walk (461px inside a 390px viewport) is
holding.

---

## 2 · The field anatomy — the half of rule 39 with a worked ratio

Rule 39: **label → input 5px · input → helper 6px · field → field 20px, a ratio of ≈ 1 : 1 :
4**, and the clause that decides it: *"DOM ORDER ALONE IS NOT ENOUGH — the helper must READ
as attached to the input above it, never to the label below it, and a 3/3/9 rhythm destroys
that even with correct markup."*

| | order | label → input | input → helper | field → field |
|---|---|---|---|---|
| **ratified** | label → input → helper | **5** | **6** | **20** |
| **portal** (`FormField`, `primitives.tsx` line 585) | label → input → helper ✅ | **4** everywhere | **4** by construction (17 measured — see below) | **12** on `/sign-in`, `/pay`, `/enrol` · **16** on `/start-service`, `/accounts/add`, `/ask-for-a-plan` |
| **staff** (`FormModal.tsx`, all five field variants) | label → **helper** → input ❌ | 5 (to the helper) | — | **14** |

**The portal's number is one number.** Its field container is `<div className="flex flex-col
gap-1">`, and `gap-1` is 4px — measured as `containerGap: "4px"` on every one of the eight
portal screens that drew a field, at both widths. Label → input, input → helper and input →
error are all that same 4px. ⚠ **Where the measured input → helper reads 17px rather than 4,
the extra 13 is the browser's own `1em` paragraph margin**, which `global.css` restores on
purpose and the kit's `<p>` elements do not reset — a sibling lane has that root cause filed
in full as `DEF-CWP-4845` and `DEF-CWP-4856`, and it is the better explanation of the same
measurement. **Field → field goes NEGATIVE on two screens at 1280** (−65 and −116), which is
not a fault: `TwoUp` becomes two columns at that width, so the second field starts above the
first one's bottom edge. That is the responsive behaviour working.

**The staff app's is the defect rule 39 was written against.** `FormModal.tsx` renders

```
<div className="field">
  <FieldLabel … />
  {props.help !== undefined && <p className="field-help" …>{props.help}</p>}
  <input … />
```

— label, **then the help**, then the control. That shape is in all five field variants
(lines 241, 311, 363, 624, 786) and again in `CustomFields.tsx` line 239; `field-help` is
referenced by **28 files**, so it is the shape of every staff form in the product. Measured
through the real stylesheet with a probe element: `.field > label { margin-bottom: 5px }`
and `.field-help { margin: 0 0 5px }`, so the rhythm is 5 / 5 **with the helper in the wrong
place**. And `.modal-body { gap: 14px }` makes field → field **14px** — one of the four
numbers rule 39 forbids by name (*"NO AD-HOC 3 / 7 / 9 / 14 ANYWHERE"*) sitting in the shared
dialog every staff form opens in. Filed as **`DEF-SHL-4921`**.

⚠ **B14 rule 38 settles this without a further ruling:** *"where a drawing and our UI rules
disagree about how a FORM IS BUILT, the UI rules win."* The helper's position is
construction, not content.

---

## 3 · The off-scale audit, counted

**Stylesheets.** Every literal `px` value in a `padding`, `margin` or `gap` declaration
across `07-frontend/src/**/*.css`, comments stripped: **100 values, of which 68 are off the
seven-step scale.** The four numbers rule 39 names appear as **3px ×1 · 7px ×1 · 9px ×2 ·
14px ×6**; the rest are 1, 2, 5, 6, 10, 18, 28, 30, 34, 48, 56 and 64.

They concentrate where it costs most:

| file | off-scale values | what it is |
|---|---|---|
| `components/AppShell.css` | **23** | the frame every staff screen sits in |
| `components/FormModal.css` | **15** | the form kit every staff dialog composes |
| `features/tenancy/SettingsPage.css` | 6 | |
| `components/StateFrame.css` | 5 | the loading / failed / empty frame |
| eight other files | 19 | |

⚠ **SOME OF THOSE ARE RULE 39'S OWN ANCHORS, AND THAT IS A COLLISION INSIDE ONE RULE.**
`.kpi { gap: 6px }` and `.input { padding: 6px 10px }` are off the seven-step scale **and are
exactly what rule 39 ratifies**; the field anatomy ratifies a third pair, 5 and 6. So the
scale as written governs LAYOUT gaps — between fields, between blocks, between sections —
while the anchors include INTRA-CONTROL values that are deliberately not on it. **A lane
building to rule 39 meets that on its first control and the rule does not say which clause
wins.** Recorded here rather than guessed at; it is a question for the PO and this lane is
not the place to put it, because a rule-versus-rule collision should reach them once from one
place.

**The portal's Tailwind usage** is lopsided, and the distribution is the finding. 566 spacing
utilities:

| step | px | uses in the portal |
|---|---|---|
| `-1` | 4 | 43 |
| `-2` | 8 | **163** |
| `-3` | 12 | **162** |
| `-4` | 16 | 98 |
| `-5` | 20 | **9** — seven of them the frame's own `px-5` gutter |
| `-6` | 24 | **8** |
| `-8` | 32 | **0** |
| off-scale | 2 / 6 | 10 (`0.5` ×4, `1.5` ×6) |

**Two thirds of every gap in the customer portal is 8px or 12px**, and the two steps rule 39
reserves for separating sections and ending a page are between them used eight times and
never. That is the PO's sentence measured: *"the components are too much close as well as
manage the margins also."* Filed as **`DEF-CWP-4922`**.

**And the front end holds 36 ARBITRARY spacing values in Tailwind brackets** — a padding,
margin or gap utility with a value in `[…]`, counted over every non-test `.tsx` in
`07-frontend/src`: `py-[3px]` ×11, `gap-[2px]` ×6, `py-[7px]` ×4, `pl-[18px]` ×3,
`gap-[5px]` ×3, `px-[9px]` ×2, `gap-[18px]` ×2, `pb-[18px]` ×2, and one each of
`px-[14.4px]`, `gap-[0.4rem]` and `mt-[0.35rem]`. **All four numbers rule 39 bans by name —
3, 7, 9 and 14 — are present**, and `px-[14.4px]` is a FRACTIONAL pixel, which no scale of
any kind can contain. **Four of the 36 are in the portal**: `gap-[2px]` twice in
`primitives.tsx`, and `px-[9px] py-[3px]` in `PortalScreenIdTag.tsx`, which renders on every
portal screen. Filed as **`DEF-CWP-4928`**.

⚠ **THAT COUNT IS ALSO A CORRECTION OF THIS LANE'S OWN FIRST ANSWER, AND THE MECHANISM IS
WORTH MORE THAN THE NUMBER.** The first pass reported **zero** arbitrary values in the
portal. Its regex ended in `\b` immediately after the closing bracket — and `\b` cannot hold
between `]` and a space — so it matched nothing and returned 0 **truthfully, over everything
it could see**. That is law 7's *reports zero over a scope it silently excludes*, in a
counting script, and what exposed it was a sibling lane naming `px-[9px]` in
`CR-085-lane4-04-spacing-rule-39.md`. **Two independent passes at one rule is why it was
caught at all**, which is the argument for both existing.

---

## 4 · What is unbuilt, precisely

| the rule asks for | what exists today |
|---|---|
| `--sp-1 … --sp-7` | **no `--sp-N` property anywhere** — the browser returns empty for `--sp-1` and `--sp-5` at `:root` |
| a seven-step scale | a **six**-token `--space-N` scale in `tailwind.css`'s `@theme`, missing 20px |
| the scale used everywhere | 68 of 100 literal spacing values in CSS are off it; 32px is unused in the whole portal |
| label → input → helper | right in the portal, **wrong in the staff form kit**, 28 files |
| 5 / 6 / 20 | 4 / 4 / 12–16 in the portal; 5 / — / 14 in the staff kit |
| a gate | **none.** Nothing in this repo reads computed spacing, and B14's own status column says so at ratification |

⚠ **The cheapest thing that would hold any of this is not a token, it is the ORDER.** A
source check that fails when a helper element precedes its control inside the same field
container is writable today, needs no browser, and closes the half of rule 39 a customer
actually experiences. The figures need rendered output and there is no tool for that —
hard-won law 6's standing gap.

---

## 5 · The frame's own arithmetic, which is the number behind the ruling

On a 390px phone the signed-in portal spends this much before the first word of content:

| band | at 390 | at 1280 |
|---|---|---|
| heading bar | **57** | **57** |
| tab strip (six tabs) | **100** (three rows) | **50** (one row) |
| account line | **72** (two rows) | **40** (one row) |
| `main` padding-top | **24** | **24** |
| **total chrome** | **253px** | **171px** |

253px is **30% of a 390 × 844 phone viewport**, before anything the customer came for.

The guest half is worse in its own way: the guest heading bar alone measures **147px at 390
and 96px at 1280** — brand, seven nav words, two language words and *Sign in*, wrapped.
`DEF-CWP-4468` records this as *"two rows in English"*; **two rows is what it is at desktop
width, and at phone width it is three.**

⚠ **And the frame is not the same on both sides.** The guest bar carries a language control
(`GuestFrame.tsx` line 364); `PortalShell.tsx` contains no reference to language at all, so a
signed-in customer has none anywhere in the frame. ⚠ **That one is NOT a defect and was
withdrawn** — `GuestFrame.tsx` records the reason beside the control (a signed-in customer's
choice is STORED on `CWP-024` and reaches their letters too, and two controls for one setting
is how a product tells one person two things); `DEF-CWP-4924` stands as `invalid` and
`CR-085-lane1-frame-and-headings.md` §4 has the full reasoning. The signed-in
account line carries the account number and the service address and **neither the customer's
name nor the amount due**, where the blueprint draws all four — `DEF-CWP-4925`.

---

## 6 · How to re-run this, and the trap it cost

The method, so the next lane rebuilds it in ten minutes rather than an hour: resolve
`playwright-core` through `createRequire` on an absolute path to `07-frontend/package.json`,
stub `**/api/<tenant>/portal/public/front` and `**/api/<tenant>/portal/session` with
`context.route`, walk the 50 paths from `screenIds.ts` at 390 and 1280, and read
`getComputedStyle` on `[data-portal-frame]`, its `header`, `nav`, `[data-account-bar]`,
`main`, `h1`, `[data-field]` and `[data-stepper]`. Write the results after every page, not at
the end.

⚠ **One trap, paid for twice in this lane.**
`page.evaluate(<a string that is an arrow function>)` returns **the function**, not its
result, so every measurement comes back `undefined` and `JSON.stringify` writes `{}` — a file
that looks like a clean run of a check that measured nothing. Wrap it:
`page.evaluate('(' + probe + ')()')`. Two complete 50-address walks finished, reported
success and produced an empty object before the output was read rather than the exit code.
That is hard-won law 7's *incapable of failing* shape inside a measuring script, and law 7's
own habit (3) is what found it: **a check's output must distinguish pass from fail to a
reader, not merely to an exit code.**
