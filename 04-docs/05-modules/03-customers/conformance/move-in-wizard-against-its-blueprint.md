# The move-in wizard against its blueprint — all six steps, read as images

| | |
|---|---|
| Read | `05-prototype/02 Accounts Menu Blueprint.pdf` — ⚠ **pages 067–073 of the 242-page edition, which are pages 070–076 of the CURRENT 281-page one** (see the note directly below). Rendered at scale 2.6 and 5 and read AS IMAGES (B14 rule 42) |
| Against | `07-frontend/src/features/customers/MoveInWizard.tsx` (1,932 lines) · `06-backend/apps/customers/services.move_in` · `moves.py` · `deposit.py` |
| Product at | `2.311.5` |
| Raised by | the Product Owner, 2026-09-19: *"Find unit → Customer → Start & read → Account preferences → Deposit → Review - it does not match with current product screen"* |
| Status | **ALL SIX STEPS SIGNED OFF** by the PO in this session, one at a time, in their own words — steps 1, 2, 3, 4, 5, 6, plus the draft design and the submit behaviour. |
| ⚠ Read first | **THE STEP NAMES MATCH AND THE CONTENT DOES NOT.** All six rail labels are byte-identical to the drawing, which is why this looked conformant and was not. The divergence is entirely in what each step CONTAINS. |

---

## ⚠ THE BLUEPRINT WAS REPLACED ON 2026-09-19 — THE SIX WIZARD STEPS MOVED BY +3

The PO uploaded a new Accounts blueprint (`74a2e6b52`): **281 pages, up from 242**,
10,282,571 bytes up from 9,067,711. **The six move-in steps moved from p067–p073 to
p070–p076.** Every citation in the step sections below, and in `CR-122-BRC06`, names the
OLD numbering. ⚠ **The shift is NOT uniform** — the Move-ins list and the move record
moved by FOUR, and the `BUILT 2026-09-19` section at the foot of this file states their
own numbers. **Apply +3 to the WIZARD steps only.**

**The READINGS below are unaffected and were re-checked rather than assumed.** All six
steps were re-rendered from the current file at scale 2.6 and 5 and read again as images:

| What was checked in the 281-page edition | Verdict |
|---|---|
| Step 2 (now **p071**) — eleven fields, no document control | **unchanged**, which is why `CR-122-BRC06` is a CHANGE and not a defect |
| Step 3 (now **p072**) — `METER · READING · READ DATE · COULD NOT BE READ`, the water row dated 04/29 against a 05/02 move, the demand row `—` and ticked | **unchanged** |
| Step 4 (now **p072–p073**) — delivery, paying, tax, language; **no discount section** | **unchanged**; the discount claim is the PO's addition, not the drawing's |
| Step 5 (now **p073–p074**) — the clearing-date box and its red sentence carrying **`$0.00`** | **unchanged** |
| Step 6 (now **p074**) — the reads read back with `READ DATE` and `HOW` | **unchanged** |

**What actually changed is a PROVENANCE BANNER on every frame**, which is where the extra
text came from: *"REDESIGN — PUBLISHED 2026-09-11, DRAWN TO THE RULINGS IN §13, NEVER
BUILT. TODAY: the product's move-in wizard has FIVE steps and takes no deposit; these six
add the deposit step and a read date."*

⚠ **SO NOTHING BUILT UNDER `CR-122-BRC06` CONTRADICTS THE CURRENT DRAWING.** The page
numbers are corrected in the header above and left in place in the body, because
renumbering forty citations is the mass rewrite law 11 exists to prevent — **read the
header's +3 and apply it**.

---

## The one-line summary

**The drawing puts twenty facts on step 1, where a clerk decides. The product puts five there,
and mounts the rest on steps 3 and 4 — after the decision.** Almost none of this is missing
data: `GET /units/{id}/pricing` and `GET /units/{id}/assets` are both already built, already
mounted, and already serving every figure the drawing draws. They are on the wrong screens.

## The four findings that are not layout

**1 · `Save & exit` writes NOTHING, and there is no draft.** Not a paraphrase — the file says
so in its own words: *"`Save & exit` leaves quietly and writes NOTHING: the step is in the
address bar and that is all it relies on."* `Park` renders DISABLED beside it because
`waiting_on` / `park_note` / `remind_on` are columns on `service_requests` alone and **a
move-in in progress is not a row anywhere**. A clerk who fills in five steps, keys a $150.00
deposit with its receipt number, and presses the button on the page head starts again from
scratch. Nothing warns them.

**2 · NOTHING REACHES THE CUSTOMER.** The commit path was read and contains no message, no
letter, no queue write. The drawing designs **five** for this moment — the welcome carrying the
new account number, the deposit receipt, the service agreement, the opening reads, and a note
that a meter still has to be read — each with a template, a channel and a *when*, and each
tickable. **None of the five exists.** The blueprint's own caption says *"Everything here is
queued, and nothing is sent"*, which was true of the whole product when it was drawn; the PO
stated on 2026-09-17 that email is now configured, so this is buildable rather than blocked.

**3 · THE CLEARING DATE IS A MONEY TRAP AND THE SCREEN IS SILENT ABOUT IT.** A move-in deposit
runs `payments.services.record_payment(purpose="deposit", cleared_at=…)` →
`ledger_seam.post_payment_cleared` → **DR undeposited funds / CR 2300**, and the ledger leg
**waits on the clearing**. Leave `Clearing date` blank and the payment row is real, the cash is
in the drawer, and **the new account reads a deposit of `$0.00`**. The drawing states this on
the step in red. Our step says nothing.

⚠ **A CORRECTION THIS RECORD OWES ITS OWN READER.** An earlier reading of this said
`initial_reads` was *"refused — reads go through metering"*. That conflated two doors. The
refusal entry in `services.py` guards **every door except this one**, and says so in its own
words: *"initial reads are captured on the MOVE-IN flow only"*. The move-in door has accepted
them since 2026-08-26. So the PO's ruling — a clerk types an opening read and it lands in the
reading register — needs **no backend work at all**; the screen simply never offered the input.

**4 · A DISCOUNT CLAIM HAS NOWHERE TO GO ON A MOVE-IN.** Eligibility CRITERIA live on the plan
(`rate_plans.eligibility`, advisory, never gates assignment) and the plan comes from the unit,
so there is nothing to choose. But a CLAIM — `eligibility_claimed` / `eligibility_note`, under
B18 §5.3.4's *"never blocks service — only the discount"* — exists **on `service_requests`
only**. A tenant moving in who is a senior or on a low-income tariff cannot say so in this
flow. Raised with the PO; not built.

