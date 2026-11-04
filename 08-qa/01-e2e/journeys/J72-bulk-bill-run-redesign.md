# J72 — The bulk bill run, redesigned (Scope · Check · Calculate · Sign off · Send · catch-up · E1–E11)

---
id: J72
tier: 2
rules: [BR-BIL-004, BR-BIL-005, BR-BIL-015, BR-BIL-024, BR-BIL-034, BR-BIL-055, BR-BIL-056, BR-BIL-058, BR-BIL-1025, BR-BIL-1039, BR-BIL-1040, BR-BIL-1041, BR-BIL-1043, BR-BIL-1050, BR-BIL-1051, BR-BIL-1052, BR-BIL-1053, BR-BIL-1054, BR-BIL-1055, BR-RAT-007]
stories: [US-BIL-036, US-BIL-037, US-BIL-038, US-BIL-039, US-BIL-040, US-BIL-041, US-BIL-005, US-BIL-006]
# ⚠ NOT ACTIVATED — no `J72.spec.ts`. Written 2026-09-30 as the HANDOFF CONTRACT BEFORE THE CODE
# (build plan `04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md` R3, journeys E1–E11).
# Nothing below is built; the defects DEF-BIL-8200…8215 name what the live product does today.
# WALKED 2026-09-30 in a browser at 1440 and 1280 on PostgreSQL 16 — `07-frontend/e2e/J72-bulk-bill-run.spec.ts`,
# seed `manage.py seed_j72_bulk_run`; results in § WALKED 2026-09-30 at the foot of this file.
# ACCURACY checks A1–A6: `07-frontend/e2e/J72-bulk-bill-run-accuracy.spec.ts` on
# `seed_j72_bulk_run --month-two`; results in § WALKED 2026-09-30 (evening) — ACCURACY.
# THE 22 CLERK CHECKS after the bulk-run-rest fixes (2.413.0): § WALKED 2026-09-30 (night).
# E16 RUN AUDIT IN THE DATABASE (`10-scripts/verify_bulk_run.py`) and E17 SINGLE-ACCOUNT TRACE
# (`07-frontend/e2e/J72-bulk-bill-run-single-account-trace.spec.ts`), 2.416.0: § E16/E17 at the foot.
# E11 DRAWING DIFF (`07-frontend/e2e/J72-bulk-bill-run-e11-capture.spec.ts`), 2.417.1: § E11 at the foot.
# E11 WAVE 2, 2.418.9: all 36 states at both widths, 28 match, 8 differ on filed server fields; U2 PASS.
---

**Intent.** One bill-run screen, four steps, and a run that never loses an account. The PO approved
the redesign on 2026-09-30 — *"im good with thsi … please start and ensure between step 1 and 2 for
given account you runs allc heck sand dont stop at first problem"*. The journey proves it as numbers
on a screen: Scope shows **every** run-level problem at once; Check finds **all three** problems on
Grace Okafor's account in one pass and blocks Tom Becker's unitless reading **without stopping the
other nine**; a price change the day after the period ends does **not** reach the bill (**$40.50**,
not **$43.00**); Sign off's lines add back to Scope's **10 accounts** and **12 units**; and every
account not billed is on the run, in Pending billing after Send, and billable from a catch-up run.

