# CR-094-BRC01 · The Accounts menu, read against its blueprint

**Raised:** 2026-09-12 · **Branch block:** `BRC01` · **Status:** step 1 running

**PO verbatim:** *"We have to run write a new CR - extract all screens and run
step1 and 2 - there will be maintence as well as new screens in this ; it is PDF
file"*, then *"yes go ahead - extract all screens and run step 1"*.

**Source:** `05-prototype/02 Accounts Menu Blueprint.pdf`, 242 pages, pinned at
commit `033981d4f`, sha256 `c8d596bb505f5020ce4b9474…`. The screen index built
from it is `04-docs/05-modules/03-customers/08-screen-layouts.md`.

---

## 0 · STEP 0 — IS THE PACKET CURRENT? YES, AND IT WAS CHECKED RATHER THAN ASSUMED

The blueprint audits **2.234.15, commit `2824c2e5`, 2026-09-10**. The product is
at **2.237.10** — **219 commits later**.

**Measured, not guessed:** across those 219 commits, the whole Accounts surface
(`07-frontend/src/features/customers/` + `06-backend/apps/customers/`) moved by
**6 files, +79 −25**. Five of the six are `<h1>` matcher fixes from **B14 rule 40**
landing this morning; the sixth is `UnitPricingPanel.tsx` (+72/−18).

⚠ **SO THE AUDIT'S READING STILL HOLDS** — but each lane proves its own rows
against the running product, never against this paragraph. That is the discipline
`CR-092` had to learn twice.

### ⚠ ONE RULING CAME OUT OF THIS DOCUMENT BEFORE THE CR DID, AND IS ALREADY LANDED

`DEF-CUS-4996` / `BR-CUS-1046`, pushed as `7dbd15d82` on the PO's instruction
*"record the ruling first"*. **A PO ruling of 2026-09-10 had reached no file in
this repository for two days**, surviving only in the chat and in this PDF:

> *"Whenever any account is created or any entry is created in the system, it
> automatically sorts it by the alphabetical order. It should always sort it by
> the creation order. The new newly created entries should always show on the
> top."*

It **supersedes `BR-CUS-053`'s `default sort name A→Z` clause** and
`ACCOUNT_DEFAULT_SORT = "name"` at `selectors.py:111`. A lane reading the repo in
those two days would have found the alphabetical default ratified and built
exactly what the PO had rejected — with every check green, because the code
matched its rule and cited it by id.

---

## 1 · CLASSIFY — AND IT IS BOTH, WHICH IS WHY THE PO SAID SO

PO: *"there will be maintence as well as new screens in this"*. Correct, and the
routing is per item, not per CR:

**The one question** (`22-product-maintenance-process.md`): ***can a user do this
task in the product today?*** No → BUILD (r11). Yes → MAINTENANCE.

All seventeen routes are live and reachable — the blueprint's own figure is
**0 of 17 naming no door**, so nothing here is a wholly new screen. What splits
the work is the TASK, not the screen:

| routing | what it looks like here |
|---|---|
| **MAINTENANCE** | the list opens on the alphabet · six decimals of money on the screen that takes money · a missing `/` 404ing two paths · dates in a bare text box · a stated absence a screen no longer has |
| **BUILD** | a master-account tab that does not exist · a company naming its master · a work queue after each wizard · documents on an account · reopening a finished import |

⚠ **WHERE IT IS AMBIGUOUS IT IS A DEFECT** — `13-change-process.md` §1, because
filing our own miss as a "change" quietly converts our error into the customer's
new requirement. The blueprint applies the same test to itself and says so.

---

## 2 · WHAT SIGNED STATEMENT IS BEING REVERSED

**One, and it is already recorded and pushed:** `BR-CUS-053`'s default-sort
clause, superseded by `BR-CUS-1046` (§0 above). No ❄️ FROZEN B4/B5 figure is
touched. No money rule moves.

---

## 3 · THE INVENTORY, AS READ

Every figure below was **read off a rendered page**, never off the text layer —
see §3a for why that distinction is not pedantry.

| measure | figure |
|---|---|
| routes behind one sidebar word | **17** |
| drawn in full | 13 of 17 · **2 not drawn** |
| naming no door | **0 of 17** — every screen is reachable |
| journeys walked | 9 of 14 · **5 issues** |
| UI rule violations | **1**, and it is repo-wide (dates) |
| module seams not healthy | **2 of 6** |
| fields served | 17 of 30 |
| cross-module facts | 13 |
| screens not field-traced | **15 of 17** |
| specifications | **17 rows**, ids running to `ACC-S21` — settled 2026-09-12, see §3b |
| remedies drawn | **9** (`R1`…`R9`) |
| out of scope | 6 |