**5 · A MOVE-IN CAN ALREADY NAME THE REQUEST IT CAME FROM, AND THE WIZARD HAS NEVER ONCE READ
ONE.** PO ruling, 2026-09-19, verbatim: *"here if move is coming from service request these
details will be filled in"*. The column is not missing — `service_request_id` joined
`MOVE_IN_FIELDS` on 2026-09-15 under `CR-094-BRC01` and the server accepts it today. The front
end has **zero** references to a service request anywhere in its 1,932 lines: nothing sets the
link on the way in and nothing reads the request on the way out. That is hard-won law 2 exactly
— built and not wired — and it is why step 2 asks a clerk to re-key a name, an email, a phone,
a date of birth and two encrypted identifiers that an approved request is already holding.
⚠ **AND IT SETTLES WHERE THE DOCUMENTS COME FROM.** `CR-122-BRC06` asks for document upload on
step 2; the store built on 2026-09-19 is scoped to a service request. If the move-in carries
its request, the documents arrive WITH it and no second store is needed — which is a smaller
change than the one that was asked for, and a better one.

---

## ⚠ WHAT HAS SINCE BEEN BUILT — read this before acting on the five findings above

The findings keep their ORIGINAL wording, because a finding rewritten after the fact
stops being evidence of what was wrong. **Four of the five are now closed**, and a lane
acting on the wording alone would rebuild working code:

| Finding | State |
|---|---|
| **1 · `Save & exit` writes nothing** | **CLOSED.** The wizard writes a draft the moment it OPENS — the same `wizard_parks` row `Park` writes, never a second store — carrying `MVI-26-…` from the moment it exists. ⚠ **The finding's second half was FALSE when written**: `Park` was never disabled; `CR-035` gave it a store on 2026-08-26 |
| **2 · Nothing reaches the customer** | **STILL OPEN.** None of the drawing's five messages exists. This is the largest remaining gap on the screen |
| **3 · The clearing-date trap** | **CLOSED.** The advisory was already built and goes `blocked` on a blank date; what it never said is the thing that bites, so the sentence now names it — *"Blank clearing date holds the deposit. The account reads $0.00 until cleared."* ⚠ That correction reached **English only** for a day; ten catalogues kept the superseded sentence and `depositCapability.tsx` reads the key with no `defaultValue` (`DEF-CUS-5889`, fixed) |
| **4 · A discount claim has nowhere to go** | **CLOSED.** `customers/0057` adds `eligibility_claimed` / `eligibility_note` to `accounts`. One question on step 4, the THREE a person must apply for. ⛔ It gates nothing, grants nothing and enrols nobody — all three proved on real PostgreSQL |
| **5 · The wizard never reads its request** | **CLOSED.** `?request=<id>` fills step 2 once, only where the clerk has typed nothing, and the request's documents ride along read-only (§5 option (a)). ⛔ The two encrypted identifiers are NOT copied |

⚠ **THE CUSTOMER SEARCH IS STILL ITS OWN PIECE AND IS WITH THE PO** — a move-in still
writes a fresh contact row and the server still warns `customer_not_linked` on every one.
**The sentence on step 2 explaining why there is no search is FALSE and has been since
2026-08-11**; it is reported, not edited, and deleting it belongs to that piece.

---

## Step 1 · Find unit — **PO-SIGNED-OFF**

### The search

| Drawing | Product | Front end | Backend |
|---|---|---|---|
| `Search for a vacant unit *` | present **only on the standalone road**; from an account the unit comes from the one being moved out of | ⚠ two different screens | `GET /units?occupancy=vacant` ✅ ; server **refuses** `unit_id` (`BR-CUS-017`) |
| help — *"An address, a unit label or a premises name"* | — | 🔧 add | — |

### The results table

| Drawing column | Product | Front end | Backend |
|---|---|---|---|
| radio select per row | ✅ | ✅ | — |
| `Unit` | ✅ | ✅ | ✅ |
| `Address` | ✅ | ✅ | ✅ walked from premises (hard rule 8) |
| `Type` — `Duplex — half` | 🔧 | 🔧 | ✅ |
| `Services` — chips | ✅ | ✅ | ✅ |
| `Vacant since`, or **`Occupied · A-11455`** in amber | 🔧 | 🔧 | ⚠ unverified |
| `Previous account` | ✅ | ✅ | ✅ |

### The panel — twenty facts in four blocks; the product shows five in one

| Block | Drawing facts | Product | Backend |
|---|---|---|---|
| **The unit** | Unit number · Label · Unit type · Floor · Floor area · Premises · Service address · **Map point (`Reads the building's`)** · Parcel | one combined line | ✅ all served |
| **What it is billed on** | Plan · In force since · Plan locked · **Base charge `$20.00 a month`** · Bill the owner when vacant | Plan only | ✅ `GET /units/{id}/pricing` — **mounted on step 4** |
| **Services and meters** | Services available · a table of Meter · Service · Type · Last read · Read on | services only | ✅ `GET /units/{id}/assets` — **mounted on step 3** |
| **Who was here before** | Previous account · Closed · Vacant since · **Vacant for (`94 days`)** | first two only | ✅ / derived |

Three sentences the drawing carries and the product does not: *"the plan belongs to the unit
and the new account inherits it"* (the product DOES say this) · *"these become the new
occupant's opening reads on step 3"* · *"a long vacancy is worth noticing: nothing has been read
here since January, so the opening reads are three months old"*. And the panel closes with
**"Nothing on this panel is an input."**

⚠ **One line the drawing insists on and nothing in the product says:** *"A unit with no meter
can still be moved into. The wizard does not refuse it. Service starts, nothing can be
measured, and no metered bill can be raised until one is fitted."*

---

## Step 2 · Customer — *"Who is moving in?"*

| Drawing element | Product | Front end | Backend |
|---|---|---|---|
| `Category *` (dropdown) · `Full name *` · `Email` · `Phone` · `Date of birth` · `Customer kind` (`A person · A company`) | built | ✅ | ✅ |
| `Government id` — placeholder *"last four only"* | ⚠ | 🔧 | column exists; the drawing's OWN review reads **`— not captured`** |
| **Identity — stored encrypted** · `SSN` · `Driving licence` | built | ✅ | ✅ encrypted; only the last four leaves the server |
| **Mailing address** · `Address line` · `City / State / Postal` | built | ✅ | ✅ |
| *(not drawn)* | **47 words** explaining why there is no customer search | 🔧 cut — B14 rule 33 puts rationale at zero words on screen | ⚠ **the reason given is known to be false** and was already REPORTED rather than edited |
| **— NEW (PO, 2026-09-19) —** *"if move is coming from service request these details will be filled in"* | never | 🔧 build | ✅ `service_request_id` accepted since 2026-09-15 — **nothing sets it** |
| **— NEW (PO, 2026-09-19) —** | — | documents, as on the request | see `CR-122-BRC06` |

## Step 3 · Start & read

