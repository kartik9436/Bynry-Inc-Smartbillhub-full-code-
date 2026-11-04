# The end-to-end clerk walk

**PO ruling 2026-09-15.** The decision-log row of that date beginning *"RULED: WHAT
'AN END-TO-END RUN FROM SCREEN' MEANS"* carries the PO's words verbatim and is the
authority; this file is the procedure.

⚠ **THE ONE-LINE VERSION, BECAUSE EVERY WALK BEFORE THIS ONE ASKED THE WRONG
QUESTION.** A conformance walk asks *does each drawn control exist and does it fire*.
**That can be answered YES by a screen that stops the clerk three times.** This walk
asks whether a clerk can serve somebody at a counter, start to finish, without the
product refusing them. **The pass mark is the clerk getting through.**


PO, verbatim:

> *"when youa re done with all steps - can you run end to end request creation from
> screen theway clark will do it and then end to end view and approval the way clark
> will do it; perform all 3 actions approvae, refuse and ask for more"*

**This is a BROWSER walk, not a test run.** Hard-won law 6: no gate in this repository
looks at rendered output, and nine defects in one day were found this way and by
nothing else. A green suite is not this.

## Precondition — THE NEW WORK IS IN, AND THE WALK IS NEVER RUN ON WHAT IS ALREADY SHIPPED
PO verbatim, correcting a walk run against the live product:

> *"you are doing it wrong - you ave to do this test when new nackend and froentend is
> developed"* · *"not on what existi in prodctrightnow"*

**Every lane of the change must have landed first.** Until they have, the screens move
under the walk and a screenshot proves nothing — and a walk over already-shipped
screens only re-documents a gap that has already been measured, which costs the PO
their time twice. Wait.

## Setup
1. `git fetch` + `git merge --ff-only`, then verify by subtraction (`git diff --numstat <tip>` prints nothing).
2. Apply any unapplied migrations to the demo database — a lane found `GET /service-requests`
   returning HTTP 500 today for exactly this reason (`customers/0050` sat on the branch unapplied).
3. `cd 07-frontend && npx vite build` — the dist on disk is stale the moment a lane lands.
4. Backend on a free port, `DJANGO_SETTINGS_MODULE=config.settings.local`; SPA through
   `07-frontend/server.mjs`. See `10-scripts/11-smoke-stack.sh`, `SMOKE_SKIP_SEED=1`.
   ⚠ **Do NOT run seed_demo or provisioning** — it would rewrite the PO's tenant.
5. Chromium at `/opt/pw-browsers/chromium`. Never `playwright install`.

## Who and where
Tenant `/brazosbend`, sign in as `dana@brazosbendutilities.com` (password: line 99 of
`apps/tenancy/management/commands/seed_demo.py`).

⚠ **NEVER act on `SR-26-0001`…`SR-26-0008`.** Those are the PO's own eight. Everything
this walk touches is created BY this walk.

## The walk — three requests, because two of the three actions are terminal
Approve and Refuse each end a request. Ask-for-more does not. So the walk creates
**three** requests through the wizard and takes one down each road.

### Part 1 · Creation, six steps, three times
For each of the three, click every step the way a clerk does — no API calls, no shortcuts:

| Step | What the clerk does | What to capture |
|---|---|---|
| 1 Customer | channel, name, email, phone, **date of birth, driving licence**, SSN; the person/company selector | the kind branch — a company must NOT be asked for a licence |
| 2 Connection | category + sub-category **on this step**, services from the **multiselect**, a start date **per service** | the chip list and the `N of M selected` count |
| 3 Addresses | **search the register, pick a premises and a unit**; town/state/ZIP read-only from the record; billing address | that nothing is typed into city/state/ZIP |
| 4 Documents | attach one, leave a required one missing | the filters, and that a missing document does not block creation |
| 5 Fees | application fee only; take money by **card** on one, **cheque** on another, **cash** on the third | the tender fields, and the receipt number |
| 6 Check | the review blocks, **what goes out to the applicant**, the template picker | then **Submit** |