**Sources.** Change list `04-docs/05-modules/07-billing/14-bulk-bill-run-changes.md` · build plan
`15-bulk-bill-run-build-plan.md` (E1–E11) · decision log 2026-09-30 · rules `BR-BIL-1050` (the Scope lane's) and `BR-BIL-1051`–`1055` and
the rows amended the same day · the stories above (EP-BIL-01, whose §AMENDED 2026-09-30 carries the
`BBR` fixture and open items OI-B1…OI-B3) · drawing images `05-prototype/bulk-bill-run-2026-09-30/`
(the E11 baseline). A figure drawn in the mock-up is an illustration (B14 rule 37).

## ⚠ HOW THIS WALK IS ORGANISED — BY THE CLERK'S 22 ACCEPTANCE CHECKS (PO ruling 2026-09-30)

PO verbatim: *"your end ot end walk should be around these cases"* — the 22 checks of
`04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md`. So from 2026-09-30:

- **Every spec test is named for the check it proves** — `U1 …`, `A2 …`, `F3 …`, `S1 …` — and may also carry
  the old E-number it grew from (E1 → U1, E8 → A1, E9 → A4/F3, E10 → U7 …).
- **The results table reports the 22 checks**, one row each, PASS / FAIL / NOT RUN with what decided it,
  at 1440 and 1280. A check with no walk case is reported NOT RUN, never left out — the count is always 22.
- **The seed carries what each check needs**: a failing bill at Send (F3), a second clerk (F4), a way to take
  Meter Reads down and bring it back (F2), a worker stopped mid-Check (F1), and a scale variant of 10,000 and
  40,000 accounts (S1–S4, `manage.py seed_j72_bulk_run --accounts N`).
- **Usability checks (U2, U6) are judged by a person** against the drawings; the walk captures the screens
  they judge and records who judged them and when.
- **The walk is not finished until all 22 have a row, and the release is not done until all 22 PASS.**

The E1–E11 cases below are kept as written; each now maps onto one or more of the 22.

## Preconditions — the seed (`BBR`; every E-case starts from it unless it says otherwise)

Tenant **Brazos Bend Utilities** (`brazos-bend`); isolation tenant **Lone Star Ridge WSC**. Actors
**Priya Menon** (Billing Clerk), **Alex Reed** (System Admin), **Jo Park** (view-only). Clock
**Thu 1 Oct 2026, 09:00**.

| Item | Seeded as |
|---|---|
| Cycle | **Cycle 3 · Riverside** — monthly, bill day **1st**, **21 days to pay**, usual template **Standard bill · v4** (published); **Winter insert · draft** unpublished |
| Previous runs | **BR-0231** Aug 1 – Aug 31, 2026, *Sent* (J. Ortiz, 10 bills) · **BR-0229** Sep 1 – Sep 30, 2026, **Cancelled** |
| Units / accounts | **12 units · 10 accounts** (9 regular, 1 master `AC-2026-00110` Elm St Apartments covering 1418 Elm St Units A and B) · 1416 Elm St · Unit B **vacant, nobody to bill** (moved out Aug 12) |
| Clean | `AC-2026-00101` Maria Alvarez (water W-2001 Aug 31 **482.0** → Sep 30 **492.0** kgal) · `00102` Omar Haddad · `00109` Sara Cohen · `00110` master |
| Decisions | `00103` Priya Natarajan — **no reading** on W-2003 · `00107` Hannah Lee — **$120.00 paid Oct 1 after the cut-off** |
| Blocks | `00104` Luis Alvarez — **no plan** · `00105` Grace Okafor — **no plan + disputed reading on W-2005 + bounced $85.00 (Sep 20) not reversed** · `00106` Tom Becker — electric consumption **with no unit** |
| Warnings | `00108` Diego Ramos — electric **no base charge** ($0.00) · gas on 1408 Elm St · Unit A connected **with no meter** |
| Water price | **$3.25/kgal until Sep 30**, **$3.50/kgal from Oct 1, 2026**; base **BASE-W $8.00** |

## The journey

| # | Actor · action · screen | Expected result (what this step leaves) | Downstream assertions | Rule · story |
|---|---|---|---|---|
| **E1.1** | Priya opens **Billing › Bills › Run** | The four-step screen, rail **Scope · Check · Sign off · Send**, at Scope | No route renders `BillRunWizard`; the door is asserted by ADDRESS | US-BIL-036 TC-1 · `DEF-BIL-8200` |
| **E1.2** | Types run name **September 2026 · Riverside**; Cycle 3; **Sep 1 – Sep 30**; bill date **Oct 1**; 21 days; **Standard bill · v4** | *Continuous — Follows run BR-0231 (Aug 1 – Aug 31). 30 days.* (the cancelled BR-0229 ignored); due **Oct 22, 2026**; covers **12 units · 10 accounts · 9 regular · 1 master**; *Last run 10* under Accounts to bill only; **2 warnings** (1 unit nobody to bill · 1 service no meter); no services filter, no standing answers, no tick | Start enabled; the create body has no `scope_services`; key `<cycle>|2026-09-01|2026-09-30` | US-BIL-036 TC-2, TC-3, TC-9 · BR-BIL-1050, 1051, 005 |
| **E1.3** | **Start checking** | *Checking accounts — n of 10*, then five tiles **ready 5 · need a decision 2 · blocked 3** | The pass ran in the background; leaving and returning resumes the view | US-BIL-037 TC-5 |
| **E1.4** | Tag **No reading** → *Answer for all 1* = **Estimate** (pre-selected); tag **Paid after cut-off** → **Apply to this bill**; on **Ready to bill**, **Leave out** `00109` | Both tags answered; *1 left out* | `bill_runs.case_defaults` carries both answers; `00109` is in Not in this run as *left out by clerk* | US-BIL-037 TC-8, TC-10, TC-14 · BR-BIL-1040, 1053, 1054 |
| **E1.5** | **Price 6 accounts** (`00104`–`00106` blocked, `00109` left out) | *Calculating bills — n of 6*, then Sign off on 6 drafts | `00101`'s water: **$32.50 + $8.00 = $40.50** (the Sep-30 version), not $43.00 | US-BIL-038 TC-1, TC-2 · BR-BIL-1055 |
| **E1.6** | Sign off: ticks all five confirmations → **Sign off** | One `bill_run_releases` row, each confirmation recorded | — | US-BIL-039 TC-8 |
| **E1.7** | Send: ticks *I checked the totals*; **Send 6 bills** twice quickly | **6 bills sent** | 6 invoices, 6 numbers, 6 balanced entries, 6 delivery rows, one audit per send | US-BIL-040 TC-1, TC-2 |
| **E2** | **Scope problems** (fresh): run name empty · period end **Aug 20** · bill date empty on a cycle with no bill day · days to pay **-3** · **Winter insert · draft**; then bill date **Sep 25** on Sep 1 – Sep 30 | **Fix 5 things to start.** — all five at once, each field red with its own message; then the bill date alone refused (before the period ends) | One response, `field_errors` × 5; no `bill_runs` row either time | US-BIL-036 TC-6, TC-7 · BR-BIL-1050 · `DEF-BIL-8212`, `8213` |
| **E3** | **Gap and overlap**: period **Oct 10 – Nov 9** → then (after E1.2 made BR-0232) **Sep 15 – Oct 14** | Gap: amber *Oct 1 – Oct 9 not billed by any run.*, **no tick**, Start enabled. Overlap: red *Sep 15 – Sep 30 already billed.* **Open BR-0232**, Start disabled | — | US-BIL-036 TC-4, TC-5 · BR-BIL-1051 · `DEF-BIL-8204` |
| **E4** | **Decide a tag three ways** on a tag with 2+ rows: answer for all; override one row to **Hold**; select two and **Apply to 2 selected** | The table shows each row's decision | One `bill_run_decisions` row per override; the tag's answer for the rest | US-BIL-037 TC-8, TC-9 |
| **E5** | **Fix inline and re-check** (fresh seed, after E1.4): tag **No plan**, row `00104`, choose **Residential Standard** → Save | Row **Fixed · re-checked**; ready 6, blocked 2; **Price 7 accounts** | The plan written by Accounts' own service — no billing write; `00105` stays blocked by its other problems | US-BIL-037 TC-6, TC-7, TC-1 |
| **E6** | **Meter Reads down** at Check | *Meter Reads isn't answering. No account was checked.* + support reference + **Try again**; the run kept | Nothing half-checked is shown as ready | US-BIL-037 TC-15 |
| **E7** | **Payments tag**: `00107`'s $120.00 → Apply to this bill; Sign off | Payments applied includes $120.00 against `00107` | Its draft's amount due is reduced by $120.00 | US-BIL-037 TC-10 · US-BIL-039 TC-5 |
| **E8** | **Sign off reconciles** (the E5 branch: `00104` fixed, 7 priced) | Accounts **10 = 7 billed (6 regular · 1 master) + 3 not billed (2 blocked · 1 left out)**; Units **12 = 8 billed + 4 not billed (3 account not billed · 1 nobody to bill)**; every *See* opens Not in this run with its filter pressed | Usage and charges' total = sum of the 7 drafts to the cent | US-BIL-039 TC-1…TC-4 · BR-BIL-1054 |
| **E9** | **Send with 2 breaks**: `00102` GL account missing for trash, `00108` template cannot render | **5 bills sent**, *2 bills not sent* named, *See breaks* | The 5 issued; the 2 are breaks, not issued | US-BIL-040 TC-3 · BR-BIL-055 |
| **E10** | **Catch-up**: fix `00105` (plan, dispute, bounced payment); on Sent's Not in this run select `00105`, `00109` → **Start catch-up run for 2**; then leave `00106` for next cycle | Child run **BR-0232-A** Sep 1 – Sep 30 goes through Check · Sign off · Send and bills 2; `00106` stays in Pending billing | `parent_run_id` = BR-0232; key = parent key + those accounts; the October run bills `00106` from Aug 31's read with no usage lost | US-BIL-041 TC-3, TC-5, TC-6 · BR-BIL-015, 1039 |
| **E11** | **Screenshot diff** — every state above at **1440** and **1280** | Each capture compared with its D1 image (`01`–`36`) against the UI skill's §4 checklist; figures NOT compared (rule 37); the drawing's capture faults (inventory §0) not copied | Differences in arrangement are defects; spacing and type follow our UI standard (rule 44) | B14 rules 37, 42, 44 |
| **LINKS** | Click every link and button on every step | Each opens a list, a tag, a panel or a named screen in a new tab | The test fails on a link that changes nothing (plan T7) | US-BIL-039 TC-9 · row 42 |
| **ISO** | Lone Star Ridge's clerk: scope preview with Brazos Bend's cycle; findings and Send with Brazos Bend's run id | `404` each | Nothing of Brazos Bend's read or written | hard rule 1 |
| **INV** | — | — | Every issued bill immutable (hard rule 4); every fixed fact written by its owning module; one issue pass per send; every money action audited | hard rules 4, 6, 7 |

## Open items this journey does not decide

EP-BIL-01 §AMENDED 2026-09-30: **OI-B1** where Check's results live (the plan's store vs
`OQ-843`'s RECOMPUTE ruling — E1.3 asserts only that leaving and returning works and E5 that a fix
is seen) · **OI-B2** payment facts with no source (E7 uses the one the fixture seeds) · **OI-B3**
proved by E10.

