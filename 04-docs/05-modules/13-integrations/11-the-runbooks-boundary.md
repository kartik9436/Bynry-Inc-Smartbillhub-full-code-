# integrations — the Runbooks boundary, as the Product Owner models it

**PO working session, 2026-09-06, five exchanges. Recorded under CLAUDE.md law 9 and law 10.**
This is not a feature and nothing here commissions one: `BR-INT-054` says *"NOTHING IS TO BE
BUILT AGAINST THIS RULE YET"* and that sequencing is unchanged. This file exists so that the
next agent, **with only the repository**, builds the same thing — which is law 10's test, and
the reason a model that lived only in a chat session is written out in full.

> **Where each part of this model is law.** This file is the MODEL and the REASONING.
> The normative statements are `BR-INT-055`–`065` in [`02-business-rules.md`](02-business-rules.md),
> the batch and its states are [`04-flows.md`](04-flows.md) Part 3, the infrastructure
> requirement is [`10-execution-plan.md`](10-execution-plan.md) §9, and the wave-by-wave
> application is `CR-069` §20.9. Where this file and a `BR-` row differ, **the rule wins** and
> the divergence is a defect in this file.

---

## 0 · The corrections come first, because the wrong version is what gets reinvented

The PO corrected me **four times** across the session. Recording only the conclusion would
throw away the most valuable part: each correction is a reading that is *obvious, plausible and
wrong*, and a reader who is not shown it will arrive at it again by themselves.

| # | What I said | What the PO ruled | Why the wrong version is attractive |
|---|---|---|---|
| **1** | The value mapping (`ACHCHECK` → *Bank transfer*) is **"a dictionary, not business logic"**, so it is integration settings. | **Wrong. It is business logic wherever it is stored.** It is how the runbook decides what to write. | Because it *looks* like configuration — two columns and a lookup. The shape is a dictionary; the PURPOSE is a decision about what a record means. |
| **2** | *What their success and failure codes mean* belongs in integration settings — it is per-vendor. | **Wrong. The PO moved it to the runbook.** Interpreting a `429` or a `401` **for our processing** is meaning, not reach. | Because the codes are a property of the vendor, so they feel like they belong beside the endpoint and the key. But the question being answered is *what do we now DO*, and that is processing. |
| **3** | The earlier drafts described integrations as one shape — **we call them**. | **Wrong. There are FOUR directions**, and the other three behave differently enough to change the design. See §A. | Because *we pull* is the one everyone pictures, and it is the one the first waves built. |
| **4** | (Implied by 3) every connection has a schedule. | **Wrong. When THEY start it there is no schedule** — the trigger is their call, a third trigger beside scheduled and one-off. See §C.1. | Because a scheduler is the first thing you build for a batch, and *they push* is not a batch. **Nobody should build a scheduler for a doorbell.** |

**The single test that settles all four, and it is the thing to remember if nothing else is:**

> **PURPOSE, NOT SHAPE.**
> Integration settings answer *"how do I talk to this vendor, and am I allowed to right now?"*
> **Anything about what the data MEANS is the runbook's.**

Corrections 1 and 2 are the same test applied twice. Both times I sorted by SHAPE — a lookup
table looks like config, a status code looks like a vendor property — and both times the PO
sorted by PURPOSE and got the other answer.

---

## A · The four directions

A utility's connections come in four shapes. **The earlier drafts described only the first**,
and that is correction 3.

| Direction | Real example | Who starts it |
|---|---|---|
| **We pull** | Kiosk payments, the bank file, the City's address service | **Us** — on a schedule, or one-off |
| **We push** | Email and SMS provider — we hand them our messages to send | **Us** — on a schedule, or one-off |
| **They push** | The kiosk posts a payment to us; the email provider reports a bounce | **Them**, whenever |
| **They pull** | A partner reads our invoices with a key we issued | **Them**, whenever |

### A.1 · This is not new schema — the code has had these four since wave B

⚠ **The four directions the PO named are exactly the four quadrants already built**, and saying
so is the point of this section: nobody should add a `direction` field, because there is one.
`06-backend/apps/integrations/runners/__init__.py` opens with *"The four quadrants — direction ×
initiative picks the runner, and there is no fifth cell"*, and `BR-INT-028` already declares
both axes **per operation**.

