# §05 entry 25.3 `Asks` — BUILD record

**Track: BUILD (`r11`).** The maintenance process's one question — *can a user do this task
in the product today?* — is **no**. There is no screen, no address and no endpoint on which a
clerk can see who asked from the portal, so this is a build. What it DEPENDS on, and does not
change, is `customers`' request queue, which already shows these asks as ordinary rows.

| | |
|---|---|
| Id | `CR-103-BRC03`, continued — the same change request's next wave after 25.1 |
| Branch | `claude/eager-johnson-r0k88b`, base **`679329eb`** (the tip when this lane started; the brief named `12b30c99`, which had already moved) |
| Worktree | `/tmp/claude-0/wt-s253-asks`, a `git worktree` at the pinned tip — four other lanes were editing the shared checkout and running the gate suite in it when this lane began (CLAUDE.md law 12's *"cheapest lesson"*) |
| Drawing | `05-prototype/04 Billing, As Built.pdf` · 14,363,163 bytes · sha256 `137a2a48…` · **on this branch**, verified before reading |
| Pages read AS IMAGES (B14 rule 42) | p121–p128 at scale 2. **p126 is entry 25.3's head, its four tiles, group 1 and the top of its table; p127 carries the pager, the warning band and the commentary, then entry 25.4's head; p128 is 25.4's commentary.** Nothing was taken from `pdf_text.py` — this screen is almost entirely money and references, and the brief warns the text layer drops digits in the mono meta lines |
| Screens | **NEW** `07-frontend/src/features/billing/BudgetAsksPage.tsx`, routed at `/:tenant/billing/budget/asks` |
| Version | `2.274.0` — four literals in lockstep, `## [2.274.0]` in `CHANGELOG.md` (G35 PASS, run directly) |

---

## 1 · THE MODULE BOUNDARY — SETTLED BEFORE A LINE WAS WRITTEN

This was the part of the brief most likely to go wrong, so it was decided first and is
asserted by a test rather than described.

| Step | Who runs it | Which table | Read or write |
|---|---|---|---|
| 25.4 *Ask to join level pay* | `portal` → `customers.service_request_service.create_from_portal` | **`customers.service_requests`** (+ `service_request_events`, `audit_log`) | WRITE, through customers' own door |
| **25.3 this screen** | `billing` → `apps/billing/customers_seam.py`, resolved BY NAME at call time | **`customers.service_requests`** | **READ ONLY** |
| 25.1 `Enrol →` | `billing` | **`billing.account_budget_status`** | WRITE |

**Billing owns no ask table and must not grow one.** `BR-CWP-066`: *"a portal ask raises an
ordinary service request, **never a request of a new kind**"*. A `billing.budget_ask` model
would be exactly that new kind, in the module that prices the customer's water — and it would
mean the portal writing a billing row, which B2 §2 forbids outright.

`test_billing_owns_no_ask_table_and_imports_no_customers_module` asserts both halves.

⚠ **AND ITS FIRST DRAFT WAS A CHECK THAT LOOKED AT THE WRONG THING.** It grepped the seam's
source for `"from apps.customers"` — and that file *explains the rule in prose*, so the string
search found the SENTENCE and reported a violation that was not there. It parses the AST now.
Caught by running it, which is the only thing that catches this shape.

---

## 2 · WHAT WAS BUILT, AGAINST WHAT IS DRAWN

| Drawn on p126–p127 | Built | Note |
|---|---|---|
| Page head `Asks from the portal`, `Export` top-right | ✔ head, ✖ Export | See D3 and D7 |
| Caption *"6 customers have asked to level their payments"* | ✔ without the count | D6 — the count cannot be read and `6` is an illustration (rule 37) |
| The Billing tab strip, `Budget Bills` active | ✔ | The drawing keeps it; so does 25.1 |
| Four tiles: `WAITING` · `ELIGIBLE NOW` · `NOT ELIGIBLE` · `ENROLLED THIS MONTH` | ✔ all four, in the drawn order | One real, three stated absent — §3 |
| Group 1 `WHY AN ASK AND NOT AN ENROLMENT`, four rows | **✖ not rendered** | **D1** — the largest divergence, and it is rule 33 |
| Search box · `Eligibility ▾` · `Asked ▾` · `+ Filter ▾` · two icon buttons | **✖ not rendered today** | D7 — furniture over rows that cannot arrive |
| Table: `REFERENCE · ACCOUNT · ASKED · LEVEL THEY WERE SHOWN · LEVEL NOW · ELIGIBLE · action` | ✔ **all seven columns declared**, rendered only once the server stops withholding | §4 |
| `Enrol →` on an eligible row, `Tell them why →` on one that is not | ✔ both, as LINKS with addresses | |
| `Showing 1–6 of 6` · `Rows per page 50 ▾` · `‹ ›` | ✔ via the shared `DataTable` footer | `NFR-3`, paged at the server |
| The warning band *"THE TWO LEVEL COLUMNS ARE NOT A DUPLICATE"* | **✖ not rendered** | **D2** — rule 33, same clause as D1 |
| *"Enrolling closes the request and the customer's portal starts showing their standing."* | ✖ | D5 — it describes a write this screen does not perform yet |

---

## 3 · THE FOUR TILES — ONE REAL FIGURE, AND WHY THE OTHER THREE ARE NOT ZEROS

`ENROLLED THIS MONTH` is **billing's own row and billing's own `enrolled_on` date**, so it is
counted. Measured on the seeded utility with three status rows written deliberately — two
enrolled this month, one on the last day of last month — the tile reads **2**. The last-month
row is what makes that a test rather than a demonstration: without it, an endpoint counting
every enrolment ever would pass.

The other three are all downstream of ONE missing fact (§4), so they share **one sentence**.
Three wordings would read as three problems. `count` is likewise `null` and never `0`.

> **`0` on `WAITING` says *nobody asked*. `null` says *nobody could ask*.** The first is a
> claim about customers and the second is a claim about us, and the drawing's own note is what
> the first one costs: *"A customer who asked online and heard nothing asks again by
> telephone."*

The drawn detail line *"3 from the portal"* is **not served**. Nothing on
`account_budget_status` records where an enrolment came from; rule 37 makes the drawn figure
an illustration, and the tile says the provenance is not held.

---

## 4 · THE THREE FACTS THAT ARE NOWHERE IN THE PRODUCT — `OQ-BIL-12359`

**WORKED, so the gap is concrete.** Nguyen presses *Ask to join level pay* on 7 November and
is shown **$112.00**. The ask lands correctly — an ordinary service request, `SR-26-0087`,
reading *"Asked through the customer portal for help paying on account ACC-10519-C: the
customer would like to level out next year's payments."* Four weeks later a bill lands and the
correct figure is **$119.00**. This screen can show neither, and cannot find the request.

| The column | Why it has no source |
|---|---|
| **which requests are level-pay asks** | The only marker is that English sentence, built from `HARDSHIP_ASK_MARKER` — a constant in **`apps/portal/seams/customers_seam.py`**. Billing may not import portal (B1, `G6`), so matching the prose is not a bad option billing is declining: **it is an option billing does not have.** |
| **the account it is about** | `create_from_portal` says it in its own docstring: *"it links no account and changes none"* (`BR-CWP-026`, CONFIRMED). |
| **the level the customer was shown** | Captured by nothing, anywhere, in any module. And it is not recoverable later — recomputing is precisely what gives `$119.00`. |

⚠ **The third is why this is not a small seam job.** The drawing's whole argument for the
screen is the two level columns side by side.

**Nothing was chosen.** `OQ-BIL-12359` names four options and recommends (a) — three columns
on `customers.service_requests` — **answered in the same breath as `OQ-CWP-1680`**, which asks
for the identical narrowing of `BR-CWP-026` for a different reason. One ruling closes both.

---

## 5 · WHERE THE DRAWING AND B14 DISAGREED — RULE 33, RECORDED, NOT BUILT

**No drawn FACT, ROW or COLUMN was dropped for any of these.** Every one is copy or furniture.

| D | The drawing | Built | The rule |
|---|---|---|---|
| **D1** | Group 1, `WHY AN ASK AND NOT AN ENROLMENT` — four rows: *"The portal may write / rows of exactly six kinds"*, *"What is at stake / Enrolment fixes what somebody pays for a year"*, *"What the portal cannot see / Eligibility rides a rate-plan flag no endpoint publishes"*, *"So the ask is / An ordinary service request"*, then *"The customer asks and a person decides."* | **not rendered at all** | Rule 33 — RATIONALE (*why the product works this way, why a control is absent*) is **zero words on screen**: removed, not shortened. Every one of those five lines answers *why*. They are in `budget_api.py`'s header, in `BudgetAsksPage.tsx`'s header, in the decision log and here |
| **D2** | The warning band *"⚠ THE TWO LEVEL COLUMNS ARE NOT A DUPLICATE — A month can pass between the ask and the enrolment… SR-4468 was shown $112.00 and the correct figure today is $119.00."* | **not rendered** | Rule 33, same clause. It is the REASON the columns exist, not a fact a clerk acts on; the two columns carry the meaning, which is the drawing's own argument for them |
| **D3** | Page-head title `Asks from the portal` (4 words) | `Portal asks` | Rule 33 — a label or heading is ≤ **3 words** |
| **D4** | Column header `LEVEL THEY WERE SHOWN` (4) | `Level shown` | Rule 33 |
| **D5** | *"Enrolling closes the request and the customer's portal starts showing their standing."* | not rendered | Rule 33 (rationale) **and** it is not true yet: nothing closes the request, because closing it is a write into `customers` this module may not make |
| **D6** | Caption *"6 customers have asked to level their payments"* | *"Customers asking for a flat amount"* — no count | Rule 37 — `6` is an illustration of a number this screen cannot read; printing any number would be the `$0.00` defect in words |
| **D7** | The toolbar (search, `Eligibility ▾`, `Asked ▾`, `+ Filter ▾`, two icon buttons) and `Export` | not rendered **while the rows are withheld** | Not a copy rule — hard-won law 2's mirror. A search box a clerk types into that can never match, and an `Export` of nothing, are controls over nothing. They arrive with the rows, because the `DataTable` config that carries them is already written |

⚠ **AND `GapNotes` IS NOT RENDERED HERE THOUGH THE SIBLING TAB SHIPS IT.** The server serves
`unavailable[]` and the screen does not print it: that list explains *why a control is absent*,
which is rule 33's own phrase for zero words. It stays on the wire for support and for the
tests. This is the same split `DEF-BIL-5316` forced on the enrol form one screen along.

⚠ **AND THE NEW `unavailable[].detail` ENTRIES CARRY NO IDS, WHILE THEIR TWO NEIGHBOURS ON THE
SIBLING SCREEN DO.** `BUDGET_UNAVAILABLE`'s existing rows read *"…OQ-237 asks the PO where that
flag is read from"* in the field a clerk reads. Rule 32 forbids that. The two rows added here
put every id on `br_ref` instead, and a test asserts it. **The existing two were not rewritten**
— that is another surface's defect and rewriting it mid-flight is how one lane's fix becomes
another lane's mystery.

---

## 6 · PROOF

### 6a · Backend — nine cases, and every guard shown RED FIRST in the harness that runs it

`cd 06-backend && JOBS_EAGER=false python3.12 -m pytest tests/test_s253_budget_asks.py -q
--reuse-db -p no:randomly` → **9 passed in 17.84s**.

Seven sabotages, each applied to the real implementation and run through `pytest`:

| Break | What went red |
|---|---|
| `count: 0` instead of `None` | `AssertionError: an unreadable queue must not report a count of rows` |
| a different wording for one of the three tiles | `assert 'an ask to le…body checked.' == 'a different … same absence'` |
| an id put into a clerk-facing `detail` | `level_pay_ask_carries_no_route_account_or_level: an id reached clerk-facing copy — put it on br_ref` |
| count every enrolment instead of this month's | `assert 3 == 2` |
| ask the seam for 10,000 rows instead of the page | `assert {'limit': 10000, 'offset': 0} == {'limit': 100, 'offset': 200}` |
| `customers` publishes `level_pay_asks_page` | the hold-expiry test fired, with its instructions |
| the route declared below `<str:account_id>` | `assert {'account_id': 'asks'} == {}` |

⚠ **ONE OF THE SEVEN PASSED ON THE FIRST ATTEMPT AND THE PASS WAS WORTHLESS.** The id-in-copy
sabotage searched for `"The queue cannot be"` where the source says `"the queue cannot be"`, so
**nothing was changed and a green result read exactly like a working check**. Redone with an
assertion that the file actually moved — `REFUSING: the break did not apply — the pass below
would prove nothing` — and it then failed properly. That is law 7's *check that cannot fail*
happening to the PROOF rather than to the check, and it is written down because it would have
been invisible in any report that only listed verdicts.

**Three of the nine were rewritten because they could not have failed correctly**, all found by
running them:

* the route test asserted `match.func.__name__ == "budget_asks"`. DRF's `api_view` wraps every
  view, so that name is `view` for **every** route in the module — a check that cannot tell the
  two routes apart. It proves the static path won **by contrast** now: `asks` captures nothing
  and `not-the-word-asks` captures `account_id`.
* the boundary test grepped prose (§1).
* the paging test asked for `per=25`. `PAGE_SIZES` starts at 50, so `clamp_page_size` raises it
  — the test was asserting the clamp, not the paging. It uses `per=100` and expects
  `offset=200`.

### 6b · Frontend — fourteen cases, `tsc` clean and PROVED ABLE TO FAIL

`npx vitest run src/features/billing/budgetAsksPage.dom.test.tsx` → **14 passed**.
`tsc --noEmit -p tsconfig.json` → clean.

⚠ **`tsc` FOUND THREE REAL ERRORS OF MINE BEFORE IT WAS CLEAN**, which is the point of running
it rather than assuming: a `MoneyCell` handed a `currency` of `string | null` (twice — fixed by
treating a figure whose currency did not travel as ABSENT, CLAUDE.md rule 2, rather than by
casting), and `DataTable`'s `error` prop, which takes `{reason, onRetry}` and not a string. A
fourth followed: `DataTable` requires an `empty` block, which is now supplied **without a CTA**
— nothing a clerk does here creates an ask, so a button would be `DEF-MET-4764`'s live control
onto nothing.

The fixture mounts the **real path pattern** `/:tenant/billing/budget/asks`. A bare
`MemoryRouter` leaves every built address `//billing/…` — a protocol-relative URL that reads as
a perfectly good string to `toContain`, which is how `DEF-CWP-3925` hid eight dead doors.
`TC-A7` asserts the full address INCLUDING the tenant segment and asserts `//requests` is absent.

### 6c · The hold-expiry test, written in the same commit as the hold

`test_hold_expires_when_customers_publishes_the_read` asserts the read is absent **today**. It
is the only test here designed to fail later, and its failure message says what to do: read the
owner's real shape against the documented contract, wire the table, and close `OQ-BIL-12359`
**as a fan-out across its surfaces, not a status edit** (`DEF-WRK-4030`). Proved red by
appending the function to `service_request_reads.py` and watching it fire.

### 6d · Gates — compared by DETAIL, in two worktrees, because the count is the wrong question

A full `run_gates.py` was taken on a **pristine** tree at `679329eb` before any edit: **72
PASS, 51 FAIL, 3 SKIP**. ⚠ **That run's own header read *"since the last recorded run
(2026-09-15T05:07:53Z)"*** — another lane's record, in a shared checkout, which is exactly why
`last-run.json` cannot be trusted for a per-lane comparison.

So the gates that could plausibly move were run in **two `git worktree`s** — one pristine at
`679329eb`, one with this change — through each gate's own `run()`, and the DETAIL STRINGS were
diffed. The runner REFUSES rather than printing an empty line when a gate cannot be loaded or
returns an unexpected shape, because a blank line there reads exactly like *no findings*.

Result in §7 below.

### 6e · ⚠ THE PROOF THAT WAS NOT PERFORMED — LAW 6, STATED RATHER THAN IMPLIED

**The screen was NOT opened in a browser and diffed against p126.** Law 6 is explicit that no
gate reads rendered output and that nine defects in one day were found this way and by nothing
else, so this is a real gap.

**Why:** `G120` reports *"THE APPLICATION WILL NOT START: ModuleNotFoundError: No module named
'rest_framework'"* under the gate runner's interpreter, four sibling lanes were holding the
shared checkout, and the container was at load average 9–10 throughout.

**What stands in its place, and what it cannot cover.** 14 cases assert the head, the four
tiles IN ORDER, the dash-not-zero, the provenance absence, the withheld state drawing no table
furniture, both level columns when rows arrive, the two doors BY ADDRESS, no uuid in text and no
id in copy. That is CONTENT and ORDER. **It is not the LOOK** — nothing has compared a rendered
pixel against p126, so spacing, the tiles' visual weight and the panel's balance are unverified.

**What the next lane should do first:** open `/<tenant>/billing/budget/asks` at 1440 and 1280
and diff it against p126, and check the tile row does not wrap at 1280 with four tiles in it.

---

## 7 · GATE DETAIL, BEFORE AND AFTER

The raw pairs are in `CR-103-BRC03-entry-25-3-gate-detail.txt` beside this file. The two that matter most:

* **`G78 work-writes-nothing-foreign`** — the brief singled this out because a boundary
  violation of mine would hide inside an already-red gate. It is **red in both trees with the
  identical finding**: `06-backend/apps/work/sample_field_work.py:746 imports
  apps.metering.connections outside seams/ (BR-WRK-002)`. One finding before, one finding
  after, same file, same line. **My change touches no `work` file and adds nothing to it.**
* **`G106 cited-ids-exist` CAUGHT A REAL DEFECT OF THIS LANE'S, AND IT IS THE REASON THIS
  COMPARISON WAS WORTH DOING.** The seam's new docstring cited **`DEF-BIL-5327`** — an id
  written into the code BEFORE the allocator had answered — and the number that came back for
  that finding was `DEF-BIL-5331`. ⚠ **`5327` IS A REAL ROW ABOUT A DIFFERENT SUBJECT**
  (`DEF-CWP-5330`, the level-pay document copy), so nothing would have looked broken to a
  reader: a citation pointing at a real row about the wrong thing is `DEF-2804`'s shape, on a
  money-adjacent seam. G106 named it exactly — *"DEF-BIL-5327 is cited at
  06-backend/apps/billing/customers_seam.py:496 and no register ever issued it"* — because the
  module segment `BIL` had never been issued with that number. Corrected, and G106's detail is
  now **byte-identical to the pristine tree's**, verified with `diff`. The lesson is the one
  `14-id-reservations.md` already records in its own words: **cite nothing until the allocator
  has answered.**
* **`G32 refusal-keys`** — red in both trees, **4 unresolved keys before and 4 after**, the same
  four, none of them mine. ⚠ **AND ITS ZERO IS NOT TO BE TRUSTED ANYWAY**: it resolves a
  `message_key` only where the helper is defined in the same file. That is not a risk here for a
  reason worth stating rather than assuming — **`budget_asks` raises no refusal at all.** It
  requires a tenant, reads, and answers; there is no `ValidationError`, no `message_key` and no
  new refusal path anywhere in this wave. The absences it carries are DATA on a 200, not errors.

* **`G20 seam-implementers` WENT PASS → FAIL AND IT WAS MINE, WHICH IS THE GATE WORKING.**
  Declaring `apps.customers.service_request_reads.level_pay_asks_page` as a contract and
  publishing no implementer is precisely what that gate exists to name: *"NO IMPLEMENTER …
  declared at 06-backend/apps/billing/customers_seam.py:508 (prose)"*. The repo already owns the
  mechanism for a contract that is deliberately dark — `seam_known_gaps.txt`, whose own header
  says **"ADDING A ROW IS NOT HOW A FINDING IS CLOSED. The fix is to publish the function in the
  owning module. A row buys time and writes down the price."** The row is parked with
  `absent=apps.customers.service_request_reads.level_pay_asks_page` as its guard, and G20 is PASS
  at **390 contracts, 23 parked** (up from 389 and 22 — so the gate did see the new contract).
  **The park's guard was proved to BITE**: appending the symbol to
  `service_request_reads.py` produced *"STALE PARK line 166: … RESOLVES now — the park has done
  its job; delete the row so the gate guards it again"*, and the file was restored and verified
  by `git diff --stat`. **So the hold has TWO expiry guards, not one** — a merge gate and a test
  — and both were shown red before either was trusted.
* **`G17 duplicate-ids` is red in both trees with the identical finding** (`4497` and three
  others, all carried), so none of this lane's four new ids collides with anything.

---

## 7b · A RED THIS LANE DID NOT CAUSE, DATED RATHER THAN ASSERTED

`npx vitest run src/features/billing` reports **1 failed | 750 passed | 6 todo across 51 files**.
The failure is `oneTimeWizardSteps.test.tsx > the hold expires the moment a step body exists`:

> `OneTimeWhatStep.tsx is built against OneTimeWizardStepProps and no step opens it. Point
> ONE_TIME_WIZARD_BODIES at it and remove its step from HELD_ONE_TIME_STEPS — both in one commit.`

⚠ **DATED, NOT CLAIMED** — CLAUDE.md law 7's first habit, and `DEF-CWP-4187` is what a
confident *"not mine"* costs when two lanes say it and one of them caused it. Two pieces of
evidence, neither of them memory:

1. **It fails identically in a PRISTINE `git worktree` at the same tip `56be25eb`** — 1 failed,
   5 passed, in a tree containing not one byte of this lane's work.
2. `git log -S "OneTimeWhatStep"` dates it to **`a86efb7c`, 2026-09-15, *"CR-108: the one-time
   bill's step two, 'What we bill on', for all six kinds (2.273.0)"*** — a sibling lane on this
   same branch.

**It is that lane's own hold-expiry test firing exactly as designed**: the component landed and
the step that opens it has not been pointed at it yet. That is the mechanism this lane's own
`test_hold_expires_when_customers_publishes_the_read` copies, working on somebody else. It is
theirs to close and is named here so the next reader does not take it for a broken tree.

---

## 8 · WHAT THIS WAVE DID NOT DO, AND WHY

* **It did not answer `OQ-BIL-12359`.** Three of seven columns stay empty. Choosing where the
  facts live would reverse a CONFIRMED rule, which the prime directive and law 13 both forbid.
* **It did not build 25.4's Join.** The contract it can POST to is published (decision log §2)
  and it already exists — `POST /portal/accounts/{id}/help-paying/ask` with `route:
  "level_pay"`. The portal screen is `portal`'s file and `CWP-044`'s wave.
* **It did not fix `DEF-CWP-5330`** (`bring_the_document: true` on a level-pay ask). Filed. It
  is a `portal` file with its own tests, and the fix wants a per-route assertion driven from
  `HARDSHIP_ROUTE_WORDS`' own keys rather than a one-line special case.
* **It did not reopen `OQ-CWP-1568`**, which is CLOSED. `DEF-BIL-5332` records that the drawing
  argues from it as though it were open; the decision log records why the ask shape is still the
  right build today and what would change if the PO wants the direct write.
* **It closed no defect row**, so `G67`'s traceless count is untouched in either direction.

<!-- lifecycle: VERIFIED-UNRATIFIED · §05 entry 25.3 build lane, 2026-09-15 -->
