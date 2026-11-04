# CR-093-BRC01 · The shared-component findings the Assets pass could not make

**FIVE, not four — and the count is the first finding of this CR.** Both the ruling
and `CR-092-BRC01` §1 say *four*; the register holds five rows of the same kind. §3.5
is the one that fell out of the enumeration, and §1.1 says how.

**Raised:** 2026-09-12 · **Branch block:** `BRC01` (`CR-090`–`094`) · **Status:** OPEN, sized, not started
**Raised by:** the Assets blueprint pass (`CR-092-BRC01`), by PO ruling 7 of 2026-09-12.

**PO verbatim, 2026-09-12, answering *"Four of the findings are in the shared table
— fix them here, or give them their own change request?"*:** ***"(b). It's the right
fix and it touches 54 lists at once. That risk doesn't belong inside an Assets
pass"*** — their own change request, sized on its own.

**Why it was ruled that way, in the CR that raised it:** *"four rows reaching 54
lists is not a risk to take inside an Assets pass. A lane meeting one states the
change and does not make it."*

---

## 1 · CLASSIFY — and all five are DEFECTS, not changes

`13-change-process.md` step 1 says that when intake is ambiguous the item is a
**defect**, because filing our own miss as a "change" converts our error into the
customer's new requirement. None of these five is ambiguous:

**Every one of them is a live screen disagreeing with a UI rule the PO already
ratified.** Nothing here asks for new behaviour, and no signed statement is being
reversed — which is why §2 below is empty rather than long.

So by the maintenance process's one question — ***can a user do this task in the
product today?*** — the answer is **yes** for all five (they sort lists, they read
page heads, they use row actions, they look at KPI strips every day), and the track
is **MAINTENANCE**, not build.

⚠ **THIS CR IS THEREFORE AN INTAKE AND A SIZING, NOT A BUILD PLAN.** What it carries
is the PO's ruling, the measured blast radius and the sequencing. **The work itself
runs through `12-governance/22-product-maintenance-process.md`** — reproduce,
locate, blast radius, minimal fix, proof in a browser, regression walk of the
neighbours, version, rollback, and a close that tells the reporter which build to
look in.

### 1.1 · WHY THIS CR SAYS FIVE WHERE THE RULING SAYS FOUR

**Nothing was added to the PO's scope. A row was double-counted out of it.**

| # | the finding | the Assets pass filed | already open since |
|---|---|---|---|
| 1 | the sort's third click never clears | `DEF-SHL-4946` | (`DEF-MET-4957`, dup) |
| 2 | two page-title sizes | `DEF-SHL-4947` | — |
| 3 | rule 15's row-action cap | `DEF-SHL-4948` | **`DEF-2453`, 2026-08-30** |
| 4 | the KPI strip's gap | `DEF-SHL-4949` | — |
| 5 | the pager has no first/last and no *Page N of M* | `DEF-MET-4958` (dup) | **`DEF-449`, 2026-08-21** |

**Ruling 7's own sentence names four — *the sort's missing third click, first/last
page, the two title sizes, the KPI gap* — and then adds that *"two of the four were
already filed weeks ago (2026-08-21 and 2026-08-30)"*. Those two dates are rows 5 and
3. So the ruling was counting the row-action cap and the sentence was not.**

**Row 3 is the one that slips**, and the reason is worth keeping: it has an
Assets-specific twin — `DEF-MET-4956`, *six row-action controls in one cell* on the
registry — so one pass read it as an Assets finding and the other as a shared one. It
is both: the registry cell is the worst instance of a rule breach in fourteen files.

⚠ **THE PO IS NOT BEING RE-ASKED (law 13).** The ruling was *"(b)"* on the
shared-component findings **as a class**, with the reason given as the blast radius —
*"it touches 54 lists at once"*. A fifth row of exactly that kind is inside the
ruling, not outside it. **What would need re-asking is a row that is NOT of that
kind, and there is none.**

---

## 2 · WHAT SIGNED STATEMENT IS BEING REVERSED

**None.** No B4/B5 frozen figure is touched, no money path, no rule is superseded.
Four of the five *restore* a ratified rule that the code never matched; the fourth
(`DEF-SHL-4947`) makes the component match a token sheet that already describes the
intended default.

---

## 3 · THE FIVE, RE-MEASURED AT HEAD TODAY

⚠ **These figures were re-measured on 2026-09-12 at `672f2f515`, not copied from the
rows.** The rows were written on 2026-09-11 by step 1 lane 6; where a figure has
moved it is called out, because a description is not a measurement and this CR is
what the maintenance lanes will size from.