| PO's words | `direction` | `initiative` | Runner | The runner file's own sentence | The card says |
|---|---|---|---|---|---|
| **We pull** | `in` | `us` | `runners/fetch.py` | *we go and collect something* | *We collect* |
| **We push** | `out` | `us` | `runners/deliver.py` | *we send them something* | *We send* |
| **They push** | `in` | `them` | `inbound.py` (module root) | *they send us something (the door)* | *They send* |
| **They pull** | `out` | `them` | `runners/serve.py` | *they read from us* | *They read* |

Two consequences worth stating rather than leaving to be inferred:

1. **The axes are closed and exhaustive**, so there is no fifth direction and a manifest cannot
   declare one — `registry.py` validates both against closed vocabularies.
2. **A quadrant name never reaches a screen.** `DELIVER` and `SERVE` are internal; the clerk
   reads *We collect* / *They send*. **The PO's four names are the MODEL's vocabulary, not
   necessarily the clerk's** — where the two differ, the catalogue wins (B14 rule 35: a
   catalogue is written in its own language). No copy is being changed by this document.

⚠ **A provider is a set of operations, not one direction.** `BR-INT-028` puts direction and
initiative on the **operation**, so one provider can occupy two quadrants at once — the email
provider is *we push* for the messages we hand it and *they push* for the bounce it reports
back. Wave `F` is exactly this and carries both. **Never classify a provider; classify an
operation.**

---

## B · The split — what is integration settings, and what is the runbook

**Integration settings — *how to reach them, and may we?***

* who the vendor is (name, endpoint)
* **their** keys, where we hold them
* **our** key, where they hold it
* payload shape
* how many records per call
* **test the connection**
* **on / off for this vendor**
* where they may call us from
* how often they may call us

**Runbook — *what to do with it?***

* when it runs — schedule, one-off, or **their call**
* the data check, before anything
* **what their success and failure codes mean**
* what the data means, including `ACHCHECK` → *Bank transfer*
* walking records one at a time
* writing when conditions map
* recording why a record failed
* the result, and closing the batch

### B.1 · The two corrections, in their own place

⚠ **THE PO CORRECTED ME TWICE ON THIS LIST AND BOTH CORRECTIONS ARE PART OF THE RULE.**

* **The value mapping is not "a dictionary, not business logic".** It is **how the runbook
  decides what to write**, so it is business logic **wherever it is stored**. The storage
  location is not the test; the purpose is. A mapping table living in an integrations table
  does not make the mapping an integrations concern — which is precisely the situation wave `D`
  is in today, and precisely why `OQ-INT-1727` exists.
* **Interpreting a `429` or a `401` is the runbook's, not integration settings'.** I had put
  *what their success and failure codes mean* on the settings side because the codes are the
  vendor's. The PO moved it. **Reach is *can I call them*; meaning is *what do I now do*** —
  and `429` → *retry with a longer wait* versus `401` → *stop and fetch a person* is a
  processing decision that happens to be keyed by a vendor's number.

**This is not a distinction without a difference.** §G below sorts failures into two buckets by
*who can fix it*, and the bucket is chosen **from the vendor's codes** — so if code
interpretation lived in integration settings, the failure policy would be split across the
boundary and neither side could state it whole.

### B.2 · How this sits on `BR-INT-054`

`BR-INT-054` as amended 2026-09-06 gives integrations exactly three things — **(a)** building a
connection · **(b)** holding keys and secrets · **(c)** the lifecycle of a connection — and
gives Runbooks **business logic · scheduling · processing**. This section is the **same line
drawn item by item** rather than a new one:

| The PO's list here | `BR-INT-054`'s item |
|---|---|
| vendor name and endpoint · payload shape · records per call · where they may call from · how often they may call | (a) building a connection |
| their keys · our key | (b) holding keys and secrets |
| test the connection · on/off for this vendor | (c) the lifecycle of a connection |
| when it runs | **scheduling** — Runbooks (this is the word the 09-06 sharpening added) |
| the data check · their codes' meaning · what the data means · walking records · writing · recording a failure · the result | **business logic and processing** — Runbooks |

**Nothing in this model moves the line `BR-INT-054` draws.** It says the same thing in the
PO's own vocabulary and adds the three direction-specific behaviours in §C, which
`BR-INT-054` does not address at all.

---

## C · Direction-specific behaviour — the points that change the design

### C.1 · When THEY start it, there is no schedule — the third trigger

There are **three** triggers, not two:

1. **Scheduled** — a cadence the utility set.
2. **One-off** — a person pressed the button.
3. **Their call** — ⚠ **the trigger IS the inbound request.**

