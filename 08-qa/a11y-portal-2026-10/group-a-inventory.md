# Portal accessibility, Group A — the colour inventory (F-01, F-09)

**Lane A11Y-A-INVENTORY · 2026-10-23 · read-only.** Nothing in the product was changed to produce this file.

**What this is.** The tester's working rule for Group A is *"list every similar place before changing anything"*. This is that list, measured in a real browser and in the code, with every number re-run from a script anyone can run again:

    node 10-scripts/a11y/portal_contrast_scan.mjs --code                 # the code inventory
    node 10-scripts/a11y/portal_contrast_scan.mjs --states               # every page, with hover/focus/selected/errors
    node 10-scripts/a11y/portal_contrast_scan.mjs --simulate             # the approved colours, injected in the browser
    node 10-scripts/a11y/portal_contrast_scan.mjs --brand=#F5C518        # any brand colour, swapped in the browser

The set-up (private database, fake data, the build mode, the pinned axe) is in the script's header.

> ⚠ **The colours changed while this was being measured.** The baseline below is commit `05763ea16` — the decision-log entry that confirmed the colours, before any of them was built. By the time the scans finished, the colour lane had built them (`dd246e1a4`, `075f26b87`, `9dcce4538`, `4d2605488`, `94d74bc6d`, released as 2.598.0 at `758daa0ec`). So this file gives **three** measurements of the same 53 pages: **before**, **the approved colours simulated** on the old build, and **as built**. The third one is the check on the colour lane's work, and it is where the open items at the end come from.

## How it was measured

| | |
|---|---|
| Browser | Chromium 141.0.7390.37 (Playwright), 1280 × 900 |
| Rule | axe-core **4.10.3** (pinned), rule `color-contrast` only; `incomplete` ("needs review") nodes are counted, never dropped |
| Data | a private PostgreSQL copy, `seed_portal_demo` — Pine Hill Water & Power (fake), sample brand `#EC3013`, login `alvarez0@example.invalid` (fake). Dropped afterwards |
| Passes | every page signed **out** and signed **in**, in **English** and **Spanish** (language set through the app's own i18n and read back on every page — no page reported the wrong language) |
| Also measured by the script, because axe does not | placeholder text; field and select borders against the colour on both sides of the edge (3:1); text inside SVG; icon-only controls (3:1); the keyboard focus ring at every Tab stop (3:1); text on brand-coloured fills |
| States (English) | hover over up to 25 controls a page (425 probes); Tab through up to 40 stops a page (1,014 focus stops); open every expander, tab, toggle, radio and checkbox (38 on 10 pages); press the form's send button with nothing filled in |
| Brand colours | the sample `#EC3013`, a dark test colour `#1D3557` and a light one `#F5C518`, swapped into the API answer in the test browser only |

**What would make this pass wrongly, and what the script does about it.** A signed-in pass that is really signed out (the script refuses to report if `/home` says signed out). A Spanish pass that is still English (read back per page). A bundle that cannot reach the API — a bare `vite build` bakes in the production API address and every page draws *"We couldn't reach …"* and scans almost clean; the first run here did exactly that, so the script now refuses when more than half the pages show it, and the header says to build with `--mode walk`. A colour the parser cannot read — Chrome reports `color-mix()` as `color(srgb …)`, which the first version could not parse.

## 1 · The pages

**The router mounts 55 routes** (`07-frontend/src/portal/routing/portalRoutes.tsx`), and the screen register (`screenIds.ts`) has a row for each. **53 were scanned.** Two could not be:

- `/start-service/:draft` — the address is minted by the application form, it cannot be typed.
- `/requests/:reference` — the fake login has no request to open.

Of the 53, **17 are open to anyone** and **36 need a sign-in**; signed out, those 36 all draw the same sign-in wall, which was scanned too (it has its own failures — see 3.6).

**The tester counted 23 pages. We count 53, and we cannot name the difference page by page**, because the tester's page list is not in the repository. The likeliest reading is that the tester walked the pages a customer reaches by clicking, while this scan opens every route the router mounts, including deep ones (a bill's comparison, its printed copy, the dispute form, level-pay standing, the four arrears screens). **To reconcile exactly we need the tester's 23 addresses.**

The full table, with the failing-element count for every page in every pass, is in the appendix (A1).

## 2 · Baseline counts against the tester's

