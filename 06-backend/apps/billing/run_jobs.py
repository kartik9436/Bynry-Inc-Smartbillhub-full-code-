# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-002 (S31.2 findings) · US-BIL-004 (phase 2 calculate) ·
#           US-BIL-005 (phase 5 issue)   Screens: S31 steps 2, 4 and 6
# Contract: TD-17 (async = Celery on Redis; every job idempotent + resumable) ·
#           B12 r1 §3 (202 + job_id for EVERY async op; the client polls
#           /api/jobs/{id}) · NFR-4 (heavy jobs async, with progress) ·
#           NFR-16 (idempotency wherever money enters or leaves)
# Rules:    BR-BIL-051 (phase 2 and the release are BACKGROUND batches; the
#           clerk is not held at the screen and closing the browser loses
#           nothing) · BR-BIL-052 (per-account, restartable, resumable) ·
#           BR-BIL-053 (the break list) · BR-BIL-055 (a break never blocks the
#           run) · BR-BIL-005 (a run is idempotent on its key) · BR-TEN-043
#           (event time is an ARGUMENT — a worker reads no clock)
# Tests:    06-backend/tests/test_cr051_run_jobs_and_breaks.py
# Impacts:  apps/billing/apps.py (registers these three bodies) ·
#           apps/billing/api.py (the three routes that enqueue them) ·
#           core/jobs.py (the kernel this is the fifth caller of)
# ───────────────────────────────────────────────────────
"""CR-051 tasks 8, 9 and 10 — the bill run's three background verbs.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file carries the IDEMPOTENCY KEYS for
the three verbs that produce and issue bills, and idempotency keys are a
CLAUDE.md 🔒 path. AI-authored 2026-08-30 under the PO ruling of 2026-08-09; row
in 12-governance/09-human-review-ledger.md.

⚠ **THIS FILE IS NOT IN `10-scripts/gates/human_owned.txt` AND DELIBERATELY DID
NOT ADD ITSELF.** That file's own header makes changing the guarded set a
PROCESS EVENT — *"the guarded set must not drift with whoever is coding"* — and
records three occasions where a money file joined the CODE without joining the
LIST. So the markers and the ledger row are here, and whether the glob should be
added is a question for the Product Owner, raised in the ledger row rather than
answered by a lane.

WHAT THIS IS FOR, IN ONE SENTENCE. *"we dont want even 100 bills runing in
browser"* (PO, 2026-08-30). `POST /billing/runs/{id}/calculate` drafted every
ready account inside the request and `POST .../issue` issued every bill inside
the request; BR-BIL-051 has said since 2026-08-11 that neither should.

⚠ **BILLING IS THE FIFTH CALLER OF MACHINERY ALREADY IN DAILY USE — IT INVENTS
NOTHING.** Before this file, SEVEN job kinds were registered across four modules
(`apps/tenancy` ×2, `apps/metering` ×3 — all three stages of the premises import
— `apps/rating` ×1, `apps/audit` ×1) and billing registered NONE. The store is
registered by `apps.tenancy`, a `celery` service runs in `docker-compose.yml`,
and `JOBS_EAGER=False` in production. The pattern followed here is
`apps/metering/import_runs._defer` and `run_transform_job`, hop for hop.

── WHAT DECIDES WHETHER A VERB GOES TO A WORKER, AND WHY IT IS NOT A ROW BAR ──

The import decides by MEASURED row count: `async_row_bar(target, stage)`, set
from a real 50,000-row file (extract 6.8s · transform 77.9s · validate 50.8s ·
dry-run 1.9s · load 101.5s). **There is no equivalent figure for a bill run
anywhere in this repository** — CR-051 says so in as many words and makes
measuring it task 21, which is not this lane's. Picking a number here would be
inventing a figure with no evidence behind it, which is the one thing a lane may
not do.

**So the CALLER asks.** `background: true` on the body enqueues and answers 202;
absent, the verb runs inline exactly as it does today and every existing caller
— including the shipped S31 wizard, which is another lane's file — is byte-for-
byte unaffected. When task 21 publishes the figures, a measured default can
replace the flag without changing anything here except who sets it.

── AND IT NEVER QUEUES INTO A VOID (DEF-2487, CLAUDE.md law 3) ──

`core.jobs.dispatch_is_ready()` answers *"if I enqueue right now, will anything
actually RUN it?"*. On a deployment with no worker, a queued run would accept
the click, say *queued*, and bill nobody, for ever — strictly worse than the
visible failure it replaced.

The import REFUSES in that case. **This falls back to INLINE instead**, and the
difference is deliberate: an import that runs inline over 50,000 rows exceeds
the request timeout, so inline is not an option there; a bill run that runs
inline is exactly what this product did until today and the work IS DONE when
the response returns. Nothing is queued into the void either way. The caller can
tell which happened from the status code (202 vs 201) and from the `background`
member on the body, and the reason is stated on the response rather than
implied. Recorded in 12-governance/02-decision-log.md, 2026-08-30.

── IDEMPOTENCY: THREE LAYERS, AND ONLY THE MIDDLE ONE IS NEW ──

Hard rule 6 says a bill run is idempotent, and a job that runs twice must not
bill twice. Nothing here relies on a flag:

1. **The WRITE, which cannot rot.** Stage 6 REPLACES an account's draft for this
   run rather than adding a second (BR-BIL-023), so a re-calculated run
   converges on the same drafts. `issue.issue_run` selects the run's REMAINING
   DRAFTS, so a second issue pass finds nothing and issues nothing (US-BIL-005
   TC-6). `bill_run_breaks` carries `uq_bill_run_breaks_once`, so a second pass
   updates one row rather than appending a second.
2. **The SCOPE KEY (new, and the only thing this file adds).** Every enqueue
   carries `billing:<verb>:<run id>`, so a re-enqueue while a job with that
   scope is still active returns THE EXISTING RECORD — `core.jobs.enqueue`'s
   NFR-16 fold-in. A double-clicked *Work out the bills* is one job, not two
   passes racing over the same accounts. **This decides what a second CLICK
   does; layer 1 decides what a second PASS does, and neither substitutes for
   the other.**
2b. **The RESUME SKIP (CR-051 task 11, 2026-08-31).** A re-delivered CALCULATE
   task skips the accounts its own earlier attempt finished —
   `apps/billing/run_resume.py`. **It is not a fourth guarantee against
   double-billing and must never be read as one:** layer 1 is what makes a
   second pass harmless, and this only makes it unnecessary. If the predicate
   erred towards skipping too LITTLE the pass re-drafts and BR-BIL-023 absorbs
   it; all of its care is spent on never skipping an account nobody has billed.

3. **The RELEASE ROW.** Issue refuses without an authorised, unreleased release
   (BR-BIL-058), and `release_run` refuses a row already stamped `released_at`.
   A re-delivered Celery task on an already-released run therefore does nothing
   rather than issuing again — which matters more here than anywhere else in
   this file, because after issue there is no un-issuing (hard rule 4).

── NO CLOCK, IN A WORKER LEAST OF ALL (BR-TEN-043 · gate G6) ──

`issued_at` and `released_at` are the CALLER's instants, carried in the job
payload as ISO-8601 strings and parsed back here. A worker that read its own
clock would stamp an immutable financial record with the moment the queue got
round to it — which on a busy broker is a different day from the moment a person
pressed Send. There is no `timezone.now()` in this file and G6 forbids one.

── WHAT THE WORKER CARRIES INSTEAD OF A ROLE ──

`_JobActor` holds an id and no role, copied verbatim in intent from
`apps/metering/import_runs._JobActor` and the rating bulk-change job before it:
*"Role was checked at enqueue; the worker carries the actor id in the record,
never a role, so it can grant nothing."* The role gate ran on the request that
enqueued (`AdminOrClerk` on all three routes); rebuilding a role in the worker
would be a second, weaker place for that decision to live.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

from apps.billing import decisions, models, release, run_resume, runs, selectors
from apps.billing.exceptions import BillingRuleError
from core import jobs as core_jobs

logger = logging.getLogger("smartbillhub.billing")

# ── the three kinds ─────────────────────────────────────────────────────────
#: The `<module>.<subject>.<verb>` grammar `metering.import.transform` and
#: `rating.bulk_rate_update` already use. Registered in
#: `apps/billing/apps.py::BillingConfig.ready` — a kind with no registered
#: handler is a job that fails at the worker with "no handler registered", which
#: is why the registration sits three lines from nothing anyone can forget.
CALCULATE_JOB = "billing.run.calculate"
FINDINGS_JOB = "billing.run.findings"
ISSUE_JOB = "billing.run.issue"
#: `DEF-BIL-5271`(a) — phase 2 again, for the accounts ONE DECISION touched.
#: Its own kind rather than `CALCULATE_JOB` with a narrower payload, for one
#: reason that is about people rather than about code: `core_jobs` scope-keys on
#: the kind, so a re-price sharing the calculate kind would be de-duplicated
#: against a running full calculate and silently never happen — and the clerk
#: would be told their decision was applied. Different act, different key.
REPRICE_JOB = "billing.run.reprice"
#: Bulk bill run plan B17 / A3 (2026-09-30) — the redrawn Check step, run in a
#: worker with per-account progress, SAVING each account's result as it goes
#: (OQ-843 re-ruled, option C). Its own kind, not FINDINGS_JOB: that one
#: records counts only and serves the legacy S31.2 screen unchanged. A payload
#: naming `account_ids` is a RE-CHECK of those accounts (B15) and is scope-keyed
#: on them, so two clerks re-checking two cohorts are two jobs.
CHECK_JOB = "billing.run.check"
#: B28 (2026-10-01) — ONE BATCH of 500 of a Check, run beside the others under
#: the per-utility cap (`apps/billing/check_batches.py`). The Check job above
#: is their coordinator. On billing's own queue like every other kind here.
CHECK_BATCH_JOB = "billing.run.check_batch"
#: DEF-BIL-8726 (2026-10-01) — ONE BATCH of 500 of a Send, under the Send's
#: coordinator (`ISSUE_JOB`, `apps/billing/send_batches.py`). B28's shape for
#: issue, so no single task approaches the time limit at 40,000 bills.
ISSUE_BATCH_JOB = "billing.run.issue_batch"
RUN_JOBS = (
    CALCULATE_JOB,
    FINDINGS_JOB,
    ISSUE_JOB,
    REPRICE_JOB,
    CHECK_JOB,
    CHECK_BATCH_JOB,
    ISSUE_BATCH_JOB,
)

#: **BILLING'S OWN NAMED QUEUE — CR-051 task 29, PO ruling 2026-08-31.**
#:
#: Verbatim: *"we will ahve to create named worker for billing - eventually we
#: should able to scale these works on the fly itf required; but billing will
#: need its own named workers - otherwise it will slow down the system"*.
#:
#: ⚠ **THE NAME IS THE POINT, AND IT IS NOT AN OPTIMISATION.** CR-051 task 27
#: measured that concurrent bill runs never block each other in PostgreSQL —
#: zero ungranted locks across six waves — so a second queue creates no core and
#: makes no run faster. What it creates is an ADDRESS. Until this constant
#: existed, one unrouted queue carried bill runs, CSV exports, staged imports
#: and customers' outbound notices through the same two worker slots, so a CPU
#: cap on the worker capped the notices too and a second worker for billing was
#: a second worker for everything. Task 28 measured what a clerk in a DIFFERENT
#: utility feels while two runs execute: the accounts list p95 goes from
#: **605.8 ms to 2,868.9 ms**, one account's detail 44 → 228 ms, one bill
#: 18 → 97 ms. The remedy that fixes that is a CPU limit, and a CPU limit needs
#: something to be aimed at.
#:
#: ⚠ **A QUEUE NAME HERE IS HALF A QUEUE.** The other half is a worker consuming
#: it — `docker-compose.yml`'s `celery-billing` service, `-Q billing`. Register
#: this and forget that and a bill run is accepted, says `queued`, and never
#: runs. `G59` fails when either half is absent, and
#: `tests/test_cr051_billing_queue.py` proves it goes RED on each half
#: separately, because they are two different faults.
BILLING_QUEUE = "billing"

#: How often the calculate gauge is written, in accounts. Every account would be
#: one UPDATE per draft on a table every poll reads; never would make the gauge
#: useless. 25 puts a 1,124-account run at 45 writes and moves the number on
#: screen about twice a second at the import's measured per-row rate. The LAST
#: account always reports regardless, so a finished run never reads "1,100 of
#: 1,124" for ever. This is a display cadence, not a rule, and no signed figure
#: depends on it.
PROGRESS_EVERY = 25

#: CR-051 task 30 — **THE LARGEST RUN THIS DEPLOYMENT ACCEPTS.**
#:
#: The CR states the gap plainly: *"Nothing bounds a run. No
#: `CELERY_TASK_TIME_LIMIT`, no account ceiling. A run that goes wrong at
#: 100,000 accounts runs until it finishes."* Both halves of that are still
#: true of the WORKER — a time limit is a `config/settings` change and is
#: reported rather than taken here — and this is the half billing owns: the
#: number of accounts one run may cover.
#:
#: **WHERE 25,000 COMES FROM — RULED BY THE PRODUCT OWNER ON 2026-09-14, AND THE
#: REASON IS BILLING CYCLES RATHER THAN THE SIZE OF THE BOOK.** PO verbatim:
#: *"(b) Keep 25,000, fix the stale comment only - generally utilities will
#: devide them into nilling cycles and hence 25k limit is good"*.
#:
#: ⚠ **A UTILITY DIVIDES ITS ACCOUNTS INTO BILLING CYCLES, SO NO SINGLE RUN EVER
#: COVERS THE WHOLE BOOK.** A 40,000-account utility at the top of the ICP does
#: not need a 40,000-account run — it bills, say, four cycles of 10,000 — so
#: 25,000 is comfortable headroom for the largest cycle anybody sensibly
#: configures. That is a fact about how utilities OPERATE, held by the Product
#: Owner and by nobody in this repository, which is why it was put to them
#: (CLAUDE.md law 13: *a fact only they hold*) and why no measurement in this
#: repository could have reached it.
#:
#: ⚠ **THIS COMMENT ARGUED FROM BOOK SIZE UNTIL 2026-09-14 AND WAS FALSE
#: (`DEF-BIL-4224`).** It read: *"`CLAUDE.md`'s first line states the product's
#: market: utilities and submetering under 3,000 connections … 25,000 is
#: therefore eight times the largest utility the product is for."* That first
#: line was SUPERSEDED on 2026-09-06 — the ICP ceiling is **40,000** (tier T5) —
#: so the same sentence had come to read **0.625×**, and the recommendation put
#: to the PO was to RAISE the default above 40,000. **They refused it and gave
#: the fact above.** A number smaller than the ICP's ceiling is not by itself a
#: breach: `NFR-5` is NOT breached, because this is a per-RUN operational
#: ceiling and not a per-tenant account cap (`max_accounts` on `plans` stays a
#: commercial tier bound that no code path gates on). **The LIMIT never moved;
#: only its stated reason did, and a stated reason that is false is how a later
#: lane either raises a correct ceiling or stops trusting it.**
#:
#: The other two facts behind the number are MEASUREMENTS and stand unchanged:
#:   * CR-051 task 21 measured the run at **~170 ms per account** on real
#:     PostgreSQL with row-level security enforced. A 10,000-account cycle is
#:     about **28 minutes**; 25,000 is about **70 minutes**.
#:   * `docker-compose.yml` runs the worker at `--concurrency 2` with
#:     `CELERY_WORKER_PREFETCH_MULTIPLIER = 1`, so a 70-minute run occupies
#:     HALF the deployment's background capacity for over an hour.
#:
#: **IT IS A DEPLOYMENT SETTING, AND THE UNSAFE OPTION IS THE ONE YOU TYPE**
#: (hard-won law 3). A genuinely larger utility is not locked out — an operator
#: raises `BILLING_MAX_ACCOUNTS_PER_RUN`, deliberately, having read why it is
#: where it is. `0` disables the ceiling entirely and has to be typed too.
#:
#: ⚠ **AND FOR A WHILE THAT SENTENCE WAS NOT TRUE — `DEF-2806`, fixed in
#: v2.119.0.** No settings module declared `BILLING_MAX_ACCOUNTS_PER_RUN`, so
#: Django never exposed it, the `getattr` below always fell through to this
#: default, and an operator who put `BILLING_MAX_ACCOUNTS_PER_RUN=5000` in
#: `.env` changed nothing and was told nothing. The name is declared in
#: `config/settings/base.py` through `env.int` now, so the override is read;
#: `tests/test_cr051_task30_time_limit.py` holds the settings default equal to
#: this literal so the pair cannot drift. **The shape is worth remembering:
#: `getattr(settings, NAME, DEFAULT)` cannot fail — an undeclared setting is
#: indistinguishable from one deliberately left at its default.**
MAX_ACCOUNTS_PER_RUN_DEFAULT = 25_000

#: What one account costs, MEASURED — CR-051 task 21, real PostgreSQL 16 with
#: row-level security enforced, `10-scripts/cr051_run_benchmark.py`. It is here
#: so the refusal below can say how long an oversized run would take in
#: minutes, which is the only form of that number a clerk can act on.
#:
#: ⚠ **IT IS A MEASUREMENT AND NOT A BUDGET.** Nothing enforces it, nothing
#: fails when a run is slower, and no rule depends on it. When the engine
#: changes, re-run the benchmark and move this; do not reason it forwards.
#: The figures it comes from are published in 12-governance/02-decision-log.md
#: so a later reader can see what world it was taken in — the first version of
#: this figure was 0.137 and was measured with RLS BYPASSED (DEF-2717).
MEASURED_SECONDS_PER_ACCOUNT = 0.17


def max_accounts_per_run() -> int:
    """The ceiling in force, or 0 when an operator has switched it off."""
    from django.conf import settings

    return int(getattr(settings, "BILLING_MAX_ACCOUNTS_PER_RUN", MAX_ACCOUNTS_PER_RUN_DEFAULT))


def refuse_if_oversized(run: models.BillRun) -> int:
    """Refuse a run bigger than this deployment accepts. Returns the size.

    ⚠ **IT REFUSES AT THE DOOR, BEFORE ANY BILL IS DRAFTED, AND THAT IS THE
    WHOLE POINT.** `runs.scope_account_count` answers in two queries; the
    prepare pass it replaces would take the length of the run itself. A ceiling
    discovered half way through a 100,000-account run is not a ceiling, it is a
    crash with drafts behind it.

    **WHAT THE CHECK ITSELF COSTS, stated rather than assumed:** exactly what
    `_prepare_run`'s own first two lines cost, because it is the same two seam
    calls — the cycle's unit ids, then one `COUNT(*)` over the accounts on
    them. At 25,000 units the second is one query with a large `IN` list, which
    is what the run would have done anyway as its very first act.

    **WHAT IT DOES ABOVE THE CEILING**, which is the half CR-051 task 30 asks
    to be stated: it refuses, it names the count and the ceiling, and it names
    the two ways a run is legitimately made smaller — both of which this
    product already has and neither of which needs a rule change:
      * **scope it to fewer services** (`bill_runs.scope_services`, US-BIL-001
        §5: an unchecked service is an explicit recorded choice);
      * **run it per cycle** — a cycle IS the population split, and a utility
        with 100,000 connections has more than one.
    It does NOT silently truncate, and it does not proceed and hope.

    A one-time run (no cycle) is never oversized: it bills ONE named account.

    ⚠ **THE CLERK NOW SEES IT — `DEF-2720`, CLOSED 2026-08-31.** This paragraph
    read *"THE CLERK DOES NOT SEE THIS SENTENCE"* and described why: `api.
    _as_catalog_refusal` mapped every rule refusal on the calculate route onto
    one catalogue entry and put the sentence in `params.detail`, which
    BR-SHL-020 r2 keeps off the screen on purpose, so what a clerk read was
    *"This billing run can't go ahead as asked."* It is rewritten rather than
    left standing, because a stale absence-claim misleads exactly as much as a
    stale guarantee (hard-won law 1).

    **The refusal now names its own key**, `billing.run.tooLarge`, and hands the
    two figures over as PARAMS — so the sentence a clerk reads is composed in
    the catalogue, where all eleven languages are, and the numbers in it are
    these numbers. `detail` below is untouched and still travels: the log and
    the BR-AUD-018 attempt row get the full sentence exactly as before, which is
    where the two ways out belong in the form an engineer wants them.

    ⚠ **THE FIGURES GO AS INTEGERS, NOT AS `"25,000"`.** The sentence below
    groups with commas because it is written for an English log; a pre-grouped
    string would print `25,000` at a German clerk whose language groups with a
    full stop. There is no locale-aware count formatter on the refusal path, so
    an integer is the one form that is never wrong in any of the eleven.
    """
    if run.cycle_id is None:
        return 1
    ceiling = max_accounts_per_run()
    if ceiling <= 0:
        return 0
    scope = run.scope_services
    size = runs.scope_account_count(
        cycle_id=run.cycle_id,
        scope_services=None if scope is None else tuple(scope),
    )
    if size > ceiling:
        raise BillingRuleError(
            f"this run covers {size:,} accounts and this system runs at most "
            f"{ceiling:,} in one pass. At the measured rate a run that size takes "
            f"about {size * MEASURED_SECONDS_PER_ACCOUNT / 60:.0f} minutes and holds "
            "half the background capacity for all of it. Bill it in smaller "
            "pieces: choose fewer "
            "services on the run, or run one billing cycle at a time. Nothing "
            "has been drafted.",
            br_ref="BR-BIL-052",
            message_key="billing.run.tooLarge",
            params={"count": size, "limit": ceiling},
        )
    return size


# ── REFUSE RATHER THAN RUN INLINE ABOVE THE BAR (CR-105-BRC03) ──────────────
#: How long a request has before its answer stops being readable, in seconds.
#:
#: **PUBLISHED BY THE BLUEPRINT, not chosen here.** `05-prototype/04 Billing, As
#: Built.pdf` p050, verbatim: *"Today the clerk presses Prepare and waits on one
#: request. Measured on real PostgreSQL, a run costs 137 ms per account — so
#: 25,000 accounts is about 57 minutes, and the request wall is about 60
#: seconds. There is no version of this where the clerk waits."*
#:
#: It is the gateway/proxy timeout a clerk actually meets, not a Django setting,
#: which is why it is a stated figure rather than something this process can
#: read. If a deployment's proxy is tuned, this and the bar below move together.
REQUEST_WALL_SECONDS = 60

#: **THE BAR: the largest run this product will still work out INSIDE a request
#: when nothing would run it in the background.** Above it, the verb REFUSES.
#:
#: ⚠ **WHAT IT FIXES, in the blueprint's own words (p050, the panel headed
#: *"What it must also do, but cannot be drawn"*):** *"Refuse rather than run
#: inline above the bar — a deployment with no worker runs the check inline
#: today and the request dies long before its own `ran inline` answer can be
#: read."* That was exactly true: `api.run_calculate` and `api.run_findings`
#: asked `would_run()`, and on a `False` they logged a line nobody reads and
#: **ran the whole pass inline anyway**. On a 25,000-account run the clerk got a
#: dead connection at 60 seconds while the server worked for 57 minutes, and the
#: `background: false` member that would have explained it was in a response
#: body that never arrived.
#:
#: ⚠ **WHERE 300 COMES FROM, AND IT IS ARITHMETIC OVER TWO PUBLISHED FIGURES
#: RATHER THAN A NUMBER SOMEBODY LIKED.** `MEASURED_SECONDS_PER_ACCOUNT` below
#: is **0.17** — CR-051 task 21, real PostgreSQL 16 with row-level security
#: ENFORCED, which is the correction of p050's 0.137 (`DEF-2717`, measured with
#: RLS bypassed). The wall is 60 seconds. So the largest run that can finish
#: inside the wall is 60 ÷ 0.17 = **352 accounts**, and the bar is set at
#: **300** — 51 seconds of work, leaving about 9 seconds for everything a
#: request does that is not billing. `test_cr105_run_transport.py` tc5
#: RECOMPUTES that rather than copying it, so moving either input without
#: moving the bar goes RED.
#:
#: ⚠ **IT IS THE FIRST ROW BAR THIS MODULE HAS HAD, AND THE REASON THERE WAS
#: NONE HAS EXPIRED.** `_wants_background` and this file's own docstring both
#: say a bill run has no measured figure to set one from — *"picking a number
#: here would be inventing a figure with no evidence behind it"* — and that was
#: correct when CR-051 made the measurement task 21. **Task 21 has since been
#: run.** This is not a decision about WHETHER work goes to a worker (that is
#: still the caller's `background` flag); it is the much narrower question of
#: what to do when the caller asked for a worker and there is not one.
#:
#: **BELOW THE BAR NOTHING CHANGES.** A small utility running with no broker at
#: all — which is every `JOBS_EAGER` deployment and every demo box — keeps the
#: inline fallback it has today, and that is the whole reason this file chose an
#: inline fallback over the import's flat refusal in the first place.
#:
#: **IT IS A DEPLOYMENT SETTING AND `0` SWITCHES IT OFF** (hard-won law 3: the
#: unsafe option is the one you type). `BILLING_INLINE_ACCOUNT_BAR` is declared
#: in `config/settings/base.py` — declared, because `DEF-2806` is the record of
#: what happens when a module reads `getattr(settings, NAME, DEFAULT)` for a
#: name no settings module exposes: the override is silently ignored and the
#: operator is told nothing.
INLINE_ACCOUNT_BAR_DEFAULT = 300


def inline_account_bar() -> int:
    """The bar in force, or 0 when an operator has switched it off."""
    from django.conf import settings

    return int(getattr(settings, "BILLING_INLINE_ACCOUNT_BAR", INLINE_ACCOUNT_BAR_DEFAULT))


def refuse_if_no_worker(run: models.BillRun, *, reason: str) -> int:
    """Refuse a run too big to work out inside a request. Returns its size.

    Called on the branch where the caller ASKED for background work and
    `would_run()` answered no. Below the bar this returns and the caller falls
    back to inline exactly as it always has; above it, this raises and nothing
    is drafted.

    **THE SENTENCE IS COMPOSED IN THE CATALOGUE, NOT HERE** (`DEF-2720`, and
    BR-SHL-020 r2). `detail` below is the diagnostic — it reaches the log and
    the BR-AUD-018 attempt row, where an engineer wants the queue name and the
    minutes — while what a clerk reads is the entry for `billing.run.noWorker`
    in each of the eleven catalogues, composed from `params`. **The figures go
    as integers and never as `"25,000"`**: a pre-grouped string prints
    `25,000` at a German clerk whose language groups with a full stop.

    ⚠ **`reason` IS FOR THE LOG AND NEVER FOR A SCREEN** (CR-016: no internal
    references in front of a utility). It is `dispatch_is_ready`'s short
    technical phrase — *"no consumer on queue billing"* — and it is not in
    `params`, so it cannot reach the catalogue by accident.

    A one-time run (no cycle) is never above the bar: it bills ONE account,
    which is 0.17 seconds.
    """
    if run.cycle_id is None:
        return 1
    bar = inline_account_bar()
    if bar <= 0:
        return 0
    scope = run.scope_services
    size = runs.scope_account_count(
        cycle_id=run.cycle_id,
        scope_services=None if scope is None else tuple(scope),
    )
    if size > bar:
        logger.warning(
            "run %s covers %s accounts and nothing would run it in the background (%s) — "
            "refusing rather than starting an inline pass the request cannot outlive",
            run.pk,
            size,
            reason,
        )
        raise BillingRuleError(
            f"this run covers {size:,} accounts and nothing is running background work "
            "on this deployment right now. Worked out inside the request it would take "
            f"about {size * MEASURED_SECONDS_PER_ACCOUNT / 60:.0f} minutes, and the "
            f"request gives up after about {REQUEST_WALL_SECONDS} seconds — so the "
            "answer would never reach the screen. Start the billing worker and ask "
            "again. Nothing has been drafted.",
            br_ref="BR-BIL-051",
            message_key="billing.run.noWorker",
            params={"count": size},
        )
    return size


class _JobActor:
    """The actor a WORKER carries: an id, and no role. See the module docstring."""

    __slots__ = ("id",)

    def __init__(self, user_id: Any) -> None:
        self.id = user_id


def _actor_of(record: dict[str, Any]) -> _JobActor | None:
    user_id = (record.get("payload") or {}).get("actor_user_id")
    return None if user_id is None else _JobActor(user_id)


def _run_of(record: dict[str, Any]) -> models.BillRun:
    """The run this job is about, inside the job's own tenant context.

    `run_or_404` is the ONE door onto a run and it filters by the current
    tenant, which `core.jobs.run_job` has already entered from the record
    (B3: a worker never carries one tenant's context into another's job). So a
    job record naming another tenant's run cannot reach one — the same refusal
    a request would get, for the same reason.
    """
    return selectors.run_or_404(record["payload"]["run_id"])


def _instant(payload: dict[str, Any], name: str) -> datetime:
    """An ISO-8601 instant the CALLER named — never a clock (BR-TEN-043 / G6).

    The API layer has already refused a naive or unparseable value at the door
    (`api._datetime_field`), so anything that reaches here is offset-bearing.
    Re-parsing rather than trusting is not distrust of that check: a job payload
    is JSON and JSON has no datetime, so the string is what was stored and the
    string is what must be turned back into an instant.
    """
    return datetime.fromisoformat(str(payload[name]).replace("Z", "+00:00"))


def _progress_reporter(job_id: Any, *, cursor: bool = False) -> Any:
    """`on_progress(done, total, label)` → `core.jobs.record_progress`.

    ⚠ **THIS DOCSTRING SAID "THE CHECKPOINT IS THE COUNT, NOT A CURSOR" AND
    THAT IS NO LONGER TRUE OF CALCULATE — corrected here rather than left
    standing (hard-won law 1).** It read: *"the run does not need one to resume
    correctly (BR-BIL-052 — stage 6 replaces a draft, so a resumed pass
    re-walks and converges), so a cursor would claim a resumption mechanism
    that does not exist and is not needed … CR-051 task 11 is the real
    checkpoint and is not this lane's."* Every clause was correct about
    CORRECTNESS and silent about COST, and CR-051 task 21 has now measured the
    cost: **137 ms per account**, so the re-walk it called free is 22 minutes
    on a 10,000-account run. Task 11 built the cursor and it is
    `apps/billing/run_resume.py`.

    `cursor=True` on the CALCULATE pass only. Findings and issue keep the
    count-shaped marker they had: findings reports once at the end and has no
    per-account loop to resume into, and issue's resumption is the release row
    (`run_issue_job` — a replay finds no pending release and issues nothing),
    which is a stronger guarantee than a cursor and must not be second-guessed
    by one.
    """

    def report(done: int, total: int, label: str) -> None:
        if done % PROGRESS_EVERY and done != total:
            return
        core_jobs.record_progress(
            job_id,
            done=done,
            total=total,
            checkpoint=(
                run_resume.checkpoint(done=done, total=total, account_no=label)
                if cursor
                else {"done": done}
            ),
        )

    return report


#: DEF-BIL-9010 — the stage name a Calculate job's FIRST pass reports under.
PREPARING_STAGE = "preparing"


def calculate_scope(run: Any) -> str:
    """The one scope key a whole-run Calculate job is enqueued under."""
    return f"billing:calculate:{run.pk}"


def active_calculate(run: Any) -> dict[str, Any] | None:
    """DEF-BIL-9010 — this run's queued or running Calculate job, or None.
    One indexed lookup; the run read carries it so a re-opened run shows the
    Calculating progress instead of Sign off over half-written drafts."""
    return core_jobs.find_active(CALCULATE_JOB, calculate_scope(run))


def _preparing_reporter(job_id: Any, total: int | None) -> Any:
    """DEF-BIL-9010 — Calculate's prepare pass, counted.

    A Calculate job reads every account of the run before it drafts any. At
    40,009 accounts that is ~11 minutes, and until this reporter it recorded
    nothing, so the screen read *0 of —* the whole time. It reports
    `{done, total, stage: "preparing"}` every `PROGRESS_EVERY` accounts and
    writes NO checkpoint: the resume cursor belongs to the drafting pass
    (`run_resume`), and an account READ here is not an account DRAFTED.
    """
    done = 0

    def report(_checked: Any) -> None:
        nonlocal done
        done += 1
        if done % PROGRESS_EVERY and done != total:
            return
        core_jobs.record_progress(job_id, done=done, total=total, stage=PREPARING_STAGE)

    return report


# ── enqueue (the API layer's door) ──────────────────────────────────────────
def enqueue_calculate(run: models.BillRun, *, actor_user_id: Any = None) -> dict[str, Any]:
    """Phase 2 to a worker. Returns the job record; the API answers 202.

    CR-051 task 30: the ceiling is checked HERE rather than in the worker, so
    an oversized run is refused while a person is still looking at the screen.
    A worker that discovered it would have nobody to tell.
    """
    refuse_if_oversized(run)
    return core_jobs.enqueue(
        CALCULATE_JOB,
        payload={
            "run_id": str(run.pk),
            "actor_user_id": None if actor_user_id is None else str(actor_user_id),
        },
        scope_key=calculate_scope(run),
    )


def enqueue_reprice(
    run: models.BillRun, account_ids: Any, *, actor_user_id: Any = None
) -> dict[str, Any]:
    """`DEF-BIL-5271`(a) to a worker — the SAME `runs.reprice_accounts` a
    request calls, on billing's own queue and the same progress channel.

    **THE SCOPE KEY CARRIES THE ACCOUNTS AND NOT ONLY THE RUN.** Two clerks
    deciding two different cohorts of one run are two pieces of work and must
    not de-duplicate against each other; the same clerk double-clicking one
    bulk action is one (NFR-16). The set is sorted and hashed rather than
    listed, because a scope key is an index value and a 44-account list is not.
    """
    ids = sorted(str(account_id) for account_id in account_ids if account_id)
    digest = hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()[:16]
    return core_jobs.enqueue(
        REPRICE_JOB,
        payload={
            "run_id": str(run.pk),
            "account_ids": ids,
            "actor_user_id": None if actor_user_id is None else str(actor_user_id),
        },
        scope_key=f"billing:reprice:{run.pk}:{digest}",
    )


def enqueue_findings(run: models.BillRun, *, actor_user_id: Any = None) -> dict[str, Any]:
    """Phase 1's prepare pass to a worker. See `run_findings_job` for what it
    leaves behind and, just as importantly, what it does not."""
    return core_jobs.enqueue(
        FINDINGS_JOB,
        payload={
            "run_id": str(run.pk),
            "actor_user_id": None if actor_user_id is None else str(actor_user_id),
        },
        scope_key=f"billing:findings:{run.pk}",
    )


def enqueue_check(
    run: models.BillRun,
    *,
    only_accounts: Any = None,
    actor_user_id: Any = None,
    categories: Any = None,
) -> dict[str, Any]:
    """The Check (or a re-check of named accounts) to a worker — A3 / A6.

    `categories` (DEF-BIL-8286) narrows a re-check to those categories of the
    Check and what is downstream of them; it is part of the scope key, so a
    payments re-check and a full re-check of the same accounts are two jobs."""
    ids = None if only_accounts is None else sorted(str(one) for one in only_accounts if one)
    cats = None if categories is None else sorted({str(one) for one in categories})
    scope = f"billing:check:{run.pk}"
    if ids is not None:
        digest = hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()[:16]
        scope = f"{scope}:{digest}"
    if cats is not None:
        scope = f"{scope}:{'+'.join(cats)}"
    return core_jobs.enqueue(
        CHECK_JOB,
        payload={
            "run_id": str(run.pk),
            "account_ids": ids,
            "categories": cats,
            "actor_user_id": None if actor_user_id is None else str(actor_user_id),
        },
        scope_key=scope,
    )


def enqueue_issue(
    run: models.BillRun,
    *,
    issued_at: datetime,
    released_at: datetime,
    template_id: Any,
    template_version: int,
    invoice_ids: list[Any] | None = None,
    dispatch_not_before: datetime | None = None,
    actor_user_id: Any = None,
    template_pin_explicit: bool = False,
) -> dict[str, Any]:
    """Phase 5 to a worker.

    Every argument except the run is a fact the CALLER supplied and the worker
    must not re-derive: the two instants (BR-TEN-043), the template pin
    (BR-BIL-026 — a bill issued against an invented pin can never say what
    rendered it), and the optional subset of bills.
    """
    return core_jobs.enqueue(
        ISSUE_JOB,
        payload={
            "run_id": str(run.pk),
            "issued_at": issued_at.isoformat(),
            "released_at": released_at.isoformat(),
            "template_id": str(template_id),
            "template_version": int(template_version),
            "invoice_ids": None if invoice_ids is None else [str(one) for one in invoice_ids],
            "dispatch_not_before": (
                None if dispatch_not_before is None else dispatch_not_before.isoformat()
            ),
            "actor_user_id": None if actor_user_id is None else str(actor_user_id),
            # CR-052 W3 task 12 — whether the caller TYPED that pin. A worker
            # cannot re-derive it (the body is gone by then), which is the same
            # reason every other fact above is carried rather than recomputed.
            # Absent on every job enqueued before this task, and `.get(..., False)`
            # on the read side makes that mean exactly what it meant then.
            "template_pin_explicit": bool(template_pin_explicit),
        },
        scope_key=f"billing:issue:{run.pk}",
    )


def would_run() -> tuple[bool, str]:
    """Would a job enqueued right now actually be EXECUTED? (DEF-2487, law 3.)

    A thin pass-through so the API layer asks `core.jobs` rather than reaching
    for Celery, and so the answer is asked in exactly one place. The `reason` is
    a short technical phrase for the log and NEVER a sentence for a screen
    (CR-016: no internal references in front of a utility).

    ⚠ **IT ASKS ABOUT BILLING'S OWN QUEUE, AND FROM 2026-08-31 THAT IS A
    DIFFERENT QUESTION FROM THE ONE IT USED TO ASK (CR-051 task 29).** Until the
    split, one broadcast ping answered *"will this run"* because there was one
    queue. Now a perfectly healthy `celery` worker answers that ping while the
    `billing` queue has no consumer at all — the `celery-billing` service
    stopped, or shipped without its `-Q billing`. Asking the old question would
    tell a clerk *ready* and then leave the run `queued` for ever, which is
    DEF-320 rebuilt by the change meant to help. `CALCULATE_JOB` stands for all
    three kinds here: they are registered to one queue on purpose.
    """
    return core_jobs.dispatch_is_ready(CALCULATE_JOB)


# ── RESUME GOES BACK TO THE WORKER (DEF-BIL-8511) ──────────────────────────
def _abandon_thresholds() -> tuple[float, float]:
    from django.conf import settings

    return (
        float(getattr(settings, "BILLING_JOB_STALL_SECONDS", 300)),
        float(getattr(settings, "BILLING_JOB_STOPPED_FLOOR_SECONDS", 20)),
    )


def job_is_abandoned(job_id: Any) -> bool:
    """A RUNNING billing job whose worker is gone (`core.jobs.is_abandoned`,
    with this deployment's two thresholds — `config/settings/base.py`).

    B28 — a Check that has HANDED OFF to its batches is executed by no worker
    by design, so the ordinary question would call it abandoned 20 seconds
    after its last *n of N*; it is asked of the batches instead
    (`check_batches.chain_stalled`). DEF-BIL-8710 — a batched SEND
    (`send_batches`) is the same shape and is asked the same way."""
    stall, floor = _abandon_thresholds()
    try:
        record = core_jobs.current(str(job_id))
        if record.get("kind") in (CHECK_JOB, ISSUE_JOB) and (record.get("checkpoint") or {}).get(
            "batches"
        ):
            from apps.billing import check_batches

            return record["status"] == core_jobs.RUNNING and check_batches.chain_stalled(record)
        return core_jobs.is_abandoned(str(job_id), stalled_after=stall, stopped_floor=floor)
    except core_jobs.JobsError:
        return False


def resume_job(run: models.BillRun, job_id: Any) -> tuple[dict[str, Any], str]:
    """The clerk's *Resume*, and the Check screen's own recovery: hand a
    stopped billing job BACK TO THE WORKER — never run it in the request.

    Until 2026-09-30 `check_api.run_check_resume` called `core.jobs.resume`,
    which runs the body in the caller: the rest of a 10,000-account Check
    inside a web request given 60 seconds (DEF-BIL-8511). Now:

    * the run row is LOCKED while the record is decided, so two presses (two
      clerks, or a press and the screen's own poll) put ONE message on the
      queue, never two;
    * the record is reclaimed and requeued under that lock, and handed to the
      transport only AFTER the commit, so a worker never reads it before it
      says `queued`;
    * with no worker on the billing queue it is REFUSED
      (`billing.run.noWorker`), never run here instead — an eager deployment
      answers *ready* and runs it in-process, which is that box's own choice.

    Answers the record and one word (`core.jobs.REDISPATCHED` and the three
    reasons nothing was done)."""
    from django.db import transaction

    ready, reason = would_run()
    if not ready:
        logger.warning("resume of job %s refused: %s", job_id, reason)
        raise BillingRuleError(
            "nothing is running background work for billing right now, so this "
            "run cannot carry on. Start the billing worker and press Resume again. "
            "Nothing checked so far is lost.",
            br_ref="BR-BIL-051",
            message_key="billing.run.noWorker",
            params={"count": 0},
        )
    from apps.billing import check_batches

    stall, floor = _abandon_thresholds()
    # B28 — inside the utility's Check lock too: every write to a Check
    # coordinator's record is made under it (`check_batches` docstring).
    with check_batches.tenant_lock():
        models.BillRun.objects.select_for_update().filter(pk=run.pk).first()
        record, outcome = core_jobs.take_back(
            str(job_id), stalled_after=stall, stopped_floor=floor
        )
        if outcome == core_jobs.REDISPATCHED:
            requeued = dict(record)
            transaction.on_commit(lambda: core_jobs.dispatch(requeued))
    if outcome == core_jobs.REDISPATCHED:
        record = core_jobs.current(str(job_id))
    return record, outcome


# ── the three bodies (the BE-07 runner contract: record → result_link|None) ──
def run_calculate_job(record: dict[str, Any]) -> str | None:
    """Phase 2 in a worker — the SAME `runs.calculate_run` a request calls.

    That sameness is the point: the transport changed and the work did not, so
    everything already proved about the inline pass (BR-BIL-052's per-account
    transaction, BR-BIL-023's draft replacement, BR-BIL-055's a-break-never-
    blocks-the-run) is true here without being re-proved.

    THE DECISIONS ARE FOLDED IN, exactly as `api.run_calculate` does it and for
    the reason recorded there: `decisions.apply_decisions` WRITES (a held
    account gains a `bill_run_exclusions` row), which is why a GET may not reach
    it and why both write paths must call it or a clerk's recorded answer is
    read by nobody.

    NO `result_link`. The metering stages return None for the reason that
    applies here word for word: *"a link built here would have to guess the
    tenant path segment (`core.tenancy.tenant_path` needs the request), and a
    guessed URL in a job record is a link that 404s later."* The client already
    holds the run id it enqueued with, and `GET /billing/runs/{id}` is where the
    answer lives.

    ── CR-051 TASK 11 · A KILLED WORKER RESUMES, IT DOES NOT RE-WALK ──────────
    A re-delivered task reads the checkpoint its own earlier attempt wrote and
    hands `prepare_run` a predicate that skips the accounts that attempt
    finished. **The skip is not a shortcut around idempotency — it is a fourth
    layer of it**, and it is the only one that can make a resumed run FAST:
    layers 1-3 above make a re-walk harmless, and this one makes it
    unnecessary. Measured at 137 ms per account (task 21), a worker killed at
    9,000 of 10,000 was paying 22 minutes to redo finished work.

    **It cannot double-bill, and there are two reasons rather than one.** The
    accounts it skips are exactly those that already carry a draft or a break
    row for this run, so skipping them changes no row; and if the predicate
    were wrong in the other direction — skipping too little — the pass would
    simply re-draft, which BR-BIL-023 has always made safe. `run_resume`'s
    docstring carries the argument for why the predicate needs BOTH a cursor
    and the write before it may answer True.
    """
    run = _run_of(record)
    # CR-051 task 30's backstop. The enqueue already refused an oversized run,
    # so this fires only when the ceiling was LOWERED after the job was queued
    # — which is a real sequence on a deployment being tuned, and the honest
    # answer is the same refusal rather than an hour of work nobody wants.
    refuse_if_oversized(run)
    # CR-051 task 11 — what an EARLIER attempt of this same job already
    # finished. `ResumePlan()` (skip nothing) on a first delivery, which is
    # every enqueue: `core.jobs.enqueue` mints a record with `checkpoint: None`.
    # Only a re-delivered or restarted job carries one, because `core.jobs.
    # start` is explicit that a failed→running transition keeps it.
    plan = run_resume.plan_for(record)
    if plan.resuming:
        logger.info(
            "billing calculate job %s resuming run %s after account %s (%s already done)",
            record["id"],
            run.pk,
            plan.resume_after,
            plan.already_done,
        )
    prepared = selectors.prepared_for(
        run,
        resume_skip=run_resume.skip_predicate(plan, run),
        on_account=_preparing_reporter(record["id"], _check_total(run)),
    )
    prepared = decisions.apply_decisions(prepared, bill_run=run)
    runs.calculate_run(
        prepared,
        bill_run=run,
        on_progress=_progress_reporter(record["id"], cursor=True),
        job_id=record["id"],
        already_done=plan.already_done,
    )
    return None


def run_reprice_job(record: dict[str, Any]) -> str | None:
    """`DEF-BIL-5271`(a) in a worker — the same function a request calls.

    That sameness is the point, exactly as it is for `run_calculate_job`: the
    transport changed and the work did not, so BR-BIL-023's draft replacement
    and BR-BIL-052's per-account transaction are true here without being
    re-proved.

    **NO RESUME PLAN, AND THE REASON IS THE SIZE.** `run_calculate_job` reads a
    checkpoint because a killed worker at account 9,000 of 10,000 would pay 22
    minutes to redo finished work (`CR-051` task 21). A re-price covers the
    accounts one decision touched; re-walking it is seconds, and a checkpoint
    would be machinery guarding a cost nobody would notice. If a re-price is
    ever measured at run scale, `reprice_accounts` takes the same
    `prepare_run(resume_skip=…)` hook the full pass does.
    """
    run = _run_of(record)
    account_ids = (record.get("payload") or {}).get("account_ids") or []
    runs.reprice_accounts(
        bill_run=run,
        account_ids=account_ids,
        bill_type=run.bill_type,
        on_progress=_progress_reporter(record["id"]),
        job_id=record["id"],
    )
    return None


def run_findings_job(record: dict[str, Any]) -> str | None:
    """Phase 1's prepare pass in a worker — and it records COUNTS, not a cache.

    ⚠ **READ THIS BEFORE MAKING IT SERVE THE CASE LISTS.** `selectors.
    prepared_for` records a deliberate design constraint: a prepare pass is
    *"recomputed on every call and cached nowhere … a clerk who fixes a plan and
    reloads must see the fix; a cached findings set would show them the world as
    it was when they first opened the wizard."* That still holds, and
    `GET /billing/runs/{id}/findings` is unchanged — it still recomputes.

    So what this job leaves behind is `bill_runs.findings_summary`: the COUNTS
    the pass found, and the job that found them. A clerk who closed the tab can
    be told *"the pass finished — 1,124 accounts, 6 blocked, 18 waiting on a
    decision"* without a second five-minute pass. What it does NOT do is spare
    them the pass when they open the case tables, and that is stated on the
    calculate/findings responses rather than left to be discovered.

    **Whether the case LISTS may be snapshotted is `OQ-843` and is NOT decided
    here.** It is a product question — a clerk reading a five-minute-old case
    table against a world that has moved is a different behaviour from what
    ships today — and the prime directive forbids a lane resolving one by
    choosing a value.
    """
    run = _run_of(record)
    prepared = selectors.prepared_for(run)
    total = prepared.account_count
    core_jobs.record_progress(record["id"], done=total, total=total, checkpoint={"done": total})
    # ⚠ ONE COLUMN MOVES, AND IT IS A COLUMN NO BILL READS. `bill_runs` carries
    # no money and this write touches neither the run's scope nor its dates, so
    # a findings pass can never change what the run would bill.
    run.findings_summary = {
        "job_id": str(record["id"]),
        "accounts": total,
        "ready": len(prepared.ready),
        "blocked": len(prepared.blocked),
        "decisions": len(prepared.decisions),
        # `BR-BIL-1025` — accounts examined and found to have nothing to
        # charge. Stored beside `blocked` and never inside it: the stored
        # summary is what a re-opened run screen reads, and a silent account
        # counted as blocked would put an exception count on a run that had
        # none.
        "silent": len(prepared.silent),
        "blocked_by_reason": {
            reason: len(items) for reason, items in prepared.blocked_by_reason().items()
        },
    }
    run.save(update_fields=["findings_summary", "updated_at"])
    return None


def _check_total(run: models.BillRun) -> int | None:
    """How many accounts a whole-run Check will walk — `runs.scope_account_count`,
    the count the run's own size ceiling uses. None when it cannot be counted
    (an unknown total shows as an indeterminate bar, never a guessed N)."""
    try:
        scope = run.scope_services
        return runs.scope_account_count(
            cycle_id=run.cycle_id,
            scope_services=None if scope is None else tuple(scope),
        )
    except Exception:  # noqa: BLE001 — a count is display, never the Check
        return None


def run_check_job(record: dict[str, Any]) -> Any:
    """The Check in a worker: the COORDINATOR of its batches of 500 (B28).

    A whole run, a catch-up run and a re-check of NAMED accounts are planned
    in batches of 500 and handed to batch jobs, at most `batch_cap()` of this
    utility's at once (`check_batches.start`); the job's record stays
    `running`, its progress is the sum of every batch, and the last batch to
    finish counts the run's totals once and succeeds it. A re-delivered or
    resumed coordinator re-dispatches only the batches that did not finish.

    A re-check of only some CATEGORIES (DEF-BIL-8286) is not batched: it is a
    re-check of the accounts a fix touched, read in one pass as before.

    The actor has no role (G140): nothing on this path is role-guarded; the
    role was checked on the request that enqueued. A utility-wide stop is
    recorded on the run (`findings_summary.stop`) and fails the job with a
    sentence a clerk can act on; the run is kept.
    """
    from apps.billing import check_batches, check_store

    payload = record.get("payload") or {}
    categories = payload.get("categories")
    if categories is None:
        return check_batches.start(record)
    run = _run_of(record)
    only = payload.get("account_ids")
    total = len(only) if only is not None else _check_total(run)
    core_jobs.record_progress(record["id"], done=0, total=total, checkpoint={"done": 0})

    def progress(done: int, account_no: str) -> None:
        if done % PROGRESS_EVERY:
            return
        core_jobs.record_progress(
            record["id"], done=done, total=total, checkpoint={"done": done, "account_no": account_no}
        )

    summary = check_store.check_run(
        run, only_accounts=only, on_progress=progress, job_id=record["id"], categories=categories
    )
    final = int(summary.get("accounts") or 0)
    core_jobs.record_progress(
        record["id"], done=final, total=final, checkpoint={"done": final, "finished": True}
    )
    return None


def run_check_batch_job(record: dict[str, Any]) -> Any:
    """ONE batch of a Check, in a worker (B28) — `check_batches.run_batch`."""
    from apps.billing import check_batches

    return check_batches.run_batch(record)


def run_issue_batch_job(record: dict[str, Any]) -> Any:
    """ONE batch of a Send, in a worker (DEF-BIL-8726) — `send_batches.run_batch`."""
    from apps.billing import send_batches

    return send_batches.run_batch(record)


def run_issue_job(record: dict[str, Any]) -> str | None:
    """Phase 5 in a worker — the COORDINATOR of the Send's batches of 500
    (`send_batches`, DEF-BIL-8726), with the caller's instants. Each batch runs
    `issue.issue_run` over its own bills and the last completes the release with
    `release.complete_release`, the end `release.release_run` has inline.

    🔒 THIS BODY CROSSES INTO FINANCIAL IMMUTABILITY. After it returns, a bill it
    issued cannot be un-issued, only corrected by new rows (hard rule 4). Three
    things therefore hold and each is load-bearing:

    * **The gate is not re-checked HERE and must not be.** `release_run` refuses
      an unconfirmed row and `issue_run` refuses a run with no authorised
      release (BR-BIL-058, US-BIL-005 TC-14). Adding a third, weaker copy in a
      worker would be a fourth place for that decision to live.
    * **A REPLAY DOES NOTHING, and the ordering says why.** `pending_releases`
      finds authorised-but-not-released; if a re-delivered task finds none, the
      release has already completed and this returns without issuing — the same
      answer `POST .../issue` gives a double-clicked Send (200, `created:
      false`). It is not an error and must not be recorded as one, because a
      failed record over completed work is what sends someone to re-run it.
    * **The instants are the caller's** (BR-TEN-043). See `_instant`.

    A BREAK STILL NEVER BLOCKS THE RUN (BR-BIL-055): 499 issue and one comes
    back named. That is `issue_run`'s property and running in a worker does not
    change it.
    """
    run = _run_of(record)
    release_row = release.pending_releases(run).first()
    if release_row is None:
        # A REPLAY, not a failure — see the docstring. `completed_releases`
        # tells a replay from a forgery, and a forgery cannot reach here at all:
        # the enqueueing route already refused it (US-BIL-005 TC-14).
        done = release.completed_releases(run).first()
        logger.info(
            "billing issue job %s: run %s has no authorised unreleased row (%s) — "
            "nothing issued, nothing re-issued",
            record["id"],
            run.pk,
            "already released" if done is not None else "never authorised",
        )
        return None
    # ── DEF-BIL-8726 / DEF-BIL-8710 — THE SEND IN BATCHES OF 500 ───────────
    # Until 2026-10-01 this called `release.release_run` over every draft in
    # ONE task: a 40,008-bill Send at the measured 1.9 bills a second would
    # have been stopped by its own 8,520 s time limit after ~16,000 bills, and
    # a worker that died left it `running` for ever with nothing to hand it
    # back. The coordinator now plans, dispatches its batches and HANDS OFF;
    # the last batch completes the release with `release.complete_release` —
    # the same end `release_run` has. The two replay answers above are
    # unchanged, and a RESUMED coordinator reaches here with its plan in its
    # checkpoint and re-dispatches only the batches that did not finish.
    from apps.billing import send_batches

    return send_batches.start(record, release_row)


def register() -> None:
    """Register the three bodies. Called from `BillingConfig.ready`.

    Here rather than inline in `apps.py` so the kind→body mapping lives beside
    the bodies: `core/jobs.py`'s contract is that the module owning the WORK
    owns its registration, and a kind whose handler is registered in a different
    file is a kind somebody will one day rename in one place.
    """
    core_jobs.set_job_handler(CALCULATE_JOB, run_calculate_job)
    core_jobs.set_job_handler(FINDINGS_JOB, run_findings_job)
    core_jobs.set_job_handler(ISSUE_JOB, run_issue_job)
    core_jobs.set_job_handler(REPRICE_JOB, run_reprice_job)
    core_jobs.set_job_handler(CHECK_JOB, run_check_job)
    core_jobs.set_job_handler(CHECK_BATCH_JOB, run_check_batch_job)
    core_jobs.set_job_handler(ISSUE_BATCH_JOB, run_issue_batch_job)
    # CR-051 task 29 — the ROUTING half of billing's named queue, registered
    # beside the bodies for the same reason the bodies are registered here: the
    # module that owns the WORK owns the statement about where it runs, and a
    # kind whose queue is declared in a different file is a kind somebody will
    # one day rename in one place. All three, deliberately: splitting the run's
    # calculate off from its issue would put two halves of one bill run on two
    # queues with two different CPU shares, and nothing would say so.
    for kind in RUN_JOBS:
        core_jobs.set_job_queue(kind, BILLING_QUEUE)


__all__ = [
    "BILLING_QUEUE",
    "CALCULATE_JOB",
    "INLINE_ACCOUNT_BAR_DEFAULT",
    "MAX_ACCOUNTS_PER_RUN_DEFAULT",
    "MEASURED_SECONDS_PER_ACCOUNT",
    "REQUEST_WALL_SECONDS",
    "inline_account_bar",
    "max_accounts_per_run",
    "refuse_if_no_worker",
    "refuse_if_oversized",
    "FINDINGS_JOB",
    "ISSUE_JOB",
    "REPRICE_JOB",
    "RUN_JOBS",
    "BillingRuleError",
    "enqueue_calculate",
    "enqueue_findings",
    "enqueue_issue",
    "enqueue_reprice",
    "register",
    "run_calculate_job",
    "run_findings_job",
    "run_issue_job",
    "run_reprice_job",
    "CHECK_JOB",
    "CHECK_BATCH_JOB",
    "enqueue_check",
    "run_check_job",
    "run_check_batch_job",
    "ISSUE_BATCH_JOB",
    "run_issue_batch_job",
    "would_run",
    "job_is_abandoned",
    "resume_job",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-051@tasks8-10 (12-governance/11-change-requests.md §CR-051 tasks 4/8/9/10 · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-051..055 · core/jobs.py's BE-07 contract)
# generated: 2026-08-30 by the CR-051 W0/W1/W2 backend lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — CR-051 task 12 is another lane's; 07-frontend was not touched by this lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests/test_cr051_run_jobs_and_breaks.py (RED-proved first; verbatim failures in the report) · the transaction-sensitive cases re-run against real PostgreSQL under config.settings.local (CLAUDE.md law 14) · golden 33/33 unchanged — no ❄️ B4/B5 figure is reachable from this file
# exceptions: (1) `background: true` is the CALLER's flag and not a measured row
#         bar, because no timing figure for a bill run exists anywhere in this
#         repo (CR-051 task 21 measures it) and inventing one is inventing a
#         figure · (2) with no worker running, `background` falls back to INLINE
#         rather than refusing as the import does — the work is DONE when the
#         response returns, so nothing is queued into a void; the divergence
#         from `import_runs._refuse_no_worker` is deliberate and recorded in
#         12-governance/02-decision-log.md · (3) no `result_link` on any of the
#         three: a link built in a worker would have to guess the tenant path
#         segment, and a guessed URL in a job record is a link that 404s later
#         (the metering precedent, verbatim) · (4) `run_findings_job` records
#         COUNTS and not the case lists — snapshotting the lists is OQ-843 and a
#         lane may not close it by choosing · (5) this file is NOT in
#         10-scripts/gates/human_owned.txt: adding a glob there is a process
#         event the PO owns (that file's own header), so the markers and the
#         ledger row are here and the glob is REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
