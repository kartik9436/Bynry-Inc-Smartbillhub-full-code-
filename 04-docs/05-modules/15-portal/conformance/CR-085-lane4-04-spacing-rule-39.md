# CR-085 step 1 · lane 4 — **B14 rule 39, measured**

<!-- ── Trace ──────────────────────────────────────────────
     Change:  CR-085 step 1 lane 4 — IDENTIFY ONLY.
     Rule:    04-docs/02-decisions/14-ui-conventions.md rule 39, RATIFIED
              2026-09-11, UNENFORCED. PO verbatim: "have a proper padding for
              each component on the screen. these padding should be universally
              fit for the product… the components are too much close as well as
              manage the margins also" and "in the forms for the fields. It
              starts with the field name. then the input field, and then it
              should show the helper text below that input field."
     Method:  getComputedStyle and getBoundingClientRect in a real browser,
              Chromium via playwright-core, against the shared stack at
              http://127.0.0.1:8401, tenant `brazosbend`, signed in as
              elena@example.test, at 1280 AND 390, on 2026-09-11.
              NOT read off class names — Tailwind emits only for files on
              route-b-migrated.txt and `portal/` is a directory entry there,
              so a class-name reading would have been a guess either way.
     ───────────────────────────────────────────────────── -->

## 0 · The scale does not exist, and rule 39 says so about itself

```
SPACING TOKENS on :root, measured at 1280 and at 390:
  --sp-1 (unset)   --sp-2 (unset)   --sp-3 (unset)   --sp-4 (unset)
  --sp-5 (unset)   --sp-6 (unset)   --sp-7 (unset)
```

This is not a surprise and it is not a defect against a lane. B14 rule 39's own
status column states it: *"No `--sp-N` token exists in `tokens.css` today (94
custom properties, not one of them a spacing scale), so this rule is entirely
unbuilt at ratification, which is stated here rather than discovered by the
first lane that looks."*

⚠ **The scale is nevertheless mostly present by accident**, because
`tailwind.css` records *"Our scale IS Tailwind's: `--space-N` is N × 4px"*. So
`gap-1` = 4, `gap-2` = 8, `gap-3` = 12, `gap-4` = 16, `gap-5` = 20, `gap-6` = 24,
`gap-8` = 32 — the same seven numbers rule 39 names. **What is missing is the
NAMING, and the naming is what would let a check read intent.** Every figure
below is on the scale; the failures are about **which step was chosen**, not
about ad-hoc values.

**One genuine ad-hoc pair was found, and it is in the frame rather than in this
lane's screens:** `PortalScreenIdTag.tsx` writes `px-[9px] py-[3px]` — **9 and
3**, two of the four numbers rule 39 bans by name (*"NO AD-HOC 3 / 7 / 9 / 14
ANYWHERE"*). It renders on every portal screen. Recorded here; it belongs to
whoever owns the tag.

---

## 1 · THE KPI ANCHOR — *"KPI 16/20 gap 6"*

**This lane's anchor, and the row IS built** (see the `DEF-CWP-3986`
re-verification). Measured on `/brazosbend/portal/home`:

| | Ratified anchor | Measured 1280 | Measured 390 | Verdict |
|---|---|---|---|---|
| KPI cell padding — vertical | **16** (`--sp-4`) | `padding-top 16px` · `padding-bottom 16px` | same | ✅ |
| KPI cell **side** padding | **20** (`--sp-5`, *"KPI cell side padding"*) | `padding-left 16px` · `padding-right 16px` | same | ❌ **16, should be 20** |
| gap between tiles | **`--sp-6` = 24** | `row-gap 16px` · `column-gap 16px` | `row-gap 16px` | ❌ **16, should be 24** |

Raw:

```
1280  [data-kpi-row]  display:grid  grid-template-columns: 253px 253px 253px 253px
                      row-gap:16px  column-gap:16px
      [data-kpi=balance]  16px / 16px / 16px / 16px   inner row-gap 4px
390   [data-kpi-row]  display:grid  grid-template-columns: 350px
                      row-gap:16px
      [data-kpi=balance]  16px / 16px / 16px / 16px   inner row-gap 4px
```