⚠ **Say this plainly so that nobody builds a scheduler for a doorbell.** *They push* and *they
pull* have **no cadence, no due time, no next-run and no catch-up policy**, and a screen that
shows a *Next run* field for one of them is showing a field that can never have a value. A lane
reading `BR-INT-024` (cadence, spreading, skip-if-still-running, catch-up) must know that
**every word of it applies to the two directions WE start and to no others.**

This is correction 4, and it is the one most likely to be missed, because a scheduler is the
first thing anyone builds for a batch and *they push* is not a batch.

### C.2 · They push — the door and the work are two separate acts

They call → **we check the key, refuse duplicates, save exactly what arrived, and reply fast.**
**That is integrations, and it stops there** (`OQ-INT-1729`, ruled 2026-09-06, option (a)).
Everything after — reading it, deciding what it means, writing a record — **is the runbook, and
may happen a second later.**

⚠ **WRITE DOWN WHY, BECAUSE THE REASON IS OPERATIONAL AND NOT ARCHITECTURAL, AND WITHOUT IT
SOMEBODY WILL "SIMPLIFY" THE TWO HALVES BACK TOGETHER:**

> **The vendor is waiting on our reply and will re-send if we are slow.**
> **So answering the door must never wait on processing.**

Fold the processing into the door and a slow runbook becomes a *duplicate delivery* from every
vendor at once — not a slow screen, but a correctness failure on a money path, arriving as a
retry storm precisely when the system is least able to absorb it.

The pipeline itself is already law and is **not** being restated here: `BR-INT-021` (authenticate
before the body is trusted · persist raw before processing · reply before the work is done) and
`BR-INT-030` (the reply is a **declared position** — after `authenticate`, `dedupe`, `persist`
or `apply`). **What this section adds is the OWNERSHIP line across that existing pipeline**:
the first three positions are integrations', and `apply` is the runbook's.

### C.3 · They pull — there is no vendor data to interpret

A partner reads **our** invoices. **Nothing came from outside, so nothing needs mapping.**
Integration settings do the whole job — their key, where they may call from, how often, on or
off — and **the only record is who read what, and when** (`BR-INT-035`: a run with
`direction = inbound_read`, `trigger = partner`, the key's hint as *who*).

⚠ **PRECISION MATTERS HERE, AND A RULED VERDICT DEPENDS ON IT.** *"No vendor data to
interpret"* is a statement about **what arrives**, and in this direction nothing arrives. It is
**not** a claim that this direction is free of business logic altogether, because there is still
a **payload we compose**, and composing one is a **projection** — `BR-INT-033` keeps the
projection separate from the codec for exactly this reason, and `CR-069` §20.4 already puts
projections on the Runbooks side (*"building a business record out of our data … is ETL"*).

**The worked case is the difference between wave `R` and wave `S`, both *they pull*, ruled the
same day with different verdicts:**

* **Wave `R` — `+ integrations`, whole.** We mint a key, show it once, revoke it. **There is no
  payload at all**, so there is nothing to project and nothing to interpret. This is the
  direction in its purest form.
* **Wave `S` — `÷ split`.** Machine authentication, the allowlist refusal, the rate limit and
  *every page is a run* stay. What moves is **what is in the payload** — `tenderType` through
  the mapping rows, `accountString` from the ledger codes. **That is outbound ETL**, and it
  moves for the same reason correction 1 moved the value mapping: it decides what a record
  MEANS.

**So the direction removes INBOUND interpretation, not the outbound projection**, and the two
verdicts are consistent once that is said. ⚠ It has to be said, because the summary sentence
*"integration settings do the whole job"*, read literally, would tell a lane that wave `S` is
`+ integrations` whole — contradicting a verdict the PO ruled the same day. **The verdicts stand
and are not re-drawn here** (see §H).

### C.4 · We push is the mirror of we pull

**Same batch, same states, same failure handling** — records travelling the other way. There is
no second design and no second set of states: §E and §F apply unchanged.

The one thing to name is the far end's answer: **the provider's per-message result —
*accepted*, *rejected: bad address* — is read exactly like any other vendor's codes**, through
§B's rule (correction 2) and sorted by §G's buckets. *Rejected: bad address* is **needs a
person**; a `429` from the same provider is **retry**.

⚠ **`BR-INT-018` still governs the CONNECTION's own outcome here**: a provider that returns
`200` and will not say how many it accepted has not succeeded — it leaves us **`unconfirmed`**.
That word is about the connection's answer, not about the batch's progress; see §F.2.

---

## D · Infrastructure — separate compute per utility

**The PO's words: this will be heavy for each utility, and they must be able to set up separate
compute.** Six requirements:

1. **Work is queued PER UTILITY**, not one global queue — **one utility's heavy night must not
   be everyone's.**
2. **The runner is its own deployable**, separate from the web application.
3. **A setting says which pool a utility's runbooks use.** **The default is a shared pool** — so
   a utility that never asks for its own compute is not made to think about pools.
4. **Moving a utility to its own compute is a SETTING CHANGE** — no migration, no code change,
   no downtime.
5. **Every pool still enforces tenant isolation.** ⚠ **Separate compute is CAPACITY, never a
   relaxation of CLAUDE.md hard rule 1** — `app.tenant_id` is set and RLS `FORCE` is on in a
   dedicated pool exactly as in the shared one. A pool boundary is not a security boundary and
   must never be described as one.
6. **A utility on its own compute fails alone** — its runner dying stops no one else's batches.

### D.1 · This EXTENDS `BR-INT-041`; it does not replace it

`BR-INT-041` already says integrations work runs on **its own named queue with its own consuming
worker, off the billing workers** — *"one utility's dead mail server holds every other utility's
queue"* is the thing it prevents, and `BR-INT-022`'s per-connection concurrency cap (2 on an
8-worker pool) is the same instinct one level down.

