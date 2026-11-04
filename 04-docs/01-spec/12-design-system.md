# A12 — Design System

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. Tokens (hex), type scale, spacing, components, breakpoints — Tailwind-ready.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


Tokens are defined in the bound **Modernist** design system (`styles.css`, 253 lines) — namespace `Modernist_modern`. Font family is **Archivo** (400/600/800). **Radii are 0px throughout** (sharp corners are intrinsic to the brand — do not round). Exact values below, transcribed from `styles.css`:

**Core colors**
| Token | Hex | Use |
|---|---|---|
| `--color-bg` | `#f3f2f2` | page background |
| `--color-surface` | `#eae9e9` | cards, inputs, panels |
| `--color-text` | `#201e1d` | ink / primary text |
| `--color-accent` | `#ec3013` | primary / brand (vermilion) |
| `--color-accent-2` | `#e15b47` | secondary accent |
| `--color-divider` | `#201e1d` @ 40% alpha | borders, rules |

**Accent ramp** (primary): 100 `#fff2ef` · 200 `#ffe0d9` · 300 `#ffc4b8` · 400 `#ff9783` · 500 `#ff563c` · 600 `#dd2b0f` · 700 `#ae1800` · 800 `#7c1405` · 900 `#4d170e`. Buttons: base `--color-accent`, hover `-600`, active `-700`.
**Accent-2 ramp:** 100 `#fff2ef` · 200 `#ffe0da` · 300 `#ffc4b9` · 400 `#ff9784` · 500 `#ef6853` · 600 `#c94b39` · 700 `#9e3526` · 800 `#71261b` · 900 `#471d16`.
**Neutral ramp:** 100 `#f8f4f4` · 200 `#eae7e7` · 300 `#d7d3d3` · 400 `#bab6b6` · 500 `#9b9797` · 600 `#7d7979` · 700 `#605d5d` · 800 `#444141` · 900 `#2d2b2b`.

**Semantic-color note:** the system ships **no dedicated success/danger/warning tokens** — it is a monochrome-ink + single-accent system. In the prototype, positive money uses `--color-accent-700` and overdue/danger uses `--color-accent`; amber/green pills (`.pill.warn/.ok/.past/.draft`) are prototype-local, **not** in `styles.css`. `RESOLVED for palette; UNKNOWN — product decision: add real success/warning/danger tokens, or keep the accent-only convention?`

- **Type:** `--font-heading` / `--font-body` both **Archivo**; headings weight **800**, letter-spacing −0.015em, line-height 1.12. Scale (from styles.css): h1 42px · h2 32px · h3 25px · h4 20px · h5 16px · h6 13px (uppercase, tracked 0.08em). Body 15px / line-height 1.55 / weight 400. (The prototype overrides some sizes inline, e.g. clamp on wizard h1 — treat styles.css as canonical.)
- **Spacing scale:** `--space-1..8` = 4 / 8 / 12 / 16 / 24 / 32px. **Radii `--radius-sm/md/lg` all 0px.**
- **Elevation:** `--shadow-sm` `0 1px 2px` ink@14% · `--shadow-md` `0 3px 10px` ink@16% · `--shadow-lg` `0 12px 32px` ink@22% (helpers `.elev-sm/md/lg`).
- **Grid helpers (prototype):** view padding 28/32 (→18–24 responsive); `.two-col` (1fr 1fr → 1fr < 1200px); `.kpi-grid` auto-fit minmax(180px,1fr).
- **Components:** button (`.btn` primary/secondary/ghost/icon), input/select/textarea (`.input`), `.field`+label, `.seg` segmented radios, `.radio` checkbox, `.pill` badges, `.svc-tag` service chips (E/W/G/S/T/B), `.table` (+tfoot), `.card`, `.panel` (+`.h`/`.see`), `.kpi`, `.settings-tabs`, `.br-steps`/`.br-step` (wizard rail), `.wizard`/`.wizard-actions`, `.toolbar`, modal shell (fixed overlay + card + header/body/footer), toast.
- **States:** default/hover/active on buttons & tabs; disabled/loading/error `UNKNOWN — not fully specified`.
- **Icons:** inline stroke SVGs (currentColor). No icon-font.
- **Responsive:** breakpoints 1440 / 1200 / 1024; below 1024 tab strips & step rails scroll horizontally, page-actions wrap, two-col stacks. Mobile (<~700) explicitly out of scope per brief.
- **Empty/loading/error states:** `UNKNOWN — only partial empty states designed; must be authored.`

