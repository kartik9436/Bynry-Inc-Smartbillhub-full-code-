# Plans list — built screen beside images 01–03 (CR-167-BRC10 round 2 task 6)

Build **2.484.0** (the list screen is 2.483.0; 2.484.0 adds the server fields it reads), PostgreSQL 16 (`sbh_planlist`: `migrate` + `seed_demo` + `load_sample_data --tenant brazosbend`),
API `runserver 127.0.0.1:8171`, SPA `vite build --mode wolocal` served on `5271`, Chromium at 1440 × 900, signed in as Dana
(System Admin). Re-run: `BASE=http://127.0.0.1:5271 OUT=08-qa/plans-2026-10-03/list node 10-scripts/cr167_plans_list_after_walk.mjs`.
Its printed output is `walk-output.txt`. Every photograph below was opened and is not blank.

| Built | Drawing | State |
|---|---|---|
| `01-list-all.png` | `05-prototype/plans-2026-10-03/images/01-list-all.png` | all plans |
| `02-list-search.png` | `images/02-list-search.png` | searched "water" |
| `03-list-no-results.png` | `images/03-list-no-results.png` | a search with no match (`zzz`) |
| `lang-de.png`, `lang-ja-JP.png`, `lang-ko-KR.png` | — | the list in three of the eleven languages |

## Same as the drawing

- Header, roll-up line, *History* and *+ New plan*, the five tabs, no paragraph above the table.
- Toolbar: *Search plan name or code* · *All* · *+ Filter ▾* · download · columns.
- Columns in the drawn order: **Plan · Version · Services · Schedules · Base charges · Units · From · To · Status** and one
  action per row.
- Plan cell: the name (a link to the plan) with `CODE · Class` under it (`SCW-COM · Commercial`; a plan for every class reads
  `Every customer class`). No database id anywhere (checked by the walk).
- Version is a grey `V1` tag; Schedules and Units are counts, right-aligned; From is a date; To reads *No end* when open.
- A draft row reads *Draft* (the walk writes *Rural Draft* through `POST /plans`, as image 01 draws one).
- The searched states go to the server (`q=water` in the address and the request).
- The sorts are the server's: Units descending reads 75 · 7 · 2 · 2 · 1 · 1 · 0 from the API and on screen.

## Different, and why

| # | Difference | Why |
|---|---|---|
| 1 | The app frame (sidebar, top bar, build number, screen badge) surrounds the page | The drawing is the page alone; the frame is the product's (B14 rule 44). |
| 2 | The row action is the kit's eye icon named *Open*, not a `›` box | Our kit decides the component (rule 44); the Taxes & fees and Discounts lists use the same icon. Decision log, *"THE PLANS LIST — FIVE JUDGMENTS"* (4). |
| 3 | Images 02 and 03 keep the table head and print *No plan matches.*; ours shows the kit's *No results for 'water'.* with *Clear filters* and no table | Every list in the product answers a no-match the same way (the Discounts and Taxes lists, CR-166 §12, CR-165). |
| 4 | Image 02's "water" matches nothing in the drawing; here too (no plan name or code holds "water") | Same behaviour: the search reads plan name and code only. |
| 5 | Base charges reads `—` on 5 of 7 plans; the drawing shows a figure on every row | The server cannot state one monthly figure for them and says why (`BR-RAT-1040`): three plans name every class while the codes are priced per class, one prices electric by size, one has no industrial water base. A dash, never `$0.00`. Figures in a drawing are illustrations (rule 37). |
| 6 | The pager shows *Rows per page* and ‹ › beside *1–7 of 7* | The kit's pager (NFR-3: the list is server-paged). |
| 7 | Plan names and figures differ | The sample tenant's own data; a drawn figure is an illustration (rule 37). |
| 8 | In ja-JP the Plan head reads 計画 | The existing translation of `rating.plans.col.plan`; the eleven languages are task 9's (round 3). |

## Width, eleven languages

At 1440 the table is 1,120 px in a 1,120 px box in all eleven languages, the page never scrolls sideways, and no word of
any header, cell, button or tab sits on two lines (measured per word with a Range). The check was proved able to fail:
`FORCE_SQUEEZE=1 LANGS=ja-JP` narrows every cell and it reports `FAIL` with 計画, 戸数, ステータス … split.
