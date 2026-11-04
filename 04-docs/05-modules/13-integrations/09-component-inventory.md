# 13 · Integrations — component inventory

**The components the 41 frames are built from, each defined once as Tailwind utilities and mapped to the
staff kit.** The pack's own vocabulary is the proof this list should be short — *"one `.win` per frame, then
`.scr-hd`, `.pill`, `.counts`, `.tbl`, `.note`, `.frow` and `.acts`. Nine providers do not become nine
components."* B14 rule 21: `features/integrations/` joins `07-frontend/src/styles/route-b-migrated.txt` in
its first commit, or every utility below renders as nothing while `tsc` and the tests pass. Compose the staff
kit; do not fork it.

**Staff surface, staff tokens.** Integrations is a Settings tab; it inherits `tokens.css`. The frames use four
accents on white: **teal** (primary outline buttons, *Working*, *Reading from us*, *Accepting*, the lead
`CountTile` border) → `text-teal-700 border-teal-600` · **amber** (*Not tested yet*, *Unconfirmed*,
*Collecting*, the warning box, the unusual access row) → `text-amber-700 border-amber-600` · **red** (*Not
working*, *Not collecting*, *No answer*, *Failed*, **Fix it**, **Disconnect**, **Revoke the key**, **Map it**,
the refused tile, the money-consequence box) → `text-red-700 border-red-600` · **green** (*Passed*, *Working*
on the first proposal, *Ran cleanly*, *Handed over*, *active*) → `text-green-700`. Mono (`font-mono
text-[11px] uppercase tracking-wider text-slate-500`) for every kicker, column header, badge and support
reference; mono at 13 px (`font-mono text-[13px]`) for every value a machine gave us — an address, a key
hint, a hash, a count in a table cell.

## Frames

| Component | What it is | Recipe | Staff kit |
|---|---|---|---|
| `StaffShell` + `SettingsNav` | the Settings page's left nav; *Integrations* is a tab in it | exists | `SettingsPage.tsx` |
| `Modal` | the connect/manage frame: label-left rows, a dashed field slot, a footer row | `max-w-[700px] p-5 bg-white border border-slate-300`; rows `grid grid-cols-[160px_1fr] gap-3 items-center py-2` | staff `Modal` |
| `ConfirmDialog` (destructive) | the disconnect: question · red box · blue box · type-the-name · red commit disabled until typed | staff `ConfirmDialog` with `variant="danger"` and a `confirmText` | exists |

## Heads, filters, cards

| Component | Recipe | Notes |
|---|---|---|
| `PageHead` — title (`text-xl font-semibold`) · one sentence (`text-sm text-slate-600 max-w-[60ch]`) · right-side control | staff `PageHeader` | rule 32: one sentence |
| `CategoryFilter` — mono caps chips, *ALL* active | `flex gap-2`; chip `font-mono text-[11px] uppercase tracking-wider px-2 py-1 border border-slate-300`; active `border-teal-600 text-teal-700` | **generated from the registry's categories** — never a typed list (the pack's callout) |
| `CardGrid` — three `ProviderCard`s per row | `grid grid-cols-3 gap-4` | — |
| `ProviderCard` — kicker with direction (*EMAIL · WE SEND*) · name · one sentence · `StateWord` + mono meta · one full-width button | `border border-slate-300 p-4 flex flex-col gap-2`; button `w-full` | one manifest each; the button's label and tier come from the state (below) |
| `StateWord` — the card state as a coloured **word** with a mono meta after a middle dot | `font-semibold text-sm` + tone; meta `font-mono text-xs text-slate-500` | seven states: *Not set up* (slate) · *Not tested yet* (amber) · *Working* (green) · *Not working* (red) · *Turned off* (slate) · *Reading from us* (teal) · *Coming soon · W7* (slate, hollow dot) — **words, not pills**; the staff `StatusPill`'s tone tokens, in text |
| state → button | 1 **Connect** (secondary) · 2 **Test it now** (primary) · 3 **Manage** (primary) · 4 **Fix it** (danger) · 5 **Turn on** (primary) · 6 **Manage** · 7 **Connect** dashed (`border-dashed text-slate-400`, `aria-disabled`) | one map, in the manifest reader, not in nine components |

## Forms