**The fix is two utilities in one shared component** — `KpiTile`'s `p-4` becomes
`py-4 px-5`, and `KpiRow`'s `gap-4` becomes `gap-6`. Both are on
`primitives.tsx`, which is on `route-b-migrated.txt`, so neither adds a
stylesheet class (B14 rule 21). **It reaches four screens at once** — `CWP-022`,
`CWP-033`, `CWP-065`, `CWP-066` — which is the point of the piece being in the
kit, and is also why this lane did not make the change: it is four screens'
worth of visual movement and this lane is identify-only.

### The other KPI finding, which the anchor does not cover

`KpiRow` is **`grid-cols-4` unconditionally** at ≥768px (`max-md:grid-cols-1` is
the only override). On this fixture Home renders **one** tile, so the measured
columns are `253px 253px 253px 253px` and the balance sits in **the left quarter
of a 1,060px row with three empty columns beside it**. The drawing's
`AmountDueCard` is a full-width accent-bordered card carrying *"the largest type
on the page"*. A one-account, one-service customer is the T7 majority. Delta
**H-15**.

---

## 2 · THE FIELD ANATOMY — *label → input 5 · input → helper 6 · field → field 20, ≈ 1 : 1 : 4*

`/my-details` is this lane's form. It composes the **shared** `FormField` from
`portal/components/primitives.tsx:577`, so every number below is every portal
form's number.

⚠ **No helper renders on `/my-details` on this fixture.** All three helper slots
there are conditional on `*_varies`, which is false for a one-account login. So
the **input → helper** figure was measured on **`/brazosbend/portal/enrol`**,
which composes the **same `FormField`** and carries an unconditional helper
(*"Just the postcode, not the whole address."*). Stated rather than inferred,
because a figure measured somewhere else is a figure the next reader must be
able to re-take.

### Measured

| | Ratified | Measured | Verdict |
|---|---|---|---|
| label → input | **5px** | **4.00px** (1280 **and** 390, every field on both screens) | ⚠ one step short, and it is the tightest gap of the three |
| input → helper | **6px** | **17.00px** | ❌ **2.8× the ratified figure** |
| field → field | **20px** (`--sp-5`) | **16.00px** on `/my-details`; **12px** declared on `/enrol`'s stack | ❌ one step short |
| ratio | **≈ 1 : 1 : 4** | **1 : 4.25 : 4** | ❌ |

Raw, from `/enrol` at 1280 — the one place all three can be taken at once:

```
[data-field=enrol-postcode]
  row-gap                       4px         ← the component's single `gap-1`
  input bottom → helper top    17.00px
  helper bottom → next label   25.00px
  helper margin-top            13px         ← THE MECHANISM
  helper margin-bottom         13px
  parent row-gap               12px
  label font-size              13px
  helper font-size             13px
  input padding                8px 12px
  input height                 41.3px
```

### Why input → helper is 17px when the component asks for 4

`FormField` is `<div class="flex flex-col gap-1">` — **one uniform 4px gap for
all three relationships**. The helper is a bare `<p>` with **no `m-0`**, and the
portal reset does not zero paragraph margins, so it carries the browser's
`1em` = **13px** top and bottom margin. `4 + 13 = 17`.

**Rule 39 names this exact failure and gives its reason:** *"⚠ **DOM ORDER
ALONE IS NOT ENOUGH — the helper must READ as attached to the input above it,
never to the label below it, and a 3/3/9 rhythm destroys that even with correct
markup.** That is why the three gaps are ratified as FIGURES and not as an
ordering."*

Here the helper sits **17px** below the input it belongs to and **25px** above
the next field's label. It is still nearer its own input — by 8px — but the
ratified margin is **14px** (6 vs 20). **The attachment survives on a third of
the intended margin, and it survives by accident**, because the un-reset
`margin-bottom: 13px` happens to push the next label away by as much as the
un-reset `margin-top: 13px` pulled the helper down.

⚠ **The kit already knows about this.** `KpiTile`'s sub-line, three hundred
lines away in the same file, is `<p className="m-0 …">`. `Home.tsx`'s instalments
paragraph is `m-0`. `FormField`'s helper and error paragraphs are the two that
are not — so a check written as *"does the component declare the right gap"*
would pass, and only a browser can see it. That is hard-won law 6 in one
component.

