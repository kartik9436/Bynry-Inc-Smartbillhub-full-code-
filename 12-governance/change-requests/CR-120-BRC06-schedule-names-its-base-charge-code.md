# `CR-120-BRC06` · The rate schedule NAMES its base charge code — a default made explicit, on a money path

| | |
|---|---|
| Raised | 2026-09-19, in the working chat session, after the Product Owner walked the rate schedule wizard (`S11` / `RAT-03`) in the beta |
| Requester | Product Owner |
| Branch | `claude/kind-wozniak-rl0uzt` · block `CR-120`–`CR-124`, suffix `BRC06` (claimed in `14-id-reservations.md` before this file was written) |
| Module | rating (Plans & Rates) · 🔒 rating math |
| Classification | **CHANGE** — argued in §1 rather than assumed, because §1's own rule says an ambiguous item is a DEFECT |
| Version | `2.308.0` |
| Status | **CAPTURED 2026-09-19** |
| ⚠ Read first | **THE SCHEDULE NAMES A CODE. IT DOES NOT HOLD A FIGURE.** `tariff_versions.base_charge` — the retired decimal — stays retired, stays NULL on every schedule this product creates, and is not repurposed. The new column is a FOREIGN KEY to `charges`. Whoever reads this next and reaches for the old column has read it backwards. |

---

## 0 · Capture — the requester's words, verbatim

The Product Owner asked for a base-charge binding on step 1 of the rate schedule wizard. The
route was put back to them as `plan → charge code → base charges`, which is the wording of
their own ruling of 2026-08-31. **They corrected it:**

> *"no this is not correct ; So: plan → rate schedule -> charge code → base charges - this is
> correct"*

Asked whether this reverses `BR-RAT-088`:

> *"we are not bindng base charges in rate schedule - you were taking it default; now we are
> making it explicit it is a same rule - change is default -> expliciate"*

And on the minimum bill:

> *"base will come from base - min we can give in rate schedule - if it is not there then you
> ahve to add it at step 2 - deulta will be zero"*

**Read together, those three sentences say four things:**

1. The **rate schedule NAMES the base charge code.**
2. The **plan reaches the base THROUGH the schedule** it already binds for that service.
3. The **base AMOUNT is still the charge code's** — *"base will come from base"*. Nothing about
   `BR-RAT-088`'s arithmetic moves.
4. The **minimum bill is the SCHEDULE's**, entered at step 2, and **an absent minimum is zero.**

---

## 1 · CLASSIFY — and it is decided deliberately, because the tie goes to DEFECT

`13-change-process.md` §1 says *"when it is ambiguous it is a DEFECT, not a change"*, and its
beta amendment of 2026-09-10 makes that the DEFAULT rather than an edge case, on the Product
Owner's own test: **did the product do what was expected?**

**It did.** The route a bill actually takes today — a schedule for the service, and the base
resolved from the `is_base` charge code narrowed by service, customer class and connection size —
is exactly what `BR-RAT-088` ruled on 2026-08-20 and exactly what the Product Owner confirmed on
2026-09-10 (*"Charge Code -> base charge -> rate schedule -> plans - that is the path"*, decision
log of that day: *"THE MIDDLE STEP IS THE RATE SCHEDULE, AND IT IS A ROUTE RATHER THAN A STORE"*).
No bill is wrong. No screen shows a figure that is not the one that bills.

**So the beta table's third row applies: *"It works as agreed, and now that they have used it
they want it different"* → CHANGE.** And the Product Owner said so themselves in the sentence
that matters most here — *"it is a same rule - change is default -> expliciate"*. They are not
reporting a miss; they are asking for an implicit mechanism to become a stated one.

It is also a **NEW REQUIREMENT** on the first row of the same table: `TariffVersion` has no
charge-code column at all today (`tariff`, `basis_service`, `approved_by` and the identity FKs
are the whole set), so this is a capability that does not exist rather than one that
misbehaves.

⚠ **AND IT CARRIES THE SEVENTH KIND'S FLAG: `screen-shaped`.** It puts a control on step 1 of
`S11`/`RAT-03`, a row on step 5, and a column of attribution on the plan's review. That flag is
a routing obligation and not a fifth category — the drawing file is named in §3.

⚠ **WHAT WOULD HAVE MADE IT A DEFECT, STATED SO THE NEXT READER CAN CHECK THE REASONING RATHER
THAN THE VERDICT:** if the `is_base` lookup were producing a base that DISAGREED with what a
screen shows, that would be our miss and a defect however politely reported. It is not. The
lookup and the screens read one shared resolver today and agree; §6's activation gate exists to
keep them agreeing once a NAMED code can differ from an inferred one.