| Component | Recipe | Notes |
|---|---|---|
| `Segmented` — *Sign-in \| Password \| Key file*, *Production \| Sandbox*, *Nightly \| Hourly \| Manual*, *BAI2 \| camt.053 \| CSV \| OFX* | `inline-flex border border-slate-300 text-sm`; segment `px-3 py-1.5 border-r last:border-r-0`; active `bg-slate-100 text-slate-900`; disabled `text-slate-400` | the manifest decides which segments exist and which is fixed |
| `FieldSlot` — the dashed region *rendered from manifest.fields* | `border border-dashed border-teal-600 p-3 my-3`; caption mono caps teal | the only part of the modal that varies |
| `FormRow` — label left, value right; values a machine gave us in mono | label `text-sm text-slate-700 text-right`; input `border border-slate-300 px-3 py-2 font-mono text-[13px] w-full` | staff `FormField`, laid out label-left |
| `ChoiceChips` — *Payments \| Bills \| Customers*, *12 Silver Creek Rd \| All of mine* | as `Segmented`, multi-select where the manifest says | — |
| `RedirectPanel` — dashed box · **Sign in with Microsoft** · *We never see or store your password.* | `border border-dashed border-teal-600 p-4 text-center` | field kind `redirect`; **no Save in the footer** |
| `IssuedKeyPanel` — dashed *THE KEY FOR THEM TO USE* · key in mono · **Copy** · *Copy it now. This is the only time it is shown.*; afterwards the masked hint only | key `font-mono text-[13px] border px-3 py-2`; **Copy** primary small | field kind `issued_secret` |
| `ColumnMapping` — *WHICH COLUMN IS WHICH*: rows `Column 1 — 20260901 → Date` (a select) | `grid grid-cols-[1fr_auto_1fr] gap-2 items-center` per row | field kind `mapping_editor`; **appears only once a file has been seen** |
| `ButtonRow` — **Save and test** (primary) · **Cancel** · one explanatory sentence | `flex items-center gap-3 pt-3 border-t`; sentence `text-sm text-slate-600` | — |

## Detail, runs, counts

