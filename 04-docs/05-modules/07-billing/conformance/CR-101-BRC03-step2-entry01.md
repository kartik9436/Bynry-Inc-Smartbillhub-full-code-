# Billing §02 entry 01 · All bills — THE STEP-2 BUILD RECORD

`CR-101-BRC03` lane 01 · built 2026-09-14 · branch `claude/eager-johnson-r0k88b` ·
from `v2.261.4` to **`v2.262.0`**

**Scope: ONE screen.** `/:tenant/billing`, second address `/:tenant/billing/all`,
`S30` · `BIL-01`, plus the Print bills screen it now tabs to. Step 1 measured entry 01 at
**40 drawn elements — 28 match · 6 differ · 5 absent · 1 not judged**, with 5 present-and-not-drawn
(`conformance/CR-100-BRC03-diff-02.md`).

## Where the drawing came from

`05-prototype/04 Billing, As Built.pdf` on the DEFAULT branch
`claude/confirm-understanding-3ktufc`, extracted with `git show` and hashed:
`sha256 137a2a48c0398c39897f49aafa0bbb9c44ff21d6258eed78cd7558e6cc200971`, 14,363,163 bytes.
Pages 5–12 rendered with `10-scripts/pdf/pdf_render.py` at scale 2 and **read as images**
(B14 rule 42), plus four crops at 4×–8× for the tab strip, the header band, the column row and
the disclosure summary. The entry carries `TWO REVISIONS`; **the REDESIGN on p007 is what was
built** — the as-built half is a collapsed disclosure the PDF renders closed and is marked
*do not build this*.

⚠ **One internal contradiction in the document, resolved by a dated ruling rather than by
preference.** The drawing renders the tab strip **seven** wide with `Print bills` last. Its own
carry-over table on p008 says *"The six-tab strip · UNCHANGED · Untouched"*, and the remedy
arithmetic names four new elements — cycle chip, date-range chip, Printed column, row overflow —
**and not the tab**. The tab was built anyway, because `12-governance/02-decision-log.md` records
it as ruling #10 of the fifteen of 2026-09-12, verbatim: *"We will need Print bills as tab at
Billing level"*, with *collides with a signed rule?* → **No**. A ruling outranks a carry-over table.

## What was built — measured in Chromium at 1440 on `brazosbend`, 92 invoices behind it

| # | Drawn | Before | After |
|---|---|---|---|
| 1 | Tab **`Print bills`**, seventh | strip 6 wide; the screen reachable only from a header button; the Print bills page carried **no tab strip at all** | strip **7** wide; clicking the seventh tab lands `/brazosbend/billing/print`, `h1` *Print bills*, strip still 7 with `Print bills` selected; clicking `All bills` from there returns to `/brazosbend/billing` |
| 6/7 | The roll-up, and `Unresolved … 3 →` as a door | `/billing` read `Bills lifetime 92 · Out this cycle Not counted yet · Unresolved 0`; **`/billing/fix` and `/billing/history` read `Not counted yet` three times** | all three tabs read `Bills lifetime 92 · Out this cycle Not counted yet · Unresolved from the last run 0 →`, and the third is an `<a href="/brazosbend/billing/pending">` |
| 9 | **ⓘ** on the `STATUS` header | absent | present — an `InfoIcon` with accessible name *"Why no bill is marked past due"*, rendered **only while** the disclosure below is rendered |
| 10 | `TOTAL` header right-aligned over the money | header content ended **47px** from the cell's right edge against **12px** for `$71.50`; `getComputedStyle(th).textAlign` = `left` | **12px against 12px**, `textAlign` = `right` — flush |
| 11 | The past-due explainer as a **closed `<details>` below the table** | **45 words of open prose above the table**, on every visit | a `<details>` **closed** by default below the pager, summary *"Why no bill is marked past due"* character-for-character as drawn, the same 45 words inside, unchanged |

Also corrected, not drawn: three comments that justified the absent tab and the column chooser.
Two said *"the Billing strip has six labels G14 checks against the prototype"* — **G14 reads no
billing tab label at all**; `grep billing.tab 10-scripts/gates/` returns nothing. The file header
said the column chooser *"needs US-SHL-013's preference service, which is not wired"*; it is wired
and the chooser uses it, which the step-1 diff had already measured and asked a step-2 lane to fix.

## What was NOT built, and why

| # | Drawn | Why not |
|---|---|---|
| 2, 3 | Filter chips `Cycle 09-A ×` and `Issued 09/01–09/30 ×` | A cycle lookup a Billing Clerk may read, and a **date-range control the shared `FilterBar` does not have** — it renders option lists only. A new kit control is its own work with its own proof and changes every list at once; doing it inside a screen commit is the side-effect migration the process forbids. |
| 4 | Column `PRINTED`, three values | **Backend.** No served field: the row carries no print state. The drawing's own legend calls it *"the largest of the eight"*. |
| 5 | Third row action — a `…` overflow carrying *Fix this bill* | The overflow component does not exist. UI-RULES 15 is *max 2 visible + overflow*, so the product is **lawful today at two** and the drawing adds the third; building the overflow is a kit addition every table inherits. |
| 6 | `Out this cycle $342,180.00` | **Backend, and already filed as `DEF-BIL-5236`.** `selectors.invoices_rollup()` returns `billed_this_cycle=None` hardcoded. This lane fixed the *client* half — the header now asks on every tab — and reworded the sentence, which no longer claims the server has not counted. The figure itself needs `apps/billing/selectors.py`, another lane's file on a money path. |
| 8 | Download glyph **enabled** | **Backend.** There is no `apps/billing/exports.py`, so no `bills` resource exists to ask for. The code's own stated reason is still true. |
| 12 | *"A draft sorts to the top"* | **Still NOT JUDGED.** This tenant holds 91 `issued` + 1 `corrected` and **zero drafts**, so the null-issue-date branch still never renders. Creating one would have changed a shared fixture four lanes are measuring against mid-session; it is left for a lane that owns the seed. |
| 13–17 | The five present-and-not-drawn treatments | **Left alone, on the document's own instruction.** The carry-over marks the three header actions `UNCHANGED ×3`, the search box / status segment / `+ Filter` `UNCHANGED ×3`, and the two action icons `UNCHANGED`. The wireframe's flat rendering of a filled primary button is an illustration (B14 rule 37), not a demotion. |

