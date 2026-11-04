# §05 entry 25.2 `Settle-up forecast` — BUILD record

**Track: BUILD (`r11`).** The maintenance process's one question — *can a user do this
task in the product today?* — is **no**. There is no forecast anywhere in the product:
no screen, no address, and, uniquely among the five §05 entries, **no endpoint at all**.
`CR-103-BRC03`'s step-1 record already classified 25.2 as *"NEVER BUILT"*, which the
blueprint's own caption repeats on every §05 page.

| | |
|---|---|
| Id | `CR-103-BRC03`, continued — the same change request's next wave |
| Branch | `claude/eager-johnson-r0k88b`, base `679329eb` |
| Drawing | `05-prototype/04 Billing, As Built.pdf` · 14,363,163 bytes · **on this branch**, verified before reading |
| Pages read AS IMAGES (B14 rule 42) | p117–p129 at scale 2. **p124(low) is the head, the chips and the top of the frame; p125 is the whole body — tiles, the `WHERE IT HAPPENS` panel, the toolbar, the table and the footer; p125(low)–p126(top) is its commentary.** `pdf_text.py` was used ONLY to find the page and to cross-check spelling — the brief warns it drops every digit in the mono meta lines, and this screen is almost entirely money |
| Read | `GET /budget-billing/settle-up-forecast` — **new**, `06-backend/apps/billing/budget_api.py` |
| Screen | `07-frontend/src/features/billing/SettleUpForecastPage.tsx`, routed at `/:tenant/billing/budget/settle-up` |
| Version | see the CHANGELOG entry landed with this wave |

---

## 0 · THE BLOCKER, AND WHY THE READ IS LAWFUL WHILE THE POSTING IS NOT

`OQ-142` was read by its **STATUS COLUMN**, not its body (the prime directive's own
warning, `DEF-WRK-4030`). The status reads:

