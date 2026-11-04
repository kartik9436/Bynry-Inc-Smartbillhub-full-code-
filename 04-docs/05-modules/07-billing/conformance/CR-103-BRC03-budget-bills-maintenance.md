# Budget Bills (§05, entries 25–25.4) — MAINTENANCE record

**Track: MAINTENANCE, not Build.** `12-governance/22-product-maintenance-process.md`'s
one question — *can a user do this task in the product today?* — answers **yes**: a
clerk can open `Billing › Budget Bills`, look an account up, read its computed level
and put it on budget billing, one at a time. This is the redesign case the process
names by name (*"a live screen redrawn end to end is MAINTENANCE"*), so it borrows
exactly one thing from Build — the drawing step — and keeps reproduce, locate, blast
radius, regression, version and the reporter's build number.

| | |
|---|---|
| Id | **`CR-103-BRC03`** — block `CR-100`–`CR-104`, suffix `BRC03`, claimed for this branch in `12-governance/14-id-reservations.md` before use. ⚠ **This record was first written as `CR-102-BRC01` and both halves were wrong:** `BRC01` is `claude/hi-0jmv62`'s suffix, so it would have attributed this work to a branch that did not do it; and `102` was already TAKEN by a sibling — `allocate.py cr --verify 102` answers *"TAKEN — a sibling pushed it"*. **The suffix is provenance and it is not what makes a number unique** (`CLAUDE.md`, Screen IDs): two branches can both write `CR-102` with different suffixes, git merges the two files cleanly because they are different files, and nothing goes red until `G17` fails the duplicate NUMBER at merge. `103` was re-verified against the REMOTE at push time. |
| Branch | `claude/eager-johnson-r0k88b` |
| Drawing | `05-prototype/04 Billing, As Built.pdf` on the DEFAULT branch · 14,363,163 bytes · sha256 `137a2a48…c200971` — **verified, not assumed** |
| Pages read AS IMAGES (B14 rule 42) | **p117–p130 at scale 2; p121, p122, p123 again at scale 4** |
| Product read at | **`v2.263.0`**, on screen |
| Walked | 1440 and 1280, in Chromium, against a booted stack |

---

## 0 · WHAT THE DRAWING ACTUALLY SAYS — verified from the pages, not from a briefing

**§05 spans p118 – p128.** p129 opens §06 *Fix a bill*, so the index's *"p129(top)"* is
the boundary and not a §05 page. **Five entries, and the section's own front matter
counts them: *"these five screens are what it needs — four for staff and one for the
customer."***

| Entry | Title | Pages (verified) | Chips, read off the page |
|---|---|---|---|
| 25 | Budget bills | p121(mid) – p122(top) | `THE LEVEL, THREE WAYS` · **Blocked `S75`** · New build `S80 S81 S82` · New read `S74` · Exists behind `S58 S59 S67` |
| 25.1 | Enrol | p122(mid) – p124(top) | `ONE AT A TIME` · **Blocked `S75`** · New build `S80 S82` · New read `S74` · Exists behind `S58 S59 S67` |
| 25.2 | Settle-up forecast | p124(low) – p126(top) | `READ ONLY` · New build `S80` · Exists behind `S60` |
| 25.3 | Asks | p126(mid) – p127(mid) | `THE CUSTOMER ASKS, A CLERK ENROLS` · Exists behind `S66 S67` |
| 25.4 | Portal · Level pay | p127(mid) – p128(end) | `THE CUSTOMER'S SIDE` · Exists behind `S66` |

**Every entry carries the identical caption: `REDESIGN` drawn 2026-09-12, NEVER BUILT.
No entry carries a `BUILD THIS` band and none carries a screen id.**

### Three differences from the briefing, reported as findings

1. **THE `Blocked` MARKER IS ON TWO ENTRIES, NOT ONE.** The briefing flagged it on
   25.1. **Entry 25 carries `Blocked S75` too**, on the same commitment.
2. **`S75` IS THE BULK ENROL, NOT THE ENROLMENT.** `S75` = *"A clerk can enrol every
   eligible account at once"*, blocked on `OQ-237`. So the blocked boundary is the
   BULK path; one-at-a-time enrolment is explicitly outside it — `OQ-237`'s own scope
   line says *"The ELIGIBILITY SOURCE and bulk enrolment only. One-at-a-time
   enrolment, the computed level, re-levelling, the override and removal all ship."*
3. **§05 HAS NO CARRY-OVER MAP.** Counted over the extracted text of p118–p128:
   `UNCHANGED` 0 · `RELABELLED` 0 · `REMOVED` 0 · `MOVED` 0 · `Carry-over` 0. The
   document's carry-over tables are on p1, p2, p6, p8, p17, p203, p230, p238, p241 and
   its dispositions on p8, p11, p12, p23, **p87, p88**, p202, p230, p237, p238, p241,
   p242 — the bulk run's, not this section's. **What §05 has instead is p121's
   `THE CONTROL / WHY NOT` table, which is removals only** (three rows, and its own
   heading says *"Two prototype controls"* over three), plus p118's red band recording
   25.2's withdrawn `Settle these 2` button. There is no arithmetic to reconcile
   against, so this record supplies the element tie-out itself.

