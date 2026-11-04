# CR-018 Phase 3 · THE SHARED-CLASS SPIKE — MEASUREMENT NOTES

**Read this before the decision-log row.** The row states the recommendation; this file
carries the numbers it was derived from, measured at tip `5dbf2d7` (v2.29.6) in an
isolated `git worktree`, against a live stack (`boot_stack.sh`, Postgres 16, built
bundle on `127.0.0.1:8090`).

Phase 1 migrated ONE screen and said plainly that it *"could not touch a single shared
class"* and that *"a Phase 2 for 179 shared classes remains entirely unmeasured."*
This is that measurement, on the widest family: `btn`, `btn-primary`, `btn-secondary`,
`btn-ghost` — and, because the census found them, `btn-sm`, `btn-danger`, `btn-link`,
`btn-icon`, `table-page-btn`, `settings-icon-btn` and **seven descendant rules that
re-style buttons from a parent**.

---

## 1 · THE CALL-SITE CENSUS — every site, not a sample

Parsed from `07-frontend/src/**/*.tsx` by matching `className=` values whose tokens
intersect the button kit, then walking back to the opening JSX element.

| | |
|---|---|
| call sites | **250** |
| files | **83** of 127 components (65%) |
| written as a plain string | **245** |
| assembled at runtime (template literal) | **5** |

**The element the kit is applied to — this is the finding that sizes option (b):**

| element | sites |
|---|---|
| `<button>` | **192** |
| `<GuardedButton>` (our own wrapper, `features/metering/meteringShared.tsx`) | **36** |
| `<Link>` (react-router) | **20** |
| `<a>` | **1** |
| `<summary>` | **1** |

A button component that renders `<button>` covers 192 of 250. The other 58 are a
router `<Link>`, an `<a href>` that opens a PDF in a new tab, a `<summary>` that is the
open-control of a `<details>` menu, and a wrapper component that already does shape (b)
badly (it takes the class string as a `className` prop).

**Non-kit classes carried alongside the kit ones at those sites** — 19 distinct, 43
occurrences: `settings-icon-btn` (17), `settings-danger` (5), `active` (3),
`rcw-exit` (2), `rd-chip-drill` (2), and 14 more at one site each.

---

## 2 · THE CSS BEING REPLACED

28 rules, **79 declarations**, ~164 lines, across **9 stylesheets**.

| stylesheet | rules | what |
|---|---|---|
| `components/StateFrame.css` | 17 | the kit: `.btn` (15 decls) + primary/secondary/ghost/danger/sm/link and their `:hover`/`:active`/`:disabled` |
| `components/DataTable.css` | 2 | `.table-page-btn` — a **second button implementation**, 8 decls, not composed with `.btn` |
| `components/FormModal.css` | 1 | `.btn-icon` 36×36 |
| `components/DownloadButton.css` | 1 | `.download-menu-list .btn` |
| `features/tenancy/SettingsPage.css` | 2 | `.settings-icon-btn` 32×32, `.settings-row-actions .btn` |
| `features/assets/assets.css` | 1 | `.ast-row-actions .btn` |
| `features/metering/metering.css` | 1 | `.met-row-actions .btn` |
| `features/customers/customers.css` | 1 | `.cus-note-meta .btn` |
| `features/payments/payments.css` | 1 | `.pay-result-head .btn` |
| `features/identity/SignInPage.css` | 1 | `.signin-actions .btn` |

### ⚠ THE SEVEN DESCENDANT RULES ARE THE HARD PART, AND THEY ARE NOT A DETAIL

Seven rules style a button **from its parent**, so the button's own markup does not say
what it renders as:

```
.signin-actions       .btn { width:100%; justify-content:center }
.settings-row-actions .btn { font-size:var(--text-btn-sm); padding:2px 6px }
.ast-row-actions      .btn { padding:0 var(--space-2); font-size:var(--text-btn-sm) }
.met-row-actions      .btn { padding:0 var(--space-2); font-size:var(--text-btn-sm) }
.cus-note-meta        .btn { margin-left:auto }
.pay-result-head      .btn { margin-left:auto }
.download-menu-list   .btn { justify-content:flex-start }
```