**What is new is the axis.** `BR-INT-041` separates work **by kind** (integrations off billing).
Requirement 1 separates it **by tenant**, and requirements 2–4 make the separation something a
utility can be MOVED between without a deployment. Under `BR-INT-041` alone, three hundred
utilities share one integrations queue, and requirement 1 says that is not enough.

⚠ **And this stays with integrations rather than moving to Runbooks**, which is worth stating
because §B has just given Runbooks everything that decides anything. `BR-INT-054` is explicit:
*"The QUEUE and the WORKER are not the scheduler and stay here: they are how a connection's work
runs, which is item (c), and Runbooks runs on them."* **The pool is plumbing, not a decision.**
Runbooks decides *when* and *what*; the pool is *where it runs*, and that is item (c).

### D.2 · Why it changes wave sizing

Requirement 2 — a separate deployable — is **not** a thing that can be added at the end. A
runner that starts as a thread inside the web application and is later pulled out is a
re-architecture, not a setting. That is why this belongs in the execution plan (§9 there) and
not only in this file.

---

## E · The batch

**The steps, in order:**

1. **Fires at 12:30 in the time that utility has saved**, or a person runs it once.
2. **Is this vendor on?** If not, **stop and say *Off***.
3. **Data check.**
4. **Take keys, API and call details from integration settings.**
5. **Call, in the chunk size the settings hold.**
6. **Walk records one at a time.**
7. **Conditions map → write.**
8. **Conditions don't → record why THAT RECORD failed.**
9. **Show what was achieved, and close.**

Step 2 is a state and not merely a branch: *Off* is a **deliberate** outcome, not a fault (§F).
Steps 4 and 5 are the boundary in miniature — the runbook *takes* the keys and the chunk size
from integration settings and does not own them.

### E.1 · Clock changes: run once, skip the repeat

**PO ruling.** When the clock goes back and a wall-clock time occurs twice, **the batch runs
once and the repeat is skipped.**

**Why, in the PO's own terms: a batch running twice is worse than one running an hour late.**
Late is a delay; twice is a duplicate — and on any direction that moves money, a duplicate is a
correctness failure that a person has to unpick.

⚠ **The PO named a live example: *"we shipped a defect last night where meter reads drew a day
early west of Greenwich, the same root cause."*** That is **`DEF-MET-4101`**, filed 2026-09-05
and fixed 2026-09-06 in `2.197.1`. **State what it actually was, so the parallel is not
mis-remembered as something it is not:** it was a *display* fault — a calendar date served as a
raw instant and then converted into the tenant's timezone, so every meter read drew one day
early for any tenant west of UTC. It was **not** a double-run. **The shared root cause is the
one the PO drew the line to: a clock question answered in the wrong frame**, where every check
in the repository compared UTC and the product showed local, so the two never met. `BR-INT-024`
already requires cadence to be evaluated in the tenant's own timezone; this ruling settles what
happens when that timezone hands the same wall-clock time back twice.

