# §05 entry 25 · Budget Bills — THE TABLE, walked against its drawing

**Track: MAINTENANCE** (`12-governance/22-product-maintenance-process.md`). A clerk
could already list, re-level, override and remove budget accounts on this screen
today, so nothing here is a build. Lane: `claude/eager-johnson-r0k88b`, 2026-09-15.

**Drawing:** `05-prototype/04 Billing, As Built.pdf` §05 entry **25**, **p121 (mid) –
p122 (top)**, read **AS IMAGES** (B14 rule 42) at scale 2, and the table and toolbar
re-rendered cropped at scale 3 to read the cells. Page range confirmed by eye, not
taken from the briefing: p118–p120 are §05's prose, p121 carries the `THE CONTROL /
WHY NOT` table and then entry 25's frame, p122 carries the pager, entry 25's five rule
rows, and then entry 25.1.

**What this is NOT:** the table redraw itself, which landed on 2026-09-14 and is
recorded in `CR-103-BRC03-budget-bills-maintenance.md`. **This lane found that record
already in the tree and did not re-litigate it.** What follows is a second walk of the
same drawing against the shipped screen, three months of rot later in repo-time —
which found three differences the first tie-out could not see, because a tie-out that
asks *"is the column built?"* cannot ask *"is the thing drawn in it a door?"*.

---

## 0 · WHAT MOVED — three filed defects, all inside the drawn table

| Defect | Severity | What a clerk saw | What they see now |
|---|---|---|---|
| `DEF-BIL-5262` | medium | The override amount and reason sat in two boxes **under** the table, attached to no row. A clerk typed a figure, and only the pencil they pressed afterwards decided whose bill it changed. | The pencil opens a dialog **headed with that account**, showing the computed level the ±30% bound is measured against. |
| `DEF-BIL-5325` | medium | The account number was plain text. There was no way to open the account from this list. | The number is a link to the account, the same `accountDetailPath` the Bills tab one over has used since it shipped. |
| `DEF-BIL-5324` | low | The `RE-LEVEL` cell printed `2027-01`. | It prints `Jan 2027`, through `formatMonthYear`, the product's one month-year formatter. |

`DEF-BIL-5262` was filed by the 2026-09-14 lane and **deferred to entry 25.1's wave**
in its own words: *"§05 screen 25.1 is where the override belongs … and moving it is
that wave's work."* **Entry 25.1 landed, and did not take it.** What 25.1 drew is a
*greyed* override for the ENROLMENT moment (`DEF-BIL-5315` — an enrolment request
carries no override), which is a different act. So the hold expired silently and
nobody was holding it: hard-won law 2's mirror, the shape that cost the portal front
page six of its eight doors. **This lane is the reader that went and looked.**

---

## 1 · REPRODUCE — and what could NOT be reproduced, said plainly

**The screen was not driven in a browser, and no claim here rests on one.** Nothing was
listening on `:5173` or `:8000` in this container, and the constraint is older than
that: budget enrolment needs **twelve months of ISSUED billing history** and this
database holds **zero invoices**, so no account anywhere can be enrolled and the live
table has no row to draw. The 2026-09-14 lane recorded the same thing and built the
static DOM test for exactly this reason.

**So the reproduction is the rendered markup and the drawing, side by side**, and
every symptom below was read off one or the other:

* the override boxes and their two `id="bil-budget-override…"` inputs, in the markup
  under the table, with no account named anywhere near them;
* the pencil rendered `disabled` on **every** row until those boxes were filled —
  proved, not inferred: `expect(element).not.toBeDisabled()` fails against the
  pre-change component (§8);
* the account cell rendered `<span title="01a0…">` and no `<a>` at all;
* the `RE-LEVEL` cell rendered `2027-01`.

**⚠ No gate in this repository reads rendered output, so green tests do not mean this
screen was checked against its drawing.** The drawing was checked by eye, as images,
and the differences are listed in §4 and §5. A browser pass is still owed and is named
in §9.

---

## 2 · LOCATE — the file actually mounted

`07-frontend/src/features/billing/BudgetBillsTab.tsx`, mounted by
`BillsListPage.tsx:1200` as the `Budget Bills` tab of `/{tenant}/billing/:tab`. Not a
second component of a similar name: `BudgetEnrolPage.tsx` is entry **25.1** and is
mounted separately at `BUDGET_ENROL_ROUTE` from `App.tsx:1116`.

## 3 · BLAST RADIUS — both directions

**What else uses what was touched:**

| Touched | Who else reads it |
|---|---|
| `budgetTableConfig`'s third argument | nobody — it is module-private to this file |
| `LevelCell` (exported) | `BillingSurfaces.test.tsx:23`. **Untouched by this change.** |
| `budgetListKey`, `budgetEligibilityKey` (exported) | `budgetBillsTable.dom.test.tsx`, `budgetEnrolPage.dom.test.tsx`, `BudgetEnrolPage.tsx:170`. **Untouched.** |
| `overrideBudgetLevel` | this file only |
| the eleven locale catalogues | +2 keys each, additive, `2 insertions / 0 deletions` per file |

**And the mirror — what USED what was removed:**

* the two `<input>` elements and their `overrideAmount` / `overrideReason` state: read
  by nothing outside this component; grepped before removal;
* `billing.budget.overrideNeedsReason`: no longer referenced by code. It is **kept in
  all eleven catalogues and referenced by a test** (`TC-B9` asserts its absence from
  the screen), the same posture `billing.budget.field.accountHint` has carried since
  `DEF-BIL-5232` removed the field it labelled;
* `apiErrorText` and `isApiError`: still used — the list's error state and the
  dialog's server-refusal path respectively.

---

## 4 · THE ELEMENT WALK — p121/p122 against the shipped screen

Everything the drawing puts on entry 25, and where it stands after this change.

| Drawn | Status |
|---|---|
| Page title `Budget Bills`, summary line under it | built (the tab's explainer) |
| `+ Enrol an account` (header, right) | **built and wired** — a `ButtonLink` to entry 25.1's address |
| `Settle up the year →` (header, right) | **absent, deliberately** — §6 |
| Four KPI tiles `ENROLLED · CARRYING A SHORTFALL · DUE TO RE-LEVEL · ASKS WAITING` | built; the red on `37` and two detail lines diverge — §5, §6 |
| Search `Search account #, customer or address…` | built, three server legs |
| `Status ▾` · `Re-level due ▾` · `+ Filter ▾` · column chooser | built |
| `Plan ▾` | **absent** — §6 |
| `↓` export | **absent** — §6 |
| Selection checkbox column · `3 selected` · `Export these` · `Enrol these` · `Re-level these` | **absent** — §6, and a PO question is already open on it |
| `ACCOUNT` — number over customer name | built; **the number is now the drawn link** (`DEF-BIL-5325`) |
| `STATUS` | built, as a `StatusPill` rather than the drawn plain text — §5 |
| `COMPUTED` · `OVERRIDE` · `THEY PAY` (bold) | built, three cells, never collapsed |
| `ACTUAL TO DATE` | built |
| `VARIANCE`, signed | built; the drawn RED on a positive figure is NOT applied — §5 |
| `RE-LEVEL` — `Jan 2027` / bold `Drifted 14%` | month **now as drawn** (`DEF-BIL-5324`); the drift half is a stated absence — §6 |
| `Showing 1–50 of N`, rows-per-page, pager | built (B14 rule 16, `NFR-3`) |
| an ACTIONS column | **not drawn anywhere on p121–p122; the product has one** — §5 |