**The fix is small and it is not this lane's to make:** `m-0` on the helper and
the error `<p>`, `gap-1` → an explicit `gap-[…]`-free pair that expresses 5 and
6 on the scale, and the field stack's `gap-4` → `gap-5`. It moves **every form
in the customer portal**, which is exactly why it is a finding here rather than a
commit.

### The other two anchors that touch this lane

| Anchor | Ratified | Measured | Verdict |
|---|---|---|---|
| `.input` | **6 × 10, min-h 36** | padding `8px 12px`, height **41.3px** | ❌ padding one step over on both axes; height 5px over |
| page | **24 / 16 / 32** | `main` padding **24px / 20px / 24px / 20px**, identical at 1280 and 390 | ❌ sides **20** should be 16; bottom **24** should be 32 (`--sp-7`) |
| `th`/`td` (`CWP-023`'s table) | **8 × 12** | `td` **`8px / 12px / 8px / 0px`**; `th` **`0px / 12px / 8px / 0px`** | ⚠ the vertical 8 is right and the horizontal is **12 on one side and 0 on the other**, so the first column has no left padding and `th` has no top padding. Whether the anchor means 12 per side or 12 between is what the rule does not say. |

`Card` padding was measured at **16 / 16 / 16 / 16** with a **16px** row gap
(`[data-testid="my-details"]`), which is on the scale and which rule 39's anchor
list does not name — recorded so the next reader does not have to re-take it.
`/my-details`' rail panels are not `<aside>` elements, so the *rail
margin-bottom 24* anchor could not be taken on this lane's screens; `YourAccount.tsx`
does use `Panel as="aside"` and is where that one should be measured.

---

## 3 · A tension inside rule 39 itself, for whoever owns B14

Not a defect and not a lane's call — recorded because the next reader will hit
it in the first minute.

**Rule 39 gives two different figures for the gap between two fields.**

* the scale: *"`--sp-4` **16px** between fields, between blocks"*
* the field anatomy: *"field → field **20px**, a ratio of ≈ 1 : 1 : 4"*

The built product uses **16**, which satisfies the first half and fails the
second. Whichever is meant, one of the two sentences needs amending, and until
it is a lane fixing `/my-details` to 20px is putting the form out of step with
every other block on the page.

**And the field-anatomy figures are off the scale the same rule ratifies.** `5`
and `6` are not `--sp-1` (4) and not `--sp-2` (8). Rule 39 also says *"NO AD-HOC
3 / 7 / 9 / 14 ANYWHERE"* — it does not name 5 or 6, and they are the two
numbers its own field anatomy requires. The anchors were taken with
`getComputedStyle` on a running app, so they are measurements of something that
was on screen; what they are not is expressible in the seven-step scale beside
them.

---

## 4 · What a check would have to read

Rule 39's status column says **UNENFORCED — no gate reads computed spacing**,
and this lane's experience says why that matters more here than usual.

**Seven anchors touch these six screens. All seven diverge.**

| Anchor | Ratified | Measured | Off by |
|---|---|---|---|
| page | 24 / 16 / 32 | 24 / 20 / 24 / 20 | sides +4, bottom −8 |
| KPI cell padding | 16 / 20 | 16 / 16 | sides −4 |
| KPI row gap | 24 | 16 | −8 |
| label → input | 5 | 4 | −1 |
| input → helper | 6 | 17 | **+11** |
| field → field | 20 | 16 | −4 |
| `th` / `td` | 8 × 12 | 8 × (12 / 0) | one side |

**Six of the seven are a legal utility class from the ratified scale — just the
wrong step — so every one of them passes `tsc`, eslint, `G34`, `G31`, all 58
portal test files and every gate.** The seventh, the 17px helper gap, is **not
in a class at all**: it is a browser default margin the shared component never
zeroed, so no source reading of any kind can see it.

**So a source-reading gate cannot find four of these five and cannot find the
fifth at all.** The instrument that found every one of them is
`getComputedStyle` in a browser against a booted stack, which is the shape
`10-scripts/*_walkthrough.mjs` already has 34 worked examples of. If rule 39 is
to be enforced rather than ratified, that is where it goes.
