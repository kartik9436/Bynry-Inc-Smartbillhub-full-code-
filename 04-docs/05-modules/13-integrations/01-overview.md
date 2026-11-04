# Module — integrations

Provider-agnostic seams (B7): BYO mailbox, transactional ESP, bank/lockbox file profiles, accounting file targets — plus the visible-but-later cards (Stripe/Plaid, Twilio, live QBO/Xero, Itron/Sensus, Okta/Azure AD). Connect/test/manage/disconnect per the A1/A11 addenda. **This module owns the CONNECTION surface only — it sends, imports and exports NOTHING** (dispatch = notifications BR-NOT-005; import/rec flows = payments BR-PAY-019/023; handover = ledger BR-LED-004/020).

**Owns (B2):** integration connections + file-channel profiles (per-tenant, encrypted credentials — secrets never rendered back; masked refs only). ⚠️ Table not yet itemized in B2 — anchoring flagged (field-map discrepancy I-2, Eng-Lead 🔒).
**Screens:** S8 Settings → Integrations (card grid + connect modals + profile lists); consumer surfaces read-only: S8 Notifications tab (provider status), S35/S38 (bank profiles), S42/S43 (export targets).
**Boundary rule (B1):** no other module writes this module's tables; cross-module reads via service functions only (US-INT-004 read-model).

**Governing ruling:** **CL-1(a) v1 connector matrix** (PO, 2026-08-08) — v1-REAL: BYO email (Google/Microsoft OAuth + SMTP), transactional ESP, bank/lockbox import profiles, accounting FILE export targets. VISIBLE-BUT-LATER (coming-soon card, connect disabled, wave label): Stripe/Plaid **W7** · Twilio SMS **v1.1** · QBO/Xero live sync **v2** (BR-LED-020) · Itron/Sensus MDM **v2** (NFR-27 gate) · Okta/Azure AD SSO **v2**. Email connections may be made early; customer sending activates **W6** (OQ-073/074 closures).

## Pack status (2026-08-09)
**12 stories · 4 epics authored** — see [`05-user-stories.md`](05-user-stories.md). Rules BR-INT-001..016 consolidated BY CITATION in [`02-business-rules.md`](02-business-rules.md).
- **EP-INT-01** the connections surface: S8 card grid (v1-real vs coming-soon per CL-1), connect modal lifecycle (method/env/cadence/test), encrypted secrets + masked-refs-always, IS-6 disconnect with consequence messaging, audit + read-model + subprocessor-register feed (W4).
- **EP-INT-02** comms connections: BYO mailbox (Google/Microsoft OAuth, SMTP + send-test), transactional ESP (API key + sending-domain checklist), the dispatcher's adapter binding + provider health for the delivery dashboard (W5; sending W6).
- **EP-INT-03** file channels: bank/lockbox import profiles (BAI2/CSV/OFX/QBO/QFX, upload-or-SFTP) consumed by US-PAY-003/021; accounting export targets (QBO-file/Xero-file/CSV/IIF + export-code readiness) consumed by US-LED-016; IS-1 lifecycle + idempotency survival (W4/W5).
- **EP-INT-04** future seams: the coming-soon cards as real deferred stories — rails W7, Twilio v1.1, live accounting v2, MDM v2 + NFR-27 gate, SSO v2 — gating at UI AND API, zero secret acceptance while gated.

**The spine:** every connection = encrypted per-tenant secret + a connection row; every lifecycle event audited with masked refs; consumers (dispatcher, payments, ledger, dashboards) READ one service-function read-model and never touch the tables; disconnect never loses queued or recorded data.

## Pack status (2026-09-03) — `CR-069`, the integration substrate

**Source:** *The Integration Substrate* — engineering design, baseline `2.109.0` (31 Aug), re-read at
`2.120.1` (1 Sep), 84 figures, 24 wireframes, 36 specification cards `C1`–`C36`. **Read to about page 106 of
~310** — the file is 32.8 MB against a 10 MB download cap (decision log 2026-09-03) — and completed from
`CR-069` §8, which carries every card's *"what done looks like on screen"* sentence. Product at `2.128.2`.

**34 stories · 9 epics · 36 rules · ~150 test cases · 34 test data sets · 5 tables · 31 endpoints · 12
journeys · 6 screens · 19 open questions.** ⚠ Deltas from the confirmed table, stated rather than implied:
endpoints 31 where the table said *provisional*; **journeys 12 (`J48`–`J59`) where it said 9** — the design's
own §2.11 lists eleven and phase 5's exit test is a twelfth.