---

## 2 · WHAT IS BEING REVERSED — quoted, with the supersedes chain

**Nothing signed is reversed. One SENTENCE is corrected, and it is a Product Owner sentence
quoted verbatim inside a 🔒 file.**

| # | Date | What was ruled | Standing after this CR |
|---|---|---|---|
| 1 | — | `BR-RAT-012` · `BR-RAT-027` — the base is *"defined per service within a plan"* | **SUPERSEDED 2026-08-20**, unchanged by this CR |
| 2 | 2026-08-20 | `BR-RAT-088` (closing B1 / `OQ-238`) — **the CHARGE CODE owns the base amount**; `tariff_versions.base_charge` **RETIRED**; `plan_services.base_charge` displays only | **CONFIRMED, NOT TOUCHED.** *"base will come from base"* |
| 3 | 2026-08-31 | PO, verbatim: *"We already agreed that it will be in charge code, per utility services , you ahve to take it from there, and plan will bind it , so plan -> charges code -> base scharges"* | **THE ORDER IS CORRECTED BY THIS CR.** The source and the arithmetic in the same sentence are not |
| 4 | 2026-09-10 | PO, verbatim: *"Charge Code -> base charge -> rate schedule -> plans - that is the path"* — and the decision log's reading: the schedule is the **ROUTE**, *"never a second place to type a figure"* | **CONFIRMED AND MADE EXPLICIT.** This CR builds the route as a stored link. The schedule still types no figure |
| 5 | 2026-09-10 | PO, verbatim: *"set it in rates and use it in plans - thats it - this is rule"* — the minimum bill is the schedule version's, not the plan's (`rating/0030`, `0031`) | **CONFIRMED by *"min we can give in rate schedule"*.** Already built |
| 6 | **2026-09-19** | **PO, verbatim: *"no this is not correct ; So: plan → rate schedule -> charge code → base charges - this is correct"*** | **THIS CR** |

**The one live sentence that is now wrong** is in `06-backend/apps/rating/resolution.py`, in
`resolve_base_charge`'s docstring under the heading *"THE TRAVERSAL, AND THE PRECEDENCE, STATED
ONCE (PO 2026-08-31)"*. It quotes row 3 above and then draws the chain with the schedule absent
from it. **It is amended in place with its supersession stated**, never deleted — a reader
tracing row 3's quotation needs the middle link, which is the discipline `CR-111-BRC04` recorded
for its own ruling 1.

**NO ❄️ FROZEN B4/B5 FIGURE MOVES, AND THAT IS PROVED RATHER THAN ASSERTED.** The base AMOUNT is
the charge code's before and after; the binding changes only WHICH code is asked, and on every
schedule that exists the binding is NULL and the old lookup answers. The proof obligation this
CR accepts is in §5.

---

## 3 · IMPACT — eleven surfaces

| Surface | Answer |
|---|---|
| User stories | `US-RAT-005` (`S11` / `RAT-03`) gains step 1's picker and step 5's row. No story becomes obsolete |
| Business rules | **NEW `BR-RAT-1025`** — the schedule names its base charge code; named first, `is_base` second. `BR-RAT-088` **CONFIRMED-AS-AMENDED** (the route gains a step; the source does not move) |
| Build steps / waves | No order change. Plans & Rates is built; this is a wave inside it |
| Documents | `04-docs/05-modules/04-rating/02-business-rules.md`, the decision log, `09-human-review-ledger.md`, `CHANGELOG.md`, this file |
| Code | 🔒 `apps/rating/resolution.py` · 🔒 `apps/rating/selectors.py` · 🔒 `apps/rating/services.py` · 🔒 `apps/rating/resolution_catalogue.py` · a migration (🔒 migration ordering) · `apps/rating/models.py` · `apps/rating/api.py` · `RateScheduleWizard.tsx` · `RateScheduleDetail.tsx` · `baseCharge.ts` · `endpoints.ts` · the eleven locale catalogues |
| Test cases | New backend suite (the binding, the fallback, the activation refusal) + a front-end DOM suite for the picker and the review row. **The no-movement proof is NOT a test** and deliberately so — see §5 |
| E2E journeys | None asserts the OLD route, because the old route is UNCHANGED for every existing schedule. Nothing should fail correctly here — and that is the claim §5 has to prove |
| Seed data | The demo utility's schedules keep a NULL binding, so the demo still shows the inferred route. A tenant that wants the explicit route sets it on step 1 |
| Open questions | **ANSWERS** nothing outright. **RE-OPENS** nothing. ⚠ **RAISES ONE** — see §9 |
| The demo fixture | Unchanged and still coherent — **measured: 78 accounts, 156 account×service answers, 137 of them resolving a base, identical before and after** (§5) |
| **THE DRAWING** | `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html` — RAT-03's step rail and its `size · base · min · t1 · t2 · t3` matrix. **`05-prototype/03 Plans and Rates, As Built.pdf` is the blueprint and it OWNS layout, copy, flows and states** (`DEF-GOV-5248`); r10 is visual style alone for this module |