### 3a · ⚠ THE TEXT LAYER OF THIS PDF IS UNSAFE FOR ANY NUMBER, AND THAT IS MEASURED

| what | text layer | image |
|---|---|---|
| prose, labels, headings | reliable | reliable |
| **every digit** | **`&`** — the cover reads `& of &&` | reliable |
| specification ids | **dropped 8 of 21** | reliable |
| figure captions | found **1** | reliable |
| the wireframes | **absent** (vector art) | reliable |

**101 of 242 pages extract under 150 characters and are essentially pure drawing;
46 more are mixed — so 147 pages must be read as images.** A lane quoting a
figure from the text layer is quoting `&`. This is `CR-092`'s *"a description is
not a measurement"* with a mechanical cause instead of a human one.

### 3b · ✅ SETTLED 2026-09-12 — IT IS SEVENTEEN ROWS, AND BOTH EARLIER FIGURES WERE WRONG

Its cover reads **10 specifications**; this CR read its §12 register as **21**.
**Step 1 lane 2 read §12 end to end on the rendered pages 207–209 and counted the
register's own rows: SEVENTEEN.** `ACC-S1` `S2` `S3` `S4` `S5` `S6` `S7` `S8` `S9`
`S10` `S14` `S15` `S16` `S17` `S18` `S20` `S21`.

⚠ **THE `21` WAS THE HIGHEST ID, NOT A COUNT**, and the two differ because the
series is shared between two uses: **`ACC-S11`, `ACC-S12` and `ACC-S13` are §10
FINDING ids** — the alphabetical default, the missing `/`, the six decimals of
money — with no register row, and **`ACC-S19` appears nowhere in the document.**
The register's own explainer box is a third wrong figure: *"`ACC-S1`…`ACC-S10` is
a series minted for this document"*, printed above a table that runs to `S21`.

**Quote SEVENTEEN ROWS, IDS RUNNING TO `ACC-S21`, and say it came from counting
§12's rows.** `DEF-GOV-5007`; `08-screen-layouts.md` corrected in the same commit.
**Ten of the seventeen name screen 02**; `ACC-S4` (dates) does not.

---

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

**No lane is live anywhere in this repository.** The three `CR-092` wave C lanes
were killed by a container restart, their work was rescued and pushed
(`18f679cb3`, `8e9bf7b05`), and the tree is clean at `7dbd15d82`. **So this CR
starts with no file contention at all** — the first time in this session that has
been true.

⚠ **`CR-093-BRC01` IS OPEN AND TOUCHES THESE SCREENS.** Its four remaining
shared-component items — the sort's third click, the pager, the row-action cap,
the KPI gap — all reach the accounts list. **Neither CR may fix the other's
rows**; where a lane here meets one, it states it and does not build it.

---

## 5 · STEP 1 — WHAT IT DOES, AND WHAT IT MUST NOT DO

**Step 1 classifies; step 2 fixes.** Five lanes, split by the blueprint's own
sections so no two lanes read the same pages:

| lane | screens | pages |
|---|---|---|
| 1 | the register — Accounts list + its seven sibling tabs | p3–5 |
| 2 | **Account detail** — every tab and panel | p6–59 |
| 3 | starting service — new account, both move-ins, request capture, new connect | p60–97 |
| 4 | ending service — both move-outs, close-out, transfer, disconnect | p98–131 |
| 5 | money and the queue — change plan, payment plan, import, requests list + detail | p132–148 |

**Every lane reads its own pages as IMAGES**, reads §10's remedies for its
screens (p150–206) and §12's register (p207–209), and produces rows — **it fixes
nothing.**

⚠ **THE THREE THINGS A STEP 1 LANE MUST NOT DO**, each learned from `CR-092`:
**(a)** quote a figure it has not measured; **(b)** file a finding that is really
a deliberate, registered refusal — *a held control and a broken control look
identical on screen*; **(c)** resolve an open question by choosing a value.

---

## 6 · VERSION AND ROLLBACK

Step 1 writes documents and register rows only; it ships no version. Step 2
carries its own bumps. **Rollback for step 1 is the revert of its commits** —
nothing it produces is read by running code.

---

## 7 · STEP 2 · WAVE G — COMPLAINTS AND SERVICES (built 2026-09-12, `2.239.7`)