⚠ **THE MIRROR CASE IS NOT RULED, AND IS RECORDED HERE RATHER THAN ASKED (law 13).** The PO
ruled the **repeat** (clocks back). When clocks go **forward** the wall-clock time may never
occur at all, and 12:30 simply does not happen that day. **This model does not settle it.** The
frame for settling it already exists and no new question is needed to reach it: `BR-INT-024`
carries *skipped and recorded as skipped* and *never auto-caught-up for anything that moves
money*, which is the same shape of answer. **No `OQ` is minted** because `BR-INT-054` commissions
nothing here — no lane can reach this before Runbooks is commissioned — and minting a question
the PO must answer today for code nobody may write is the re-ask law 13 forbids. **Whoever
commissions Runbooks settles it then, and this paragraph is the note that it is open.**

### E.2 · Mode is chosen at the START of the run

Two modes, and the choice is made **before the walk begins**, never inferred from what happened:

| Mode | What it means | When it is right |
|---|---|---|
| **All or none** | Either all 1,000 land or none do. | **Money.** |
| **Update what is received** | Each record stands alone — **993 land, 7 are named.** | Everything where a partial result is useful. |

⚠ `BR-INT-023`'s per-row `SAVEPOINT` is what makes *update what is received* possible at all,
and `BR-INT-029`'s idempotency modes (`refuse` / `reconcile`) are the same distinction at the
arrival layer. ⚠ **And law 14 applies with full force**: `try/except IntegrityError: continue`
**cannot** implement *update what is received* on PostgreSQL — a failed statement poisons the
whole transaction — and the SQLite test suite cannot see the difference, so it passes green and
loses production data. **A nested `transaction.atomic()` is the only option, and the comment
must say so.**

---

## F · Batch states

**The PO asked for one or two words each.**

| State | Meaning |
|---|---|
| **Waiting** | Scheduled, not started |
| **Off** | Vendor switched off — **deliberate, not a fault** |
| **Checking** | The data check, before any call |
| **Running** | Walking records |
| **Done** | Everything written |
| **Partial** | Some written, some named — **only under *update what is received*** |
| **Rolled back** | Under ***all or none***, something failed and **nothing** was written |
| **Interrupted** | Died mid-run; **some records are already in** |
| **Failed** | **Never started** — bad key, API unreachable, data check failed |

**Read the table as three groups**, because the distinctions are the whole value of it:

* **Off** is not **Failed**. One is a person's choice, the other is a fault. Collapsing them
  puts a support call on a switch somebody deliberately flipped.
* **Failed** is *never started*; **Rolled back** is *started and undone*; **Interrupted** is
  *started and NOT undone*. The three differ by **what is in the database now**, which is the
  only question anyone actually has.
* **Partial** and **Rolled back** are mode-locked: Partial cannot occur under *all or none*, and
  Rolled back cannot occur under *update what is received*. **A state machine that allows either
  crossing has lost the mode.**

### F.1 · Interrupted earns its keep

**It is the only state where a re-run must know what it already did.** So: **each record carries
its own identity, and a re-run recognises the 400 already written and does not write them
twice.**

This is not a new mechanism — `BR-INT-020` already declares the idempotency key **by the
operation's shape** and `BR-INT-029` gives it a mode. What §F adds is the **reason the key is
not optional**: without per-record identity, Interrupted is indistinguishable from Failed and
the only safe response to either is to do nothing, which strands the batch.

### F.2 · These nine are the BATCH's states — they do NOT replace the run outcome vocabulary

⚠ **Two vocabularies exist and they are deliberately separate. Do not merge them.**

| | The nine states here | `BR-INT-018` / `BR-INT-039`'s outcome |
|---|---|---|
| **Whose record** | The **runbook's batch** | Integrations' **`IntegrationRun`** |
| **What it describes** | How far the batch got and what is in the database | What the **connection** did and whether the far end confirmed a count |
| **Vocabulary** | Waiting · Off · Checking · Running · Done · Partial · Rolled back · Interrupted · Failed | `succeeded` · `failed` · `unconfirmed`, with attempted / succeeded / failed / skipped / `changed` |

`BR-INT-054`(3) is what keeps them apart, and it is worth quoting because it settles the
question in advance: a run row recording *a connection authenticated, pulled a file and took
three seconds* is **lifecycle** and stays with integrations; a row recording *what was decided
about the 899 rows inside that file* is **Runbooks'**.