> **ANSWERED 2026-08-15 → a SEPARATE budget-variance account (PO: *"Create seperate
> account"*). Blocked on a finance re-sign of B5 line 74 ❄️ via HUMAN-GUIDE §6 before
> the designation goes live; until then the settle-up posting REFUSES BY NAME rather
> than posting to a semantically wrong bucket.**

**So the question is ANSWERED and only the POSTING waits — on a signature, not on a
decision.** `budget.settle_up_gl_account` is therefore *not* a `NotImplementedError`
stub and this lane did not add one: `posting_seam.budget_variance_account_id` refuses
by name, and its own docstring says *"this is no longer a stub — it is a refusal
waiting on a signature."*

**Nothing this lane built posts anything.** The forecast is arithmetic over rows that
already exist — `account_budget_status.variance_balance` and the append-only
`account_budget_events` — every figure of which is computed and stored today. A read
of figures the engine already holds is lawful while the GL side is unsigned, and that
is exactly where `budget.py`'s own docstring already drew the boundary: *"the
billing-side arithmetic below is complete and tested; only the posting is blocked."*

**No `NotImplementedError("OQ-142")` was added, and adding one would have been wrong** —
it would have recorded a question as open that the PO closed on 2026-08-15.

---

## 1 · WHAT WAS BUILT, AGAINST WHAT IS DRAWN

| Drawn (p124–p125) | Built | Note |
|---|---|---|
| Page head `Settle-up forecast` | ✔ | `PageHeader` — rule 2 (one header) and rule 40 (32px) |
| Caption `Read only · the cycle run posts every one of these` | ✔ *shortened* | `Read only. The run posts these.` — rule 33, two sentences of ≤6 words |
| `Export` top-right | ✔ **disabled, with its reason** | `DEF-BIL-5328` — see §3 |
| `Back to budget bills` top-right | ✔ *shortened* | `← Budget bills` — a LABEL caps at 3 words (rule 33) |
| The Billing tab strip, `Budget Bills` active | ✔ | |
| Tile `SETTLING THIS MONTH` · `9` · `November` | ✔ | count + month name, from the server |
| Tile `TO COLLECT` · `$1,204.60` · `6 accounts` | ✔ | a POSITIVE magnitude; one currency or none |
| Tile `TO CREDIT` · `$318.20` · `3 accounts` | ✔ | as above |
| Tile `LATER IN THE YEAR` · `28` · `8 other months` | ✔ *shortened* | `Later this year`; the detail is a DISTINCT-month count |
| Panel `NOTHING ON THIS SCREEN WRITES ANYTHING` / `WHERE IT HAPPENS` | ✔ *3 of 4 rows* | heading → `Where it posts`; see §2 |
| `There is no button here on purpose…` | ✘ **removed** | RATIONALE — rule 33 gives it zero words on screen; see §2 |
| Toolbar: search, `Month`, `Direction`, `+ Filter` | ✔ | the kit's `DataTable` toolbar + `FilterBar`; `+ Filter` is the kit's own overflow, not a fourth control |
| Table `ACCOUNT / SETTLES IN / PAID ON THE LEVEL / ACTUAL SO FAR / BALANCE / WILL` | ✔ 6 columns, drawn order | `Paid on level` — rule 33 |
| Account cell: number over customer name | ✔ | rule 31 — the NUMBER shows, the id rides the `href` |
| `Nov 2026` | ✔ | `formatMonthYear`, the product's ONE month-year formatter (`DEF-BIL-5324` is the sibling cell that printed `2027-01`) |
| `+$212.80` in the accent / `−$61.40` plain | ✔ | see §4 — the sign is the engine's own `SettleUp.signed` |
| `Collect` / `Credit` | ✔ | plus a third state the drawing has no row for: exactly zero to true up |
| `Showing 1–37 of 37`, `Rows per page 50`, ‹ › | ✔ | the kit's pagination footer (rule 16); the page is cut in SQL (`NFR-3`) |
| `Accounts do not all settle together. Each one carries…` | ✔ *first sentence only* | `Accounts settle in different months` (5 words); the second sentence is rationale |
| `v2.235.0`, `1440 × desktop` | n/a | blueprint chrome, not screen content |

⚠ **Every figure in that drawing is an ILLUSTRATION (B14 rule 37) and not one of them
is asserted anywhere.** `100412`, `+$212.80`, `9`, `37`, `8 other months` — the tests
assert that a SERVED figure reaches the screen, that the sign survives in both
directions, and that an UNSERVED one says so. The drawn numbers are never the contract.

---

## 2 · THE FOUR COPY DIVERGENCES, AND THE RULE THAT DECIDES EACH

B14 rule 41 makes the drawing the specification; rule 33 is a signed rule the drawn
PROSE exceeds. The structure is built exactly and the words are cut to the caps.
**Nothing drawn is dropped except what rule 33 gives zero words on screen.**

1. **`There is no button here on purpose. A second way to settle the same money is a
   second answer to it.`** — RATIONALE (*why a control is absent*), which rule 33 puts
   at **zero words on screen**. ⚠ Rule 33's own note: rationale is **REMOVED, not
   shortened** — a six-word version keeps the breach and makes it terser. It lives in
   `SettleUpForecastPage.tsx`'s header, in `budget_api.budget_settle_up_forecast`'s
   docstring and in this record, and `TC-F4` asserts it never creeps back on screen.
2. **`What this screen is for / Seeing it coming, and answering the customer who rings
   to ask`** — the same thing, so the panel is **three factual rows, not four**.
3. **Headings over three words** — `NOTHING ON THIS SCREEN WRITES ANYTHING` → `Where it
   posts`; `LATER IN THE YEAR` → `Later this year`; `PAID ON THE LEVEL` → `Paid on
   level`; `Back to budget bills` → `← Budget bills`.
4. **The table caption's second sentence** — rationale; the first is a fact a clerk
   needs and is kept.

**This is the same reading entry 25.1's lane applied** (*"the four captions are
RATIONALE and rule 33 gives rationale ZERO words on screen"*), so the two screens
diverge from their drawings in the same way and for the same reason. **Nothing here is
put to the PO**: hard-won law 13's short list is a ruling colliding with a signed rule,
a ❄️ FROZEN B4/B5 figure, or a fact only they hold, and rule 33 winning over drawn
prose is a precedent already set on the sibling screen rather than a new collision.

---

## 3 · WHAT IS DRAWN AND NOT SERVED — STATED, NEVER INVENTED

* **`Export`** — `DEF-BIL-5328`. `EXPORT_RESOURCES` is a closed list of eleven and none
  is a budget list; `BR-SHL-010` makes the SERVER's capability row the config, and
  registering one is a `billing/exports.py` surface with its own 50,000-row cap and,
  because this is money, its own `audit_log` write under `BR-SHL-016`. The button is
  **drawn, rendered and disabled with its reason** — the blueprint's own doctrine one
  page earlier (p121: *"Greyed-with-a-reason tells a clerk… a missing control tells
  them the product forgot"*).
  ⚠ **THE HOLD CARRIES THE TEST THAT FIRES WHEN IT EXPIRES** (hard-won law 2): `TC-F9`
  asserts `EXPORT_RESOURCES` still contains no settle-up and no budget resource, so the
  day one is registered the suite goes RED and names this button.
* **An account with no settle-up month.** `settle_up_month` is nullable and such an
  account never trues up. It is excluded from the rows and **COUNTED** in
  `no_settle_month`, which the screen states in one line — a forecast that silently
  covered fewer people than are enrolled would be worse than one that says so.
* **A period with no bill in it.** `paid_on_level` and `actual_so_far` are served NULL
  and render as *"No bills yet"*, **never `$0.00`** — a zero says the meter read zero.

---

## 4 · THE SIGN, AND WHY THIS SCREEN IS NOT CONTRADICTING ITS SIBLING

`BudgetBillsTab` records, correctly: *"the variance sign is the engine's and not the
drawing's… nothing here flips a sign."* This screen prints `+$212.80 → Collect`, which
looks like the opposite. **It is not a flip, and the reconciliation was already in the
engine before this lane started.**

| | screen 25 | screen 25.2 |
|---|---|---|
| The fact drawn | the POSITION the account is in | the TRANSACTION that is coming |
| The field | `variance_balance` | `budget.SettleUp.signed` |
| ❄️ WE-8, July | **−50.87** (under-paid) | **+50.87** to collect |

`SettleUp.amount` is always positive, `direction` carries the sign, and `signed`'s own
docstring reads *"+ collects, − credits"* — **exactly the drawn column**. So
`balance_signed` is served off the ❄️ frozen dataclass and **no figure is negated in
either the API or the browser.** `TC-F5` asserts both directions.

---

## 5 · THE THREE MONEY COLUMNS TIE OUT, AND NOTHING IS ADDED CLIENT-SIDE

A `billed` event's movement IS `level − actual`, so over one settle-up period
`Σlevel − Σactual` **is** the variance balance. The server serves all three figures and
the browser adds nothing — the rule entry 25.1's lane applied when it refused to sum
twelve monthly figures client-side.

Proved on the ❄️ frozen WE-8 chain
(`06-backend/tests/test_s80_settle_up_forecast.py`):

| | |
|---|---|
| `paid_on_level` | 3 × **242** = **726.00** |
| `actual_so_far` | 292.87 + 231.40 + 198.75 = **723.02** |
| `balance_signed` | 723.02 − 726.00 = **−2.98** → **CREDIT 2.98** |

and the other way, two months in: balance **−40.27** held → `balance_signed` **+40.27**,
**COLLECT**.

⚠ **THE PERIOD STARTS AT THE LAST SETTLE-UP, NOT AT ENROLMENT**, or the two sums would
report a year the balance no longer covers. The boundary is strictly *after* the
settle-up's `occurred_on`, because the settle-up month's own bill belongs to the year
being closed — `budget_service.record_bill` says so in its own words.

---

## 6 · A DEFECT FOUND ON THE WAY IN, FILED BEFORE IT WAS FIXED

**`DEF-BIL-5327` — the Budget Bills tab's `ACTUAL TO DATE` column double-counts the
settle-up month.** `selectors.budget_actuals_to_date` summed every budget event
carrying an `actual`, and a settle-up month writes **two** such rows for one bill: the
`billed` row that moves the variance and the `settled` row that resets it, which
`_record_event` stamps with the same `level` and `actual` so a year-end row can
reproduce what the customer was shown.

Measured on the frozen chain driven through its settle-up:

| | served | true |
|---|---|---|
| Actual to date | **$921.77** | **$723.02** |
| Months | **4** | **3** |

overstated by **$198.75**, which is September's actual counted twice. **The month count
inflated with it, so the row looked internally consistent** and the column was wrong on
every account that had ever settled.

**Fix:** filter on `event = billed` rather than on `actual IS NOT NULL`. *The event kind
is the fact being asked for; "has an actual" was a proxy for it that stopped being true
the moment a second event kind carried one.* The same reasoning is why the new
`budget_settle_up_windows` filters on the kind for BOTH sums — five of the six event
kinds carry a `level`, so a `level IS NOT NULL` sum would have added a decision to a
year of bills.

Regression:
`test_s80_settle_up_forecast.py::test_def_bil_5327__actual_to_date_counts_billed_months_only`.

---

## 7 · PROOF

**Backend** — `06-backend/tests/test_s80_settle_up_forecast.py`, **13 passed**.
Neighbours re-run for regressions (the selector is shared with screen 25):
`test_us_bil_018_budget_enrollment` · `test_us_bil_019_budget_bill` ·
`test_us_bil_020_budget_maintenance` · `test_us_bil_surface_apis` ·
`test_def2480_account_snapshot_budget` · `test_us_rbs_044_budget_relevel` —
**73 passed**.

**Frontend** — `settleUpForecastPage.dom.test.tsx`, **13 passed**; the whole billing
suite **51 files, 751 passed**; `tsc --noEmit` clean, **after** planting a deliberate
type error and watching it fail (the skill's own warning: a `tsc` that cannot fail is
a green over an unchecked tree).

### ⚠ THREE GUARDS WERE PROVED RED BY SABOTAGE, AND **TWO OF THEM PASSED THE FIRST TIME**

This is law 7's *"ask what would make this check pass wrongly"*, and both false passes
were found by breaking the component rather than by reading the test.

| Guard | First draft | What made it pass wrongly | Hardened to |
|---|---|---|---|
| `TC-F9` the Export hold | `expect(html).toContain("disabled")` | **every** Button in the kit carries `disabled:opacity-45 disabled:cursor-not-allowed` in its class string, disabled or not — so the word is always present | a regex on the rendered **attribute** `disabled=""` |
| `TC-F5` the sign | `toContain("$212.80")` | `-$212.80` **contains** `$212.80`, so a cell rewritten to negate passed unchanged. A sign check built only from `toContain` cannot see a flipped sign at all | plus `not.toContain("-$212.80")` — a collection is never negative |
| `TC-F4` the rationale | — | bit on the first sabotage | unchanged |

Each sabotage was applied to this lane's own files only, and the file was restored and
**verified byte-identical by sha256** (`c1639dbc…`) before the next one.

A fourth false pass was found in the fixture itself: the query key hard-typed `25` where
`DEFAULT_PAGE_SIZE` is **50**, so the query held no data and six cases failed for a
fixture fault rather than for anything on the screen. It is derived now, as is the
account href (`accountDetailPath`) — an address written out by hand would go on passing
after the real route moved, which is `DEF-CWP-3925`'s exact shape.

---

## 8 · WHAT THIS LANE DID NOT DO

* **No bulk settle-up control, and no sibling POST.** The drawing withdrew its own
  button and the cycle run is the only writer.
* **No `NotImplementedError("OQ-142")`** — see §0; the question is answered.
* **No change to any ❄️ FROZEN figure.** WE-8's chain is QUOTED and asserted so drift
  goes red, never moved.
* **No export resource registered** — reported as `DEF-BIL-5328` rather than built,
  because it is a money export with an audit rule of its own.
* **`DEF-BIL-5312` (the ±30% override band on screen 25.1) was NOT released**, and it
  was checked: `budget.override_bounds` still has no caller outside `validate_override`
  and no payload carries the range. It belongs on `GET /budget-billing/{id}/eligibility`
  — the read that already computes the level the band is measured against — and NOT on
  a settle-up forecast, which has nothing to do with enrolment overrides. Publishing it
  from here would have closed a register row by putting a figure on the wrong read.