**The capability:** two new tabs in the register's tab strip, and one full-page
intake form behind each. PO rulings, verbatim: *"in the main tab list, add
complaints and services. These two tabs. build their ad form and detail view.
and tables."* · *"A complaint form should be of a staple form and on new page it
should open up. Same for the services"*, confirmed ***"Yes that is correct"*** ·
folded into this CR by ***"(a) Fold into this CR as build items."***

### 7.1 · ⚠ THE TABS ARE ON THE REGISTER, NOT ON THE ACCOUNT DETAIL

*"The main tab list"* names neither screen and both draw a strip. It was read
off the drawing rather than guessed: **page 39's address is
`/:tenant/accounts?tab=complaints`, page 47's is
`/:tenant/accounts?tab=services`**, and the drawn header reads *"10 tabs"*. The
register went from **eight to ten**, the two sitting after the six flow queues
and before `Imports`. **The account detail's twelve tabs are untouched by this
wave.** (The briefing this lane was given said the account detail; the drawing
is the specification and this is the drawing.)

### 7.2 · THE MODEL DECISION, MADE AND RECORDED RATHER THAN ASKED

**A complaint is a WORK ORDER of type `Consumer Complaint`; a service is one of
type `Consumer Services`. No new table.** Full reasoning, evidence and what it
supersedes: `12-governance/02-decision-log.md`, 2026-09-12, *"A COMPLAINT IS A
WORK ORDER, NOT A SERVICE REQUEST"*. ⚠ **It withdraws this session's own earlier
recommendation** (a `class` column on `ServiceRequest`), which was never put to
the PO and was written before the blueprint's §10 was read.

### 7.3 · WHAT WAS REUSED RATHER THAN REBUILT

| the drawing asks for | what serves it |
|---|---|
| the two tables | `GET /work-orders` with its `type` pinned — no new read, no new pager |
| the two forms' write | `POST /work-orders`, *"the ONE raise every door uses"* |
| the step rail, the single-flight commit, the failure-with-state-preserved | `components/WizardFrame` |
| step 1's account search | the shared `AccountFinder` (`DEF-732`'s component) |
| the kinds a clerk picks from | `GET /lookups/work_order_types`, filtered to the heading's children |
| the priority and the response time | `BR-WRK-018`, stamped by the server |
| the detail view | the work order's own page, which the blueprint itself draws |
| the page head | the shared `PageHeader` (B14 rules 2 and 40 — 32px, no wizard exception) |

**Three new front-end files, and two of them are ONE component each used twice**
— `jobIntakeShared.tsx` (the two configurations), `JobQueueTab.tsx` (both
tables), `JobIntakeWizard.tsx` (both forms). PO standing instruction: *"Do all
changes bsed on actual code - also dont create duplcate code"*.

### 7.4 · TWO DEFECTS ON THE CRITICAL PATH, FOUND BY BUILDING AND FIXED HERE

* **`DEF-WRK-5106`** — `dispatch._apply_filters` matched a job-type HEADING and
  nothing beneath it, so a queue pinned to *Consumer Complaint* returned nothing
  on a utility full of complaints. Red proof, verbatim:
  `assert complaints["total"] == 1` → `E assert 0 == 1`.
* **`DEF-WRK-5109`** — `_resolve_priority` walked no parent, so a job filed under
  a kind with no response time of its own got **no priority and no due date at
  all** — the drawn *Respond by* column empty on nearly every row. Three
  documents asserted the inheritance and none of them was the code (hard-won law
  1). Red proof, verbatim: `assert order.priority_id is not None` →
  `E assert None is not None`.

Both fixed one level deep and as a FALLBACK, never an override, so a gas leak
call-out keeps its own **4 hours** instead of inheriting its heading's 8 — the
figure `OQ-WRK-1765` exists to prevent. **`BR-WRK-026`'s six filters do not
move.**

### 7.5 · A RED THIS WAVE DID NOT CAUSE, DATED

`test_us_wrk_026_tc4_each_of_the_five_chips_narrows_the_list` has been red since
**2026-09-07**, when `work/0023` deactivated eight seed types under `BR-WRK-058`
and its fixture kept raising *Leak investigation*. `DEF-WRK-5108`, filed and
**not** fixed here.

### 7.6 · WHAT IS OWED, EACH WITH ITS REASON

