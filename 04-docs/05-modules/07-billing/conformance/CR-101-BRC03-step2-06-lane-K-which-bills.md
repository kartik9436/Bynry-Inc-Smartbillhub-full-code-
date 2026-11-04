# CR-101-BRC03 §06 lane K — which bills a bulk correction takes

Three Product Owner rulings of **2026-09-15**, all about the same question, and
one principle underneath them:

> **A SCOPE FILTERS; A CLERK WHO NAMES A BILL DOES NOT.**

Both selection rulings carve the `single` selector out, and they do it for the
same stated reason: a utility may have overbilled somebody who has since left,
and refusing that for ever would be wrong.

---

## What was read, and how

| Read | How |
|---|---|
| The three decision-log rows of 2026-09-15 | verbatim, before writing anything |
| `05-prototype/04 Billing, As Built.pdf` **p137** | as an **IMAGE**, scale 2, with the **Read** tool (B14 rule 42) |
| `12-governance/10-defect-log.csv` — `DEF-BIL-5377`, `DEF-BIL-5360`, `DEF-BIL-5361` | the rows, before touching the code |
| The code each ruling names | **before** building on it — see *what the record got wrong* below |

---

## Ruling 1 · `DEF-BIL-5377` — selection, not refusal

> *"you will not select the bill/account in first place ; our rule to selct
> account will apply - we do this at the time of bulk billing also"*

**Reproduced on the demo tenant, then re-measured after.** Opening a class-R
case over cycle `CY-001`:

| | bills in scope | accounts | what happened |
|---|---|---|---|
| **before** | **79** | 40 | refused, all of them: *"account 'AC-2026-00042' is not in the billable set for its unit (BR-CUS-055)"* |
| **after** | **77** | 39 | the case **opens**, and the closed account's 2 bills are simply not there |

One closed account was stopping seventy-nine. At 40,000 accounts a utility
always has closed ones, so bulk corrections did not work at T5 at all.

**The rule is REUSED and nowhere restated.** `customers.selectors` now publishes
**`billable_accounts()`** — `BR-CUS-055`'s class set with no unit scope — and
`accounts_for_bill_run` is **that queryset plus a unit filter**. One statement of
who may be billed, so the bill run and the correction cannot drift apart.
Billing reaches it through the seam by name and uses it as a **SQL subquery**
(`account_id__in=billable_accounts().values("id")`), never a list of ids: `NFR-5`
puts no cap on a tenant, and materialising 40,000 account ids is the limit the
ceiling forbids.

**If the seam is not published the scope REFUSES.** Carrying on unfiltered is
this defect restored silently on the day somebody renames a selector.