| Drawing element | Product | Front end | Backend |
|---|---|---|---|
| `Moved in on *` with `Earliest start` shown beside it | built | ✅ | ✅ refuses an earlier start — the outgoing account must be billed through the move day |
| **Opening reads** · `Meter` | listed | ✅ | ✅ |
| · `Reading`, prefilled from the outgoing finals | shown | ✅ **BUILT — and the finding above it was WRONG.** ⚠ This row read *"not editable"* until 2026-09-19; **the box has always been an editable input** bound to the same draft the payload is built from, so the PO's ruling was already satisfied for the READING. What was genuinely missing was the per-row `READ DATE` below. **That is the THIRD expired-absence finding on this one screen**, with `initial_reads` and `Park` | ✅ **ACCEPTED** — `initial_reads` is in `MOVE_IN_FIELDS` and commits through `seams.commit_event_reads` (event `move_in`, `BR-MET-128`). **Proved end to end on real PostgreSQL**, not sqlite: `06-backend/tests/test_cr122_brc06_move_in_reads_and_claim.py` |
| · `Read date` — *"every date opens on the move-in day"* | ✅ **BUILT** (`CR-122-BRC06`) | ✅ each row opens on the move day and can be changed. ⚠ **The box SHOWS the move day while the draft holds `""` underneath**, so an untouched row sends NO `read_at` and a clerk who later edits the start date gets readings that follow it, instead of readings frozen to whatever the date was when the table first painted | ✅ per-row dates travel. **Proved on real PostgreSQL**: a row dated 04/29 and a row dated by the 05/02 move land on DIFFERENT days, and the screen→payload join is proved both ways in `moveReadsCapture.test.tsx` |
| · **`Could not be read`**, a tick per register | ✅ **BUILT** | ✅ ticking it CLEARS the value — the two never travel together | ✅ **verified, and the answer is a refusal rather than a post.** On the drawn case the door returns `posted_reads: 0`, names the register, `estimated: false`, `reason: "no_history"` and a `forced_disposition` of **`field_visit`** — nothing is invented and somebody is sent back, which is the drawing's own *"could not be estimated either"* |
| `Bill from` | absent | — | **refused — no column** (`BR-CUS-022`) |
| ⚠ *"Nothing guards the read date"* — duplicate and negative period ARE caught; **nothing checks it against the previous occupant and nothing refuses a date after today** | — | 🔧 | **true, and it is a gap** |
| ⛔ *"A demand register is never estimated, because the charge it drives would be disputed"* | — | 🔧 | ✅ the rule holds |

## Step 4 · Account preferences

| Drawing element | Product | Front end | Backend |
|---|---|---|---|
| ⛔ **`A bill is always printed`** — paperless and text are extra, never instead | built | ✅ | — |
| `Paperless billing` · *"with no email on file this cannot be ticked"* | built | ✅ / 🔧 the condition | ⚠ column may be PROPOSED only |
| `Text reminders` · *"needs a mobile number" · "both start off"* | built | ✅ / 🔧 | ⚠ |
| `Autopay` — **capture only, nothing collects on it** | built | ✅ | stored, collects nothing |
| `Tax exempt` — *"a reference and an expiry are asked the moment it is ticked"* | built | ✅ | ✅ |
| `Preferred language` | built | ✅ | ✅ |
| **Account plan is not asked here or anywhere** — it lives on the unit | same | ✅ | ✅ |
| *(not drawn)* | — | **a discount claim, proposed** | `eligibility_claimed` exists on requests only — see finding 4 |

## Step 5 · Deposit

| Drawing element | Product | Front end | Backend |
|---|---|---|---|
| `Deposit *` — `Yes — take one · No · Waive it (needs a supervisor)` · `Amount *` · `Why this amount` (four reasons) · `Due` | built, shared with the new-account wizard | ✅ | ✅ |
| ⚠ *"A credit tier would size this, and nothing works one out"* | — | 🔧 say it | no tier |
| ⛔ **BOTH ROWS ABOVE SUPERSEDED 2026-09-23 by PO ruling** (*"take deposit amount as per plan … no override is required"*; `OQ-CUS-12620` (a)): `Amount` is the unit's plan figure for the category, read-only · `Why this amount` and the credit-tier note removed · the answers are *Yes — take one* / *Waive it* where the plan asks a figure, and *No deposit on this plan.* (nothing to pick) where it asks none · a waive asks a reason and is kept on the account (`DEF-CUS-6369`/`6370`/`6371`) | built by lane DEPOSIT | ✅ | ✅ refuses *No*, a figure not the plan's, and take/waive on a plan asking none |
| **Has this customer paid a deposit before?** | asked | ⚠ | **cannot be answered** — no customer linkage; the server warns `deposit_carry_forward_unavailable` |
| `Take the deposit now *` · `Method` (7) · `Reference` · `Amount taken` · `Posting date *` · `Clearing date` | built | ✅ | ✅ `record_payment(purpose="deposit")` |
| ⛔ **the clearing-date trap** (finding 3) | — | 🔧 say it | true today |

## Step 6 · Review

| Drawing element | Product | Front end | Backend |
|---|---|---|---|
| every step read back, block by block | ✅ | ✅ | — |
| **`✎ Step N`** beside each block | — | 🔧 build | — |
| **What the commit writes** — `Account number: allocated at save` · `Status: Active from …` · `Order: the account, then the reads, then the payment` · **one transaction** | same | ✅ | ✅ `BR-SHL-019` |
| **What goes out to the customer** — five rows, each with template, channel and *when*, tickable | **absent** | 🔧 build | finding 2 |
| **Template picker** — search, Group · Channel · Variant · Version, drafts listed and unpickable | **absent** | 🔧 build | templates exist |

---

## What the two buttons do, verified in code

| | Save & exit | Submit |
|---|---|---|
| Account | — | created, advisory lock on (tenant, unit) |
| Account number | — | **allocated at save**, never shown in advance |
| Account status | — | the tenant's `active`; a non-occupying status is **refused**, not quietly accepted |
| Reading entries | — | committed AFTER the account exists, through metering |
| Payment | — | a row, `purpose="deposit"` |
| Journal entries | — | **DR undeposited funds / CR 2300 — only when the payment clears** |
| Communication | — | **none** |
| On any failure | — | **none of it happens** |
| **Everything typed** | **LOST** | committed |

## What I would build, in this order

1. **The draft** — a reference at the moment the wizard opens, every field surviving a closed tab, visible on the Move-ins tab as `open`. This is the one a clerk feels every day.
2. **The five messages** — the moment a customer is told their account number.
3. **The clearing-date warning** — six words on step 5, against a $0.00 deposit on a real account.
4. **The request prefill** — the link exists; filling it stops a clerk re-keying six fields an approved request already holds, and brings its documents with it.
5. **Step 1's twenty facts** — mostly moving two panels that already exist onto the screen where the decision is made.


---

## The discount question, answered from the seeded data — PO asked 2026-09-19

PO: *"please evaluate whther we have to take any disount related field - based on what plans
says becuase you ahev plan details now"*.