**`work_orders` has no column for any of these, and a field with nowhere to store
its value is dead UI:** the reporter's name and phone (page 41's *Who told us*),
the complaint's own words, an attachment, and a cause/outcome category (page 42
states that gap itself). **The service form's drawn fifth step, `Service fees`,
is NOT built** — page 219 calls it *"a proposal"* on the SERVICE REQUEST's fee
model, and a work order carries no price, so the form is FOUR steps and nothing
on either screen mentions a fee. Also owed: the drawn `CUSTOMER` column (the row
serves `{id, account_no}` only), the four KPI tiles (each is an aggregate and
A11's envelope carries none), and the `Resolved` / `All` segments (the route
serves the OPEN window only).

### 7.7 · VERSION AND ROLLBACK

`2.239.7` in all three places. **Rollback is the revert of this wave's commits:**
the two tab ids leave `ACCOUNTS_TAB_IDS`, the two routes leave `App.tsx`, and the
two backend fixes revert to the prior behaviour — which returns the empty queue
and the blank response time, so the defect rows stay open rather than being
closed by the revert.

---

## 8 · STEP 2 · WAVE I — `ACC-S8`, AN ACCOUNT CAN HOLD A DOCUMENT (built 2026-09-12, `2.239.10`)

**The commitment, verbatim from §12's own card:** *"An account can hold a
document."*

**What step 1 measured (lane 2, finding F10):** *"An account can hold no
document. `BR-CUS-036` is CONFIRMED and names an `account_documents` table;
neither the table nor an upload endpoint exists, and the tab draws five column
heads over the stated absence."* Classified **BUILD** with no defect row,
because *"a confirmed rule that was never implemented is unbuilt work, not a
defect"* — and that classification is confirmed rather than revisited here.

**`BR-CUS-036` was CONFIRMED in the PO closure batch of 2026-08-08 and nothing
implemented it for thirty-five days.** That is the shape `DEF-2505` already
named once — *"the PO's ruling did not create this requirement; it restated one
signed three weeks ago that nobody built"* — and no gate in this repo compares a
ratified rule against the code that must implement it.

### 8.1 · WHAT WAS REUSED RATHER THAN BUILT — the PO's standing instruction, applied

PO, verbatim, binding this CR: ***"Do all changes based on actual code — also
don't create duplicate code."***

`apps/tenancy/document_store.py` has existed since `CR-049` task 1 and already
does every hard part: the object store behind a seam, the sha256 written and
re-checked on the way back, `NFR-35`'s seven-year object lock, the write-once
trigger, and the RLS-scoped read that is the **only** way a storage key can ever
be learned. **This wave adds no second storage path and stores no bytes of its
own.** `apps/work/evidence.py` — `CR-070` wave K's photograph upload — is the
worked precedent for the shape and is followed function for function.

### 8.2 · ⚠ THE ONE REAL DESIGN DECISION, AND `tenancy/0040` HAD ALREADY FOUND IT ONCE

`uq_stored_documents_filed` allows **one** artefact per
`(tenant, source_type, source_id, content_type)` where the channel is NULL. So
filing under `SOURCE_CUSTOMER_ACCOUNT` — the value whose own comment reads
*"account documents, certificates"* — works for the FIRST document on an account
and **the database refuses the second `application/pdf`**.

**The constraint is right and was NOT widened.** Its own docstring gives the
reason and the reason is about RENDERINGS: a bill's PDF and its HTML are two
representations of one document, and a chooser between them would be a re-render
wearing a different coat. That is exactly right about a bill and it does not
describe a filing cabinet — a signed lease, a scan of a licence and a landlord's
letter are three PDFs on one account and none of them is a copy of the account.

So `tenancy/0044` adds a **ninth** source type, `account_document`, and a
document's `source_id` is its own `account_documents.id`. That is
`tenancy/0040`'s finding — *"nine photographs are not nine renderings of a work
order"* — applied a second time rather than rediscovered by a clerk.

**Proved by breaking it:** with the obvious source type, the second-pdf case
fails on `UNIQUE constraint failed: stored_documents.tenant_id,
stored_documents.source_type, stored_documents.source_id,
stored_documents.content_type`.

### 8.3 · WHAT THE RULE NAMES AND WHAT WAS BUILT

`BR-CUS-036` names *"name, type from lookup System/Contract/KYC/Payment/
Correspondence, uploader, size, storage ref"*. The **type** is a CHECK
constraint on `account_documents`; the **storage ref** is a foreign key to
`stored_documents`. **`name` and `size` are deliberately NOT columns** — they
are `display_name` and `byte_length` on the immutable row, and a second copy of
a file's own name is a second answer to what it is called.

### 8.4 · THE GUARDS ARE `BR-SHL-031`'s, QUOTED RATHER THAN CHOSEN