| Epic | Phase | Stories | What it makes true |
|---|---|---|---|
| `EP-INT-05` the substrate | 1 | 013–019 | Manifests with operations as the unit, five tables anchored first, the four-method adapter, a queue with its worker, coming-soon refused by the API, one modal for every provider |
| `EP-INT-06` the run record | 1–2 | 020–023 | Five counts, `unconfirmed`, S142, the breaker, delivery and bounce that stay *not reported* until they exist |
| `EP-INT-07` credentials have a lifecycle | 2–3 | 024–028 | Versions and rollback, offboarding, the sender card folded in, the dated expiry warning, token exchange across a two-hour walk |
| `EP-INT-08` scheduling | 3–4 | 029–031 | The product's first beat schedule, the request budget, submit–poll–collect |
| `EP-INT-09` files in, files out | 4 | 032–036 | Savepoints proved on PostgreSQL, hash before parse, reconcile mode, safety parameters, the register sync (blocked) |
| `EP-INT-10` their words for our things | 1 / 4 | 037–039 | The target-reference rows, unknown values in and out, codecs |
| `EP-INT-11` the partner reading from us | GL track | 040–041 | Machine credentials shown once, the partner surface, the record of who read what (blocked `OQ-INT-1481`) |
| `EP-INT-12` GIS and the map | 4–5 | 042–043 | Browser executor, inline address search, the nightly reconciliation (blocked `OQ-INT-1470`–`1472`) |
| `EP-INT-13` the inbound door | 5 | 044–046 | The kiosk payment applied once, `indeterminate` (contingent), consent (conditional) |

**The five phases, each launchable (PO 2026-09-03 *"at the end of each pahse we should abl to luanch some
funtionlaity"*):** **1** — the Settings grid lists every integration we will ever offer and honestly says none
is set up; a connect on a coming-soon key is refused by the API · **2** — a utility connects its own mail
server and sends real email; a wrong password reads *the mail server rejected the password* and the credential
is provably absent from the database, the logs and the audit trail · **3** — Google or Microsoft connected, the
token renews itself, a dated warning eleven days ahead, re-authorising keeps the run history · **4** — files
out and files in; the same bank file twice is refused naming the first, **on PostgreSQL** · **5** — a payment
taken at a kiosk appears on the account by itself, a replay is applied once and answered 409, a return is not
mistaken for a duplicate.

**Execution plan (2026-09-03):** [`10-execution-plan.md`](10-execution-plan.md) — the five phases and the GL track as **19 waves and 122 tasks**, every wave ending in a clicked walkthrough of the running product and a version bump, every story placed exactly once (PO: *"each phase/wave should produce tangila eoutcome"*).

**Screens — `S141`–`S146` (`CR-069` §9; the document's `S116`–`S121` were all taken on 2026-09-03; `S147`
is next free):**

| Screen | What it is | Frame | Stories |
|---|---|---|---|
| `S141` | Connect / Manage modal — one frame, a field slot from the manifest, environment, cadence, Save and test, the four states, Replace credential, Disconnect (danger) | modal over S8 | 019 · 024 · 026 · 029 |
| `S142` | Connection detail — `describe()` line, state in words, the dated expiry sentence, the last twenty runs grouped by operation, budget figure, breaker note, *who has been reading* | T6 detail (B14 rule 20 table) | 020 · 021 · 022 · 030 · 031 · 032 · 034 · 041 · 045 |
| `S143` | Value mapping — *Their words* (red when unmapped) · *Waiting for a decision* (the GIS queue) | T5 list, two tabs | 037 · 038 · 043 |
| `S144` | Machine credentials — partner, hint, issued by/on, last used, state; issue / replace / revoke | T5 list | 040 |
| `S145` | Consents (staff) — customer, allowed, what, how much history, until, state; *Stop sharing* | T5 list — **conditional `OQ-INT-1482`** | 046 |
| `S146` | Consent (customer) — grant, see, stop; drawn in the portal when built and takes the next `CWP` id there | portal — **conditional** | 046 |

The **S8 Integrations tab** changes (`C1`): operations listed under a card, each with its own state, and the
*"arrives with"* sentence deleted from all eleven locale catalogues in the same commit as the grid. On-screen
badges for the six are a separate allocation into `g29_allocated_badges.txt` and are **not** decided here.

**What step 0 found, recorded rather than fixed silently:**
- **The document numbers its own new rules `BR-INT-018`–`036` and new stories `US-INT-013`–`034`** — above this
  repository's frontier, colliding with nothing. The morning's decision-log row recorded a +17 / +12 offset
  from the truncated read; the approved bands are kept and filled as `02-business-rules.md` Part 2 explains.
- **`CR-069` §11 says `16-integrations/`; the module lives here.** Recorded as a lane judgment; `16-` goes to
  `CR-070` as `16-work/`.
- **`payments/webhooks.py` is 577 lines, not one** (built 2026-09-03, `CR-060` `C21`, 15 tests). `T-9.04` is
  largely done; the inbound door reuses its guards (`US-INT-044`).
- **There is no `beat_schedule` anywhere in `config/`** — verified; `US-INT-029`'s two entries are the first.
- **Two live third-party calls have no connection record** — the Census geocoder and the Esri tiles. Defects, not
  changes (`CR-069` §0.3); both become manifests.
- **The accounting export's `target` column mixes a place with a format.** Defect, not a change; becomes
  `destination × codec` on the substrate.
- **The PO's ruling on ids landed while this was being written**: questions carry their module — the nineteen
  here are `OQ-INT-1470`–`1488`, the first of their kind.

🔒 **Sensitive paths — eleven of the thirty-six cards, and the stories that carry them:** `C13`, `C17`, `C18`,
`C22`–`C25`, `C26`, `C27`, `C30`, `C32` → `US-INT-034`, `035`, `040`, `043`, `045` (and `BR-INT-049`–`052`).
Each file implementing one is flagged `HUMAN-REVIEW-PENDING` with a row in `09-human-review-ledger.md` **in plain
English with a worked figure** — the figures are already in the stories (1,240 / 6 / 1,238 · 69,000 / 66,500 ·
$142.18 once, not twice). **And before phase 2 stores the first real credential:** the human sign-off on
`core/crypto.py`'s four self-made judgments (where the key comes from, what happens when it is absent, how
rotation works) — a review-ledger row, not a question.