---

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

**Nothing billed is wrong. Two things are INCOMPLETE rather than wrong:**

1. **`resolve_base_charge`'s traversal docstring** draws a four-step chain with the schedule
   missing from it (§2). Corrected in the build commit.
2. **Two implementations of `baseChargeFor` exist** — `features/rating/baseCharge.ts` (RAT-02 +
   RAT-03, signature `(charges, service)`) and `features/rating/PlanWizard.tsx:1193` (signature
   `(service, charges)`). They agree today because both do the same `is_base` + service lookup.
   **The moment a schedule can NAME a code they can disagree**, which is exactly the shape
   `baseCharge.ts`'s own docstring was written to prevent (*"Two screens showing one fact is
   exactly where two implementations start disagreeing"*).

**LANES BUILDING RIGHT NOW, and this is the step-4 question that matters here:** a sibling lane
owns `07-frontend/src/features/rating/PlanWizard.tsx` and the eleven locale catalogues, and a
third owns `PlanDetail.tsx`. **The plan-side half of item 2 above is therefore NOT taken in this
CR's first commit** — it is stated here, and §9 records what is owed.

---

## 5 · SIZE IT, AND THE ONE CLAIM THAT MUST BE PROVED

**In plain English, with the figure the Product Owner is being asked to rely on:**

> Today a rate schedule works out its own base charge by looking for the charge code that is
> ticked *"this is the base"* for that service. From this change a schedule can instead SAY which
> code it means, and step 1 of the wizard is where you say it. **If you say nothing, nothing
> changes** — the schedule goes on working it out exactly as it does today.
>
> **The figure, MEASURED rather than promised: the real billing calculation was run for every one
> of the 78 accounts on the sample utility, against both services — 156 answers — on the old code
> and on the new. All 156 are identical.** Not one account's base moved by a cent. No bill moves
> on the day it ships.

**THE DEFAULT-TO-EXPLICIT SHAPE IS WHAT MAKES IT SAFE, and it is three lines:**

* schedule NAMES a code → **that** code is the base. Stated.
* schedule NAMES nothing → today's `is_base` + service lookup, **byte for byte unchanged**.
* therefore **no existing schedule changes behaviour and no bill moves on day one.**

**This is not a new pattern in this repo.** `PlanWizard.lateFeeSourceCharge` is the same
two-tier shape for the same reason — *"Two places a plan can name it, and the order matters:
1. `rate_plans.late_fee_charge` — what the ENGINE actually reads. 2. an attached charge code"* —
and `BR-RAT-1011`/`CR-078` is the ruling behind it.

⚠ **THE FIGURE IS 78 ACCOUNTS AND NOT THE 47 THIS REPO USUALLY QUOTES, AND THE DIFFERENCE IS
STATED RATHER THAN GLOSSED.** This file was DRAFTED saying *"47 ready accounts"*, because that is
the number the register's earlier rows carry for this fixture. **It is the ready-to-bill
population of the July run, and this lane did not re-derive it** — quoting a figure somebody else
measured, for a population nobody had checked was the one under test, is how a worked number stops
meaning anything. What was actually measured is every account against every enabled service: a
SUPERSET of the 47, and a fixed cross-product on purpose, so that an account vanishing from one
side of the comparison is as loud as a figure changing on it.

⚠ **AND THE PROOF IS A CROSS-TREE DIFF, NOT A TEST, BECAUSE A TEST HERE COULD NOT FAIL.** The claim
is a negative — *nothing moved* — and a negative proved by running the NEW code twice passes
whatever the new code does. `10-scripts/cr120_base_route_measure.py` prints one line per
account×service and is run on a worktree pinned at the tip this lane started from AND on this one,
against two clones of the same seeded PostgreSQL; the proof is that the two outputs diff clean. It
also prints its counts AFTER the rows rather than instead of them, so a run that read nothing
cannot look like a healthy estate.

