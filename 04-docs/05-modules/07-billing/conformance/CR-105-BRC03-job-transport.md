# CR-105-BRC03 · the bill run's job transport — resume, and refuse rather than run inline

**Lane:** job transport (`apps/billing/run_jobs.py`, `core/jobs.py`)
**Date:** 2026-09-14 · **Version:** 2.266.0
**Authority:** `05-prototype/04 Billing, As Built.pdf` **p050** — 14,363,163 bytes,
sha256 `137a2a48c0398c39897f49aafa0bbb9c44ff21d6258eed78cd7558e6cc200971`, confirmed
independently by this lane. Rendered at scale 2.0 and read **as an image** (B14 rule 42).

---

## 0 · WHAT THE PAGE ACTUALLY SAYS, VERBATIM

p050 is the pre-bill **Check** screen. Its last panel is headed **"What it must also do, but
cannot be drawn"** and reads, in full:

> Refuse rather than run inline **above the bar** — a deployment with no worker runs the check
> inline today and the request dies long before its own *ran inline* answer can be read. And
> **resume without re-walking**: a worker killed at 9,000 of 10,000 pays **22 minutes** again
> unless the checkpoint is used.

Two further figures on the same page are load-bearing and are quoted here because the build
rests on them:

> Today the clerk presses Prepare and **waits on one request**. Measured on real PostgreSQL, a
> run costs **137 ms per account** — so 25,000 accounts is **about 57 minutes**, and **the
> request wall is about 60 seconds**. There is no version of this where the clerk waits.

### ⚠ TWO DIFFERENCES FROM THE COORDINATOR'S BRIEF, REPORTED AS ASKED

1. **The brief dropped the words "above the bar".** It quoted the refusal sentence as *"a
   deployment with no worker runs the check inline today…"* and stopped there. The drawing makes
   the refusal **conditional on size**, which is the whole difference between this build and a
   flat refusal that would break every `JOBS_EAGER` deployment in the product.
