# `CR-133-BRC07` · A move-in gets its `MVI-` number the moment it is approved

| | |
|---|---|
| Raised | 2026-09-22, in the working chat session, the PO reading the Move-ins tab after approving `SR-26-0011` |
| Requester | Product Owner |
| Branch | `claude/laughing-thompson-kpmwih` · block `CR-130`–`CR-134`, suffix `BRC07` |
| Module | customers |
| Classification | **CHANGE** — argued in §1, not assumed |
| Version | `2.327.4` at capture · shipped in `2.328.0` |
| Rule minted | **`BR-CUS-1090`** |
| Defect filed alongside | **`DEF-CUS-6177`** (the paragraphs in the table cells — the PO's second row) |
| ⚠ Read first | **THE REVERSAL THE BRIEF EXPECTED HAS ALREADY HAPPENED, AND IT IS DATED 2026-09-16.** `B18 §5.5.2`'s footnote — *"a move-in is short enough that the wizard is the record"* — was superseded **for the move-in** by `BR-CUS-1077`, which put `move_in_jobs` on the branch. See §2: this CR reverses something narrower, and knowing that makes it a smaller change rather than a bigger one. |

---

## 0 · Capture — the requester's words, verbatim

The PO pressed **Approve** on `SR-26-0011`, chose *"A move-in"*, and looked at what appeared on
Accounts → Move-ins:

> *"you would ahve created a new move In request ID and add all details from servcies request to
> it and save it as a draft - do you ahve move in request ID in numbering?"*

and, over a table whose row 16 reads *A move-in gets `MVI-…` at creation and its own page*:

> *"fix all these issues"*

**The last clause of the first sentence is a question with a yes in the repo**: the `move_in`
series exists (`core/numbering.py:241`), the format is `MVI-{YY}-{0000}`
(`apps/tenancy/models.py:1817`), and two other rows already draw from it. What did not exist is a
number on the row the approval raises.

---

## 1 · Classification — CHANGE, and the argument for it

`13-change-process.md` §1: an ambiguous item is a **DEFECT**, because filing our own
misunderstanding as a change converts our error into the customer's new requirement. Answered
rather than waved through, and it splits cleanly:

* **The number at approval is a CHANGE.** Nothing signed says an approved move-in carries a
  reference. `BR-CUS-1077` deliberately gave the job *"NOTHING THAT ALREADY HAS AN OWNER"* and a
  number has no owner until somebody issues one. Nobody asked for it before and the product is
  not failing to do what it was told. It is the specification being extended.
* **The paragraphs in the table cells are a DEFECT** and are filed as one — `DEF-CUS-6177`. The
  product was told (B14 rules 32 and 33) not to put rationale on screen and it does. That is us
  missing, not the PO changing their mind, and it is routed through
  `12-governance/22-product-maintenance-process.md` rather than through this file.

---

## 2 · What signed statement is being reversed — and what was reversed already

### 2.1 The one everybody expects, and it moved six days ago

> **B18 §5.5.2, footnote:** *"a move-in is short enough that the wizard is the record"*

**Already superseded for the move-in, on 2026-09-16, by `BR-CUS-1077`** (PO: *"it should do B"*).
That rule says so in its own words — *"THIS SUPERSEDES B18 §5.5.2's FOOTNOTE FOR THE MOVE-IN, AND
THE SUPERSESSION IS STATED"* — and `apps/customers/move_in_jobs.py` §1 carries the same paragraph.
An approved move-in has had a row of its own for six days. **This CR does not reverse it a second
time and must not be written down as though it did**, because a supersession recorded twice reads
as two rulings that have to be told apart.

What survives of the footnote is the **step** half. `move_reads.STEP_HAS_NO_STORE` asks for *"a
move-in/move-out case row carrying step + state"*; `move_in_jobs` carries state and **no step**,
and this CR adds none. So the footnote is exactly as superseded after this change as before it.

### 2.2 The one this CR actually reverses

> `move_reads.MOVE_IN_IS_STILL_A_DRAFT.detail`, live on screen today:
> *"This move-in has not completed, so there is no job to reference yet. **The record and its
> number are written when the account opens** — which is also when the row leaves this list."*

**That sentence is what stops being true**, and it was already half-false before this CR:
`CR-122-BRC06` gave a PARKED move-in wizard a number from the same series on 2026-09-20
(`wizard_parks._allocate_draft_reference`), so a number has not waited for the account to open
since that day. This CR finishes the same move one step earlier in the job's life. The sentence is
narrowed in the same commit as the code.

### 2.3 What is NOT reversed, stated so nobody narrows it by accident

| Signed | Status after this CR |
|---|---|
| **`BR-CUS-152`** — *nothing ever updates a `move_records` row* | **UNTOUCHED, word for word.** See §5 — the answer is that a draft is a different TABLE, not a looser rule. |
| **`BR-CUS-150`** — *a `move_records` row exists only for a COMPLETED job* | **UNTOUCHED.** No draft is written to `move_records`. |
| **`move_in_jobs` §2** — *it copies nothing; every fact is read through the request* | **UNTOUCHED.** See §6 — the details are CARRIED, not COPIED. |
| **CLAUDE.md hard rule 8** — an address lives on `premises` | **UNTOUCHED.** The job still declares no address column and still walks. |

---

## 3 · Impact

| Surface | What changes |
|---|---|
| `move_in_jobs` | one new column, `move_no`, and a unique index per tenant |
| `customers/0064` | the migration, plus the case-insensitive unique index |
| Approval (`request_jobs._raise_move_in`) | allocates the number inside the approval's own transaction |
| `moves.record_move` | ADOPTS the job's number instead of minting a second one |
| `wizard_parks` | a move-in wizard opened on a job CARRIES that job's number (`CARRIED_REFERENCE_KEYS`) |
| Move-ins tab REFERENCE cell | the `MVI-` and a link to `/moves/{ref}`, not the request number |
| `/moves/{ref}` | resolves a THIRD kind of row — a pending job — beside the record and the draft |
| `move_reads.MOVE_IN_IS_STILL_A_DRAFT` | its sentence narrowed (§2.2) |
| Eleven catalogues | the new short cell words |
| Open questions | none minted — nothing here is a fact only the PO holds (hard-won law 13) |
| Demo fixture | `SR-26-0006`'s pending job on `brazosbend` gains a number when re-seeded; rows written before this change keep `NULL` and say so |

## 4 · What is already built and is now wrong

**Nothing is wrong. Three things were incomplete, and the third is the one that would have bitten.**

1. `move_in_jobs` had no number. That is the change.
2. `/moves/{ref}` knew two kinds of row and there were three.
3. ⚠ **THE TWO-NUMBER HAZARD, which is what makes this more than a column.** One move-in can leave
   rows in **three** tables — `move_in_jobs` (approval), `wizard_parks` (the clerk opens and parks
   the wizard) and `move_records` (completion). Giving the first one a number without chaining it
   to the other two would have printed `MVI-26-0115` on the queue and filed the finished job under
   `MVI-26-0117`, which is the exact *two vocabularies* cost `moves.record_move` already names in
   its own comment. The chain is closed in §7.

**Lanes building right now:** LANE REQ-A holds `ServiceRequestDetailPage.tsx`,
`ServiceRequestCapturePage.tsx`, the document components and the fee modal. **None of those is
touched by this CR** — the approval's server side is `apps/customers/request_jobs.py`, which is not
theirs.

## 5 · THE CRUX — what `BR-CUS-152` means now that a record exists before the move happens

The brief put this as a fork: *either a draft is a different thing from the completed record, or
the immutability rule narrows.* **It is the first, and the reason is that the two things were
already two tables before anybody asked.**

* `move_records` is **the job that happened**. Its own docstring: *"written by a flow that has
  already committed … there is no in-flight moment for it to describe"*. `account_id` is NOT NULL
  — the very account the job exists to create.
* `move_in_jobs` is **the job waiting to happen**. Two states, `pending` → `done`.

**What travels between them is the NUMBER, not the ROW.** `record_move` INSERTs a new
`move_records` row carrying the reserved string; nothing is updated, nothing is promoted, and no
row ever changes table. `BR-CUS-152` is a rule about `move_records` and this change writes nothing
to `move_records` that was not written before.

⚠ **AND THE MECHANISM WAS ALREADY IN THE CODE, WHICH IS WHY THIS IS AN EXTENSION AND NOT A
DESIGN.** `moves.record_move` has taken `reserved_move_no` since `CR-122-BRC06`, with its own
comment: *"A RESERVED NUMBER IS ADOPTED, NOT RE-ALLOCATED … allocating a second one here would
file the finished job under a number nobody was told."* The parked wizard reserves; this CR lets
the approval reserve too. One argument, one code path, two callers.

**The job's own row is mutable and says so.** `state`, `closed_at` and `closed_reason` already
move — `complete_for_request` has updated them since 2026-09-16 and that is a queue row's
lifecycle, exactly as `connections` moves from `draft` onward. `move_no` is written ONCE, at
creation, and no door rewrites it; that is enforced by the unique index rather than promised by a
comment (hard-won law 1).

## 6 · The details — CARRIED, not COPIED, and this is a judgment recorded rather than smuggled

The PO said *"add all details from servcies request to it and save it as a draft"*. That sentence
has two halves and only one of them was missing.

**Every detail the PO named is already on the row and has been since 2026-09-16** — applicant,
unit, requested start, the documents still outstanding — read through the link at the moment
anybody asks. **The services were the one thing genuinely absent**, and they are added the same
way: read, not stored.

**They are not copied onto `move_in_jobs`, deliberately**, and three signed things say so:

* `move_in_jobs` §2 — *"a second copy of a fact that already has an owner is how two numbers come
  to disagree"*;
* CLAUDE.md hard rule 8 — an address is stored on `premises` and every other entity walks to it, so
  an address column here would be a fourth home `G85` fails;
* `request` is **NOT NULL and `on_delete=PROTECT`**, so the facts can never become unreachable —
  which is the only argument a copy would have had.

**What the PO sees is identical either way**, and what they cannot see is that a copy would let the
queue and the application disagree about a start date the day somebody edits one. Recorded here
because a judgment made and written down is the deliverable (hard-won law 13); the same paragraph
is in `move_in_jobs.py`'s own docstring, which is what the next lane actually reads.

## 7 · How the two-number hazard is closed — one number, three tables

    approval  ──►  move_in_jobs.move_no          MVI-26-0115   (allocated ONCE, here)
                       │
                       │ the wizard opened on this job carries the number
                       ▼
    park      ──►  wizard_parks.reference        MVI-26-0115   (carried, burns no counter)
                       │
                       │ _adopt_wizard_draft, else the job's own
                       ▼
    commit    ──►  move_records.move_no          MVI-26-0115   (adopted, never re-allocated)

Three mechanisms, each already in the repo before this CR:

1. **`CARRIED_REFERENCE_KEYS`** gains `move_in_no`. `_draft_reference` prefers a carried number
   over an allocation and says why: *"a park that carries one burns no counter"*.
2. **`record_move(reserved_move_no=…)`** prefers the draft's number, and now falls back to the
   JOB's before minting.
3. **`uq_move_in_jobs_tenant_move_no_ci`** makes one number mean one job at the database, so a
   double press cannot mint two even if the service check races — which is `BR-CUS-093` clause (e)
   and the posture `uq_move_in_jobs_tenant_request` already took for the request.

**A rolled-back approval burns its number and the gap is normal.** `BR-CUS-093` (2026-08-24)
settled this for service requests — a request is numbered at CREATION *"so the clerk can quote the
number to the customer on the phone while the form is still half-filled"*, and an abandoned draft
burns its number. `BR-TEN-035` permits the gap and prefers it to a number issued twice. **Gaps in
`MVI-` are not loss and must never be reported as loss.**

## 8 · Size, and the plain-English confirmation

One column, one migration, one index; four backend files touched, two front-end. The figure worth
saying aloud: **on the seeded `brazosbend` utility the Move-ins tab shows three rows, and before
this change one of them — the approved move-in for Michael Kwan — had no reference at all while
the two beside it had `MVI-26-0001` and `MVI-26-0002`.** After it, all three carry a number from
one series and all three open their own page.

**Fast path?** No. It touches a numbering series and a migration, so it goes the long way.

## 9 · Version

`2.328.0` — a CHANGE, so the middle number moves. Written into
`07-frontend/package.json`, `07-frontend/package-lock.json` and `06-backend/pyproject.toml`, with a
`CHANGELOG.md` entry.

## 10 · Rollback, stated before shipping

The column is **additive and nullable**. Rolling back is `migrate customers 0063`, which drops
`move_no` and its index and leaves every `move_in_jobs` row otherwise intact; `move_records` and
`wizard_parks` are untouched by the down path because this change writes nothing new to either.
The screen falls back to the request link it showed before. **The one thing that does not roll
back is the counter**: numbers issued to jobs are spent, so a rollback leaves gaps in the `MVI-`
series — which `BR-TEN-035` already permits and §7 already states.

## 11 · What the browser found that no unit test could

Step 2d of the build process is *prove it by clicking*, and on this change it earned its place
twice. `10-scripts/br_cus_1090_move_in_number_walkthrough.mjs` ends at **17 checks, all passing**;
its first run ended at 12 of 13, and both failures were real:

1. **A door the server served and the page never drew.** `moveRecordActions` has emitted
   `Open the request →` on a non-null `requestRef` since it was written, with both call sites
   hardcoding `null` and a note reading *"the day it starts arriving, this needs no change at
   all"*. That was true of the CONDITION and false of the branching: the in-flight arm **returns
   before `requestRef` is ever considered**, so folding the new state into it left the walk back
   served, typed and drawn nowhere. `tsc`, vitest and every gate were green over it — hard-won
   law 2, found by clicking. The new state has an arm of its own now and **neither ratified arm
   moved by a byte**.
2. **Two cells the vitest fixture could not produce.** The new length check measured every `<td>`
   and went red on an ADDRESS (`3450 Oak Ridge Dr · Unit 1`, seven "words") and on a **27-word
   parked cell that is mostly the clerk's own note**. B14 rule 33 caps what WE write; an address
   is a tenant's VALUE and a reviewer's free text must not be cut to six words (the chart of
   accounts settled that one the same day). So the check's subject is now a stated ABSENCE, it
   prints how many cells it did NOT cover beside how many it did, and the parked cell is filed as
   `DEF-CUS-6192` rather than silently excluded.

**And the services were the third.** They were served by the API and rendered by nothing, which
is the same defect as (1) one field over. They are a row on the job's page now.

## 12 · Status

**BUILT and pushed on `claude/laughing-thompson-kpmwih` in `2.328.0`.** Human review pending; the
row is in `12-governance/09-human-review-ledger.md`.

⚠ **THE FIRST COMMIT OF THIS CR, `c311d3f1b`, CARRIES ANOTHER LANE'S MESSAGE.** Its TREE is
correct — the five governance files of this CR, 250 insertions, no deletions — and its subject
line reads *"Two governance docs still said OQ-MET-12520 was OPEN after the PO closed it"*,
which belongs to a lane that worked on 2026-09-20. The cause is `DEF-GOV-6191`: a compound
command that was refused as a whole never wrote the message file, and `push_paths.sh` read a
two-day-old `msg1.txt` left in the **shared** scratchpad. It checks the file is non-empty and
cannot tell a stale one from a fresh one. **It is recorded here rather than rewritten**, because
rewriting a pushed commit on a branch three lanes are working in costs more than the wrong
subject line does.
