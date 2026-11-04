# Bulk bill run redesign — build plan (2026-09-30)

Status: **PLAN, NOT STARTED.** Builds every change in `14-bulk-bill-run-changes.md`
(rows 1–54; rows 43–54 were agreed after this plan was written and were added as B22–B26 and T8 on 2026-09-30) as drawn in the mock-up https://claude.ai/artifact/NXYoLbAzQEC3FGyyLhjv4X,
reviewed by the PO screen by screen on 2026-09-30. Rulings: the 2026-09-30 rows of
`12-governance/02-decision-log.md`.

**Which process:** the bulk run exists and clerks use it, so this is MAINTENANCE
(`12-governance/22-product-maintenance-process.md`) — a live screen redrawn end to
end — borrowing Build's drawing step, exactly as the one-time bill redesign did
(`12-one-time-bill-build-plan.md`). Every screen is built from the drawing captured
as IMAGES (B14 rule 42) with the `react-tailwind-css-ui-generator` skill, in our UI
standard (rule 44).

**What is already done and is NOT repeated here** (built for the one-time bill,
shared by the engine): changes 1–8 — sewer with no service point, no asset = not in
service, missing base = $0.00 + warning, two meters = two lines with the minimum per
meter, counted services one base line per service, no agreements = bill all + warn,
warnings on drafts, one bad bill breaks only itself.

**Carried over from the one-time bill and shared:** change 29 (price version at
PERIOD END) is one engine change serving both — it is task B16 here and is not
built twice.