**Not a silent filter.** The step-1 table and `open_case` resolve through the one
filter, so an excluded bill is visibly absent rather than dropped behind a
clerk's back. `scope_table` also publishes **`narrowed_by`**, naming which
narrowings ran — because a `single` scope is narrowed by neither, and a table
with no exclusions in it cannot otherwise be told from one where exclusion does
not run (hard-won law 7's fifth shape).

---

## Ruling 2 · `DEF-BIL-5360` — the capped month is excluded, the case proceeds

> *"in such sitution 6 bills only ; 7th is not valid case"*

`refuse_upward_beyond_window` is split: **`beyond_backbill_window`** makes the
same test and returns **figures** (`code`, `months`, `window_months`,
`period_end`, `delta`, `currency`) or `None`; the raising form is a thin wrapper
on it, so neither restates the test. `open_case` reads the dict and leaves the
bill out.

**Worked, and it is p137's own case:** seven monthly bills January–July 2026
judged on **15 February 2027** against the tenant's default **12-month** window.
January ended **13** months before. **Six proceed; the seventh is excluded**,
and travels on `preview["excluded"]` → the case detail's `excluded` → the screen.

**The cap did not move.** `BR-BIL-018`, the tenant's window, **upward only**,
theft exempt, `OQ-104` option A and `OQ-071`/`BR-BIL-019` all stand exactly as
signed. Only the blast radius of the refusal moved, from the case to the bill.

**When nothing survives the case still refuses**, with `br_ref` `BR-BIL-018`
unchanged so the API maps it as before — which is the same answer for a one-bill
case whose one bill is capped, so the single path needs no branch of its own.

**Rule 7 is honoured on the exclusions too:** `audit_log` records how many bills
were excluded **and their bill numbers**, because what a case did *not* take is
part of what an auditor needs.

`preview_hash` deliberately covers the **pinned** bills and not the exclusions —
`BR-BIL-044` binds an approval to the artifact that will execute, and an excluded
bill is not in it.

---

## Ruling 3 · `BR-BIL-1046` — the months are a consecutive run

> *"we take consicative bills ; not like in 24 months - latest 12 and then 18
> one - 18th is not valid and it will not be taken into processing at all"*

New rule, written into `04-docs/05-modules/07-billing/02-business-rules.md` this
commit, dated, quoting the PO, cross-referenced to the decision log. **The id was
taken by hand as the billing register's maximum + 1** (`BR-BIL-1045` → `1046`);
there is no `BR` family in `allocate.py`, and the maximum was read from the rules
file and cross-checked repo-wide.

The run kept ends at the account's **most recent** bill in scope; the walk goes
back and stops at the first hole. Judged **per account**. Applied in
`resolve_scope_queryset`, so step 1 shows what step 2 pins.

### Two judgments where the rules ran out — decided, not asked (law 13)

`12-governance/02-decision-log.md` and `01-open-questions.md` were grepped for
*consecutive*, *contiguous* and *unbroken run* first. Nothing had been ruled.

**(1) The hole is measured against the PERIOD, never the calendar. Two periods
are consecutive when the gap between them is less than HALF a billing period.**
A cycle here may be Daily · Weekly · Fortnightly · Monthly · Bimonthly ·
Quarterly · Semiannual or Annual, so a *"one month"* threshold would read every
quarterly account as one long gap and refuse corrections nobody asked to refuse.
Half rather than a whole period because a missing bill leaves a hole one period
**minus a day** wide, so a whole-period threshold could never fire — and half
also absorbs the two or three days a move-in or a final bill puts on a boundary.

| worked case | hole | shortest period | verdict |
|---|---|---|---|
| billed to 31 Aug, next from 1 Sep | 0 days | 31 | one run |
| billed to 31 Aug, next from 3 Sep (move-in wobble) | 2 days | 31 | one run |
| billed to 31 Aug, next from 1 Oct | 30 days | 31 | **September is a gap** |
| quarterly, to 31 Mar then from 1 Apr | 0 days | 90 | one run |
| quarterly, to 31 Mar then from 1 Jul | 91 days | 90 | **a gap** |

**(2) Why a gap is a gap is not asked.** An account with no bill for a month
because it was closed and reopened, and one whose middle months are already
`corrected` and so outside the correctable set, are the same shape to this rule.
Telling them apart needs a second cross-module read at selection time to reach an
outcome that is never safer, and the conservative answer — take the recent run,
leave the older one to its own case over its own date range — cannot overbill
anybody and loses no month.

### Cost, stated rather than hidden

Contiguity is not a predicate a row can answer about itself, so there is no
`WHERE` clause for it. `_narrow_to_the_consecutive_run` reads **four scalar
columns** over the scope (`id`, `account_id`, `period_start`, `period_end`) and
excludes the gapped ids — typically none. Applying it inside `open_case` instead
would have been free, and was rejected: the PO said an excluded period is *"not
offered"*, and the only place a clerk is offered anything is the step-1 table.

---

## What the record got wrong, found by checking the rule against the code

**The decision log and the lane brief both name
`corrections._refuse_outside_backbill_window`. There is no such function.** It is
`corrections.refuse_upward_beyond_window`, at the line the brief quotes. The
citation never dangled into nothing — it simply names a function that does not
exist, so a grep for it returns zero and reads as *"already removed"*. Recorded
here rather than silently worked around.

---

## Proof

### Red first, in the harness that runs them

`tests/test_cr101_lane_k_which_bills_a_bulk_correction_takes.py` — 20 cases — run
against the tip **`a5374d48`** extracted into a scratch tree (`git archive`, the
file copied in, the same `pytest` from the same venv):

**18 of 20 failed**, each naming its own defect:

```
tc1  AssertionError: the closed account's bill is not in the billable set … assert [] == ['BL-K1-000001']
tc4  KeyError: 'narrowed_by'
tc6  AttributeError: billable_accounts
tc7  BillingRuleError: this correction adds 40.00 USD to a period that ended 13 months ago …
tc9  KeyError: 'excluded'
tc10 the twelve consecutive months, and only those: [… 13 numbers …]
tc12 a missing quarter is a gap, so only the quarter after it is taken
tc15 AttributeError: module 'apps.billing.bulk_corrections' has no attribute '_periods_are_consecutive'
```

**The two that passed are the two *this must NOT change* guards** — an unbroken
run is taken whole, and a clerk naming a bill behind a gap still gets it. A
regression guard that is green before and after is the right shape; a guard that
is red before is a feature test. Both kinds are in the file on purpose.

The three screen cases were proved red through `npx vitest run` — the harness
that runs them — by deleting the row: **3 of 24 failed** (TC-D3.3 on the row
count, TC-D3.3b on the row being absent, TC-D3.3c on the zero state).

### Green, and what else was run

| Suite | Result |
|---|---|
| the 20 new backend cases | **20 passed** |
| the six correction suites **+ `tests/golden`** | **119 passed**, 3 skipped, 1 xfailed — **no signed money figure moved** |
| `FixWhatStepBulk.dom.test.tsx` + `routeBUtilities.test.ts` | **35 passed** |
| `npx tsc --noEmit` | proved able to fail (see reds below) |
| `npx vite build` | **built in 20.03s** — the product builds |
| the browser walk | **0 problems** at 1440 and 1280 |

### The shared-fixture change, measured rather than assumed

`tests/test_w3_billing_models.an_account` took
`AccountStatus.objects.filter(tenant=tenant).first()`, and `AccountStatus`
declares **no `Meta.ordering`** — so *first* is whatever the database hands back,
a `pending_activation` row (class `non_billable`) on this tenant. **Every account
in every billing test was in an arbitrary billability state**, invisible while
nothing read that state. The moment `resolve_scope_queryset` started asking, six
existing cases in two files resolved to zero bills, correctly.

Pinned to `active` with a fallback. **260 test files use that helper**, so the
blast radius was measured rather than reasoned about: the nine
billability-sensitive suites were run on this tree and on `a5374d48`, same
command, same harness.

| | |
|---|---|
| **new failures my change caused** | **0** |
| failing in both (pre-existing) | 4 |
| red on the tip, green here | 21 |

⚠ **The 21 are not a claim that this lane fixed 21 tests.** On the tip they fail
with `kombu … Error 111 connecting to localhost:6379` — no broker runs in this
container — because a `pending_activation` account being activated by a move-in
dispatches a notification. Pinning the status avoids that path. It is an
environment absence, not a product failure, and is written this way so nobody
reads a green as more than it is.

### Reds I did not cause, dated

* **`npx tsc --noEmit`: one error**, `pastBillingRuns.dom.test.tsx(241,11): error TS2322: Type 'false' is not assignable to type 'true'`. It is **lane I's deliberate tripwire**, which fires the day `PastRunRow` carries money — its own comment says so. Both that file and `PastBillingRunsPanel.tsx` are **unmodified in this worktree**, and the tripwire arrived with **`93afce58` (2026-09-15)**. Left alone: flipping the const would be editing a baseline to go green, and drawing the VALUE column is that lane's work. **`npx vite build` succeeds**, so this is a failing check (§9), not a broken build (§10).
* **Four backend cases fail on this tree AND on `a5374d48`**, which dates them by measurement rather than by claim: `test_us_bil_004_tc3`, `test_us_bil_004_tc4`, `test_us_bil_010_tc8`, `test_us_cus_004_tc1`.

### A trap in the proof itself, worth more than the fix

The venv carries an **editable-install finder pointing at the MAIN checkout**
(`__editable__.smartbillhub-*.pth`). A probe script run from the scratchpad
therefore imports whichever checkout that finder names — **not the worktree you
are editing**. The first *"after"* run of the reproduction executed the tip's
code from a tree that held the fix and reported the defect still present.

**Run a probe as `python -c "exec(open(…).read())"` from the worktree's
`06-backend`, and print `module.__file__` before believing any before/after.**
The final proof does exactly that and names the file it ran.

---

## The browser walk

`10-scripts/cr101_lane_k_excluded_row_walkthrough.mjs`, at **1440 and 1280**,
against a real PostgreSQL tenant with the deployed join (Django on :8007, the
built SPA served by `server.mjs` on :8087). **0 problems.**

```
✓ 1440: DEF-BIL-5377 — the case opened over a run holding a closed account's bill
✓ 1440: the case pinned 38 bills
  group 3: 3 ROWS THAT NEED A HUMAN EYE Bills | Already paid in full 36 List them |
           Posting period is closed 0 | Nets to zero 38 List them | Asks for more 0 |
           Beyond the back-bill cap 0
✓ 1440: DEF-BIL-5360 — p137's fifth row is drawn
✓ 1440: no rule id or internal code in group 3
✓ 1440: no horizontal scroll
✓ 1440: the case was abandoned, so its bills are free
```

**38, where the run holds 39.** That is `DEF-BIL-5377` fixed, read off the
running product rather than off a test.

Lane D's own `cr101_fix_a_bill_step2_bulk_walkthrough.mjs` was re-run too and
reports **0 problems** at both widths — it had reported 2 before, both *"26.3:
the case would not open"*. ⚠ **That was NOT this defect and the distinction
matters:** the refusal was *"this scope matches no issued bills"*, because the
script picks the first run in the dropdown and two of this tenant's four runs
carry no correctable bills. Passing `RUN_ID` for `RUN-0001` is what makes 26.3
walkable; the script already supported it.

### The demo tenant was left as it was found

Every case this lane opened was **rolled back or abandoned**. Counted after:
**0 cases in any state but `done`**. The tenant grew from 40 cases to 58 during
the session; the new ones are **single/goodwill cases belonging to a sibling
lane**, and the one cycle-scoped case predates this lane (created 12:51, class D,
already closed by the orchestrator).

---

## What was NOT built, and why

* **The row's POPULATED state was never seen in a browser.** A real excluded bill
  needs an upward re-price on a period older than the tenant's window, and the
  demo tenant's bills are recent and re-price flat — the walk shows the row at
  **0**. The populated state is held by `FixWhatStepBulk.dom.test.tsx` TC-D3.3b
  against a served payload. Named here rather than left to look covered.
* **The per-bill CHECKBOX p136 draws on 26.2.** Lane D's measurement still holds
  for that half: the ruling excludes a capped bill **by the rule**, it does not
  let a clerk hand-pick which months a case takes — and `BR-BIL-1046` says the
  months are a consecutive run rather than a set someone ticks.
* **`DEF-BIL-5361`** (a case serves every pinned bill in one unpaginated
  response) is **left open**. This lane worked in that code and did not widen its
  scope to fix it. ⚠ **It did not become cheaper to page, and the honest reason
  is that it got slightly harder:** `preview["excluded"]` is a second unpaginated
  list on the same payload, bounded by how many bills the cap removed. On a T5
  batch that is small in practice and unbounded in principle, which is the same
  shape as the defect already filed.
* **A version bump and a `CHANGELOG` row** — the orchestrator does those when the
  wave lands. The sentence is in the lane report.

## One divergence from the drawing, stated rather than followed silently

p137 draws **four** rows in group 3 — *Already paid in full · Posting period is
closed · Beyond the 12-month cap · Nets to zero*. The screen now shows **five**:
those four plus **_Asks for more_**, which lane D added from the server's fourth
warning code. This lane added only the drawn row that was missing and left lane
D's addition alone. The group is therefore a **superset** of the drawing, not a
contradiction of it, and the extra row is a real warning the server raises.

The label reads **_Beyond the back-bill cap_** with no figure, or **_Beyond the
{n}-month cap_** where the server served a window — **never the drawing's
`12`**, which is B14 rule 37: a figure in a wireframe is an illustration, never a
fact to build to.

## The review row

`12-governance/09-human-review-ledger.md` carries this lane's row, **HUMAN-REVIEW-PENDING**.
It states in plain English, with figures and no ids, the two things that changed
for a clerk (79 refused → 77 offered; seven months → six done and one named) and
the **two judgments a reviewer is asked to agree or disagree with** — the
half-a-billing-period gap test, and not asking why a gap is there. A signature
covers only what was shown, so nothing else on these files is put up.

## Screenshots

`/tmp/…/scratchpad/lane-K-shots/`

| file | what it shows |
|---|---|
| `lane-K-group3-1440.png` · `lane-K-group3-1280.png` | **group 3 with the new fifth row**, both widths |
| `step2-batch-1440.png` · `step2-batch-1280.png` | 26.3 whole, from lane D's walk, now opening at 38 bills |
| `step2-batch-listed-1440.png` · `step2-batch-listed-1280.png` | `List them` filtering the collapsed list |
| `step2-months-1440.png` · `step2-months-1280.png` | 26.2, unchanged by this lane |
