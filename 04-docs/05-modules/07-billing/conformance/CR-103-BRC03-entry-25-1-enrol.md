# §05 entry 25.1 `Enrol an account` — BUILD record

**Track: BUILD (`r11`), not Maintenance.** The maintenance process's one question —
*can a user do this task in the product today?* — is genuinely **yes**: a clerk could
enrol one account from the Budget Bills tab. But `CR-103-BRC03`'s own step-1 record
already classified entries 25–25.4 and settled 25 as maintenance while calling 25.1
*"NOT BUILT … this journey's next wave"*. This is that wave: a screen that does not
exist, at an address that does not exist, so it is built. What it *replaces* inside
the tab is carried as maintenance — reproduce, blast radius, regression — below.

| | |
|---|---|
| Id | `CR-103-BRC03`, continued — this is the same change request's next wave, not a new one |
| Branch | `claude/eager-johnson-r0k88b`, base `0da36511` |
| Drawing | `05-prototype/04 Billing, As Built.pdf` · 14,363,163 bytes · **on this branch**, verified before reading |
| Pages read AS IMAGES (B14 rule 42) | p118–p124 at scale 2. **p122 (head + group 1) and p123 (the whole body) are the screen; p124 is its commentary; p121 is entry 25's table and its `THE CONTROL / WHY NOT` removals.** Nothing was taken from `pdf_text.py` — the brief warned the text layer drops every digit in the mono meta lines, and this screen is almost entirely money |
| Screen | `07-frontend/src/features/billing/BudgetEnrolPage.tsx`, routed at `/:tenant/billing/budget/enrol` |

---

## 1 · WHAT WAS BUILT, AGAINST WHAT IS DRAWN

The four numbered groups, in the drawn order, with the drawn rows.

| Drawn | Built | Note |
|---|---|---|
| Page head `Enrol an account`, `Cancel` top-right, caption *"Nothing is written until you enrol"* | ✔ | `PageHeader` — rule 2 (one header, declared) and rule 40 (32px, and the shipped `<h1 class="text-h2">` proves it) |
| The Billing tab strip, `Budget Bills` active | ✔ | The drawing keeps it; so does the screen |
| `1 WHO` — account picker, *"Search by account, customer or address"* | ✔ | A real picker. It replaces a free-text box asking a clerk to paste a uuid |
| `WHO, AND WHERE` — Account · Where · Services | ✔ 3 rows | |
| `CAN IT BE LEVELLED` — Plan · Status · Already on a level · Open since | ✔ 4 rows | The plan's *"offers budget billing"* half is `OQ-237` and is stated absent |
| `WHAT CHANGES FOR THEM` — Balance now · Autopay · Next bill | ✔ 3 rows | Three sub-facts absent; see §3 |
| The warning block, two rows | ✔ | `ConsequenceBox`, one per fact, each drawn only when its fact is TRUE |
| `2 IS THIS ACCOUNT ELIGIBLE` — `TEST \| THIS ACCOUNT`, two rows | ✔ | Test one is answered; test two is the staff confirmation |
| `3 THE LEVEL` — `BASIS \| AMOUNT`, three rows + override + what they will pay | ✔ | Two of the three AMOUNTs are unpublished; see §3 |
| `4 WHAT HAPPENS NEXT` — three rows | ✔ | |
| Footer sentence · `← Back` · `Enrol at $85.00` | ✔ | The button carries the figure that will really be written |

### ⚠ TEN ROWS ARE DRAWN AND THE DOCUMENT SAYS NINE, TWICE

p123's caption says *"Nine facts"* and p124's first commentary row says *"Nine facts,
in three bands"*. Counted off the image: `WHO, AND WHERE` 3 + `CAN IT BE LEVELLED` 4 +
`WHAT CHANGES FOR THEM` 3 = **10**. Under B14 rule 42 the image is the specification
and the prose is an index, so **ten rows are built**. Step 1 reached the same count
independently at scale 4, which is worth stating: two readings of the same page, the
same answer, and the prose wrong both times. The likeliest reading of the nine is that
the `Account` row echoes the picker above it.