### 3.1 `DEF-SHL-4946` — the sort's third click does not exist

**B14 rule 13:** *"Headers show the sort glyph; click cycles asc, then desc, then
CLEAR."*

`components/DataTable.tsx` `nextSortState` has exactly two branches — same column
flips the direction, a different column starts at `asc` — and **no branch returns
the list to the server's default order.** A clerk who sorts a column cannot undo it
without reloading the page.

**Blast radius: 54 non-test files mount `<DataTable>`.** That is every list in the
product.

⚠ **It was found once before and recorded where nobody reads it.** `DEF-211`'s
closure text of 2026-08-18 names it exactly — *"rule 13's THIRD click
(`nextSortState` toggles asc/desc and never clears)"* — as one of three remainders,
and `DEF-211` was then **closed**. `defect_report.py` counts open rows, so a
remainder written into a closed row is invisible. **A leftover recorded inside a
closed row is not recorded.**

### 3.2 `DEF-SHL-4947` — two page-title sizes, and the token sheet describes a default the component does not have

`styles/tokens.css` line 203 reads `--text-h2: 32px; /* page-head title — THE APP
DEFAULT, every screen head */`, and line 202 reserves `--text-h1: 40px` for a
full-page wizard title.

But `PageHeader.tsx` renders a **bare `<h1>`** unless a caller passes `titleAs="h2"`,
and `global.css` line 58 sizes a bare `h1` at `var(--text-h1)` — 40px. Nothing
overrides it for a page head.

**Measured at HEAD: 137 non-test files mount `<PageHeader>`, and `titleAs="h2"`
appears exactly ONCE in non-test source** (`features/notifications/TemplateDetail.tsx`).
**So 136 screen heads render at the wizard size while the token sheet calls 32px the
app default.**

### 3.3 `DEF-SHL-4948` — sixteen row-action cells exceed rule 15's cap

**B14 rule 15:** *"Row actions are ICONS with tooltips, never text links. Max 2
visible + `…` overflow."*

⚠ **THE ROW'S FIGURE IS SUPERSEDED BY THIS ONE.** `DEF-SHL-4948` reads *"63
`RowActions` blocks, of which 14 declare more than two actions and no overflow, in 14
files"*. Re-measured at HEAD, counting `<RowActionLink>` as an action alongside
`<RowAction>` — it is a control in the same cell and the cap is about what a clerk
sees:

**68 `RowActions` blocks in non-test source · 16 of them declare more than two with
no overflow · in 14 files.** The file count is unchanged at 14; the block count is 16
rather than 14 because **two files declare two over-cap cells each**
(`features/ledger/CostOfServicePage.tsx` and `features/billing/BudgetBillsTab.tsx`),
and one more has appeared since the row was written
(`features/runbooks/work/WorkList.tsx`).

| actions | file |
|---|---|
| **6** | `features/assets/AssetRegistryPage.tsx:663` |
| 4 | `features/metering/PremisesListPage.tsx:542` |
| 4 | `features/payments/RefundsPage.tsx:472` |
| 4 | `features/rating/PlansTab.tsx:512` |
| 4 | `features/tenancy/SettingsReferenceData.tsx:931` |
| 3 | `features/billing/BudgetBillsTab.tsx:417` and `:420` |
| 3 | `features/ledger/ChartOfAccountsPanel.tsx:241` |
| 3 | `features/ledger/CostOfServicePage.tsx:941` and `:945` |
| 3 | `features/notifications/TemplateDetail.tsx:3109` |
| 3 | `features/payments/WriteOffQueuePage.tsx:249` |
| 3 | `features/rating/ChargeCodesTab.tsx:350` |
| 3 | `features/runbooks/work/WorkList.tsx:195` |
| 3 | `features/tenancy/SettingsCustomFields.tsx:395` |
| 3 | `features/tenancy/SettingsRoutesCyclesTab.tsx:450` |

⚠ **DECLARED IS NOT RENDERED, AND THE DIFFERENCE IS THE LANE'S FIRST JOB.** Several
of these cells wrap actions in conditionals, so the number a clerk actually sees can
be lower than the number declared — `CostOfServicePage`'s two cells are one logical
column rendered two ways by status. **Count what renders, per status, in a browser,
before changing anything**; a cell that declares four and can only ever show two is
not over the cap.

**The overflow component exists.** `RowActionsMore` is built and used in three
places, so this is a conversion rather than a build. `DEF-2453` carries the same
finding and is still open, and **its own text is now half stale** — it says *"no such
component exists"*, written before `RowActionsMore` landed. Close the two together.