`apps/rating/discount_sample_data.py` seeds **six** discounts. They split cleanly.

### Three are AUTOMATIC, and step 4 already collects every input they need

| Discount | `eligibility_summary` | Where the input already comes from |
|---|---|---|
| Paperless billing | `E-bill on` | the paperless tick — **step 4** |
| Autopay discount | `Autopay enrolled` | the autopay tick — **step 4** |
| Municipal account | `Government account` | Category — **step 2** |

**Nothing new to ask.**

### Three need a person to apply, and a document

| Discount | `eligibility_summary` | `proof_required` | `accepted_proof_kinds` | `recertification_months` |
|---|---|---|---|---|
| **Senior discount** | `Age 65+` | **true** | `government_id` · `birth_certificate` | **12**, with 60 days' notice |
| **CAP / low-income credit** | `Program enrolment` | **true** | `programme_award_letter` · `agency_file` | **1** — agency file, monthly |
| **Veteran discount** | `Veteran ID` | **true** | `veteran_id` | `None` — one-time proof |

### Why this is cheap, and why it is the SAME change as `CR-122-BRC06`

**Step 2 already asks for a `Date of birth` and a `Government id`.** That is the senior
discount's entire test AND its accepted proof, on the screen, going nowhere. And the documents
`CR-122-BRC06` adds to step 2 are precisely what these three accept — a veteran ID, an award
letter. The discount capture and the document capture are one piece of work.

### Recommendation

**One question on step 4, not a form:** *is this customer claiming a discount?*, the three that
need applying, and the proof riding on the documents already collected. It never gates service —
B18 §5.3.4 is explicit, *"never blocks service — only the discount"*.

### ⚠ Two cautions that belong with the recommendation

**1 · A claim gets them into the queue; it does not start the discount.**
`proof_before_first_reduction` defaults to **true**, so an unverified enrolment reduces nothing
until somebody approves it. Capturing at move-in is a head start, not a grant.

**2 · THE "AUTOMATIC" THREE ARE NOT AUTOMATIC, AND THAT IS A BIGGER GAP THAN ANYTHING ON THIS
SCREEN.** `DiscountVersion.eligibility_rule` carries the rule builder's output and **no code
evaluates it** — the field's own docstring says so: *"ADVISORY IN THIS SLICE … Enrolment is a
staff act with a recorded verification; automatic evaluation is EP-RAT-12's remainder and is
named rather than half-built."* So a customer who ticks paperless does **not** get the paperless
discount; somebody has to enrol them by hand through `discount_services.enrol_account`. Worth
knowing before deciding how much to put on step 4, because it is true of all six and not only of
a move-in.

---

# The Move-ins LIST and the MOVE RECORD — blueprint pages 073–074

Both put to the PO on 2026-09-19 and both approved: the list changes with *"this si all good - please update it"*, and the record page with *"we have to buid … we have it in drawing that is our next work"*.

## ⚠ A correction this record owes, the second of the day

An earlier reading said *"`Save & exit` writes NOTHING and `Park` is DISABLED because a move-in
in progress is not a row anywhere"*. **The second half is false.** `parkStoreBlockedReason()` in
`moveShared.tsx:138` returns `null` — not blocked — whenever `wizardParkPort()` is wired, and it
is; `CR-035` step 6 built the port and resume. The running product proves it: the Move-ins tab
carries a live parked move-in — `Draft · waiting on documents · 3450 Oak Ridge Dr · Unit 1 ·
Step 1 of 6 · Waiting 16 days`. The comment in `MoveInWizard.tsx` asserting a missing store is
**stale**, and it was repeated as fact without being run.

**So the defect is sharper and worse than first reported:** the wizard head carries two buttons
side by side, and one of them silently discards everything the clerk typed while the other keeps
it. Nothing on either button says which. `BR-SHL-048` governs the store — PO 2026-08-26,
*"Option A - Unitl move in executed, no records updates"* — a parked draft holds the TYPING and
touches no records, and resume restores neither `reached` nor any verdict so every check re-runs.

⚠ **TWICE IN ONE DAY A DOCSTRING ASSERTED AN ABSENCE THAT HAD BEEN CLOSED MONTHS EARLIER** — this
one, and `initial_reads` above. Hard-won law 1 runs in this direction too: a comment claiming a
GAP is not the gap. Check the running product before believing a docstring about what is missing.

## The Move-ins list · `/accounts?tab=move-ins` — approved changes

### The head
| Drawing | Product | Change |
|---|---|---|
| `ACCOUNTS` kicker | absent | add |
| Title **The register** | `Accounts` | rename |
| `10 tabs · Move-ins · 1 still open` | absent | add |
| Breadcrumb `Accounts / Move-ins` | `Accounts` only | add the tab |
| `+ New move-in` | `Move-in` | rename |
| *(not drawn)* | `Accounts 82` on the tab | drop the count |

### The parked panel — NOT in the drawing, and it stays
| Product | Change |
|---|---|
| Amber box, **four paragraphs**, above everything | keep the panel, cut the copy to one sentence per section (rule 32) |
| *"there is no email or SMS in this release"* | VERIFY against today — the PO stated on 2026-09-17 that email is configured — then delete or correct |
| Restore ↺ and delete 🗑 per draft | keep |

### The KPI strip — three drawn, five built, and the third is a different question
| Drawing | Product | Change |
|---|---|---|
| **Open** · *not yet completed* | **Open** · *taking over live service* | reword |
| **Starting this week** | same | — |
| **Waiting on a reading** · *one unread, one estimated* | **Waiting on the customer** | **REPLACE** |
| — | Deposits to carry over | drop |
| — | Oldest | drop |

⚠ The third one is the screen's whole job. The drawing's own note: *"The Reads column is the one
a clerk works from. MVI-26-0113 opened with no reading at all and MVI-26-0114 with one estimated
register — both bill, and both need somebody to go back."*

### The toolbar
| Drawing | Product | Change |
|---|---|---|
| chips `Open · Starting this week · Completed · All · Filter ▾` | `All` + `+ Filter ▾` | add the three |
| search *by reference, account, customer or unit* | *Customer, unit, address, account #, or request #…* | shorten |
| `Columns ▾` | an icon | label it |
| `⇩ Export` | **absent** | add |

### The rows
| Drawing | Product | Change |
|---|---|---|
| **the reference opens the move record** | plain text | link, once the record page exists |
| **the account number opens the account** | plain text | link — the account page exists today |
| Step `6 of 6` | *"Step not recorded"* | check whether the data is there |
| Reads `1 estimated` · `Read` · `Not taken`, as chips | *"Not readable here"* | check — this is the point of the screen |
| Deposit `$150.00 taken` | `$150.00` | add the word |
| State `Completed` · `In progress` | `Due` | reconcile the vocabulary |
| **`↗ Open` per row** | absent | opens the record page |
| `1–3 of 3 · Rows per page 50 100 200` | `1–1 of 1`, bottom right | align |