---

## 5 · WHERE THE DRAWING AND OUR OWN RULES DISAGREED

**E1 · The override form.** The drawing draws **no override on screen 25 at all** —
not the two boxes that were there, and not a dialog either. It also draws no actions
column, so it does not say where a clerk overrides an ENROLLED account's level; entry
25.1 answers only the enrolment moment. Deleting the capability was the other reading
of that silence and it is the worse one: it takes a live write off the product to
satisfy a drawing that simply does not cover the case. **So the CONTROL is the
drawing's (a row action) and the FORM is built to our own kit — which is exactly the
split B14 rule 38 makes.** The dialog carries the computed figure because p122's own
rule row demands it: *"The ±30% bound is measured against the computed figure, so
hiding it is how an override gets typed blind."*

**E2 · `STATUS` is a pill, not plain text.** p121 draws `Enrolled` and `Off budget` as
bare words. The product draws a `StatusPill`. **B14 rule 36 gives visual style to r10
and the shared kit**, and a status pill is the kit's one answer for a state word
across every list in the product. Not changed, recorded.

**E3 · The `VARIANCE` colour is NOT taken from the drawing, and this is a money
path.** p121 inks `+$212.80` and `+$318.20` red and leaves `−$61.40` black. ❄️
B5/WE-8/GT-24 runs the other way — `variance_movement` is `level − actual`, so a
POSITIVE balance means the levels collected MORE than the customer used and the
utility **credits** it (`budget.settle_up`'s own words). Colouring by the drawn sign
would paint every customer who is owed money as the one to chase. The first walk
recorded this as its divergence D4; **this lane re-read it and confirms it, and adds
only that the colour is the same trap as the sign.** Nothing here flips or tints one.

**E4 · The bulk bar's sentence would be rationale on screen.** *"Enrolling in bulk is
not offered — eligibility rides a plan flag nothing publishes"* is 14 words of WHY.
**B14 rule 33 gives rationale zero words on screen.** Moot while the controls are
absent (§6); named here for whoever builds them.

**E5 · `from the portal · screen 25.3` under the `ASKS WAITING` tile.** B14 rule 31
keeps an internal screen reference off a clerk's screen. Unchanged from the first
walk; the tile carries the reason the queue cannot be counted instead.

**E6 · The drawn `10%`, `14%`, `218`, `$4,912.60`, `1,284` and every money figure on
p121 are ILLUSTRATIONS** (B14 rule 37). Not one of them is hardcoded, and no fixture
in either test file uses one — both say so in their own headers.

---

## 6 · STATED ABSENCES — each with the code that proves it

**Nothing below is fabricated in the browser, and nothing below is drawn as a control
that cannot act.** PO ruling 2026-08-27 (`CR-043` finding 10) is why an unbuilt
control comes off the screen rather than being greyed: *"you ahve to remove - Filters
that arrive later … Export and column choices"*.

| Drawn | Why it is not there | Code evidence |
|---|---|---|
| `Plan ▾` filter | The list endpoint has no plan parameter, and no account records which plan it is on, so there is no set to filter by | `06-backend/apps/billing/budget_api.py` `budget_enrollments` reads `f.status`, `f.relevel` and `q` and nothing else |
| `↓` export · `Export these` | Billing's export kernel registers exactly **one** resource, and it is bill-run releases | `06-backend/apps/billing/exports.py` `register()` → `register_export_resource(RELEASES)`; the word `budget` appears **0** times in that file |
| selection column · `3 selected` bar | The shared table has no row selection at all | `07-frontend/src/components/DataTable.tsx` header: *"Row actions, bulk selection and the real export control are later packets"* — re-checked this lane, still true; the only `bulk` identifier in that file is the expand-all toggle |
| `Enrol these` · `Re-level these` | `S75` (bulk enrol) is **Blocked** on `OQ-237`, which is **OPEN** | entry 25's own chip on p121 reads `Blocked S75` |
| `Settle up the year →` | Entry **25.2** has no front end. **Its server half DOES exist** — `budget-billing/settle-up-forecast` is a live GET — so this is one wave from expiring | `budget_api.py` urlpatterns; `budget_settle_up_forecast` is a GET with no sibling POST, on purpose |
| `Drifted 14%` · `drifted past 10%` | `budget.relevel_due` has two gates and only the cadence is stored; the drift half is a fresh twelve-month invoice read **per account** | `_relevel_fields` serves `relevel_drift_unavailable` on every row |
| `ASKS WAITING 6` | A level-pay ask carries no route, kind or account to count by | `summary.asks_waiting` is null with `asks_waiting_unavailable` beside it; `DEF-BIL-5260` |
| the red on KPI `37` | `KpiTile` has no tone member — a kit change under every strip in the product, not a minimal fix for one screen | `07-frontend/src/components/KPIStrip.tsx` — `tone` appears **0** times |

**⚠ AND THE ABSENCE THAT HAS A TEST WATCHING IT.** `Settle up the year →` is the one
hold here whose clock is already running, so `TC-B10` in
`budgetBillsTable.dom.test.tsx` **fails on the day entry 25.2's route is declared** and
says in its own words what is then owed. A hold with no such test is a promise nobody
is keeping (hard-won law 2), and this is the first one on this screen to have one.

---

## 7 · TWO CORRECTIONS TO THE EARLIER RECORD — dated, because they rotted

`CR-103-BRC03-budget-bills-maintenance.md` §5, written 2026-09-14, gives three reasons
the bulk bar is not built. **The third is now wrong, and the second reads as more than
it is:**

1. It says *"there is no `apps/billing/exports.py` at all"*. **There is** — it landed
   2026-09-01 under `DEF-2842`. The accurate reason is narrower and still holds: that
   file registers `RELEASES` and knows nothing about budget enrolments.
2. It says entry 25.2 is *"NOT BUILT"*. True **of the screen**; its read endpoint
   `budget-billing/settle-up-forecast` is live and documented at length.

Neither changes the conclusion — the bulk bar stays unbuilt for the two reasons that
survive — and both are recorded here rather than left, because **a stated absence
resting on evidence that has gone stale is how a refusal outlives its reason.** That
is the same mechanism as `DEF-BIL-5262`'s expired hold, one document along.

---

## 8 · PROOF

**Every new case was proved RED first, in the harness that runs it** (`npx vitest run
<file>`, never a bare script), **in a `git worktree` pinned at `679329eb`** — the tip
before this change — so the red is against the shipped component and not against a
half-edited tree.

`budgetBillsTable.dom.test.tsx` — **3 failed, 6 passed** (the six pre-existing cases
stayed green, which is also the proof that parameterising `render()` moved nothing):

```
TC-B7 → expected '<div class="flex flex-col gap-4"><p c…' to contain
        'href="/brazosbend/accounts/01a00000-0…'
TC-B8 → expected '<div class="flex flex-col gap-4"><p c…' to contain 'Jan 2027'
TC-B9 → expected '<div class="flex flex-col gap-4"><p c…' not to contain
        'id="bil-budget-override"'
```

`budgetOverrideDialog.dom.test.tsx` — **5 failed, 0 passed**, and the first is the
defect itself in one line:

```
TC-D1 → Error: expect(element).not.toBeDisabled()
TC-D2 → TestingLibraryElementError: Unable to find role="dialog"
TC-D3 → TestingLibraryElementError: Unable to find role="dialog"
TC-D4 → TestingLibraryElementError: Unable to find role="dialog"
TC-D5 → TestingLibraryElementError: Unable to find role="dialog"
```

**What would make these pass wrongly, asked of each** (law 7 habit 2):

* `TC-B7` — a `MemoryRouter` with no `:tenant` builds `//accounts/…`, a
  protocol-relative URL to another host that reads as a fine string to `toContain`.
  The tenant is pinned into the expected value and the component is mounted under the
  real path pattern; the case also asserts `//accounts/` is absent.
* `TC-B8` — `formatMonthYear` returns its input verbatim on a value it cannot parse,
  so the case also asserts the raw `2027-01-04` is absent.
* `TC-B9` — an absence assertion passes over a blank page, so it asserts the table
  rendered first.
* `TC-B10` — **this one was written wrong and the wrongness was caught live, within
  the hour. It is the most useful thing in this record.** The first version asserted
  that NO settle-up route was declared, so that it would fail the day one appeared. It
  named the event it was watching for. Entry 25.2's lane then declared its route and
  called it **`BUDGET_FORECAST_ROUTE`** — no `SETTLE` anywhere in the identifier — and
  the `/SETTLE/i` filter sailed straight over it. **A check whose whole job is to fire
  on an event, silently unable to fire, on the one case written to prevent exactly
  that**: hard-won law 7's *structurally incapable of failing*, in its own trap.
  It is now stated POSITIVELY and holds in both worlds without knowing which it is in:
  if a forecast route exists, the page head must carry a link **to that address**; if
  none exists, nothing on the screen may point at one. Both branches were proved:
  the negative passes at `7f414ad4`, and the positive was shown RED in a throwaway
  worktree with the route declared and the door absent —
  `expected … to contain 'href="/brazosbend/billing/budget/settle-up"'`.
  **The general lesson, and it is not about this screen: never key a guard on a name
  somebody else has not chosen yet.**
* `TC-D1`–`TC-D4` — every one passes on a dialog hardwired to the first row. **`TC-D5`
  is there for that and nothing else:** it opens the SECOND row and asserts the first
  account is *not* named and the post goes to the second account's address.

---

## 9 · VERSION, ROLLBACK, AND WHAT IS STILL OWED

* **Version:** see `CHANGELOG.md`; the three defect rows carry it.
* **Rollback:** code only — revert the commit (PO 2026-09-10). **Nothing here repairs
  data and nothing here sends anything**, so the revert is complete.
* **Still owed, and named rather than implied:** a browser pass against p121 at 1440
  and 1280 with rows on the table, which needs a database holding twelve months of
  issued bills. No gate in this repo reads rendered output, so until somebody does
  that, the alignment and the density of this table are unverified.