**Route B has no parent selector.** Utilities live on the element they style, so every
one of these must be pushed down onto each descendant button — and the parents were not
counted in the 250 sites, because the sites do not mention the class.

### ⚠ AND THEY PROVE B14 RULE 5 IS ALREADY BROKEN, INVISIBLY

B14 rule 5 is *"two button sizes only — default and small (12px)"*. The product renders
**four small-button paddings**, all at the same 12px font size:

| | padding |
|---|---|
| `.btn-sm` (the declared small tier) | `6px 8px` |
| `.settings-row-actions .btn` | `2px 6px` |
| `.ast-row-actions .btn` / `.met-row-actions .btn` | `0 8px` |
| `.settings-icon-btn` | `0`, forced to 32×32 |

`CR-016-ui-conformance.spec.ts` rule E measures **font size only** —
`distinctButtonFontSizes: ["12px","14px"]` — so all four pass. The rule says *sizes*;
the guard reads *type sizes*. That gap is not created by this migration; it is found by
it, and it is the reason a size answer has to be part of the recommendation rather than
a follow-up.

---

## 3 · THE BASELINE THAT EVERYTHING IS MEASURED AGAINST

* `CR-016-ui-conformance.spec.ts` — **2 passed**, 24 screens, every baseline number, at
  tip `5dbf2d7` before any edit.
* Stack: `boot_stack.sh` on ports 8010/8090, database `sbh_cr018p3`.

---

## 4 · WHAT WAS BUILT, AND WHAT IT MEASURED

Shape **(b)** — a component that owns the utility string once. Shipped in **v2.29.9**.

| | |
|---|---|
| `src/components/buttonKit.ts` | the strings, ONE copy, 263 lines |
| `src/components/Button.tsx` | `Button` · `ButtonLink` · `ButtonAnchor` · `ButtonSummary`, 190 lines |
| `src/components/buttonKit.test.ts` | the kit checks itself at the real Tailwind compiler, 139 lines |
| `e2e/CR-018-phase3-button-parity.spec.ts` | legacy vs component, every computed property, four states |
| `e2e/CR-018-phase3-screens.spec.ts` | four screens, every clickable, before/after |
| call sites migrated | **34 in 8 files**, plus **18 in 9 more** from the API change |
| unit assertions rewritten | **18** (32 exist across 19 files) |

### The proof

| measurement | result |
|---|---|
| kit vs legacy, 8 variants × 4 states, every computed property | **16,768 comparisons, 0 differing** |
| 4 screens, 475 clickables, 23 properties + geometry | **11,875 comparisons, 0 differing** |
| full-page PNGs | **53 pixels differ on each, all 53 inside one 7×8 box at the sidebar version label this release bumped** |
| `CR-016-ui-conformance.spec.ts` | **24 screens, every baseline number, PASS** |
| Phase 1 + Phase 2 specs re-run | PASS |
| `npm test` | 99 files, 1,516 tests, PASS |
| `g31` · `g34` | PASS, ratchets untouched |
| bundle | CSS 138.31 → **141.79 kB** raw (gzip 20.92 → 21.49); JS +1.8 kB raw. The 28 button rules are still in the sheet — 74 files still name them — so the shrink is at the END of the family, not here |

---

## 5 · THE FIVE THINGS THAT BROKE, AND THEY ARE THE DELIVERABLE

**1 · A repeated utility string cannot express the kit at all.** The first parity
run printed **540 differing properties**: the primary button was transparent with
body-coloured text and the small button had default padding. In CSS,
`.btn-primary{background:accent}` beats `.btn{background:transparent}` because it
is later IN THE FILE. Tailwind emits one rule per utility and sorts them itself,
so `bg-transparent` and `bg-accent` in one class attribute is a coin toss decided
at build time. **Shape (a) — repeating the utilities at 250 sites — is not merely
expensive, it does not work** unless every author resolves the three-class
cascade in their head at every site.

**2 · SEVEN parent rules re-style buttons, and Route B has no parent selector.**
The first screen census after migrating the call sites moved **1,416 properties
on 273 buttons**: every Assets row action grew from 12px/`0 8px` to 14px/`8px
14.4px`, because `.ast-row-actions .btn` no longer reached a button that had
stopped carrying `.btn`. Nothing else in the repo could have seen it — `tsc`,
eslint, 1,516 unit tests and both class-name gates were green throughout.

