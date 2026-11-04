# 15 · Customer Web Portal — the component inventory

**Seventy-nine screens are built from twenty-four components, and this file defines each
one ONCE.** A screen's layout entry in `08-screen-layouts.md` names components from this
list and nothing else. **If a screen needs something not here, add it here first** — a
component defined inside one screen is how a second visual grammar starts.

**Everything is Tailwind utilities (B14 rule 21).** `07-frontend/src/portal/` must be added
to `07-frontend/src/styles/route-b-migrated.txt` **in the module's first commit**, or every
class below renders as nothing at all while `tsc` and every test pass.

**Reuse the staff kit where the drawing matches it.** The blueprint says so — *"a
customer-facing surface with its own visual grammar doubles the design system for no
gain"* — and B14 says the portal meets the same checks. Where a staff component already
exists (`07-frontend/src/components/`) the portal **composes** it; where a component is
portal-only it is defined below as Tailwind.

---

## 0 · Tokens

Set once on the portal root, read everywhere. The brand colour is the **tenant's**, read
from `tenant.brand_primary_hex` — never a constant (⚠ this line and the two token rows read `brand_colour` / `accent_colour` until 2026-09-03; those columns do not exist — `apps/tenancy/models.py:147–148`, `DEF-CWP-3609`).

| Token | Value | Tailwind |
|---|---|---|
| `--brand` | `tenant.brand_primary_hex` (Pine Hill `#EC3013`) | extend `theme.colors.brand = 'rgb(var(--brand-rgb) / <alpha-value>)'`; until then `text-[var(--brand)]` / `border-[var(--brand)]` |
| `--accent` | `tenant.brand_accent_hex` (`#E15B47`) | hover fill on the danger tier only |
| Ink | near-black | `text-neutral-900` |
| Ink-2 (body grey) | `text-neutral-600` | subtitles, descriptions, KV labels |
| Ink-3 (helper) | `text-neutral-500` | helper lines, footers, mono strips |
| Rule | 1px `border-neutral-200` | every card, panel, row |
| Rule-heavy | 2px `border-neutral-900` | total rows only |
| Surface | ~~`bg-white`~~ **`bg-[white]`** (⚠ stamped 2026-09-03: this theme clears Tailwind's stock palette — `bg-white`, `text-white` and every `slate` shade compile to NOTHING; the arbitrary value is what the compiler honours) | cards, panels |
| Ground | `bg-neutral-50` | page background behind cards |
| Radius | **square** | `rounded-none` everywhere; `rounded-sm` at most on inputs |
| Shadow | none | the drawings have no elevation |

**Type scale** (one sans — the staff app's; no second family):

| Role | Size / weight | Tailwind | Rule |
|---|---|---|---|
| Kicker | 11px · uppercase · tracking-wide · 700 | reuse staff `.kicker` (declared once in `global.css`) | B14 rule 2 |
| Page title | 28px · 700 → **25px** | ~~`text-[28px]`~~ **`text-h3 font-bold leading-tight`** (⚠ stamped 2026-09-03: G34 refuses an arbitrary type size — the ruled scale has a name for every step; the nearest named step is used throughout) | — |
| Section title (in-card) | 20px · 700 | `text-xl font-bold` | — |
| Card title | 17px · 700 → **16px** | ~~`text-[17px]`~~ **`text-lead font-bold`** (stamped 2026-09-03, G34) | — |
| Body | 15px · 400 | ~~`text-[15px]`~~ **`text-body leading-relaxed`** (stamped 2026-09-03, G34) | — |
| Small / helper | 13px | ~~`text-[13px]`~~ **`text-base text-neutral-500`** (stamped 2026-09-03, G34) | — |
| Table body | **13.5px** | `text-[13.5px]` | **rule 20, enforced** |
| Table header | **12px** · uppercase · tracking | `text-xs uppercase tracking-wider font-semibold` | rule 20 |
| KPI value | 34px · 700 | `text-[34px] font-bold tabular-nums` | — |
| Button | **14px** default · **12px** small | staff `Button` sizes | **rule 5, enforced** |
| Mono (URL strip, dial input) | 14px mono | `font-mono` | — |

**Spacing:** page gutter `px-5` · card padding `p-4` · panel header `px-4 py-3` · grid gap
`gap-4` · vertical rhythm between blocks `space-y-4`. Content max width `max-w-[1100px]
mx-auto`.

---

## 1 · Frames — the three things every screen sits inside

### `PortalShell` — portal-only
Header row: utility name `font-bold` · `AccountSwitcher` · (right) *Messages* with
superscript count · *Help* · ***Sign out*** · `Avatar` initials in a bordered square.
⚠ **THE DRAWING HAS NO SIGN-OUT AND THAT WAS `DEF-CWP-4359`** (PO on the running product,
2026-09-07: *"we dont have sign out in Customer portal"*). `CWP-022.png` draws
*Messages · Help · MA* and nothing else; the pack's only sign-out is *Sign out everywhere*
on `CWP-024`, which is `sessions/revoke-all` and a different act. The word is added
**after *Help* and before the avatar**, so the drawing's right edge does not move and the
new word joins the row of words rather than turning the avatar into an undrawn menu. It is
`NavActionWord` — the kit's own nav word on a `<button>` that ACTS — never a hand-drawn
control (`B14` rule 36, and this file's rule that a component a screen needs is added to
the kit FIRST). The frame owns it and no screen passes a prop: twenty-five screens render
this shell. `BR-CWP-104` rules where it lands. Below it the
**tab strip**: Home · Bills · Usage · Payments · Requests · My details, active tab
`border-b-[3px] border-[var(--brand)] font-semibold`, strip `border-b border-neutral-200`.
```
header  : flex items-center gap-4 px-5 h-14 bg-white border-b border-neutral-200
switcher: h-9 px-3 border border-neutral-300 bg-white text-[15px] (a real <select> styled per rule 8; renders as a LABEL when the set has one entry)
tabs    : flex gap-6 px-5 border-b border-neutral-200 text-[15px]
tab     : py-3 -mb-px border-b-[3px] border-transparent aria-[current=page]:border-[var(--brand)] aria-[current=page]:font-semibold
```
⚠ Changing the switcher re-scopes **every** tab; the scope is applied in the query
(`BR-CWP-010`).

### `GuestFrame` — portal-only
Header: utility name `font-bold` left; right nav *Help · Visit us · Pay a bill · Report a
problem* as plain links + `Button(outline)` *Sign in*. **Visit us is absent when no centre
is shown; Help is absent when nothing is published** (`BR-CWP-093`).
```
flex items-center justify-between px-5 h-14 bg-white border-b border-neutral-200
nav: flex items-center gap-5 text-[15px] text-neutral-700
```

### `BackOfficeFrame` — **the STAFF `AppShell`**, not portal code
`CWP-069`–`CWP-075` render inside the staff app: left nav rail → Settings tab strip →
Configure sub-tabs → a **segment row** for Customer portal (Overview · Branding · Help &
answers · Tips) drawn as outlined buttons with the current one un-bordered and greyed.
`CWP-074`/`075` use a breadcrumb *Reference data › Service centres* instead. Compose the
existing shell; add nothing.

---

## 2 · Page structure

### `PageHead` — compose staff `PageHeader`
Kicker · title · one grey subtitle (**rule 32: one sentence**) · right-aligned actions
(`secondaryActions` then `primaryAction`, rule 2). **Detail variant:** a small-caps
`← PARENT` back link above the kicker via `backTo` — **rule 1: the header ← is EXIT**.
```
wrapper : flex items-start justify-between gap-4 mb-4
left    : kicker + h1.text-[28px].font-bold + p.text-neutral-600.max-w-[80%]   (rule 18)
back    : text-xs uppercase tracking-wider font-semibold text-neutral-800 mb-2
actions : flex items-center gap-2 shrink-0
```

### `Stepper` — compose staff `WizardFrame` steps rail
Equal cells in one bordered row; each cell = a small square (number, or ✓ when
complete, **brand-outlined when current**) + label. 2, 3 or 4 cells span the full width.
```
row  : grid grid-cols-{n} border border-neutral-200 divide-x divide-neutral-200 mb-4
cell : flex items-center gap-2 px-4 py-2.5 text-[15px]
box  : w-5 h-5 grid place-items-center border text-xs   current→ border-[var(--brand)] text-[var(--brand)]   done→ border-neutral-400 (✓)
```
Inside a stepper the footer's *← Back* means previous step only (rule 1).

### `TwoCol` — the default signed-in body
```
grid grid-cols-12 gap-4      main: col-span-8      rail: col-span-4 space-y-4
```
Drawn at ≈62/35; `8/4` is the nearest grid and is used throughout.
**`TwoEqual`** = `grid grid-cols-2 gap-4`. **`CardGrid3`** = `grid grid-cols-3 gap-4`.
**`KpiRow`** = `grid grid-cols-{3|4} gap-4`.

---

## 3 · Containers

### `Card`
`bg-white border border-neutral-200 p-4`. A plain card has **no header**.

### `Panel` — portal-only, the most-used component
A card with a **small-caps header row** and a bottom rule; optional right-aligned link in
the header.
```
panel  : bg-white border border-neutral-200
header : flex items-center justify-between px-4 py-3 border-b border-neutral-200
title  : kicker (11px uppercase tracking-wide font-bold text-neutral-900)
link   : text-[13px] text-[var(--brand)]
body   : p-4 text-[15px] text-neutral-700
```
**Variants** (same shell, different opening):
- **Info** — body opens with a brand `i` glyph; one bold clause. `Panel.Info`
- **Warning** — body opens with `⚠` in brand red; bold key phrase. `Panel.Warning`
- **Emergency** — `border-l-4 border-l-[var(--brand)]`, bold title in the body, no header
  row. Used once (`CWP-006`).
  ⚠ **BUILT 2026-09-05 (`DEF-CWP-3986`) as `tone="emergency"` on the shared `Panel`, and
  the accent is `border-l-accent`, NOT `border-l-[var(--brand)]`.** `--brand` is a variable
  this product sets NOWHERE and every rule that read it painted GREY (`DEF-CWP-3736`); the
  tenant's own hex arrives as an override of `--color-accent` on the portal frame. The tone
  keeps the plain border and adds the left rule — it is deliberately not a fourth hue, for
  the reason `ReportProblem.tsx` records from looking at the running screen.

### `InfoBar` / `WarningBar` — full-width, single row
```
flex items-start gap-3 border border-neutral-200 bg-white px-4 py-3 text-[15px]
glyph: text-[var(--brand)] font-bold shrink-0
```
An optional trailing `Button(outline)` sits at the end (`CWP-001`, `CWP-037`).

### `ConsequenceBox` — **B14 rule 11**, portal-only
`WHAT THIS WILL DO` header in kicker type · **thick brand left rule** · 3–4 bullets, each
**≤ 6 words per sentence, at most two** (rule 33). The commit button sits **directly below
it, left-aligned**, in a `ButtonRow`.
```
border border-neutral-200 border-l-4 border-l-[var(--brand)] p-4 mb-4
ul: list-disc pl-5 space-y-1.5 text-[15px]
```
Header text varies by screen (*WHAT ACCEPTING THIS DOES*, *WHEN YOU FINISH*, *IF YOU
APPLY*, *WHAT HAPPENS NEXT*, *WHAT HAPPENS IN JUNE*) — same component.

### `TipBar` — portal-only
Full-width under the page head: `border border-neutral-200 border-l-4 border-l-[var(--brand)]
flex items-center gap-3 px-4 py-3`, kicker-type brand **TIP**, one sentence, `×` dismiss at
the far right. **Not rendered when no tip is live** — the element is absent, not empty
(`BR-CWP-095`).

### `AttachedAnswerCard` — portal-only
Under a bill's charges: `border border-neutral-200 border-l-4 border-l-[var(--brand)] p-4`,
bold question + `→` right, grey two-line excerpt. Absent unless an answer is attached.

---

## 4 · Data display

### `KVList` — portal-only
Rows of grey label (left) and bold value (right), 1px rule per row. **`TotalRow`**
variant: `border-t-2 border-neutral-900`, both sides bold, `text-[17px]`.
```
row  : flex justify-between items-baseline py-2 border-b border-neutral-200 text-[15px]
label: text-neutral-600     value: font-semibold text-right tabular-nums
```
Signed money in the explainer: positive **brand red**, zero and negative ink.

### `KpiTile` — compose staff `KPIStrip` tiles
Kicker label · `text-[34px] font-bold tabular-nums` value with the unit in `text-[15px]
font-normal ml-1` · grey sub-line. **`lead`** variant adds `border-l-4 border-l-[var(--brand)]`
— used for **the balance** (`CWP-022`) and **you pay each month** (`CWP-066`).

### `StatusChip` — **staff `StatusPill`**, tones only
Tiny uppercase bordered chip: `inline-flex px-2 py-0.5 border text-[11px] uppercase
tracking-wider font-semibold`. Tones: **neutral** (grey — PAID, TO COME, REVERSED, HIDDEN),
**success** (green — CLEAR, CLEARED, VERIFIED, ACTIVE, PUBLISHED, ON, DELIVERED, HOLDING
NOW), **warning** (amber — ESTIMATED, INVITED, NEEDED, DRAFT, SCHEDULED, PAID LATE, NEEDS
TRANSLATING), **danger** (brand — DUE, OVERDUE 19 DAYS, BOUNCED, DUE SOON, CREW ON SITE,
PLANNED, CAME BACK), **info** (blue-grey — the tip target screens, STARTS 1 DECEMBER).
The chip carries a fact of **≤ 6 words** (rule 33).

### `DataTable` — **staff `DataTable` + `FilterBar` + `ListPager`**, one table type
Toolbar `[Search {entities}…] [All | chips] [+ Filter ▾] … [▦ Columns]` (rule 12, 19) ·
headers `⇅` sortable (13) · row actions **icons only, ≤ 2 + overflow** (15) · footer
`Showing 1–50 of N · Rows per page … · ⇤ ← Page x of y → ⇥` (16) · empty state (17).
Body **13.5px**, header **12px** (20). Money right-aligned `tabular-nums`; a quantity
**always carries its unit** (hard rule 3). A bold first column with a grey sub-line is the
standard two-line cell. **Greyed row** = `text-neutral-400` on every cell (a corrected bill,
a hidden centre). **Danger row** = `text-[var(--brand)]` on every cell (a bounced payment).
**Drag handle** `⋮⋮` as a leading column where order is the portal's order (`CWP-071`,
`CWP-073`).

### `MiniTable` — inside a panel, no toolbar, no footer
Same type sizes as `DataTable`; `w-full text-[13.5px]`, header row `text-xs uppercase`.
Used for instalments, readings behind a bill, credits, fees, next-few autopay dates.

### `ChecklistTimeline` — portal-only
Vertical list: a `w-4 h-4 border` square (done → `border-neutral-800` with ✓; **current →
`border-[var(--brand)]`**; future → `border-neutral-300`) · bold step text (`· date`) · grey
detail to the right or beneath. Rows `flex gap-3 py-2`. Used by the guest report, the
request tracker, the refund lifecycle, the reading pipeline, the booked visit and **the
collections ladder**.

### `ErrandCard` — portal-only
`border border-neutral-200 bg-white p-4 flex flex-col gap-2`: `text-[17px] font-bold`
title · grey two-line description · `Button(outline, sm)` *Verb →* at the bottom. Always in
a `CardGrid3`.

### `CentreCard`, `ProtectionCard` — compositions of `Panel` + `StatusChip` + `KVList` +
`Button`. Defined in their screens' entries; nothing new.

### `PreferenceGrid` — portal-only, one screen
A table whose cells are the channel switches; the **POST** cell renders a neutral
**ALWAYS** chip on the four print-floor classes and `—` elsewhere (`BR-CWP-087`, `R4`).

### `DocumentPreview` — portal-only
A bordered frame containing a centred letter-aspect image of the issued PDF:
`border border-neutral-200 p-6 grid place-items-center` → `aspect-[8.5/11] w-[62%] border`.

⚠ **BUILT 2026-09-05 (`DEF-CWP-3983`), AND IT EMBEDS THE KEPT FILE RATHER THAN DRAWING A
PICTURE OF IT.** *"an image of the issued PDF"* reads as something this product could
render, and rendering one would be a second document beside the legal one, free to differ
from it — the whole hazard `BR-CWP-045` and `BR-NOT-027` name. It is an `<object>` pointed
at the document route with `?view=1`, which streams the SAME frozen bytes and changes only
`Content-Disposition`. `<object>` and not `<iframe>` or `<embed>` because it is the only
one of the three with a **child fallback**, so a browser with no PDF viewer gets the
download link instead of a silent grey rectangle. The `aspect` is on the frame: a PDF
viewer reports no intrinsic size, so an unsized object collapses to about 150px.

### `ChartPanel` — `Panel` with a chart body
Bars `bg-neutral-100`, axis labels `font-mono text-xs text-neutral-500`, legend line
below. **Load the `dataviz` skill before drawing a real chart.** The unit is on the axis
(hard rule 3).

---

## 5 · Controls

### `Button` — **staff `Button`**, variants and sizes as it defines them
Sizes: default (14px) and small (12px) — **rule 5, enforced**. Label grammar — **rule 4**:
`+ Noun` creator · `Verb →` navigates · `Verb ✓` commits · `↓` download · `↑` upload · `↗`
opens an external thing.
- **Commit** (enabled) — outlined ink: `border border-neutral-900 text-neutral-900 bg-white
  hover:bg-neutral-900 hover:text-white`.
- **Secondary** — outlined grey: `border border-neutral-300 text-neutral-900`.
- **Danger** — **rule 6**: `border border-[var(--brand)] text-[var(--brand)]
  hover:bg-[var(--accent)] hover:text-white`. Used for **Send this request ✓** (move-out),
  **Request this ✓** (disconnect), **Remove** (a centre). Never for paying a bill.
- **Held** — a control that exists and may not be used yet (`CR-068` `R3`): the drawings
  show it as brand-outlined with grey text. Render as the staff `disabled` presentation
  **plus** a visible one-line reason beneath (≤ 6 words, rule 33) and the reason on
  `title`. **Never hidden, never live-but-inert.**

`ButtonRow` = `flex items-center gap-2 mt-4` — a row with **no way back in it**.

⚠ **AMENDED 2026-10-02 — THIS LINE READ *"`ButtonRow` = …, commit first"* AND EVERY
PORTAL FORM PUT ITS COMMIT LEFT OF ITS BACK. THE PO RULED THE OPPOSITE** (decision log
*"PORTAL START-SERVICE FORM — FIVE DEFECTS"*, `DEF-CWP-9164`), verbatim: *"continue and
Back button mis placed at right side continue button should display at left side back
button should display"* — read and recorded as **Back on the LEFT, Continue / Send on the
RIGHT, on every step and every portal form.** A row with a way back — a stepper's
`← Back`, a *Change*, a *Cancel*, an exit to the card list — is now
**`WizardFooter`** (`portal/components/primitives.tsx`): `back` on the left, `forward`
on the right with the commit last, DOM order Back → forward (which is the tab and
screen-reader order). With no `back`, the commit still sits on the right. Seven screens
moved to it the same day (start service ×3 steps, quick service, stop or restart ×2,
question a bill, pay now, pay now · check, payment methods); `WizardFooter.dom.test.tsx`
asserts each one builds its footer from it.

### `FormField` — portal-only wrapper around the staff inputs
```
label : block text-[13px] font-semibold mb-1     required → <span class="text-[var(--brand)]"> *</span>   (rule 10)
input : w-full h-11 px-3 border border-neutral-300 bg-white text-[15px]
helper: mt-1 text-[13px] text-neutral-500
```
**`TwoUp`** = `grid grid-cols-2 gap-4`. **`ReadOnly`** = `bg-neutral-50 text-neutral-500`
with the helper saying how to change it. **`DialInput`** = `font-mono text-[22px]
tracking-[0.35em] h-14`; **flagged** → `border-[var(--brand)]` + a brand helper sentence.
⚠ **BUILT 2026-09-05 (`DEF-CWP-3986`), AND ALL THREE SPELLINGS ABOVE ARE REFUSED BY THIS
REPO'S OWN RULES WHILE EVERY PIXEL IS UNCHANGED.** `text-[22px]` is `text-metric-sm`
(`--text-metric-sm: 22px`) because eslint bans arbitrary type values by name (decision log
2026-08-19, `OQ-275`/`276`/`278`); `tracking-[0.35em]` is `tracking-dial`, a token added to
`tailwind.css` beside the five wide-tracking values already named there, because `G34` bans
the bracket form outright; and `border-[var(--brand)]` is `border-accent` (`DEF-CWP-3736` —
`--brand` is set nowhere and paints grey). **This entry is kept in its original wording
above rather than rewritten**, because the drawing is the drawing; where it and the ruled
scale disagree, the scale wins and the number does not move.
**`Date`** = the staff date input (rule 7). **`Select`** = the staff dropdown (rule 8;
searchable at 5+). **`PhotoPicker`** = an input-shaped button with `📷` and *Optional…*.

### `RadioList`
Rows `flex items-center gap-3 py-1.5 text-[15px]`; inline grey hint after `·`; an optional
trailing `StatusChip` slot (`CWP-038`).

### `ToggleChips` — payment methods on `CWP-075`
Outlined small chips that toggle; selected = ink border + ink text.

⚠ **THIS PIECE IS ALREADY SHIPPED UNDER ANOTHER NAME AND MUST NOT BE BUILT A SECOND TIME
(measured 2026-09-05, `DEF-CWP-3986`).** `components/ChipMultiSelect.tsx` — added to the
shared kit in `CR-068` wave D under B14 rule 36, for the breach the rule itself names
(*"a **WALL OF CHECKBOXES**, which r10 rule 9 forbids by name"*) — is what `CWP-075`
composes today, on **both** of its multiple-choice fields: *what a customer can do here*
and *takes payment by*. **Building a second toggle control would put two different
multiple-choice controls side by side on ONE screen**, which is the four-different-chips
drift rule 36 exists to stop, and B14 rule 9 already rules how a multiple-choice field
renders in this product. The interactions genuinely differ — `ChipMultiSelect` shows the
CHOSEN values with an add control, while this entry describes all options always visible
— and that difference is a **rule 9 question for whoever owns B14**, not a lane's call.
The mapping belongs beside `FormField.Select` → `SelectInput` in `14-layout-audit.md` §4,
not in its *pieces that do not exist* list.

### `Avatar` — `w-8 h-8 grid place-items-center border border-neutral-300 text-xs
font-bold` with initials only (rule 31).

---

## 6 · What is NOT a component, on purpose

- **No modal for a commit.** Every commit is a page with a `ConsequenceBox`.
- **No toast-as-confirmation.** Every guest flow ends on a **reference screen**.
- **No inline font sizes, no second table type, no third button size** — B14 enforces
  these on the staff app and the portal meets the same gates.
- **No `.css` file in `src/portal/`.** Rule 21.