---

## 1 · REPRODUCE — driven before a line moved

`10-scripts/`-style walkthrough in the scratchpad; stack booted on a private port pair
so no sibling lane's server moved. Tenant `brazosbend`, signed in as Dana Whitfield.

**What the screen did, at `v2.263.0`:**

| | |
|---|---|
| `h1` | **`Billing`** — the drawing's title is `Budget Bills` |
| Section headings | `Put a customer on budget billing` · `On budget billing` · `Three things this screen does not do` |
| Table | **none** — *"Nobody is on budget billing."* |
| Filter | a two-button segment, `On budget billing` / `Taken off` |
| Search · filter chips · column chooser · pagination footer | **absent, all four** |
| Account field | a free-text box, placeholder *"Paste the account's id from its detail page"* |
| Eligibility read | works, and refuses honestly: *"0 month(s) of issued bills; this utility averages over 12."* |
| Commit button | `Put them on budget billing`, disabled |

**⛔ AND THE ENROLMENT ITSELF COULD NOT BE REPRODUCED, WHICH IS THE LARGEST FINDING IN
THIS PASS.** `select status, count(*) from invoices group by status` returns **zero
rows — this database holds no invoice at all.** Enrolment needs twelve months of
ISSUED billing history (`eligibility_months`, the tenant's own setting), so
`computed_level` is null for every one of the 72 accounts on the tenant and the commit
button is disabled on all of them **by construction and correctly**. The billing
sample seeder produces **two** cycles, so even a full demo seed does not reach twelve.

**So: the one thing this tab exists to do cannot be demonstrated on any tenant in this
environment.** That is recorded rather than worked around, per the process's *"if you
cannot reproduce it, that is a FINDING"*. The states that WERE driven — the account
lookup, the eligibility refusal, the open-balance line, the empty list, the stated
absences — are what this change is proved against.

**Two live defects seen in the reproduction and filed rather than fixed here:**

* the commit button **overlaps the checkbox label** it sits beside, cutting
  *"…offers budget billing"* mid-sentence at 1440;
* the eligibility block reads **"They already owe $402.15 / across 0 unpaid bill(s)"**.
  The figure is *correct* — it is the migrated opening balance, which has no invoice
  behind it (`customers_seam.opening_position_for_account`) — but the two lines
  together read as a contradiction to a clerk.

---

## 2 · LOCATE

`App.tsx` mounts `/:tenant/billing/:tab`; `BillsListPage.tsx:1200` renders
`<BudgetBillsTab>` when `active === "budget"`. `BillsListPage.tsx:107` is the only
import of the component. The screen id tag rendered on the page is `BIL-01.budget`.

## 3 · BLAST RADIUS — both directions

**Outward — what consumes what this change touches:**

| Consumer | What it uses | Effect |
|---|---|---|
| `BillsListPage.tsx:107,1200` | mounts `BudgetBillsTab` | unchanged — same export, same props |
| `BillingSurfaces.test.tsx:23` | imports **`LevelCell`** | **kept, exported, unchanged** |
| `apps/runbooks/definitions/budget_relevel.py` | reads `account_budget_status.level` | does not call `budget_status_row`; unaffected |
| `apps/portal/seams/billing_seam.py` | `level_pay_position` · `level_pay_standing` · `level_pay_months`, via `budget_service.status_for`, `effective_level`, `budget_history_for`, `compute_level` | **NONE of those is touched.** The customer portal is another module and nothing here writes to it |
| `apps/ledger/chart.py` | the budget-variance designation | unaffected |

**Inward — what is being removed, and who used it:** nothing is removed. The
`PlainTable` markup and the `seg` segmented control are replaced by the shared
`DataTable` and its `Status` filter chip; **both of the segment's two values survive as
filter options**, and grep confirms `billing.budget.filter.enrolled` /
`.off_budget` are still the keys rendering them. No locale key was deleted. No
endpoint, service, refusal or stated absence was deleted.


---

## 4 · THE MINIMAL FIX — what moved, and the tie-out

**Version `2.264.0`. One screen: entry 25, the tab's own table.** Entries 25.1–25.4
are NOT in this change; §5 below says what each is waiting on.

### The element tie-out against p121–p122, read as images

**29 elements were compared by `CR-100-BRC03` step 1 across entries 25 and 25.1: 2
matched, 4 differed, 23 were absent. This change moves 13 of them.** The counts sum:
**13 built + 3 deliberately not built + 13 belong to 25.1 = 29.**

| # | Drawn element | Before | After |
|---|---|---|---|
| 5 | KPI `ENROLLED` | absent | **built** — count, and *"of N accounts"* through the customers seam |
| 6 | KPI `CARRYING A SHORTFALL` + money | absent | **built** — count, and the summed variance with its own `CHAR(3)` |
| 7 | KPI `DUE TO RE-LEVEL` | absent | **built, cadence half only** — see divergence D1 |
| 8 | KPI `ASKS WAITING` | absent | **tile drawn, value withheld with its reason** — `DEF-BIL-5260` |
| 9 | Search box | absent | **built** — *"Search account #, customer or address…"*, three server legs |
| 10 | `Status` filter | a two-button segment | **the toolbar's `Status` chip** — same two values, one filter mechanism |
| 12 | `Re-level due` filter | absent | **built** — `Due now`, on the cadence |
| 13 | `+ Filter` · column chooser | absent | **both built** (kit) |
| 17 | Table col `ACCOUNT` | no table | **built** — number over customer name, absence in words, never the id |
| 18 | Table col `STATUS` | absent | **built** |
| 19–21 | `COMPUTED` · `OVERRIDE` · `THEY PAY` | one column | **three columns** |
| 22 | Table col `ACTUAL TO DATE` | absent | **built** — one grouped query for the page, not one per row |
| 23 | Table col `VARIANCE` | present | **kept** (see divergence D3) |
| 24 | Table col `RE-LEVEL` | absent | **built, month only** — divergence D1 |
| 25 | `Showing 1–50 of N` + pager | absent | **built** — B14 rule 16, `NFR-3` |

**Deliberately NOT built, 3:** the selection column, the `3 selected` bar, and its
three bulk controls (elements 14–16). See §5.

**Reused, unchanged, and this is most of the screen:** all six endpoint calls, the
enrolment write, the eligibility read and its refusals, the open-balance line, the
plan-flag confirmation, `LevelCell`, the three row actions with their icons, disabled
reasons and toasts, every existing locale key, and the *"Three things this screen does
not do"* panel. **Nothing was deleted.**

### Divergences from the drawing, each with its reason

**D1 · `RE-LEVEL` carries a MONTH, not a drift percentage — and the `DUE TO RE-LEVEL`
tile counts cadence, not drift.** The drawing puts *"Drifted 14%"* in the cell and
*"drifted past 10%"* under the tile. `budget.relevel_due` needs **both** gates —
cadence AND a drift breach — and drift is `|recomputed − current| ÷ current`, so every
figure of it costs a fresh twelve-month invoice read **per account**: 50 extra queries
a page, and one per enrolled account for the tile. **Nothing stores a recomputed
level**, so this is a NEW READ and not a rendering. The server carries the reason on
every row (`relevel_drift_unavailable`) rather than leaving the cell blank, and the
tile names the tenant's own cadence. **The drawn `10%` is an illustration anyway
(B14 rule 37) — the tenant's seeded setting is `relevel_drift_pct = 20`.**

**D2 · `from the portal · screen 25.3` is not on screen.** B14 rule 31 keeps an
internal screen reference off a clerk's screen. The tile carries the reason the queue
cannot be counted instead.

**D3 · the `VARIANCE` header keeps the product's existing words, *"Ahead or behind"*.**
The drawing says `VARIANCE`. Both are inside B14 rule 33's 3-word label cap; the
existing wording is plainer for a clerk, is already in all eleven catalogues, and has
no defect behind it. **Changing it is a copy change with no reporter, which step 3 of
the maintenance process forbids.** Recorded rather than done.

**D4 · ⚠⚠ THE DRAWING'S VARIANCE SIGNS ARE THE OPPOSITE OF THE FROZEN ENGINE'S, AND
THIS IS THE ONE TO READ TWICE.** p125 draws `+$212.80 → Collect` and `−$61.40 →
Credit`. ❄️ **B5/WE-8/GT-24 is the other way round**: `variance_movement` is
`level − actual`, so a customer who used MORE than their level drives the balance
NEGATIVE, and `budget.settle_up`'s own words are *"A POSITIVE balance means the levels
collected more than the customer used, so the utility owes them: **CREDIT**. A NEGATIVE
balance means they used more than they paid: **COLLECT**."* **Nothing here flips a
sign.** The engine's convention is finance-signed and frozen; the drawing's figures are
illustrations (B14 rule 37). **A lane that builds screen 25.2's `WILL` column from the
drawing rather than from `budget.settle_up` will tell customers to pay when they are
owed.** Written out here because it is a money path and the inference is not obvious.

**D5 · the bulk bar's sentence would have been rationale on screen.** The drawing puts
*"Enrolling in bulk is not offered — eligibility rides a plan flag nothing publishes"*
(14 words) beside the greyed controls. B14 rule 33 makes RATIONALE **zero words on
screen**. Moot for now — the controls are not built (§5) — and the existing *"Three
things this screen does not do"* panel already carries the fact. **⚠ AND IT IS A REAL
CONTRADICTION FOR WHOEVER BUILDS THEM: the drawing says grey-with-a-reason, the PO
ruled on 2026-08-27 that unbuilt controls come OFF the screen** (*"you ahve to remove -
Filters that arrive later … Export and column choices"*, `CR-043` finding 10). Under
B14 rule 41 that is the one legitimate question to put to the PO, and it is put in §6.

## 5 · WHAT IS NOT BUILT, AND WHAT EACH IS WAITING ON

### The selection column and the `3 selected` bulk bar — NOT BUILT

Three reasons, and the third is the one that decides it:

1. **`DataTable` has no selection.** Its own header says so — *"Row actions, bulk
   selection and the real export control are later packets"*. Adding it is a KIT change
   under every list in the product, which is not a minimal fix for one screen.
2. **Two of the three controls are Blocked.** `Enrol these` and `Re-level these` are
   `S75`, blocked on `OQ-237`, which is **OPEN**.
3. **The third has nothing behind it either.** `Export these` needs an export resource
   and **there is no `apps/billing/exports.py` at all** — the bills list one tab over
   records the same gap in its own comment.

**A selection mechanism whose every action is dead is hard-won law 2's dead control,
three times over.** Not built, stated here, and the fact already reaches a clerk in the
panel at the foot of the screen.

### Entry 25.1 `Enrol` — NOT BUILT, and the blocked boundary is now measured

The drawing's four numbered sections are `1 WHO` · `2 IS THIS ACCOUNT ELIGIBLE` ·
`3 THE LEVEL` · `4 WHAT HAPPENS NEXT`, with a wizard footer reading *"This writes an
enrolment and an event row. Nothing bills yet."*

**THE BLOCKED BAND, read off the page: the chip is `Blocked S75` and `S75` is the BULK
enrol, not this form.** `OQ-237`'s own scope line settles the boundary:
*"The ELIGIBILITY SOURCE and bulk enrolment only. One-at-a-time enrolment, the computed
level, re-levelling, the override and removal all ship."* So the form ships and two
things inside it do not:

* **`2 IS THIS ACCOUNT ELIGIBLE`'s second row — *the plan offers budget billing* —
  CANNOT BE ANSWERED, and answering it would resolve `OQ-237`.** The question is
  *where does the product read the plan's budget-billing flag from, and until it can,
  may a clerk assert it?* — **(a)** rating publishes a selector, or **(b)** the tick-box
  IS the record. **Building the seam callable chooses (a)**, which the prime directive
  forbids. Measured on this branch: `apps/billing/rating_seam.py` names no such callable
  (its 1,394 lines carry `price_period`, `price_bill`, `charge_amount`,
  `plan_late_fee_terms` and eighteen others, and none of them the budget flag), and
  **`customers.Account` has no `rate_plan` column at all** — it reaches a plan by
  walking to its `unit`, which is metering. So billing cannot get from an account to a
  plan without TWO cross-module hops. **The product keeps the staff confirmation it
  ships today and the row says so.**
* **`S74` — *the Enrol button can enable itself* — is chipped `New read` and is the same
  question's read half.** Not built here, for the same reason.

**Everything else on 25.1 is buildable and is this journey's next wave:** the account
PICKER (today a free-text box asking a clerk to paste a uuid — `DEF-BIL-5232`, already
filed), the three fact bands, the two-test eligibility table with its history row
answered, section 3's `Trailing twelve months, billed ÷ 12 → computed · ±30% band` — all
served already by `GET /budget-billing/{id}/eligibility` — the override field with the
band beside it, and the four-line *what happens next*. **⚠ TEN FACT ROWS ARE DRAWN AND
THE DOCUMENT SAYS NINE, TWICE** (p123 *"Nine facts"*, p124 *"Nine facts, in three
bands"*). Counted off the image at scale 4: `WHO, AND WHERE` 3 + `CAN IT BE LEVELLED` 4
+ `WHAT CHANGES FOR THEM` 3 = **10**. Under B14 rule 42 the image is the specification
and the prose is an index, so **ten rows are drawn and ten is what a lane builds**;
the likeliest reading of the nine is that the `Account` row echoes the picker above it.

### Entry 25.2 `Settle-up forecast` — NOT BUILT

Chipped `READ ONLY · New build S80 · Exists behind S60`, and the data is genuinely
there (`settle_up_month`, `variance_balance`, `actual_to_date`, the level paid). It is
a screen's worth of work and it is the next wave after 25.1. **Two things a lane must
carry into it:** divergence **D4** above — the `WILL` column is `budget.settle_up`'s
answer and NOT the drawing's signs — and the drawing's own withdrawn button, which
p125 records and explains: *"The cycle run already posts the settle-up… idempotently
per invoice. A bulk button would have been a second writer for the same money."*
**The product has no such button either — that one is agreement, not a gap.**

### Entry 25.3 `Asks` — NOT BUILDABLE TODAY · `DEF-BIL-5260`

Chipped `Exists behind S66 S67`. **It does not.** `apps/portal/services._hardship_ask`
raises an **ordinary service request** — which is `BR-CWP-066` working exactly as ruled
(*"never a request of a new kind"*) — whose only level-pay marker is the English
sentence `HARDSHIP_ROUTE_WORDS["level_pay"]` inside `what_they_said`, and
`create_from_portal` *"links no account and changes none"*. So of the drawn columns,
**`ACCOUNT` has no source, `LEVEL THEY WERE SHOWN` was never recorded anywhere, and
`ELIGIBLE` is `OQ-237`.** Counting the queue would mean matching a piece of copy, which
makes a KPI on a money screen depend on nobody ever improving a sentence.
`customers_seam.level_pay_asks_waiting()` therefore answers null **with its reason**,
and the tile prints that rather than a zero.

### Entry 25.4 `Portal · Level pay` — ⛔ REFUSED. IT IS NOT BILLING'S TO BUILD

**Read off p127–p128 and stated as a refusal with its evidence, which is the correct
deliverable here:**

* its address line is **`Customer portal · /level-pay and /level-pay/standing`** — not
  `/:tenant/billing/…`;
* the drawn frame is the **portal's** chrome (`Bills · Usage · Payments · Help` and an
  avatar), not the staff shell;
* the page's own footer mark reads **`1440 × customer portal`**, where every other §05
  screen reads `1440 × desktop`;
* §05's front matter counts the section as *"four for staff and **one for the
  customer**"*;
* and the code agrees: both reads live in `apps/portal/selectors.py`
  (`level_pay`, `level_pay_standing`) and reach billing **through a seam**
  (`apps/portal/seams/billing_seam.py` → `level_pay_position`, `level_pay_standing`,
  `level_pay_months`).

**Nothing in this change touches any of them.** Cross-module writes are forbidden and a
billing lane building a portal screen would be that, in code rather than in data.
**The finding worth passing on is the drawing's own:** *"the join control is **held**…
Across 64 portal routes, both level-pay endpoints are `GET`. So a customer can see
exactly what they would pay, press `Join level pay`, and nothing happens."* That is
hard-won law 2's dead control on a money screen, **and it belongs to a portal lane.**

## 6 · WHAT GOES TO THE PRODUCT OWNER — one question, and it is narrow

**Under B14 rule 41 the drawing is the scope and the only thing that reaches the PO is
a drawn element that contradicts a signed rule or an earlier ruling. There is exactly
one here (divergence D5):**

> On the Budget Bills screen there is a *Enrol these* button that cannot work yet,
> because the product cannot read whether a customer's price plan allows budget
> billing. The new drawing shows it greyed out with a sentence next to it saying why.
> In August you told us the opposite — that controls we have not built should come off
> the screen, not sit there greyed. Which do you want on this screen? Today the fact is
> written in a short panel at the bottom instead, and no greyed button is drawn.

Nothing is blocked either way: the controls are not built for three other reasons.

## 7 · PROOF, REGRESSION, VERSION AND ROLLBACK

**Proved against the reproduction, in a browser, at 1440 and 1280**, on the booted
stack. Screenshots in the lane's scratchpad under `budget-bills/`:
`00-reproduce-1440-before.png` · `01-reproduce-1440-eligibility.png` ·
`10-screen25-1440.png` · `10-screen25-1280.png`.

**What the browser showed after:** four KPI tiles — `ENROLLED 0 / of 72 accounts` ·
`CARRYING A SHORTFALL 0` · `DUE TO RE-LEVEL 0 / Every 6 months` ·
`ASKS WAITING — / Not counted yet`; the toolbar with the drawn placeholder, the `All`
chip, a `Status: On budget billing` chip, `+ Filter ▾` and the column glyph; the
stated-absence panel still at the foot. **No horizontal scroll at either width.**

⛔ **AND WHAT IT COULD NOT SHOW: A ROW.** Nobody is enrolled, and nobody can be — see
step 0 and `DEF-BIL-5259`. **So the populated table is proved by a DOM test and not by
the browser, and saying which check covers what is the point of this paragraph.**
`07-frontend/src/features/billing/budgetBillsTable.dom.test.tsx`, six cases: the eight
columns in the drawn ORDER, the pagination footer, the computed figure beside the
override, an absent figure as a dash and never `0.00`, no uuid as a visible value, and
the four tiles with the uncountable one saying so. **All six were proved RED first**,
through `npx vitest run` and not a hand-rolled entry point, in a `git worktree` pinned
at `531f3506`; the verbatim failures and **what that red does and does not prove** are
in the file's own header.

**Regression — the neighbours walked:** the whole `src/features/billing/` suite,
**403 passed, 1 failed**. The failure is `BillsPage.test.tsx`'s `searchFields`
assertion, which wants `["invoice_no","account_no","customer"]` and gets `"address"`
too. **Dated, not mine:** `git log -S '"address"' -- BillsListPage.tsx` names
`cf45a3d2` (2026-09-13), and `git merge-base --is-ancestor cf45a3d2 531f3506` confirms
it was already red at this lane's session start. `git diff --stat` shows this lane
touched no line of `BillsListPage.tsx`. **`DEF-BIL-5263`.**

`npx tsc --noEmit` — clean over this lane's files, **and it was capable of failing when
run**: it reported `TS2741 Property 'customer_name' is missing` on the fixture before
that was fixed. The only other errors are `FixABillTab.tsx`'s, which is **a sibling
lane's uncommitted work in this shared tree** — `git log -S "previewedFor"` returns no
commit at all, so those symbols exist in no history and the file is mid-edit. **That
file is not in this lane's commit.** `npx eslint --max-warnings 0` clean.
`npx vite build` passed — on the second attempt: the first failed on
`FixABillTab.tsx:1355 Multiple exports with the same name "default"`, which is the same
sibling's deliberate red-proof probe (`const __probe: number = "not a number"`) and
which cleared on its own.

`src/styles/routeBUtilities.test.ts` — 11 pass; `BudgetBillsTab.tsx` is on
`route-b-migrated.txt` (line 2293), so the **stricter** checker owns it and every class
token in the new markup compiles as a real utility.

**All 27 new strings are in all eleven catalogues** (`33 insertions, 0 deletions` on
each of the eleven files — an append, not a round-trip; `10-scripts/file_defect.py`'s
own lesson about a serialiser wearing the costume of an append). ⚠ **They are
`NATIVE-REVIEW-OWED` in ten of the eleven** (B14 rule 35): they were written to each
catalogue's existing register rather than translated from the English — German keeps
`Abschlagsrechnung`, Japanese and Korean are nouns (`均等払い`, `균등청구`), Hindi keeps
the everyday loanword — but nobody who speaks those ten has read them.

**Version `2.264.0`**, in `07-frontend/package.json`, `package-lock.json` and
`06-backend/pyproject.toml`, with the changelog entry in the same commit.

**Rollback: code only — revert the commit.** PO ruling 2026-09-10. ⚠ **And one line of
honesty: this change writes no data and applies no migration, so the revert is
complete.** The only thing it leaves behind is three defect rows and this record, which
are the point.

## 8 · WHICH BUILD TO LOOK IN

**`2.264.0`.** A tester who reported *"the Budget Bills list has no search and shows
everything"* should look there. What they will still find: the enrol form is above the
list rather than on its own screen, the override boxes still sit under the table with
no row attached (`DEF-BIL-5262`), and the list is empty because nobody can be enrolled
on this data (`DEF-BIL-5259`).

---

## 9 · ⚠ WHERE THIS CHANGE ACTUALLY LANDED, AND WHY THE COMMIT MESSAGE IS WRONG

**The code is in `16b7c35f`. The MESSAGE on that commit describes a different
lane's work** — *"Fix a bill becomes the four-step wizard"* — and it is recorded
here rather than rewritten, because siblings have already built on the branch.

**What went wrong, and it is a shape `CLAUDE.md` law 11 does not cover.** This
lane wrote its commit message to `msg.txt` in a scratch directory it believed
private. A sibling lane wrote its own `msg.txt` to the same path at 12:11, eleven
minutes later. `push_paths.sh` reads the message with `git commit-tree -F` **at
push time**, not when the lane wrote it, so at 12:13 it committed this lane's 25
files under the sibling's sentence. **`DEF-GOV-5265`.**

**⚠ AND EVERY CHECK LAW 11 PRESCRIBES PASSED, CORRECTLY.** `git diff --stat
67ddeee9 16b7c35f` is **25 files, and every one is on this lane's path list** —
nothing of a sibling's was published and nothing was reverted. The tree is right;
only the sentence describing it is wrong, and **no check in this repository reads
a commit message**. That is the whole of the finding: law 11 is written about
shared files inside the REPOSITORY — the index, a register, a blob — and says
nothing about a shared file outside it.

**Verified by subtraction and by bytes, after the push:** `CR-103-BRC03-…md`,
`budgetBillsTable.dom.test.tsx`, `BudgetBillsTab.tsx`, `ja-JP.json` and
`14-id-reservations.md` are each **byte-identical** between this tree and
`16b7c35f`. ⚠ **`git diff --numstat` reported the two NEW files as `0 406` and
`0 249` deletions and that reading is false** — they are untracked, so git
compares the commit against an index with no entry for them and calls them
deleted. `DEF-2100` already records this trap in its own words: *"the diff is not
the check"*. The byte comparison is.

**The working tree was deliberately NOT synced afterwards.** `commit-tree` writes
no file (`DEF-2474`), and this tree is dirty with two other lanes' in-flight work
— `FixABillTab.tsx` and `WizardFrame.tsx` — so `merge --ff-only` or a
`reset --mixed` here would move files under a lane that is mid-edit. The tip is
`16b7c35f`; that SHA is the thing to tell the other lanes, and it is the last line
of this record for that reason.

---

## ⚠ CORRECTIONS, 2026-09-15 — appended by the entry-25 table walk, not a rewrite

Lane `claude/eager-johnson-r0k88b` re-walked entry 25 against p121–p122 and found
**two pieces of evidence in §5 that have gone stale.** Neither changes a
conclusion; both are recorded because **a stated absence resting on evidence that
has gone stale is how a refusal outlives its reason.** Full record:
`CR-103-BRC03-entry-25-table-walk.md`.

1. **§5 says of the bulk bar: *"there is no `apps/billing/exports.py` at all"*.
   There is.** It landed 2026-09-01 under `DEF-2842`. The accurate reason is
   narrower and still holds: that file's `register()` registers exactly one
   resource, `RELEASES`, and the word `budget` appears **0** times in it.
2. **§5 says entry 25.2 `Settle-up forecast` is *"NOT BUILT"*.** True of the
   SCREEN. **Its read is live** — `budget-billing/settle-up-forecast` is a
   documented GET in `apps/billing/budget_api.py`, deliberately with no sibling
   POST. So the drawn `Settle up the year →` door is one wave from being owed,
   not a distant prospect, and `TC-B10` in `budgetBillsTable.dom.test.tsx` now
   goes red on the day its route is declared.

**And one deferral in this record expired.** §4's divergence note on the override
fields says *"§05 screen 25.1 is where the override belongs … and moving it is
that wave's work."* **Entry 25.1 landed on 2026-09-15 and did not take it** — what
it built is the *enrolment-time* override, greyed, which is a different act
(`DEF-BIL-5315`). `DEF-BIL-5262` is fixed on THIS screen instead, as a row-scoped
dialog; the reasoning is in `12-governance/02-decision-log.md` under
*"§05 screen 25 · where an override is asked for, when the drawing does not say"*.

---

## 2026-09-15 · TWO DEFECTS THE PRODUCT OWNER FILED THIS MORNING — `DEF-BIL-5339` (high) · `DEF-BIL-5340` (medium)

MAINTENANCE, by `12-governance/22-product-maintenance-process.md`: a clerk could
already open this tab and search it; what it SAID was wrong. Lane G,
`claude/gifted-johnson-top7zn`, from tip `9cda92e6`. The decision that shaped the
fix is in `12-governance/02-decision-log.md` under the 2026-09-15 row *"RULED
BEFORE CODING, `DEF-BIL-5339` + `DEF-BIL-5340`"*, written before a line of code.

### 1 · REPRODUCE — before a line moved, in Chromium at 1440 and 1280

`10-scripts/def_bil_5339_budget_copy_walkthrough.mjs --before`, against the
before-fix build served by `server.mjs` on the demo tenant `brazosbend` (72
accounts, 0 on budget billing). The PO's account `AC-2026-00038` is on the
Ottumwa tenant, which is not in this database; **`A-10432`** exists here and is
not enrolled, checked in SQL under the tenant GUC, and stood in for it.

**20 findings, ten per width, identical at both.** What a clerk read:

* under the list title, nothing on this data (the settings seam resolved) — the
  test below shows what it prints when it does not;
* the heading **"Three things this screen does not do"** — a hand-typed count;
* in the gap list, four bullets whose text carried, in order: `BR-RAT-043`,
  `OQ-237`, `budget_service.enroll`, `OQ-142`, `budget.settle_up_gl_account`,
  `BR-BIL-017` — six references, read off text nodes, not source;
* the zero-results line **"No results for ''."** with nothing typed — because
  the tab's default `Status` chip counts as a filter, so the kit's empty-list
  block *"Nobody is on budget billing."* could never render (law 2, dead UI);
* after typing `A-10432`: **"No results for 'A-10432'."** and nothing else — no
  word on which set was searched, no way to enrol from there.

⚠ **The first run of that script typed into the WRONG BOX.** `input[type=
"search"]` matched the shell's global search first, so the "search" screenshot
showed an untouched table. Fixed to the toolbar's placeholder before the record
was taken; the script says so in a comment, because every "after" assertion
would have passed over a search that never happened.

### 2 · LOCATE

Two render sites, both in the mounted file `BudgetBillsTab.tsx`: the
`parameters_unavailable` paragraph under the list title, and the shared
`GapNotes` in `billingOpsShared.tsx` printing each gap's `detail`. The strings
originate on the SERVER: `BUDGET_UNAVAILABLE` in `apps/billing/budget_api.py`
(four entries, three carrying ids) and `str(BillingConfigError)` from
`settings_seam.budget_billing`, which names `apps.tenancy.selectors.
settings_family` and `BR-BIL-017`.

**Why the 2026-09-15 fix for `DEF-BIL-5316` (`efc2f74e`) did not cover them:** it
removed the enrol panel and the ONE render site inside it (`eligible_
unavailable`). It touched neither the server sentences nor the gate that had
them: `G28` had held all three budget `detail` sentences in `g28_served_dict_
baseline.txt` (lines 20–22) since 2026-08-19, a ratchet that only shrinks, and
the settings sentence is built by `str(exception)` in a non-API file that G28's
served-dict part never reads — a zero reported over a scope it silently
excludes. The backend asks test even SAID so in its docstring (*"the two
`BUDGET_UNAVAILABLE` rows on the sibling screen carry ids in `detail` and are
another surface's defect"*) and filed nothing.

### 3 · BLAST RADIUS — both ways

`GapNotes` is mounted by **seven** billing screens, not five: Fix a bill, the
bill document, One-time bill, Bill layout (under Settings → Templates), the
pending queue, the settle-up forecast and this tab. `FixABillTab.tsx` is a
sibling lane's file and was not touched. The component's prop contract is
unchanged: a gap WITH a `message_key` renders the catalogue sentence; one
without renders `detail` as before. `parameters_unavailable` had ONE consumer.
`ZeroResults` is the kit's and is behind every `DataTable`; the change is one
branch on an empty query. The payments module has its own `GapNotes` in
`depositsShared.tsx` over a different type; untouched.

### 4 · THE MINIMAL FIX

**Server** (`budget_api.py`): each `BUDGET_UNAVAILABLE` entry carries
`message_key`, its `detail` is the id-free English mirror of the `en` sentence,
and its reasoning is a comment beside it; `parameters_unavailable` is served in
the same `{code, br_ref, message_key, detail}` shape as a gap, the seam's
sentence goes to the log. The relevel-drift sentence, which G28 had been red
on since 2026-09-14 and which no screen prints, lost its rule id the same way.
**Catalogues**: ten keys in all eleven languages through `i18n_fanin.py`, each
in the catalogue's own vocabulary (`Abschlagsrechnung`, `cuota fija`, `cobro
parejo`, `mensualisé`, `rata fissa`, `均等払い`, `균등청구`, `valor fixo` …).
**Screen**: the settings note and every bullet render `t(message_key)`; the
"Three things" note is **`Yearly cap` / `Set in Settings, not here.`** (the
count dropped, not derived — that note now states the one absence the server
list does not carry, and the list's heading already derives its count); a
scope note under an empty list — *"Searched accounts on budget billing only."*
with a term, *"Only enrolled accounts are listed."* without — carrying
`+ Enrol an account` as an inline link to `/billing/budget/enrol`. **Kit**:
`ZeroResults` says *"No results match these filters."* when no term was typed.
**G28 baseline**: three lines off, 20 entries → 17. `OQ-237` and `OQ-142`
stay OPEN; only where their citation sits moved.

### 5 · PROOF — red first, in the harness that runs it

* `07-frontend/src/testSupport/internalReferences.ts` — the shared helper: every
  text node and every `title`/`aria-label` in a rendered subtree (never
  `data-*`, which the 2026-08-19 ruling put there on purpose), against the id
  grammar and dotted Python identifiers. ⚠ Its first draft read `textContent`
  and **missed `BR-RAT-043`** because adjacent elements glue together
  (`yetBR-RAT-043`); it walks text nodes now. A markup-string form serves the
  route sweep, which renders in node.
* `budgetBillsClerkCopy.dom.test.tsx` (RTL, jsdom) — **RED against the unfixed
  screen**, quoting: `GapNotes`: `["BR-RAT-043","OQ-237","budget_service.enroll",
  "OQ-142","budget.settle_up_gl_account","BR-BIL-017"]`; the tab: `["BR-BIL-017",
  "apps.tenancy.selectors.settings_family","BR-RAT-043","OQ-237","budget_service.
  enroll","OQ-142","budget.settle_up_gl_account","BR-BIL-017"]`, heading *"Three
  things this screen does not do"*, zero state *"No results for ''."*. Green
  after, 8 cases, the search driven through the toolbar with the debounce.
* `routing/renderedCopy.test.tsx` — the repo's existing rendered-output sweep
  gained a THIRD question over its 14 routes (36 → 50 cases, all green): no id
  or identifier in the page.
* `tests/test_def_bil_5339_clerk_facing_copy.py` — ties every served `detail`
  to its `en` sentence, refuses an id in either, caps each sentence at six
  words, and reads the wire with the seam monkeypatched to fail. 52 backend
  tests green across the budget suites.
* `tsc` (proved capable of failing first), eslint clean, `G31` 0 undeclared,
  `G15`/`G32`/`G33` name none of the new keys, `G28` served-dict level at 17/17.
* **After, in Chromium, 1440 and 1280: 0 findings** — heading `Yearly cap`, four
  clean bullets, *"No results match these filters."* with no term, and after
  `A-10432`: *"No results for 'A-10432'."* over *"Searched accounts on budget
  billing only. + Enrol an account"* → `/brazosbend/billing/budget/enrol`.

### 6 · REGRESSION WALK — the neighbours, in the browser

All six other mounts opened; 0 broken bullets. Fix a bill (4 bullets), the
pending queue (3) and the settle-up forecast (4, now the new sentences) render
their lists; One-time, the bill document and the layout tab served no list on
this data. **Two neighbours show the same defect** — Fix a bill prints
`US-BIL-027`, `BR-BIL-009`; the pending queue prints `BR-BIL-021`, `US-BIL-006`,
`BR-BIL-051` — filed as `DEF-BIL-5344`, not fixed here (one commitment). The
doubled clear cross in every `DataTable` search box, present before and after,
is `DEF-SHL-5345`.

### 7 · REDS I DID NOT CAUSE, DATED

`G13` (three unwired props, since `f6fa3670` 2026-09-13) · `G15` (403
untranslated values, none mine) · `G18` (4 missing keys, none mine) · `G32`
(`billing.templates.layout_preview_refused` and three siblings, since
2026-09-14) · `G33` (`integrations.field.site_id` and two siblings, since
2026-09-14) · `G28` Part 3 (`apps/audit/diagnostics.py`, since `d6d31c46`
2026-09-04). Each dated with the history search law 7 prescribes.

### 8 · VERSION, ROLLBACK, WHICH BUILD

Version and CHANGELOG are the orchestrator's when the wave lands. Rollback is
the one commit: the server shape returns to a string and the tab prints it. A
tester who reported the ids or the empty search should look in the build the
orchestrator names for this wave.