| Component | Recipe | Notes |
|---|---|---|
| `DetailHead` — name (mono for an address, semibold for a provider) · `StateWord` right · meta line (*Production · connected by Alex Reed, 12 Aug · they call us*) | `flex justify-between items-baseline`; meta `text-sm text-slate-600` | — |
| `BudgetLine` — *Calls used this week* … **4,180 of 10,000** (mono, right) + one sentence | `flex justify-between text-sm`; figure `font-mono` | `BR-INT-034`; red when spent |
| `WarningBox` (amber) — ***Needs re-authorising by 12 September.** After that, bills stop going out.* | `border border-amber-600 p-3 text-sm` | the dated sentence, in words |
| `AlertBox` (red) — the money consequence, the four unsafe defaults, *2 of their 14 values are not mapped* | `border-l-4 border-red-600 border p-3 text-sm` | never a toast |
| `NoteBox` (grey, `.note`) — the explanatory aside under a table or a tile row | `border-l-4 border-slate-300 pl-3 py-2 text-sm text-slate-700` | rule 32: no id in it |
| `InfoBar` (blue) — *4 matches from the City's records*, *They are building the file…* | `border-l-4 border-teal-700 pl-3 py-2 text-sm font-semibold` | — |
| `OperationsTable` — OPERATION (+ sub-sentence) · HOW IT RUNS · STATE · LAST · a button | B14 rule 20 table; sub-sentence `text-xs text-slate-500` | `C1`; **no aggregate word** for a provider with several operations |
| `RunsTable` / `AccessLog` — WHEN (mono) · WHAT RAN / WHAT THEY TOOK · RESULT (coloured text with a **second number in bold**) · ROWS / SUPPORT REF (mono) | rule 20 table; unusual row `font-semibold` and an `AmberBox` beneath | `C13`; CR-045 toolbar on both |
| `CountTile` — big figure · small label; **a dash where a number would be a claim**; the lead tile bordered teal, a refused tile bordered red | `border border-slate-300 p-3`; figure `text-2xl font-semibold tabular-nums`; label `text-xs text-slate-600` | the staff `KPIStrip` tile with the label **under** the figure; four (or two) in a row |
| `ItemList` — *THE SEVEN IT COULD NOT SEND*: account · masked address · reason | mono caps caption; rows `grid grid-cols-[120px_1fr_auto] text-sm py-1 border-b` | masked at the adapter |
| `SupportRef` — *Support reference **4C71A0E5*** | `text-sm`; code `font-mono` | rule 31: the only identifier on the screen, labelled |
| `KeysTable` — **In use** `••••A17C` *Added today, 17:04* **active** / **Previous** `••••3F9A` **Go back to this** | two rows, rule 20 | `BR-INT-025` |
| `RunCard` — title + result word right · sentence · tiles · list or note · one button + `SupportRef` | `border border-slate-300 p-4` | the shape of 51.1, 51.2, 53.x, 54.x, 80.1, 81.1, 82.2, 83.2, 75.1 |
| `TestOutcomeCard` — title · **Passed / Failed / No test** · sentence · optional `ProviderSaid` · note · **Done / Try again · Edit / Close** | as `RunCard` | `BR-INT-019` |
| `ProviderSaid` — *THE SERVER SAID: 535 5.7.8 AUTHENTICATION FAILED* | `font-mono text-xs bg-slate-50 border p-2` | `provider_error`, scrubbed, owning tenant only |
| `ProgressBand` — *Asked them **4 times*** · **checking again in 30 s** (mono) · **Stop waiting** · *You can leave this page.* | the bill run's own progress band | `C10`, nothing new |
| `DefaultsTable` — WHAT · IF WE SAID NOTHING (mono) · **WHAT WE SAY** (bold) | rule 20 table | `C18` |
| `MappingRow` — `CODE` (mono) → our value · **Change**; unmapped: red border, *not set — will record as Other*, **Map it** (danger) | `flex items-center justify-between border p-3 my-2`; unmapped `border-red-600` | `C4`, `BR-INT-032` |
| `MatchRow` — address · mono parcel · *strong match* / *close match* · **Use this** | `border p-3 flex justify-between` | `C17`: **never a score as a number** |
| `KVRows` — *We have · **Outside the city** · no city tax* | `grid grid-cols-[1fr_auto] text-sm py-2 border-b`; key mono | the decision card |
| `ConsentForm` / `ChoiceGroup` / `ConsentTable` | question title · sentence · three `ChoiceChips` groups · blue note · **Allow** · **No thanks**; table WHO · WHAT · UNTIL · **Stop it** (danger) / *ended* | **conditional `OQ-INT-1482`** |
| `RefusalLine` — `409 · this connection is not available yet · nothing was saved` | `font-mono text-sm text-red-700 border border-slate-300 p-3` | the server's refusal, six words, catalogue-keyed (rule 33) |

## Buttons

Three tiers, one size on these frames, as the staff `Button` (`variant`, `size`, `data-variant`): **primary
outline** (`border border-teal-600 text-teal-700`) — *Save and test · Manage · Test it now · Turn on · Re-authorise
now · Accept the change · Use this · Allow*; **secondary** (`border border-slate-400 text-slate-900`) — *Cancel ·
Done · Close · Edit · Remind me · Keep ours · Ask the City · Type it in instead · Try the City again · No thanks ·
History · Who has read · Mappings · Replace key · Download it again · Run it now*; **danger** (`border
border-red-600 text-red-700`) — *Fix it · Disconnect · Revoke the key · Map it · Stop it · Map the 2*. **Disabled
until a condition** (`opacity-50 cursor-not-allowed`): *Disconnect* until the name is typed; the coming-soon
*Connect* always — and **the server refuses it too** (`RefusalLine`). B14 rule 5 (two sizes) and rule 6
(destructive commits danger-tier) hold on every frame.

## What the staff kit does not have yet — four things

1. **`FieldSlot` with the three field kinds** (`redirect`, `issued_secret`, `mapping_editor`) — the modal is one component only if these are declared kinds, not branches (`BR-INT-043`).
2. **`CountTile` that renders a dash** where a number would be a claim (`51.2`, `82.2`) — the staff KPI tile has never shown an honest absence.
3. **`StateWord`** — a state as a coloured word with a mono meta, rather than a pill; seven words, one map from state to button.
4. **`AccessLog` with an unusual-row emphasis** and an `AmberBox` beneath — the closest thing to a security screen in the design.

Everything else is composition. Four files under `features/integrations/`, four lines in `route-b-migrated.txt`,
no class in any stylesheet.