⚠ **`unconfirmed` has no counterpart among the nine, and that is correct rather than an
omission.** It is a statement about **the far end's answer** — *they returned 200 and would not
say how many they took* — not about a batch's progress. A batch whose connection came back
`unconfirmed` may still be **Done**, **Partial** or **Interrupted**; the two records answer
different questions about the same event.

---

## G · Failure handling

**Sort by WHO CAN FIX IT, not by what went wrong.** Two buckets:

| Bucket | Examples | What happens |
|---|---|---|
| **Retry** | Timed out · rate limited · their server erred · connection dropped | **The batch retries itself a few times, waiting longer each time.** |
| **Needs a person** | Address doesn't exist · account isn't ours · amount is negative | **Held, with its reason.** |

**Four rules:**

1. **The runbook decides the bucket from the vendor's codes** — ⚠ **which is exactly why
   interpreting those codes is the runbook's and not integration settings' (correction 2).**
   This rule is the reason that correction matters: put code interpretation on the settings side
   and the failure policy is split across the boundary, with neither side able to state it whole.
2. **A code we don't recognise goes to *needs a person*.** ⚠ **Safer to ask than to retry
   forever on something unseen.** The unsafe option must be the one you type (hard-won law 3),
   and here the unsafe option is *assume it is transient*.
3. **A clerk can re-run just the failures.** **Chasing 7 timeouts must not re-do 993 good
   records** — which is only possible because of §F.1's per-record identity, and is the
   practical payoff of it.
4. **Twice the same way and it stops retrying**, so **one bad record cannot consume every run
   forever.**

⚠ **Rules 1 and 2 together are why *unknown* is a bucket decision and not a shrug.**
`BR-INT-031` already rules that unknown values **degrade inbound and refuse outbound**; rule 2
is the same instinct applied to a status code rather than a data value. ⚠ **And rule 1's
retry-with-a-longer-wait is `BR-INT-022`'s existing backoff-with-jitter**, including its warning
that **retrying through a `429` turns a delay into a ban** — `Retry-After` is honoured and a
token bucket sits in front. The buckets here decide *whether* to retry; `BR-INT-022` decides
*how*.

---

## H · The consequence for work already built

**The value mappings and the per-record run results are the RUNBOOK's.** Read against §E's
steps, they are *conditions map* (step 7), *record why it failed* (step 8) and *show what was
achieved* (step 9) — three of the nine steps, and all three on the runbook's side of §B.

**About three people-weeks are built and one clerk screen is live** (wave `C` 1.5 + wave `D`
1.5 at the plan's own sizing; screen **S143**, shipped at `2.131.0`). So:

> **They keep running where they are, and move as a unit when Runbooks exists. Nothing is
> rebuilt.**

⚠ **`OQ-INT-1727` IS THE OPEN QUESTION THAT FORMALLY SETTLES THIS, AND IT STAYS OPEN.**
**This section is the FRAME in which that question will be answered — it is NOT its answer**,
and no lane may treat it as one. The register's three options are still all live: **(a)** both
move to Runbooks and S143 moves with the mappings · **(b)** both stay as a named, dated
exception to `BR-INT-054` · **(c)** they stay where they are and Runbooks READS them across a
seam, owning neither.

**Why it is the PO's and not ours** (law 13's first case): it is **a ruling colliding with
signed, shipped work**, and the supersession must be **stated, never assumed**.

⚠ **What this frame DOES settle, so that a lane is not paralysed:** *keep running where they
are* means **nothing stops and nothing is rewritten today**, under every one of the three
options. The question is **where the code eventually lives**, not whether it keeps working.

---

## The gaps this model does not close — stated, not hidden

| Gap | Where it stands |
|---|---|
| The **spring-forward** mirror of §E.1 — a wall-clock time that never occurs | **Not ruled.** Recorded in §E.1; no `OQ` minted, and §E.1 says why. |
| **`OQ-INT-1727`** — where the ≈3 people-weeks of built Runbooks-side work lives | **OPEN.** §H is the frame, not the answer. |
| Whether the clerk-facing card copy (*We collect* / *They send*) should adopt the PO's four names | **Not raised with the PO.** No copy is changed by this document; §A.1 records the difference. |
| Where the batch record and its nine states physically live | **Undecided with Runbooks' home** — execution plan §8.2 already records that the home is undecided. |