---

## 2 · WHERE THE DRAWING AND OUR UI RULES DISAGREED — RULE 38

This is a FORM. B14 rule 38: *"where a drawing and our UI rules disagree about how a
FORM IS BUILT, the UI rules win … the drawing loses, the divergence is RECORDED in the
conformance file, and nothing is built for it."* Every divergence below is COPY LENGTH
under rule 33. **No drawn fact, row or control was dropped for any of them.**

| D | The drawing | Built | The rule |
|---|---|---|---|
| D1 | Group 1's caption: *"Nine facts, and each one can change the answer. Everything here is read; nothing on this screen edits an account."* | **not rendered** | Rule 33 — RATIONALE (*why the product works this way, why a control is absent*) is **zero words on screen**. It is in the file's docstring and in this record, which is where rule 33 puts it |
| D2 | Group 2's caption: *"Two tests, and both refuse by name…"* | **not rendered** | Rule 33, same clause |
| D3 | Group 3's caption: *"The band is measured against the computed figure, so it does not move when you override."* | **not rendered** | Rule 33, same clause. The INSTRUCTION half — *"Inside the band. Leave it empty to use $78.00."* — is a different kind and survives, recast as the override's own reason |
| D4 | Band heading `CAN IT BE LEVELLED` (4 words) | `Can it level` | Rule 33 — a label or heading is ≤ **3 words** |
| D5 | Band heading `WHAT CHANGES FOR THEM` (4) | `What changes` | Rule 33 |
| D6 | Section heading `IS THIS ACCOUNT ELIGIBLE` (4) | `Eligibility` | Rule 33 |
| D7 | Warning heading `TWO OF THOSE NINE CHANGE WHAT YOU TELL THE CUSTOMER` (10) | tag `TELL THEM` + two titled boxes | Rule 33. It also sidesteps the nine/ten miscount above, which is a happy accident rather than the reason |
| D8 | Row labels `Every bill from 30 Nov`, `If they stop paying` | `Every bill`, `If unpaid` | Rule 33. The dates and conditions move into the value cell, where a fact may run to six words per sentence |
| D9 | Footer *"This writes an enrolment and an event row. Nothing bills yet."* | *"An enrolment is written. Nothing bills yet."* | Rule 33 — a CONSEQUENCE before a commit is ≤6 words per sentence, at most two. *"an event row"* is also a database row, which rule 31 keeps off a clerk's screen |
| D10 | The two warnings, at ~20 words each | two sentences of ≤6 | Rule 33, and **they stay** — they are facts a clerk says out loud, not rationale, and rule 33's own words are *never cut below clarity* |

### ⚠ D11 — THE AUTOPAY WARNING IS WORDED TO WHAT THE PRODUCT DOES, AND THAT IS NOT A LENGTH CUT

The drawing says *"From 30 Nov the amount taken becomes **the level**, not the bill."*
**In this version nothing is taken at all.** `StatusPill`'s `title` prop exists for
precisely this fact — `DEF-644`, whose own note reads *"autopay in this version is 'a
promise recorded, never a charge'… a clerk can switch it on and reasonably expect the
next bill to be taken. It will not be."* Printing the drawn sentence would tell a clerk
money will leave a customer's account when nothing collects.

So the row keeps the established qualifier (`customers.account.pill.autopayOnWhy` —
*"Autopay is recorded, not collected."*) and the warning says the part that is true and
useful: **tell them the amount changes**. This is the one divergence that is not rule 33,
and it is the kind rule 41 would send to the PO — except that the repo already ruled it
once, in `DEF-644`, and law 13 forbids re-asking a settled question.

---

## 3 · THE FIVE THINGS THE DRAWING SHOWS THAT NOTHING SERVES

**No money arithmetic happens in the front end.** Every figure on this screen is a
decimal string the server computed. Five drawn figures are therefore absences with
their reason beside them, each with a filed row:

| Drawn | Why it is not there | Row |
|---|---|---|
| `±30%` band as **`$54.60 – $101.40`** | `budget.override_bounds` is written and tested and its ONLY caller is `validate_override`. No payload carries the range. The PERCENTAGE *is* served (the tenant's `override_bound_pct`) and IS drawn | `DEF-BIL-5312` |
| `12 bills \| $936.00` | The eligibility read serves the twelve per-period actuals and no sum. Summing them here would be a second answer to a figure the server owns — and `compute_level` divides by the tenant's `eligibility_months`, which need not equal the number of actuals read | `DEF-BIL-5313` |
| `$312.40 past due · **34 days**` · `On · **card ending 4218**` · `**30 Nov 2026 · cycle 09-A**` | `aging` is served null with its reason; `autopay` is a bare boolean; an account reaches a cycle by walking unit → route → cycle at bill-run time and no read publishes that chain | `DEF-BIL-5314` |
| `Override the level` → `Enrol at $85.00` in one act | `POST /budget-billing/enrollments` carries no override and `enroll` computes the level itself; an override is a second write and `validate_override` refuses a reason-less one, which the drawing gives no field for | `DEF-BIL-5315` |

**The override box is DRAWN, RENDERED AND GREYED WITH ITS REASON**, which is the
blueprint's own doctrine one page earlier (p121: *"Greyed-with-a-reason tells a clerk to
enrol one at a time; a missing control tells them the product forgot"*). The commit
button names the **computed** figure, because that is what the request will write. A
button naming a number the request does not carry is a customer paying something nobody
agreed.

---

## 4 · WHAT THE BLUEPRINT SAYS THAT THE CODE CONTRADICTS

**p124's own headline row is STALE.** It reads: *"⚠ This is the caller that was missing
— `enroll` is written, tested and had **no caller outside tests** — hard-won law 2. This
form is the whole gap."* **It has had a caller since `budget_api.py` landed**, mounted in
`config/urls.py`, and `BudgetBillsTab` has called it from the tab's own panel. Verified
before building, as the brief asked: `budget_service.enroll` at `budget_service.py:251`,
called from `budget_api.py:651`. The blueprint was drawn 2026-09-12 and the API landed
before it. **The gap was the SCREEN, and only the screen.**

**And a second one, found while replacing that panel:** the tab rendered the server's
`eligible_unavailable` sentence verbatim at a clerk — *"BR-RAT-043 puts budget-billing
eligibility on the rate PLAN and no endpoint publishes that flag (OQ-237)."* Two rule ids
on screen, which B14 rule 31 forbids by name and rule 32 repeats. Filed as
`DEF-BIL-5316` and gone with the panel. A server sentence written for an engineer is not
screen copy.

---

## 5 · MAINTENANCE HALF — WHAT WAS REMOVED, AND THE BLAST RADIUS

**REPRODUCE:** the panel is the one step 1 recorded at `v2.263.0` — `Put a customer on
budget billing`, account field a free-text box reading *"Paste the account's id from its
detail page"*, eligibility read, plan-flag tick, `Put them on budget billing`.

**Removed**, with the two rows it carries:
* `DEF-BIL-5232` (high) — a database id as the visible value of a field. B14 rule 31,
  and the One-time bill tab beside it has picked an account properly all along.
* `DEF-BIL-5261` (low) — the commit button overlapped the checkbox label at 1440. Its
  own prevention note says the fix *"rides that wave rather than patching the current
  stacking"*. **This is that wave**, so it is closed rather than patched.

**BLAST RADIUS, both ways.** What else used what was removed:
* `enrollInBudgetBilling` and `getBudgetEligibility` — the tab was their only caller;
  the new screen is their caller now, so neither becomes dead code.
* `budgetEligibilityKey` — still EXPORTED from the tab and imported by the new screen,
  deliberately, so the two surfaces share one cache key rather than minting a second.
* `OpenBalanceLine` — the tab was one of its callers; `billingOpsShared` keeps it and
  other callers are untouched.
* `budgetBillsTable.dom.test.tsx` — checked: it asserts the TABLE, the KPI tiles and the
  filter chips, and nothing about the enrol panel.
* **`DEF-BIL-5262` is NOT closed by this wave.** It is the override boxes under the
  *table* with no row attached — entry 25's surface, not this form's. Left open on
  purpose; closing it here would be recording a fix that was not made.

**Two ways to enrol would be two answers to one question**, so the panel does not survive
beside the screen that replaces it. The tab now carries `+ Enrol an account` as a LINK —
an address, so middle-click works and a test can assert the door by where it points.

---

## 6 · PROOF

* **`tsc --noEmit` green — and PROVED RED FIRST, in the harness that runs it.** A
  deliberate `const deliberateBreak: number = "law 7 proof"` in the new screen produced
  `src/features/billing/BudgetEnrolPage.tsx(294,9): error TS2322`, exit 2. That matters
  twice over: it proves the checker can fail, and it proves **the new file is inside
  `tsconfig`'s scope**, which a green run alone cannot tell you. The worktree had no
  `node_modules`, so the install was symlinked from the main checkout rather than letting
  `npx` fetch a different TypeScript — CLAUDE.md law 7 names that exact false pass.
* **What would make these checks pass wrongly**, stated per law 7 habit 2:
  * `TC-E7` asserts the absence sentences AND that `0.00` appears nowhere. Without the
    second half it would pass over a screen that rendered a fabricated zero beside a
    correct sentence — which is the actual failure mode, since a `$0.00` looks finished.
  * `TC-E4` strips `<option value="…">` before asserting the uuid is absent. Without the
    strip it would fail on a correct screen; without the assertion it would pass on one
    printing a uuid at a clerk.
  * `TC-E11` asserts the tenant's percentage appears AND that an unreadable settings
    block produces **no** percentage. The first half alone passes on a front end with
    `30` hardcoded, which is what BR-BIL-021 forbids.
  * `TC-E16` asserts the three no-data sentences are DISTINCT. Collapsing them is
    `G122`'s defect — a screen that says the same thing while loading and after a failed
    read cannot tell a clerk which happened.
  * The fixture mounts `/:tenant/billing/budget/enrol` — the REAL pattern. A bare
    `MemoryRouter` leaves every built address `//billing/…`, which `toContain` accepts.
* ⚠ **ELEVEN MIN-WIDTH VARIANTS WERE WRITTEN AND CORRECTED BEFORE THE GATE RAN.**
  The first draft used `sm:flex-row`, `sm:w-48`, `sm:gap-8` and eight more. This theme
  is DESKTOP-FIRST and `tailwind.css` says so in capitals — *"Every responsive rule in
  this product is max-width, so authoring reads `max-lg:grid-cols-1` — NEVER
  `lg:grid-cols-2`"*. The fix is an INVERSION and not a rename: the desktop shape is
  the base rule and the phone shape is `max-sm`. It was found by reading `G107`'s
  baseline detail rather than by waiting for `G107` to fail, which matters because that
  gate's baseline **may fall, never rise** — a new file adding to it is the new file's
  own defect. Eleven to zero, in `c91c6f54`.
* **Gate baseline, dated:** taken in a PRISTINE worktree at `0da36511` before any edit,
  because the first run was taken while this lane's own file was already on disk and was
  therefore not a baseline at all. Any red named in the report is compared against that
  list, not asserted from memory.

---

## 6b · ⚠ THE ONE PROOF THAT WAS NOT PERFORMED — LAW 6, STATED RATHER THAN IMPLIED

**The screen was NOT opened in a browser and diffed against the drawing.** Hard-won
law 6 is explicit that no gate in this repo reads rendered output and that nine defects
in one day were found this way and by nothing else, so this is a real gap and not a
formality.

**Why:** this lane was scoped frontend-only with another lane owning the entire backend
for the hour, and booting a stack means a Django server and a database that lane is
using. The container was additionally carrying ten concurrent gate runs at load average
10 while this work finished.

**What stands in its place, and what it cannot cover.** `tsc` is clean, 679 cases across
46 billing and i18n files pass, and 17 of those cases are this screen's — asserting the
four groups IN ORDER, the ten fact rows, both warnings, the six stated absences, that no
`0.00` is drawn anywhere, and that no database id and no rule id reaches the markup.
That is the CONTENT and the ORDER. **It is not the LOOK**: nothing here has compared a
rendered pixel against p122–p123, so spacing, alignment, the bands' visual weight and
the footer's balance are unverified. `DEF-BIL-5259` is also live — the demo database
holds zero invoices, so no account can reach a computed level and the populated state
could not be driven end to end even with a stack.

**What the next lane should do first:** open `/<tenant>/billing/budget/enrol`, seed an
account with twelve issued bills, and diff it against p122–p123 at 1440 and 1280.

## 6c · ⚠ A NEW FAILURE HID INSIDE AN ALREADY-RED GATE, AND COMPARING GATE IDS MISSED IT

**The first comparison said this wave added nothing, and it was wrong in a way worth
writing down.** The pristine baseline at `0da36511` failed 50 gates; the run after this
wave failed the same 50. Set difference: empty. That reads exactly like a clean result.

**`G44 display-truth` was in both lists, and its RATCHET moved from 29 to 30 — the
new entry was this lane's own.** `VerdictRow`'s last prop was called `amount`, and G44
classifies by FIELD NAME: a prop whose name carries a money token, rendered straight
into a text position, is counted whether or not the value is safe. The value WAS safe —
that prop only ever receives a `MoneyCell`, a `NotHeld` sentence or a bolded verdict,
never a decimal string — **but the gate was right about the name.** A later reader
passing a bare `"78.000000"` into a prop called `amount` is precisely the defect it
guards, so the name was a trap this lane had set for the next one. It is `cell` now,
which is what it actually holds, and G44 is back to 29 with this file absent from its
list.

**THE LESSON IS THE METHOD, NOT THE PROP.** *Was this red before I started* is a
question about a gate ID, and CLAUDE.md law 7 asks it that way — but a gate with a
BANKED NUMBER in it can absorb a new failure without changing its status, and 50 red
gates is where such a number goes to hide. **Compare the ratchet, not the verdict:** on
a gate that was already failing, diff the COUNT in its own message between the baseline
and your run. Here that was one line of output, `29` against `30`.

⚠ **AND THE REPO ALREADY DOES THIS — THE FIRST DRAFT OF THIS PARAGRAPH SAID NOTHING
ELSE WOULD HAVE REPORTED IT, AND THAT WAS WRONG.** `run_gates.py` stores every gate's
DETAIL in `last-run.json`, buckets a gate that is *"still red with different findings"*
as `detail_changed`, and prints the count. It would have named G44 on its own.

**What actually happened is narrower and more useful: the record is deliberately not
committed, so a container's FIRST gate run has nothing to compare against — and every
run in this container was a first run.** The runner said so in its own words: *"since
the last recorded run: NOTHING TO COMPARE — no record existed before this run."* That
line reads like housekeeping and is in fact the comparison switching itself off.

**So the rule for a fresh container is: run the gates TWICE** — once on a pristine tree
at your base, once with your change — and let the runner's own `detail_changed` do the
work, or diff the details by hand as this lane ended up doing. One run is blind to every
ratchet in the suite, and nothing about its output says so.

## 7 · WHAT THIS WAVE DID NOT DO, AND WHY

* **The version was NOT bumped.** The scheme is four literals in lockstep and one of
  them is `06-backend/pyproject.toml`; this lane was instructed to touch nothing under
  `06-backend/`. Bumping three of four makes `G35` red, so the honest choice was to bump
  none and leave `G35` exactly as green as it was. **Step 7 is owed** and is one line in
  each of four files plus a `## [x.y.z]` heading in `CHANGELOG.md`.
* **`S74` — *the Enrol button can enable itself* — is not built.** It is `OQ-237`'s read
  half and building the seam would CHOOSE the answer, which the prime directive forbids.
  The staff confirmation the product already ships is what stands in its place.
* **Bulk enrol (`S75`) is outside this screen entirely**, as step 1 measured.

<!-- lifecycle: VERIFIED-UNRATIFIED · §05 entry 25.1 build lane, 2026-09-15 -->