2. **The brief said "At 137 ms per account a 25,000-account run is about 57 minutes".** That is
   p050's own arithmetic and it is correct against p050's own figure — but the figure in the
   code is **0.17 s**, not 0.137 s, because `DEF-2717` re-took the measurement with row-level
   security ENFORCED (p050's was taken with RLS bypassed). At 0.17 s the same run is **71
   minutes**. The bar below is computed from 0.17.

---

## 1 · ELEMENT LIST — the two requirements, and what was found for each

| # | p050 requires | Found on the branch at `cab896fa` | Verdict | Built |
|---|---|---|---|---|
| 1 | The progress a pass reports is PERSISTED | `core.jobs.record_progress` writes `checkpoint` to the record; `JobStore.save` writes it to the `jobs.checkpoint` column | **already built** | — |
| 2 | A cursor a resumed pass can skip on | `apps/billing/run_resume.py`: cursor + write, both required | **already built** | — |
| 3 | `calculate_run` accepts `already_done` and reports `on_progress(done,total,stage)` | present, and `run_jobs._progress_reporter(cursor=True)` writes the cursor | **already built** | — |
| 4 | A re-delivered job STARTS from that checkpoint | **`core.jobs.start()` refuses a `running` record, and a killed worker leaves exactly that** | **BROKEN — `DEF-BIL-5284`** | `core.jobs.reclaim` + `core.jobs.resume` |
| 5 | The transport calls it | `apps/tenancy/tasks.run_pending_job` called `run_pending`, which refused | **BROKEN** | one line, + the test that fails if it changes back |
| 6 | A redelivery proves the previous attempt is dead | no `visibility_timeout` declared; kombu's Redis default 3,600 s < the 8,520 s hard limit | **BROKEN — `DEF-BIL-5285`** | `CELERY_BROKER_TRANSPORT_OPTIONS` |
| 7 | `JOBS_REQUIRE_LIVE_WORKER` / `dispatch_is_ready` exists | `core.jobs.dispatch_is_ready`, `run_jobs.would_run()` | **already built** | — |
| 8 | It is wired on calculate | wired at `api.py:1242` — and on `False` it **logs a line and runs the pass inline anyway** | **wired, wrong behaviour** | refuse above the bar |
| 9 | It is wired on findings (the screen p050 draws) | same, `api.py:745` | **wired, wrong behaviour** | refuse above the bar |
| 10 | A clean refusal the clerk can READ | one existed for the size ceiling (`billing.run.tooLarge`); none for this | **not built** | `billing.run.noWorker` ×11 |

**Tie-out: ten elements · four already built and correct · two wired with the wrong behaviour ·
four absent. Six built by this lane, four left exactly as found.**

---

## 2 · THE ONE HOP, AND WHY EVERY EXISTING CHECK PASSED OVER IT

`apps/billing/run_resume.py` is careful, complete work. Its cursor-AND-write predicate is right.
Its checkpoint is persisted in a real column. `core.jobs.start` allows `failed → running` and
says *"checkpoint SURVIVES"*. `CELERY_TASK_ACKS_LATE` is on so a dead worker's message is
re-delivered. **Nothing in the product could reach any of it**, because:

* a worker killed by `SIGKILL` writes **nothing** — `run_job` catches `Exception`, and a process
  that dies raises none — so the record is left saying `running`;
* `start()` refuses a `running` record;
* so the re-delivery raised `JobsError: job … is running — cannot start (resume is
  failed→running)`, and the run stayed `running` **for ever**.

Not *slow*. **Never finished.**

**Why it was invisible, and it is two shapes CLAUDE.md already names:**

* **Law 7, *looking at the wrong thing*.** `tests/test_cr051_run_scale.py` proves the resume with
  a job record it builds itself — `a_job_record()`, a plain dict whose `id` is the BILL RUN's
  primary key, never saved to `jobs`, never passed through a status transition. Ten green cases,
  every one skipping the hop that refused.
* **Law 7, *a check that cannot fail*.** tc11 calls `10-scripts/cr051_kill_and_resume.py` *"the
  real kill proof"* and checks it by **grepping the file for four substrings**. The script itself
  reached the checkpoint only by hand-writing `core_jobs.fail(job_id, "worker killed (SIGKILL)")`
  first — supplying the missing hop itself — and it had additionally rotted into being unable to
  run at all (`DEF-BIL-5286`: its child called `core_jobs.run_job`, which LOADS the record before
  entering tenant context, so under RLS it died with *"unknown job"* every time). A guard that
  reads a script instead of running it cannot see either fault.

---

## 3 · THE BAR — 300 ACCOUNTS, RECOMPUTED RATHER THAN COPIED

    60 s request wall ÷ 0.17 s per account = 352 accounts
    bar = 300  →  51 s of billing, ~9 s for everything else a request does

`run_jobs.INLINE_ACCOUNT_BAR_DEFAULT = 300`, declared as `BILLING_INLINE_ACCOUNT_BAR` in
`config/settings/base.py` (the `DEF-2806` lesson: a name no settings module exposes is an
override silently ignored), `0` switches it off, and tc5 **recomputes** `bar × 0.17 < 60` so
moving either input without moving the bar goes RED.

**It is not a decision about whether work goes to a worker.** `run_jobs.py`'s standing reason for
having no row bar — *"there is no equivalent figure for a bill run anywhere in this repository"* —
expired when CR-051 task 21 measured one. This is the narrower question of what to do when the
caller asked for a worker and there is not one. **Below the bar the inline fallback is unchanged**,
which tc7 exists to hold.

Refusal copy, `billing.run.noWorker`, English: **"Billing cannot run right now. Nothing has
changed."** Two sentences of five and three words — B14 rule 33 for a consequence — no rule id,
no internal code, no rationale (rule 32). Written in all eleven catalogues in their own language
(rule 35); each file gained **1 insertion and 0 deletions**, verified as arithmetic.

---

## 4 · PROOF

**RED first, in the harness that runs them.** Before any production line was written, the seven
cases then in `tests/test_cr105_run_transport.py` ran **6 failed / 1 passed** — and the one that
passed is tc7, the case asserting the inline fallback below the bar is unchanged, which is
exactly the behaviour the fix must not touch. The failing sentence for the resume was

    JobsError: job 019… is running — cannot start (resume is failed→running)

and for the refusal it was `201` with `background: false` plus the server log line
*"calculate for run … asked for background and fell back to INLINE"*.

**That RED is kept rather than described.** tc9 asserts `run_pending` alone STILL refuses an
abandoned record — the widening deliberately lives in `resume`, not in the kernel's ordinary
entry point — and that `apps/tenancy/tasks.py`'s body still names `core_jobs.resume`, so the day
somebody changes it back the checkpoint's unreachability is a failing test rather than a silent
fortnight.

**After:** `tests/test_cr105_run_transport.py` **9 passed**. `ruff` clean and `black` clean on all
six touched files (`config/settings/base.py` was already black-dirty at the tip for unrelated
reasons and was NOT reformatted — that would have been another lane's diff).

**Neighbours, dated rather than asserted (law 7 habit 1).** Eight suites — the two CR-051 run
suites, both BE-07 job suites, the Celery transport suite, the time-limit suite, the queue suite
and `test_def2720` — run **13 failed / 92 passed / 2 skipped** in this tree, and **the same 13
names, 13 failed / 92 passed / 2 skipped, at the pinned tip `cab896fa` in a private worktree with
neither this lane's work nor the sibling's in it.** So every one of the thirteen is pre-existing
on the branch and none is this lane's. They are fixture-count failures (`done: 1, total: 1` where
the case expects 2) plus three queue cases that pass in isolation and fail only in that file
order — cross-file pollution, also pre-existing.

⚠ **The three queue cases are worth naming because the first reading of them was wrong.** Run as
their own file they pass; run after the others they fail. A lane that had only run the eight
together would have reported three regressions it did not cause, which is precisely what law 7's
*date it before you call it pre-existing* is for — and the thing that settled it was running the
identical command at the tip, not reasoning about it.

**Gate baseline recorded before starting:** `run_gates.py` 72 PASS / 50 FAIL / 3 SKIP at
`447b359a`, saved as a set so the after-run is a comparison and not an impression.

**Gates, before and after, as a set rather than an impression.** Baseline at `447b359a`:
**72 PASS / 50 FAIL / 3 SKIP**. After everything landed: **72 PASS / 51 FAIL / 3 SKIP** over
126 gates (one more gate exists than at the baseline — `G125`, a sibling's, which now passes).
Exactly one gate is newly failing and it is not this lane's: **`G54 image-build`**, a `tsc` error
(`Property 'currency' is missing … in type 'InvoiceSummary'`) in
`src/features/billing/CR105DocumentGroups.dom.test.tsx` — an UNTRACKED file created in the shared
tree at 14:17 by another lane. This lane changed no `.ts` or `.tsx` file.

**Two gates went red during the work and both were this lane's own doing.** They are recorded
because the way each was found is worth more than the fix:
* **`G35 version-lockstep`** — the changelog entry was written under `## [Unreleased]` with
  `(2.266.0)` inline, and the gate reads HEADINGS. Moved to `## [2.266.0] - 2026-09-14`. Green.
* **`G30 defect-register` — `DUPLICATE ID DEF-BIL-5283 appears 2 times`** (`DEF-BIL-5289`). Not
  this lane's id: the duplicate arrived because the re-derivation computes *"my append"* as the
  working copy minus the bytes at my base, which is a statement about **POSITION, not
  authorship** — so a sibling's row appended to the same shared file inside that window was
  replayed onto a tip that already had it. Both rows were asserted byte-identical before either
  was touched; the later one is removed and the register rebuilt **by id**. Green.

⚠ **THE SAME MECHANISM BIT THE CATALOGUES AN HOUR EARLIER AND IS WORTH THE SPACE
(`DEF-BIL-5288`).** The post-push subtraction check on the eleven locale files read **40
insertions / 1 deletion each** where this lane had made **1 / 0** — a sibling had edited the same
working-tree files between this lane's edit and its push, and a pathspec commit takes the whole
file (law 11, mechanism five). Nothing was lost: 39 bill-detail keys and one reworded
`summaryHint` are on the branch earlier than their author intended, and the reworded key still
resolves at its call site, checked on the branch. **It is not reverted** — reverting would now
destroy a sibling's work to tidy a record — and the owning lane is told rather than surprised.
**Both collisions were caught by reading `git diff --numstat` AS ARITHMETIC against a remembered
+1/−0, and by nothing else.**

---

## 5 · WHAT THIS LANE DID NOT DO, STATED RATHER THAN IMPLIED

* **A `failed` job is still re-delivered by nothing** (`DEF-BIL-5287`). A worker KILLED mid-pass
  now resumes; a soft time limit or a raised body leaves a `failed` record with a usable
  checkpoint and no retry policy, no reaper, and no `manage.py run_pending_jobs` — a command
  `apps/tenancy/tasks.py` has named in a docstring and in an operator-facing error message since
  2026-08-19 and which **has never existed**. How many times a money job may re-attempt itself is
  a product decision, not a lane's.
* **The kill proof still cannot complete** (`DEF-BIL-5286`). Its "unknown job" fault is fixed and
  it now exercises the production path, but against the seeded dev database the pass finds no
  ready accounts and it never reaches its kill. Fixing that is billing fixture work in files this
  lane does not own.
* **`REPRICE_JOB` — reported to the coordinator, not edited.** A sibling lane added
  `billing.run.reprice` to `run_jobs.py` while this lane was in it, and the two halves land
  differently, so the claim is stated precisely rather than sweepingly:
  * **The resume half is a DELIBERATE and argued absence, not a gap.** `run_reprice_job`'s own
    docstring says why — a re-price covers the accounts one decision touched, re-walking it is
    seconds, and *"a checkpoint would be machinery guarding a cost nobody would notice"* — and it
    names the hook to use if that ever stops being true. **Nothing to do.**
  * **The worker half does have this record's fault.** `api.py:892` asks `would_run()` and, on a
    `False`, re-prices **inline** with no bar — the same shape `run_calculate` had. At a decision
    over a large cohort that is the same dead request. **It is one call to
    `run_jobs.refuse_if_no_worker(run, reason=…)` on that branch**, and it is the sibling's line
    to add, not this lane's to reach into. Reported to the coordinator: two lanes in one file is
    the mechanism this project has been bitten by twice.
* **`core.jobs.run_job` loads the record before it enters tenant context.** Every production
  caller happens to have context already (`run_eager` is mid-request; `tasks.run_pending_job`
  wraps it), so this bites only a direct caller — which is exactly what killed the kill proof.
  Noted inside `DEF-BIL-5286` rather than changed, because moving the load is a kernel change
  with five modules downstream of it.
* **p050's `137 ms` is not corrected in the drawing.** The code's figure is the RLS-enforced 0.17
  and the difference is stated here; amending a PO document is not a lane's act.

---

## 6 · FILES

| File | What changed |
|---|---|
| `06-backend/core/jobs.py` | `reclaim` (running → failed, checkpoint kept) · `resume` (the delivery entry point) · `RECLAIMED_ERROR_TEXT` |
| `06-backend/apps/billing/run_jobs.py` | `REQUEST_WALL_SECONDS` · `INLINE_ACCOUNT_BAR_DEFAULT` · `inline_account_bar()` · `refuse_if_no_worker()` · `__all__` |
| `06-backend/apps/billing/api.py` | the refusal on the `not ready` branch of `run_calculate` and `run_findings` |
| `06-backend/apps/tenancy/tasks.py` | the worker task calls `core_jobs.resume`, not `run_pending` |
| `06-backend/config/settings/base.py` | `BILLING_INLINE_ACCOUNT_BAR` · `CELERY_BROKER_TRANSPORT_OPTIONS.visibility_timeout` |
| `07-frontend/src/i18n/locales/*.json` | `billing.run.noWorker`, eleven files, +1/−0 each |
| `10-scripts/cr051_kill_and_resume.py` | the child is a real worker and the resume is the real `resume` |
| `06-backend/tests/test_cr105_run_transport.py` | new — nine cases, every resume case through the Celery task |
