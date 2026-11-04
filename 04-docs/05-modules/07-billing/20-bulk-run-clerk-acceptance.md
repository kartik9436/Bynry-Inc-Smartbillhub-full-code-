# Bulk bill run — does it work for the CLERK? Acceptance criteria (2026-09-30)

Status: **THE RELEASE GATE FOR THE BULK BILL RUN**, written at the PO's direction: *"you are not looking from
clerk point of view - how they will run and what will be success criteria for them - are they able to run
the entire run end to end - how easy is to understand, how easily it work if something break down does it
tell clerk - you have to see user experience point of view, plus accuracy point of view plus scale point of
view"*. The build plan's tasks prove the CODE; this file proves the CLERK can do the job. The run is done
when every row below passes in a browser, on PostgreSQL, walked by a person as well as by J72/J73.

Each criterion is a thing the clerk can see or do, with a pass figure. Status is updated at each merge.

## 1 · Can the clerk run a whole cycle end to end?

| # | Criterion (what the clerk experiences) | Pass when | Proved by |
|---|---|---|---|
| U1 | A clean cycle runs Scope → Check → Sign off → Send without leaving the run or asking anyone | Done in one sitting, one primary button per step, no dead end | J72 E1 + person |
| U2 | They always know where they are and what happens next | Step name, what the step is for (≤ 6 words), the next button named for its act | person, against the drawings |
| U3 | They can leave and come back | Closing the browser mid-Check and reopening the run lands on the same step with progress intact | J73 F1 |
| U4 | Long work shows progress | Check, Calculate and Send each show *n of N* and keep moving; never a spinner with no number | J72 + J73 S2 |
| U5 | Problems are sorted so they can clear them | Category → tag → accounts, one tag at a time, *Answer for all N* pre-selected, per-row override, fix inline where possible | J72 E4/E5 |
| U6 | Every message says what, which account, and what to do | Rule 33 caps; a fix link or a named owner; never a bare error | J72 E2/E6, person |
| U7 | Nobody is forgotten | Held, blocked, left-out and nothing-to-bill accounts are listed in *Not in this run*, with a catch-up or next-cycle action | J72 E10 |

## 2 · Are the numbers right? (accuracy)

| # | Criterion | Pass when | Proved by |
|---|---|---|---|
| A1 | Everything adds up across the steps | Scope's accounts = Ready + Blocked + Held + Nothing to bill + Left out, on every step; Sign off's billed = bills Send issues | J72 E8/E9 |
| A2 | No account is billed twice | An account already billed for the period (by a one-time bill or an earlier run) gets no second base or usage | J72 + DEF-BIL-8473 test |
| A3 | No account disappears | Every account ends as sent, broken (with reason), or in *Not in this run*; none vanishes | J72 + DEF-BIL-8474 test |
| A4 | Each bill equals its draft | The issued bill's total = the Sign off draft's, to the cent | J72 E9 |
| A5 | The PO's rulings hold on real bills | The five fixed-charge cases, estimate true-up, price at period end — on the second month too | two-month tests + J73 A5 |
| A6 | Every clerk decision is traceable | Who answered what, when, on which account, visible in the run's check report after Send | J72 + report tab |

## 3 · When something breaks, does the clerk know?

| # | Criterion | Pass when | Proved by |
|---|---|---|---|
| F1 | A worker dies mid-Check | Progress resumes where it stopped; the clerk sees the run carry on; no account checked twice into two results | J73 F1 |
| F2 | Meter Reads (or another module) is down | A banner says what is down and who fixes it, with *Try again*; the run is kept | J73 F2 |
| F3 | Some bills fail at Send | Sent and failed listed apart, each failure with its reason, *Retry failed* sends only those; nothing sent twice | J72 E9 + J73 F3 |
| F4 | Two clerks open the same run | The second sees who is working on it; two Sends cannot both issue | J73 F4 |
| F5 | Something unexpected | The clerk gets a support reference, the run is kept, the account is blocked with that reference | test + J73 F5 |

## 4 · Does it hold at the size of the utility? (scale)

| # | Criterion | Pass when | Proved by |
|---|---|---|---|
| S1 | Check time | ≤ 10 min at 10,000 accounts; ≤ 30 min at 40,000 (after batching, B27/B28) | 19-check-cost-measured.md + J73 S1 |
| S2 | Screens stay quick at 40,000 accounts | A tag's account list, Sign off and Not in this run open in < 2 s, paged | J73 S2 |
| S3 | Send at scale | 40,000 bills issue with progress; a failure part-way resumes, no duplicate numbers | J73 S3 |
| S4 | Other utilities keep working | While one utility runs 40,000, another's run still starts (per-utility cap = half the billing workers, minimum 1 — decided 2026-09-30) | J73 S4 |

## 5 · What must be PROVED at each step, in the PO's words (2026-09-30)