**After each submit, verify in PostgreSQL, not on screen:** the request exists with its
number; the counter receipt posted (payments + a balanced ledger pair against cash and
customer credit — the PO's ruling of today); the acknowledgement is queued with the
applicant's own address on it.

### Part 2 · The request screen, three actions
Open each request from the register and act on it.

1. **Approve** — the modal, the outcome radios, `WHAT APPROVING WILL DO`.
   Verify after: the job row exists and names the request; the outstanding travels;
   the held money becomes the account's; the decision message is queued.
2. **Refuse** — a reason from the five, and the words to the applicant.
   Verify after: state is terminal; the refusal letter carries the CLERK'S words and no
   reason code; **the fee stays collected and becomes revenue** (the PO ruled it
   non-refundable today); the money is still in the books.
3. **Ask for more** — the tick list and the message.
   Verify after: state is `more_info`, NOT refused; the message carries what the clerk
   typed; **nothing moves in payments or the ledger** (the PO ruled ask-for-more changes
   nothing).

## What to capture
Every step and every modal, at **1440 and 1280**, into
`<scratchpad>/clerk-walk-shots/`, named so a reader knows what they are looking at
without being told. The PO reads these in chat beside the drawing.

## What to report
Plain sentences. What a clerk sees at each step in their own words; where the product
and the drawing differ; every figure verified against the database rather than the
screen; anything that refused, with the exact sentence it showed.

## Cleanup — ASK FIRST
The demo tenant already holds 8 rows of lane debris (`SR-26-0009` *Probe*, `SR-26-0010`
…`SR-26-0016` *Lane A Walkthrough*) plus a raised connection. This walk adds three more
and a connection. **Offer to remove all of it in one pass; do not delete without the
PO's word** — it is their reference data and deletion is not reversible.

---

## ⚠ THE INTENT, STATED BY THE PO AFTER THIS PLAN WAS WRITTEN — IT CHANGES THE PASS MARK

PO, verbatim:

> *"the intent here is the workflow for claark run smoothly and there are no issues or
> too many refual so that clark is unable to perform his task"*

**So the walk is NOT "does every control exist and does every button fire".** It is: **can a
clerk get a real person served, start to finish, without the product stopping them?**

That reframes what counts as a finding. A screen that draws every element the blueprint
draws and still refuses the clerk three times is a FAILED walk, not a passed one.

### What to record, and it is the main output
**Every refusal the clerk meets, counted, with its exact on-screen sentence**, and for
each one a judgement in plain words:

| Ask of each refusal | |
|---|---|
| What did it say? | The exact sentence a clerk reads. If it is a code, a blank, or silence, that is itself the finding |
| What is it protecting? | A signed rule, money, or the law — or nothing |
| Could the clerk have known? | A refusal that arrives only after ten minutes of typing is worse than one at the door |
| Is there a way forward? | A refusal with no next step is a dead end, and a dead end is a defect |

**A refusal that protects nothing real is a defect, and it is filed as one.**

### Two are already known, and both are the PO's to settle
Found by the approval lane today, both filed, both left unfixed because they change what
a clerk can DO:
- **`DEF-CUS-5399`** — an unpaid application fee BLOCKS approval. The blueprint says on
  p083, in as many words, *"The money does not gate approval and the documents do"*.
  The product refuses. A clerk who took a part payment at the counter cannot approve.
- **`DEF-CUS-5404`** — a DISCONNECT request is blocked by the applicant's own arrears,
  and a disconnect is the one request where owing money is the normal case.

**Both are exactly the shape the PO has just named.** The walk must hit them and report
them as blockers rather than stepping around them with a tidy fixture.

### The walk's own rule
**Use real, ordinary data — a part-paid fee, a missing document, an applicant who owes
money.** A walk on a perfect record proves nothing, because the refusals only fire on the
imperfect ones, and every real counter is imperfect.


---

## A BUG FOUND IN A WALK IS FIXED IN THE SAME PASS

PO verbatim: *"in case you find any bugs fix them when you do"*.

This supersedes the report-and-hold posture a walk would otherwise take. A defect found
mid-walk is **filed AND fixed**, not handed back with a screenshot.

⚠ **THE BOUNDARY, SO NOBODY OVERRUNS IT** (law 13, and `13-change-process.md` §1):

| Found | What you do |
|---|---|
| A bug — the product does not do what it was built to do | **Fix it**, file it, prove it |
| A dead end — a refusal with no way forward | **Fix it**; a dead end is a defect |
| A refusal protecting nothing real | **File it.** Fixing it may be a rule change — check first |
| **A contradiction between two SIGNED surfaces** | **Report it. Do NOT fix it.** Reversing either reverses a signed rule, and that is the PO's alone |

**Two of the last kind are already live and must be reported, never fixed, by any walk
that meets them:**
- `DEF-CUS-5399` — the Accounts blueprint p083 says *"The money does not gate approval
  and the documents do"*, and the product refuses approval over an unpaid application
  fee. A clerk who took a part payment at the counter cannot approve.
- `DEF-CUS-5404` — a **disconnect** request is blocked by the applicant's own arrears,
  and a disconnect is the one request where owing money is the normal case.

Both stop a clerk, which is exactly what this walk exists to catch — and both need the
PO, because the fix is a ruling and not a patch.

---

## THE NEW CONNECT WALK — OWED, 2026-09-16

PO, verbatim, on the eight-step new connect wizard:

> *"once you bild new conenct request - please to end to end walk - simialr to what
> Clark will do . ensure he is able to perform this workflow and it procude the
> intented result - you ahve to do it from product screens"*

**Same procedure, same pass mark, one addition.** *"and it procude the intented
result"* is the new clause and it changes what finishing means: on the service
request walk the question was whether a clerk could get through. Here a clerk can
get through a wizard that writes nothing — that is exactly what this one did until
today, when the final button posted to an address answering **404** and eight
finished screens wrote no build at all, with no error a clerk could act on.

**So the walk ends in the DATABASE, not on the confirmation screen.** Fill the
wizard in as a clerk, press **Create connection**, and then read back:

| What | Expected |
|---|---|
| The premises | one row, with the town and the parcel the clerk typed |
| The connection | one row, numbered |
| Units | the count the clerk asked for, plus the common area |
| Meters | one per service point, **and on the right unit** — they all landed on unit 1 until today |
| Plan assignments | one per unit |
| Work orders | what step 5 left standing, **actually raised** — the screen promised nine and the server raised none until today |
| The customer | **matched** where one was attached, not a second copy minted |
| The owner's account | opened, and the build tagged to it |
| The quote | posted to the books, or an honest stated absence saying why |
| The messages | queued, or an honest refusal naming the question that blocks them |

⚠ **THE PRECONDITION STILL BINDS AND IT IS THE PO'S OWN RULING:** the walk runs
when the new work is in, never against what is already shipped. Two lanes were
still building when this was asked.

⚠ **AND A REFUSAL IS A RESULT, NOT A FAILURE OF THE WALK.** Several things are
deliberately, visibly absent — deposits pending `OQ-BIL-12381`, the three letters
pending `OQ-376`. **The walk records what the clerk was TOLD**, and an honest
stated absence passes where a silent nothing fails. What fails is a screen that
promises a count the server did not produce, which is the shape this wizard has
already failed in twice.