**Blocked, and stubs rather than guesses:** eleven stories wait on nine of the nineteen questions —
`US-INT-036` (`OQ-INT-1485`), `040`/`041` (`1481`), `042` (`1471`, one branch), `043` (`1470`–`1472`), `045`
(`1476`, `1478`), `046` (`1482`). **`OQ-INT-1476` is the one to read first**: whether the processor accepts our
idempotency key decides whether a timed-out charge can ever be retried, and every `T-9` task waits on it.
`OQ-INT-1473` goes back to the PO as a closed ruling whose premise changed — not reversed here.

**Not done, and said so rather than implied:** the twelve journey files in `08-qa/01-e2e/journeys/` (described
in `04-flows.md` Part 2); **B2 is not edited** — anchoring the five tables in the brief is the build lane's first
task (`C34`) and closes I-2; no code, no migration, no frontend root. **The visual pass IS done (2026-09-03,
later the same day):** the PO uploaded *The Integrations Surface* (22 pages, 41 frames) and every frame is saved as
`wireframes/frame-NN-N.png` with `08-screen-layouts.md` mapping each screen to its frames and `09-component-inventory.md`
naming the pieces — see `wireframes/README.md` for provenance.

**Hazards written into the documentation:** the credential table is separate from the connection table and a
gate asserts the connection row holds no secret · `features/integrations/` joins `route-b-migrated.txt` in its
first commit or every Tailwind utility renders as nothing (B14 rule 21) · the savepoint, the reconcile mode and
the duplicate-file guard are proved on real PostgreSQL, because the SQLite suite cannot see them (law 14) · a
queue with no consuming worker accepts work and never runs it (`DEF-320`) · there is no `POST
/integrations/{key}/send`, and a gate says so.

## Pack status (2026-09-06) — the boundary in FOUR DIRECTIONS, and what each side owns

**PO working session, 2026-09-06. The model is written out whole in
[`11-the-runbooks-boundary.md`](11-the-runbooks-boundary.md); the rules are
`BR-INT-055`–`065`; the batch and its states are [`04-flows.md`](04-flows.md) Part 3; the
infrastructure requirement is [`10-execution-plan.md`](10-execution-plan.md) §9; the wave-by-wave
application is `CR-069` §20.9.** ⏸ **Nothing here is commissioned** — `BR-INT-054` still says
*"NOTHING IS TO BE BUILT AGAINST THIS RULE YET"* and that sequencing is unchanged.

### The four directions

⚠ **Every earlier draft in this pack described only the first of these** — *we call them* — and
the other three behave differently enough to change the design.

| Direction | Real example | Who starts it | Quadrant (already built) |
|---|---|---|---|
| **We pull** | Kiosk payments, the bank file, the City's address service | **Us** — schedule or one-off | `in`+`us` → `runners/fetch.py` |
| **We push** | Email and SMS providers — we hand them our messages to send | **Us** — schedule or one-off | `out`+`us` → `runners/deliver.py` |
| **They push** | The kiosk posts a payment; the provider reports a bounce | **Them**, whenever | `in`+`them` → `inbound.py` (the door) |
| **They pull** | A partner reads our invoices with a key we issued | **Them**, whenever | `out`+`them` → `runners/serve.py` |