PO, verbatim, on how we will know the bulk run works end to end: *"here it is important process complete for 1 account end to end and does not break down in between"*, and per step:

| Step | The PO's requirement (verbatim) | Proved by (E16/E17 run audit) |
|---|---|---|
| Whole run | *"process complete for 1 account end to end and does not break down in between"* | **E17 single-account trace**: ONE account followed from Scope to Send and into month two, every record it touches checked at every step |
| 2 Start checking | *"it is important all decision made by clark from screen for that bill run are saved correctly"* | Every decision the walk made on screen exists in the database with account, tag, answer, amount/unit, who, when — and nothing the clerk did not choose |
| 3 Work through problems | *"it is important all decision saved by clark are passed to bill run process correctly + it check the data from system if required + it create records other than bill due to impact on next billing"* | Each saved answer is what Calculate used (estimate quantity on the draft line, waived account not drafted, held account in Pending billing, fix written to its owning module and re-checked); where the answer needs system data it was read; and the non-bill records exist: estimate in Meter Reads, plan extended, pending-billing row, waive logged, carried items |
| 4 Calculate | *"it is important to check all draft bills are in database + summary is correct on screen"* | One draft per priced account in the database, none for held/blocked/waived; every figure on the screen summary equals the database sum |
| 5 Sign off / after | *"it is important background processes are completed for bulk bill run - communication, draft to final bills, ledger payments reading etc"* | After Send: every draft became a final issued bill; communication queued (paper at least, email/SMS per election); ledger journals posted and balanced; payments applied as decided; readings/estimates saved; no background job left pending or failed |
| 6 Send | (as ruled: sent and failed apart, Retry failed) | Every bill issued with its number, lines = draft to the cent, books balance, balance moved by the total, paper queued, audit row, second Send issues nothing |

## Where it stands (2026-10-01, 02:30 — build 2.417.0, J72 + accuracy + J73 at 1440 and 1280 on PostgreSQL 16)

