# J73 — The bulk bill run when something breaks, and at the size of the utility (F1–F5 · S1–S4)

---
id: J73
tier: 2
checks: [F1, F2, F3, F4, F5, S1, S2, S3, S4]
criteria: 04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md §3 (breakdown) and §4 (scale)
plan: 04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md E12 · B21 · B27 · B28
spec: 07-frontend/e2e/J73-bulk-run-breakdown-and-scale.spec.ts
seed: manage.py seed_j72_bulk_run [--send-failure] [--second-clerk] [--accounts N]
harness: 10-scripts/j73_bulk_run_harness.py
# PREPARED 2026-09-30. F1-F5 walked 2026-10-01 (2.417.0); S1-S4 measured 2026-10-01
# (2.418.6-2.423.0): S1 and S4 PASS, S2 and S3 FAIL - see the S1-S4 results section.
# S3 re-timed 2026-10-01 on 2.426.0 (batched Send, auto hand-back): PASS.
# S2 re-timed 2026-10-01 (2.428.0): every screen's own read < 2 s at 40,000; the cold page
# open still fails on two side reads (DEF-TEN-8731, DEF-MET-8732).
# S2 cold open timed 2026-10-01 (2.433.2, J73_COLD=1) at 40,008 sent: no worker lost (side reads
# 0.6 s / 1.2 s, run read 1.2-1.5 s); first data 4.3-7.9 s at 1440/1280 - still FAIL vs 2 s (DEF-BIL-8809).
# S2 cold open re-timed 2026-10-01 (2.436.1): reads start beside the run read; Not in this run 2.8-5.1 s,
# Sent total 3.9-7.6 s (was 5.2-6.3 / 6.1-8.0) - still FAIL vs 2 s on server time (DEF-BIL-8809 open).
# S2 cold open re-timed 2026-10-01 (2.437.2, server half): Not in this run 1.08-1.40 s, Sent total
# 1.02-1.59 s (old 2.55-4.46 / 3.60-5.94) - PASS vs 2 s on 3 workers (DEF-BIL-8809 closed).
---

