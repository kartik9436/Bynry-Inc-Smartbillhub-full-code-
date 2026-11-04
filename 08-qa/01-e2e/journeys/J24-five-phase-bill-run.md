# J24 — The five-phase bill run (prepare → calculate in background → breaks → summary + gate → release, and 1,122 of 1,124 is a run that worked)

---
id: J24
tier: 2
rules: [BR-BIL-050, BR-BIL-051, BR-BIL-052, BR-BIL-053, BR-BIL-054, BR-BIL-055, BR-BIL-056, BR-BIL-057, BR-BIL-058, BR-BIL-059, BR-BIL-060, BR-BIL-061, BR-BIL-062, BR-BIL-005, BR-BIL-015, BR-BIL-029, BR-BIL-034, BR-BIL-036, BR-BIL-037, BR-BIL-040, BR-BIL-004, BR-BIL-011, BR-CUS-055]
stories: [US-BIL-001, US-BIL-002, US-BIL-003, US-BIL-004, US-BIL-005, US-BIL-006, US-BIL-029]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The bill run the PO described on 2026-08-11, end to end, as five phases
over the six S31 wizard steps. J2 is the money spine and J16 is the hold path;
this is the RUN itself — where the machine works in the background, where a
clerk reviews, and what is recorded at each point.

Three of its steps could not have been written before that ruling, because the
epic did not say them: the calculation is a **background batch** (step 4), the
**breaks** are shown the moment it finishes with retry-now or mark-for-later
(step 5), and the release gate is a **consolidated summary carrying consumption
plus five separately-recorded confirmations** (step 6) rather than one "confirm".
⚠ That gate summary was specified here as FROZEN; the PO reversed that on
2026-08-11 (option B — *"recalculate live"*). The `bill_run_releases` row is
still written once and never rewritten (hard rule 4); the SCREEN recalculates.
Steps 6 and 9 below assert the two separately, which is the point.
The other three steps are the already-signed wizard, reconciled onto the phases
rather than replaced.

**What this journey is really proving:** that there are **two review points and
one authorisation**. Phase 1 reviews the inputs before anything is calculated;
phases 3–4 review the outputs before anything is issued. A calculated run has
still billed nobody — every assertion below about phase 2 is an assertion that
nothing money-bearing exists yet.

**Fixture.** Tenant brazos-bend · run **07-A**, cycle 07-A, period **Jul 1–31,
2026**, bill date Aug 1 → due Aug 22 (due-days 21) · **1,124 accounts** ·
ACC-1042 = WE-1 (current **$247.87**, prior 45.00, total due **$292.87**) ·
ACC-1077 Vacation hold from Jul 16 = WE-12 (**$105.36**) · ACC-1602 Suspended ·
ACC-1520 moved in Jul 12, no prior read · ACC-3020 at **312%** of trailing
average (guardrail 200%) · breaks ACC-1201 (stage 2, gas read missing),
ACC-1455 (stage 1, no plan in force), ACC-1710 (stage 6, template variable
unresolvable) · **68 accounts with no email address** · actors Priya Menon
(Billing Clerk, ran), Alex Reed (System Admin, sign-off). Aggregate figures —
late-fee candidate count, summary totals, consumption sums — are
**engine-computed** (00-e2e-design.md §5); no aggregate is typed into this file.