**Tailwind mapping (ready to use):**
```js
// tailwind.config — Modernist
theme: {
  colors: {
    bg: '#f3f2f2', surface: '#eae9e9', text: '#201e1d',
    accent:  { DEFAULT:'#ec3013', 100:'#fff2ef',200:'#ffe0d9',300:'#ffc4b8',400:'#ff9783',500:'#ff563c',600:'#dd2b0f',700:'#ae1800',800:'#7c1405',900:'#4d170e' },
    accent2: { DEFAULT:'#e15b47', 100:'#fff2ef',200:'#ffe0da',300:'#ffc4b9',400:'#ff9784',500:'#ef6853',600:'#c94b39',700:'#9e3526',800:'#71261b',900:'#471d16' },
    neutral: { 100:'#f8f4f4',200:'#eae7e7',300:'#d7d3d3',400:'#bab6b6',500:'#9b9797',600:'#7d7979',700:'#605d5d',800:'#444141',900:'#2d2b2b' },
  },
  fontFamily: { heading: ['Archivo','system-ui','sans-serif'], body: ['Archivo','system-ui','sans-serif'] },
  borderRadius: { none:'0px', sm:'0px', md:'0px', lg:'0px' }, // brand is sharp-cornered
  spacing: { 1:'4px',2:'8px',3:'12px',4:'16px',6:'24px',8:'32px' },
  boxShadow: { sm:'0 1px 2px rgba(45,43,43,.14)', md:'0 3px 10px rgba(45,43,43,.16)', lg:'0 12px 32px rgba(45,43,43,.22)' },
}
```
`--color-divider` = `color-mix(in srgb, #201e1d 40%, transparent)` → `rgba(32,30,29,.40)`. Prefer shipping `styles.css` itself as the source of truth; this config mirrors it 1:1.

---


## Addendum — Settings adds no new tokens
The Settings rework uses existing components (`.settings-tabs`, `.table`, `.panel`, `.card`, `.lookup-grid`/`.lookup-card`, `.field`/`.input`, `.seg`, `.radio`, modal shell, `.pill`). Audit-lock uses a 🔒 glyph + `not-allowed` cursor (no new token). Confirms the monochrome+accent system holds; still no dedicated success/warning/danger tokens (see gap in README).


## Correction — accent-2 is a stand-in (2026-08-07)
Earlier text calling `--color-accent-2` a "secondary accent" was WRONG. Per `theme.json` (`"scheme":"mono"`) and the design-system readme, the palette is **monochrome + one accent**; `--color-accent-2-*` is a **machine-generated stand-in that reads the same as accent** and carries no semantic meaning. Do not use it as a real second brand color.

## Semantic tokens added (2026-08-07) — resolves the status-color gap
The design system now ships dedicated status tokens in `styles.css` (and `theme.json`), used ONLY for status meaning, never decoration:
| Token | 100 (bg) | 500 | 700 (text) | Use |
|---|---|---|---|---|
| success | `#e6f4ec` | `#1f9d57` | `#0f6e3a` | paid, matched, active, positive money |
| warning | `#fdf0d8` | `#e08a1e` | `#a65d0a` | due-soon, estimated, needs-review |
| danger | `#fde4df` | `#e0341a` | `#a81600` | overdue, failed, unmatched, disconnect |
Status pills are now real design-system classes: `.pill.ok` → success, `.pill.warn` → warning, `.pill.past` → danger, `.pill.draft` → neutral-200/700. They are no longer prototype-local hacks.

**Tailwind additions:** `success:{100:'#e6f4ec',500:'#1f9d57',700:'#0f6e3a'}, warning:{100:'#fdf0d8',500:'#e08a1e',700:'#a65d0a'}, danger:{100:'#fde4df',500:'#e0341a',700:'#a81600'}`.