> **Check-engine lane, 2026-09-30 (`2.412.0`) — BUILT:** B7, B8, B9 + DB1 (the
> store, now IN scope under OQ-843's re-ruling, option C), B10, B11, B12 (the
> facts payments stores; four declared absent — `DEF-BIL-8240`–`8242`), B13,
> B15, B16 🔒, B17 (Check job; Calculate's job already existed), B21, and API
> A3–A6 (`apps/billing/check_api.py`: `POST|GET …/check`, `…/check/resume`,
> `…/check/findings`, `…/check/decisions`, `…/check/recheck`; A7 is the
> existing `POST …/calculate` with `background: true`). The per-account check
> order, the change feed and the seven judgments are the decision log's row of
> the same day. **NOT built here:** B14 (inline fixes — the screen calls the
> owning module; every tag says which), A10 (schema regenerated once, later),
> the money application of the choices listed in `DEF-BIL-8243`.

## R · Records (before any code)

| # | Task | Change rows |
|---|---|---|
| R1 | File one defect per bulk-run review gap, including the 10 finding codes with no clerk label and warnings missing from the findings payload | 28, 36 |
| R2 | Amend rules, each stamped with its 2026-09-30 ruling: BR-BIL-1040 (standing answers at Check, per tag), the run key without a services term (BR-BIL-005), continuity (overlap refuses, gap warns with NO tick), vacant unit with nobody to bill = warning, price version at period end, payment checks at Check, left-out → Pending billing | 11, 13, 17, 18, 29, 38, 40 |
| R3 | Stories with §3 test cases written BEFORE code: Scope · Check · Calculate · Sign off · Send · Not in this run / catch-up; journey J72 | all |
| R4 | Human-review-ledger rows for every 🔒 file touched (`runs.py`, `pending.py`, `issue.py`, rating version selection, the idempotency key) | 11, 21, 26, 29 |
| R5 | Correct row 17 of the changes list ("gap = warn with a tick" is superseded by row 35: no tick) and the blueprint/B14 note for the Scope change | 17, 35 |

## D · The drawing into the tree

| # | Task |
|---|---|
| D1 | Capture every mock-up state as PNG at 1440 and 1280 — **36 states × 2 widths = 72 images** — into `05-prototype/bulk-bill-run-2026-09-30/` (list below) |
| D2 | The skill's §2.1 inventory from the images, including what is ABSENT (no services filter, no standing answers on Scope, no "billed to owner") |


**The 36 states D1 captures** (each at 1440 and 1280):

| Step | States | Count |
|---|---|---|
| Scope | continuous · gap · overlap · warnings · problems · panels collapsed · Nobody to bill panel · Missing meter panel | 8 |
| Check | checking progress · module down · decision tag (No reading) · decision with rows selected · blocking tag fixed on the row · blocking tag fixed on another screen · warning tag · payments tag · filtered by the Blocked tile · problem search · passed checks shown · Ready to bill · a ready account left out · Fix-account panel · a fixed, re-checked row | 15 |
| Calculating | progress | 1 |
| Sign off | summary with all sections open · Who is billed · Usage and charges · Payments and balances · Not in this run filtered to Nobody to bill · Failed to draft panel · confirmations ticked | 7 |
| Send | not ticked · ticked · sending · sent with Not in this run · catch-up run started | 5 |
| **Total** | | **36** |

## B · Backend — engine and reads

| # | Task | Rows |
|---|---|---|
| B1 | Scope validation returns EVERY refusal and warning at once, each on its field with its own key (run name, period order, overlap, bill date, days to pay, template published, run-number series; gap, period length, bill day, days to pay changed, template not usual, nobody to bill, missing meter) | 16, 19, 35 |
| B2 | Continuity against the cycle's REAL last run (not the first 50; cancelled drafts ignored): overlap refuses naming the run, gap warns | 17 |
| B3 | Drop the services filter from the run and from its idempotency key 🔒 (existing runs keep their key) | 11 |
| B4 | Run name required on create; template required and published | 12, 14 |
| B5 | Scope counts read: units in cycle, accounts to bill, regular, master, meters, sub-meters, behind the meter, missing meter, units with nobody to bill; last-run figures for the three account counts only | 15, 30 |
| B6 | Cycle details read (frequency, reads start, days to complete, bill day, days to pay, routes, first run, runs so far, status) and previous runs for the cycle | 31, 32 |
| B7 | Check isolates each account in its own savepoint; ANY error on an account blocks that account with its reason; a reading without a unit is that account's problem | 21, 23, 26 |
| B8 | Check finds EVERY problem on an account in one pass (account, each service on its own, decisions) | 22 |
| B9 | Check runs as a background job: saved results, progress, resumable; results read from the store instead of recomputed on every load (today 137 ms/account → ~90 min at 40,000) | 25 |
| B10 | Problem taxonomy: every finding code → category · tag · severity · fix screen; clerk labels for the 10 codes that have none | 36 |
| B11 | Warnings (base $0.00, no agreements, …) on the findings payload, not only on drafts | 36 |
| B12 | Payment checks at Check through the payments seam: paid after cut-off, unmatched payment, bounced payment, plan instalment due, level pay off track (decisions); credit covers bill, autopay card expiring, deposit not paid, in collections (warnings) | 38 |
| B13 | Standing answers per tag: answer-for-all (default from Billing settings), per-row override, apply to selected | 20 |
| B14 | Inline fixes from Check, each written by its OWNING module's service (reading → Meter Reads, plan/unit → Accounts, size/count → Assets, city limits → Premises) — no cross-module write from billing | 36 |
| B15 | Re-check named accounts only (`calculate_run(only_accounts=…)` pattern for prepare) | 36 |
| B16 | Price version = the one in force at PERIOD END for bulk AND one-time bills 🔒 | 29 |
| B17 | Calculate as a background job with progress (drafts only) | 39 |
| B18 | Leave a ready account out → Pending billing with reason "left out by clerk"; put back | 41 |
| B19 | Sign-off summary read: who is billed (accounts and units reconciling to Scope's figures), usage and charges per service, other categories (taxes, fees, credits), payments and balances, how it will be paid, by customer type | 37 |
| B20 | Not in this run list; catch-up run for selected (`pending.create_catch_up_run`, exists); leave for next cycle | 40 |
| B21 | Utility-wide stops name what and who; unexpected errors carry a support reference; the run is always kept | 24 |
| B22 | At Send, write each clerk's estimate into Meter Reads as an estimated reading through its own service (added 2026-09-30) | 47 |
| B23 | The five fixed-charge rulings: base without a reading, Waive, one base after a hold, overlap from the day after, plan extended by a month (added 2026-09-30) | 48–52 |
| B24 | Saved Check results; re-check an account automatically when its plan, reading, meter or payment changes (added 2026-09-30) | 53 |
| B25 | Keep Check output as long as the bills: lock decisions and standing answers at Send, freeze the check report, keep only final findings (added 2026-09-30) | 54 |
| B26 | Scope checks, the no-stop alternatives, no automatic fixes, one tag per former automatic case (added 2026-09-30; rows 43–46 were agreed after the plan was written) | 43–46 |
| B27 | Each Check batch of 500 loads its accounts' readings, plans and payments in one query set instead of per account; measure ms/account before and after (added 2026-09-30) | 55 |
| B28 | The Check runs as parallel batches of 500 under one coordinator: per-utility cap on batches at once (half the billing workers, minimum 1, a platform setting — decided 2026-09-30), totals counted once at the end, progress summed, resume per batch; PostgreSQL proof at 40,000 accounts (added 2026-09-30) | 55 |
| B29 | The PO's six rulings of 2026-10-01 that reach the bulk run: no plan on the unit blocks until the plan is fixed, no default plan (57); the balance forward over the whole account since the last bill (58); the cart prorates like the base (59); a swapped meter priced per meter (60); a payment-plan bill asks new charges + this month's instalment (61) (added 2026-10-01) | 57–61 |

## A · API

| # | Task |
|---|---|
| A1 | `POST /billing/runs`: run name, template, no services; `field_errors` lists all problems; warnings returned |
| A2 | `GET /billing/runs/scope-preview?cycle&period…`: counts, last-run counts, cycle details, previous runs, continuity, problems |
| A3 | Check job: start, progress, resume |
| A4 | `GET …/findings`: categories and tags with counts; one tag's accounts paginated and searchable, with each account's other tags; Ready to bill as its own list |
| A5 | Decisions: answer for a tag, per account, for a selection |
| A6 | Re-check selected accounts |
| A7 | Calculate job: start and progress |
| A8 | `GET …/sign-off-summary` |
| A9 | Not in this run; catch-up (exists: `POST …/catch-up`); leave for next cycle; leave out / put back a ready account |
| A10 | OpenAPI schema regenerated once |

## DB · Database

| # | Task |
|---|---|
| DB1 | Findings store for the background Check: one row per account per problem (tag, severity, detail, fixed-at) — tenant-scoped, RLS FORCE |
| DB2 | Run name required going forward (existing rows keep theirs); services term out of the key for new runs only |
| DB3 | Pending-billing reason for "left out by clerk" |

## F · Frontend (built from the D1 images; skill `react-tailwind-css-ui-generator`)

| # | Task | Rows |
|---|---|---|
| F1 | Pre-flight per skill §7 | — |
| F2 | ONE bill-run screen: Bills → Run opens the new 4-step screen; delete `BillRunWizard` and the unreachable duplicates; door test | 9 |
| F3 | Scope · What to bill (run name, cycle, period, bill date, days to pay, template) | 10–14 |
| F4 | Scope · refusals and warnings at the top, on each field, Start disabled with "Fix N things first." | 35 |
| F5 | Scope · Cycle details, This run covers (with last-run figures), Previous runs — collapsible | 15, 30–33 |
| F6 | Scope · Run to start side card with `ServiceChips` | 34 |
| F7 | Check · progress and module-down states | 24, 25 |
| F8 | Check · tiles, category → tag list, search, passed checks, Ready to bill tab | 36, 41 |
| F9 | Check · tag pane: answer for all, table, selection, per-row decision, "also has", pagination | 20, 36 |
| F10 | Check · inline fixes and re-check | 36 |
| F11 | Check · Fix-account side panel | 36 |
| F12 | Check · Ready to bill list with leave out / put back | 41 |
| F13 | Calculating bills progress | 39 |
| F14 | Sign off · summary, Who is billed, Usage and charges, Payments and balances, By customer type, Not in this run, warnings, confirmations | 37, 40 |
| F15 | Send and Sent, with Not in this run → catch-up / next cycle | 40 |
| F16 | Every string in all eleven catalogues within B14 rule 33 | — |
| F17 | Tailwind only; new files on `route-b-migrated.txt` | — |
| F18 | API client types and calls | — |
| F19 | Not in this run gains a Nobody to bill filter (unit rows); Scope keeps two list panels (Nobody to bill, Missing meter) because no run list exists yet; Failed to draft panel with Retry | 42 |

## T · Tests (from each story's §3, before the code)

| # | Task |
|---|---|
| T1 | Unit, red first: 3 accounts with the middle broken → 2 priced; all problems on one account found at once; each Scope refusal and warning; continuity; price at period end ($3.25 not $3.50); each payment tag; left-out → pending |
| T2 | PostgreSQL proofs: per-account savepoint (law 14); a 40,000-account Check and Calculate timed against the 60-second worker limit (background) |
| T3 | API tests: every new route, pagination, tenant isolation |
| T4 | Component tests per F-component, routed under the real path |
| T5 | Door test: Bills → Run opens the new screen, the old wizard is unreachable |
| T6 | Gate suite green (G31, G32, G33, G15, G7, G13, G140) |
| T7 | Every-link test: click every link on every step; fail on a link that changes nothing |
| T8 | Two-month tests: bill September with each decision, then October, and assert the October figures above ($3.73 prorated base, 7 kgal true-up, one base after a hold, 7 × $45) (added 2026-09-30) | 47–52 |

## E · End-to-end (Playwright, seeded tenant, 1440 and 1280)

⚠ **ORGANISED BY THE 22 CLERK ACCEPTANCE CHECKS (PO 2026-09-30, *"your end ot end walk should be around these cases"*).** Every E task below is walked and reported as the checks it proves (U1–U7, A1–A6, F1–F5, S1–S4 in `20-bulk-run-clerk-acceptance.md`); the results table always has 22 rows.

| # | Journey |
|---|---|
| E1 | Clean run: Scope → Check → Calculate → Sign off → Send |
| E2 | Scope problems: all shown at once, each on its field |
| E3 | Gap (warns, starts) and overlap (refused, links the run) |
| E4 | Check: decide a tag for all, override one row, apply to selected |
| E5 | Check: fix a blocked account inline, re-check, it moves to Ready |
| E6 | Check: Meter Reads down → the stop names what and who; run kept |
| E7 | Payments tags: paid after cut-off applied to this bill |
| E8 | Sign off: every figure reconciles to Scope's |
| E9 | Send with 2 breaks → sent and broken shown apart |
| E10 | Not in this run → catch-up run for 5 → it runs through all four steps |
| E11 | Screenshot diff of every state against the D1 images |
| E12 | J73 breakdown walk: a worker killed mid-Check resumes (F1); Meter Reads down shows what and who with Try again (F2); failed bills at Send listed apart and retried alone (F3); two clerks on one run (F4); an unexpected error gives a support reference (F5) (added 2026-09-30) |
| E13 | J73 scale walk on PostgreSQL: Check at 10,000 and 40,000 accounts (S1); tag list, Sign off and Not in this run open in < 2 s at 40,000 (S2); Send 40,000 with progress and resume, no duplicate numbers (S3); a second utility's run still starts (S4) (added 2026-09-30) |
| E14 | J73 accuracy walk: counts reconcile on every step (A1), no double billing (A2), no vanished account (A3), bill = draft to the cent (A4), rulings hold on month two (A5), every decision traceable in the report (A6) (added 2026-09-30) |
| E15 | Clerk usability pass by a person against `20-bulk-run-clerk-acceptance.md` §1: a clean cycle in one sitting, always knows the step and the next act, leaves and returns, progress always a number (U1–U7) (added 2026-09-30) |
| E16 | **Run audit in the DATABASE after every bulk walk** (added 2026-09-30, answering the PO's *"how you will know whether bulk run capabilities are working end to end and it is generating bill and sending it"*): a re-runnable verifier that, for EVERY account in the run, checks it ended in exactly one place (issued bill · failed with reason · Not in this run); every issued bill is ISSUED with a number, its lines equal its Sign off draft to the cent, its ledger journal balances and the receivable moved by its total; the release carries the confirmations; audit rows exist; paper delivery is queued; clerk estimates sit in Meter Reads as estimated readings; decisions and the check record are locked after Send; a second Send issues nothing. Then a SECOND MONTH on the same accounts: the next bill starts where the last ended, no usage or base billed twice, the PO's worked figures hold. Run on the J72 seed (11 accounts) and on the J73 10,000-account seed. Results as a table per run in J72/J73 |
| E17 | **Single-account trace** (PO 2026-09-30: *"process complete for 1 account end to end and does not break down in between"*): one account with a real problem (e.g. no reading → estimate) followed Scope → Check → answer → Calculate → Sign off → Send → month two, asserting at every step every record the account touches — decision saved, decision used by Calculate, system data read, next-billing records (estimate in Meter Reads, plan extension, pending billing), draft, final bill, communication, ledger, payment application, audit — per `20-bulk-run-clerk-acceptance.md` §5 |

## C · Close

| # | Task |
|---|---|
| C1 | Version bump; recorded on every defect and change |
| C2 | Review-ledger rows state what was shown to the PO, with the figures |
| C3 | PO walk-through in a browser; tell the PO which build to look in |
| C4 | Rollback stated before shipping |

### Close-out status (2026-10-01, close-out lane)

| # | State | Where |
|---|---|---|
| C1 | **Done.** 20 closed bulk-run defects had no version on their register row; each now carries the version of the build it landed in, taken from git (the closing commit's version where it named one, otherwise the first build numbered with the fix), never guessed. Seven bulk-run versions (`2.417.0`, `2.418.1`, `2.418.3`, `2.418.5`–`2.418.7`, `2.418.9`) had been published with no CHANGELOG entry (G35 red since then); each now has one, written from the commit that published it. No bulk-run change request exists (the work ran on this plan, not a CR). | `12-governance/10-defect-log.csv`, `CHANGELOG.md` |
| C2 | **Partly done.** The six top rows for this plan (Scope `B1`–`B3`, R4 1–5) read *PLANNED, NOT BUILT* and *none yet* for evidence; corrected to what is built and tested. The Scope row's empty Human review cell now states what was shown and the question still to put, with its figure. Still missing a figure: the *NOT shown* lists of three 2026-09-30 sections (*BULK CHECK ENGINE*, *FIXED-CHARGE RULINGS 1–5*, *BULK RUN REST*) name each item in words but give no worked figure, and the decision log has none to copy. Nothing is ratified; only the PO can. | `12-governance/09-human-review-ledger.md` |
| C3 | **Script written, PO walk not yet done.** | `21-bulk-run-po-walkthrough.md`, screenshots in `08-qa/screens/bulk-run-closeout-2026-10-01/` |
| C4 | **Stated below.** | this section |

**The gate (`bulk_run_trace.py --close`) still fails, and it should:** a row is `Walked` only when the PO has
seen it in a browser on a named build, and the PO has walked none of the 61 rows. C3's walk-through is the
instrument for that. Before this close-out, 23 rows read `In progress` or `To build`, most of them built and tested;
19 of them now name their proving tests and read `Merged`. Three Scope rows (31 Cycle details panel, 33
collapsible panels, 34 the Run to start card with service chips) are built and appear in every E11 screenshot,
but no test asserts them, so they stay `In progress` until one does. Row 28 (records) is done but a records
task has no test to carry its marker, so the tracker cannot move it.

### C4 · Rollback (stated 2026-10-01, before the PO walk-through)

**This supersedes `18-rollback-2.412.md` for any rollback from `2.413.0` on.** That note was written for
`2.412.x` and says to run `migrate billing 0031` first, which drops the three Check tables; since then a
40,000-account run has been sent with its check record locked and kept by ruling, so that command would
delete records the PO ruled are kept as long as the bills.

**The short answer.** Roll the bulk run back by **reverting code and leaving the database as it is**. Every
schema change the bulk run made is additive and nullable, so older code runs on the newer schema. Do **not**
run the migrations backwards in production: three of them would delete records the rules say must be kept.

**Versions.** The last build before any bulk-run code is **`2.410.21`** (the changes list, `acf6ea7bd`, was
written on top of it). The bulk-run code runs from `2.411.0` to **`2.437.2`** (today's tip), but it is
interleaved with unrelated work in the same window — the charge-code waves (`CR-156-BRC10`, rating
`0050`–`0055`), the seasonal price split (`OQ-234`, `2.437.1`), the meter-reads post (metering `0064`) and
twelve new message kinds (tenancy `0054`). So "go back to `2.410.21`" is not a bulk-run rollback: it takes all
of that out too, and rating `0051` and `0053` move price data. **The rollback unit is the bulk-run commits,
reverted on top of the tip.** The screen cannot go back on its own: `91eca0bff` (`2.412.3`) deleted the old
six-step wizard, and the old wizard called routes and fields (the services filter) that no longer exist.

**The migrations since the bulk-run work began, by name** (all in `06-backend/apps/billing/migrations/`):

| Migration | What it adds | First build | Reverse it? |
|---|---|---|---|
| `0031_invoice_line_asset_id` | `invoice_lines.asset_id`, nullable — which asset a bill line priced | `2.411.4` | **No.** Reversing drops the column from issued bill lines. |
| `0032_bbr_check_store` | tables `bill_run_account_checks`, `bill_run_findings`, `bill_run_standing_answers` | `2.412.3` | **No.** Reversing drops every saved Check, which the PO ruled is kept as long as the bills. |
| `0033_rls_bbr_check_store` | row-level security on those three tables | `2.412.3` | Only with `0032`; leave it. |
| `0034_bbr_check_record_locked_at_send` | a trigger refusing any write to a sent run's check record | `2.412.3` | **No.** It is the lock the PO ruled; old code never writes those tables, so it does no harm. |
| `0035_bbr_finding_check_step` | `bill_run_findings.check_step`, nullable | `2.413.0` | Not needed; harmless if left. |
| `0036_bbr_exclusion_next_cycle` | `bill_run_exclusions.next_cycle_at`, `next_cycle_by_id`, nullable | `2.413.0` | Not needed; harmless if left. |
| `0037_def_bil_8708_invoice_line_id_index` | index `ix_invoice_lines_id` | `2.424.1` | Safe either way (`DROP INDEX`); leave it, the Send is faster with it. |
| `0038_d8696_sign_off_snapshot` | `bill_runs.sign_off_snapshot`, `sign_off_snapshot_key`, nullable | `2.425.0` | Safe (`migrate billing 0037` drops two columns of a cache); not needed. |
| `0039_invoice_line_pricing_trace` | `invoice_lines.pricing_trace`, nullable — how each line was priced | `2.426.1` | **No.** Reversing drops the column from issued bill lines. |

No other module gained a migration for the bulk run.

**Data a revert leaves behind, and how to undo each** — none of it is undone by a revert, by design:

1. **Bills already sent.** On the 40,000-account world, 40,008 bills totalling $7,371,531.12, due 10/22/2026.
   Issued bills, their lines, ledger journals and payments are never updated or deleted (hard rule 4). To
   undo a bill: a credit note through *Fix a bill*, one bill at a time, or a corrective run. A code revert
   does not touch them.
2. **Saved Check records** (account checks, findings, standing answers, decisions). Kept and locked once a run
   is sent. Old code ignores them. Nothing to undo.
3. **Clerk estimates written into Meter Reads** at Send (`DEF-BIL-8280`): estimated readings tagged with run,
   bill and clerk. They stay and Meter Reads' own true-up subtracts each at the next real reading. To undo one
   before then: correct it in Meter Reads.
4. **Accounts left out, held or put to *Leave for next cycle*** (`bill_run_exclusions`, Pending billing). They
   stay in Pending billing, which predates the bulk run, and the next run or a catch-up bills them.
5. **Payment plans made one month longer** by a *Skip* answer. They stay; undo by editing the plan.
6. **Queued paper bills and messages, audit rows, job records.** They stay; nothing to undo.

**Order of a rollback, if one is needed:** stop new runs (no Start checking); let any Send in flight finish,
because the reverted code would finish it with the old single-task body; revert the bulk-run commits on top of
the tip; leave every migration applied; deploy; re-run the bill-run suites. A code-only revert is stated for
each lane's change in its own ledger section (*"Rollback: revert the lane's commits; no migration"*).

## Count

| Group | Tasks |
|---|---|
| R records | 5 |
| D drawing | 2 |
| B backend | 28 |
| A API | 10 |
| DB database | 3 |
| F frontend | 19 |
| T tests | 8 |
| E end-to-end | 17 |
| C close | 4 |
| **Total** | **96** |

## Order and lanes

1. **R1–R5, D1–D2** first (one lane).
2. **Engine lane:** B7–B11, B15–B17, B21, DB1 — after the one-time bill API lane merges, because both touch `runs.py` and `api.py`.
3. **Reads lane:** B1–B6, B12, B18–B20, DB2–DB3, A1–A10.
4. **Screen lane:** F1–F18 from the images, starting with Scope (no engine dependency) while lanes 2–3 build.
5. **T and E alongside each piece; C1–C4 last.** Push after every step.

## Open (not blocking the start)

- Payment checks (B12) need the payments module to expose each fact through a seam; where a fact has no source today it is built as a deliberate absence and filed, not guessed.
- "Leave for next cycle" relies on the next run billing from the last billed read; a proof that no usage is lost belongs in T1.