## The MOVE RECORD · `/moves/{ref}` — a NEW screen, drawn on p074

The blueprint labels it **Proposed**, which is honest: it was designed and never built. There is
no route and no component. A new TOP-LEVEL route, not under `/accounts/`.

**The table exists** — `move_records` carries `move_no`, `kind`, `account`, `from_account`,
`effective_on`, `performed_by`, `performed_at`, `reads_committed`, `request_id`. Everything else
is assembled from the account, metering and payments.

### Head
`← The register` · kicker `MOVE-IN MVI-26-0114` · title **the customer's name** · chips
`Completed` + `1 register estimated` (amber) + `Moved in 05/02/2026` · the address line ·
and ONE control, top right: **`Open the account`**.

### What happened — six facts
Account opened · From account · Unit · Moved in on · Earliest legal start · Committed by
(with the time: `S. Ortiz · 05/02/2026 10:04`).

### Opening reads — a table
`Register · Reading · Read date · How`, where **How** reads `Read` or `Not estimated`.

### Money taken — a bordered box
`Deposit` → *Required by the plan* · *Taken · cheque 4471* · **Still to collect**.

### What is still owed to this move — three facts
Demand register · Visit · Carry-forward.

### ⚠ THE DESIGN POINT, AND IT IS THE WHOLE SCREEN
The blueprint, verbatim: *"**This record has no actions, and that is the answer rather than a
gap.** A move-in and a sale are records of acts that have already happened — there is nothing
left to decide on them, so the only controls are doors to the account and the customer. **The two
things this record says are still wrong are deliberately not buttons here**: the property's owner
record and the account's contact details are both fixed on their own screens, by somebody who can
see the whole picture."*

**One link out, no actions.** That is unusual enough that somebody will try to "improve" it
later, which is why it is written down before it is built.

### What it unlocks
The reference becomes a link, `↗ Open` has a destination, and the account number becomes the
second door the drawing describes.

---

## The action bar on the move record — the question the drawing could not settle, and the fact that settles it

The PO read the spec, agreed with it, and then challenged exactly one thing — verbatim:

> *"drawing has issue with actions - we will need save as draft, need more and approve action
> button or you can suggest simialr action what hapen when those actiosna re completed by user -
> rest is good"*

**They were right to challenge it, and the drawing is genuinely incomplete here.** p074 draws
only a COMPLETED move and states its *"this record has no actions"* rule about that one. p073's
list proves the page must also account for a move still in flight — `MVI-26-0113 · 3 of 6 · In
progress` sits two rows above `MVI-26-0114 · 6 of 6 · Completed`. The rule is true of a finished
move and **silent** about an unfinished one.

### The fact that settles it, measured rather than argued

**A `move_record` is written ONLY when the move commits.** `moves.record_move()` says so in its
own first line — *"Write the record for a job that has just completed"* — and its only two
callers are both inside the commit in `services.py`. There is no row before that moment.

**So there is no such thing as an in-flight move record, and `/moves/{ref}` can never open one.**
An unfinished move is a parked WIZARD DRAFT, which lives on the Move-ins list's own panel and is
reached from there. The drawing's in-progress row is a divergence between the drawing and this
product, not a state this page has to serve.

### Which means the PO's three already exist, under other names, in the right place

| The PO's name | What it actually is | Where it lives today |
|---|---|---|
| **Save as draft** | **Park** — keeps the typing, what is awaited, a note and a remind-on date; writes no account, no reads, no money and sends nothing | the parked-drafts panel, works |
| **Need more** | **Park with its reason filled in** — the product already renders `Draft · waiting on documents · Waiting 16 days · Remind on 09/10/2026` | same |
| **Approve** | the step 6 commit | the wizard |

⚠ **AND `Approve` IS THE WRONG WORD FOR IT, WHICH IS WORTH SAYING BEFORE IT IS BUILT.** Approving
is a DECISION — a clerk weighs something and says yes, which is exactly what the request screen's
Approve does. Finishing a move-in decides nothing: everything has been gathered and is being
committed. Giving the two acts one word would tell a clerk they are the same act. The drawing
calls it **`Complete move-in ✓`** and the page should too.

### The four proposed for the record page, and the principle kept

Nothing on this page CHANGES the move — that part of the drawing's rule stands, and a committed
move cannot be undone, re-approved or refused. But the page currently reports two things as
still wrong and offers no way to reach either, which is the friction the PO is pointing at.

| Button | What happens | What does not |
|---|---|---|
| **Open the account** | the account — where every later question is answered | nothing here changes |
| **Open the customer** | the customer's own record. ⚠ **The drawing's own prose sanctions this** — *"doors to the account AND the customer"* — it names two doors and draws one | — |
| **Raise a visit** | a work order for the register nobody could read; the page then reads `Visit — raised` | no reading is invented, no bill moves |
| **Record the reading** | Reads for that meter, dated and prefilled | the move record is untouched — the reading goes to metering as always |

**All four are DOORS, not decisions.** That is the drawing's principle honoured rather than
overruled, and it is the distinction to defend if somebody later proposes a fifth.

**OPEN at the time of writing:** whether `Raise a visit` and `Record the reading` stay. The
drawing says the two wrongs are *"deliberately not buttons here"* because they are fixed on
their own screens by somebody who can see the whole picture. The counter-argument is that a
clerk reading `Visit — not raised` on this page has nowhere to go. Put to the PO; the lane is
held on the action bar and building everything else.

### RULED 2026-09-19 — the action bar, and what `Approve` actually does

PO, verbatim: *"use this Save as draft, Need more, Approve - On the move record — the move
already happened - Open the account, Open the customer -f requried otherwise we will ahev to
link to exisitng one; billable, we will ahve to change status of accounts, units, etc, assign
assets, , plan updates , deposite wwewill ahve to apply , apply books, ; Raise a visit - not
required, if readings are given then we create reads in register or leave it ; Record the
reading - if provdied in move in"*.

**The record page carries TWO controls: `Open the account` and `Open the customer`.**
`Raise a visit` and `Record the reading` are REMOVED on the ruling — the readings come from the
wizard's step 3, which already accepts them and commits them through metering, so a button here
would be a second door onto one act. **The drawing's principle survives intact:** nothing on
this page changes the move, and both controls are doors rather than decisions.

⚠ **`Approve` IS CHOSEN, NOT AGREED, AND THE DISTINCTION IS RECORDED ON PURPOSE.** The argument
against it is written above — approving is a decision, and the request screen's Approve decides
something, while finishing a move-in decides nothing. The PO has chosen the word. It is the
ruling; the reasoning is kept here so that if it is ever revisited nobody has to re-derive it.

#### What `Approve` does — the PO's list measured against the code