**Intent.** The clerk's nine breakdown and scale checks, walked the way J72 walks the
others (J72 § *HOW THIS WALK IS ORGANISED*, PO 2026-09-30: *"your end ot end walk should
be around these cases"*). One spec test per check, named by its id, at **1440** and **1280**.
The results table always has **nine rows**; a check with no walk yet is **NOT RUN**, never
left out.

## The world — what the seed adds, each behind its own flag

Run after `migrate` → `seed_demo` → on PostgreSQL. Without a flag the command seeds exactly
the J72 world. Code: `06-backend/apps/tenancy/management/commands/_j73_scale.py`.

| Flag | For | What it seeds |
|---|---|---|
| `--send-failure` | F3 | `AC-2026-00002` (Omar Haddad, a clean account) pinned to **"Riverside draft layout (J73 F3)"**, a bill template with only a draft version. At Send the template chain refuses it (*"has no PUBLISHED version (BR-BIL-026)"*), caught per bill, so it is one break and every other bill goes. Nothing at Check or Sign off reads the override, so the clerk first meets it at Send. The override is an ORM write — no customers door assigns one (BR-BIL-025) — and the docstring says so. |
| `--second-clerk` | F4 | **Marcus Webb**, Billing Clerk, `marcus.webb.j73@brazosbendutilities.com`, password the harness's own — made through `identity.services.add_user` and the forced first-sign-in `change_password`, so he can sign in. |
| `--accounts N` | S1–S4 | N more accounts in the Riverside cycle, prefix `J73S-`: residential, four-service plan *Residential Four-Service (Riverside J73)* — **water** on 1 meter (3 in 4) or 2 meters (1 in 4), **electric** on 1 meter, **trash** with 1–2 96-gallon carts at $15.00 a cart, **sewer** at 40% of water usage — reads on Jul 31, Aug 31 and Sep 30 with a varied spread (water 5–13 kgal, electric 450–750 kWh), 25 units per premises. **One account in ten** has a $45.00 payment posted Sep 15. Four templates go through the modules' services; the N clones are bulk inserts of the templates' rows, 1,000 accounts per batch, each batch its own transaction (a re-run tops up). Payments go through `payments.services.record_payment` one by one (hard rule 5 — only the ledger writes journal lines). |

**F2 has no seed flag, because the product offers no switch** (`DEF-BIL-8510`). The
harness takes Meter Reads down at the database: `j73_bulk_run_harness.py meter-reads down`
renames `routes`, so `metering.units_in_cycle` — the first seam a Check calls — raises as
it would if Meter Reads' storage were unreachable; `meter-reads up` restores it. It breaks
every route screen while down; use it only on a walk database.

**F1 is a harness, not a seed:** `j73_bulk_run_harness.py f1-worker-kill --kill-at N` starts
a private redis and a real Celery worker on the `billing` queue, enqueues the Check the
product's way, SIGKILLs the worker when progress passes N, records progress and saved rows,
starts a fresh worker, waits 20 s to see whether the broker re-delivers by itself, then
resumes the way the clerk's Resume does and records it again (including rows saved twice).

## Seed timings (PostgreSQL 16, 127.0.0.1:55433, shared machine at load ~8.5 on 4 CPUs, `nice -n 10`)

| World | Templates | Clones | Payments | Total |
|---|---|---|---|---|
| J72 base world (the fix below) | — | — | — | **13.2 s** |
| `--accounts 100` smoke | 0.2 s | 0.8 s | 10 in 1.4 s | **2.5 s** |
| `--accounts 10000` (`sbh_j73_10k`) | 5.4 s | **53.2 s** | 1,000 in **93.1 s** | **151.9 s** (wall 156 s) |
| `--accounts 40000` (`sbh_j73_40k`) | — | **33,000 cloned in 200.3 s**, then stopped by the coordinator (machine overloaded) | not reached | not finished — a re-run tops up from 33,000 |

Clones run at about 5.3–6.5 s per 1,000 accounts; payments at about 93 ms each, so 40,000
is expected near 4 minutes of clones plus 6 minutes of payments. Measured, not yet run to
the end.

**The base seed was broken on the branch tip and is fixed here (test data only):**
`one_time_send.send()` gained a required `confirmations` argument on 2026-09-30
(`7d75bd7d2`), and `seed_j72_bulk_run` died with a `TypeError` at unit 110's interim bill.
It now passes the five confirmations a clerk would tick.

**Smoke proof that the clones are billable:** a prepare pass over 40 `J73S-` accounts on
PostgreSQL returned **40 ready, 0 blocked, 0 decisions, 0 warnings**. It took **19.4 s**
(~0.48 s an account on the loaded machine). That is not the S1 figure — S1 is the whole
Check after B27/B28 — but at that rate a 10,000-account Check would be over an hour, which
is why S1 waits on B27/B28.

## Results — S1–S4 at 10,000 and 40,000 (2026-10-01, builds `2.418.6`–`2.423.0`, the S1–S4 scale lane)

Measured on PostgreSQL 16 (`127.0.0.1:55433`) as the RLS-enforced role `sbh_b27`, on real Celery workers.
World: `sbh_s14_40k` (B28's 40,015-account world plus a second utility, `perf-utility-1`, 199 accounts) and
`sbh_s14_10k` (10,015). Every timed run waited for a load average under 2 and records the load beside its
figure; the machine never stayed quiet, so **no figure here is a clean number — read each with its load**.
The full method and every figure: `04-docs/05-modules/07-billing/19-check-cost-measured.md` §10. Scripts:
`10-scripts/b28_parallel_check_proof.py` (S1), `10-scripts/j73_scale_proof.py` (S2 server, S3, S4),
`07-frontend/e2e/J73-s2-screen-timing.spec.ts` (S2 in Chromium at 1440, behind gunicorn 3 × 60 s as in
production). These supersede the four **S1–S4 NOT RUN** rows below.

| Check | Target | Measured | Load during | Result |
|---|---|---|---|---|
| **S1** Check time | ≤ 10 min at 10,000; ≤ 30 min at 40,000 | **70 s** at 10,015; **5.6 min** at 40,015 (4 slots, cap 2, `2.418.6`); 13.1 min on 2 slots, cap 1 (`2.423.0`); every account saved once | 3.1 / 3.5 median (max 3.7 / 4.0); 1.7 on 2 slots | **PASS** |
| **S2** three screens < 2 s, paged | each < 2 s; never all rows | **Cold open re-timed 2026-10-01 (2.437.2, `19-check-cost-measured.md` §15; `J73_SENT=1 J73_COLD=1`, new and old alternated on one server, every open started at load < 3):** Not in this run's first row **1.08–1.40 s** (old 2.55–4.46 s), the Sent card's total **1.02–1.59 s** (old 3.60–5.94 s), $7,371,531.12 due 10/22/2026 in every open — **PASS** on gunicorn 3 × 60 s. The run read no longer carries *Meter reads* (0.06 s, was 1.34 s), the page asks the summary's headline alone (`/totals` 0.11 s), Not in this run reads only the accounts the run did not bill (0.16 s, was 0.95 s) (`DEF-BIL-8809` closed). **Before that:** **Cold open re-timed 2026-10-01 (2.436.1, `19-check-cost-measured.md` §14; `J73_SENT=1 J73_COLD=1`, new and old alternated on one server, every open started at load < 3):** Not in this run's first row **2.8 / 5.1 s at 1440, 2.8 / 4.3 s at 1280** (old 5.9 / 6.3, 5.2 / 5.7); the Sent card's total **4.0 / 7.6 s, 3.9 / 4.9 s** (old 6.9 / 8.0, 6.1 / 7.0). The screen's reads now start beside the run read (0.84 s, was 3.37 s), and a sent run asks eight reads, not eleven (`DEF-BIL-8809`, page half). Still over 2 s on the server's time: `/summary` 3.1 s beside the other reads, the run read 1.45 s alone, first API call at 0.84 s. A tag's account list was not re-timed cold (a sent run's Check is locked; its read is unchanged). **Before that:** **Cold open timed 2026-10-01 (2.433.2, `19-check-cost-measured.md` §13; `J73_SENT=1 J73_COLD=1`, every open started at load < 3):** the sent 40,008-bill run's page, navigation → Not in this run's first row **4.6 / 7.9 s at 1440, 4.3 / 5.1 s at 1280**, → the Sent card's total 5.5–8.7 s. No web worker is lost: `/settings/services` 52–63 s → **0.6 s** (`DEF-TEN-8731`), `/cycles` 7.6–8.2 s → **1.2 s** (`DEF-MET-8732`), the run read 6.9–7.6 s → **1.2–1.5 s** (`DEF-BIL-8758`); still over 2 s because the eight screen reads start only after the run read, on three workers (`DEF-BIL-8809`). Sign off after Send reads the bills' stamps — $7,371,758.07 due, was `—` (`DEF-BIL-8727`). Sign off can no longer be re-entered on a sent run (the rail is locked), so the cold open times the Send screen. **Before that:** **Re-timed 2026-10-01 (2.428.0, `19-check-cost-measured.md` §12, load < 2):** server reads at 40,008 — Sign off 0.50 s (saved summary; 8 s when rebuilt in the request), `/summary` 1.0 s, a tag's list 0.03 s, Ready 0.26 s, Not in this run 0.91 s; at 10,008 (open run, sweep included) the tag's list 0.06 s. Browser at 10,008 (1440 / 1280): tag click → first row 0.26 / 0.16 s; Sign off 7.2 / 3.3 s and Not in this run 4.0 / 3.5 s from a COLD page open, held up by `/settings/services` (13.6 s, killed at 60 s at 40,000 — `DEF-TEN-8731`) and `/cycles` (2.8 s — `DEF-MET-8732`). Still FAIL on the cold open; the screens' own reads pass. **Was:** **Sign off never shows its figures**: `sign-off-summary` 250–396 s server-side, 500 in the browser after 66 s (worker killed at 60 s). A tag's account list **3.3 s** (click → first row; 3.1 s is the staleness sweep before every Check read). Not in this run **2.5 s** from a cold page load (read 0.6–1.2 s). Paged: every list caps a page at 1,000 when asked for 100,000 | 2.8–3.0 (opens started < 3) | **PASS** (2.437.2; was FAIL — `DEF-BIL-8694`, `8696`, `8697`, `8809`) |
| **S3** Send 40,000 with a failure part-way | issues with progress; resumes; no duplicate numbers | `2.426.0` on `sbh_send40k` (fresh J73 world): **11–12 bills a second, ~1 hour for 40,008** (was 1.9 a second, ~5.8 hours), batches of 500. Four kills, each handed back with no hand by the Send screen's poll in 16–19 s (or by pressing Send again), progress read from the bills (*9,916*, *11,616*, *20,318 of 40,008*), never 0. **40,008 of 40,008** issued, 0 numbers twice, 40,008 issue audits, every journal balanced ($7,371,531.12), second Send 200 `created: false`; audit 40,014 of 40,015 PASS. `DEF-BIL-8746` found and fixed, `DEF-BIL-8747` filed | 2.0 start; 2.1–5.4 median | **PASS** |
| **S4** another utility's run starts | B's run starts while A runs 40,000 | B's Check (199) running **≤ 1 s** after its press and **done in 4 s**, A at 5,000 of 40,015 keeping its 2 batches (4 slots) or 1 (2 slots) | 2.7 / 1.7 median | **PASS** |

**Count: 9 checks · 8 PASS · 1 FAIL · 0 NOT RUN** at 1440 (F1–F5 as below; S1, S3 and S4 pass, S2
fails; S3 re-timed on 2.426.0). S2's cold open was walked at 1440 and 1280 (2.433.2); S1, S3 and S4 are server-side and have no width.

**What was done to reach S3 that the product does not do, said plainly:** the deployment's per-run
ceiling (`BILLING_MAX_ACCOUNTS_PER_RUN`, 25,000) refuses a 40,008-bill Calculate and was set to 0; the
killed Send was handed back by calling `run_jobs.resume_job` (the Check's Resume path — the Send has no
door to it); and after a second deliberate kill the last 37,384 bills were sent with an experimental index
on `invoice_lines (tenant_id, id)` in this test database only, which took the per-line update from 68 ms to
2.1 ms (dropped afterwards). The correctness figures above do not depend on the index.

**Defects filed by this walk:** `DEF-BIL-8694` (the Check's reads sweep the whole run first), `8696` (Sign
off's summary per account), `8697` (`/summary` 11 s), `8708` (Send 1.9 bills/s — renumbered from a
colliding `8703`), `8710` (a killed Send does not resume), `8722` (the run audit counts a standing default
as an answer), `DEF-MET-8693` (a utility signing up on the 1st–9th gets a short sample set).

## Results — the nine checks (2026-10-01, build `2.417.0`, the final bulk-run lane)

Walked on PostgreSQL 16 (`127.0.0.1:55433`) on the lane's branch rebased on `d1d1fb29b`, the SPA
built from it. **F2 walks a fresh `--send-failure` world; F3 and F4 walk the same world after J72
has sent its September** — F3 needs a sent run to retry, F2 needs one that has not started.

| Check | 1440 | 1280 | What decided it |
|---|---|---|---|
| **F1** worker dies mid-Check | **PASS** (harness) | **PASS** (harness) | `j73_bulk_run_harness.py f1-worker-kill` on real Celery, 315 accounts: the worker is killed with 100 of 315 checked; **24.3 s** later the screen's own poll hands the job back to a worker, which carries on to 175 from its last saved account; no account is saved twice. The browser case stays skipped (it needs the harness's kill and start commands). |
| **F2** Meter Reads down | **PASS** | **PASS** | The test-only switch (`SBH_WALK_SWITCHES_DIR`, refused in production) takes Meter Reads down; the stop says what is down, that support fixes it, and the reference; *Try again* carries the same run on. |
| **F3** some bills fail at Send | **PASS** | **PASS** | *7 bills sent · 1 bill not sent*; See breaks lists AC-2026-00008 with *a service has no revenue account*; *Retry failed* retries only that bill and the sent count does not move. |
| **F4** two clerks on one run | **PASS** | **PASS** | Marcus opens Dana's run and reads *Also on this run: Dana Whitfield*; Dana sees Marcus on her next heartbeat. Two Sends at once issue each bill once — `tests/test_bbr_f4_two_sends_pg.py` on PostgreSQL. |
| **F5** something unexpected | PASS (by test) | PASS (by test) | `check_engine` `CHECK_FAILED` with a support reference; no browser way to cause it. |
| **S1–S4** | NOT RUN | NOT RUN | The 10,000 and 40,000 worlds are not timed on this build. **Superseded by the S1–S4 section above (2026-10-01).** |

**Count: 9 checks · 5 PASS · 0 FAIL · 4 NOT RUN** at each width.

**S1, server half, measured 2026-10-01 (B28, `2.418.4`, not a browser walk):** the whole Check at
**40,015 accounts** on PostgreSQL 16 with RLS enforced took **8.0 min** in one process (`2.417.0`) and
**9.1 min** as 81 batches of 500 on real Celery workers, two at a time (4 slots, the ruled cap) — both
inside S1's 30 minutes. The batched run gained nothing on this machine because other lanes held its four
cores; eight workers is estimated at ≈ 2–2.5 min. `10-scripts/b28_parallel_check_proof.py`,
`04-docs/05-modules/07-billing/19-check-cost-measured.md` §9. S1 stays NOT RUN until a browser walks it.

**Two spec faults found and fixed on the way (not product faults):** F3 began with
`onStep(page, "Send")`, which is always false on a sent run (the rail has no current step once Sent
is drawn) — it now waits for the Sent card; and the page it failed on already showed everything F3
asks for. F2 cannot pass on a world whose September is sent, so it is walked on a fresh world.

## Results — the nine checks (2026-09-30) — SUPERSEDED by the section above

No browser walk was run: the bulk-run lane is not merged and the coordinator closed the
machine to scale and Celery runs. Every row is NOT RUN in the browser at both widths; what
did run, and what it showed, is in the last column.

| Check | 1440 | 1280 | What decided it |
|---|---|---|---|
| **F1** worker dies mid-Check | NOT RUN | NOT RUN | Harness written (`f1-worker-kill`), not run — Celery runs closed. Found by reading: the clerk's **Resume runs the remaining Check inside the web request**, not on the worker (`DEF-BIL-8511`), and after a SIGKILL the broker re-delivers only after 8,820 s. At 9,000 accounts left that request is over an hour against a 60 s web timeout. "Nothing checked twice" is guaranteed by `uq_brac_once` (one saved row per run + account). |
| **F2** Meter Reads down | NOT RUN | NOT RUN | **Server half PASS** on PostgreSQL (115 accounts, harness `f2-probe`): with Meter Reads down, `POST …/check` → **503** `{module: meter_reads, who: support, support_ref: SBH-73FBC9D7}`; `GET …/check` carries the same stop; the run is kept; after `meter-reads up`, `POST …/check` → **200**, 115 accounts checked. Browser banner (`[data-check-stop]`) not walked — waits on the lane. No product switch exists (`DEF-BIL-8510`). |
| **F3** some bills fail at Send | NOT RUN | NOT RUN | Fixture seeded and smoke-proved (`--send-failure`, 100 accounts). Not walked: Send breaks and *Retry failed* on the redrawn Send step are not merged (J72 E9). |
| **F4** two clerks on one run | NOT RUN | NOT RUN | Second clerk seeded (`--second-clerk`). **Expected to FAIL when walked:** nothing records or shows who is working on a run and no build task builds it (`DEF-BIL-8512`). The second half (two Sends cannot both issue) has existing guards and is walked when Send lands. |
| **F5** something unexpected | NOT RUN | NOT RUN | Proved by test (`check_engine` records `CHECK_FAILED` with a support reference), as the acceptance file says; no browser way to cause it yet. |
| **S1** Check ≤ 10 min at 10,000; ≤ 30 min at 40,000 | NOT RUN | NOT RUN | 10,000-account world seeded (`sbh_j73_10k`); the pass not timed (runs closed; B27/B28 not merged). Harness: `s1-check-time`. |
| **S2** three screens < 2 s at 40,000 | NOT RUN | NOT RUN | 40,000 world not finished. Today's screen builds its tag list and Not in this run from `GET …/findings`, the whole prepare pass on a GET (`DEF-BIL-8216`), which cannot meet 2 s at any size near this; the paged saved-check reads exist server-side. Harness: `s2-screens`. |
| **S3** Send at scale | NOT RUN | NOT RUN | Waits on the 40,000 world, B28 and F1's resume fix (`DEF-BIL-8511`). |
| **S4** other utilities keep working | NOT RUN | NOT RUN | Waits on B28 (per-utility cap) and a second provisioned tenant (`10-scripts/cr051_provision_utilities.py`). |

**Count: 9 checks · 0 PASS · 0 FAIL · 9 NOT RUN** at each width (F2's server half passed).

## Defects filed by this preparation (filed before any fix; none fixed here — product code is another lane's)

- `DEF-BIL-8510` — no test-only switch takes Meter Reads down on a live stack (F2; harness workaround recorded).
- `DEF-BIL-8511` — Resume runs the rest of the Check inside the web request (F1, U3).
- `DEF-BIL-8512` — nothing shows the second clerk who is working on the run (F4).

## Seen, not filed

- On this branch tip the Check puts `unit_has_no_plan` and a disputed reading (`AC-2026-00004`,
  `00005`) under **decisions**, not **blocked** — J72's walk earlier the same day read *Blocked 2*.
  The Check lane is changing this code now; left for the accuracy walk to judge against the rules.