PDF/PNG/JPG/CSV → **415** · over **10 MB** → **413** (11b G11's own two rows) ·
*"v1 uploads staff-mediated"* → `POST` takes `AdminOrClerk` while an Executive
may read the tab. Both transport refusals were shown red first, each reporting
`Failed: DID NOT RAISE UploadRefused`.

⚠ **THE MALWARE SCAN IS THE ONE HALF NOT BUILT, AND IT IS REPORTED RATHER THAN
LEFT TO BE NOTICED.** *(History: built 2026-09-13 under `BR-SHL-253`, then SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload) and deleted, `DEF-SHL-6347`.)* There is no scanner in this backend and no seam for one;
`apps/tenancy/logo.py` recorded the identical absence for the tenant logo on
2026-08-11 and it is still true. **An allowlist is not a substitute** — a PDF
carries malware perfectly well. ⚠ **AND THE 10 MB CAP IS A CONSTANT** where the
rule says *"10MB tenant-config"*: no settings family declares the key, and
inventing one is how two spellings of one option appear.

### 8.5 · ⚠ A DRAWING WAS OVERRULED, AND THE DIFFERENCE IS FILED

`ACC-T10` draws the filter chips `All` · `Correspondence` · `Evidence`.
**`Evidence` is not one of `BR-CUS-036`'s five CONFIRMED values.** A wireframe
cannot amend signed law, so the filter offers the five and a test asserts that
the word appears **nowhere** on the tab. This is B14 rule 37's instinct about a
drawn NUMBER applied to a drawn VALUE, and it is recorded in the conformance
file rather than resolved silently in either direction.

**`Export` is not drawn either:** nothing registers this resource with
`POST /exports`, and `BR-SHL-010` keeps an undeclared capability unrendered —
not drawn disabled, which is `BR-SHL-025`'s posture for a control this ROLE
cannot use rather than one the PRODUCT does not have.

### 8.6 · WHAT IS DELIBERATELY ABSENT

**No delete**, no removal column and no removal endpoint. `BR-CUS-036`
audit-locks system and contract documents, `NFR-35` makes the bytes write-once
for seven years, and `ACC-T10` draws no row action at all. A clerk who files the
wrong scan against the wrong account cannot take it back, and **that is put to
the PO in the review-ledger row** rather than solved by adding a button.

### 8.7 · THE AUDIT POSTURE, DECIDED RATHER THAN ASSUMED

Hard rule 7 covers **money** actions and filing a document is not one — no
ledger line moves and no invoice changes — so it compels nothing. Two rows are
written anyway: the store's own `document.stored` about the bytes, and
`customers.account_document.filed` about the filing. A document filed against a
financial record is evidence about that record, and the store's row cannot name
an account because it does not know what one is.

**Hard rule 8 was checked rather than assumed:** `account_documents` declares no
address column and no `lat`/`lng`.

### 8.8 · A KERNEL FOLLOW-UP ARRIVED BECAUSE A SECOND UPLOADER NEEDED IT

`apps/tenancy/api.py` composed the 413/415 envelope by hand and said so in its
own docstring on 2026-08-09: *"Built here because core.errors' handler has no 413
branch and core/ is outside this lane's territory: REPORTED as a kernel
follow-up."* It is `core.errors.http_series_refusal_body` now, and tenancy's
private copy delegates to it rather than being duplicated.

### 8.9 · WALKED IN A BROWSER — 24 CHECKS, 0 FAIL, AT 1280 AND 1440

`10-scripts/cr094_wave_i_documents_walkthrough.mjs`, against live PostgreSQL
with the three migrations applied. **It files a real PDF and reads the row back**
— a walkthrough that only opened the tab would prove the tab renders, and what
`ACC-S8` commits to is that an account can HOLD a document. It also exercises
the **refusal** before the happy path: a `.txt` comes back refused and the
sentence *"Only PDF, PNG, JPG or CSV."* is asserted by name, because an
unresolved `message_key` renders as **nothing at all** and a check that only
looked for "no row was added" would pass over silence.

⚠ **THE FIRST RUN FAILED ONE CHECK AT 1280 AND THE SCREEN WAS RIGHT BOTH
TIMES.** It asserted the five column heads on arrival: that passed at 1440 and
failed at 1280. `BR-SHL-012` replaces the WHOLE table region when a list is
empty, header included — *"never an empty header"* — so on the FIRST width, before
this script had filed anything, there was correctly no header to find, and on
the second the first pass's document was there. **A check whose result depends
on which order the widths ran is not a check**, so the empty state is now
asserted where the list is empty and the heads where rows exist. The instrument
was wrong; the code was not.