| The PO's item | Built | What actually happens |
|---|---|---|
| change account status | ✅ | the account opens on the tenant's ACTIVE status, and a status that does not occupy is **refused** rather than quietly accepted |
| change unit status | ✅ | the unit derives Occupied — the wizard's own exit condition |
| assign assets | ✅ **and there is nothing to assign** | meters belong to the UNIT, not the account; the new account inherits them by standing on the unit, and the unit's `service_agreements` are written on the same act |
| plan updates | ✅ **by design, nothing to do** | the plan lives on the unit and the account derives it — the PO's own ruling, *"it is not a choice on any later step"* |
| apply the deposit | ✅ | `record_payment` writes `accounts.deposit_on_file` INSIDE its own transaction, so the account and the money cannot disagree (`DEF-177`, closed) |
| apply books | ✅ | `DR undeposited funds / CR 2300`, **and only when the payment clears** |
| billable | ⚠ **not proved** | it follows from the six above rather than being a switch. NOT verified end to end — a bill has not been run against a fresh move-in. Stated as unproved rather than assumed |

**Six of seven are already built.** The seventh is not missing; it is unwatched, and the honest
record says so.

#### ⚠ The clause that is bigger than it looks

*"otherwise we will ahev to link to exisitng one"* means building a **customer search on the
move-in that has never existed**. Today a move-in writes a FRESH contact row every time, the
server warns `customer_not_linked` on every one, and the sentence the screen gives as the reason
is KNOWN TO BE FALSE and already reported. It is its own piece of work with its own proof, it is
with the PO, and the record-page lane was told explicitly not to start it.

---

## Linking a mover to a customer — investigated 2026-09-19, and most of it is already built

PO: *"yes - we will ahve to do it - we will ahve to tag it to master account or customeer iDs -
so we need to find out who to do it"*.

### ⚠ The two names the PO used are TWO DIFFERENT THINGS, and a mover belongs to one

| | What it is | Right for a move-in? |
|---|---|---|
| **Customer ID** | the person or company — one customer, many accounts over time, joined through `customer_accounts` | ✅ **yes.** This is how a returning tenant keeps their history and their deposit |
| **Master account** | an `accounts` row with `kind='master'` — **the premises OWNER or MANAGER's** account (`models.py:463`) | ❌ **no.** A tenant moving in is not the owner |

The master account is the property's, and it is how an owner is billed for vacant units and
common areas. **Tag the mover to a Customer ID; the master account stays the owner's.** Recorded
because the two were named in one breath and conflating them would bill a tenant as a landlord.

### The machinery exists, and the criteria are already SIGNED

`apps/customers/identity_match.py` weighs evidence against a customer. **It does not score, does
not threshold and does not fuzzy-match a name** — it is a three-part test, and its own header
says so. `BR-CUS-1022` / `BR-CUS-089`:

| kind | `strong` when | never asked for |
|---|---|---|
| **person** | name **+** date of birth **+** (SSN **or** driving licence) | a Tax ID |
| **company** | name **+** Tax ID | a date of birth, an SSN, a driving licence |

Only a `strong` verdict may MOVE MONEY — which is what lets a returning customer's **$150.00**
deposit follow them, and why a tier derived from weaker evidence is a money bug.

### What is built, and the one thing that is not

| Piece | State |
|---|---|
| the criteria | ✅ signed and implemented |
| the matcher | ✅ `recognise` / `reuse_candidate` |
| a door taking a raw payload | ✅ `from_payload(payload, kind=…)` |
| a door for a service request | ✅ `evidence_from_service_request` |
| customer search | ✅ `GET /customers` — *"one search box, four legs"* |
| the link table | ✅ `customer_accounts` (built 2026-08-11) |
| **a door for the move-in wizard, and a panel to show candidates** | ❌ **the whole job** |

⚠ **AND THE MOVE-IN ALREADY COLLECTS EVERY FIELD A STRONG PERSON MATCH NEEDS, THEN THROWS THEM
AWAY.** Step 2 captures full name, date of birth, SSN and driving licence — all four, on the PO's
rulings of 2026-08-27 and 2026-09-15 — and the commit writes a FRESH contact row regardless. The
server warns `customer_not_linked` on every single move-in.

⚠ **THE SENTENCE ON STEP 2 EXPLAINING WHY THERE IS NO SEARCH IS FALSE, AND HAS BEEN SINCE
2026-08-11.** `customers.moveIn.customer.noSearch` tells a clerk *"the shared customer record it
would look through does not exist"*. `models.Customer` and `models.CustomerAccount` were both
built on 2026-08-11. The same false reason was corrected in `suggest_customer_matches`'s own
docstring on 2026-09-15 — *"A refusal whose stated reason has expired is the mirror of dead UI
and nothing in this repo can see it"* — and **four user-visible sentences carrying it were
REPORTED rather than edited.** This is one of them. **That makes THREE expired-absence findings
on this screen in one day**, with `initial_reads` and `Park`.

### The work, in order

1. A **panel on step 2**: as the four fields are typed, offer candidates. A `strong` match gets a
   *Link* button; anything weaker is shown and **refused BY NAME**, never silently.
2. Write **`customer_accounts`** on the commit instead of a fresh contact row.
3. **Delete the false sentence.**
4. `Open the customer` on the move record then has somewhere to go.

### OPEN — a money question, not a design one

**If the clerk links a strong match, does the deposit follow automatically, or must they say so?**
`BR-CUS-089` PERMITS it. Money moving without a person asking for it is not a decision this lane
should make, and it is with the PO.

### The premises type decides WHERE to look, not WHAT to tag — PO 2026-09-19

PO: *"based on premises type we will have to take decision"*.

`PROPERTY_TYPES` carries six values — `standalone_owner_occupied` · `rental_tenant_applying` ·
`rental_landlord_applying` · `multi_unit_building` · `under_construction` · `vacant_land` — and
they are exactly the axis the PO means.

| Premises type | Who moves in | Tag to | The master account |
|---|---|---|---|
| standalone, owner occupied | the owner themselves | **Customer ID — the SAME customer as the premises owner** | already exists; the mover IS that party |
| rental, tenant applying | a tenant | the **tenant's** Customer ID | the landlord's — untouched |
| rental, landlord applying | the landlord | the **landlord's** Customer ID | the landlord's — same party |
| multi-unit building | one tenant per unit | each tenant's OWN Customer ID | the owner's — untouched |
| under construction | the builder or developer | the **builder's** Customer ID | the owner's |
| vacant land | the owner | the **owner's** Customer ID | the owner's — same party |

**THE RULE UNDERNEATH IS SIMPLER THAN THE TABLE: every mover is tagged to a Customer ID, always.
What the premises type decides is whether that customer is the SAME PARTY as the owner, and
therefore where the matcher looks first.**

* **Owner-is-mover types** (owner-occupied · landlord applying · vacant land) — the premises
  already knows its owner, and `premises_owners` can point at *"the customer they already are"*.
  **Seed the candidate list with that owner**, marked as such. It is evidence already held.