### 3.4 `DEF-SHL-4949` — the KPI strip's gap is 6px where the ratified anchor is 8

`components/KPIStrip.css` line 18 sets `gap: 6px`. B14 rule 39's anchor first read
*"KPI 16/20 gap 6"* and was amended hours later on the PO's own words — *"One
off-scale value invites the next one. 8 is the nearest step and nobody will see
2px"* — so the ratified anchor is **16/20 gap 8**, and 6 is not a step of the scale
the same rule ratifies (4, 8, 12, 16, 20, 24, 32).

**One declaration. 33 non-test files mount `<KPIStrip>`.** The strip's padding is
already correct. **This is a two-character change and it is the whole fix** — which
is exactly why it must not be bundled with the other three: it needs no design
decision and should not wait on one.

### 3.5 `DEF-449` / `DEF-MET-4958` — the pager has no first/last jump and never says where you are

**Open since 2026-08-21.** r10's `.pgbar` draws: *Showing 1–7 of 7* · *Rows per page*
· **first-page** and previous-page, then the literal **`Page 1 of 1`**, then next-page
and **last-page**.

`DataTable`'s own pager renders the range, the rows-per-page control and **prev/next
only** — no first/last buttons, and **nothing anywhere that says which page you are
on.**

⚠ **AND THE WORDS FOR IT ALREADY EXIST, IN ALL ELEVEN LANGUAGES.** Measured at HEAD:
`table.pager.pageOf` = *"Page {{page}} of {{pages}}"* is present in **every one of the
eleven catalogues** — `Seite {{page}} von {{pages}}`, `{{pages}}ページ中{{page}}ページ`,
and so on — and it **is** rendered, by `components/ListPager.tsx`, which **9 non-test
files** mount. `DataTable`'s inline pager, which **54** files mount, does not use it.

**So the two pagers in this product disagree, and the smaller one is the correct
one.** That makes this the cheapest of the five to fix well: no new copy, no
translation round, no design decision — one span and two buttons, borrowed from a
component already in the tree.

⚠ **`DEF-MET-4958` IS MARKED `duplicate` AND ITS TEXT IS THE BETTER OF THE TWO** — it
counts *four* missing clauses where `DEF-449` names three. Close them together and
keep the newer text.

---

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

**Nothing is mid-flight on these five.** `CR-092-BRC01`'s wave B lanes were briefed
with the boundary in their own words — *a lane meeting one of these states the change
and does not make it* — and none of them touched `DataTable.tsx`, `PageHeader.tsx`,
`RowActions.tsx`, `ListPager.tsx` or `KPIStrip.css`.

⚠ **ONE OVERLAP TO SEQUENCE, AND IT IS 3.3's WORST OFFENDER.** The six-action cell in
`AssetRegistryPage.tsx:663` is the top row of the table above **and** is inside the
file `CR-092-BRC01` wave B lane 1 is editing right now. **This CR's row-action work
starts after that lane lands**, or the two collide on one file — law 11's mechanism
two, which reverts by subtraction and passes every check.

---

## 5 · SIZE IT, IN PLAIN ENGLISH

Five separate pieces of work, and **they are not one job** — that is the point of the
ruling that separated them:

| # | the fix | size | what makes it big or small |
|---|---|---|---|
| **1** | **The KPI gap** — 6px becomes 8px | **minutes** | one declaration, no decision to take, nothing to design |
| **2** | **The pager** — first/last buttons and *Page N of M* | **small, and cheaper than it looks** | the copy exists in all eleven languages and `ListPager` already renders it. Borrowing from a sibling component, not authoring |
| **3** | **The sort's third click** — a third branch that clears | **small change, wide reach** | ~10 lines in one function, then a walk of what 54 lists do when the sort clears. **The server's default order has to exist and be stable**, or "clear" means "some order" — see §6 |
| **4** | ~~**The page-title size**~~ — **DONE, 2026-09-12** | **was: small change, WIDEST reach** | ✅ **RULED AND SHIPPED.** Shown to the PO as a rendered picture of the two sizes side by side; ruled ***"use 32 pixels — for every ordinary screen"***, confirmed ***"Please use 32 pixels"***. Now **B14 rule 40**. The one line was the easy half — see §9 |
| **5** | **The row-action cap** — 16 cells behind `RowActionsMore` | **the real work** | 14 files, each needing a judgment about WHICH two actions stay visible. Per file, not in bulk |

~~**The one that needs the PO's eye is #4**~~ — **it got it, and the answer was yes.**
The other four are ours to decide and record.