The final bulk-run lane's branch, rebased on the tip `f8c216d71`, with the E16/E17 audit's four
defects fixed (`DEF-BIL-8650`–`8653`) and every walk re-run on that build. Three worlds on the local
PostgreSQL 16 cluster (`127.0.0.1:55433`), each reset from its snapshot before every walk: the
plain J72 seed, `--month-two` for the accuracy spec (the October reading planted after September
is sent, through Meter Reads' own commit), and `--send-failure` for F3. J73 F3 walks the
send-failure world *after* J72 has sent its September; F2 walks a fresh one.

| Check | Result | What decided it |
|---|---|---|
| U1 run a clean cycle | ✅ PASS | J72 E1 → E1b → E1c at 1440 and 1280: Scope → Check → Sign off → Send, 11 accounts |
| U2 always know where you are | ✅ PASS | E11 wave 3, 2.422.3: all 36 states beside their drawings at 1440 and 1280 — **36 match**; the last 8 (04, 11–14, 25, 28, 35) matched once the server sent the cycle's frequency, the meter number, payments apart from credits and the meter-read lock (`DEF-BIL-8691`, `8701`, `8682`, `8685`); table below. Wave 2 (2.418.9) had 28 match |
| U3 leave and come back | ✅ PASS | Re-opening lands on the same step (E8, E1c, E9, E10); closing mid-Check is F1, which passes |
| U4 progress as n of N | ✅ PASS by test | Check, Calculate ("754 of 1,371") and Send ("612 of 1,371") |
| U5 clear problems easily | ✅ PASS | E4 opens No reading on *Estimate*, the utility's Billing default, and applies it to all; per-row override; E5 inline fix; E7 Paid after cut-off (DEF-BIL-8418 fixed) |
| U6 every message clear | ✅ PASS (walked cases) | Scope refusals, gap, overlap, and the Meter Reads stop (*what*, *who fixes it*, a support reference); a person has not yet read all the copy |
| U7 nobody forgotten | ✅ PASS | Held, waived and nobody-to-bill listed; catch-up starts; Scope's *Nobody to bill* panel now lists the unit with *Add account ↗* (DEF-BIL-8221) |
| A1 totals match every step | ✅ PASS | Scope 11 = Ready 3 + Decision 8; Sign off Billed 6 + held 4 + waived 1; 6 drafted, 6 issued |
| A2 nobody billed twice | ✅ PASS | The account a sent one-time bill covers gets no second base or usage |
| A3 no account vanishes | ✅ PASS | 6 sent + 5 in Not in this run, each in exactly one place |
| A4 bill = draft to the cent | ✅ PASS | 6 bills equal their drafts; $335.58 |
| A5 rulings hold in month two | ✅ PASS | October: overlap base prorated **$3.61** (AC-2026-00001), estimate true-up **7 kgal** (00003), **one** base after a hold (00009), the plan's **$45.00** instalment printed on the bill and charged nowhere (00008, "Instalment 1: 45.00 USD due 2026-10-15") |
| A6 every decision traceable | ✅ PASS | The Check report tab shows each answer with who and when |
| F1 server stops mid-Check | ✅ PASS (harness) | Real Celery worker on PostgreSQL, 315 accounts: killed with **100 of 315** checked; the screen's own poll handed the job back to the worker **24.3 s** later; it carried on to 175 from its last saved account and none was saved twice. Resume never runs the Check in the web request (DEF-BIL-8511) |
| F2 Meter Reads down | ✅ PASS | J72 E6 and J73 F2 at 1440 and 1280: the test-only switch takes Meter Reads down; the stop says what, who fixes it and the reference; *Try again* carries the same run on (DEF-BIL-8510, DEF-BIL-8580) |
| F3 some bills fail at Send | ✅ PASS | J72 E9 at 1440 and 1280 and J73 F3: *7 bills sent · 1 bill not sent*; See breaks shows AC-2026-00008 with *a service has no revenue account*; *Retry failed* sends only that bill and the sent count does not move (DEF-BIL-8421, DEF-BIL-8581) |
| F4 two clerks on one run | ✅ PASS | J73 F4 at 1440 and 1280: Marcus sees *Also on this run: Dana Whitfield* and Dana sees Marcus; two Sends at the same moment issue each bill once, proved on PostgreSQL (DEF-BIL-8512) |
| F5 something unexpected | ✅ PASS by test | Support reference, run kept, only that account blocked |
| S1 Check time | ✅ PASS | 2.418.6, real Celery, RLS-enforced role: **10,015 accounts 70 s; 40,015 accounts 5.6 min** (4 worker slots, cap 2; load 1.8 before, 3.1–3.5 during); 13.1 min on 2 slots, cap 1, at load 1.7 (2.423.0). Every account saved once. J73 § S1–S4, `19-check-cost-measured.md` §10 |
| S2 screens at 40,000 | ✅ PASS (2.437.2, 19-check-cost-measured §15): both screens inside 2 s on a cold open, three workers | **Cold open of the sent 40,008-bill run, `2.437.2` against `2.436.3` on the same server, alternated (Chromium, gunicorn 3 × 60 s, every open started at load < 3):** Not in this run's first row **1.08–1.40 s** (old 2.55–4.46 s); the Sent card's total **1.02–1.59 s** (old 3.60–5.94 s), in seven clean opens each at 1440 and 1280. $7,371,531.12, due 10/22/2026, *Meter reads: Locked* in every open. The server half of `DEF-BIL-8809`, now closed: the run read no longer carries *Meter reads* (1.34 s → 0.06 s; that fact is its own read, asked by the Sent card); the page asks the summary's headline alone (`/totals`, 0.11 s, where `/summary` took 1.09 s); Not in this run reads only the accounts the run did not bill (0.95 s → 0.16 s). Every answer unchanged. A tag's account list was not re-timed (its read is untouched; 0.03 s at 40,008). Was (2.436.1): **Cold open of the sent 40,008-bill run, `2.436.1` against `2.433.2` on the same server, alternated (Chromium, gunicorn 3 × 60 s, each open started at load < 3, ended 3.0–4.2):** Not in this run's first row **2.8 / 5.1 s at 1440, 2.8 / 4.3 s at 1280** (was 5.9 / 6.3 and 5.2 / 5.7); the Sent card's total **4.0 / 7.6 s and 3.9 / 4.9 s** (was 6.9 / 8.0 and 6.1 / 7.0). Every read the Send screen draws now starts 0.84 s after navigation, where it started at 3.37 s, and a sent run no longer asks three reads it never draws, so eleven reads became eight (`DEF-BIL-8809`, page half). Still over 2 s: the first API call is at 0.84 s, the run read is 1.45 s alone, and `/summary` took 3.1 s beside the other reads. `DEF-BIL-8809` stays open for the server half. A tag's account list was not re-timed: a sent run's Check is locked and its read is unchanged (0.03 s on the server at 40,008). Was (2.433.2): **Cold open of the sent 40,008-bill run in Chromium (gunicorn 3 × 60 s, each open started at load < 3):** Not in this run's first row **4.6 s and 7.9 s at 1440, 4.3 s and 5.1 s at 1280**; the Sent card's total 5.5–8.7 s. **No web worker is lost any more** — `/settings/services` **52–63 s → 0.6 s** (`DEF-TEN-8731`), `/cycles` **7.6–8.2 s → 1.2 s** (`DEF-MET-8732`), and the run's own read **6.9–7.6 s → 1.2–1.5 s** (`DEF-BIL-8758`, found by this walk: 18.3 s in the browser under load), every response byte-identical. Still over S2's 2 s because the page asks its eight screen reads only after the run read answers, on three workers (`DEF-BIL-8809`, open). Sign off after Send now shows the bills' stamped figures — **$7,371,758.07** due, Σ of the 40,008 stamps to the cent — where it showed `—` (`DEF-BIL-8727`). Was (2.428.0): **Every screen's own read now meets the bar on the server, at load under 2:** at 40,008 bills Sign off **0.50 s** (a summary saved at Calculate and rebuilt whenever a row it reads is written; 8 s when it must be rebuilt in the request), Sign off's `/summary` **1.0 s**, a tag's account list **0.03 s** (10,008 open run, the staleness sweep included: **0.06 s**; the sweep's own read 0.13 s at 40,015), Ready **0.26 s**, Not in this run **0.91 s**; every figure identical to the old read (40,191 compared). In the browser at 10,008 a tag's list opens in **0.16–0.26 s** from the click; Sign off and Not in this run take **3.3–7.2 s from a cold page open** although their reads take 0.2–1.2 s, because the page's side reads `/settings/services` (13.6 s; **killed at 60 s at 40,000**) and `/cycles` (2.8 s) hold two of the three web workers (`DEF-TEN-8731`, `DEF-MET-8732`). Was:  (asked for 100,000 a page, every list serves at most 1,000). But **Sign off never shows its figures**: its summary read takes 250–396 s at 40,008 drafts and a production web worker is killed at 60 s (500 in the browser; `DEF-BIL-8696`, `8697`). A tag's account list **3.3 s** in the browser, 3.1 s of it a whole-run staleness sweep (`DEF-BIL-8694`). Not in this run **2.5 s** from a cold page load, its read 0.6–1.2 s |
| S3 Send at 40,000 | ✅ PASS | `2.426.0`, RLS-enforced role, real Celery on 4 slots: **about 11–12 bills a second — a 40,008-bill Send is about an hour** (was 1.9 a second, about 5.8 hours), in 81 batches of at most 500, so no task nears its time limit (`DEF-BIL-8708`, `8726`). **Every killed worker was handed back by the Send screen itself**, 16–19 s after a fresh worker was up, reading the bills already sent and never 0; pressing Send again on a dead Send also hands it back (`DEF-BIL-8710`). 40,008 of 40,008 issued, no number twice, one audit and one balanced journal each ($7,371,531.12 both sides), a second Send wrote nothing; the run audit passes 40,014 of 40,015 accounts (`DEF-BIL-8722` is the audit's). Found on the way: a kill left 985 sent bills listed *not sent* (`DEF-BIL-8746`, fixed) and a code-ahead-of-database fault broke 22,640 bills one by one instead of stopping (`DEF-BIL-8747`, open; *Retry failed* recovered them). `19-check-cost-measured.md` §11 |
| S4 other utilities unaffected | ✅ PASS | While Brazos Bend's 40,015-account Check ran, a second utility's 199-account Check started within 1 s of its press and finished in 4 s — on 4 slots (cap 2, A kept its 2 batches) and on 2 slots (cap 1, A kept its 1) |

**Count: 22 pass · 0 fail · 0 not run (22)** — S2 passes at `2.437.2` (`DEF-BIL-8809` closed; was 21 · 1 · 0 — the count line was not moved in that commit, corrected by the close-out lane 2026-10-01). S3 re-timed after the Send was batched (`2.426.0`, was 20 · 2 · 0); S1–S4 measured 2026-10-01 at 40,000 (was 18 · 0 · 4). U2 passes on E11 wave 3.

**The database audit (`10-scripts/verify_bulk_run.py`) on the accuracy walk, September then
October, at 1440 and 1280:** every check passes on every account but one row, both widths — each
account ends in exactly one place (11 of 11), the screen equals the database, no job is left
failed, month two bills no day or base twice. Accounts with an open question (*Standing charges
only*, *Gap or overlap*, an unanswered *No reading*) now wait in *Not in this run* instead of being
billed (`DEF-BIL-8650`, `8653`). *Apply to this bill* on a payment still processing is refused
(`DEF-BIL-8651`).

**The one red row, left red on purpose:** AC-2026-00007's $120.00 (now cleared) settles the
$34.00 September bill in full, so the October bill prints *payments received $0.00* and
*total due $37.25* although $37.25 of the credit was drawn against it at issue. What the bill
should print was the balance-forward question (`OQ-217`, CLOSED 2026-10-01: the whole account — $34.00 − $120.00 + $37.25 = a $48.75 credit, BR-BIL-1065); filed as `DEF-BIL-8670`. On J72's
plain walk the audit also counts the Check job that the deliberate *Meter Reads down* walk (F2)
stopped; *Try again* runs a new Check, which succeeds.

Seen on the way and not product faults: at load 8–10 one accuracy run read *Not in this run* and
October's tag list before they had loaded, and one J72 E7 at 1280 drew a blank page; the spec
reads now wait, and both passed when walked again.

### U2 · E11 WAVE 3 — THE LAST EIGHT STATES, EACH A FIELD THE SERVER NOW SENDS (2026-10-01, build 2.422.3)

**How.** The same capture spec on a fresh J72 seed with `--e11-states` (`sbh_e11w3`, snapshot
`sbh_e11w3_snap`, reset before each width), PostgreSQL 16 at 127.0.0.1:55433, built SPA (`vite build
--mode compose`) behind `server.mjs`, `runserver` with JOBS_EAGER on. `E11_PYTHON` set to the venv so
Module down (10) is reached through the harness. **All 36 states captured at 1440 and 1280 (72 images,
`08-qa/screens/bulk-bill-run-e11-wave3-2026-10-01/`); none unreachable.** The other 28 states were
re-captured with them and still match.

**Result: 36 of 36 match.** The eight below were each put beside their D1 image at both widths.

| # | State | 1440 | 1280 | What changed (defect, 2.422.3) |
|---|---|---|---|---|
| 04 | Scope · warnings | MATCH | MATCH | *45 days. Cycle is monthly. Ends after today.* in the warnings and under Period end (8691: the server sends metering's frequency word; the screen has one sentence per frequency in all eleven catalogues; the field note now carries every warning on the field) |
| 11 | Check · No reading | MATCH | MATCH | Service reads *Water · W-72103* (8701: the meter's number, read through billing's metering seam, two reads per page) |
| 12 | Check · rows selected | MATCH | MATCH | 8701 |
| 13 | Check · fixed on the row | MATCH | MATCH | 8701 — on this seed the tag is *No plan*, a finding about the unit and not a service, so its Service cell is `—` and has no meter to name; a row with a service names its meter |
| 14 | Check · fixed on another screen | MATCH | MATCH | *Water · W-72115* (8701) |
| 25 | Sign off · all open | MATCH | MATCH | the tile is the payments with *N payments* beneath (8682) |
| 28 | Sign off · Payments and balances | MATCH | MATCH | *Payments applied* and *Credits applied* on two lines, each with its count, adding back to the old single figure (8682) |
| 35 | Send · sent, Not in this run | MATCH | MATCH | *Meter reads · Locked* under Delivery (8685: Meter Reads' own count of the sent bills' reads held BILLED) |

**What 8682 is built on.** Sign off now reads ruling 6's window (OQ-217, *the whole account since the
last bill*), the same reads issue stamps on the bill, asked once for the whole run (NFR-3). Payments and
credits are told apart by payments' own `type` column: `payment` rows less refunds are *Payments
applied*, `credit` and `adjustment` rows are *Credits applied*. Worked in
`tests/test_def_bil_e11_wave3_served_fields.py`: a $34.00 bill, $120.00 paid, a $10.00 credit and $5.00
refunded → Sign off showed *paid $0.00 · due $37.25*; it now shows *payments $115.00 · credits $10.00 ·
due −$53.75*, the bill's own stamp. On the J72 seed the four billed accounts received nothing since their
last bill, so both lines read *$0.00* with *0* beside them — true figures, not placeholders.

**Kept on purpose:** the drawn label *Payments applied since last bill* is written *Payments applied*
(B14 rule 33 — a label is at most three words); the count sits beside it as drawn.

**Found and filed, not fixed:** `DEF-BIL-8720` — Sign off's *Amount due* still includes a payment plan's
part not yet due, which the bill leaves off since ruling 1. Not visible on this seed (no plan).

**Tests (each red first on 2.422.0):** `E11DrawingDiffWave3.dom.test.tsx` 5 ·
`tests/test_def_bil_e11_wave3_served_fields.py` 8.

### U2 · E11 WAVE 2 — THE DIFFERENCES FIXED, EVERY STATE RE-CAPTURED (2026-10-01, builds 2.417.2 – 2.418.9)

**Ruling for the wave** (coordinator, under B14 rule 41): for the bulk run the blueprint owns
layout, copy, flows and states and our UI standard owns how it is built, so every difference is a
defect to fix rather than a question for the PO. Money is shown exactly as the engine computes it;
only how it is shown moves. The money behaviour of *Next bill* stays with `DEF-BIL-8412`.

**How.** The same capture spec, now on the J72 seed with `--e11-states` (`DEF-BIL-8689`: unit 113
has water and no meter, unit 114 a gallons meter on a kgal plan, unit 115 a reading and a meter with
no unit), and with the August run recorded as sent (`DEF-BIL-8690`). PostgreSQL 16, reset before
each width. **All 36 states captured at 1440 and at 1280 (72 images); none unreachable.**

**Result: 28 of 36 match; 8 differ, each on a difference that is filed and needs a figure or a
field the server does not serve yet.** No state differs at one width and not the other.

| # | State | 1440 | 1280 | What is still different (defect) |
|---|---|---|---|---|
| 01 | Scope · continuous | MATCH | MATCH | — |
| 02 | Scope · gap | MATCH | MATCH | — |
| 03 | Scope · overlap, Previous runs open | MATCH | MATCH | — (RUN-0001 now reads sent, 8690) |
| 04 | Scope · warnings | differs | differs | `Cycle expects 30.` where the drawing says `Cycle is monthly.` — the server sends a day count, not the frequency (8691, partly fixed) |
| 05 | Scope · problems | MATCH | MATCH | — |
| 06 | Scope · panels collapsed | MATCH | MATCH | — |
| 07 | Scope · Nobody to bill panel | MATCH | MATCH | — (`Action` column and one-line place, 8699) |
| 08 | Scope · Missing meter panel | MATCH | MATCH | — (reached through 8689; 8699) |
| 09 | Check · checking | MATCH | MATCH | — |
| 10 | Check · module down | MATCH | MATCH | — |
| 11 | Check · No reading | differs | differs | Service shows `Water`, drawn `Water · W-10442` — no meter number served on a Check row (8701) |
| 12 | Check · rows selected | differs | differs | 8701 |
| 13 | Check · fixed on the row | differs | differs | 8701 |
| 14 | Check · fixed on another screen | differs | differs | 8701 (reached through 8689: *Reading has no unit*, fixed in Meter Reads) |
| 15 | Check · warning tag | MATCH | MATCH | — |
| 16 | Check · Paid after cut-off | MATCH | MATCH | — (what *Next bill* does to the money is 8412, by ruling) |
| 17 | Check · Blocked tile | MATCH | MATCH | — |
| 18 | Check · search "meter" | MATCH | MATCH | — |
| 19 | Check · passed checks | MATCH | MATCH | — |
| 20 | Check · Ready to bill | MATCH | MATCH | — |
| 21 | Check · one left out | MATCH | MATCH | — |
| 22 | Check · Fix account panel | MATCH | MATCH | — (the unit no longer shown twice, 8700) |
| 23 | Check · fixed, re-checked | MATCH | MATCH | — |
| 24 | Calculating | MATCH | MATCH | — |
| 25 | Sign off · all open | differs | differs | one *Payments applied* figure where the drawing splits payments from credits — the server serves one merged figure (8682, partly fixed) |
| 26 | Sign off · Who is billed | MATCH | MATCH | — |
| 27 | Sign off · Usage and charges | MATCH | MATCH | — |
| 28 | Sign off · Payments and balances | differs | differs | 8682 (the same split) |
| 29 | Sign off · Nobody to bill filter | MATCH | MATCH | — |
| 30 | Sign off · Failed to draft panel | MATCH | MATCH | — (reached through 8689; *Retry* is greyed for *Pricing refused* on purpose — the fix is in Plans & Rates) |
| 31 | Sign off · confirmations ticked | MATCH | MATCH | — |
| 32 | Send · not ticked | MATCH | MATCH | — |
| 33 | Send · ticked | MATCH | MATCH | — |
| 34 | Send · sending | MATCH | MATCH | — |
| 35 | Send · sent, Not in this run | differs | differs | no *Meter reads: Locked* line — needs a metering read (8685, partly fixed) |
| 36 | Send · catch-up started | MATCH | MATCH | — |

**Fixed in this wave, each with a DOM or backend test written red first**
(`E11DrawingDiffWave2.dom.test.tsx`, `tests/test_def_bil_8680_8681_8685_run_facts.py`,
`tests/test_def_bil_8700_display_for.py`): 8678 (2.417.2) · 8684 (2.418.1) · 8680, 8681, 8683 and
half of 8685 (2.418.3) · 8675, 8676, 8677 (2.418.5) · 8679, 8688 (2.418.6) · 8686, 8687, most of
8682 and 8691 (2.418.7) · 8689, 8690, 8699, 8700 (2.418.9). **8679 and 8688 touch the shared wizard
frame:** the new props (`actionsHidden`, `backAtStart`, `actionNote`, `doneMark`) are opt-in and
only the bulk run passes them, so the other 28 wizards render as before.

**Kept on purpose:** *Apply to all* stays in the decision bar (row 45, `DEF-BIL-8418`); the
footnote reads `1 blocked stays out.` and not the drawn `… stay out of this run.` (B14 rule 33, a
fact is at most six words).

**U2's verdict — PASS.** The step name is on the rail at every state, done steps are ticked, every
primary names its act, and no footer offers a step that cannot go on: the progress panels and the
Meter Reads stop show no *Price* button (`DEF-BIL-8678`).

### U2 — every drawn state put beside its D1 image (E11, 2026-10-01, build 2.417.1) — superseded by wave 2 above

**How.** `07-frontend/e2e/J72-bulk-bill-run-e11-capture.spec.ts` walks one September run on the
plain J72 seed (PostgreSQL 16, reset before each width) in the clerk's order and saves each state
under its D1 name in `08-qa/screens/bulk-bill-run-e11-2026-10-01/` (`<state>-1440.png`,
`<state>-1280.png`). A state it cannot reach is written to `reached-<width>.json`, never dropped.
Checking, Calculating and Sending are held at a fixed *n of N* after the real request has
finished (with the jobs inline they are never on screen long enough to see). Module down takes
Meter Reads down for real with `10-scripts/j73_bulk_run_harness.py`. Each capture was put beside
its D1 image and compared for **shape, content, order, wording and state** — never for pixel
figures (B14 rules 37 and 44: every drawn number is an illustration, and spacing, sizes and
colours are our kit's). The 1280 captures arrange every state the same way as the 1440 ones; no
difference was found at one width and not the other.

**Result: 33 of 36 states captured at each width (66 images); 3 not reachable on this seed;
4 match; 29 differ. 20 differences filed (`DEF-BIL-8672`–`8691`); 3 fixed in 2.417.1.**

| # | State | 1440 | 1280 | Differences (defect) |
|---|---|---|---|---|
| 01 | Scope · continuous | differs | differs | `1 units` (8672, fixed) · Back/footnote placement (8679) · no *Last run total*, `Day 1` for `1st` (8691) |
| 02 | Scope · gap | differs | differs | lines out of field order (8673, fixed) · gap line drops *by any run* (8691) |
| 03 | Scope · overlap, Previous runs open | differs | differs | footnote under the button (8679) · aside Period `—` while refused (8691) · RUN-0001 listed *Draft* (8690, seed) |
| 04 | Scope · warnings | differs | differs | field order (8673, fixed) · two *Period end* lines for the drawn one *Period* line (8691) |
| 05 | Scope · problems | differs | differs | *No runs yet* and Last run `—` while the period is invalid (8681) · footnote under the button (8679) |
| 06 | Scope · panels collapsed | MATCH | MATCH | — (after 8672) |
| 07 | Scope · Nobody to bill panel | MATCH | MATCH | — (column `Fix` for `Action`, a link for a button: kit, rule 44) |
| 08 | Scope · Missing meter panel | not reachable | not reachable | every seeded service has a meter (8689) |
| 09 | Check · checking | differs | differs | footer shows `Price 0 accounts` under the progress (8678) · done step shows its number, not a tick (8688) |
| 10 | Check · module down | differs | differs | an **enabled** `Price 4 accounts` under *No account was checked* (8678) |
| 11 | Check · No reading | differs | differs | tag names are sentences (8675) · no meaning line, long answers, no *Pre-selected* note, extra *Apply to all* / *Re-check* (8676) |
| 12 | Check · rows selected | differs | differs | 8675 · 8676 |
| 13 | Check · fixed on the row | differs | differs | the fixed row disappears; no green *Fixed · re-checked* (8677) · 8676 |
| 14 | Check · fixed on another screen | not reachable | not reachable | the served Check blocks nothing on this seed (8689) |
| 15 | Check · warning tag | differs | differs | head line without the meaning sentence (8676); otherwise as drawn |
| 16 | Check · Paid after cut-off | differs | differs | `Put it on this bill` beside `Apply to this bill` (8674, **fixed: `Next bill`**) · 8676 |
| 17 | Check · Blocked tile | MATCH | MATCH | the empty case (Blocked 0); the drawn blocked list needs 8689 |
| 18 | Check · search "meter" | differs | differs | no tag name contains *meter*, so the search finds none of the drawn Meter tags (8675) |
| 19 | Check · passed checks | differs | differs | passed tags named as sentences (8675) |
| 20 | Check · Ready to bill | differs | differs | no count line, no segment counts, an extra Status column (8687) |
| 21 | Check · one left out | differs | differs | 8687 |
| 22 | Check · Fix account panel | differs | differs | no address line, no meaning per card (8686) · 8675 |
| 23 | Check · fixed, re-checked | differs | differs | 8677 |
| 24 | Calculating | differs | differs | footer `Working…` under the progress (8678) |
| 25 | Sign off · all open | differs | differs | Run name `—` in the aside (8680) · `Payments applied 0`, balances table (8682) · raw `institutional` (8683) · no warnings note (8684) |
| 26 | Sign off · Who is billed | differs | differs | 8680 |
| 27 | Sign off · Usage and charges | differs | differs | 8680 |
| 28 | Sign off · Payments and balances | differs | differs | 8682 · 8680 |
| 29 | Sign off · Nobody to bill filter | MATCH | MATCH | — (aside name, 8680, aside) |
| 30 | Sign off · Failed to draft panel | not reachable | not reachable | every J72 account drafts (8689) |
| 31 | Sign off · confirmations ticked | differs | differs | no warnings note (8684) · 8680 · Back placement (8679) |
| 32 | Send · not ticked | differs | differs | *Signed off* without who and when (8685) · `Warnings 0` (8684) · 8680 · 8679 |
| 33 | Send · ticked | differs | differs | as 32 |
| 34 | Send · sending | differs | differs | footer `Working…` under the progress (8678) · 8680 |
| 35 | Send · sent, Not in this run | differs | differs | no *Meter reads: Locked* (8685) · no ticks on the rail (8688) · 8680 |
| 36 | Send · catch-up started | differs | differs | 8680 · 8688 (the catch-up note itself is as drawn) |

**Fixed here (2.417.1), each with a test written red first** —
`07-frontend/src/features/billing/bulkRun/E11DrawingDiff.dom.test.tsx`:
`DEF-BIL-8672` the singular (`1 unit has nobody to bill.`, `1 service has no meter.`, all eleven
catalogues); `DEF-BIL-8673` Scope's problem lines in the form's field order, count lines last;
`DEF-BIL-8674` Paid after cut-off's next-bill answer reads `Next bill` (the shared catalogue
words stay right for a true-up). ⚠ `8674` fixes the **words** only: what that answer does to the
bill is `DEF-BIL-8412` (`OQ-217` CLOSED 2026-10-01: a payment deferred with *Apply next bill* is counted on the next bill).

**Left open, and why:** `8675` (tag names) moves keys the older exceptions screen shares; `8676`,
`8677`, `8678`, `8682`, `8684` change what a step does or shows about money; `8679`, `8688` are the
shared wizard frame; `8680`, `8681`, `8683`, `8685`, `8686`, `8687`, `8691` are small but each
needs its own served field or decision; `8689` and `8690` are the seed.

**U2's verdict — FAIL (one clause).** The step name is on the rail at every state and every primary
names its act (*Start checking*, *Price 4 accounts*, *Sign off*, *Send 4 bills*, *Start catch-up
run*). What fails is the footer while the step cannot go on: *Price 0 accounts* while checking, and
an enabled *Price 4 accounts* under *Meter Reads is not answering. No account was checked.*
(`DEF-BIL-8678`).

---

### Superseded — the 2026-09-30 21:40 status (build 2.413.0)


| Check | Result | What decided it |
|---|---|---|
| U1 run a clean cycle | ✅ PASS | Scope → Check → Sign off → Send, 11 accounts |
| U2 always know where you are | ⚪ NOT RUN | Needs a person against the drawings; screens captured |
| U3 leave and come back | ✅ PASS (re-open) | Re-opening lands on the same step; closing mid-Check is F1 |
| U4 progress as n of N | ✅ PASS by test | Check, Calculate ("754 of 1,371") and Send ("612 of 1,371") |
| U5 clear problems easily | ❌ FAIL (one part) | Tag → accounts, answer for all, per-row, fix on the row all pass; *Answer for all* not pre-selected from Billing defaults (DEF-BIL-8418) |
| U6 every message clear | ✅ PASS (walked cases) | Scope refusals, gap, overlap; the rest of the copy not yet read by a person |
| U7 nobody forgotten | ✅ PASS | Held, waived and nobody-to-bill listed; catch-up starts |
| A1 totals match every step | ✅ PASS | Scope 11 = Ready 3 + Decision 8; Sign off Billed 6 + held 4 + waived 1; 6 drafted, 6 issued |
| A2 nobody billed twice | ✅ PASS | Already-billed account gets no second base |
| A3 no account vanishes | ✅ PASS | 6 sent + 5 in Not in this run, each in exactly one place |
| A4 bill = draft to the cent | ✅ PASS | 6 bills equal their drafts; $335.58 |
| A5 rulings hold in month two | ❌ FAIL (part) | One base after a hold ✅, overlap prorated $3.61 ✅, Skip extends plan ✅; *Add to bill* instalment (DEF-BIL-8243) and the estimate true-up seed (DEF-BIL-8420) fail |
| A6 every decision traceable | ✅ PASS | Check report tab shows each answer with who and when |
| F1 server stops mid-Check | ⚪ NOT RUN | J73 harness ready; DEF-BIL-8511 (Resume runs in the web request) |
| F2 Meter Reads down | ⚪ NOT RUN (server half ✅) | Server answers what/who/reference, run kept; banner not walked (DEF-BIL-8510) |
| F3 some bills fail at Send | ❌ FAIL | The send-failure seed breaks nothing (DEF-BIL-8421) |
| F4 two clerks on one run | ⚪ NOT RUN | DEF-BIL-8512 |
| F5 something unexpected | ✅ PASS by test | Support reference, run kept, only that account blocked |
| S1 Check time | ⚪ NOT RUN | Measured: ~690 ms/account today → 40,000 ≈ 7.7 h on one worker; needs B27 (target 150–250 ms) and B28 |
| S2 screens at 40,000 | ⚪ NOT RUN | J73 |
| S3 Send at 40,000 | ⚪ NOT RUN | B28, DEF-BIL-8511 |
| S4 other utilities unaffected | ⚪ NOT RUN | B28 (cap: half the billing workers, min 1) |

**Count: 11 pass · 3 fail · 8 not run (22).**
