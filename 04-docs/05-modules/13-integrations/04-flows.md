# integrations — Flows & States

Screens: S8 Settings → Integrations (details: A1 screen inventory + addendum, A9 navigation map).
State machines extracted from the ratified rules (BR-INT-001..016; A1/A11 addenda; B7; CL-1 matrix). A5 predates the connect surface; the lifecycle here is law per the citations in 02-business-rules.md.

## 1. Connection lifecycle (US-INT-002/003)
```
NOT_CONNECTED ──connect (modal: method oauth|apikey|sftp · env · cadence · secret→encrypted store)──▶ CONNECTED
      ▲                                                                                                  │
      │                                       test-connection / provider failure (B7 "Failed · Retry")   ▼
      └──── disconnect (IS-6 confirm + consequence copy; secret DESTROYED; history untouched) ◀─── FAILED ──retry──▶ CONNECTED
```
- Coming-soon cards (CL-1): no lifecycle — Connect disabled at UI AND API; zero secret acceptance (US-INT-011/012).
- Every transition → `audit_log` `integration.connected|test_run|updated|disconnected` (masked refs only, BR-INT-003/014).
- Reconnect after disconnect = fresh credentials always (secret is gone).

## 2. The card grid dispositions (US-INT-001 — CL-1 matrix)
```
v1-REAL:            Email band (Google OAuth · Microsoft OAuth · SMTP) → connect live, SENDING W6 (OQ-073)
                    Transactional ESP (OQ-074) · Bank & lockbox profiles (→ EP-INT-03) · QBO/Xero as FILE targets (BR-LED-020)
COMING-SOON:        Stripe W7 · Plaid W7 (TD-9/OQ-015) · Twilio v1.1 · QBO/Xero LIVE sync v2 · Itron v2 · Sensus v2 (NFR-27) · Okta/Azure AD v2
UNPLACED (I-1):     Lob/DocPrint — connectable per A1 addendum; CL-1 silent → candidate OQ (pack report)
```

## 3. Email activation flow (US-INT-005/006/007 → the BR-NOT-005 seam)
```
connect mailbox (OAuth/SMTP + send-from + test email)  ─┐
connect ESP (API key + sending-domain checklist)        ─┤─▶ adapter BINDING (sole connection = default;
                                                        ─┘    both connected = explicit audited choice, OQ-074 guidance)
                                                                │  (integrations-owned CONFIG — read by US-NOT-002/003)
   pre-W6: rows rest queued w/ deferred marker (US-NOT-003) ◀───┤
   W6: dispatcher drains backlog in tenant-config batches ◀─────┘
   no binding / stale binding → dispatch home shows config-missing; rows WAIT (never a shared-sender fallback)
   provider errors → health surface (Failed · Retry) → US-NOT-004 panel + US-NOT-013 dashboard
```

## 4. File-channel profile lifecycle (US-INT-008/009/010)
```
create profile (bank: label·format·mapping·source | accounting: target·label·code-readiness pointer)
   → ACTIVE (offered in S35/S38/S43 pickers; batches record their producing profile)
   → edit (audited before/after; forward-only — history keeps its producing profile/version)
   → DEACTIVATED when used-by > 0 (IS-1 🔒 — delete blocked; vanishes from pickers; reactivatable)
   → hard delete ONLY when used-by = 0
IDEMPOTENCY INVARIANT: file+tags (BR-PAY-028/OQ-044) + period+target (BR-LED-004) blocks survive
every profile edit/deactivate/reactivate/disconnect — no lifecycle action launders a duplicate.
```

## 5. Consumer read-model (US-INT-004 — the only cross-module surface)
```
integration_connections (🔒 I-2) ──service-function read (B1)──▶ S8 grid states (GET /integrations)
                                                              ▶ US-NOT-004 provider-status panel · US-NOT-013 dashboard health
                                                              ▶ S42 Connections panel (ledger D-7) · S38/S35 profile pickers
                                                              ▶ platform subprocessor-register feed (soc2 §5 classes only)
Consumers NEVER write; credentials resolve server-side inside the seam at use time — never handed out.
```