**Recommended order: 1, 2, 3, ~~4~~, 5** — cheapest and safest first. **#5 is last for a
reason that is not cost:** it waits on `CR-092-BRC01` wave B lane 1 releasing
`AssetRegistryPage.tsx`.

---

## 6 · OPEN — WHAT THIS CR CANNOT ANSWER ITSELF

**One question, and it belongs to fix #2.** B14 rule 13 says the third click CLEARS.
**Clear to WHAT?** The rule does not say, and neither does `DataTable`. Two readings:
the server's default order for that list, or no `sort` parameter at all and whatever
the endpoint does then. **These are the same thing only if every list endpoint has a
deterministic default order**, which is unproved — `nextSortState`'s own comment says
ties break by a stable secondary sort by id on the server, which is a promise about
TIES and not about the unsorted case.

**A lane takes this to the boundary and stops** (prime directive): measure whether the
list endpoints have a stable default order, and if they do not, that is what reaches
the PO — not a choice made inside a UI fix.

---

## 7 · VERSION

**Not yet cut.** Each of the five fixes carries its own `<release>.<change>.<fix>`
bump when it lands, per `13-change-process.md` step 7. Nothing in this CR ships as
one version, because nothing in it ships as one change.

---

## 8 · ROLLBACK, STATED BEFORE SHIPPING

| fix | rollback |
|---|---|
| KPI gap | revert one declaration |
| pager | revert; the buttons and the position span are additive |
| sort's third click | revert `nextSortState`; the clear branch is additive, so nothing else changes shape |
| page-title size | revert the one line in `PageHeader.tsx` — every screen returns to 40px together |
| row-action cap | per file, independently; no file depends on another |

**All five are revertible file by file, and none writes data.** That is the strongest
thing that can be said about this CR's risk, and it is why the sizing above is about
how many screens change at once rather than about what could be lost.


---

## 9 · ITEM 4 IS CLOSED — WHAT IT ACTUALLY COST, WHICH WAS NOT THE ONE LINE

**Shipped 2026-09-12 as B14 rule 40.** `DEF-SHL-4947` closed. The full account is
in `12-governance/02-decision-log.md`; the three things a future reader of THIS
CR needs are below, because each one changes how items 1, 2, 3 and 5 should be
sized.

### 9.1 · §3.2's premise was wrong in the PO's favour, and they caught it

This CR said the component *"does not have"* a default the token sheet
*"describes"*. The PO's reply was ***"if that is our rule"*** — and the honest
answer was **no, it was not a rule at all**. B14 held no ratified rule about
title size: only a **comment beside a token** in `tokens.css`, asserting an app
default that nothing in the product made true, for three weeks. **Hard-won law 1,
exactly.** The PO's instruction is what ratified it.

⚠ **THE OTHER FOUR ITEMS SHOULD BE RE-READ FOR THE SAME FAULT.** Each cites a
rule as though it were settled. Rules 13, 15 and 39 genuinely are ratified — that
was checked — but *"the token sheet says"* is not the same kind of claim as
*"B14 rule N says"*, and this CR made them look alike once.

### 9.2 · The one-line estimate was right and the sizing was wrong

The fix is one line. **Landing it changed 18 assertions across 12 test files**,
because they matched the literal string `"<h1>"` and the title now carries a
class. One of them — `expect(html).not.toContain("<h1>")` — was made
**structurally incapable of failing** by a change three modules away, which is
the failure shape this repo files more of than any other.

**So for items 1, 2, 3 and 5, size the TEST surface, not the change.** A grep for
the markup each one touches, before starting, is the whole cost.

### 9.3 · The measurement has to read the built stylesheet

`10-scripts/render-checks/cr093-page-title-size.mjs` reads `getComputedStyle`
against `dist/` at 1280 and 1440, and carries a `--before` mode that renders the
pre-rule markup and must fail. **A class-name assertion cannot do this job**: a
Tailwind utility in a file absent from `route-b-migrated.txt` is in the DOM and
styles nothing, with every check green (the UI skill's §7.1). **Items 1, 2 and 5
all change rendered output and all need a probe of this shape**, not a
`toContain`.

⚠ **AND MEASURE IT IN A PRIVATE `git worktree`.** The shared tree held three
lanes' uncommitted work — including a file importing a module not yet on disk —
so `tsc` and the suite were unmeasurable in it. Both baselines for item 4 were
taken in worktrees at the tip, one clean and one carrying only this change. That
is law 12's recovery technique used as a measuring instrument, and on a busy day
it is the only way to get a number that is yours.