## The kit changed, and the blast radius is 120 headers

`.cell-num` is specificity **(0,1,0)** and `.data-table th { text-align: left }` is **(0,1,1)**, so
the generic header rule won and **every numeric column in the product** shipped a left-aligned
header over right-aligned figures. `.settings-table th.cell-num` in `SettingsPage.css` already
carried the identical fix for its own table, which is the tell that the kit rule was the wrong one.
`.data-table th.cell-num { text-align: right }` now sits beside it. **`grep -c "numeric: true"`
across `07-frontend/src` = 120 column declarations**; each gets its header over its figures.
The generic `text-align: left` stays — it is what holds every text column where it belongs.

Two additive kit pieces, both optional so no existing screen moves: `InfoIcon` in
`components/icons.tsx`, and `headerNote?: string` on `TableColumnConfig`.

## Guards, and the false pass they were written around

Eleven cases across `CR101Entry01.dom.test.tsx` (jsdom) and `CR101Entry01.test.tsx` (node, for the
stylesheet rule jsdom cannot resolve). **All eleven were proved RED on 2026-09-14 at tip
`7dcf65c3` before any code was written**; the run is kept at `lane01/RED-PROOF-2026-09-14.txt`.

⚠ **The obvious test for the roll-up defect passes on the broken code.** Seeding the query cache
and asserting the number renders proves nothing: `useQuery({ enabled: false })` still returns
whatever the cache holds. The guard therefore seeds nothing and uses a **recording client**,
asserting separately that `GET /invoices` went out while the Fix-a-bill tab was mounted and that
the served figure reached the screen. A first draft of that test also went red for the wrong
reason — the Fix tab crashes on a bare list envelope and a crashed tree renders an empty body,
which reads exactly like a header that did not render; the stub answers `/corrections/reasons`
properly so the only thing the file can fail on is the header.

Two existing assertions were **amended rather than loosened**, each with the ruling quoted inline:
`BillsPage.test.tsx`'s six-tab list (now seven) and its assertion on the old tooltip wording.

## Reds, each with the date it was proved

The billing + components suites were run **at the pinned tip `7dcf65c3` in a private worktree**,
which is the only way to answer *was this red before I started*.

| Red | Verdict |
|---|---|
| `US-BIL-025 TC-2 · search and the status segments are URL state` | **PRE-EXISTING at `7dcf65c3`, proved 2026-09-14.** Stale since 2026-09-09, when `address` joined `searchFields`. Filed as **`DEF-BIL-5242`** and deliberately NOT fixed here — a one-line stale expectation in another wave's scope, and correcting it inside a commit about the Print bills tab is the silent fix the process forbids |
| `WizardFrame · TC-FRAME-5 · single-flight` | **PRE-EXISTING at `7dcf65c3`, proved 2026-09-14.** Not billing |
| `DEF-SHL-3964 · the shell reads all three fields` | **PRE-EXISTING at `7dcf65c3`, proved 2026-09-14.** Not billing |
| `BillDetailPage` / `CR053BillSurface` — six cases, and `tsc: Cannot find name 'SentTab'` | **A SIBLING'S UNCOMMITTED WORK, not a branch red.** `SentTab` appears in no commit (`git log -S` finds nothing) and not at the tip; the working tree holds +352/−110 in `BillDetailPage.tsx`. That is entry 02.5's lane mid-build. Not touched |
| `US-BIL-025 §1 · six tabs` and `… zero would be a claim` | **MINE, caused by this build, and both amended** — see above |

## Two things worth the next lane's attention

**A sibling's commit `b6fe8821` published this lane's five catalogue keys.** They are live and
correct in all eleven catalogues, so nothing is lost, but they are attributed to another lane's
commit. That is CLAUDE.md law 11 mechanism five and is **already filed as `DEF-BIL-5241`** by the
lane that caused it. The consequence here: this lane could not push the eleven catalogue files at
all, because by then the working tree's copies also held a *third* lane's in-flight
`billing.run.*` edits, and pushing them would have published that lane's unfinished work.
`push_paths.sh` refused first — the guard working.

**The closed-`<details>` stated absence is now its THIRD hand-written copy** —
`billRunShared.RunGap`, `SettingsBillingPlanTab.AbsenceDetails`, and this one. It is a kit
candidate. Not promoted here: a kit component is its own work with its own proof, and the drawing
wants the plain treatment rather than either of those two boxes.

## Walked

Chromium at **1440 and 1280**, against the running stack, signed in as
`dana@brazosbendutilities.com` on `brazosbend`. No page errors and no horizontal scroll at either
width. The seventh tab was **clicked**, not merely rendered, and the way back out was clicked too.
Screenshots: `step2-shots/list-allbills.png`, `list-allbills-headerband.png`,
`list-allbills-foot-closed.png`, `list-allbills-foot-open.png`, `list-printbills-tab.png`,
`list-fixtab-header.png`, and the `-1280` pair of each.