### 8.10 · VERSION AND ROLLBACK

`2.239.10` in all three places. **Rollback is the revert of this wave's
commits**, and it is clean in one direction only: the tab returns to its frame
and the two endpoints stop being served, but `tenancy/0044` **refuses to roll
back over live rows** by design — a stored document already filed under
`account_document` could be neither edited nor deleted to make room for the
restored eight-value constraint. So a deployment that has taken a real upload
reverts the CODE and keeps the MIGRATION.

---

## X · `BR-CUS-1047` — PUTTING AN ACCOUNT BACK ON THE RIGHT UNIT (built 2026-09-13, `2.244.0`)

**This wave is numbered `X` and not a letter on purpose: it is not one of the
step-2 waves.** It closes a ruling this CR's own step 1 lane 2 raised, which
closed on 2026-09-12 as `BR-CUS-1047` and then reached no line of code. Nothing
went red when it was answered, because its register row said — correctly —
*"NOTHING IS BLOCKED AND NOTHING IS STUBBED."*

### X.1 · WHAT A CLERK CAN DO THAT THEY COULD NOT

An account opened against the wrong unit had no way back: the only fix was to
close it and open another, losing its number, notes, payments and history to
correct a typo. `POST /accounts/{id}/correct-unit` re-points it — a reason from
a fixed list of three, a supervisor's approval, effective today, issued bills
untouched. On the ruling's own fixture (`ACC-E07`, p185) the plan moves
`SCW-RES v1 → SCM-COM v2`, the base charge `$20.00 → $63.00` a month, and the
five already-issued bills stand.

### X.2 · THE TWO JUDGMENTS, AND NEITHER WENT BACK TO THE PO

Both are in the decision log of 2026-09-13 with their reasoning.

**Who is a supervisor** — `@require_role(SYSTEM_ADMIN, EXECUTIVE)`, because the
PO has answered it twice already and law 13 forbids re-asking: `OQ-042`'s
closure names them verbatim, and A4's signed grid gives `Approve` to those two
and `Request` to a Billing Clerk on `adjustment_approval`.

**What the fixed list is** — DERIVED, not invented: the three doors that write
`accounts.unit_id` are the three ways a record can name the wrong one. None of
them says a customer moved, which is what keeps `BR-CUS-017` intact.

### X.3 · WHAT IS NOT BUILT, NAMED RATHER THAN IMPLIED

**No screen.** `ACC-E07` is not drawn; the capability is API-only today, which
is hard-won law 2 stated rather than hidden. It is not folded into `ACC-S15`'s
edit pencils because a Billing Clerk is refused, so it is a different control
with a different door — and the account screen belonged to `BR-CUS-1053`'s wave
while this ran. The decision log entry of 2026-09-13 lists what that screen must
do, so the next lane does not re-derive it.

**No request-and-approve step** — `OQ-CUS-12355`. A4 gives a clerk `Request`,
and nothing in this product implements a request that waits for an approval.

### X.4 · VERSION AND ROLLBACK

**`2.244.0`** — `07-frontend/package.json`, `package-lock.json`,
`06-backend/pyproject.toml`.

**Rollback is two steps and loses nothing.** (1) Remove the route
`accounts/<str:account_id>/correct-unit` from `apps/customers/api.py`: the
capability disappears and every other account door is untouched, because the
service lives in its own file and nothing else imports it. (2) `customers 0046`
then `0045` reverse cleanly — the table starts empty and takes rows only from
this one path, so a reversal loses only corrections made since the release, and
each of those also wrote an `audit_log` row that the reversal does not touch.

`REFUSED_FIELDS`' three new reasons are prose on a refusal and can stay or go
independently; reverting them only restores the wording that told a clerk the
unit can never change, which stopped being true on 2026-09-12.

### X.5 · PROOF

`06-backend/tests/test_br_cus_1047_unit_correction.py` — 22 cases, all green.
The issued-bill case reads every invoice row of the account before and after and
refuses any difference at all; a Billing Clerk and a field technician are each
refused AND the account re-read to prove the refusal wrote nothing; the old and
new service agreements are asserted to end and start on the same day.
`test_cr094_n_account_edit_scope.py`'s five pinning assertions were FLIPPED, as
their own note asked, and its 21 cases are green. `G46`, `G85` pass; `G15` and
`G32` fail on four keys dated 2026-09-07, none of them this lane's.