**This journey leaves (for downstream).** Run **BR-0232** sent for Cycle 3, Sep 1 – Sep 30, 2026,
with its breaks recorded; child run **BR-0232-A** sent for 2 accounts; `00106` in Pending billing
marked for the next cycle; no account of the cycle unaccounted for.

## WALKED 2026-09-30 — E1–E11 in a browser, 1440 and 1280, on PostgreSQL 16

**Stack.** Build 2.412.1 (branch tip `f8dabc0d7` plus this lane's commits). Database `sbh_j72` on the
local PostgreSQL 16 cluster (127.0.0.1:55433): `migrate` → `seed_demo` → `seed_j72_bulk_run`,
snapshotted and **reset to that snapshot before each width**. Django `runserver` (JOBS_EAGER on, so
Check and Calculate run inline) behind the built SPA (`vite build --mode compose`, `server.mjs`).
Run: `E2E_VIEWPORT=<w> E2E_BASE_URL=… npx playwright test e2e/J72-bulk-bill-run.spec.ts --workers=1`.
Screens: `08-qa/screens/bulk-bill-run-e2e-2026-09-30/` — 17 of the 36 D1 states at each width,
named after their drawing.

**The seed is not the table above.** `seed_j72_bulk_run` builds cycle `J72-RIVERSIDE · Riverside`
(monthly, bill day 1, 21 days to pay), 12 units at 2200 Riverside Dr, 11 regular accounts
`AC-2026-00001`…`00011`, one vacant unit, and a real August run `RUN-0001` (6 bills sent). Proved on
PostgreSQL by preparing Sep 1 – Sep 30 (bill Oct 1): no reading (`00003`) · no plan (`00004`) ·
disputed reading + no plan (`00005`) · held in August after a July bill (`00006`, prepared Aug 1 –
Sep 30, one base) · $120.00 posted Oct 1 (`00007`, paid after cut-off) · electric with no base code
(`00008`, $0.00 + warning) · gap (`00009`, last bill July) · overlap (`00010`, a sent one-time bill
already covers Sep 1 – Sep 30) · vacation hold (`00011`, standing charges only / Waive) · unit 112
nobody to bill. **Not seeded, and why** (the seed's docstring): no master account, no unitless
electric reading (metering refuses one on the way in), no cancelled BR-0229 (its idempotency key
would make E1 a duplicate), no Send-time break (E9), no unpublished template (E2's fifth refusal).

**Results.** 14 cases per width. *Expected-fail* means the case runs every step, fails where the
named work is missing, and is marked `test.fail(…)` with that reason — the day it lands the case
passes and Playwright reports *expected to fail but passed* (hard-won law 2's hold expiry). Nothing
is skipped. Both widths: **8 pass · 6 expected-fail · 0 unexpected**.

| Case | 1440 | 1280 | What the walk saw |
|---|---|---|---|
| E1 Scope, clean | **PASS** | **PASS** | *Continuous — Follows run RUN-0001 (08/01/2026 – 08/31/2026). 30 days.*; covers 12 units · 11 accounts (*Last run 6*) · 11 regular · 0 master; warning *1 unit nobody to bill* with *See units* → the panel; Start enabled; Start → Check |
| E1b Check → Calculate → Sign off | **PASS** | **PASS** | Overlap row answered *Look into it* row by row; *Price 9 accounts*; Calculating; Sign off |
| E1c Sign off → Send | **PASS** | **PASS** | Five confirmations ticked, signed off, *I checked the totals*, **6 bills sent** (`RUN-0002`) |
| E2 Scope problems | **PASS** | **PASS** | *Fix 3 things to start.* — run name, period end (*Ends before it starts.*), days to pay — each on its field; Start disabled; a bill date before the period ends refused on its own |
| E3a Gap | **PASS** | **PASS** | *Gap 09/01/2026 – 10/09/2026 not billed.*, a warning, no tick |
| E3b Overlap | **PASS** | **PASS** | Refused *09/15/2026 – 09/30/2026*, **Open RUN-0002** links `?run=`, Start disabled |
| E4 Decide three ways | expected-fail | expected-fail | Tiles right (Blocked 2 · Ready 9); *Answer for all 1* pre-selected *Estimate the reading*, changed to Hold, row override works. **Apply to 2 selected on Gap or overlap answers neither row: `DEF-BIL-8472`** |
| E5 Fix inline, re-check | expected-fail | expected-fail | No inline plan control on the No plan row — **B14 inline fixes not merged**. Also: `00005` (no plan + disputed) is listed under *Disputed reading* only, never under *No plan* — the interim client read keeps one row per blocked account (`DEF-BIL-8216`) |
| E6 Meter Reads down | expected-fail | expected-fail | No switch takes Meter Reads down on a live stack — **B21** stop cannot be reached by a browser |
| E7 Paid after cut-off | expected-fail | expected-fail | The served `paid_after_cutoff` shows as *Setup › Other decision*, Payments & balances reads 0 — **`DEF-BIL-8471`** |
| E8 Sign off reconciles | expected-fail | expected-fail | Accounts add up: *Accounts to bill (step 1) 11 · Billed 8 · Not billed 3 (Blocked 2 · Held by a decision 1)*; **Units billed** and *Regular · master* read *Not available yet.* — **B19 sign-off summary not merged**. And *Billed 8* is not what Send issued (6): see `DEF-BIL-8474` |
| E9 Send with 2 breaks | expected-fail | expected-fail | The seed plants no Send-time break, so there is no *not sent* line to find (J72 E9 fixtures not seeded) |
| E10 Catch-up starts from Sent | **PASS** | **PASS** | Not in this run lists the blocked, held and nobody-to-bill rows; a selection starts a catch-up run (draft child run created). *Runs through all four steps* is not yet walked |
| E11 Drawing | **PASS** | **PASS** | 17 of 36 states captured at each width, every one named after its D1 image; the rest wait on the cases above. The arrangement comparison is by eye against the D1 images (figures not compared — rule 37) and is not yet done |

**Defects this walk found (filed before any fix; none fixed here — each is product code outside
this lane):** `DEF-BIL-8471` paid after cut-off shown as *Other decision* · `DEF-BIL-8472` overlap
offered *Bill as it stands*, refused, *Apply to selected* answers neither row · `DEF-BIL-8473` an
account already billed for the whole period by a sent one-time bill is DRAFTED a second base (seen
in an earlier pass before the walk answered the overlap row; draft only) · `DEF-BIL-8474` the
unanswered paid-after-cut-off account (`00007`) leaves the run with no bill, no break and no Pending
billing row, while Sign off counts it billed.

## WALKED 2026-09-30 (evening) — ACCURACY, clerk checks A1–A6, 1440 and 1280, on PostgreSQL 16

**Stack.** Branch tip `4ec9e6eaa` plus this lane's commits (seed fix and walk only; no product code
touched). Own database `sbh_acc_a7f` on the local PostgreSQL 16 cluster (127.0.0.1:55433): `migrate`
→ `seed_demo` → `seed_j72_bulk_run --month-two`, snapshotted and **reset to that snapshot before each
width**. Django `runserver` (JOBS_EAGER on) behind the built SPA (`vite build --mode compose`,
`server.mjs`). Run: `E2E_VIEWPORT=<w> E2E_BASE_URL=… npx playwright test
e2e/J72-bulk-bill-run-accuracy.spec.ts --workers=1`. One test per check, named by its id.

**What the seed needed.** It no longer ran on a fresh database — its one-time bills called Send
without the five confirmations Send has required since the PO's option-B ruling (`DEF-BIL-8550`;
the J73 prep lane made the same fix in `dbbe1b3ae`, and the row is closed against it). `--month-two` (opt-in, so E4's September tiles do not move) adds an Oct 31
reading on every metered unit, an Oct 17 reading on unit 101, and a 7 × $45.00 payment plan on
`AC-2026-00008` from Sep 15.

**How the walk runs.** A1 walks September through all four steps and reads the counts off each;
its answers set up October — `00003` Estimate, `00009` and `00010` Look into it, `00011` Waive,
`00007` Apply to this bill, `00008` Skip the instalment. Two of those answers cannot be saved today
(`DEF-BIL-8551` Estimate refused, `DEF-BIL-8552` Waive refused), so the walk records the refusal
and falls back to Hold and Include, and September still goes out. Between the runs it sends a
one-time interim bill for `00001` (Oct 1 – Oct 17). A5 then walks October on the same accounts,
answering every open row.

**Results.** Identical at both widths: **2 pass · 4 expected-fail · 0 unexpected**. An expected-fail
runs every step and fails where the named defect bites; the day the fix lands Playwright reports
*expected to fail but passed*.

| Check | 1440 | 1280 | What the walk saw |
|---|---|---|---|
| A1 Totals reconcile on every step | expected-fail | expected-fail | Scope 11 accounts, 12 units. Check 11 checked = Ready 9 + Blocked 2 (adds up). After holding 3 accounts the button still says **Price 9 accounts**; Sign off says **Billed 9**, *Held by a decision 1*, so 9 + 2 + 1 = 12 against 11 to bill; **5 drafts** were made and **Send 5 bills** issued 5. `DEF-BIL-8554` (Price N counts held accounts) · `DEF-BIL-8474` / `DEF-BIL-8220` (Sign off's Billed is not the drafts made) |
| A2 Nobody billed twice | **PASS** | **PASS** | `00010` (a sent one-time bill already covers Sep 1 – Sep 30), answered *Look into it*, has no September bill; no September bill's days overlap any earlier bill of the same account. Note: the walk ANSWERS the overlap, so the unanswered case of `DEF-BIL-8473` is not what this proves |
| A3 No account vanishes | expected-fail | expected-fail | Sent 5 (`00001`, `00002`, `00006`, `00008`, `00011`); Not in this run lists `00003`, `00007`, `00009`, `00010` and the vacant unit — **`00004` and `00005`, the two blocked accounts, are nowhere**: no bill, no break, no Pending billing row. The four held ones are labelled *Blocked*. `DEF-BIL-8553` |
| A4 Bill = draft to the cent | **PASS** | **PASS** | Each of the 5 issued bills equals its Sign off draft ($40.50, $35.63, $76.25, $111.95, $8.00); Sent card $272.33 = their sum = Sign off's total |
| A5 Rulings hold on month two | expected-fail | expected-fail | **Held → one base: PASS three times** — `00006` (held in August) Aug 1 – Sep 30, one $8.00; `00003` (held in Sep) Sep 1 – Oct 31, one $8.00; `00009` (Look into it in Sep) Aug 1 – Oct 31, one $8.00. **Overlap → prorated base: PASS** — `00001` billed Oct 18 – Oct 31 with base **$3.61** = $8.00 × 14/31, the ruled rule on a 31-day month (the PO's $3.73 is the same rule on a 30-day run). **7 kgal true-up: not reachable** — September's Estimate is refused (`DEF-BIL-8551`), so there is no estimate to true up; held instead, October billed all 15 kgal. **$45 instalment: FAIL** — after *Skip* the plan still has Sep 15 due (now *missed*) and ends Mar 15, not Apr 15 (`DEF-BIL-8556`); October's *Add to bill* holds the account, so no October bill carries the $45 (`DEF-BIL-8243`) |
| A6 Every decision traceable | expected-fail | expected-fail | The sent run re-opens on Sent: *5 bills sent*, Not in this run, *View run* (the run list). No screen shows the six answers with who, what, when; the check report read carries findings and no decisions. The answers ARE stored (`bill_run_decisions`, with `decided_by` and `created_at`). `DEF-BIL-8555` |

**Defects this walk filed (before any fix; none fixed here but the seed's):** `DEF-BIL-8550` seed
cannot run (fixed, `dbbe1b3ae`) · `DEF-BIL-8551` Estimate refused on Check · `DEF-BIL-8552` Waive
refused (screen asks no reason; `exclude` vs `waive`) · `DEF-BIL-8553` blocked accounts vanish after
Send · `DEF-BIL-8554` Price N counts held accounts · `DEF-BIL-8555` no decision report after Send ·
`DEF-BIL-8556` a skipped instalment never extends the plan (the screen never saves the Check, and the
extension reads the saved Check). Also seen, already on the register: `DEF-BIL-8243` (*Apply to this
bill* and *Add to bill* hold the account — `00007` in September, `00008` in October) and
`DEF-BIL-8474`'s wider shape — an October row left unanswered (price changed mid-period) leaves the
run with no bill and no Pending billing row; the walk now answers every open row.

## WALKED 2026-09-30 (night) — THE 22 CLERK CHECKS, after the bulk-run-rest fixes (`2.413.0`)

**Stack.** The bulk-run-rest lane's branch (`2.413.0`) rebased on `f4999860c`. Two databases on the
local PostgreSQL 16 cluster, each `migrate` → `seed_demo` → `seed_j72_bulk_run` (plain, and
`--month-two` for the accuracy spec), **seeded with the job queue off** so the J72 accounts are
`AC-2026-00001`…`00011` as both specs expect, snapshotted and reset before every width. A third,
`--send-failure`, for F3. Django `runserver` (JOBS_EAGER on) behind the built SPA (`server.mjs`).
Both specs run with `--workers=1`, Chromium `/opt/pw-browsers/chromium-1194`.

**What changed in the specs, and why.** The screen now reads the SERVED Check (`DEF-BIL-8216`), so
tags are the engine's codes (`missing_read`, `billing_continuity` …) and the figures are the served
taxonomy's: on this seed **Blocked 0 · Ready 4 · Need a decision 7** (no plan and a disputed reading
are decisions), where the interim client showed Blocked 2 · Ready 9. Released holds, each now passing:
E4 (`DEF-BIL-8472`), E5 (B14 inline fixes), E7 (`DEF-BIL-8471`), E8 (B19), accuracy A1, A3, A6. Every
test is named for the check it proves. Held: E6 (B21, no switch — `DEF-BIL-8510`), E9 on the plain
seed (no break seeded), A5 (`DEF-BIL-8243` *Add to bill* holds; `DEF-BIL-8420` the true-up cannot be
walked on this seed).

**J72: 12 pass · 2 expected-fail · 0 unexpected, at both widths. Accuracy: 5 pass · A5 expected-fail.**

| # | Check | 1440 | 1280 | What decided it |
|---|---|---|---|---|
| U1 | Clean cycle end to end | **PASS** | **PASS** | J72 `U1 · E1`, `U1 · U4 · E1b`, `U1 · E1c`: Scope → Check → Sign off → Send, one primary button per step, 11 accounts |
| U2 | Where am I | PASS | PASS | Judged state by state against the D1 drawings in § E11 wave 2 (2.418.9) and wave 3 (2.422.3: 36 of 36 match); this row read NOT RUN until then |
| U3 | Leave and come back | **PASS** (re-open) | **PASS** (re-open) | E8, E1c, E9 and E10 each re-open the run and land on its step (Sign off, Sent). Closing mid-Check is J73 F1's |
| U4 | n of N on Check, Calculate, Send | **PASS** (by test) | **PASS** (by test) | dom tests `DEF-BIL-8224` (Check n of N), `US-BIL-038` (Calculating 754 of 1,371), `DEF-BIL-8422` (Sending 612 of 1,371), `DEF-BIL-8417` (never 0 tiles while checking). In the browser the jobs run inline, so no count is on screen long enough to read |
| U5 | Category → tag → accounts, answer for all, override, inline fix | **FAIL** (one clause) | **FAIL** (one clause) | `U5 · E4`, `U5 · E5`, `U5 · E7` all PASS: a tag's rows, answer for all, a row's Estimate with its figure, *Apply to 1 selected* (1 cannot take it), the plan fixed on the row and re-checked. **But *Answer for all* is not pre-selected** from the Billing defaults (`DEF-BIL-8418`, open) |
| U6 | Every message says what, which, what to do | **PASS** (walked cases) | **PASS** (walked cases) | `U6 · E2`, `U6 · E3a`, `U6 · E3b`; a person's read of the copy is not done |
| U7 | Nobody forgotten | **PASS** | **PASS** | `U7 · E10` (Not in this run lists held, waived and nobody-to-bill; a catch-up run starts) and accuracy A3 |
| A1 | Everything adds up | **PASS** | **PASS** | accuracy A1: Scope 11 = Ready 3 + Need a decision 8; after the answers Price **6** + waiting 2 + held 2 + waived 1 = 11; Sign off Billed 6 + held 4 + waived 1 = 11; 6 drafts; Send 6; issued 6. J72 `A1 · E8` too |
| A2 | Nobody billed twice | **PASS** | **PASS** | accuracy A2: `00010` (a sent one-time bill covers Sep 1 – 30) has no September bill; no bill overlaps an earlier one |
| A3 | No account vanishes | **PASS** | **PASS** | accuracy A3: each of the 11 ends in exactly one place — 6 sent, 5 in Not in this run (4 held, 1 waived) — and the vacant unit is listed |
| A4 | Each bill = its draft | **PASS** | **PASS** | accuracy A4: 6 issued bills equal their Sign off drafts to the cent; Sent card $335.58 = their sum |
| A5 | Rulings on real bills, month two | **FAIL** | **FAIL** | PASS: held → one base (`00006`, Aug–Sep, $8.00), overlap prorated (`00001`, Oct 18–31, $3.61), skip extends the plan (`00008`, 7 × $45.00 to 2027-04-15). FAIL: the October instalment (*Add to bill* holds the account — `DEF-BIL-8243`, the payment-checks lane's) and the 7 kgal true-up (September's 8 kgal estimate IS recorded; the seed commits October's reading before it — `DEF-BIL-8420`). `00009`'s one-base case passed at 1280 and on an earlier 1440 walk, failed on the final 1440 walk (the October answer loop is timing-sensitive) |
| A6 | Every decision traceable | **PASS** | **PASS** | accuracy A6: the sent run's *Check report* tab shows every answer the walk gave with Dana Whitfield and the date |
| F1 | A worker dies mid-Check | NOT RUN | NOT RUN | J73 F1 |
| F2 | A module is down | NOT RUN | NOT RUN | `F2 · E6` expected-fail: no switch takes Meter Reads down (`DEF-BIL-8510`) |
| F3 | Some bills fail at Send | **FAIL** | NOT RUN | `F3 · A4 · E9` on `--send-failure` at 1440: every bill issued, AC-2026-00002's included — the seed produces no break (`DEF-BIL-8421`) |
| F4 | Two clerks | NOT RUN | NOT RUN | J73 F4 (`DEF-BIL-8512`) |
| F5 | Something unexpected | **PASS** (by test) | **PASS** (by test) | `tests/test_bbr_check_engine.py::test_b7__an_unexpected_error_blocks_only_that_account_with_a_support_reference` |
| S1–S4 | Scale | NOT RUN | NOT RUN | J73 S1–S4 |

**Defects this walk found (each filed before its fix):** `DEF-BIL-8417` the Check showed 0 tiles while
the first Check ran (fixed) · `DEF-BIL-8419` a tag said *No accounts here* while its page loaded
(fixed) · `DEF-BIL-8416` (units half) the waived unit was in no line (fixed) · `DEF-BIL-8422`
Sending had no n of N (fixed) · `DEF-BIL-8418` Answer for all not pre-selected (open) ·
`DEF-BIL-8420` the true-up cannot be walked on the month-two seed (open) · `DEF-BIL-8421` the
send-failure seed breaks nothing (open).

## E16/E17 — THE RUN AUDIT IN THE DATABASE, AND ONE ACCOUNT FOLLOWED END TO END (2026-09-30, late night, 2.416.0)

**Why.** The PO, asked how we will know the bulk run works end to end: *"here it is important process
complete for 1 account end to end and does not break down in between"*, with a requirement per step
(`04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md` §5, verbatim there). The walks above
prove what the SCREEN shows; E16 proves what the DATABASE holds for every account of a run, and E17
follows one account through every step and into the next month, checking every record it touches.

### The verifier — `10-scripts/verify_bulk_run.py` (E16)

Read-only, PostgreSQL only, sets `app.tenant_id` first (hard rule 1). Every query is a plain SQL
constant at the top of the file (26 of them, `SQL_…`), pasteable into `psql`; this section describes
what they decide rather than repeating them.

    DATABASE_URL=postgres://…/<db> python 10-scripts/verify_bulk_run.py RUN-0002 \
        [--walk <the walk's state file>]   # what the clerk chose and what the screen showed
        [--clerk "Dana Whitfield"]         # every decision must carry this clerk
        [--next-run RUN-0003]              # month two on the same accounts
        [--account AC-2026-00003]          # one account, with every record it touches (E17)
        [--json]

**The stage is read from the database, never passed**: a release with `released_at` is SENT, drafts
without it is SIGN OFF, a saved Check alone is CHECK. A check that does not apply at that stage prints
`–`, never PASS. It prints a per-account table, the end-state counts, each check's PASS / FAIL / n/a
counts, the run-level checks, and every failure with its figures; exit 1 on any failure.

| Check | PO step | What decides it (tables) |
|---|---|---|
| `P2.saved` | 2 | each current `bill_run_decisions` row has who (`decided_by` → `users.full_name`) and when; an estimate has amount AND unit; a waive has a reason; with `--walk`, every answer the walk clicked exists as the matching choice within 3 minutes of the click, and no current row exists that the walk did not choose; with `--clerk`, every row is that clerk's |
| `P3.effect` | 3 | estimate → the bill's water usage quantity = the decision's amount, same unit, and the payload marks the service estimated · hold / look into / leave out → no bill · waive → no bill · *Add to bill* → `payment_plan_instalment` on the bill · *Skip* → no instalment on the bill · *Apply to this bill* → the post-cut-off payment counted exactly once in the bill's payments received and on no line |
| `P3.next` | 3 | estimate → exactly one `read.estimated` reading in `meter_reads` for that bill, on the period end, amount and unit as decided, not superseded · a hold → a `bill_run_exclusions` (Pending billing) row · waive → `bill_run.base_waived` audit and NOT queued · *Skip* → one `payment_plan.extended_one_month` audit and the plan still has its instalment count · an account still waiting on a decision, or blocked, after Send → a Pending-billing row |
| `P4.drafts` | 4 | at Sign off, one draft for each account that should bill (ready, or every decision answered with a billing answer) and none for held / waived / waiting; after Send, no draft left and at most one bill per account in the run |
| `P4.screen` | 4 | (`--walk`) the screen's Price N, Sign off *Billed*, Sign off total, *Send N bills*, Sent card count and total, Scope accounts, Check tiles and Not in this run list, each against the database; and each account's Sign off draft total against its bill |
| `A3.end` | 5 | exactly one of: issued · failed (a `bill_run_breaks` row with a reason) · Not in this run (queued, waived, nothing to bill, left out, blocked, or waiting); and billed if and only if it should have been |
| `S6.issued` `S6.draft` `S6.ledger` | 6 | status `issued`, a number, `issued_at`, numbers unique · Σ lines + tax = total, the frozen payload's lines and total = the lines, total = the walk's Sign off draft · one posted journal, debits = credits, the 1200 receivable leg on this account moved by exactly the total |
| `S5.delivery` `S5.reads` | 5 | `outbound_messages` has `pdf_print` (the floor, BR-BIL-036) plus email / SMS where the account elected them, all queued · every reading the bill used (`bill_payload.services[].read_id`) and every estimate it wrote is `lifecycle = billed` |
| `S6.audit` `S6.once` | 6 | one `invoice.issued` audit per bill · one journal, one delivery row per channel and copy, one issue audit — so a replayed Send that wrote anything shows as a duplicate |
| `S5.jobs` `S5.locked` | 5 | every `jobs` row carrying the run id is `succeeded` · no decision written and no Check row re-written after `released_at`, none stale |
| run-level | 5–6 | one release row with all five confirmations and who; its authorised count and total = the bills issued; `bill_run.released` audited once; run status `issued`; no draft left |
| `M2.next` `M2.base` `M2.usage` | month two | (`--next-run`) month two starts the day after the account's last bill (or the day after month one's period when month one was WAIVED — PO fixed-charge case 2), no days overlap an earlier bill · one base line per service · usage billed across every bill of the span (month one, any one-time bill between, month two) = the actual meter advance from the last actual read before the span to the actual read at its end — i.e. an estimate trued up, nothing billed twice |

**What it cannot see, said so it is not mistaken for a pass:** the screen (figures come from the
walk's state file — `J72-bulk-bill-run-accuracy.spec.ts` writes `j72-accuracy-<width>.json`; E17
reads the screen itself); and a second Send — a read-only script cannot press it, so it proves the
database holds exactly ONE of everything a Send writes, and E17 presses Send again and compares the
counts before and after.

**Proved red before trusted green (law 7), each on a real fault rather than a planted one:** `A3.end`
and `P3.next` on DEF-BIL-8650 · `P3.effect` on DEF-BIL-8651 · `M2.usage` on the `commit_read`
October reading (15 kgal billed after an 8 kgal estimate) · `P2.saved` on a walk file from a
different database (every answer 1 h 51 min from its row).

### E17 — one account followed end to end (`J72-bulk-bill-run-single-account-trace.spec.ts`)

**Stack.** Branch `claude/upbeat-dirac-olttw0` at `f1e4a6645` (2.416.0) plus this lane's commits.
Own database `sbh_e17` on the local PostgreSQL 16 cluster (127.0.0.1:55433): `migrate` →
`seed_demo` → `seed_j72_bulk_run` (PLAIN, queue off), snapshotted and reset before each width.
Django `runserver` (JOBS_EAGER on) behind the built SPA (`vite build --mode compose`, `server.mjs`).

    E2E_DATABASE_URL=postgres://…/sbh_e17 E2E_PYTHON=<backend python> E2E_VIEWPORT=1440 \
      E2E_BASE_URL=… npx playwright test e2e/J72-bulk-bill-run-single-account-trace.spec.ts --workers=1

**The account.** `AC-2026-00003`, Priya Natarajan, unit 103, meter W-72103 — no September reading.
The clerk answers *Estimate the reading, 8 kgal* on screen. After September is sent, the spec posts
the Oct 31 reading **173.0** through Meter Reads' own import (`/read-batches` stage → validate →
post), then walks October.

**Result: PASS at 1440 and at 1280 — 37 of 37 step checks, identical at both widths.**

| Step | What was checked (in the database unless it says screen) | 1440 | 1280 | What it held |
|---|---|---|---|---|
| 1 Check | account checked, needs a decision, not stale | PASS | PASS | status `decision` |
| 1 Check | the Check read Meter Reads and found the gap | PASS | PASS | finding `missing_read` / water / decision; readings Jul 31, Aug 31 only |
| 1 Check | nothing written yet | PASS | PASS | 0 decisions, 0 bills, no Pending-billing row |
| 1 Check | the Check job finished | PASS | PASS | `billing.run.check` succeeded |
| 2 Answer | answered on screen | PASS | PASS | *Estimate the reading*, 8 kgal, *Record this estimate* |
| 2 Answer | saved: what | PASS | PASS | `missing_read = estimate`, **8.000000 kgal**, water |
| 2 Answer | saved: who and when | PASS | PASS | Dana Whitfield, within seconds of the click |
| 2 Answer | nothing the clerk did not choose | PASS | PASS | exactly 1 current decision |
| 2 Answer | still no bill, no queue row | PASS | PASS | — |
| 3 Calculate | one draft | PASS | PASS | draft **$34.00** |
| 3 Calculate | the estimate is on the draft | PASS | PASS | water usage 8 kgal × $3.25 = **$26.00** |
| 3 Calculate | the draft says the water was estimated | PASS | PASS | `services[water].estimated = true` |
| 3 Calculate | one base, no queue row | PASS | PASS | base **$8.00** |
| 3 Calculate | verifier `P3.effect` | PASS | PASS | — |
| 4 Sign off | screen *Billed* = drafts in the database | PASS | PASS | screen Billed 7, Price 7; database 7 drafts |
| 4 Sign off | verifier `P4.drafts` | PASS | PASS | — |
| 5 Send | screen *Send N* and Sent card = the database | PASS | PASS | Send 7, Sent 7 ($369.58); 7 issued |
| 5 Send | issued, numbered, dated | PASS | PASS | **BL-2610-000012** |
| 5 Send | bill = draft to the cent | PASS | PASS | $34.00 = $34.00; lines + tax = total; payload = lines |
| 5 Send | journal balanced, receivable moved by the total | PASS | PASS | Dr 34.00 = Cr 34.00; 1200 +34.00 on this account |
| 5 Send | paper queued, per election | PASS | PASS | `pdf_print` queued, `portal` queued |
| 5 Send | the estimate saved in Meter Reads | PASS | PASS | Sep 30, 8.000000 kgal, `estimated`, `billed` |
| 5 Send | readings billed-locked | PASS | PASS | — |
| 5 Send | audit rows | PASS | PASS | `invoice.issued`, `read.estimated` (Dana Whitfield) |
| 5 Send | no job pending or failed | PASS | PASS | check, calculate, issue all succeeded |
| 5 Send | decisions and check record locked | PASS | PASS | nothing written after Send |
| 5 Send | ends in exactly one place | PASS | PASS | issued |
| 5 Send | run-level: release, authorised = issued, status, no draft left | PASS | PASS | — |
| 6 Send again | a second Send issues nothing | PASS | PASS | HTTP 200 `created: false`; bills, journals, deliveries, issue audits, releases, estimates all unchanged |
| 7 Month two | Oct 31 reading accepted by Meter Reads' import | PASS | PASS | batch posted, 200 |
| 7 Month two | the October reading trues up the estimate | PASS | PASS | Oct 31 **173.0**, consumption **7 kgal**, `trues_up_read_ids` = the Sep 30 estimate |
| 7 Month two | October's Check lets it through | PASS | PASS | `ready`, no findings |
| 7 Month two | October billed and issued | PASS | PASS | BL-2611-000017, Oct 1 – Oct 31, **$32.50** |
| 7 Month two | starts the day after September's bill | PASS | PASS | Oct 1 |
| 7 Month two | no base twice | PASS | PASS | one base, $8.00 |
| 7 Month two | the estimate trued up | PASS | PASS | October water **7 kgal** × $3.50 = $24.50; **15 kgal over both months = 158.0 → 173.0** |
| 7 Month two | October bill's own after-Send checks | PASS | PASS | issued, draft, ledger, delivery, reads, audit, once, jobs |

**What changes DEF-BIL-8420.** Its escape reason says the true-up cannot be walked because the
month-two seed commits October's reading *before* September's estimate exists. The first E17 run
posted October AFTER September by re-running the seed (`--month-two`) and the true-up STILL failed
(consumption 15, `trues_up_read_ids` null, 23 kgal billed for 15 of water). The seed's `commit_read`
is a history-setup helper that writes the row directly and never runs BR-MET-029's true-up; posted
through Meter Reads' own import, the same reading trues up to 7 kgal. So 8420's fix is the PATH, not
only the order — the accuracy walk's A5 should post October's reading through `/read-batches`.

### E16 — every account of a run, on PostgreSQL 16

**Run 1 — the J72 accuracy walk, September (`RUN-0002`, 1440).** Own database `sbh_e16`: `migrate` →
`seed_demo` → `seed_j72_bulk_run --month-two`; `J72-bulk-bill-run-accuracy.spec.ts` at 1440 (6
passed, A5 expected-fail as marked); verifier with `--walk j72-accuracy-1440.json --clerk "Dana
Whitfield" --next-run RUN-0003`.

**11 accounts: 6 issued · 0 failed · 5 Not in this run** (00004 and 00005 waiting on a decision and
queued, 00009 and 00010 *Look into it* and queued, 00011 waived and listed, not queued).

| Check | PASS | FAIL | n/a | What failed |
|---|---|---|---|---|
| P2 decisions saved (who, when, amount, unit; nothing unchosen; = the walk) | 6 | 0 | 5 | — |
| P3 decision used by Calculate | 5 | **1** | 5 | `00007` *Apply to this bill*: $120.00 paid Oct 1, bill counts **$0.00** received — **DEF-BIL-8651** |
| P3 next-billing records | 7 | 0 | 4 | — (estimate in Meter Reads, plan extended to 2027-04-15, 4 queue rows, waive logged) |
| P4 drafts | 11 | 0 | 0 | — |
| P4 screen = database | 11 | 0 | 0 | Price 6 · Billed 6 · Send 6 · Sent 6 · $335.58 = $335.58 · Scope 11 · tiles 11 · Not in this run = the same 5 |
| A3 exactly one place | 11 | 0 | 0 | — |
| S6 issued · = draft · ledger | 6 · 6 · 6 | 0 | 5 | — |
| S5 delivery · readings locked | 6 · 6 | 0 | 5 | — |
| S6 audit · once | 6 · 6 | 0 | 5 | — |
| S5 jobs · locked | 11 · 11 | 0 | 0 | — |
| Run-level (release, authorised = issued 6 / $335.58, audited once, status, no draft) | 5 | 0 | — | — |
| M2 next · base · usage (October on the same accounts) | 7 · 7 · 5 | 0 · 0 · **1** | 4 · 4 · 5 | `00003` 23 kgal billed for 15 of water — the seed's `commit_read` October reading (DEF-BIL-8420, see above) |

**Run 2 — the same walk, October (`RUN-0003`).** **11 accounts: 7 issued · 4 Not in this run.**
Every after-Send check PASS for the 7 bills ($244.11); run-level PASS. **FAIL 2 — `00011`**:
billed **$8.00** (Oct 1 – 31, base) with `base_only_billing` and `billing_continuity` (gap) still
open and no answer saved — **DEF-BIL-8650**. And the run carries **0 decisions**: the accuracy
spec's October loop skips every row whose select already shows a choice, which the Check now
pre-selects without saving — **DEF-BIL-8652** (A5's expected-fail hid it).

**Run 3 — E17's September (`sbh_e17`, 1280), only `00003` answered.** **11 accounts: 7 issued · 4
Not in this run.** Every after-Send check PASS for 7 bills ($369.58). **FAIL 4 on 2 accounts** —
`00009` (gap, $63.25) and `00011` ($8.00) BILLED with their decision unanswered and not queued:
DEF-BIL-8650 again, in month one. `00007` (paid after cut-off, unanswered) was correctly held.

**Run 4 — 10,015 accounts (J73 world, `RUN-0002`).** A copy of `sbh_j73_10k` (`seed_j72_bulk_run
--accounts 10000`) migrated to 2.416.0 as `sbh_e16_10k`; the run driven through the REAL views
in-process as Dana Whitfield (the `j73_bulk_run_harness.py` `_Api` pattern, JOBS_EAGER on) — Check,
Calculate (`background: true`), release with the five confirmations, Send, then Send again — with
**no decision answered**. Times on the shared, loaded machine (load 5–6): **Check 136 s (13.6 ms an
account)** · **Calculate 317 s** · release 3 s · **Send 1,627 s (27 min, ~6 bills a second)** · Send
again **0.005 s, `created: false`**. The verifier took ~3.5 minutes over the run.

**10,015 accounts: 10,010 issued · 4 Not in this run · 1 in two places.**

| Check | PASS | FAIL | n/a | What failed |
|---|---|---|---|---|
| P3 next-billing records | 5 | **2** | 10,008 | `00009`, `00011` billed unanswered, not queued — DEF-BIL-8650 |
| P4 drafts (none left after Send) | 10,015 | 0 | 0 | — |
| A3 exactly one place | 10,012 | **3** | 0 | `00009`, `00011` (DEF-BIL-8650) · `00003` (No reading, unanswered) has a Calculate break AND a Pending-billing row — **DEF-BIL-8653** |
| S6 issued · = draft · ledger | 10,010 each | 0 | 5 | — |
| S5 delivery · readings locked | 10,010 each | 0 | 5 | 20,020 delivery rows (print + portal) |
| S6 audit · once | 10,010 each | 0 | 5 | 10,010 issue audits, 10,010 journals, 1 release |
| S5 jobs · locked | 10,015 each | 0 | 0 | check, calculate, issue succeeded |
| Run-level | 5 | 0 | — | authorised 10,010 / **$1,843,720.55** = issued 10,010 / $1,843,720.55 |

`DEF-BIL-8653` filed from this run: an unanswered *No reading* account is both a Send failure
(`missing_read_undecided_at_calculate`, resolution empty) and a Pending-billing row.

**Defects this lane filed (each before any fix; none fixed here):** `DEF-BIL-8650` an account whose
only open decisions are *Standing charges only* / *Gap or overlap* is billed with no answer ·
`DEF-BIL-8651` *Apply to this bill* counts the post-cut-off payment nowhere on the bill (the Check
raises a `processing` payment; the balance forward reads only allocated ones) · `DEF-BIL-8652` the
accuracy walk's October loop answers nothing · `DEF-BIL-8653` an unanswered No reading account ends
as both a failure and a Pending-billing row. Named, not re-filed: `DEF-BIL-8420` (refined above).
## WALKED 2026-10-01 — THE 22 CLERK CHECKS AFTER THE FINAL BULK-RUN LANE (`2.417.0`)

**Stack.** The final bulk-run lane's branch rebased on `d1d1fb29b`, the SPA built from it, Django
`runserver` behind `server.mjs`; three worlds on PostgreSQL 16 reset from their snapshots before
every walk (plain, `--month-two`, `--send-failure`). `--workers=1`, Chromium
`/opt/pw-browsers/chromium-1194`.

**What changed in the specs, and why.**
- **E6 is real**: the test-only switch takes Meter Reads down; it is no longer an expected fail.
- **E9 is real on `--send-failure`**: the seed now breaks AC-2026-00008 at Send for real.
- **U5/E4** asserts *Answer for all* opens on the Billing default, *Estimate*.
- **E1** asserts the Nobody to bill panel lists the unit, with *Add account ↗* in a new tab.
- **Accuracy A5's expected fail is removed.** The payment lane's *Add to bill* prints the $45.00
  instalment on the bill from its stamped payload and charges nothing, so A5 reads the bill's
  document.
- **Two reads now wait under load**: Not in this run, and October's tag list.

| Walk | 1440 | 1280 |
|---|---|---|
| J72 (plain seed) | **14 pass** (E9 expected-fail: no break on this seed) | **14 pass** (same) |
| J72 (`--send-failure`) | **14 pass**, E9 real | **14 pass**, E9 real |
| Accuracy A1–A6 | **6 pass** | **6 pass** |

**Month two, from the database:** AC-2026-00001's overlap base **$3.61** (14/31 of $8.00);
AC-2026-00003's true-up **7 kgal** (Oct 31 173.0 − Sep estimate); AC-2026-00009 **one** base for
Aug 1 – Oct 31 after its hold; AC-2026-00008's October bill BL-2611-000022 prints *Instalment 1:
45.00 USD due 2026-10-15* and has no plan charge line.

**Seen once, not reproduced:** J72 E7 at 1280 drew a blank page for 90 seconds at load 8 and
passed when walked again; one accuracy run at load 10 read Not in this run and October's tags
before they loaded (A2, A3 and A5 failed). The reads now wait, and both widths pass 6 of 6.

**Defects fixed by this lane:** `DEF-BIL-8418`, `8420`, `8421`, `8510`, `8511`, `8512`, `8580`,
`8581`, `8582`, `8244`, `8221`, `8222`, `8414`. **Still open:** `DEF-BIL-8412` (Apply next bill
prints like Apply to this bill; `OQ-217` CLOSED 2026-10-01 — built by the six-rulings lane), `DEF-BIL-8583` (eleven bill-run tests red on
the tip before this lane).

## E11 WAVE 3 — THE LAST EIGHT STATES, EACH A FIELD THE SERVER NOW SENDS (2026-10-01, build 2.422.3)

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

## E11 WAVE 2 — THE DIFFERENCES FIXED, EVERY STATE RE-CAPTURED (2026-10-01, builds 2.417.2 – 2.418.9)

**Ruling for the wave** (coordinator, under B14 rule 41): for the bulk run the blueprint owns
layout, copy, flows and states and our UI standard owns how it is built, so every difference is a
defect to fix rather than a question for the PO. Money is shown exactly as the engine computes it;
only how it is shown moves. The money behaviour of *Next bill* stays with `DEF-BIL-8412`.

**How.** The same capture spec, now on the J72 seed with `--e11-states` (`DEF-BIL-8689`: unit 113
has water and no meter, unit 114 a gallons meter on a kgal plan, unit 115 a reading and a meter with
no unit), and with the August run recorded as sent (`DEF-BIL-8690`). PostgreSQL 16, reset before
each width. **All 36 states captured at 1440 and at 1280 (72 images); none unreachable.**

**Result: 28 of 36 match; 8 differ, each on a difference that is filed and needs a figure or a
field the server does not serve yet.** (All eight match in wave 3, above.) No state differs at one width and not the other.

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

## E11 — EVERY DRAWN STATE BESIDE ITS D1 IMAGE (2026-10-01, build 2.417.1) — SUPERSEDED BY WAVE 2 ABOVE — clerk check U2

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

## RE-WALKED 2026-10-01 — the PO's six rulings of that day, build 2.422.0, 1440, PostgreSQL 16

**Stack.** A FRESH database `sbh_six72`: `migrate` → `seed_demo` → `seed_j72_bulk_run --month-two`
(template `sbh_six72_seeded`); `J72-bulk-bill-run-accuracy.spec.ts` at 1440 sent September
(`RUN-0002`); then `verify_bulk_run.py RUN-0002 --walk j72-accuracy-1440.json --clerk "Dana Whitfield"`
as the database's owning role (`postgres`; `DEF-BIL-8692` — the verifier still cannot be run as an
RLS-bound role).

**`AC-2026-00007` IS GREEN.** Its September bill `BL-2610-000014` stamps **previous 34.00 · payments
120.00 · current 37.25 · total due −48.75** (`basis: whole_account_since_last_bill`), printed on the
paper as *"Total due 0.00 USD · credit 48.75 USD"* and on the bill screen as *$0.00 · Credit $48.75*
(PO ruling 6, `OQ-217` closed, `DEF-BIL-8670`). The verifier's *Apply to this bill* check (P3.effect)
now passes for it: the bill counts the $120.00 paid after the cut-off as payments received.
**RESULT: PASS** — 11 accounts, 6 issued, 5 not in this run; P2 6/0, P3.effect 6/0, P3.next 7/0, every
after-Send check 6/0, run level 7/7. `AC-2026-00004` (no plan) now reads **blocked** rather than *waiting
on a decision* (PO ruling 3: no default plan; the plan is fixed on the row).

**Two things found, neither caused by the rulings.** The verifier mapped the Check's old label
*"Estimate the reading"* only, and the screen now says *Estimate* (the E11 copy lane), so `00003`'s
saved estimate read as unchosen — the map now carries both spellings. The spec's A3 still fails on
*"the vacant unit is listed too"* and A5 needs `E2E_J72_LATE_READ` (October was not walked here).
Screens: `08-qa/screens/po-rulings-2026-10-01/` (`10-scripts/po_rulings_20261001_walkthrough.mjs`,
6 of 6 PASS).