**Not the fast path.** It touches a rule, money and data, so §5's fast path is refused by name.

---

## 6 · EXECUTE — through r11, unchanged

Seven items, and item 6 is the one that keeps the screen and the bill from disagreeing:

| # | Where | What |
|---|---|---|
| 1 | Schedule step 1 (Basics) | Base charge code picker — **searchable**, showing code and name. **NOT the amount**: the Product Owner said showing the per-size base here is *"not required"* |
| 2 | `TariffVersion` | New **nullable FK to `charges`**. The NULL *is* the fallback, not an oversight |
| 3 | R4 in `resolution.py` | The schedule's named code FIRST; `is_base` + service lookup when NULL. Which route answered is RECORDED on the line, as `base_source` already does |
| 4 | Schedule step 2 (Base rates) | An absent minimum **is zero** — stated, and the reconciliation written into the docstring. See §8 for what was deliberately NOT done |
| 5 | Schedule step 5 (Review & activate) | The bound code, its base figure, and the schedule's minimum |
| 6 | Activation | **REFUSE** when the bound code contradicts what the plan would actually bill |
| 7 | Plan review | Base attribution reads the binding, so the two screens cannot disagree — **owed, see §9** |

---

## 7 · VERSION

**`2.308.0`** — a change bump, from `allocate.py version --bump change` against `2.307.4`,
re-verified at push time.

---

## 8 · THE MINIMUM BILL, AND THE ONE JUDGMENT TAKEN RATHER THAN ASKED

**The Product Owner asked for a default of zero. `RateSizeRow.minimum_bill`'s own docstring
says the opposite in as many words:**

> *"NULL = this size has no minimum bill (electric draws an em-dash for every size in r10's
> matrix). Absent is not zero, here as everywhere in this CR."*

**THEY RECONCILE, AND THE RECONCILIATION IS THE WHOLE ANSWER: A FLOOR OF ZERO AND NO FLOOR
PRODUCE THE IDENTICAL BILL.** A minimum tops a bill UP to itself; a floor of `$0.00` tops
nothing up, and neither does an absent one. That is unlike the BASE one column across, where
`0` means *free* and NULL means *not served* (`CR-013` part 1 / `DEF-277`) — there the two
readings are `$0.00` and a refused bill, which is why absent may never be read as zero THERE.

**SO WHAT IS BUILT IS THE MEANING AND NOT A PRE-FILLED BOX, AND THE REASON IS A MEASUREMENT.**
`RateScheduleDetail`'s matrix renders the minimum as `row.minimumBillDisplay ?? "—"`. A stored
`0.00` therefore **PRINTS as `0.00`**, and r10's electric matrix draws an **em-dash** on every
size. Pre-filling the step-2 box with zero would write a real `0.00` onto every size row a clerk
adds and fill the electric matrix with figures where the agreed drawing has dashes — **a
screen-wide change to a drawn screen, on the strength of a sentence about arithmetic.**

**DECIDED, not asked** (hard-won law 13: a judgment recorded with its reasoning is the
deliverable; a question is the failure to make one): **blank stays blank on screen and MEANS
zero**, said once in the copy and written into both docstrings. The bill is identical either
way, so nothing is at stake in the money — only in what the matrix draws.

⚠ **AND IT IS PUT IN FRONT OF THE PRODUCT OWNER ANYWAY, AS ONE LINE IN THE REVIEW-LEDGER ROW,
because it is the one place this build does not do the literal thing they said.** That is the
opposite of a re-ask: the decision is made, built and recorded, and they can overturn it in a
sentence.

---

## 9 · WHAT IS OWED, AND IT IS NOT CLOSED BY THIS FILE

1. **Item 6 of §6's table — the plan review.** `PlanWizard.tsx` is owned by a sibling lane
   right now (§4). The shared resolver and the served data are built here so the plan CAN read
   the binding; the four-line edit that makes it read one is owed, and until it lands **the plan's
   step-4 base panel infers the code while the schedule may NAME a different one.** The
   activation gate of item 6 is what stops that divergence reaching a bill — it refuses the
   activation rather than letting the two screens disagree — but it does not make the plan
   screen right.
2. **`CR-121`–`CR-124` remain FREE** in this branch's block.