* **Tenant types** (rental tenant · multi-unit) — the owner is NOT the mover. **Never offer
  them**, and say in a few words that they were excluded, so a clerk reads a decision rather than
  an empty search.

⚠ **WHY THIS IS A GUARD AND NOT A CONVENIENCE.** On an owner-occupied property the owner usually
already holds a master account WITH A BALANCE. Offering them on the right type links a returning
customer to their own history and deposit. Offering them on a RENTAL, where a clerk may click
through, makes **a tenant inherit a landlord's arrears.** The premises type is what stops a
`strong` match being offered against the wrong party.

⚠ **`premises_owners` NEVER WRITES `customers`** — the customer link is a POINTER validated
through the customers module, and `customer_id` is a REFUSED input on that path (`BR-MET-1020`,
`_refuse_customer_shortcut`). So seeding a candidate means READING the owner's customer pointer,
never creating one from the premises side.

#### OPEN — and it changes who gets the bill

**`rental_landlord_applying` is ambiguous in the data and cannot be settled from the code.** A
landlord applying may be taking service in their OWN name for a vacant unit, or opening it for a
tenant who moves in later. Those tag to different customers and therefore bill different parties.
Put to the PO; not decided here.

---

# BUILT 2026-09-19 — the Move-ins list, and the move record learning the second flow

⚠ **EVERY PAGE NUMBER IN THIS SECTION IS THE 281-PAGE EDITION OF
`02 Accounts Menu Blueprint.pdf`, THE ONE THE PO UPLOADED ON 2026-09-19**
(`74a2e6b52`, 10,282,571 bytes). It replaced a 242-page edition the same day and
**the pages moved**, which makes every citation in the sections ABOVE this one
stale by four:

| Screen | Was | Is now |
|---|---|---|
| The Move-ins list | p073 | **p077** (it begins at the foot of p076) |
| The move record (move-in) | p074 | **p077–078** |
| The move-out record | p105 | **p117–118** |

**The DRAWN SHAPE did not change.** The three KPI tiles, the `6 of 6` step
counts, `$150.00 taken`, the per-row `↗ Open` and both doors are in both
editions, so nothing built from the old one had to be undone. What the new
edition ADDS is a banner per screen saying what the product does today — and one
of those banners is **already stale**, which is worth recording because it is
this repo's own failure mode arriving from outside:

> *"the product's move-in wizard has FIVE steps and takes no deposit; these six
> add the deposit step and a read date"* — published **2026-09-11**, two days
> before `MOVE_IN_STEPS` gained its sixth step.

The DRAWING on the same page says `6 of 6`. **Where a blueprint's prose and its
own drawing disagree, B14 rule 42 settles it** — the screen is built from the
drawing AS AN IMAGE and the extracted text is an index, never the specification.
It is also independent confirmation of `DEF-CUS-5886`.

## The Move-ins list — what a clerk can do now that they could not

| Approved change | Built | Note |
|---|---|---|
| The reference opens the move record | ✅ | `/:tenant/moves/{ref}`, and ONLY where a `move_no` exists |
| The account number opens the account | ✅ | the account page has existed since S21 |
| `↗ Open` per row | ✅ | absent on a row with no record — see below |
| Third KPI → `Waiting on a reading` | ✅ | counted server-side, **6** on the seeded tenant |
| Drop `Deposits to carry over` | ✅ | off the screen, still on the payload |
| Drop `Oldest` | ✅ | off the screen, still on the payload |
| Deposit reads `$150.00 taken` | ✅ | the word was the missing half of the cell |
| The parked panel's copy cut | ✅ | four paragraphs → one sentence |

### ⚠ THE THIRD TILE IS A DIFFERENT QUESTION, NOT A REWORDING

It was `Waiting on the customer` and it is now **`Waiting on a reading`**. The
count is `_waiting_on_a_reading()` and it is **derived through the very
`unit_reads_cell` the READS column renders**, so the tile and the table cannot
disagree — measured on the seeded tenant, the tile reads **6** over exactly the
**6** rows whose cells say `Due`.

**Two rows could not be judged at all** (`unit_has_no_meters`), and they are in
NEITHER number. `unjudged` rides on the payload and on the tile as
`data-unjudged`, because **a count reporting zero over a scope it silently
excludes is indistinguishable from an empty one** — hard-won law 7's fifth
shape.

⚠ **THE DRAWN SUB-LINE CANNOT BE SERVED AND IS CARRIED AS DATA.** p077 writes
*"one unread, one estimated"* under the figure, and **a move-in READS cell is
two-state by design** — `taken` / `due`, with `estimated` reserved for a
move-out settlement's own stored flag. The drawing contradicts itself on that
word, exactly as it does on the record page's amber chip, which the earlier lane
resolved the same way. The drawn words ride as `data-drawn-as` so the divergence
stays findable; what a clerk reads is `reads still to take`.

### Every string CUT, and where it went

| Cut from the screen | Why | Where it lives now |
|---|---|---|
| *"A parked move-in has not taken its unit, and a parked move-out has not closed its account or stopped its bills — that all happens when you finish the job."* | RATIONALE — it explains the sentence that was kept (rule 33: zero words) | `parkedDrafts.tsx`, and `BR-SHL-048` |
| *"These are not in the list below and are not counted in it — nothing has been created yet."* | the same fact as the kept sentence, said twice (rule 32) | the test now asserts the COUNT instead of the sentence claiming it |
| *"Nothing sends these reminders — there is no email or SMS in this release. The date and the waiting time below are how a parked job gets picked back up, so this list is worth opening."* | RATIONALE **and FALSE** — see below | deleted; the measurement is in `parkedDrafts.tsx` |
| p077's red box: *"A move-in is a record OF an act … The reference opens the move record; the account number beside it opens the account"* | RATIONALE | it is the SPECIFICATION for the two doors, quoted in `MoveInsTab.tsx` |
| p077's note: *"The Reads column is the one a clerk works from…"* | RATIONALE | quoted in `_waiting_on_a_reading()`'s docstring as the argument for the tile |

### ⚠ THE EMAIL SENTENCE WAS CHECKED, NOT BELIEVED — AND IT WAS WRONG

The conformance table above said *"VERIFY against today — the PO stated on
2026-09-17 that email is configured — then delete or correct"*. Measured on the
seeded tenant through the product's own seam:

    provider_seam.provider_status("email")
      -> {"channel": "email", "connected": false, "provider_key": null}
    provider_seam.provider_status("sms")
      -> {"channel": "sms",   "connected": false, "provider_key": null}

**So the MACHINERY exists** — a provider seam, a connector surface, a mailbox
module carrying Google OAuth, M365 OAuth and SMTP — **and nothing is CONNECTED
on this tenant.** That is a configuration fact about one utility. The sentence
made a claim about the RELEASE, and that claim is not true and has not been for
some time; it is what let the PO say email is configured while a screen went on
denying it. **Deleted rather than reworded**, because every version of it is
rationale, and whether a channel is connected belongs to the notifications
settings screen that can answer it for the tenant actually looking.