| # | Phase · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · queue · record · audit) | Rule |
|---|---|---|---|---|
| 1 | **1 PREPARE** · Priya starts run 07-A (S31 step 1), scope = all services | ONE `bill_runs` row, status = phase 1, period Jul 1–31, scope recorded even when it is "all of them"; `idempotency_key` set | A second identical (tenant, cycle, period) is REFUSED with who/when/link — no second row. Closing the wizard and re-opening from S30 returns to the same run at the phase its status names; nothing is lost and nothing is duplicated | BR-BIL-005 · **BR-BIL-050** |
| 2 | **1 PREPARE** · step 2 "Check what we found" — the six tabs, plus the base-only cohort and the no-read account | Nothing written. Stages 1–5 run as PREVIEW with stage 6 not run; consumption shown per service **with its explicit unit** | ACC-1077 + ACC-1602 appear as the base-only cohort with a count and **no pre-committed default**. ACC-1520 is NOT under Missing reads and gets no estimated read — it prices at the plan's configured minimum for its category, prorated on calendar days, no usage line (the PO's own example shape: move-in on the 12th of a 30-day month = **19 of 30 days**). Zero `invoices` rows exist | **BR-BIL-061** · **BR-BIL-062** · BR-BIL-039 |
| 3 | **1 PREPARE** · step 3 decisions — Priya selects the whole late-fee candidate set and applies in ONE click; opts the base-only cohort IN; disposes ACC-1201's missing gas read as *hold* | One `bill_run_decisions` row **per account** — case `late_fee`/`apply`, `base_only_billing`/`include`, `missing_read`/`hold` — each with actor and time; the rows from one click share ONE `bulk_action_id`; ACC-1201 also writes a `bill_run_exclusions` row | The confirm dialog showed selection count and Σ fee **before** the click. Bulk **waive** is refused — a first-time waiver is per-case and manual. A later change of mind APPENDS a superseding row; the original is never updated or deleted. Phase 1 cannot end with an unresolved case row | **BR-BIL-060** · BR-BIL-003 · BR-BIL-015 |
| 4 | **2 CALCULATE** · Priya continues — and closes the browser | The run is SUBMITTED as a background batch. Per account, stages **1–6**; stage 7 is not reached. Output = DRAFT `invoices` + `invoice_lines` | The clerk is not held: the batch runs on, `bill_runs.status` reports progress, re-opening shows the same run. **Nothing money-bearing exists when it ends** — `invoice_no` NULL, `gl_account_id` NULL, `issued_at` NULL, **zero** journal lines, **zero** delivery rows. Killing the batch at 400 of 1,124 and resuming keeps the 400, completes the 724, and totals match a clean run to the digit | **BR-BIL-051** · **BR-BIL-052** · BR-BIL-004 · BR-BIL-037 |
| 5 | **3 BREAKS** · the batch finishes; 3 accounts produced no draft; ACC-1201's read is corrected and retried, the other two are marked for later | Shown BEFORE the totals: account · **failing stage by name** · staff-readable reason. Retry re-runs stages 1–6 for ACC-1201 alone → it joins the draft set. ACC-1455 + ACC-1710 → two `bill_run_exclusions` rows | No partial invoice exists for any broken account, ever. The other drafts are untouched by any one failure. The run proceeds with **1,122 drafts** — the clean bills go on, the rest wait (a partial run is the normal case). ACC-3020's 312% draft **exists** and is listed here as a post-calculation exception with required actions — it never stopped the batch | **BR-BIL-053** · **BR-BIL-055** · **BR-BIL-054** · BR-BIL-040 |
| 6 | **4 SUMMARY + GATE** · step 4 totals → step 5 confirm; Alex signs off | ONE `bill_run_releases` row: `summary` jsonb + `account_count` · `bill_count` · `total_amount` + `currency`, and the four confirmation booleans with `confirmed_by` + `confirmed_at`; `released_at` NULL | The panel carries **accounts · bills · consumption per service each with its unit · amount with currency · category breakdowns** — every figure tying to the draft set as it stands when the panel is drawn, consumption summed from the same measured quantities step 2 showed (never re-measured, never summed across different units). **The panel is COMPUTED, not read back from the release row** (PO 2026-08-11, option B — step 9 is where that bites). The email confirmation is shown against its coverage (**68 of 1,122 have no address**) and those 68 do NOT block release. Releasing with any of the five confirmations untaken is REFUSED, naming it | **BR-BIL-056** · **BR-BIL-058** · **BR-BIL-059** · BR-BIL-036 |
| 7 | **5 RELEASE** · confirm → Priya is returned to S30 | Issue + downstream jobs run as BACKGROUND batches: numbers minted, due dates set, invoices + lines frozen, per-line GL stamped, template + version pinned, documents rendered and stored, print batch and delivery rows queued, the balanced posting handoff emitted; `released_at` stamped at the end | ACC-1042 issues at current **247.87** / total due **292.87** with its 15 immutable lines; ACC-1077 at **105.36**. Billing writes **no** journal lines — stage 7 emits and the posting service is the sole writer. UPDATE/DELETE on an issued invoice or line is refused. A crash after the gate leaves `released_at` NULL — a resume continues the jobs and does **not** ask for authorisation twice, and nothing issues twice | **BR-BIL-051** · BR-BIL-004/010/011/022/024/026 |
| 8 | **the tail** · ACC-1455 and ACC-1710 clear and catch up | Queue rows carry the break's failing stage and reason and are marked **phase-3 origin** — distinguishable from a phase-1 hold like ACC-1201's. A catch-up SUB-RUN, parent-linked, scope-keyed idempotency, same period | Continues into **J16** from its step 4. The run's own status reads **completed**, not failed: 1,122 issued + 2 queued is a run that worked, and nothing about the 2 distorts the issued totals | **BR-BIL-055** · BR-BIL-015 · BR-BIL-034 |
| 9 | **THE RECORD IS FIXED, THE SCREEN IS LIVE** — two answers to two questions, and neither is a bug | The release record is written once and **never updated or deleted**; the decision trail is append-only. The summary SCREEN holds no state — it is a query over the run's current bill set | Two months later a bill in run 07-A is **voided**. **(a)** Re-opening the run from S30 shows the panel **recalculated**: the voided bill has left the count and the amount (PO ruling 2026-08-11, option B — shown as *"You approve 480 bills, $52,847.19; two bills are voided next week"*, and the screen must now move). **(b)** The `bill_run_releases` row is **byte-for-byte what it was at confirm** — same `bill_count`, same `total_amount`, same confirmations, no UPDATE, no DELETE (hard rule 4). After this ruling that row is the ONLY place *"what did I authorise?"* is answerable, so it is load-bearing evidence, not a stale cache. Every decision stays answerable in both directions: what this account's row says, and whether it was one of a thousand (`bulk_action_id`). Issue is unreachable without a recorded release for the run and scope. ⚠ **AMENDED 2026-08-11 — it is ruled now.** This step used to say a corrected bill was outside the assertion because *"whether its rebill joins the recalculated set is unruled"*. The PO closed OQ-111: *"A Replacement counts (panel = what these customers owe now)"* (BR-BIL-064). So the panel must show a corrected bill at its REPLACEMENT's figure — **$104.20** where the run issued **$117.01** — and a rebill carrying this run's `bill_run` COUNTS. **The chain has no column** (`invoices.corrects_invoice_id`, OQ-120), so `summary_for` REFUSES the whole panel for a run holding a corrected bill rather than showing $117.01 (a figure nobody owes) or $0.00 (dropping it like a void). This step's (a) assertion therefore stands for a run whose bills carry no correction; a run that does carry one asserts the refusal and names the column | **BR-BIL-056** · **BR-BIL-058** · **BR-BIL-060** · hard rule 4 |