---

# Part 2 · The substrate — twelve end-to-end journeys and three that gain a leg (`CR-069`, 2026-09-03)

**Ids `J48` … `J59`.** `J30`–`J47` are the portal's (reserved 2026-09-03); **next free was `J48`**,
verified 2026-09-03 against `08-qa/01-e2e/journeys/` and `12-governance/14-id-reservations.md`. ⚠ **The
confirmation table said nine journeys (`J48`–`J56`); the design's own §2.11 lists eleven new rides and
phase 5's exit test is a twelfth** — so twelve are described and reserved, and the reason is written here
rather than left to be inferred.

⚠ **THE JOURNEY FILES IN `08-qa/01-e2e/journeys/` ARE NOT WRITTEN YET.** This file is the authoritative
description of all twelve and the reservation of their ids; a story's `journeys:` frontmatter cites an id
described here — **do not read that as a file that exists** (hard-won law 1). `J14`, `J17` and `J19` exist
and each gains a leg below; their files are amended when the leg is built, not before.

**Every journey crosses a module boundary — integrations hands to notifications, payments, ledger,
metering or identity and never writes their tables** — so every one has a handoff contract: what upstream
leaves, what this journey leaves. **Run `J51`, `J52`, `J55` on real PostgreSQL** (law 14).

## Phase 2 — the first adapter

### `J48` · Connect day
**Actor:** Alex Reed, System Admin, Brazos Bend · **Screens:** S8 → S141 → S142 · **Modules:** integrations → notifications (the read-model) · **Stories:** US-INT-013 · 014 · 015 · 016 · 017 · 019 · 025 · 026
**Upstream leaves:** seventeen manifests registered; no connection rows; `smtp_secret_ref` migrated (`US-INT-026`). **The ride:** Alex opens Settings → Integrations and sees **seventeen cards all reading *Not set up***; presses **Connect** on Custom SMTP; types host, port, username, password, send-from; **Save and test** sends one real message to `alex@brazosbend.example`; the card turns **Working**. **Ends when:** the card's `describe()` line reads *billing@brazosbend.example · Custom SMTP* **and no plaintext exists in the database, the log or the audit trail** — three assertions. **Leaves:** one connection row, one credential v1, one run row (`trigger = manual`, `succeeded`), one audit row with `••••3F9A`.

### `J49` · Wrong key Friday
**Actor:** Alex, 5 pm Friday · **Screens:** S142 → S141 · **Stories:** US-INT-015 · 020 · 024
**Upstream leaves:** `J48`'s working connection. **The ride:** Alex pastes the wrong key as a replacement; `test()` fails; the card goes **Not working** with the mail server's own sentence; Alex presses **Roll back**. **Ends when:** sending resumes **without re-authorising**, and both credential versions are on the record (v1 active again, v2 inactive). **Leaves:** two credential rows, two run rows, two audit rows — and the plaintext of neither password anywhere.