### The three cells the brief asked about — CHECKED BEFORE CHANGING

| Cell | Does the data exist? | Verdict |
|---|---|---|
| `Step not recorded` | **No** — `reached` is `null` on all 8 rows | The absence is HONEST and stays. **But the DENOMINATOR was wrong** — `of: 5` under a six-step wizard. `DEF-CUS-5886` |
| `Not readable here` | **Mostly YES** — 6 of 8 rows serve `state: "due"` and render real data | The string appears only for the 2 rows with `unit_has_no_meters`. The cell already branches; nothing to fix here |
| `Due` vs drawn `Completed` / `In progress` | **`due`/`scheduled`/`pending` are real served states** | The absence is honest and the fix is elsewhere: `done` is `supported: false` because a completed move-in LEAVES this list (no retention window), and `in_progress` is `supported: false` for the step-store reason |

### What was NOT built, and why

* **`⇩ Export`** — the drawing has one and this tab has none. `POST /exports`
  resolves only REGISTERED resources and nothing registers `move-ins`, so a
  button here is **a control wired to a 404** — hard-won law 2, which this repo
  has four instances of from one day. `DEF-1005` carries it. Adding the button
  without the resource would be the defect, not the feature.
* **The `Completed` filter chip** — drawn, and `done` is `supported: false`
  because a completed move-in leaves this list. A chip that returns nothing is
  the same dead control in a different shape. The chips render from the server's
  own `states`, so the day a retention window is ruled it appears by itself.

## The MOVE RECORD learns the move-out — p117–p118

### ⚠ THE ADDRESS SERVED BOTH FLOWS; THE PAGE SERVED ONE

`App.tsx` carried a comment claiming *"a move-OUT record answers here too …
so one address serves both flows"*. **Measured with a real HTTP request rather
than read:**

    POST /api/brazosbend/auth/session      -> 201
    GET  /api/brazosbend/moves/MVO-26-0001 -> 200, kind "move_out", state "completed"

**The ADDRESS did serve both. The PAGE did not** — `MoveRecordPage` had no
move-out branch, so a real move-out rendered `Account opened` and `Moved in on`
about somebody who had LEFT, with the deposit box where p118 draws the
settlement. **That is worse than a 404, because it looks like a page.**
Hard-won law 1, inside the comment that claimed the guarantee; the comment is
corrected rather than left.

### Built

| p117–p118 draws | Built | From |
|---|---|---|
| kicker `MOVE-OUT {ref}`, title the customer, address | ✅ | already flow-agnostic |
| chip `Moved out {date}` | ✅ | one chip, two words, chosen by `kind` |
| chip `Short by $186.40` | ✅ | **only when the settlement landed `short`** |
| `Account closed` · `Moved out on` | ✅ | the same served field, relabelled |
| `Final reads` table | ✅ | retitled; same rows |
| `HOW THE MONEY LANDED` — closing balance, deposit applied, **Short by** | ✅ | `GET /accounts/{id}/close-impact` |
| `WHERE IT COULD GO` — Option / What it means | ✅ | the server's own `shortfall_paths` |
| `Open the account` | ✅ | already there |

### ⚠ THE SETTLEMENT IS SERVED, AND AN EARLIER READING OF THIS LANE'S SAID IT WAS NOT

A first pass concluded *"there is no field for any of them"* and would have
written a stated absence over a live endpoint — **the expired-absence defect
this file already records twice today**. `GET /accounts/{id}/close-impact` has
been mounted since 2026-08-25 and answers 200 with the settlement, the shortfall
paths, whether each is open, the server's reason when one is not, and the
account a shortfall would tie back to. **Check the running product before
believing anything about what is missing — including your own conclusion from an
hour ago.**

⚠ **IT IS A SECOND PROJECTION OF ONE ENDPOINT, DELIBERATELY.**
`moveShared.closeImpactPort()` already reads that URL and its own docstring
records why it cannot feed this screen: the payload is *"a SUPERSET on the money
side and a SUBSET on the impact side"* (`DEF-669`), and that port maps the
IMPACT half and drops every money field. Rather than widen a port four callers
depend on, `readMoveOutSettlement()` maps the money half and names what it
ignores. **It MAPS and never CASTS** — an unmapped field arrives `undefined`,
and `undefined` renders as a figure nobody measured.

### ⚠ `complete: false` IS A REAL LANDING, AND IT IS WHAT THE SEEDED TENANT GIVES

`AC-2026-00042` answers `complete: false`, `gaps: ["final_bill_not_stated"]`,
every total `null`. The drawing shows a FINISHED settlement, so its figures
cannot be rendered for that account — and **`$0.00` would state a settlement
nobody ran** (rule 37: a figure drawn in a wireframe is an illustration, never a
fact to build to). The screen shows the gap the SERVER named.

### Divergences recorded rather than resolved

* **The server offers FOUR shortfall paths and p118 draws THREE.** `collect`,
  `payment_plan`, `write_off`, `transfer` — the drawing omits `payment_plan`.
  **All four are rendered.** Hiding a path a clerk may legitimately take is
  worse than a drawing being one row short, and the list is the server's so a
  fifth appears by itself.
* **`Tie back to the master` is cut to `Tie to master`** — rule 33 caps a label
  at three words, on the PO's governing instruction that our copy rules win over
  the drawing's content.
* **`WHERE IT COULD GO` is cut to `Options`** — a heading is ≤3 words.
* **`Nothing is preselected. A default here would be the product deciding whose
  debt this is.`** is RATIONALE and is ZERO words on screen. Nothing is
  preselected, which is the behaviour; the reason lives here and in the code.
* **`Unit now · Vacant · standby off` is a STATED ABSENCE** — the one drawn fact
  of that section with no field behind it, on either endpoint. A unit standing
  empty and a unit whose standby was switched off are two facts, and deriving
  either from occupancy would state a measurement nobody took.

### NOT built, and the reason is a fact about the product rather than a gap

**`Tie the shortfall back` — the consent dialog — is the next wave.**
⚠ **The write path EXISTS and is routed:** `POST /accounts/{id}/settle-shortfall`,
mounted in `apps/customers/api.py` alongside `close-impact`, `refund` and
`hold-excess`. Saying *"there is no write path"* would be false and would rot
into a wrong absence note the next lane quotes.

It is deferred because **it moves money between accounts**, which puts it under
the hard rules: financial immutability (corrections are new rows, never
UPDATEs), balanced pairs written only by the ledger posting service, hard rule 7
(every money action writes `audit_log`), and it is a 🔒 sensitive path needing
`HUMAN-REVIEW-PENDING` and a row in `12-governance/09-human-review-ledger.md`.
That is its own wave with its own proof, not a control to add on the way past.