⚠ **THIS IS NOT NEW SCHEMA.** The four directions the PO named are exactly the four quadrants
this module already runs on — `runners/__init__.py`: *"direction × initiative picks the runner,
and there is no fifth cell"* — and `BR-INT-028` already declares both axes **per operation**.
**Nobody should add a `direction` field.** ⚠ **And a provider is a set of operations, not one
direction:** the email provider is *we push* for the messages we hand it and *they push* for the
bounce it reports back. **Classify an operation, never a provider** (`BR-INT-055`).

### The split — the one test that decides it

> **PURPOSE, NOT SHAPE.** Integration settings answer *"how do I talk to this vendor, and am I
> allowed to right now?"* **Anything about what the data MEANS is the runbook's.**

| **Integration settings** — *how to reach them, and may we* | **Runbook** — *what to do with it* |
|---|---|
| who the vendor is (name, endpoint) | when it runs — schedule, one-off, or **their call** |
| **their** keys where we hold them | the data check, before anything |
| **our** key where they hold it | **what their success and failure codes mean** |
| payload shape | what the data means, incl. `ACHCHECK` → *Bank transfer* |
| how many records per call | walking records one at a time |
| **test the connection** | writing when conditions map |
| **on / off for this vendor** | recording why a record failed |
| where they may call us from · how often they may call us | the result, and closing the batch |

⚠ **THE PO CORRECTED THIS LANE TWICE ON THAT TABLE, AND BOTH CORRECTIONS ARE PART OF THE RULE
(`BR-INT-056`).** **(1)** The value mapping was argued to be *"a dictionary, not business
logic"* — **wrong: it is how the runbook decides what to write, so it is business logic
WHEREVER IT IS STORED.** **(2)** *What their success and failure codes mean* was put on the
settings side because the codes are the vendor's — **wrong, and the PO moved it: interpreting a
`429` or a `401` for our processing is meaning, not reach.** Both times the lane sorted by
**shape** (a lookup looks like config; a status code looks like a vendor property) and the PO
sorted by **purpose**. **The wrong version is the one a reader reinvents, which is why it is
written down rather than quietly replaced.**

### The three things about direction that change the design

1. ⚠ **WHEN THEY START IT, THERE IS NO SCHEDULE.** The trigger is **their call** — a third
   trigger beside *scheduled* and *one-off* (`BR-INT-057`). *They push* and *they pull* have no
   cadence, no due time, no next run and no catch-up policy. **Nobody should build a scheduler
   for a doorbell**, and **every word of `BR-INT-024` applies to the two directions WE start and
   to no others.**
2. ⚠ **THEY PUSH: THE DOOR AND THE WORK ARE SEPARATE ACTS** (`BR-INT-058`; `OQ-INT-1729` ruled
   option (a), 2026-09-06). We check the key, refuse duplicates, save exactly what arrived and
   reply fast — **that is integrations and it stops there.** **The reason is operational rather
   than architectural, and it is the sentence that stops someone folding the halves back
   together: the vendor is waiting on our reply and will re-send if we are slow, so answering
   the door must never wait on processing.**
3. ⚠ **THEY PULL: NOTHING ARRIVES, SO NOTHING NEEDS MAPPING** (`BR-INT-059`) — the only record
   is who read what and when (`BR-INT-035`). **But that removes INBOUND interpretation, not the
   outbound projection**, which is why wave `R` is `+ integrations` whole (no payload at all)
   and wave `S` is `÷ split` (its payload is composed from our own records, which is ETL).
4. **We push is the mirror of we pull** (`BR-INT-060`) — same batch, same states, same failure
   handling, records travelling the other way. No second design.

### What it adds to this module that was not here before

* **The batch, its nine steps and its nine states** — `04-flows.md` Part 3, `BR-INT-062`–`064`.
  ⚠ **The nine states do NOT replace `BR-INT-018`'s `succeeded` / `failed` / `unconfirmed`**:
  two records, two questions, deliberately separate.
* **Failure sorted by who can fix it** — *retry* versus *needs a person*, `BR-INT-065`. **An
  unrecognised code goes to *needs a person***, because it is safer to ask than to retry
  forever on something unseen.
* **Separate compute per utility** — `BR-INT-061` and `10-execution-plan.md` §9. It **extends**
  `BR-INT-041` (which separates work by KIND) with a **per-tenant** axis, and ⚠ **a pool
  boundary is capacity and never a security boundary** — hard rule 1 holds identically in a
  dedicated pool.

### Still open, and not closed by any of this

**`OQ-INT-1727` remains OPEN.** The value mappings and the per-record run results are the
runbook's, ≈3 people-weeks are built and screen **S143** is live; **they keep running where they
are and move as a unit when Runbooks exists, and nothing is rebuilt.** That is **the FRAME in
which the question will be answered and NOT its answer** — all three registered options are
still live, and it is the PO's to rule because it is a ruling colliding with signed, shipped
work (law 13).