### `J53` · The dead mail server
**Actors:** two tenants · **Screens:** S8 · S142 · **Modules:** integrations → billing (tenant B's run) · **Stories:** US-INT-016 · 022
**Upstream leaves:** tenant A (Brazos Bend) with a working mailbox; tenant B (Silver Creek) with a 240-bill run queued (`J17`'s fixture). **The ride:** tenant A's provider stops answering mid-cycle — the fixture **hangs 90 s**, it does not error. **Ends when:** tenant B's run finishes on time; tenant A's connection shows **Not working** with a breaker note; **nobody else notices**. **Leaves:** tenant A's skipped-and-recorded window; tenant B's bills issued.

### `J17` · Delivery life — **gains its first real leg**
`J17` exists. The queue row now actually reaches a provider through the adapter. **Ends when:** delivery counts stop reading *not reported* for the **send** half — and **stay *not reported* for bounces until the feedback path of Figure 8 exists** (`US-INT-023`), never zero.

## Phase 3 — OAuth on the same rails

### `J50` · Token lapse averted
**Actor:** the nightly sweep, then Alex · **Screens:** S7 · S142 · **Modules:** integrations → notifications (the warning email) · **Stories:** US-INT-027 · 029
**Upstream leaves:** Silver Creek's Microsoft 365 credential with `expires_at = 12 Sep`; today 1 Sep. **The ride:** the credential moves inside eleven days; the sweep raises **Needs re-authorising by 12 September. After that, bills stop going out.** on the dashboard and by email; Alex re-authorises via the return trip. **Ends when:** the connection keeps its **entire run history** across the re-auth — phase 3's exit test. **Leaves:** credential v2, the warning cleared, one queued email.

### `J56` · The Thursday it went quiet
**Actor:** the due sweep · **Screens:** S142 · S8 · **Stories:** US-INT-029 · 030
**Upstream leaves:** a head-end connection with a weekly allowance of 10,000, 9,980 spent, a collection due needing 40. **The ride:** Thursday's collection falls due. **Ends when:** it **declines to start**, the screen reads *9,980 of 10,000 requests used this week · resets Monday*, and **nobody finds out from an estimated bill three weeks later**. **Leaves:** one declined row with the figure; the collection runs after Monday's reset.

## Phase 4 — files out, files in

### `J51` · The same bank file twice — **PostgreSQL**
**Actor:** Priya Menon, Billing Clerk · **Screens:** S38 → S142 · **Modules:** integrations → payments · **Stories:** US-INT-033 · 020
**Upstream leaves:** `J14`'s 40-row lockbox file. **The ride:** Priya uploads Tuesday's file; on Wednesday she uploads it again by mistake. **Ends when:** the second run reads **refused duplicate — the same file as Tuesday 06:10**, **and no payment is applied twice**; the hash was computed before parsing. **Leaves:** one committed batch (payments'), two run rows sharing `input_hash`.

### `J52` · One bad row in nine hundred — **PostgreSQL**
**Actor:** Priya · **Screens:** S38 → S142 · **Modules:** integrations → payments · **Stories:** US-INT-032 · 033
**Upstream leaves:** a 900-row file, row 412 violating a constraint. **Ends when:** **899 rows are in, one is named on the run** with its reason, and Priya fixes and re-uploads **just that one**. **Leaves:** 899 payments (payments'), a receipt naming row 412, a second one-row run.

### `J55` · Backfill Tuesday — **PostgreSQL**
**Actor:** the nightly collection · **Screens:** S142 · **Modules:** integrations → metering (readings through its service) · **Stories:** US-INT-028 · 034 · 035
**Upstream leaves:** Monday's collection of 1,240 readings for three days, one of them billed on `BL-2609-0044`. **The ride:** Tuesday collects the same three days; the supplier has filled four gaps and revised two values. **Ends when:** **six rows move, 1,238 do not, and none of the already-billed ones is touched** — the difference on the billed one is a correction. **Leaves:** four new readings, two superseded (metering's rows), one correction, a run reading *1,240 read · 6 revised*.

### `J57` · The size that unblocked a bill ⚠ blocked `OQ-INT-1485`
**Actor:** the register sync · **Screens:** S142 → the bill run · **Modules:** integrations → assets → billing · **Stories:** US-INT-036
**Upstream leaves:** account `ACC-1048` unbillable *for want of a connection size*. **The ride:** a register sync runs; the size arrives from the system that installed the meter. **Ends when:** the run goes from **blocked** to drafted. **Until `OQ-INT-1485` is ruled the ride ends one step early:** the difference is shown and nothing is written.

### `J14` · Lockbox day — **gains a profile**
`J14` exists. The file arrives through a **named bank connection** instead of a bare upload. **Ends when:** the batch records its producing connection, and editing the connection afterwards does not restate history.

### `J19` · Month-end close — **gains the saved export target**
`J19` exists. The period pack goes to a **remembered destination** (Figure 10's saved target), and the file is not offered while accounts are unmapped.

## The GL track — a partner reading from us

### `J54` · The partner's morning ⚠ blocked `OQ-INT-1481`
**Actor:** a finance system, on its own schedule · **Screens:** S144 · S142 · **Modules:** identity (machine auth) → integrations → ledger/payments (reads only) · **Stories:** US-INT-037 · 039 · 040 · 041
**Upstream leaves:** an issued key (`••••7Q2F`), an allowlist, tender and account mappings. **The ride:** the partner collects yesterday's payments and bills over three pages at 02:41. **Ends when:** the access log shows **three reads**, the counts match what we hold, **and nothing of ours was scheduled**. **Leaves:** three `inbound_read` runs; nothing written anywhere else. **Until `OQ-INT-1481` is ruled the connection cannot be enabled and the ride runs only against the test partner.**

## Phase 5 — the inbound door, and one conditional

### `J59` · The kiosk payment, twice — phase 5's exit test
**Actor:** a payment kiosk · **Screens:** the payment's detail · S142 · **Modules:** integrations → payments (`record_payment`) → ledger · **Stories:** US-INT-018 · 037 · 038 · 044
**Upstream leaves:** the five test accounts, the kiosk credential and allowlist, the tender mappings. **The ride:** the kiosk posts `K-88231 · $42.10 · CASH` for `ACC-1048`; it appears on the account with no clerk keying it, channel **KIOSK**; the kiosk **replays** the same notification; then a **return** arrives carrying the same id. **Ends when:** the replay is recognised and **applied exactly once**, answered **409** before anything is posted — **and the return is not mistaken for a duplicate** and reverses the payment. Demonstrated by replaying a real captured payload. **Leaves:** one payment, one reversal (new rows), three inbound runs, the raw envelopes.

### `J58` · Allowed, then stopped ⚠ conditional `OQ-INT-1482`
**Actors:** Maria Alvarez (customer — ⚠ the portal's Maria Alvarez is Pine Hill's; a fixture-name collision, `DEF-INT-3615`, see `US-INT-046` §4), then Priya · **Screens:** S146 → S145 · **Modules:** portal → integrations → the grantee's reads · **Stories:** US-INT-046 · 041
**The ride:** Maria allows *SunPath Installers* twelve months of usage; two months later she rings and asks to stop it; Priya revokes on S145. **Ends when:** **the installer's very next request is refused — not their next nightly collection** — and the ended row stays on the record. **Nothing is built until `OQ-INT-1482` is ruled.**

---

**Index by story:** J48 → 013 · 014 · 015 · 016 · 017 · 019 · 025 · 026 · 021 · J49 → 015 · 020 · 024 · J50 → 027 · 029 · J51 → 033 · 014 · 038 · J52 → 032 · J53 → 016 · 022 · 020 · J54 → 037 · 039 · 040 · 041 · 020 · J55 → 028 · 034 · 035 · 029 · J56 → 029 · 030 · J57 → 036 · J58 → 046 · J59 → 018 · 037 · 038 · 044 · J14 → 033 · J17 → 023 · J19 → 031 · 033. ⚠ *(2026-09-03, `DEF-INT-3613`: this index attached `020` to `J51` and `033` to `J52`; neither story's frontmatter cites that journey and neither journey exercises it — both journeys assert the rules those stories own through `BR-INT-020` instead.)*

---

# Part 3 · The batch, its nine steps and its nine states (PO 2026-09-06)

**Rules: `BR-INT-057` (three triggers) · `BR-INT-062` (the steps, and the clock change) ·
`BR-INT-063` (the mode) · `BR-INT-064` (the states) · `BR-INT-065` (failure buckets).
The model whole: [`11-the-runbooks-boundary.md`](11-the-runbooks-boundary.md).**

⏸ **NOTHING HERE IS COMMISSIONED.** `BR-INT-054` still says *"NOTHING IS TO BE BUILT AGAINST
THIS RULE YET"*. This part records the shape so that whoever builds it builds the ruled one.

⚠ **THE BATCH IS THE SHAPE OF TWO DIRECTIONS ONLY — *we pull* and *we push*.** *They push* is a
door (§3.4) and *they pull* is a read (§3.5); **neither has a batch, a cadence or a next-run
time**, and a screen offering one is offering a field that can never hold a value
(`BR-INT-057`).

## 3.1 · The three triggers — and the third one is not a schedule

```
SCHEDULED  ── the cadence a utility set ──────────────┐
ONE-OFF    ── a person pressed the button ────────────┤──▶  a batch begins   (we pull · we push)
                                                      │
THEIR CALL ── the inbound request IS the trigger ─────┴──▶  NO batch, NO cadence, NO next run
                                                            (they push → the door, §3.4)
                                                            (they pull → a read,   §3.5)
```
⚠ **Every word of `BR-INT-024`** — cadence in the tenant's timezone, the deterministic spread
across 300 connections, skipped-and-recorded when the previous run is still going, the catch-up
policy, `manual` never swept — **applies to the two directions WE start and to no others.**

## 3.2 · The nine steps

```
 1  fires at 12:30 in the time that utility has saved   ── or a person runs it once
 2  is this vendor ON?  ── no ──▶  stop, and say Off                         [state: Off]
 3  data check          ── bad ─▶  stop                                     [state: Failed]
 4  take keys / API / call details FROM INTEGRATION SETTINGS   (settings own these, not us)
 5  call, in the CHUNK SIZE the settings hold
 6  walk records ONE AT A TIME                                              [state: Running]
 7      conditions map      ──▶  WRITE
 8      conditions don't    ──▶  record why THAT RECORD failed  (bucket per BR-INT-065)
 9  show what was achieved, and close      [Done · Partial · Rolled back · Interrupted]
```
Steps **4 and 5 are the boundary in miniature**: the runbook *takes* the keys and the chunk size
and does not own them. Step **2 is a state, not merely a branch** — *Off* is a deliberate
outcome and never a fault.

## 3.3 · The state machine

```
                    ┌──────────────────────────────────────────────┐
                    │                                              │
  (trigger)         ▼                                              │
   ──────▶  [ Waiting ] ──vendor switched off──▶ [ Off ]            │  ⚠ Off is DELIBERATE.
                 │                                                 │     It is not a fault and
                 │ vendor is on                                    │     never reads as one.
                 ▼                                                 │
            [ Checking ] ──data check fails──▶ [ Failed ] ◀─────────┘
                 │                                  ▲
                 │ data is good                     │ bad key · API unreachable
                 ▼                                  │ (NEVER STARTED — nothing written)
            [ Running ] ───────────────────────────-┘
                 │
     ┌───────────┼────────────────────────┬─────────────────────────┐
     │           │                        │                         │
     ▼           ▼                        ▼                         ▼
 [ Done ]   [ Partial ]            [ Rolled back ]           [ Interrupted ]
 everything  some written,          something failed          died mid-run;
 written     some named             and NOTHING was           SOME RECORDS ARE
             ⚠ mode: update         written                   ALREADY IN
                what is received     ⚠ mode: all or none       ⚠ re-run must know
```

⚠ **THE TWO END STATES ARE MODE-LOCKED (`BR-INT-063`).** *Partial* cannot occur under **all or
none**; *Rolled back* cannot occur under **update what is received**. **A state machine that
allows either crossing has lost the mode**, and the mode is chosen at the START of the run,
never inferred from what happened.

| State | Meaning | What is in the database now |
|---|---|---|
| **Waiting** | Scheduled, not started | nothing |
| **Off** | Vendor switched off — **deliberate, not a fault** | nothing |
| **Checking** | The data check, before any call | nothing |
| **Running** | Walking records | in flight |
| **Done** | Everything written | all of it |
| **Partial** | Some written, some named — *update what is received* only | **993 of 1,000** |
| **Rolled back** | Something failed — *all or none* only | **nothing** |
| **Interrupted** | Died mid-run | **some — and we must know which** |
| **Failed** | **Never started** — bad key, API unreachable, data check failed | nothing |

**Three distinctions carry the whole table, and they are why nine words beat three:**
* **Off is not Failed** — a person's choice versus a fault. Collapsing them puts a support call
  on a switch somebody deliberately flipped.
* **Failed / Rolled back / Interrupted** differ by **what is in the database now** — *never
  started* · *started and undone* · *started and NOT undone*. That is the only question anyone
  actually has.
* **Partial and Rolled back name the mode**, so a reader can tell which contract the run was
  under without going to look.

### Interrupted earns its keep

**It is the only state where a re-run must know what it already did**, so **each record carries
its own identity and a re-run recognises the 400 already written and does not write them twice**
(`BR-INT-064`; the key itself is `BR-INT-020`, declared by the operation's shape). Without it,
Interrupted is indistinguishable from Failed, the only safe response to either is to do nothing,
and the batch is stranded.

### ⚠ These nine do NOT replace the run outcome vocabulary

```
  THE RUNBOOK'S BATCH  (these nine)          INTEGRATIONS' IntegrationRun (BR-INT-018/039)
  ───────────────────────────────────        ────────────────────────────────────────────
  how far did the batch get, and             what did the CONNECTION do, and did the far
  what is in the database?                   end confirm a count?
  Waiting · Off · Checking · Running ·       succeeded · failed · unconfirmed
  Done · Partial · Rolled back ·             + attempted / succeeded / failed / skipped
  Interrupted · Failed                       + changed (reconcile, BR-INT-029)
```
`BR-INT-054`(3) keeps them apart: *a connection authenticated, pulled a file and took three
seconds* is lifecycle and stays here; *what was decided about the 899 rows inside that file* is
Runbooks'. ⚠ **`unconfirmed` has no counterpart among the nine and that is CORRECT** — it
describes the far end's answer, so a batch whose connection came back `unconfirmed` may still be
**Done**, **Partial** or **Interrupted**.

## 3.4 · They push — the door, and where it stops

```
  their call ──▶ [ authenticate ] ──▶ [ dedupe ] ──▶ [ persist raw ] ──▶  REPLY  ──▶ (vendor released)
                 └──────────── INTEGRATIONS — and it STOPS HERE ─────────┘
                                                                          ┊  a second later
                                                                          ▼
                                                              [ apply ] — THE RUNBOOK
                                                              read it · decide what it means ·
                                                              write the record
```
⚠ **WHY THE LINE IS HERE, AND IT IS OPERATIONAL RATHER THAN ARCHITECTURAL — this sentence is
what stops someone folding the two halves back together: THE VENDOR IS WAITING ON OUR REPLY AND
WILL RE-SEND IF WE ARE SLOW, SO ANSWERING THE DOOR MUST NEVER WAIT ON PROCESSING.** Fold
processing into the door and a slow runbook becomes a duplicate delivery from every vendor at
once — a correctness failure on a money path, arriving as a retry storm exactly when the system
can least absorb it.

The pipeline is already law — `BR-INT-021` (authenticate before the body is trusted, persist raw
before processing, reply before the work is done) and `BR-INT-030` (the reply is a **declared
position**). **What `BR-INT-058` adds is the ownership line across it: the first three positions
are integrations', `apply` is the runbook's** (`OQ-INT-1729`, ruled option (a) 2026-09-06).

## 3.5 · They pull — a read, not a batch

```
  their call ──▶ [ machine auth ] ──▶ [ allowlist ] ──▶ [ rate limit ] ──▶ [ compose payload ] ──▶ page out
                 └──────── INTEGRATION SETTINGS DO THIS ────────┘          └── the PROJECTION ──┘
                 every page is a run: who read what, when, under which key  ⚠ this half is ETL
                 (BR-INT-035 — direction=inbound_read, trigger=partner)        (CR-069 §20.4)
```
**Nothing arrives, so nothing needs mapping** (`BR-INT-059`). ⚠ **But that removes INBOUND
interpretation, not the OUTBOUND projection** — which is exactly why the two *they pull* waves
were ruled differently on the same day: **wave `R` is `+ integrations` whole** (mint a key, show
it once, revoke it — **no payload at all**), while **wave `S` is `÷ split`**, because its payload
is composed from our own records (`tenderType` through the mapping rows, `accountString` from the
ledger codes) and **building a business record for someone else is outbound ETL.**

## 3.6 · Failure — sorted by who can fix it

```
  a record fails ──▶ read the vendor's code ──▶ WHICH BUCKET?     (the RUNBOOK reads it —
                                                                   BR-INT-056 correction 2)
        ┌──────────────────────────────────────┴──────────────────────────────┐
        ▼                                                                     ▼
  [ RETRY ]                                                          [ NEEDS A PERSON ]
  timed out · rate limited · their server erred ·                    address doesn't exist ·
  connection dropped                                                 account isn't ours ·
        │                                                            amount is negative
        │ a few times, waiting longer each time                              │
        │ (BR-INT-022's backoff with jitter; Retry-After honoured;           │ held, with its reason
        │  retrying through a 429 turns a delay into a BAN)                  │
        ▼                                                                    ▼
  twice the same way ──▶ STOPS RETRYING                          a clerk re-runs JUST THE
  (one bad record cannot consume every run for ever)             FAILURES — chasing 7 timeouts
                                                                 must not re-do 993 good records
        ▲
        │  ⚠ A CODE WE DON'T RECOGNISE DOES NOT COME HERE ──────▶ it goes to NEEDS A PERSON.
           Safer to ask than to retry for ever on something unseen (hard-won law 3: the unsafe
           option must be the one you type; here the unsafe option is "assume it is transient").
```
⚠ **Re-running just the failures is only possible because of §3.3's per-record identity** — it
is the practical payoff of *Interrupted* earning its keep, not a separate feature.

## 3.7 · Clock changes — run once, skip the repeat

```
  clocks BACK  ── 12:30 happens TWICE ──▶  RUN ONCE, SKIP THE REPEAT          ✅ RULED 2026-09-06
                  why: a batch running twice is worse than one running an hour late.
                  Late is a delay; twice is a DUPLICATE, and on a money path a
                  duplicate is a correctness failure a person has to unpick.

  clocks FORWARD ─ 12:30 never happens ──▶  ⚠ NOT RULED. Recorded, not asked (law 13).
                  BR-INT-024's "skipped and recorded as skipped" and "never auto-caught-up
                  for anything that moves money" is the frame that will settle it.
                  No OQ minted — BR-INT-054 commissions nothing, so no lane reaches this
                  before Runbooks is commissioned. See BR-INT-062.
```
⚠ **The PO named a live example — *"meter reads drew a day early west of Greenwich, the same
root cause"* — and it is `DEF-MET-4101`** (filed 2026-09-05, fixed 2026-09-06 in `2.197.1`).
**Stated precisely so the parallel is not mis-remembered: it was a DISPLAY fault, not a
double-run** — a calendar date served as a raw instant and then converted into the tenant's
timezone. **The shared root cause is a clock question answered in the wrong frame**, where every
check compared UTC and the product showed local, so the two never met.