**HOW STEPS 6 AND 7 ARE ACTUALLY DRIVEN (added 2026-08-15, DEF-116) — TWO CALLS, AND A LANE CODING AGAINST THIS JOURNEY NEEDS BOTH.** Step 6 is `POST /billing/runs/{id}/release`, carrying `{confirmations:{compliance, email_mandate, sms_mandate, autopay_mandate, final}, confirmed_at}`; it writes the one `bill_run_releases` row this table's step 6 names, leaves `released_at` NULL, and **bills nothing**. Step 7 is `POST /billing/runs/{id}/issue`, carrying `{issued_at}` (and optionally `released_at`, `invoice_ids`, `dispatch_not_before`); it issues the remaining drafts and stamps `released_at` at the end. **Both event times are the CALLER's and must carry an offset** — the server reads no clock in a money path (BR-TEN-043, gate G6) and refuses a naive timestamp. **The split is what makes step 7's crash-and-resume real:** a process that dies between them leaves the authorised-but-unreleased row this journey's step 6 describes, and a resume continues from it rather than asking Alex to sign again. **Both are idempotent** — a repeated Confirm returns the authorisation that exists, a repeated Send returns the release already stamped, and no bill is issued twice. ⚠ **STEP 7 IS NOT A BACKGROUND BATCH ON THIS DEPLOYMENT.** The row above says Priya is returned to S30 while the work runs on; there is no worker (TD-17), so the issue pass runs INLINE and the route answers 201 with the finished result. ⚠ **AND THERE WAS A THIRD CALL NOBODY HAD NAMED, ADDED 2026-08-16: `POST /billing/runs/{id}/calculate` — step 4 above.** With release and issue both mounted the run still billed nobody, because nothing in the product ever called `runs.calculate_run` or `decisions.apply_decisions`: every run reached the gate with zero drafts and the gate refused, correctly — *"run … has no bills to release … an authorisation of nothing would be a signature against a blank page"*. Both engines had shipped on 2026-08-11 with tests and no production caller. So the wizard's step 4 now carries a **Work out the bills** control, and the run is: create → decide → **calculate** → gate → send. **DEF-123 is CLOSED the same day** — provisioning seeds every tenant its fallback bill template, so the pin BR-BIL-026 makes non-optional resolves. **Measured in a booted browser on 2026-08-16:** a clerk signs in, starts a run, answers the missing-read case with *bill without that service*, presses Work out the bills, takes the five confirmations and presses Send — and bill **BL-2608-000006, 70.90 USD**, is ISSUED, pinned to *Standard bill* version 1, with its balanced ledger entry posted (`07-frontend/e2e/DEF-116-123.spec.ts`).