**3 · So the product renders FOUR small-button paddings under ONE font size, and
B14 rule 5 has never been able to see it.** `.btn-sm` 6px 8px ·
`.ast-row-actions .btn` and `.met-row-actions .btn` 0 8px ·
`.settings-row-actions .btn` 2px 6px. Rule 5 says *two button sizes*; CR-016's
rule E measures `distinctButtonFontSizes` and all four are 12px, so all four
pass. They are now four NAMED sizes in one file. **DEF-342.**

**4 · A typo'd utility inside a component constant is invisible to the entire
safety net.** With `components/buttonKit.ts` on `route-b-migrated.txt`,
`items-center` → `itmes-center` gave **`routeBUtilities.test.ts`: 5 passed** and
**`g31_declared_classes.py`: PASS, 0 undeclared**. Both readers read `className=`
ATTRIBUTES; a component API keeps its strings in constants. That is DEF-327's
failure mode walking in through the front door of the migration bought to remove
it. `buttonKit.test.ts` closes it for this family (proved RED first); the general
hole is **OQ-280**.

**5 · `disabled:opacity-45` in a class attribute broke assertions across the
suite.** `expect(html).not.toContain("disabled")` is true of every button in the
product now, and `/<button(?![^>]*disabled)/` matches none. Two tests silently
inverted. Route B writes state names into the markup, and any test that greps the
markup for a state word is now wrong.

---

## 6 · THE RECOMMENDATION

**Shape (b), the component API — and not because it is tidier. Shape (a) does not
work** (finding 1) and `@apply` is Route A, which the PO rejected.

**But the reasoning the PO chose Route B on does not cover shared classes, and
this is where that has to be said.** Route B was bought to make an undeclared
class impossible. For the 689 single-use classes it does exactly that. For a
shared class the same move puts the string in a constant, where **both** gates go
blind (finding 4) — so for shared classes Route B does not deliver the property
it was bought for unless every extracted kit carries its own compiler check. That
is a real, small, per-kit cost: 139 lines here. It is worth paying; it is not
free, and nothing in the CR anticipated it.

### Sizing the other 169 classes

The button family — 10 classes, 250 sites, 83 files — took **≈3 hours**, of which
the parity instrument, the census instrument, the slot-composition discovery and
the parent-selector discovery were roughly **2 hours and are one-time**. The
mechanical part was ~40 minutes.

At that rate the remaining 169 shared classes are **35–60 hours**, and the error
bars point the same way twice:

* **Buttons were EASIER than the median** in one way: one family, one file, one
  concept, and 245 of 250 sites were plain strings.
* **Buttons were HARDER in three ways that recur**: five host elements, seven
  parent rules, and a wrapper component whose prop was a class string.
* **`.met-panel` (41 components), `.met-table` (30) and `.kicker` (26) are
  layout containers, not leaf controls.** A container's utilities interact with
  its children's; nothing in this spike exercised that.
* **`.settings-refusal` (30) and `.fin-absent-reason` (16) are copy surfaces**
  that B14 rule 18's measure and the 80% descriptions land on.
* **Every family will need its own `*Kit.test.ts`**, per finding 4.

### What must be decided before the next family, and by whom

* **DEF-342 — how many button sizes?** Four exist. B14 says two. A migration
  cannot answer it; collapsing them moves pixels on every list screen.
* **OQ-280 — the safety net does not reach a component API.** Either the two
  readers learn to read string constants in a Route B file, or every kit carries
  its own compiler check. Recorded, not chosen.
* **DEF-343 — the template category chips carry a class that styles nothing.**
  Found by the migration; the selected chip has never looked selected.

### Did B14 rule 5 get easier or harder to enforce?

**Easier, and by more than it looks.** Before: rule 5 lived in four stylesheets
and was checked by counting rendered font sizes on 24 screens — which is why four
paddings passed as two sizes. After: every button writes `data-size`, generated by
the component and impossible to mistype, so *"how many sizes does this screen
render"* is one selector; and `buttonKit.test.ts` asserts on the SOURCE that the
kit writes exactly two font sizes. The rule went from RATIFIED-and-partly-measured
to countable — and the first thing counting it found was that it is broken.