| | Tester | This scan (before, `05763ea16`) |
|---|---|---|
| Pages | 23, 22 failing | 53, **52–53 failing** in every pass |
| Failing elements | **204** | signed out: **168** EN · **175** ES · signed in: **570** EN · **569** ES |
| One render per page (public pages signed out, account pages signed in), EN | — | **562** on 52 of 53 pages |
| Of which `#7d7979` (grey-600) | **161** | **389** of the 562 (69%) — the tester's share is 79% |
| Distinct failing texts across the site, EN | — | **250**, of which **142** are `#7d7979` |
| Worst pair | `#9b9797` on `#f3f2f2` at **2.58:1** | **the same**: `#9b9797` on `#f3f2f2` at **2.58:1** (the footer's office hours, on every page) |
| Field borders | `#d7d3d3` at **1.48:1** | **the same**: `#d7d3d3` on white at **1.48:1**, **99 fields on 29 pages** |

**Why our totals are higher.** Two reasons, and neither is a disagreement about a colour:
1. **More pages.** 53 against 23, and the signed-in pages carry most of the grey (372 of the 413 grey-600 failures are signed in).
2. **We count the brand colour.** 157 of the 738 English failures are the utility's own colour `#EC3013` used as text or as a button fill. The tester raised that separately as question (3); axe counts it as a contrast failure, so it is in our totals and in its own root cause below.

**Spanish matches English** to within a handful of elements on every page (longer words wrap differently); no failure is Spanish-only. Repeated runs of the same pass differ by up to 7 elements (168 and 175 for one pass), because a few guest pages are throttled or render a count that moves; every figure here is from one named run.

## 3 · Every failing element, by root cause (before)

English, both sign-in states. Spanish is the same list.

| # | Root cause | Colours | Ratio | Elements (out + in) | Pages | What it is | Fixed by the approved colours? |
|---|---|---|---|---|---|---|---|
| 3.1 | grey-600 secondary text on white | `#7d7979` on `#ffffff` | 4.30 | 41 + 372 = **413** | 53 | descriptions, hints, account bar, table notes, chart values, nav labels | **yes** → 5.58 |
| 3.2 | grey-500 used as text, on the page background | `#9b9797` on `#f3f2f2` | **2.58** | 32 + 33 = **65** | 19 | the footer (office hours, emergency line), notes under lists | **yes** → 5.00 |
| 3.3 | grey-600 on the page background | `#7d7979` on `#f3f2f2` | 3.84 | 15 + 27 = **42** | 14 | stepper step labels, notes outside a card | **yes** → 5.00 |
| 3.4 | grey-500 used as text, on white | `#9b9797` on `#ffffff` | 2.88 | 7 + 34 = **41** | 16 | *"Opens with the next release"*, hints in cards | **yes** → 5.58 |
| 3.5 | page-header subtitle, a 55% mix of the text colour | `#7f7d7d` on `#f3f2f2` · `#848383` on white | 3.66 · 3.78 | 18 + 2 = **20** | 12 | `PageHeader.css:64` `color-mix(in srgb, var(--color-text) 55%, transparent)` | **no — not in the approved table.** The colour lane moved it to grey-600 anyway (`94d74bc6d`) |
| 3.6 | light ink on a brand-coloured button | `#f3f2f2` on `#ec3013` | 3.76 | 39 + 17 = **56** | 52 | every primary button (`buttonKit.ts:191`, `bg-accent text-bg`); the sign-in wall's *Retry* / *Sign in* | no — ruling 3(a), built separately |
| 3.7 | brand-coloured small kicker on the page background | `#ec3013` on `#f3f2f2` | 3.75 | 9 + 42 = **51** | 43 | the 11px bold section kicker (`TRACK`, `BILLS`) | **no** |
| 3.8 | brand-coloured text and links on white | `#ec3013` on `#ffffff` | 4.20 | 14 + 19 = **33** | 13 | text links, *"Set up your login →"*, the required-field `*` | **no** |
| 3.9 | brand-coloured back link on the page background | `#ec3013` on `#f3f2f2` | 3.75 | 1 + 16 = **17** | 16 | `PageHeader.css:24` `.page-header-back` | **no** |
| | **total** | | | **168 + 570 = 738** | | | |

**Field borders (WCAG 1.4.11, 3:1).** Every text input and select drew `#d7d3d3` — 1.48 on white — **99 fields on 29 pages** (English). One select (the CWP-041 list filter, shared `DataTable` kit) already draws `#201e1d` and passes at 16.6. Radios and checkboxes are browser-drawn (18 on 3 pages, Chrome's own colours, not measured by this scan); none uses a grey token.

**Needs review (axe could not decide).** 34 signed out and 86 signed in, English. Most are step numbers (`2`, `3`) in grey-600 on `#f3f2f2` — 3.84, a real failure axe will not confirm because the text is one character — and check marks `✓` / arrows `→` (`primitives.tsx:580`, `:1220`, `CentresPage.tsx:380`, `HelpPage`) whose colour follows the text around them. 6 are a chart axis on `/payments` whose background axe cannot see.

## 4 · The code inventory

**What was searched.** Every file the portal **renders**, starting from `src/portal` and following an import out of it only when the imported component is drawn as JSX (`<Name`) or is a stylesheet. A plain import closure is wrong here: `portal/components/regional.tsx` imports one helper from `ShellWithSession`, which imports the staff `AppShell`, and a naive walk "finds" staff greys that never render in the portal. **157 files** at `05763ea16` (23 shared: the button, panel, page header, state frame, status pill, segmented control, form-modal pieces and the brand mark; and the three app stylesheets).

Patterns: `text-`, `border-` (and `border-t/b/l/r/x/y-`), `placeholder-`, `fill-`, `stroke-`, `ring-`, `outline-`, `divide-`, `bg-` with `neutral-300/400/500/600` and any variant prefix (`hover:`, `focus:`, `disabled:` …); `var(--color-neutral-*)` in CSS; and the hard-coded `#7d7979`, `#7f7d7d`, `#9b9797`, `#d7d3d3`.

**Found.**
- **276 uses** in the rendered portal: grey-600 text **204** (202 of them under `src/portal`, which matches the decision log's 202), grey-500 **50**, grey-300 borders **19**, and one each of `bg-neutral-300`, `bg-neutral-400`, `text-neutral-300`.
- **No `var(--color-neutral-*)`** in any stylesheet the portal mounts, **no `placeholder-`, `fill-`, `stroke-`, `ring-`, `outline-` or `divide-` grey**, and **no hard-coded copy** of any of the four hexes. The tester's `#7f7d7d` is not hard-coded anywhere: it is what `PageHeader.css:64`'s 55% `color-mix` computes to on `#f3f2f2` (3.5 above).
- **No focus ring is grey.** The ring is `outline: 2px solid var(--color-accent)` with a 2px offset (`global.css:152`), i.e. the utility's brand colour (section 5).

**Classified** (each border, chart and disabled use was read in the source; the script carries those rulings as snippet-keyed overrides so a line moving does not move the ruling):

| Use | Count | Rule | After the approved colours |
|---|---|---|---|
| text | 246 | 4.5:1 | all pass (5.58 on white, 5.00 on `#f3f2f2`) |
| chart label or legend | 6 | 4.5:1 | all pass |
| input or select border | 6 | 3:1 | all pass (3.50 on white) |
| control border (the button joined to a field, `primitives.tsx:754`) | 1 | 3:1 | **not moved by the table** — the colour lane moved it with the field |
| switched-off errand card (`primitives.tsx:122,125`, `aria-disabled`) | 2 | exempt (inactive) | kept grey-500 by the colour lane — **2.59 on `#f3f2f2`**; the tester should confirm a whole switched-off card counts as inactive |
| disabled control (`primitives.tsx:1252`) | 2 | exempt | — |
| chart mark: last year's comparison bar (`primitives.tsx:888`, `bg-neutral-300`) | 1 | 3:1 if the bar is needed to read the chart | **1.48 — still fails.** The figure is printed beside it as text, so 1.4.11 may not apply; tester's call |
| chart baseline (`primitives.tsx:1699`) | 1 | none / 3:1 | 1.48, unchanged |
| step marker: a future step's circle (`primitives.tsx:1210`, `border-neutral-300 text-neutral-300`) | 1 + 1 | 3:1 if it carries state | **1.48 — still fails.** The circle is empty (no text) on the future step, so the text half has nothing to fail; the border is what says *not yet* |
| step marker: the stepper's number box (`primitives.tsx:576`) | 1 | none (the number inside is the information) | unchanged |
| divider or card line | 8 | none | unchanged, as ruled |
| fill (`StatusPill` muted, `bg-neutral-400` under `text-neutral-900`) | 1 | the text on it, 4.5:1 | the text reads 7.01:1 on it; the fill itself carries no rule |

The full table — **every use, file:line, class, use, ratio today, ratio after** — is appendix A2.

**At the tip (`758daa0ec`), the same search finds 271 uses**: grey-500 is down from 50 to **3** (the switched-off card's two lines and the disabled box), every field and the joined button use the new `border-field-border`, and grey-600 is up from 204 to 252 because the 48 grey-500 text uses moved onto it.

## 5 · States, focus ring, charts, icons and the brand colour

**Hover** (425 probes, English, both sign-in states). Nothing new fails on hover except brand-coloured links, which stay `#ec3013` (4.20 on white). Grey text does not change on hover.

**Focus ring** (1,014 Tab stops on 106 page scans). Every stop but one draws the 2px brand-colour outline with a 2px gap, so it is measured against what is **behind** the control:

| Behind the control | Stops | Ring `#EC3013` | Dark `#1D3557` | Light `#F5C518` |
|---|---|---|---|---|
| white card | 915 | **4.20** | 12.36 | **1.63 — fails** |
| page background `#f3f2f2` | 30 | **3.76** | 11.06 | **1.46 — fails** |
| the error panel `#eae9e9` (*"We couldn't open this page"*) | 68 | **3.47** | 10.20 | **1.35 — fails** |

**All pass 3:1 with the sample colour.** **One focusable element shows no focus indicator at all:** the embedded bill (`<object>`) on `/bills/:number/document` (CWP-029). That is WCAG 2.4.7 rather than contrast, so it belongs to the focus group, not Group A — **reported here, not filed** (this lane commits only its two files).

**Selected and expanded** (38 toggles on 10 pages). Nothing new beyond the selected segment of a segmented control, which is light ink on the brand fill (3.6).

**Errors (a form sent empty).** This probe is the weakest part of the scan, and it is said plainly: across 20 form pages it found a send button to press on only 5 page scans, and only `/forgot-password` drew an error message. So error colours were checked in the code instead. **Statically, every error message in the portal is `text-danger-700`** (31 uses): **7.55** on white and **6.76** on `#f3f2f2`, a pass. The one error-coloured field border, `border-danger-500`, reads 4.49 on white, a pass at 3:1.

**Placeholder text.** **No input on any of the 53 pages has a placeholder**, so there is nothing to measure.

**Disabled controls.** 57 disabled controls on 28 pages (English). axe skips them and so does this inventory: **exempt** under WCAG 1.4.3.

**Charts.** No portal chart is drawn in SVG, so there are no SVG axis labels. The charts are HTML: the money chart (level pay, the bill comparison) and the usage chart (`primitives.tsx` around 1680–1780). Their month labels, values and legends are grey-600 text — in the 413 of 3.1, and all pass at 5.58 after. The bars are the brand colour (`bg-accent` 4.20 on white, the peak `bg-accent-700` 7.10). **The usage chart did not render in this fixture**: `seed_portal_demo` stopped part-way (below), before the usage readings were planted, so its bars were checked from the code only.

**Icons.** The icons that carry meaning are the icon-only row actions (view, download), with the SVG hidden from screen readers and the control named instead. The first version of the script skipped every hidden SVG and so found none; it now measures them. As built they draw black (21:1). No icon uses a grey token.

**The brand colour** (`brand_primary_hex`, sample `#EC3013`). It is applied as `--color-accent` by `GuestFrame.tsx` `brandStyle()` on both portal frames, and used for: primary button fills, the hover (88% brand) and pressed (72%) fills, text links, section kickers, the back link, the active nav tab's underline, the focus ring, and the chart bars.

| Where | `#EC3013` (sample) | `#1D3557` (dark test) | `#F5C518` (light test) |
|---|---|---|---|
| Light ink `#f3f2f2` on the brand fill (before) | **3.76 fails** | 11.06 | **1.46 fails** |
| The ink the build now picks on the fill (ruling 3(a)) | black **5.00** | white **12.36** | black **12.88** |
| Brand text and links on white | **4.20 fails** | 12.36 | **1.63 fails** |
| Brand kicker / back link on `#f3f2f2` | **3.76 fails** | 11.06 | **1.46 fails** |
| Focus ring on white / `#f3f2f2` / `#eae9e9` | 4.20 / 3.76 / 3.47 | 12.36 / 11.06 / 10.20 | **1.63 / 1.46 / 1.35 fail** |
| Chart bar on white (rest / peak) | 4.20 / 7.10 | 12.36 / 15.21 | **1.63 / 3.12** |

## 6 · Still failing after the approved colours

**6.1 · Simulated on the old build.** With grey-600 at `#6b6767`, grey-500 text at `#6b6767` and field borders at `#8c8888` injected into the browser, the 738 English failures fall to **178** (74 signed out, 104 signed in), and **no grey text fails except the page-header subtitle** (3.5; 10 elements a pass), which the approved table did not name. Every field border measured passes: 100 at **3.50**, and 6 that were already dark. Everything else left is the brand colour: 3.6, 3.7, 3.8 and 3.9.

**6.2 · As built (`758daa0ec`, measured).** **144 English failures (63 signed out, 81 signed in), 0 of them grey** — the build matches the simulation and also fixed the subtitle. Field borders: 106 measured, all 3.50. **Every remaining failure is the brand colour**, and with the dark test colour the signed-in pages have **zero**. What is left, in plain words:

1. **The sign-in wall's buttons are not corrected.** When a signed-out visitor opens any of the 36 account pages, the *Retry* and *Sign in* buttons still draw light ink on the stock accent — `#f3f2f2` on `#ec3013`, **3.76** — **on 36 pages**, and they do not take the tenant's colour either (with `#1D3557` they are still `#ec3013`). The wall is drawn inside `[data-portal]` (`PortalApp.tsx:101`) but outside both portal frames, and the corrected inks are set only on the frames (`GuestFrame.tsx:113–115`), so the wall falls back to the staff ink. **This is the colour lane's ruling 3(a) not reaching one screen state**, and it is the only non-text-colour item left.
2. **Brand-coloured text is not covered by any ruling.** Small kickers and back links on `#f3f2f2` read **3.75**; links and the required `*` on white read **4.20**. 81 elements signed in, 27 signed out. The colour lane recorded this as found-and-not-changed (decision log, *"four judgments"*), and it needs a colour or a rule from the PO/QA.
3. **A light brand colour fails everywhere text or the ring uses it.** With `#F5C518`: links **1.63**, kickers **1.46**, focus ring **1.63 / 1.46 / 1.35** — below 3:1, so a keyboard user cannot see where they are. Ruling 3(b) (Company → Profile refuses a failing colour) **can never fire**, because with black as the dark ink every colour passes on its FILL (the decision log says so); it says nothing about the same colour used as TEXT or as the RING. **A utility could save `#F5C518` today and the portal would fail on every page.**
4. **Non-text greys the table did not name**: the future-step circle (`primitives.tsx:1210`, 1.48) and last year's comparison bar (`primitives.tsx:888`, 1.48). Each may be exempt because the same fact is in text beside it; the tester should rule.
5. **The switched-off errand card** keeps grey-500 text (2.59 on `#f3f2f2`) as an inactive component. Exempt only if the tester agrees a whole card is an inactive control.
6. **Staff screens**, not the portal: staff fields are filled `#eae9e9`, where the new field border reads **2.89**, and staff primary buttons keep `#f3f2f2` on `#ec3013` (3.76). Both are recorded by the colour lane as open.
7. **Not measured, and why:** `/start-service/:draft` and `/requests/:reference` (no address to type); the usage chart's bars (the fixture did not plant usage); most empty-form error states in the browser (the probe could not find the send button; the colours were checked in the code). `text-warning-700` on `bg-warning-100` would read **4.45** — just under — wherever both meet; no page in this fixture drew that pair.

## 7 · Things found on the way

- **`seed_portal_demo` stops part-way on a fresh database.** It fails in `seed_priced_addresses` → `_schedule_for` with `VAL-001 (rating.schedules.base_charge_code_required)`, after both utilities' sample data are planted and **before** the priced addresses and the usage readings. The portal still opens and has 200 bills, which is why every screen here could be scanned, but the usage chart has nothing to draw. **Not filed** by this lane (it commits only its two files); the coordinator should file it.
- **There are now two Group A scan scripts.** The colour lane added `10-scripts/a11y/portal_a_contrast_scan.mjs` while this one was being written. That one checks the paramless pages plus the first bill, field borders and the ring; this one covers every routed page, the hover/focus/selected/error states, icons, the simulation and any brand colour, and produces the code inventory. They agree where they overlap: the colour lane's *after* figure is 152 failures, all brand-coloured text, and 0 field borders under 3:1; this scan's is 144 in English, 0 grey, 0 field borders under 3:1.

## Appendix A1 · Every page, failing elements per pass

Counts are axe `color-contrast` failures in the default state. *Before* is `05763ea16`; *simulated* is the approved colours injected into that build; *as built* is `758daa0ec`. A signed-out count on an account page is the sign-in wall.

| # | Route | Screen | Who sees it | Signed out EN · ES | Signed in EN · ES | Approved colours, simulated (in EN) | As built (in EN) |
|---|---|---|---|---|---|---|---|
| 1 | `/` | CWP-001 | anyone | 13 · 13 | 11 · 11 | 1 | 1 |
| 2 | `/start-service` | CWP-008 | anyone | 8 · 8 | 8 · 8 | 2 | 1 |
| 3 | `/ask` | CWP-010 | anyone | 8 · 8 | 8 · 8 | 2 | 1 |
| 4 | `/pay` | CWP-002 | anyone | 10 · 10 | 10 · 10 | 2 | 1 |
| 5 | `/pay/check` | CWP-003 | anyone | 6 · 6 | 6 · 6 | 1 | 1 |
| 6 | `/pay/done` | CWP-004 | anyone | 6 · 6 | 6 · 6 | 1 | 1 |
| 7 | `/pay-now` | CWP-038 | signed in | 1 · 1 (sign-in wall) | 14 · 14 | 2 | 2 |
| 8 | `/pay-now/check` | CWP-076 | signed in | 1 · 1 (sign-in wall) | 13 · 13 | 3 | 2 |
| 9 | `/pay-now/done` | CWP-077 | signed in | 1 · 1 (sign-in wall) | 12 · 12 | 2 | 1 |
| 10 | `/payment-methods` | CWP-039 | signed in | 1 · 1 (sign-in wall) | 12 · 12 | 2 | 1 |
| 11 | `/autopay` | CWP-040 | signed in | 1 · 1 (sign-in wall) | 15 · 15 | 1 | 1 |
| 12 | `/fees` | CWP-050 | anyone | 4 · 4 | 9 · 9 | 1 | 1 |
| 13 | `/help` | CWP-011 | anyone | 6 · 6 | 6 · 6 | 3 | 2 |
| 14 | `/help/:slug` | CWP-060 | anyone | 0 · 7 | 5 · 5 | 2 | 3 |
| 15 | `/visit` | CWP-013 | anyone | 15 · 15 | 15 · 15 | 4 | 3 |
| 16 | `/visit/:slug` | CWP-014 | anyone | 9 · 9 | 9 · 5 | 3 | 2 |
| 17 | `/sign-in` | CWP-015 | anyone | 12 · 12 | 12 · 12 | 6 | 5 |
| 18 | `/enrol` | CWP-016 | anyone | 7 · 7 | 7 · 7 | 0 | 0 |
| 19 | `/forgot-password` | CWP-019 | anyone | 6 · 6 | 6 · 6 | 2 | 1 |
| 20 | `/update-email` | CWP-079 | anyone | 7 · 7 | 7 · 7 | 0 | 0 |
| 21 | `/home` | CWP-022 | signed in | 1 · 1 (sign-in wall) | 11 · 11 | 1 | 1 |
| 22 | `/accounts` | CWP-023 | signed in | 1 · 1 (sign-in wall) | 12 · 12 | 1 | 1 |
| 23 | `/account` | CWP-065 | signed in | 1 · 1 (sign-in wall) | 10 · 10 | 2 | 2 |
| 24 | `/property` | CWP-078 | signed in | 1 · 1 (sign-in wall) | 13 · 13 | 2 | 2 |
| 25 | `/bills` | CWP-027 | signed in | 1 · 1 (sign-in wall) | 12 · 12 | 3 | 1 |
| 26 | `/bills/:number/document` | CWP-029 | signed in | 1 · 1 (sign-in wall) | 8 · 8 | 2 | 2 |
| 27 | `/bills/:number/comparison` | CWP-030 | signed in | 1 · 1 (sign-in wall) | 10 · 10 | 4 | 4 |
| 28 | `/bills/:number` | CWP-028 | signed in | 1 · 1 (sign-in wall) | 17 · 17 | 5 | 5 |
| 29 | `/my-details` | CWP-024 | signed in | 1 · 1 (sign-in wall) | 11 · 11 | 1 | 1 |
| 30 | `/my-details/preferences` | CWP-025 | signed in | 1 · 1 (sign-in wall) | 16 · 16 | 4 | 2 |
| 31 | `/accounts/add` | CWP-020 | signed in | 1 · 1 (sign-in wall) | 10 · 10 | 2 | 2 |
| 32 | `/documents` | CWP-031 | signed in | 1 · 1 (sign-in wall) | 17 · 17 | 3 | 1 |
| 33 | `/plan-offer` | CWP-063 | signed in | 1 · 1 (sign-in wall) | 9 · 9 | 1 | 1 |
| 34 | `/level-pay/standing` | CWP-066 | signed in | 1 · 1 (sign-in wall) | 9 · 9 | 1 | 1 |
| 35 | `/level-pay` | CWP-044 | signed in | 1 · 1 (sign-in wall) | 12 · 12 | 1 | 1 |
| 36 | `/final-bill` | CWP-032 | signed in | 2 · 2 (sign-in wall) | 9 · 9 | 1 | 1 |
| 37 | `/usage` | CWP-033 | signed in | 1 · 1 (sign-in wall) | 13 · 13 | 3 | 1 |
| 38 | `/readings` | CWP-034 | signed in | 1 · 1 (sign-in wall) | 10 · 10 | 2 | 1 |
| 39 | `/usage/submit` | CWP-035 | signed in | 1 · 1 (sign-in wall) | 10 · 10 | 3 | 2 |
| 40 | `/equipment` | CWP-037 | signed in | 1 · 1 (sign-in wall) | 9 · 9 | 1 | 1 |
| 41 | `/payments` | CWP-041 | signed in | 1 · 1 (sign-in wall) | 18 · 18 | 2 | 1 |
| 42 | `/ask-for-a-plan` | CWP-042 | signed in | 1 · 1 (sign-in wall) | 14 · 14 | 2 | 2 |
| 43 | `/plan` | CWP-043 | signed in | 1 · 1 (sign-in wall) | 9 · 9 | 1 | 1 |
| 44 | `/requests` | CWP-046 | signed in | 1 · 1 (sign-in wall) | 18 · 18 | 1 | 1 |
| 45 | `/stop-or-restart` | CWP-052 | signed in | 2 · 2 (sign-in wall) | 13 · 13 | 2 | 1 |
| 46 | `/overdue` | CWP-057 | signed in | 1 · 1 (sign-in wall) | 13 · 13 | 2 | 1 |
| 47 | `/help-paying` | CWP-056 | signed in | 1 · 1 (sign-in wall) | 12 · 12 | 2 | 1 |
| 48 | `/protections` | CWP-064 | signed in | 1 · 1 (sign-in wall) | 9 · 9 | 1 | 1 |
| 49 | `/money-back` | CWP-045 | signed in | 1 · 1 (sign-in wall) | 9 · 9 | 1 | 1 |
| 50 | `/bills/:number/dispute` | CWP-055 | signed in | 1 · 1 (sign-in wall) | 13 · 13 | 2 | 2 |
| 51 | `/ask-a-question` | CWP-054 | signed in | 1 · 1 (sign-in wall) | 10 · 13 | 1 | 4 |
| 52 | `/report` | CWP-006 | anyone | 8 · 8 | 8 · 8 | 2 | 1 |
| 53 | `/track` | CWP-012 | anyone | 5 · 5 | 5 · 5 | 2 | 1 |

## Appendix A2 · Every grey in the code the portal renders (`05763ea16`)

Ratios are against white and against the page background `#f3f2f2`. *After* applies the approved colours: grey-600 → `#6b6767`; grey-500 used as text → `#6b6767`; input and select borders → `#8c8888`; everything else unchanged. The 4.5:1 text rule is applied to the worse of the two backgrounds. Re-run at any commit with `node 10-scripts/a11y/portal_contrast_scan.mjs --code` (it reads the greys from `tokens.css`, so at the tip *today* is the new colours).

| Use | Count |
|---|---|
| input or select border | 6 |
| disabled (switched-off card) | 2 |
| control border (button joined to a field) | 1 |
| text | 246 |
| chart label or legend | 6 |
| chart mark (non-text) | 1 |
| chart baseline | 1 |
| step marker (future step) | 1 |
| step marker | 1 |
| divider | 8 |
| fill (non-text) | 1 |
| disabled | 2 |
| **total** | **276** |

| # | file:line | class | use | today on white · on #f3f2f2 | after on white · on #f3f2f2 | needs | after the approved colours |
|---|---|---|---|---|---|---|---|
| 1 | `portal/components/primitives.tsx:729` | `border-neutral-300` | input or select border | 1.48 · 1.33 | 3.5 · 3.14 | 3 | passes |
| 2 | `portal/components/primitives.tsx:1060` | `border-neutral-300` | input or select border | 1.48 · 1.33 | 3.5 · 3.14 | 3 | passes |
| 3 | `portal/components/primitives.tsx:2016` | `border-neutral-300` | input or select border | 1.48 · 1.33 | 3.5 · 3.14 | 3 | passes |
| 4 | `portal/components/primitives.tsx:2352` | `border-neutral-300` | input or select border | 1.48 · 1.33 | 3.5 · 3.14 | 3 | passes |
| 5 | `portal/shell/GuestLanguage.tsx:93` | `border-neutral-300` | input or select border | 1.48 · 1.33 | 3.5 · 3.14 | 3 | passes |
| 6 | `portal/shell/PortalShell.tsx:249` | `border-neutral-300` | input or select border | 1.48 · 1.33 | 3.5 · 3.14 | 3 | passes |
| 7 | `portal/components/primitives.tsx:122` | `text-neutral-500` | disabled (switched-off card) | 2.89 · 2.59 | 2.89 · 2.59 | exempt | exempt (disabled) |
| 8 | `portal/components/primitives.tsx:125` | `text-neutral-500` | disabled (switched-off card) | 2.89 · 2.59 | 2.89 · 2.59 | exempt | exempt (disabled) |
| 9 | `portal/components/primitives.tsx:754` | `border-neutral-300` | control border (button joined to a field) | 1.48 · 1.33 | 1.48 · 1.33 | 3 | **STILL FAILS** |
| 10 | `components/FormModal.tsx:1866` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 11 | `components/SegmentedControl.tsx:218` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 12 | `portal/accounts/MyAccounts.tsx:136` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 13 | `portal/accounts/MyAccounts.tsx:146` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 14 | `portal/accounts/MyAccounts.tsx:159` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 15 | `portal/accounts/MyAccounts.tsx:167` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 16 | `portal/accounts/MyAccounts.tsx:237` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 17 | `portal/accounts/MyAccounts.tsx:460` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 18 | `portal/accounts/MyAccounts.tsx:521` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 19 | `portal/accounts/TemporaryStopCard.tsx:73` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 20 | `portal/accounts/YourAccount.tsx:232` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 21 | `portal/accounts/YourAccount.tsx:239` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 22 | `portal/accounts/YourAccount.tsx:276` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 23 | `portal/accounts/YourAccount.tsx:281` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 24 | `portal/accounts/YourAccount.tsx:376` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 25 | `portal/accounts/YourAccountPage.tsx:70` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 26 | `portal/agreements/AgreementAcceptance.tsx:67` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 27 | `portal/agreements/AgreementAcceptance.tsx:190` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 28 | `portal/arrears/ArrearsPages.tsx:82` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 29 | `portal/arrears/HelpPaying.tsx:180` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 30 | `portal/arrears/MoneyBack.tsx:226` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 31 | `portal/arrears/MoneyBack.tsx:273` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 32 | `portal/arrears/MoneyBack.tsx:288` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 33 | `portal/arrears/MoneyBack.tsx:357` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 34 | `portal/arrears/MoneyBack.tsx:361` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 35 | `portal/arrears/MoneyBack.tsx:365` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 36 | `portal/arrears/Overdue.tsx:234` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 37 | `portal/arrears/Overdue.tsx:242` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 38 | `portal/arrears/Overdue.tsx:254` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 39 | `portal/arrears/Overdue.tsx:310` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 40 | `portal/arrears/Overdue.tsx:323` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 41 | `portal/arrears/Overdue.tsx:342` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 42 | `portal/arrears/Protections.tsx:265` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 43 | `portal/bill-link/BillLinkCard.tsx:55` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 44 | `portal/bills/BillComparison.tsx:305` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 45 | `portal/bills/BillComparison.tsx:426` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 46 | `portal/bills/BillDetail.tsx:271` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 47 | `portal/bills/BillDetail.tsx:603` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 48 | `portal/bills/BillDetail.tsx:676` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 49 | `portal/bills/Bills.tsx:338` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 50 | `portal/bills/Bills.tsx:574` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 51 | `portal/bills/Bills.tsx:712` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 52 | `portal/bills/Bills.tsx:716` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 53 | `portal/bills/Bills.tsx:723` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 54 | `portal/bills/Bills.tsx:728` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 55 | `portal/bills/FinalBill.tsx:108` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 56 | `portal/bills/FinalBill.tsx:118` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 57 | `portal/bills/FinalBill.tsx:132` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 58 | `portal/bills/FinalBill.tsx:178` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 59 | `portal/bills/FinalBill.tsx:293` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 60 | `portal/bills/FinalBill.tsx:320` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 61 | `portal/bills/FinalBill.tsx:372` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 62 | `portal/bills/FinalBillPage.tsx:44` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 63 | `portal/components/content.tsx:240` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 64 | `portal/components/content.tsx:288` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 65 | `portal/components/content.tsx:293` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 66 | `portal/components/content.tsx:308` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 67 | `portal/components/content.tsx:314` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 68 | `portal/components/heldCommit.tsx:61` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 69 | `portal/components/listTable.tsx:516` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 70 | `portal/components/primitives.tsx:75` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 71 | `portal/components/primitives.tsx:125` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 72 | `portal/components/primitives.tsx:417` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 73 | `portal/components/primitives.tsx:571` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 74 | `portal/components/primitives.tsx:638` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 75 | `portal/components/primitives.tsx:843` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 76 | `portal/components/primitives.tsx:912` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 77 | `portal/components/primitives.tsx:1166` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 78 | `portal/components/primitives.tsx:1210` | `text-neutral-300` | text | 1.48 · 1.33 | 1.48 · 1.33 | 4.5 | **STILL FAILS** |
| 79 | `portal/components/primitives.tsx:1225` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 80 | `portal/components/primitives.tsx:1228` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 81 | `portal/components/primitives.tsx:1484` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 82 | `portal/components/primitives.tsx:1682` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 83 | `portal/components/primitives.tsx:1845` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 84 | `portal/components/primitives.tsx:2070` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 85 | `portal/components/primitives.tsx:2165` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 86 | `portal/components/primitives.tsx:2278` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 87 | `portal/components/primitives.tsx:2339` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 88 | `portal/components/states.tsx:232` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 89 | `portal/details/AddAccount.tsx:251` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 90 | `portal/details/EmailCodeStep.tsx:113` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 91 | `portal/details/MyDetails.tsx:200` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 92 | `portal/details/MyDetails.tsx:251` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 93 | `portal/details/MyDetails.tsx:398` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 94 | `portal/details/MyDetails.tsx:403` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 95 | `portal/details/Preferences.tsx:202` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 96 | `portal/details/Preferences.tsx:243` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 97 | `portal/details/Preferences.tsx:252` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 98 | `portal/details/Preferences.tsx:289` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 99 | `portal/details/Preferences.tsx:313` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 100 | `portal/details/Preferences.tsx:351` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 101 | `portal/details/Preferences.tsx:467` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 102 | `portal/documents/Documents.tsx:299` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 103 | `portal/documents/Documents.tsx:335` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 104 | `portal/documents/Documents.tsx:552` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 105 | `portal/documents/Documents.tsx:558` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 106 | `portal/documents/Documents.tsx:593` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 107 | `portal/documents/Documents.tsx:620` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 108 | `portal/documents/Documents.tsx:670` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 109 | `portal/documents/Documents.tsx:707` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 110 | `portal/documents/DocumentsPage.tsx:61` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 111 | `portal/guest/ApplicationCustomFields.tsx:157` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 112 | `portal/guest/ApplicationDocuments.tsx:184` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 113 | `portal/guest/ApplicationDocuments.tsx:287` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 114 | `portal/guest/ApplyForService.tsx:503` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 115 | `portal/guest/ApplyForService.tsx:889` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 116 | `portal/guest/ApplyForService.tsx:1122` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 117 | `portal/guest/CentresPage.tsx:213` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 118 | `portal/guest/CentresPage.tsx:225` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 119 | `portal/guest/CentresPage.tsx:360` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 120 | `portal/guest/CentresPage.tsx:386` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 121 | `portal/guest/CentresPage.tsx:404` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 122 | `portal/guest/CentresPage.tsx:440` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 123 | `portal/guest/CoApplicantCard.tsx:127` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 124 | `portal/guest/HelpPage.tsx:112` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 125 | `portal/guest/HelpPage.tsx:529` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 126 | `portal/guest/HoldingPage.tsx:24` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 127 | `portal/guest/QuickPay.tsx:222` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 128 | `portal/guest/QuickPay.tsx:255` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 129 | `portal/guest/QuickPay.tsx:267` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 130 | `portal/guest/QuickPay.tsx:272` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 131 | `portal/guest/QuickPayCheck.tsx:232` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 132 | `portal/guest/QuickPayCheck.tsx:261` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 133 | `portal/guest/QuickPayCheck.tsx:302` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 134 | `portal/guest/QuickPayCheck.tsx:366` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 135 | `portal/guest/QuickPayCheck.tsx:447` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 136 | `portal/guest/QuickPayCheck.tsx:460` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 137 | `portal/guest/QuickPayCheck.tsx:465` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 138 | `portal/guest/QuickPayDone.tsx:131` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 139 | `portal/guest/QuickPayDone.tsx:226` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 140 | `portal/guest/ReportRouted.tsx:36` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 141 | `portal/guest/ReportSent.tsx:51` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 142 | `portal/guest/ReportSent.tsx:111` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 143 | `portal/guest/ReportSent.tsx:115` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 144 | `portal/guest/TrackAnything.tsx:320` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 145 | `portal/home/Home.tsx:331` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 146 | `portal/methods/Autopay.tsx:110` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 147 | `portal/methods/Autopay.tsx:117` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 148 | `portal/methods/Autopay.tsx:286` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 149 | `portal/methods/Autopay.tsx:334` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 150 | `portal/methods/AutopayPage.tsx:76` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 151 | `portal/methods/Methods.tsx:256` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 152 | `portal/methods/Methods.tsx:397` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 153 | `portal/methods/Methods.tsx:476` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 154 | `portal/methods/Methods.tsx:516` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 155 | `portal/methods/Methods.tsx:559` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 156 | `portal/methods/Methods.tsx:631` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 157 | `portal/payments/Fees.tsx:143` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 158 | `portal/payments/PayNow.tsx:492` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 159 | `portal/payments/PayNow.tsx:534` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 160 | `portal/payments/PayNow.tsx:563` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 161 | `portal/payments/PayNow.tsx:591` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 162 | `portal/payments/PayNowDone.tsx:221` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 163 | `portal/payments/PayNowDone.tsx:235` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 164 | `portal/payments/Payments.tsx:366` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 165 | `portal/payments/Payments.tsx:378` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 166 | `portal/payments/Payments.tsx:461` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 167 | `portal/payments/Payments.tsx:681` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 168 | `portal/payments/Payments.tsx:697` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 169 | `portal/payments/Payments.tsx:715` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 170 | `portal/payments/Payments.tsx:811` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 171 | `portal/plans/AskForPlan.tsx:224` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 172 | `portal/plans/AskForPlan.tsx:253` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 173 | `portal/plans/AskForPlan.tsx:401` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 174 | `portal/plans/AskForPlanPage.tsx:69` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 175 | `portal/plans/LevelPay.tsx:245` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 176 | `portal/plans/LevelPay.tsx:332` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 177 | `portal/plans/LevelPay.tsx:339` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 178 | `portal/plans/LevelPay.tsx:356` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 179 | `portal/plans/LevelPay.tsx:480` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 180 | `portal/plans/LevelPayPage.tsx:61` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 181 | `portal/plans/LevelPayStanding.tsx:301` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 182 | `portal/plans/LevelPayStanding.tsx:362` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 183 | `portal/plans/LevelPayStandingPage.tsx:32` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 184 | `portal/plans/PlanOffer.tsx:308` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 185 | `portal/plans/PlanOffer.tsx:381` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 186 | `portal/plans/PlanOffer.tsx:438` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 187 | `portal/plans/PlanOffer.tsx:450` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 188 | `portal/plans/PlanOffer.tsx:455` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 189 | `portal/plans/PlanOfferPage.tsx:61` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 190 | `portal/plans/YourPlan.tsx:297` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 191 | `portal/plans/YourPlan.tsx:302` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 192 | `portal/plans/YourPlan.tsx:421` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 193 | `portal/plans/YourPlanPage.tsx:72` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 194 | `portal/premises/PremisesStatement.tsx:164` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 195 | `portal/premises/PremisesStatement.tsx:256` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 196 | `portal/premises/PremisesStatement.tsx:279` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 197 | `portal/premises/PremisesStatement.tsx:324` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 198 | `portal/premises/PremisesStatementPage.tsx:90` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 199 | `portal/requests/AskAQuestion.tsx:150` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 200 | `portal/requests/AskAQuestion.tsx:168` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 201 | `portal/requests/DisputeBill.tsx:230` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 202 | `portal/requests/DisputeBill.tsx:260` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 203 | `portal/requests/DisputeBill.tsx:417` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 204 | `portal/requests/Requests.tsx:305` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 205 | `portal/requests/Requests.tsx:316` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 206 | `portal/requests/Requests.tsx:391` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 207 | `portal/requests/StopOrRestart.tsx:611` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 208 | `portal/requests/StopOrRestart.tsx:626` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 209 | `portal/requests/StopOrRestartPage.tsx:66` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 210 | `portal/requests/TrackRequest.tsx:308` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 211 | `portal/shell/GuestFrame.tsx:465` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 212 | `portal/shell/PortalShell.tsx:314` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 213 | `portal/shell/PortalShell.tsx:318` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 214 | `portal/shell/PortalShell.tsx:517` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 215 | `portal/signin/Enrol.tsx:195` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 216 | `portal/signin/Enrol.tsx:261` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 217 | `portal/signin/Enrol.tsx:303` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 218 | `portal/signin/Enrol.tsx:327` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 219 | `portal/signin/ForgotPassword.tsx:95` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 220 | `portal/signin/ForgotPassword.tsx:165` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 221 | `portal/signin/FrontDoor.tsx:86` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 222 | `portal/signin/FrontDoor.tsx:88` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 223 | `portal/signin/FrontDoor.tsx:93` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 224 | `portal/signin/FrontDoor.tsx:96` | `text-neutral-500` | text | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 225 | `portal/signin/UpdateEmail.tsx:100` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 226 | `portal/signin/UpdateEmail.tsx:271` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 227 | `portal/signin/UpdateEmail.tsx:327` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 228 | `portal/signin/UpdateEmail.tsx:355` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 229 | `portal/signin/UpdateEmail.tsx:395` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 230 | `portal/signin/UpdateEmail.tsx:423` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 231 | `portal/signin/UpdateEmail.tsx:460` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 232 | `portal/signin/UpdateEmail.tsx:464` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 233 | `portal/usage/Equipment.tsx:302` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 234 | `portal/usage/Equipment.tsx:423` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 235 | `portal/usage/Equipment.tsx:477` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 236 | `portal/usage/Equipment.tsx:499` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 237 | `portal/usage/Equipment.tsx:507` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 238 | `portal/usage/Equipment.tsx:566` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 239 | `portal/usage/Readings.tsx:374` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 240 | `portal/usage/Readings.tsx:456` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 241 | `portal/usage/Readings.tsx:656` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 242 | `portal/usage/Readings.tsx:672` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 243 | `portal/usage/Readings.tsx:680` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 244 | `portal/usage/Usage.tsx:336` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 245 | `portal/usage/Usage.tsx:760` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 246 | `portal/usage/Usage.tsx:776` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 247 | `portal/usage/Usage.tsx:862` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 248 | `portal/usage/Usage.tsx:931` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 249 | `portal/usage/Usage.tsx:965` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 250 | `portal/usage/Usage.tsx:1005` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 251 | `portal/usage/Usage.tsx:1061` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 252 | `portal/usage/Usage.tsx:1073` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 253 | `portal/usage/Usage.tsx:1111` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 254 | `portal/usage/Usage.tsx:1193` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 255 | `portal/usage/UsagePages.tsx:87` | `text-neutral-600` | text | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 256 | `portal/components/primitives.tsx:861` | `text-neutral-500` | chart label or legend | 2.89 · 2.59 | 5.58 · 5 | 4.5 | passes |
| 257 | `portal/components/primitives.tsx:878` | `text-neutral-600` | chart label or legend | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 258 | `portal/components/primitives.tsx:892` | `text-neutral-600` | chart label or legend | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 259 | `portal/components/primitives.tsx:905` | `text-neutral-600` | chart label or legend | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 260 | `portal/components/primitives.tsx:1763` | `text-neutral-600` | chart label or legend | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 261 | `portal/components/primitives.tsx:1770` | `text-neutral-600` | chart label or legend | 4.3 · 3.85 | 5.58 · 5 | 4.5 | passes |
| 262 | `portal/components/primitives.tsx:888` | `bg-neutral-300` | chart mark (non-text) | 1.48 · 1.33 | 1.48 · 1.33 | 3 | **STILL FAILS** |
| 263 | `portal/components/primitives.tsx:1699` | `border-neutral-300` | chart baseline | 1.48 · 1.33 | 1.48 · 1.33 | none | no rule |
| 264 | `portal/components/primitives.tsx:1210` | `border-neutral-300` | step marker (future step) | 1.48 · 1.33 | 1.48 · 1.33 | 3 | **STILL FAILS** |
| 265 | `portal/components/primitives.tsx:576` | `border-neutral-300` | step marker | 1.48 · 1.33 | 1.48 · 1.33 | none | no rule |
| 266 | `portal/components/content.tsx:302` | `border-neutral-300` | divider | 1.48 · 1.33 | 1.48 · 1.33 | none | no rule |
| 267 | `portal/components/primitives.tsx:402` | `border-neutral-300` | divider | 1.48 · 1.33 | 1.48 · 1.33 | none | no rule |
| 268 | `portal/components/primitives.tsx:2086` | `border-neutral-300` | divider | 1.48 · 1.33 | 1.48 · 1.33 | none | no rule |
| 269 | `portal/guest/ApplyForService.tsx:1729` | `border-neutral-300` | divider | 1.48 · 1.33 | 1.48 · 1.33 | none | no rule |
| 270 | `portal/guest/CentresPage.tsx:91` | `border-neutral-300` | divider | 1.48 · 1.33 | 1.48 · 1.33 | none | no rule |
| 271 | `portal/guest/CentresPage.tsx:305` | `border-neutral-300` | divider | 1.48 · 1.33 | 1.48 · 1.33 | none | no rule |
| 272 | `portal/guest/CentresPage.tsx:395` | `border-neutral-300` | divider | 1.48 · 1.33 | 1.48 · 1.33 | none | no rule |
| 273 | `portal/shell/PortalShell.tsx:479` | `border-neutral-300` | divider | 1.48 · 1.33 | 1.48 · 1.33 | none | no rule |
| 274 | `components/StatusPill.tsx:58` | `bg-neutral-400` | fill (non-text) | 2.01 · 1.8 | 2.01 · 1.8 | none | no rule |
| 275 | `portal/components/primitives.tsx:1252` | `border-neutral-300` | disabled | 1.48 · 1.33 | 1.48 · 1.33 | exempt | exempt (disabled) |
| 276 | `portal/components/primitives.tsx:1252` | `text-neutral-500` | disabled | 2.89 · 2.59 | 2.89 · 2.59 | exempt | exempt (disabled) |

## 8 · After the eight decisions (lane A11Y-A-FINISH, 2026-10-23)

Built under the decision log entries *"Group A, the eight remaining colour decisions: all agreed as recommended"* and *"Group A, the eight decisions: how they are built"*. Measured with this script on a private copy of the Pine Hill fixture (dropped afterwards), axe-core 4.10.3, every routed page (53 of 55; `/start-service/:draft` and `/requests/:reference` have no address to type), English and Spanish, signed out and signed in: 212 page loads per brand. The bill used for the tester's page 20 and 21 is the login's own first bill, `BL-2610-000052`, in place of `BL-2609-000651`.

**Before** is the build at `4ba5cb9a3` (after the first colour lane; every grey already fixed). **After** is the build at `8179d3401` plus the bill ring fix `854bfd6f2`.

| Scan | Contrast failures (axe) | Brand text measured by the script, under 4.5 |
|---|---|---|
| Before, `#EC3013` | **208** (27 + 27 signed out, 74 + 80 signed in) | 342 |
| After, `#EC3013` | **0** | 0 |
| After, dark `#1D3557` | **0** | 0 |
| After, light `#E8590C` (darkened to 82%, `#BE490A`) | **0** | 0 |
| After, `#F5C518` (now refused on save), signed out, English | **0** | 0 |
| After, `#EC3013`, `--states` (hover, focus, selected, empty-submit errors), English | **0** in every state; 1,014 focus stops, none under 3:1; one without a ring (the embedded bill), fixed in `854bfd6f2` and re-measured: 4.20 | 0 |

**The tester's 23 pages** (failures en / es; *n/s* is the tester's "not fully specified"):

| # | Page | Tester | Before | After `#EC3013` | After dark | After light |
|---|---|---|---|---|---|---|
| 1 | Home `/` | 6 | 3 / 3 | 0 / 0 | 0 / 0 | 0 / 0 |
| 2 | Pay a bill | 7 | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 3 | Report a problem | 5 | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 4 | Ask us for something | 5 | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 5 | Track | 2 | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 6 | Start service | 5 | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 7 | Sign in | 0 | 5 / 5 | 0 / 0 | 0 / 0 | 0 / 0 |
| 8 | Set up login | 5 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| 9 | Forgot password | 1 | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 10 | Home (signed in) | 12 | 0 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 11 | Help | 2 | 2 / 2 | 0 / 0 | 0 / 0 | 0 / 0 |
| 12 | Bills | 9 | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 13 | Usage | 27 | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 14 | Payments | 15 | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 15 | Requests | 1 | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 16 | My details | n/s | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 17 | Account | n/s | 2 / 2 | 0 / 0 | 0 / 0 | 0 / 0 |
| 18 | Accounts | 3 | 0 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |
| 19 | Pay now | n/s | 2 / 2 | 0 / 0 | 0 / 0 | 0 / 0 |
| 20 | A bill | n/s | 5 / 5 | 0 / 0 | 0 / 0 | 0 / 0 |
| 21 | Bill document | n/s | 2 / 2 | 0 / 0 | 0 / 0 | 0 / 0 |
| 22 | Payment plan | n/s | 2 / 2 | 0 / 0 | 0 / 0 | 0 / 0 |
| 23 | Past due | n/s | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |

**Still open on these pages, and not colour:** Bills' *"incorrect ARIA attribute (3)"* is F-13 (`aria-sort` on a button), Group I, deferred by the PO on 2026-10-23.

**Found on the way, and fixed:** the first after-scan still failed on every page, at **3.75**, on one element: the page-header kicker (`components/TextBits.tsx`), a kit piece outside the first list of files. Every bare `text-accent` in `components/` now reads the text shade; the test scans the whole kit. The embedded bill's ring first drew nothing: once Tab enters the PDF viewer, no CSS focus selector matches (measured), so the ring follows the window's blur (`854bfd6f2`).

**Not changed, and reported:**
- Staff brand-coloured TEXT (`#ec3013` on `#f3f2f2`, 3.76). The decision names the portal; staff reads the accent itself.
- The staff sidebar's active item (light text on the accent fill) is not a primary button and kept its ink.
- An existing utility that saved a light colour before the refusal keeps it; its text is darkened, its focus ring is not (`#F5C518`: ring 1.63 / 1.46). A new save is refused.
- The bill PDF masthead's kind label is `--accent` `#ec3013` text on white (4.20). Decision 8 named only the faint grey.