**⚠ What is NOT runnable yet, and must not be read as covered.** Every step here
is a CONTRACT, not a passing test. The billing tables exist as of 2026-08-11
(`bill_runs` · `bill_run_exclusions` · `bill_run_decisions` · `bill_run_releases`
· `invoices` · `invoice_lines`, with immutability proved on a live Postgres),
and stages 1, 2 and 6 exist. **Phases 1 and 2 landed later the same day** and
this paragraph is updated rather than left standing: `apps/billing/runs.py` now
carries `prepare_run` (scope → gather → ready/blocked/decisions, writing
nothing) and `calculate_account` (stages 1 → 2 → 3-5 → 6 for one account,
leaving a draft), proved on real rows across four modules in
`tests/test_us_bil_001_prepare.py`. **Still absent: phases 3, 4 and 5, the
per-account loop that would call `calculate_account` over a run, the reading-back
of recorded decisions (`gather.with_readings` has no caller, so a clerk's
estimate does not yet reach a bill), the S31 wizard, and any API.** Steps 4, 5
and 7 additionally depend on a job runner the project
does not have — `celery[redis]` is a declared dependency with zero `tasks.py`,
jobs run in-process under `JOBS_EAGER=true` (TD-17, still open), so "background"
today means "not yet built", not "built and asynchronous". ⚠ **AMENDED 2026-08-11: Step 7's ledger assertions are LIVE.** This read *"Step 7's ledger
assertions stay stubbed at the boundary until W5"*. They are not stubbed — issue emits the
BR-BIL-011 handoff through `apps/billing/posting_seam.py` inside its own transaction, so a
released run writes one balanced journal entry per bill (DR AR `invoices.total` / CR one
bucket per stamped GL) and a bill the books refuse does not issue at all. What is still
"background" only in name is the BATCH, above. This file is written now so
the run is BUILT against it rather than discovering it afterwards.

**⚠ One thing this journey asserts that is not yet ruled.** Step 6's *category
breakdowns* are **BR-BIL-057, PROPOSED** — the PO said *"and various
categories"* and did not enumerate them. The axes asserted here (service ·
consumer category · bill type · status class · delivery channel · exception
state) are DERIVED from what the run already knows. A run built before that
ruling implements the axes it can derive and stubs the axis SET; do not read
step 6 as fixing the list.

**⚠ One thing the 2026-08-11 option-B ruling did NOT settle.** The PO's worked
example was a **void** — *"two bills are voided next week"* — so step 9 asserts
only that case. A **correction** produces a credit note plus a rebill, and the
rebill is a NEW invoice (EP-BIL-04) that may not carry this run's `bill_run`.
Whether it joins the recalculated set, or whether only the corrected original's
current value counts, was never put to the PO. Do not read step 9 as answering
it, and do not let an implementation pick an answer quietly (BR-BIL-056).

**⚠ One rule this journey depends on that another module still records as
open.** Step 2's no-prior-read pricing (BR-BIL-062) closes OQ-102 on the
billing side, but **BR-MET-064 in metering still records the source of the
first-bill category average as OPEN** and is owed a restatement by that lane.
Named here rather than left to look settled (hard-won law 1).
